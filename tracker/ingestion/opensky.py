import httpx
import asyncio
from typing import List, Optional, Dict
from tracker.models.schemas import AircraftPosition

OPENSKY_URL = "https://opensky-network.org/api/states/all"

async def fetch_aircraft(bbox: Optional[Dict] = None) -> List[AircraftPosition]:
    """
    Fetches all live aircraft positions from OpenSky.
    bbox: {"lamin": 45.0, "lomin": -125.0, "lamax": 50.0, "lomax": -115.0}
    Rate limit: 5 req/10s (anonymous), 1 req/5s (authenticated)
    """
    params = bbox or {}
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(OPENSKY_URL, params=params)
            if resp.status_code != 200:
                print(f"OpenSky API failed with status: {resp.status_code}")
                return []
            data = resp.json()
        except Exception as e:
            print(f"OpenSky fetch error: {e}")
            return []

    aircraft = []
    for state in data.get("states", []):
        aircraft.append(AircraftPosition(
            icao24=str(state[0]),
            callsign=str(state[1] or "").strip(),
            origin_country=str(state[2]),
            longitude=float(state[5]) if state[5] is not None else None,
            latitude=float(state[6]) if state[6] is not None else None,
            altitude=float(state[7]) if state[7] is not None else None,       # meters (barometric)
            velocity=float(state[9]) if state[9] is not None else None,       # m/s ground speed
            heading=float(state[10]) if state[10] is not None else None,       # degrees from north
            vertical_rate=float(state[11]) if state[11] is not None else None,
            on_ground=bool(state[8]),
            last_contact=int(state[4]) if state[4] is not None else None,
        ))
    return aircraft
