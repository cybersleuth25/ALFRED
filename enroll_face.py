import cv2
import json
import numpy as np
import os
import time

FACE_DETECTION_MODEL = "face_detection_yunet_2023mar.onnx"
FACE_RECOGNITION_MODEL = "face_recognition_sface_2021dec.onnx"
OUTPUT_FILE = "authorized_face.json"
OUTPUT_IMG = "authorized_face.jpg"

if not os.path.exists(FACE_DETECTION_MODEL) or not os.path.exists(FACE_RECOGNITION_MODEL):
    print("Error: Face models not found. Please ensure they are downloaded.")
    exit(1)

# Initialize OpenCV Face Recognizer
detector = cv2.FaceDetectorYN.create(FACE_DETECTION_MODEL, "", (320, 320), 0.9, 0.3, 5000)
recognizer = cv2.FaceRecognizerSF.create(FACE_RECOGNITION_MODEL, "")

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Error: Could not open webcam.")
    exit(1)

print("\n" + "="*50)
print("FACIAL ENROLLMENT")
print("="*50)
print("Please look directly into the camera.")
print("Press 'c' to capture your face, or 'q' to quit.")

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    display_frame = frame.copy()
    
    # Resize frame for detection
    height, width, _ = frame.shape
    detector.setInputSize((width, height))
    
    # Detect face
    _, faces = detector.detect(frame)
    
    if faces is not None and len(faces) > 0:
        # Draw box around the first face
        face = faces[0]
        box = list(map(int, face[:4]))
        cv2.rectangle(display_frame, (box[0], box[1]), (box[0]+box[2], box[1]+box[3]), (0, 255, 0), 2)
        cv2.putText(display_frame, "Face Detected - Press 'c' to Capture", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    else:
        cv2.putText(display_frame, "No face detected...", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
    cv2.imshow("Enrollment", display_frame)
    
    key = cv2.waitKey(1) & 0xFF
    if key == ord('c') and faces is not None and len(faces) > 0:
        # Extract features
        face = faces[0]
        aligned_face = recognizer.alignCrop(frame, face)
        feature = recognizer.feature(aligned_face)
        
        # Save feature to JSON and image to disk
        feature_list = feature[0].tolist()
        with open(OUTPUT_FILE, "w") as f:
            json.dump({"face_vector": feature_list}, f)
            
        cv2.imwrite(OUTPUT_IMG, frame)
        print(f"\n[Success] Face captured and saved to {OUTPUT_FILE} and {OUTPUT_IMG}!")
        break
    elif key == ord('q'):
        print("\n[Cancelled]")
        break

cap.release()
cv2.destroyAllWindows()
