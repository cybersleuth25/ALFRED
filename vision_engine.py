"""
Vision Engine (Sentry Mode) for Alfred.
========================================
Adapted from: https://github.com/Riznish-Tahir/Hidden-Human (MIT License)

Provides:
  1. YOLOv8 person detection via the webcam (shares frames with security_engine)
  2. Hidden-person detection & threat assessment
  3. MediaPipe hand gesture recognition (palm/fist/OK)
  4. Telegram photo alerts on HIGH threat
  5. Incident logging to Alfred_Workspace/incidents/

Usage:
    import vision_engine
    vision_engine.start_vision_daemon()   # called from alfred.py
    vision_engine.stop_vision_daemon()
"""

import cv2
import threading
import time
import os
import csv
from datetime import datetime

import shared
import security_engine

# ── UniFace Setup ──
UNIFACE_AVAILABLE = False
uniface_analyzer = None
try:
    from uniface import FaceAnalyzer
    uniface_analyzer = FaceAnalyzer()
    UNIFACE_AVAILABLE = True
    print("[Vision Engine] UniFace FaceAnalyzer initialized.")
except ImportError:
    print("[Vision Engine] uniface not installed. UniFace facial emotion features disabled.")
except Exception as e:
    print(f"[Vision Engine] UniFace init failed: {e}")

# ── YOLOv8 Tracking Setup ──
YOLO_AVAILABLE = False
yolo_model = None
try:
    from ultralytics import YOLO
    _yolo_path = os.path.join(os.path.dirname(__file__), "yolov8n.pt")
    if os.path.exists(_yolo_path):
        yolo_model = YOLO(_yolo_path)
    else:
        yolo_model = YOLO("yolov8n.pt")
    YOLO_AVAILABLE = True
    print("[Vision Engine] YOLOv8 tracking loaded.")
except ImportError:
    print("[Vision Engine] ultralytics not installed. Tracking fallback active.")
except Exception as e:
    print(f"[Vision Engine] YOLOv8 init failed: {e}")

# ── Subject & Object Persistence ──
_tracked_subjects = {}  # {track_id: {"id": int, "first_seen": float, "last_seen": float, "dwell_seconds": int, "bbox": tuple, "active": bool}}

def _format_dwell(seconds: int) -> str:
    """Format seconds into readable dwell time (e.g., '14m 20s')."""
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    sec = seconds % 60
    if minutes < 60:
        return f"{minutes}m {sec:02d}s"
    hours = minutes // 60
    min_rem = minutes % 60
    return f"{hours}h {min_rem:02d}m"

# ── MediaPipe Hand Gesture Setup ──
MEDIAPIPE_AVAILABLE = False
hand_landmarker = None
try:
    import mediapipe as mp
    _hand_model_path = os.path.join(os.path.dirname(__file__), "hand_landmarker.task")
    if os.path.exists(_hand_model_path):
        BaseOptions = mp.tasks.BaseOptions
        HandLandmarker = mp.tasks.vision.HandLandmarker
        HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
        VisionRunningMode = mp.tasks.vision.RunningMode

        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=_hand_model_path),
            running_mode=VisionRunningMode.IMAGE,
            num_hands=1,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        hand_landmarker = HandLandmarker.create_from_options(options)
        MEDIAPIPE_AVAILABLE = True
        print("[Vision Engine] MediaPipe Hand Landmarker loaded.")
    else:
        print(f"[Vision Engine] Hand model not found at: {_hand_model_path}")
        print("  Download from: https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task")
except ImportError:
    print("[Vision Engine] mediapipe not installed. Run: pip install mediapipe")
    print("  Gesture controls will be disabled, but person detection will still work.")
except Exception as e:
    print(f"[Vision Engine] MediaPipe init failed: {e}")

# ── DeepFace Emotion Setup ──
# Removed: Emotion is now handled by UniFace.
DEEPFACE_AVAILABLE = False
# ── Incidents Directory ──
INCIDENTS_DIR = os.path.join(os.path.dirname(__file__), "Alfred_Workspace", "incidents")
os.makedirs(INCIDENTS_DIR, exist_ok=True)

# ── Thread Control ──
_running = False
_thread = None

# ── Detection State ──
_person_was_detected = False
_hidden_mode = False
_hidden_start_time = 0.0
_hidden_duration = 0.0
_last_bbox = None               # (x1, y1, x2, y2) of last known person
_last_speed = 0.0               # pixel movement speed before hiding
_prev_center = None             # previous frame center of person
_threat_score = 0.0
_snapshot_cooldown = 0           # frames since last snapshot
_gesture_cooldown = 0            # frames since last gesture action

