"""
Vision Tools for Alfred — Open-Vocabulary Object Detection & Visual Grounding.
=============================================================================
Integrates:
  1. NVIDIA LocateAnything-3B (Open-vocabulary Parallel Box Decoding via Hugging Face)
  2. Google Gemini 2.5 Flash Visual Grounding (Multimodal open-vocabulary fallback)
  3. YOLO-World & YOLOv8 (Local offline fallback)

Usage:
    from tools.vision_tools import locate_object_in_camera, locate_object_on_screen
    result = locate_object_in_camera("water bottle")
"""

import os
import cv2
import json
import time
import tempfile
import numpy as np

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "Alfred_Workspace", "locate_results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# ── NVIDIA LocateAnything Client ──
_locateanything_client = None

def _get_locateanything_client():
    global _locateanything_client
    if _locateanything_client is not None:
        return _locateanything_client
    try:
        from gradio_client import Client
        hf_token = os.getenv("HF_TOKEN")
        _locateanything_client = Client("nvidia/LocateAnything", token=hf_token)
        print("[Vision Tools] Connected to NVIDIA LocateAnything-3B Space.")
        return _locateanything_client
    except Exception as e:
        print(f"[Vision Tools] LocateAnything client init: {e}")
        return None


def _locate_with_nvidia(frame, target: str):
    """Query NVIDIA LocateAnything-3B Hugging Face Space for open-vocabulary grounding."""
    client = _get_locateanything_client()
    if client is None:
        return None
    try:
        from gradio_client import handle_file
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
            cv2.imwrite(tmp_path, frame)

        try:
            res = client.predict(
                input_type="Image",
                image_file=handle_file(tmp_path),
                video_file=None,
                task_type="Detection",
                category=target.strip(),
                model_mode="hybrid",
                temp=0.2,
                top_p=0.9,
                top_k=20,
                short_size=512,
                question_override=None,
                max_video_frames=4,
                api_name="/run_inference"
            )
            if res and len(res) >= 3 and isinstance(res[2], dict) and res[2].get("success", False):
                return {"engine": "NVIDIA LocateAnything-3B", "annotated_path": res[0], "meta": res[2]}
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
    except Exception as e:
        print(f"[Vision Tools] NVIDIA LocateAnything query failed: {e}")
    return None


