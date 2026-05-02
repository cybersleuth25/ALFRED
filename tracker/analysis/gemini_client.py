from google import genai
from google.genai import types
import json
import base64
import os
from dotenv import load_dotenv
from tracker.models.schemas import DetectionResponse

load_dotenv()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Initialize new client
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# Use dynamically available latest flash model
MODEL_NAME = "gemini-2.5-flash"

PANOPTIC_SYSTEM_PROMPT = """You are an advanced geospatial analyst model.
Analyze the provided image and detect ALL visible objects in these categories:
- vehicles (cars, trucks, buses, motorcycles)
- pedestrians
- infrastructure (bridges, intersections)

For each detected object, return:
1. category (string)
2. estimated_lat and estimated_lon (float) — infer from camera metadata provided
3. confidence (float, 0-1)
4. bounding_box (optional, [x1, y1, x2, y2] in pixel coords)
5. attributes (color, direction, estimated_speed if moving)

Return ONLY valid JSON. No markdown. No explanation."""

async def analyze_frame(
    image_bytes: bytes,
    camera_lat: float,
    camera_lon: float,
    camera_heading: float = 0,
    fov_degrees: float = 90,
) -> list[dict]:
    """
    Sends a camera frame to Gemini for panoptic detection.
    Camera metadata helps Gemini estimate real-world coordinates.
    """
    if not client or not image_bytes:
        return []

    try:
        context = f"""Camera metadata:
        - Position: ({camera_lat}, {camera_lon})
        - Heading: {camera_heading}° from North
        - Field of view: {fov_degrees}°
        - Image type: Traffic camera JPEG snapshot

        Use this metadata to estimate real-world lat/lon for each detected object."""

        response = await client.aio.models.generate_content(
            model=MODEL_NAME,
            contents=[
                PANOPTIC_SYSTEM_PROMPT,
                context,
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )

        try:
            detections_data = json.loads(response.text)
            # Support both array and object wrapping
            if isinstance(detections_data, dict) and "detections" in detections_data:
                detections_list = detections_data["detections"]
            elif isinstance(detections_data, list):
                detections_list = detections_data
            else:
                detections_list = []
                
            validated = DetectionResponse(detections=detections_list)
            # return as list of dicts for the panoptic orchestrator
            return [d.dict() for d in validated.detections]
        except Exception as e:
            print(f"Failed to parse Gemini response: {e}")
            return []
    except Exception as e:
            print(f"Gemini API Error: {e}")
            return []