# ── Threat Thresholds (from Hidden-Human) ──
THREAT_LOW = 40
THREAT_MED = 70
SNAPSHOT_COOLDOWN_FRAMES = 90    # ~3 seconds at 30fps


def _classify_threat(hidden_duration: float, speed: float, in_center: bool) -> tuple:
    """
    Calculate threat score 0-100 based on three factors:
      - Duration hidden: up to 40 points (maxes at 10 seconds)
      - Movement speed before hiding: up to 30 points
      - Was person in center restricted zone: 30 points
    Returns (score, level_string)
    """
    time_score = min(hidden_duration / 10.0, 1.0) * 40
    speed_score = min(speed / 200.0, 1.0) * 30
    zone_score = 30 if in_center else 0
    total = time_score + speed_score + zone_score
    total = min(total, 100.0)

    if total >= THREAT_MED:
        return total, "high"
    elif total >= THREAT_LOW:
        return total, "medium"
    else:
        return total, "low"


def _is_in_center_zone(bbox, frame_w, frame_h):
    """Check if bounding box center is in the middle third of the frame."""
    cx = (bbox[0] + bbox[2]) / 2
    cy = (bbox[1] + bbox[3]) / 2
    margin_x = frame_w / 3
    margin_y = frame_h / 3
    return (margin_x < cx < frame_w - margin_x) and (margin_y < cy < frame_h - margin_y)


def _detect_gesture(frame):
    """
    Detect hand gesture using MediaPipe.
    Returns: "palm" (open hand), "fist" (closed), "ok" (thumb+index circle), or ""
    """
    if not MEDIAPIPE_AVAILABLE or hand_landmarker is None:
        return ""

    try:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = hand_landmarker.detect(mp_image)

        if not result.hand_landmarks:
            return ""

        landmarks = result.hand_landmarks[0]

        # Finger tip and MCP (knuckle) indices
        # Index: tip=8, mcp=5 | Middle: tip=12, mcp=9 | Ring: tip=16, mcp=13 | Pinky: tip=20, mcp=17
        tips = [8, 12, 16, 20]
        mcps = [5, 9, 13, 17]

        fingers_up = 0
        for tip_idx, mcp_idx in zip(tips, mcps):
            if landmarks[tip_idx].y < landmarks[mcp_idx].y:
                fingers_up += 1

        # Thumb: tip=4, ip=3
        thumb_tip = landmarks[4]
        thumb_ip = landmarks[3]
        thumb_up = thumb_tip.x < thumb_ip.x  # For right hand (simplified)

        # OK sign: thumb tip close to index tip
        index_tip = landmarks[8]
        thumb_index_dist = ((thumb_tip.x - index_tip.x)**2 + (thumb_tip.y - index_tip.y)**2) ** 0.5

        if thumb_index_dist < 0.06 and fingers_up >= 2:
            return "ok"
        elif fingers_up >= 4:
            return "palm"
        elif fingers_up == 0:
            return "fist"

        return ""
    except Exception:
        return ""


