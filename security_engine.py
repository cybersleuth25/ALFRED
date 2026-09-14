import cv2
import threading
import time
import json
import os
import subprocess
import datetime
import shared
import numpy as np

FACE_DETECTION_MODEL = os.path.join(os.path.dirname(__file__), "face_detection_yunet_2023mar.onnx")
FACE_RECOGNITION_MODEL = os.path.join(os.path.dirname(__file__), "face_recognition_sface_2021dec.onnx")
AUTHORIZED_FACE_FILE = os.path.join(os.path.dirname(__file__), "authorized_face.json")

_latest_frame = None
_running = False
_unauthorized_strikes = 0
_frame_lock = threading.Lock()
_daemon_thread = None

def get_latest_frame():
    with _frame_lock:
        return _latest_frame.copy() if _latest_frame is not None else None

def is_running():
    """Returns True if the security daemon is active."""
    return _running

def stop_security_daemon():
    """Gracefully stops the security daemon and releases the camera."""
    global _running
    _running = False
    if _daemon_thread and _daemon_thread.is_alive():
        _daemon_thread.join(timeout=10)
    print("[System] Security Engine stopping — camera will be released.")

def start_security_daemon():
    global _running, _daemon_thread
    if _running: return
    _running = True
    _daemon_thread = threading.Thread(target=_security_loop, daemon=True, name="SecurityEngine")
    _daemon_thread.start()
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

    cap = None
    try:
        try:
            detector = cv2.FaceDetectorYN.create(FACE_DETECTION_MODEL, "", (320, 320), 0.9, 0.3, 5000)
            recognizer = cv2.FaceRecognizerSF.create(FACE_RECOGNITION_MODEL, "")
        except Exception as e:
            print(f"[Security Engine] Error initializing OpenCV Face Recognizer: {e}")
            return

        while _running:
            # ── HALTED: pause camera processing but keep thread alive ──
            if getattr(shared, 'alfred_halted', False):
                if cap is not None:
                    cap.release()
                    cap = None
                    print("[Security Engine] Camera released while halted.")
                # Clear the latest frame so the camera feed goes dark in the UI
                with _frame_lock:
                    _latest_frame = None
                time.sleep(0.5)
                continue

            if cap is None:
                cap = cv2.VideoCapture(0)
                if not cap.isOpened():
                    print("[Security Engine] Webcam unavailable, retrying in 2s...")
                    cap = None
                    time.sleep(2)
                    continue
                print("[Security Engine] Camera acquired.")


            ret, frame = cap.read()
            if not ret:
                time.sleep(1)
                continue
                
            with _frame_lock:
                _latest_frame = frame.copy()
            
            # We process the face every ~3 seconds to save CPU
            time.sleep(3)
            
            # Re-read a fresh frame after sleeping (avoid processing a stale 3-second-old frame)
            ret, frame = cap.read()
            if not ret:
                continue
            
            with _frame_lock:
                _latest_frame = frame.copy()
            
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
                else:
                    _unauthorized_strikes += 1
                    print(f"[Security Engine] Low score warning ({_unauthorized_strikes}/3 strikes)")
                    
                    if _unauthorized_strikes == 1:
                        # Take snapshot on first strike
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        incident_dir = os.path.join(os.path.dirname(__file__), "assets", "incidents")
                        os.makedirs(incident_dir, exist_ok=True)
                        img_path = os.path.join(incident_dir, f"incident_{timestamp}.jpg")
                        cv2.imwrite(img_path, frame.copy())
                        
                        # Add to unseen incidents list as just the filename for frontend fetching
                        filename = f"incident_{timestamp}.jpg"
                        if filename not in shared.unseen_incidents:
                            shared.unseen_incidents.append(filename)
                            shared.push_sentry_state()
                            print(f"[Security Engine] Intruder snapshot saved: {filename}")
                            
                    if _unauthorized_strikes >= 3:
                        shared.face_present = False
                        
                        # Security Lock Logic
                        print(f"\n[Security] Unauthorized face confirmed! Locking PC.")
                        subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=False)
                        
                        # Sleep a bit longer after locking
                        time.sleep(10)
            else:
                shared.face_present = False
                _unauthorized_strikes = 0 # If no face is detected at all, don't increase strikes (user walked away)
    finally:
        if cap is not None:
            cap.release()
            print("[Security Engine] Camera released.")

import atexit
atexit.register(stop_security_daemon)

