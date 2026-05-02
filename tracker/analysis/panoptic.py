import asyncio
from tracker.ingestion.traffic_cams import capture_frame, CAMERA_FEEDS
from tracker.ingestion.opensky import fetch_aircraft
from tracker.analysis.gemini_client import analyze_frame

async def run_detection_cycle() -> dict:
    """
    One full detection cycle:
    1. Pull aircraft data from OpenSky
    2. Capture frames from all traffic cameras
    3. Send each frame to Gemini for panoptic detection
    4. Merge all results into a single GeoJSON payload
    """
    
    # 1. OpenSky Aircraft Fetch (Bound to LA to prevent UI freezing from 10k global flights)
    bbox = {"lamin": 33.5, "lomin": -119.0, "lamax": 34.5, "lomax": -117.5}
    aircraft = await fetch_aircraft(bbox)

    # 2 & 3. Traffic Cam Analysis
    camera_tasks = []
    for cam_id, cam_info in CAMERA_FEEDS.items():
        frame = await capture_frame(cam_id)
        if frame["image_bytes"]:
            camera_tasks.append(
                analyze_frame(
                    image_bytes=frame["image_bytes"],
                    camera_lat=frame["lat"],
                    camera_lon=frame["lon"],
                )
            )
        else:
            # Create a dummy task that returns empty list
            async def dummy_empty(): return []
            camera_tasks.append(dummy_empty())

    all_detections = await asyncio.gather(*camera_tasks)

    # 4. Flatten into unified GeoJSON
    features = []

    # Add aircraft as features
    for ac in aircraft:
        if ac.latitude and ac.longitude:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [ac.longitude, ac.latitude]},
                "properties": {
                    "category": "aircraft",
                    "callsign": ac.callsign,
                    "altitude": ac.altitude,
                    "velocity": ac.velocity,
                    "heading": ac.heading,
                    "source": "opensky",
                },
            })

    # Add Gemini detections as features
    for cam_id, detections in zip(CAMERA_FEEDS.keys(), all_detections):
        for det in detections:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [det["estimated_lon"], det["estimated_lat"]],
                },
                "properties": {
                    **det,
                    "source": f"camera:{cam_id}",
                    "source_model": "gemini-vision",
                },
            })

    return {"type": "FeatureCollection", "features": features}
