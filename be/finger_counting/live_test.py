import cv2
import torch
import mediapipe as mp
import numpy as np
import collections
from torchvision.transforms import v2
from PIL import Image
from model import FingerCNN
import torch.nn.functional as F

def main():
    # 1. Device configuration
    if torch.cuda.is_available():
        device = torch.device('cuda')
    elif torch.backends.mps.is_available():
        device = torch.device('mps')
    else:
        device = torch.device('cpu')
    print(f"Running on device: {device}")

    # 2. Load the trained model
    model = FingerCNN().to(device)
    model.load_state_dict(torch.load('finger_cnn_model.pth', map_location=device, weights_only=True))
    model.eval()

    # 3. Define transformations (No thresholding, just grayscale and normalization)
    transform = v2.Compose([
        v2.ToImage(),
        v2.ToDtype(torch.float32, scale=True),
        v2.Normalize(mean=[0.5], std=[0.5])
    ])

    # 4. Initialize MediaPipe Hands
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7
    )

    # Buffer for temporal smoothing (stops flickering)
    prediction_buffer = collections.deque(maxlen=10)

    # 5. Start Video Capture
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    print("Press 'q' to quit the application.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb_frame)

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

                # Get baseline palm size (distance from wrist to middle knuckle)
                wrist_y = int(hand_landmarks.landmark[0].y * h)
                knuckle_y = int(hand_landmarks.landmark[9].y * h)
                palm_height = abs(wrist_y - knuckle_y)
                
                # Enforce a minimum bounding box size (prevents extreme zoom on fists)
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
                
                # NEW: Force the bounding box to be a perfect square to prevent squishing
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
                
                # Draw the square bounding box
                cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)
                
                # Crop exactly to the hand
                roi = frame[y_min:y_max, x_min:x_max]

                if roi.size != 0 and roi.shape[0] > 0 and roi.shape[1] > 0:
                    # 1. Create a blank mask for the hand
                    mask = np.zeros(roi.shape[:2], dtype=np.uint8)
                    
                    # Helper function to get mapped ROI coordinates for any landmark
                    def get_pt(idx):
                        return (int(hand_landmarks.landmark[idx].x * w) - x_min, 
                                int(hand_landmarks.landmark[idx].y * h) - y_min)

                    # Dynamic thickness based on how close the hand is to the camera
                    roi_width = x_max - x_min
                    finger_thickness = max(3, int(roi_width * 0.07)) 

                    # 2. Draw the Palm (tight polygon connecting wrist and base knuckles)
                    palm_indices = [0, 1, 5, 9, 13, 17]
                    palm_pts = np.array([get_pt(i) for i in palm_indices], np.int32)
                    cv2.fillPoly(mask, [palm_pts], 255)
                    
                    # 3. Draw the Fingers (thick lines along the skeleton)
                    finger_groups = [
                        [1, 2, 3, 4],       # Thumb
                        [5, 6, 7, 8],       # Index
                        [9, 10, 11, 12],    # Middle
                        [13, 14, 15, 16],   # Ring
                        [17, 18, 19, 20]    # Pinky
                    ]
                    
                    for group in finger_groups:
                        for i in range(len(group) - 1):
                            pt1 = get_pt(group[i])
                            pt2 = get_pt(group[i+1])
                            
                            # Tapering logic: Base joints get full thickness, tips get half thickness
                            if i == 0:
                                current_thickness = finger_thickness
                            else:
                                current_thickness = max(2, finger_thickness // 2)
                                
                            # Draw tapered bone
                            cv2.line(mask, pt1, pt2, 255, thickness=current_thickness)
                            # Draw circular joints
                            cv2.circle(mask, pt2, current_thickness // 2, 255, -1)

                    kernel = np.ones((3,3), np.uint8)
                    mask = cv2.dilate(mask, kernel, iterations=1)
                    
                    # NEW: Blur the mask to create a soft, natural photographic edge
                    mask = cv2.GaussianBlur(mask, (11, 11), 0)
                    
                    # 4. Apply the tight skeleton mask
                    black_bg_roi = cv2.bitwise_and(roi, roi, mask=mask)
                    
                    # 5. Preprocess for the CNN
                    gray_roi = cv2.cvtColor(black_bg_roi, cv2.COLOR_BGR2GRAY)
                    resized_roi = cv2.resize(gray_roi, (128, 128))
                    
                    pil_img = Image.fromarray(resized_roi)
                    input_tensor = transform(pil_img).unsqueeze(0).to(device)
                    
                    # Run Inference
                    with torch.no_grad():
                        outputs = model(input_tensor)
                        
                        # Convert raw model outputs to probabilities (0.0 to 1.0)
                        probabilities = F.softmax(outputs, dim=1)
                        confidence, predicted = torch.max(probabilities, 1)
                        
                        prediction = predicted.item()
                        conf_score = confidence.item()

                    # 1. Confidence Threshold: Only accept if the CNN is >85% sure
                    if conf_score > 0.85:
                        prediction_buffer.append(prediction)
                    else:
                        prediction_buffer.append(None) # None represents an invalid/uncertain frame

                    # Find the most common item in the smoothing buffer
                    smooth_prediction = max(set(prediction_buffer), key=prediction_buffer.count)

                    # 2. Stability Threshold: Only show text if it's a valid number AND 
                    # at least 6 out of the last 10 frames agree on the exact same number.
                    if smooth_prediction is not None and prediction_buffer.count(smooth_prediction) >= 6:
                        cv2.putText(frame, f"Fingers: {smooth_prediction}", (x_min, y_min - 10), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

                    # Show what the CNN sees
                    cv2.imshow('Model Input View (Masked)', resized_roi)

        cv2.imshow('Live Finger Counting', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()