def _locate_with_gemini(frame, target: str):
    """High-accuracy open-vocabulary visual grounding fallback using Gemini 2.5 Flash."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        h, w = frame.shape[:2]
        _, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        jpeg_bytes = buf.tobytes()

        prompt = (
            f"Detect and locate all instances of '{target}' in this image.\n"
            f"For each instance, return a JSON array of objects with keys:\n"
            f"- 'box_2d': [ymin, xmin, ymax, xmax] (normalized from 0 to 1000)\n"
            f"- 'label': name of the detected object\n"
            f"- 'confidence': float between 0.0 and 1.0\n"
            f"Return ONLY valid JSON array. If none are found, return empty array []."
        )

        contents = [
            types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg"),
            prompt
        ]
        config = types.GenerateContentConfig(temperature=0.1, response_mime_type="application/json")
        resp = client.models.generate_content(model="gemini-2.5-flash", contents=contents, config=config)
        raw_text = resp.text.strip()
        data = json.loads(raw_text)
        if isinstance(data, list) and len(data) > 0:
            found = []
            for item in data:
                box = item.get("box_2d", [])
                if len(box) == 4:
                    ymin, xmin, ymax, xmax = [b / 1000.0 for b in box]
                    x1, y1, x2, y2 = int(xmin * w), int(ymin * h), int(xmax * w), int(ymax * h)
                    cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                    h_pos = "left" if cx < w * 0.33 else ("right" if cx > w * 0.67 else "center")
                    v_pos = "top" if cy < h * 0.33 else ("bottom" if cy > h * 0.67 else "middle")
                    found.append({
                        "label": item.get("label", target),
                        "confidence": float(item.get("confidence", 0.9)),
                        "position": f"{v_pos}-{h_pos}",
                        "bbox": [x1, y1, x2, y2],
                        "center": (cx, cy),
                        "size_pct": round(((x2 - x1) * (y2 - y1)) / (w * h) * 100, 1)
                    })
            if found:
                return {"engine": "Gemini 2.5 Flash Grounding", "items": found}
    except Exception as e:
        print(f"[Vision Tools] Gemini Grounding fallback error: {e}")
    return None


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


def _save_annotated_frame(frame, items: list, target: str) -> str:
    """Draws styled bounding boxes on the frame and saves to Alfred_Workspace/locate_results/."""
    try:
        annotated = frame.copy()
        h, w = frame.shape[:2]
        for it in items:
            bbox = it.get("bbox")
            if bbox and len(bbox) == 4:
                x1, y1, x2, y2 = bbox
                # Cyan/Gold bounding box
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 229, 255), 2)
                label = f"{it.get('label', target)} ({it.get('confidence', 0.9):.0%})"
                cv2.putText(annotated, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 229, 255), 2)
        
        safe_target = "".join(c for c in target if c.isalnum() or c in (' ', '_')).rstrip().replace(' ', '_')
        fname = f"locate_{safe_target}_{int(time.time())}.jpg"
        out_path = os.path.join(RESULTS_DIR, fname)
        cv2.imwrite(out_path, annotated)
        return out_path
    except Exception:
        return ""


def locate_object_in_camera(target: str) -> str:
    """
    Locates any object or person described in natural language from the current webcam frame.
    Uses NVIDIA LocateAnything-3B with Gemini 2.5 Flash Grounding and YOLO-World fallbacks.

    Args:
        target: Natural language description of the object to find.
                Examples: "water bottle", "keys", "black headphones", "white cup", "person sitting"

    Returns:
        A description of detected objects, positions, and saved visual evidence.
    """
    frame = _grab_webcam_frame()
    if frame is None:
        return "Could not access the webcam, sir. Make sure the camera is connected."

    h, w = frame.shape[:2]

    # 1. Try NVIDIA LocateAnything-3B
    nv_res = _locate_with_nvidia(frame, target)
    if nv_res and nv_res.get("annotated_path"):
        return f"Found '{target}' via NVIDIA LocateAnything! Visual evidence saved to {nv_res['annotated_path']}."

    # 2. Try Gemini 2.5 Flash Visual Grounding
    gem_res = _locate_with_gemini(frame, target)
    if gem_res and gem_res.get("items"):
        items = gem_res["items"]
        saved_img = _save_annotated_frame(frame, items, target)
        if len(items) == 1:
            d = items[0]
            resp = (
                f"Found '{target}' in the camera view ({gem_res['engine']})!\n"
                f"Location: {d['position']} of frame (confidence: {d['confidence']:.0%}). "
                f"It occupies ~{d['size_pct']}% of the view."
            )
            if saved_img:
                resp += f"\nSaved annotated visual to {os.path.basename(saved_img)}."
            return resp
        else:
            lines = [f"Found {len(items)} instances of '{target}' ({gem_res['engine']}):"]
            for i, d in enumerate(items, 1):
                lines.append(f"  {i}. {d['position']} — {d['confidence']:.0%} confidence")
            if saved_img:
                lines.append(f"Saved annotated visual to {os.path.basename(saved_img)}.")
            return "\n".join(lines)

    # 3. Local YOLO-World Fallback
    model = _get_yolo_world()
    if model is not None:
        try:
            classes = [target.strip(), ""]
            model.set_classes(classes)
            results = model.predict(frame, conf=0.25, verbose=False)
            if results and len(results) > 0 and results[0].boxes and len(results[0].boxes) > 0:
                found = []
                for box in results[0].boxes:
                    if int(box.cls[0]) != 0: continue
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    cx = (x1 + x2) / 2
                    cy = (y1 + y2) / 2
                    h_pos = "left" if cx < w * 0.33 else ("right" if cx > w * 0.67 else "center")
                    v_pos = "top" if cy < h * 0.33 else ("bottom" if cy > h * 0.67 else "middle")
                    found.append({
                        "label": target,
                        "confidence": float(box.conf[0]),
                        "position": f"{v_pos}-{h_pos}",
                        "bbox": [int(x1), int(y1), int(x2), int(y2)],
                        "size_pct": round(((x2 - x1) * (y2 - y1)) / (w * h) * 100, 1)
                    })
                if found:
                    saved_img = _save_annotated_frame(frame, found, target)
                    return f"Found '{target}' via local detector at {found[0]['position']} ({found[0]['confidence']:.0%})."
        except Exception:
            pass

    return f"No '{target}' detected in the current camera view, sir."


def locate_object_on_screen(target: str) -> str:
    """
    Locates a UI element or object on the current screen using LocateAnything & Gemini Grounding.
    Useful for finding buttons, text fields, or icons by natural language description.

    Args:
        target: Description of the UI element to find (e.g., "search bar", "submit button", "error popup")

    Returns:
        A description of detected elements, pixel coordinates, and saved visual evidence.
    """
    try:
        import pyautogui
        screenshot = pyautogui.screenshot()
        frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    except ImportError:
        return "pyautogui is not installed. Cannot capture screen."
    except Exception as e:
        return f"Screen capture failed: {e}"

    h, w = frame.shape[:2]

    # 1. Try Gemini 2.5 Flash Grounding on Screen
    gem_res = _locate_with_gemini(frame, target)
    if gem_res and gem_res.get("items"):
        items = gem_res["items"]
        saved_img = _save_annotated_frame(frame, items, f"screen_{target}")
        if len(items) == 1:
            d = items[0]
            cx, cy = d["center"]
            resp = (
                f"Located '{target}' on screen via {gem_res['engine']}!\n"
                f"Coordinates: X={cx}, Y={cy} ({d['position']} region, confidence: {d['confidence']:.0%})."
            )
            if saved_img:
                resp += f"\nVisual saved to {os.path.basename(saved_img)}."
            return resp
        else:
            lines = [f"Found {len(items)} instances of '{target}' on screen:"]
            for i, d in enumerate(items, 1):
                cx, cy = d["center"]
                lines.append(f"  {i}. ({cx}, {cy}) — {d['position']} ({d['confidence']:.0%})")
            if saved_img:
                lines.append(f"Visual saved to {os.path.basename(saved_img)}.")
            return "\n".join(lines)

    # 2. Try NVIDIA LocateAnything
    nv_res = _locate_with_nvidia(frame, target)
    if nv_res and nv_res.get("annotated_path"):
        return f"Found '{target}' on screen via NVIDIA LocateAnything! Evidence saved to {nv_res['annotated_path']}."

    # 3. Local YOLO fallback
    model = _get_yolo_world()
    if model is not None:
        try:
            classes = [target.strip(), ""]
            model.set_classes(classes)
            results = model.predict(frame, conf=0.20, verbose=False)
            if results and len(results) > 0 and results[0].boxes and len(results[0].boxes) > 0:
                found = []
                for box in results[0].boxes:
                    if int(box.cls[0]) != 0: continue
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    cx = int((x1 + x2) / 2)
                    cy = int((y1 + y2) / 2)
                    found.append({"confidence": float(box.conf[0]), "center": (cx, cy), "bbox": [int(x1), int(y1), int(x2), int(y2)]})
                if found:
                    saved_img = _save_annotated_frame(frame, found, f"screen_{target}")
                    d = found[0]
                    return f"Found '{target}' on screen at pixel ({d['center'][0]}, {d['center'][1]})."
        except Exception:
            pass

    return f"Could not find '{target}' on the current screen, sir."
