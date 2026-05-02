from pydantic import BaseModel, Field
from typing import Optional

class AircraftPosition(BaseModel):
    icao24: str
    callsign: str = ""
    origin_country: str = ""
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    altitude: Optional[float] = None
    velocity: Optional[float] = None
    heading: Optional[float] = None
    vertical_rate: Optional[float] = None
    on_ground: bool = False
    last_contact: Optional[int] = None

class Detection(BaseModel):
    category: str = Field(..., description="vehicle, aircraft, pedestrian, etc.")
    estimated_lat: float = Field(..., ge=-90, le=90)
    estimated_lon: float = Field(..., ge=-180, le=180)
    confidence: float = Field(..., ge=0, le=1)
    bounding_box: Optional[list[float]] = None
    attributes: dict = Field(default_factory=dict)

class DetectionResponse(BaseModel):
    """Validates Gemini's entire response before it hits your map."""
    detections: list[Detection]
