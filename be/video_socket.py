# video_socket.py
import cv2
import torch
import mediapipe as mp
import numpy as np
import collections
import base64
import asyncio
from torchvision.transforms import v2
from PIL import Image
from finger_counting.model import FingerCNN
import torch.nn.functional as F

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# Create a router for the WebSocket
router = APIRouter()

# --- ML Model Global Setup ---
device = torch.device('cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu')
print(f"Running ML on device: {device}")

model = FingerCNN().to(device)
model.load_state_dict(torch.load('finger_counting/finger_cnn_model.pth', map_location=device, weights_only=True))
model.eval()

transform = v2.Compose([
    v2.ToImage(),
    v2.ToDtype(torch.float32, scale=True),
    v2.Normalize(mean=[0.5], std=[0.5])
])

mp_hands = mp.solutions.hands

# --- WebSocket Route ---
@router.websocket("/ws/video")
async def video_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7
    )
    prediction_buffer = collections.deque(maxlen=10)
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        await websocket.close()
        return

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                await asyncio.sleep(0.1)
                continue

            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb_frame)
            
            smooth_prediction = None

            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    x_min, y_min = w, h
                    x_max, y_max = 0, 0
                    
                    for lm in hand_landmarks.landmark:
                        x, y = int(lm.x * w), int(lm.y * h)
                        if x < x_min: x_min = x
                        if x > x_max: x_max = x
                        if y < y_min: y_min = y
                        if y > y_max: y_max = y

                    wrist_y = int(hand_landmarks.landmark[0].y * h)
                    knuckle_y = int(hand_landmarks.landmark[9].y * h)
                    palm_height = abs(wrist_y - knuckle_y)
                    min_box_size = int(palm_height * 2.5)
                    
                    box_w = x_max - x_min
                    box_h = y_max - y_min
                    
                    if box_w < min_box_size:
                        pad_x = (min_box_size - box_w) // 2
                        x_min = max(0, x_min - pad_x)
                        x_max = min(w, x_max + pad_x)
                        
                    if box_h < min_box_size:
                        pad_y = (min_box_size - box_h) // 2
                        y_min = max(0, y_min - pad_y)
                        y_max = min(h, y_max + pad_y)
                    
                    pad = 40
                    y_min = max(0, y_min - pad)
                    y_max = min(h, y_max + pad)
                    x_min = max(0, x_min - pad)
                    x_max = min(w, x_max + pad)
                    
                    box_w = x_max - x_min
                    box_h = y_max - y_min
                    
                    if box_w > box_h:
                        diff = box_w - box_h
                        y_min = max(0, y_min - diff // 2)
                        y_max = min(h, y_max + diff - (diff // 2))
                    elif box_h > box_w:
                        diff = box_h - box_w
                        x_min = max(0, x_min - diff // 2)
                        x_max = min(w, x_max + diff - (diff // 2))
                    
                    cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)
                    roi = frame[y_min:y_max, x_min:x_max]

                    if roi.size != 0 and roi.shape[0] > 0 and roi.shape[1] > 0:
                        mask = np.zeros(roi.shape[:2], dtype=np.uint8)
                        def get_pt(idx):
                            return (int(hand_landmarks.landmark[idx].x * w) - x_min, 
                                    int(hand_landmarks.landmark[idx].y * h) - y_min)

                        roi_width = x_max - x_min
                        finger_thickness = max(3, int(roi_width * 0.07)) 

                        palm_indices = [0, 1, 5, 9, 13, 17]
                        palm_pts = np.array([get_pt(i) for i in palm_indices], np.int32)
                        cv2.fillPoly(mask, [palm_pts], 255)
                        
                        finger_groups = [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16], [17, 18, 19, 20]]
                        for group in finger_groups:
                            for i in range(len(group) - 1):
                                pt1 = get_pt(group[i])
                                pt2 = get_pt(group[i+1])
                                current_thickness = finger_thickness if i == 0 else max(2, finger_thickness // 2)
                                cv2.line(mask, pt1, pt2, 255, thickness=current_thickness)
                                cv2.circle(mask, pt2, current_thickness // 2, 255, -1)

                        kernel = np.ones((3,3), np.uint8)
                        mask = cv2.dilate(mask, kernel, iterations=1)
                        mask = cv2.GaussianBlur(mask, (11, 11), 0)
                        
                        black_bg_roi = cv2.bitwise_and(roi, roi, mask=mask)
                        gray_roi = cv2.cvtColor(black_bg_roi, cv2.COLOR_BGR2GRAY)
                        resized_roi = cv2.resize(gray_roi, (128, 128))
                        
                        pil_img = Image.fromarray(resized_roi)
                        input_tensor = transform(pil_img).unsqueeze(0).to(device)
                        
                        with torch.no_grad():
                            outputs = model(input_tensor)
                            probabilities = F.softmax(outputs, dim=1)
                            confidence, predicted = torch.max(probabilities, 1)
                            prediction = predicted.item()
                            conf_score = confidence.item()

                        if conf_score > 0.85:
                            prediction_buffer.append(prediction)
                        else:
                            prediction_buffer.append(None)

                        if len(prediction_buffer) > 0:
                            temp_smooth = max(set(prediction_buffer), key=prediction_buffer.count)
                            if temp_smooth is not None and prediction_buffer.count(temp_smooth) >= 6:
                                smooth_prediction = temp_smooth

            _, buffer = cv2.imencode('.jpg', frame)
            frame_base64 = base64.b64encode(buffer).decode('utf-8')
            
            await websocket.send_json({
                "image": frame_base64,
                "prediction": smooth_prediction
            })
            
            await asyncio.sleep(0.01)

    except WebSocketDisconnect:
        print("React Client Disconnected")
    finally:
        cap.release()
        hands.close()