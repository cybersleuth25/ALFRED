"""
Vision Tools for Alfred — Open-Vocabulary Object Detection.
============================================================
Uses YOLO-World to locate any object described in natural language
from the current webcam frame. No retraining needed.

Usage:
    from tools.vision_tools import locate_object_in_camera
    result = locate_object_in_camera("water bottle")
"""

import os
import cv2
import numpy as np

# ── YOLO-World Setup (lazy-loaded on first call) ──
_yolo_world_model = None
_YOLO_WORLD_MODEL_NAME = "yolov8s-worldv2.pt"


def _get_yolo_world():
    """Lazy-load the YOLO-World model on first use."""
    global _yolo_world_model
    if _yolo_world_model is not None:
        return _yolo_world_model

    try:
        from ultralytics import YOLO
        print(f"[Vision Tools] Loading YOLO-World model: {_YOLO_WORLD_MODEL_NAME}...")
        _yolo_world_model = YOLO(_YOLO_WORLD_MODEL_NAME)
        print("[Vision Tools] YOLO-World ready. Open-vocabulary detection active.")
        return _yolo_world_model
    except ImportError:
        print("[Vision Tools] ultralytics not installed. Run: pip install ultralytics")
        return None
    except Exception as e:
        print(f"[Vision Tools] YOLO-World init failed: {e}")
        return None


def _grab_webcam_frame():
    """Grab a single frame from the webcam (via security_engine if running, else direct)."""
    try:
        import security_engine
        # Try to grab the latest frame from the already-running security engine
        frame = getattr(security_engine, '_last_frame', None)
        if frame is not None:
            return frame
    except Exception:
        pass

    # Fallback: open webcam directly for a single capture
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return None
    ret, frame = cap.read()
    cap.release()
    if ret:
        return frame
    return None


def locate_object_in_camera(target: str) -> str:
    """
    Uses YOLO-World to locate any object described in natural language
    from the current webcam frame. Returns a description of what was found.

    Args:
        target: Natural language description of the object to find.
                Examples: "water bottle", "keys", "red cup", "person sitting"

    Returns:
        A human-readable description of detected objects and their positions.
    """
    model = _get_yolo_world()
    if model is None:
        return "YOLO-World model is not available. Cannot perform visual grounding."

    frame = _grab_webcam_frame()
    if frame is None:
        return "Could not access the webcam. Make sure it is connected and not in use by another app."

    h, w = frame.shape[:2]

    try:
        # Set the target classes for open-vocabulary detection
        # Adding empty string helps reduce false positives
        classes = [target.strip(), ""]
        model.set_classes(classes)

        # Run inference
        results = model.predict(frame, conf=0.25, verbose=False)

        if not results or len(results) == 0:
            return f"No '{target}' detected in the current camera view."

        detections = results[0]
        boxes = detections.boxes

        if boxes is None or len(boxes) == 0:
            return f"No '{target}' detected in the current camera view."

        # Filter to only our target class (index 0), not the background class
        found = []
        for box in boxes:
            cls_id = int(box.cls[0])
            if cls_id != 0:  # Skip background class
                continue
            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()

            # Convert to human-readable position
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2

            # Determine position in frame
            h_pos = "left" if cx < w * 0.33 else ("right" if cx > w * 0.67 else "center")
            v_pos = "top" if cy < h * 0.33 else ("bottom" if cy > h * 0.67 else "middle")
            position = f"{v_pos}-{h_pos}"

            # Calculate approximate size
            obj_w = x2 - x1
            obj_h = y2 - y1
            size_pct = (obj_w * obj_h) / (w * h) * 100

            found.append({
                "confidence": conf,
                "position": position,
                "size_pct": size_pct,
                "bbox": [int(x1), int(y1), int(x2), int(y2)],
            })

        if not found:
            return f"No '{target}' detected in the current camera view."

        # Build response
        if len(found) == 1:
            d = found[0]
            return (
                f"Found '{target}' in the camera view! "
                f"Location: {d['position']} of frame. "
                f"Confidence: {d['confidence']:.0%}. "
                f"It occupies about {d['size_pct']:.1f}% of the frame."
            )
        else:
            lines = [f"Found {len(found)} instances of '{target}' in the camera view:"]
            for i, d in enumerate(found, 1):
                lines.append(
                    f"  {i}. {d['position']} — {d['confidence']:.0%} confidence, "
                    f"{d['size_pct']:.1f}% of frame"
                )
            return "\n".join(lines)

    except Exception as e:
        return f"Visual grounding failed: {e}"


def locate_object_on_screen(target: str) -> str:
    """
    Uses YOLO-World to locate a UI element or object on the current screen.
    Useful for finding buttons, text fields, or icons by description.

    Args:
        target: Description of the UI element to find (e.g., "search bar", "submit button")

    Returns:
        A description of detected elements and their screen positions.
    """
    try:
        import pyautogui
        screenshot = pyautogui.screenshot()
        frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    except ImportError:
        return "pyautogui is not installed. Cannot capture screen."
    except Exception as e:
        return f"Screen capture failed: {e}"

    model = _get_yolo_world()
    if model is None:
        return "YOLO-World model is not available."

    h, w = frame.shape[:2]

    try:
        classes = [target.strip(), ""]
        model.set_classes(classes)
        results = model.predict(frame, conf=0.20, verbose=False)

        if not results or len(results) == 0 or results[0].boxes is None or len(results[0].boxes) == 0:
            return f"No '{target}' found on screen."

        found = []
        for box in results[0].boxes:
            cls_id = int(box.cls[0])
            if cls_id != 0:
                continue
            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)
            found.append({"confidence": conf, "center": (cx, cy), "bbox": [int(x1), int(y1), int(x2), int(y2)]})

        if not found:
            return f"No '{target}' found on screen."

        if len(found) == 1:
            d = found[0]
            return (
                f"Found '{target}' on screen at pixel ({d['center'][0]}, {d['center'][1]}). "
                f"Confidence: {d['confidence']:.0%}."
            )
        else:
            lines = [f"Found {len(found)} instances of '{target}' on screen:"]
            for i, d in enumerate(found, 1):
                lines.append(f"  {i}. At pixel ({d['center'][0]}, {d['center'][1]}) — {d['confidence']:.0%}")
            return "\n".join(lines)

    except Exception as e:
        return f"Screen grounding failed: {e}"
