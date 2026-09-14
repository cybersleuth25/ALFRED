import time
import numpy as np
from collections import OrderedDict

_MAX_CACHE_SIZE = 200
_app_classification_cache = OrderedDict()

def generate_dynamic_scold(context_str):
    """Generates a dynamic, contextual scolding using the local Llama model."""
    try:
        from llm_engine import USER_NAME
        import llm_engine
        prompt = f"You are Alfred, a strict AI butler. Master {USER_NAME} is in a focused study session (Focus Mode). I just detected: {context_str}. Scold them strictly but professionally in 1 or 2 short sentences. Spoken format."
        res = llm_engine.chat(messages=[{'role': 'user', 'content': prompt}], options={'temperature': 0.7, 'num_predict': 50})
        return res['message']['content'].strip()
    except Exception as e:
        print(f"[Focus Mode] Dynamic scold failed: {e}")
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
            result = "DISTRACTING"
        else:
            result = "PRODUCTIVE"
        _app_classification_cache[title] = result
        if len(_app_classification_cache) > _MAX_CACHE_SIZE:
            _app_classification_cache.popitem(last=False)  # Evict oldest
        return result
    except Exception:
        return "PRODUCTIVE" # Default to safe if LLM fails

def init_drowsiness_detector():
    """Initializes the MediaPipe Face Landmarker for drowsiness detection."""
    try:
        import mediapipe as mp
        import os
        model_path = os.path.join(os.path.dirname(__file__), "face_landmarker.task")
        if not os.path.exists(model_path):
            print(f"[Focus Mode] Face landmarker model not found at {model_path}.")
            print("  Download from: https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task")
            return None
        BaseOptions = mp.tasks.BaseOptions
        FaceLandmarker = mp.tasks.vision.FaceLandmarker
        FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
        VisionRunningMode = mp.tasks.vision.RunningMode
        options = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=VisionRunningMode.IMAGE,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        landmarker = FaceLandmarker.create_from_options(options)
        print("[Focus Mode] MediaPipe Face Landmarker loaded.")
        return landmarker
    except ImportError:
        print("[Focus Mode] MediaPipe not installed. Drowsiness detection disabled.")
        return None
    except Exception as e:
        print(f"[Focus Mode] MediaPipe init failed: {e}")
        return None

def calculate_ear(landmarks, frame_w, frame_h):
    """Calculates the Eye Aspect Ratio (EAR) given face landmarks.
    
    Accepts a list of NormalizedLandmark objects (new mp.tasks API).
    """
    # Right eye indices: 33, 160, 158, 133, 153, 144
    # Left eye indices: 362, 385, 387, 263, 373, 380
    right_eye_indices = [33, 160, 158, 133, 153, 144]
    left_eye_indices = [362, 385, 387, 263, 373, 380]
    
    def get_pt(idx):
        lm = landmarks[idx]
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

