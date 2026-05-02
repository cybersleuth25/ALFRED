import cv2
import threading
import time
import json
import os
import shared
import numpy as np

FACE_DETECTION_MODEL = os.path.join(os.path.dirname(__file__), "face_detection_yunet_2023mar.onnx")
FACE_RECOGNITION_MODEL = os.path.join(os.path.dirname(__file__), "face_recognition_sface_2021dec.onnx")
AUTHORIZED_FACE_FILE = os.path.join(os.path.dirname(__file__), "authorized_face.json")

_latest_frame = None
_running = False
_unauthorized_strikes = 0

def get_latest_frame():
    return _latest_frame

def start_security_daemon():
    global _running
    if _running: return
    _running = True
    t = threading.Thread(target=_security_loop, daemon=True, name="SecurityEngine")
    t.start()
    print("[System] Security Engine (Facial Verification) started.")

def _security_loop():
    global _latest_frame, _running, _unauthorized_strikes
    
    if not os.path.exists(FACE_DETECTION_MODEL) or not os.path.exists(FACE_RECOGNITION_MODEL):
        print("[Security Engine] Face models missing. Daemon disabled.")
        return
        
    authorized_vector = None
    if os.path.exists(AUTHORIZED_FACE_FILE):
        try:
            with open(AUTHORIZED_FACE_FILE, 'r') as f:
                data = json.load(f)
                authorized_vector = data.get("face_vector")
        except Exception as e:
            print(f"[Security Engine] Error loading authorized face: {e}")

    try:
        detector = cv2.FaceDetectorYN.create(FACE_DETECTION_MODEL, "", (320, 320), 0.9, 0.3, 5000)
        recognizer = cv2.FaceRecognizerSF.create(FACE_RECOGNITION_MODEL, "")
    except Exception as e:
        print(f"[Security Engine] Error initializing OpenCV Face Recognizer: {e}")
        return

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[Security Engine] Webcam unavailable.")
        return

    while _running:
        ret, frame = cap.read()
        if not ret:
            time.sleep(1)
            continue
            
        _latest_frame = frame.copy()
        
        # We process the face every ~3 seconds to save CPU
        time.sleep(3)
        
        height, width, _ = frame.shape
        detector.setInputSize((width, height))
        _, faces = detector.detect(frame)
        
        if faces is not None and len(faces) > 0 and authorized_vector:
            face = faces[0]
            aligned_face = recognizer.alignCrop(frame, face)
            feature = recognizer.feature(aligned_face)
            
            # SFace cosine similarity (lowered threshold to 0.25 for better tolerance)
            auth_arr = np.array(authorized_vector, dtype=np.float32).reshape(1, 128)
            score = recognizer.match(auth_arr, feature, cv2.FaceRecognizerSF_FR_COSINE)
            
            print(f"[Security Engine] Face check score: {score:.3f}")
            
            if score >= 0.25:
                shared.face_present = True
                _unauthorized_strikes = 0  # Reset strikes
                
                # Auto-Wake Logic
                if not getattr(shared, 'alfred_awake', False):
                    shared.force_wake = True
            else:
                _unauthorized_strikes += 1
                print(f"[Security Engine] Low score warning ({_unauthorized_strikes}/3 strikes)")
                
                if _unauthorized_strikes >= 3:
                    shared.face_present = False
                    
                    # Security Lock Logic
                    print(f"\n[Security] Unauthorized face confirmed! Locking PC.")
                    os.system("rundll32.exe user32.dll,LockWorkStation")
                    
                    # Sleep a bit longer after locking
                    time.sleep(10)
        else:
            shared.face_present = False
            _unauthorized_strikes = 0 # If no face is detected at all, don't increase strikes (user walked away)

    cap.release()
