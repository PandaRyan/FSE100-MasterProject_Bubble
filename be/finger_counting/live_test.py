import cv2
import torch
from torchvision.transforms import v2
from PIL import Image
from model import FingerCNN

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
    model.eval() # Set to evaluation mode

    # 3. Define the exact same transformations used during testing
    transform = v2.Compose([
        v2.ToImage(),
        v2.ToDtype(torch.float32, scale=True),
        v2.Normalize(mean=[0.5], std=[0.5])
    ])

    # 4. Start Video Capture
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    print("Press 'q' to quit the application.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Flip the frame horizontally for a mirror effect
        frame = cv2.flip(frame, 1)

        # Define Region of Interest (ROI) coordinates (Larger 400x400 box)
        box_size = 400
        x1, y1 = 300, 100
        x2, y2 = x1 + box_size, y1 + box_size
        
        # Draw the ROI box on the frame
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # Extract the ROI from the frame
        roi = frame[y1:y2, x1:x2]

        if roi.size != 0:
            # Preprocess the ROI: Grayscale
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            
            # Thresholding to separate hand from background clutter
            blurred = cv2.GaussianBlur(gray_roi, (5, 5), 0)
            _, thresholded_roi = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Resize to match model input (128x128)
            resized_roi = cv2.resize(thresholded_roi, (128, 128))
            
            # Convert OpenCV numpy array to PIL Image
            pil_img = Image.fromarray(resized_roi)
            
            # Apply PyTorch transforms and add batch dimension [1, 1, 128, 128]
            input_tensor = transform(pil_img).unsqueeze(0).to(device)
            
            # Run Inference
            with torch.no_grad():
                outputs = model(input_tensor)
                _, predicted = torch.max(outputs.data, 1)
                prediction = predicted.item()

            # Display the prediction on the screen
            cv2.putText(frame, f"Fingers: {prediction}", (x1, y1 - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            # Optional: Show the thresholded view in a tiny window to debug what the model "sees"
            cv2.imshow('What the model sees (Thresholded)', thresholded_roi)

        # Show the full frame
        cv2.imshow('Live Finger Counting', frame)

        # Exit on 'q' key
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Clean up
    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()