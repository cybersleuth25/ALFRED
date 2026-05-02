import httpx
from datetime import datetime
import os

# Example: Caltrans public traffic camera feeds
CAMERA_FEEDS = {
    "I-405_LAX": {
        "url": "https://cwwp2.dot.ca.gov/data/d7/cctv/image/i405-lax/i405-lax.jpg",
        "lat": 33.9425,
        "lon": -118.4081,
    },
    "I-5_Downtown": {
        "url": "https://cwwp2.dot.ca.gov/data/d7/cctv/image/i5-downtown/i5-downtown.jpg",
        "lat": 34.0522,
        "lon": -118.2437,
    },
}

async def capture_frame(camera_id: str) -> dict:
    """Downloads a single JPEG frame from a public traffic camera."""
    cam = CAMERA_FEEDS[camera_id]
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            resp = await client.get(cam["url"])
            return {
                "camera_id": camera_id,
                "image_bytes": resp.content,
                "lat": cam["lat"],
                "lon": cam["lon"],
                "captured_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            print(f"Failed to capture frame from {camera_id}: {e}")
            return {
                "camera_id": camera_id,
                "image_bytes": None,
                "lat": cam["lat"],
                "lon": cam["lon"],
                "captured_at": datetime.utcnow().isoformat(),
            }
