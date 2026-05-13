import time
import numpy as np

_app_classification_cache = {}

def generate_dynamic_scold(context_str):
    """Generates a dynamic, contextual scolding using the local Llama model."""
    try:
        from llm_engine import USER_NAME
        import llm_engine
        prompt = f"You are Alfred, a strict AI butler. Master {USER_NAME} is in a focused study session (Protocol Omega). I just detected: {context_str}. Scold them strictly but professionally in 1 or 2 short sentences. Spoken format."
        res = llm_engine.chat(messages=[{'role': 'user', 'content': prompt}], options={'temperature': 0.7, 'num_predict': 50})
        return res['message']['content'].strip()
    except Exception as e:
        print(f"[Protocol Omega] Dynamic scold failed: {e}")
        return f"Sir, I have detected {context_str}. Please stop and return to your studies immediately."

def classify_app_title(title):
    """Dynamically classifies an unknown window title using the local LLM."""
    if title in _app_classification_cache:
        return _app_classification_cache[title]
    try:
        import llm_engine
        prompt = f"Classify this application window title as PRODUCTIVE or DISTRACTING for a student studying. Title: '{title}'. Answer with EXACTLY ONE WORD: either PRODUCTIVE or DISTRACTING."
        res = llm_engine.chat(messages=[{'role': 'user', 'content': prompt}], options={'temperature': 0.1, 'num_predict': 10})
        ans = res['message']['content'].strip().upper()
        if "DISTRACTING" in ans:
            _app_classification_cache[title] = "DISTRACTING"
            return "DISTRACTING"
        else:
            _app_classification_cache[title] = "PRODUCTIVE"
            return "PRODUCTIVE"
    except Exception:
        return "PRODUCTIVE" # Default to safe if LLM fails

def init_drowsiness_detector():
    """Initializes the MediaPipe Face Mesh for drowsiness detection."""
    try:
        import mediapipe as mp
        mp_face_mesh = mp.solutions.face_mesh
        face_mesh = mp_face_mesh.FaceMesh(max_num_faces=1, refine_landmarks=True, min_detection_confidence=0.5, min_tracking_confidence=0.5)
        return face_mesh
    except ImportError:
        print("[Protocol Omega] MediaPipe not installed. Drowsiness detection disabled.")
        return None
    except Exception as e:
        print(f"[Protocol Omega] MediaPipe init failed: {e}")
        return None

def calculate_ear(landmarks, frame_w, frame_h):
    """Calculates the Eye Aspect Ratio (EAR) given face landmarks."""
    # Right eye indices: 33, 160, 158, 133, 153, 144
    # Left eye indices: 362, 385, 387, 263, 373, 380
    right_eye_indices = [33, 160, 158, 133, 153, 144]
    left_eye_indices = [362, 385, 387, 263, 373, 380]
    
    def get_pt(idx):
        lm = landmarks.landmark[idx]
        return np.array([lm.x * frame_w, lm.y * frame_h])
        
    def _ear(indices):
        p0 = get_pt(indices[0])
        p1 = get_pt(indices[1])
        p2 = get_pt(indices[2])
        p3 = get_pt(indices[3])
        p4 = get_pt(indices[4])
        p5 = get_pt(indices[5])
        
        A = np.linalg.norm(p1 - p5)
        B = np.linalg.norm(p2 - p4)
        C = np.linalg.norm(p0 - p3)
        if C == 0: return 0
        return (A + B) / (2.0 * C)
        
    ear_right = _ear(right_eye_indices)
    ear_left = _ear(left_eye_indices)
    
    return (ear_right + ear_left) / 2.0