def _save_incident(frame, threat_score, threat_level):
    """Save snapshot and log incident to CSV."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        img_path = os.path.join(INCIDENTS_DIR, f"incident_{timestamp}.jpg")
        cv2.imwrite(img_path, frame)

        csv_path = os.path.join(INCIDENTS_DIR, "incident_log.csv")
        file_exists = os.path.exists(csv_path)

        with open(csv_path, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["timestamp", "threat_score", "threat_level", "snapshot"])
            writer.writerow([datetime.now().isoformat(), f"{threat_score:.1f}", threat_level, img_path])

        print(f"[Vision Engine] Incident saved: {img_path} (threat: {threat_score:.0f}%)")

        # Push Telegram alert with photo
        try:
            import telegram_notifier
            if telegram_notifier.is_available():
                telegram_notifier.send_photo_alert(
                    img_path,
                    f"🚨 SENTRY ALERT: {threat_level.upper()} THREAT ({threat_score:.0f}%)\n"
                    f"A person was detected and then hid from the camera.\n"
                    f"Timestamp: {datetime.now().strftime('%H:%M:%S')}"
                )
        except Exception as e:
            print(f"[Vision Engine] Telegram alert failed: {e}")

        return img_path
    except Exception as e:
        print(f"[Vision Engine] Failed to save incident: {e}")
        return None


def _vision_loop():
    """Main vision processing loop — runs as a daemon thread."""
    global _running, _person_was_detected, _hidden_mode, _hidden_start_time
    global _hidden_duration, _last_bbox, _last_speed, _prev_center
    global _threat_score, _snapshot_cooldown, _gesture_cooldown, _tracked_subjects

    if not UNIFACE_AVAILABLE and not YOLO_AVAILABLE:
        print("[Vision Engine] Cannot start — neither UniFace nor YOLOv8 available.")
        return

    print("[Vision Engine] Sentry Mode ACTIVE with ByteTrack Object Persistence.")

    _emotion_cooldown = 0

    while _running:
        # Get frame from security engine (shared webcam)
        frame = security_engine.get_latest_frame()
        if frame is None:
            time.sleep(0.5)
            continue

        frame_h, frame_w = frame.shape[:2]
        now = time.time()
        persons = []
        tracked_ids = []

        # ── 1. YOLOv8 Persistent Tracking (ByteTrack) ──
        if YOLO_AVAILABLE and yolo_model is not None:
            try:
                # Track people (classes=[0]) with ByteTrack
                results = yolo_model.track(
                    frame,
                    persist=True,
                    classes=[0],
                    tracker="bytetrack.yaml",
                    conf=0.35,
                    verbose=False
                )
                if results and len(results) > 0:
                    boxes = results[0].boxes
                    if boxes is not None and len(boxes) > 0:
                        for box in boxes:
                            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                            persons.append((x1, y1, x2, y2))
                            
                            t_id = int(box.id[0].item()) if box.id is not None else (len(persons))
                            tracked_ids.append(t_id)

                            # Subject persistence update
                            if t_id not in _tracked_subjects:
                                _tracked_subjects[t_id] = {
                                    "id": t_id,
                                    "first_seen": now,
                                    "last_seen": now,
                                    "dwell_seconds": 0,
                                    "bbox": (x1, y1, x2, y2),
                                    "active": True
                                }
                                shared.push_log(f"Subject #{t_id} entered camera field of view.", "VisionSentry")
                            else:
                                sub = _tracked_subjects[t_id]
                                sub["last_seen"] = now
                                sub["dwell_seconds"] = int(now - sub["first_seen"])
                                sub["bbox"] = (x1, y1, x2, y2)
                                if not sub["active"]:
                                    sub["active"] = True
                                    shared.push_log(f"Subject #{t_id} returned to desk.", "VisionSentry")
            except Exception:
                pass

        # ── 2. UniFace Facial Analysis & Emotion (if available) ──
        if UNIFACE_AVAILABLE and uniface_analyzer is not None:
            try:
                faces = uniface_analyzer.analyze(frame)
                if not persons:
                    for face in faces:
                        x1, y1, x2, y2 = map(int, face.bbox)
                        persons.append((x1, y1, x2, y2))
                        if hasattr(face, 'tracker_id') and face.tracker_id is not None:
                            tracked_ids.append(face.tracker_id)
                
                # Update face coordinates for the frontend orb
                if faces:
                    fx1, fy1, fx2, fy2 = map(int, faces[0].bbox)
                    shared.face_x = ((fx1 + fx2) / 2) / frame_w
                    shared.face_y = ((fy1 + fy2) / 2) / frame_h
                    
                    if hasattr(faces[0], 'emotion') and faces[0].emotion:
                        _emotion_cooldown = max(0, _emotion_cooldown - 1)
                        if _emotion_cooldown <= 0:
                            if faces[0].emotion != shared.dominant_emotion:
                                shared.dominant_emotion = faces[0].emotion
                            try:
                                import mood_engine
                                mood_engine.log_mood_snapshot(faces[0].emotion)
                            except Exception:
                                pass
                            _emotion_cooldown = 10
            except Exception:
                pass
        elif persons:
            # Fallback face/center coordinates from primary person bounding box
            bx1, by1, bx2, by2 = persons[0]
            shared.face_x = ((bx1 + bx2) / 2) / frame_w
            shared.face_y = ((by1 + by2) / 2) / frame_h

        # ── 3. Detect Inactive Subjects & Departures ──
        for t_id, sub in list(_tracked_subjects.items()):
            if sub["active"] and (now - sub["last_seen"] > 5.0):
                sub["active"] = False
                shared.push_log(f"Subject #{t_id} departed after {_format_dwell(sub['dwell_seconds'])}.", "VisionSentry")

        # Compile active subjects list for shared state & UI
        active_list = [
            {
                "id": sub["id"],
                "dwell_seconds": sub["dwell_seconds"],
                "dwell": _format_dwell(sub["dwell_seconds"]),
                "active": sub["active"]
            }
            for sub in _tracked_subjects.values()
            if sub["active"]
        ]
        shared.tracked_subjects_list = active_list
        shared.tracked_subjects = tracked_ids
        shared.persons_detected = len(persons)
        person_detected_now = len(persons) > 0

        # ── Hidden Person Detection ──
        if _person_was_detected and not person_detected_now:
            # Person was here, now gone → hidden!
            if not _hidden_mode:
                _hidden_mode = True
                _hidden_start_time = time.time()
                print("[Vision Engine] ⚠ Person HIDDEN from camera!")
        elif person_detected_now:
            # Person visible
            if _hidden_mode:
                print("[Vision Engine] ✓ Person reappeared. Threat cleared.")
            _hidden_mode = False
            _hidden_duration = 0.0
            _threat_score = 0.0
            _snapshot_cooldown = max(0, _snapshot_cooldown - 1)

            # Track movement speed (for threat calculation)
            best_box = persons[0]
            cx = (best_box[0] + best_box[2]) / 2
            cy = (best_box[1] + best_box[3]) / 2

            if _prev_center is not None:
                dx = cx - _prev_center[0]
                dy = cy - _prev_center[1]
                _last_speed = (dx**2 + dy**2) ** 0.5
            _prev_center = (cx, cy)
            _last_bbox = best_box

        # ── Threat Assessment (while hidden) ──
        if _hidden_mode:
            _hidden_duration = time.time() - _hidden_start_time
            in_center = _is_in_center_zone(_last_bbox, frame_w, frame_h) if _last_bbox else False
            _threat_score, level = _classify_threat(_hidden_duration, _last_speed, in_center)

            shared.threat_score = _threat_score
            shared.threat_level = level
            shared.hidden_mode = True

            # Save incident on HIGH threat
            if level == "high" and _snapshot_cooldown <= 0:
                _save_incident(frame, _threat_score, level)
                _snapshot_cooldown = SNAPSHOT_COOLDOWN_FRAMES
        else:
            shared.threat_score = 0.0
            shared.threat_level = "none"
            shared.hidden_mode = False

        _person_was_detected = person_detected_now
        _snapshot_cooldown = max(0, _snapshot_cooldown - 1)

        # ── Hand Gesture Detection (via Gesture Engine) ──
        _gesture_cooldown = max(0, _gesture_cooldown - 1)
        if _gesture_cooldown <= 0 and MEDIAPIPE_AVAILABLE and hand_landmarker is not None:
            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                result = hand_landmarker.detect(mp_image)

                if result.hand_landmarks:
                    landmarks = result.hand_landmarks[0]
                    import gesture_engine
                    gesture = gesture_engine.process_frame(landmarks)
                    if gesture:
                        shared.gesture_detected = gesture
                        _gesture_cooldown = 10  # Short frame skip (cooldowns managed per-gesture inside engine)
                    else:
                        shared.gesture_detected = ""
                else:
                    shared.gesture_detected = ""
            except Exception:
                pass

        # ── Emotion Detection (every 10 frames) ──
        # Handled above via UniFace

        # Push state to frontend
        shared.push_sentry_state()

        # Run at ~10 FPS (no need for 30fps for detection)
        time.sleep(0.1)

    print("[Vision Engine] Sentry Mode DEACTIVATED.")


def start_vision_daemon():
    """Start the vision engine as a background daemon thread."""
    global _running, _thread
    if _running:
        print("[Vision Engine] Already running.")
        return
    if not UNIFACE_AVAILABLE and not YOLO_AVAILABLE:
        print("[Vision Engine] Cannot start — Neither UniFace nor YOLOv8 available.")
        return

    _running = True
    shared.sentry_active = True
    _thread = threading.Thread(target=_vision_loop, daemon=True, name="VisionEngine")
    _thread.start()
    print("[System] Vision Engine (Sentry Mode) started.")


def stop_vision_daemon():
    """Stop the vision engine daemon."""
    global _running
    if not _running:
        return
    _running = False
    shared.sentry_active = False
    shared.threat_level = "none"
    shared.threat_score = 0.0
    shared.persons_detected = 0
    shared.tracked_subjects = 0
    shared.tracked_subjects_list = []
    shared.hidden_mode = False
    shared.gesture_detected = ""
    shared.push_sentry_state()
    print("[System] Vision Engine (Sentry Mode) stopped.")


def is_active() -> bool:
    """Check if sentry mode is currently active."""
    return _running
