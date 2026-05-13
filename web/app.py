import os
import json
import asyncio
import threading
import time
import random
try:
    import webview
except ImportError:
    webview = None
import psutil
import requests
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from dotenv import load_dotenv

load_dotenv()

USER_CITY = os.getenv("USER_CITY", "Chikkamagaluru")

# Make sure we can import from the parent directory
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import shared
import alfred

# Import our new tracker components (optional — requires working grpc)
try:
    from tracker.analysis.panoptic import run_detection_cycle
    _tracker_available = True
except ImportError as e:
    print(f"[System] Tracker module unavailable (grpc issue on Python 3.14): {e}")
    _tracker_available = False
    async def run_detection_cycle():
        return {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    broadcast_task = asyncio.create_task(broadcast_loop())
    yield
    # Shutdown actions
    broadcast_task.cancel()

app = FastAPI(title="Alfred AI Protocol", lifespan=lifespan)

# Add CORS Middleware just in case
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

web_dir = os.path.dirname(__file__)
dist_dir = os.path.abspath(os.path.join(web_dir, '..', 'frontend', 'dist'))

if os.path.exists(dist_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(dist_dir, 'assets')), name="assets")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    index_path = os.path.join(dist_dir, 'index.html')
    if os.path.exists(index_path):
        with open(index_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<body><h1>Alfred</h1><p>UI Native Build Mode - Please run 'npm run build' in frontend folder</p></body>")

@app.get('/stream')
async def stream(request: Request):
    """EventSource endpoint for standard Alfred events."""
    async def event_generator():
        while True:
            # We must use asyncio.to_thread because queue.get() is blocking
            if await request.is_disconnected():
                break
            try:
                # To prevent blocking the main event loop, we use wait_for or similar, but 
                # since shared.event_queue.get() is a blocking queue call, we wrap it:
                event = await asyncio.to_thread(shared.event_queue.get)
                yield json.dumps(event)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Stream error: {e}")
                await asyncio.sleep(1)

    return EventSourceResponse(event_generator())

@app.post('/set_focus')
async def set_focus(request: Request):
    data = await request.json()
    shared.focus_mode_active = data.get('focus_mode', False)
    return {"status": "success", "focus_mode": shared.focus_mode_active}



# ==========================================
# PROTOCOL OMEGA (STUDY MENTOR) ENDPOINTS
# ==========================================

@app.get('/api/omega/status')
async def api_omega_status():
    """Returns the current real-time state of Protocol Omega."""
    try:
        import shared
        return JSONResponse({
            "active": shared.omega_active,
            "phase": shared.omega_phase,
            "remaining": shared.omega_phase_remaining,
            "cycle": shared.omega_pomodoro_cycle,
            "distractions": shared.omega_distractions,
            "session_id": shared.omega_session_id,
            "session_start": shared.omega_session_start,
            "daily_goal": getattr(shared, 'omega_daily_goal_minutes', 240),
            "daily_progress": getattr(shared, 'omega_daily_progress', 0),
            "streak": getattr(shared, 'omega_streak', 0),
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get('/api/omega/history')
async def api_omega_history():
    """Returns the last 10 study sessions."""
    try:
        import memory_engine
        sessions = memory_engine.get_study_history(10)
        return JSONResponse({"sessions": sessions})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get('/api/omega/stats')
async def api_omega_stats():
    """Returns aggregate study stats."""
    try:
        import memory_engine
        stats = memory_engine.get_study_stats()
        return JSONResponse({"stats": stats})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post('/api/omega/toggle')
async def api_omega_toggle(request: Request):
    """Activates or deactivates Protocol Omega from the frontend."""
    try:
        import study_mentor
        import shared
        
        data = await request.json()
        action = data.get('action', 'toggle')
        
        if action == 'activate':
            if not shared.omega_active:
                study_mentor.activate()
                return JSONResponse({"status": "activated"})
        elif action == 'deactivate':
            if shared.omega_active:
                study_mentor.deactivate()
                return JSONResponse({"status": "deactivated"})
        else: # toggle
            if shared.omega_active:
                study_mentor.deactivate()
                return JSONResponse({"status": "deactivated"})
            else:
                study_mentor.activate()
                return JSONResponse({"status": "activated"})
                
        return JSONResponse({"status": "unchanged"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post('/api/omega/break')
async def api_omega_break():
    """Manually triggers a short break."""
    try:
        import study_mentor
        import shared
        if shared.omega_active and shared.omega_phase == "focus":
            with study_mentor._omega_lock:
                shared.omega_phase = "short_break"
                shared.omega_phase_remaining = 5 * 60
                shared.push_omega_state()
            return JSONResponse({"status": "break_started"})
        return JSONResponse({"status": "ignored"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ==========================================

# ==========================================
# SPEECH CONTROL ENDPOINTS (Pause / Resume / Status)
# ==========================================

@app.post('/api/speech/pause')
async def api_speech_pause():
    """Toggle pause/resume on Alfred's speech. Returns new state."""
    try:
        import voice_engine
        import shared
        new_paused = voice_engine.toggle_pause()
        shared.push_pause_state(new_paused)
        return JSONResponse({"paused": new_paused, "speaking": voice_engine.is_speaking()})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get('/api/speech/status')
async def api_speech_status():
    """Returns whether Alfred is currently speaking and/or paused."""
    try:
        import voice_engine
        return JSONResponse({
            "speaking": voice_engine.is_speaking(),
            "paused": voice_engine.is_paused()
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ==========================================
# COMMAND CENTER API ENDPOINTS (REAL DATA ONLY)
# ==========================================

@app.get('/api/system')
async def api_system():
    """Returns live system metrics via psutil."""
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        net = psutil.net_io_counters()
        
        # Battery info
        battery = psutil.sensors_battery()
        battery_info = None
        if battery:
            battery_info = {
                "percent": battery.percent,
                "plugged": battery.power_plugged,
            }
        
        # Get top 5 processes by memory (uses 10s cache to avoid redundant psutil scans)
        procs = _get_cached_procs()
        
        return JSONResponse({
            "cpu": round(cpu_percent, 1),
            "ram_used": round(mem.used / (1024**3), 1),
            "ram_total": round(mem.total / (1024**3), 1),
            "ram_percent": mem.percent,
            "disk_used": round(disk.used / (1024**3), 1),
            "disk_total": round(disk.total / (1024**3), 1),
            "disk_percent": disk.percent,
            "net_sent": round(net.bytes_sent / (1024**2), 1),
            "net_recv": round(net.bytes_recv / (1024**2), 1),
            "battery": battery_info,
            "top_procs": procs
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get('/api/osint')
async def api_osint():
    """Returns news headlines and earthquake data."""
    from tools.osint_tools import get_news, get_earthquakes
    try:
        news_raw = get_news("world")
        quake_raw = get_earthquakes()
        
        # Parse news into structured items
        news_items = []
        for line in news_raw.split('\n'):
            line = line.strip()
            if line.startswith('•'):
                news_items.append(line[1:].strip())
        
        # Parse earthquakes into structured items
        quake_items = []
        for line in quake_raw.split('\n'):
            line = line.strip()
            if line.startswith('•'):
                quake_items.append(line[1:].strip())
        
        return JSONResponse({
            "news": news_items[:6],
            "earthquakes": quake_items[:5],
            "updated": datetime.now().strftime("%H:%M:%S")
        })
    except Exception as e:
        return JSONResponse({"news": [], "earthquakes": [], "error": str(e)})

_civic_cache = {"time": 0, "data": None}

@app.get('/api/civic')
def api_civic():
    """Returns the AI District Health Score, cached for 12 hours."""
    from tools.osint_tools import generate_district_health_score
    import time
    from datetime import datetime
    
    current_time = time.time()
    # Cache for 12 hours (43200 seconds)
    if _civic_cache["data"] and (current_time - _civic_cache["time"]) < 43200:
        return JSONResponse(_civic_cache["data"])
        
    try:
        raw_score = generate_district_health_score()
        
        # Parse the concise summary format:
        # "The overall District Health Score for Chikkamagaluru is 66/100 (Grade: B). [Strength]. [Weakness]."
        score = 0
        grade = "N/A"
        
        import re
        score_match = re.search(r'is\s+(\d+)/100', raw_score)
        if score_match:
            score = int(score_match.group(1))
            
        grade_match = re.search(r'\(Grade:\s*([A-F][+-]?)\)', raw_score)
        if grade_match:
            grade = grade_match.group(1)
            
        # Clean up the summary by removing the first sentence
        summary = raw_score
        first_sentence_end = raw_score.find('). ')
        if first_sentence_end != -1:
            summary = raw_score[first_sentence_end + 3:].strip()
            
        data = {
            "score": score,
            "grade": grade,
            "summary": summary,
            "updated": datetime.now().strftime("%H:%M")
        }
        
        _civic_cache["time"] = current_time
        _civic_cache["data"] = data
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get('/api/weather')
async def api_weather():
    """Returns real weather data for the user's city from wttr.in."""
    try:
        url = f"https://wttr.in/{USER_CITY}?format=j1"
        resp = requests.get(url, timeout=8, headers={"User-Agent": "curl"})
        resp.raise_for_status()
        data = resp.json()

        current = data.get("current_condition", [{}])[0]
        weather_today = data.get("weather", [{}])[0]
        astronomy = weather_today.get("astronomy", [{}])[0]
        hourly = weather_today.get("hourly", [])

        # Build 3-hour forecast
        current_hour = datetime.now().hour
        forecast = []
        for h in hourly:
            h_time = int(h.get("time", "0")) // 100
            if h_time >= current_hour and len(forecast) < 4:
                forecast.append({
                    "time": f"{h_time:02d}:00",
                    "temp_c": h.get("tempC", "?"),
                    "rain_chance": int(h.get("chanceofrain", "0")),
                    "description": h.get("weatherDesc", [{}])[0].get("value", "")
                })

        return JSONResponse({
            "city": USER_CITY,
            "temp_c": current.get("temp_C", "?"),
            "feels_like": current.get("FeelsLikeC", "?"),
            "humidity": current.get("humidity", "?"),
            "wind_kmph": current.get("windspeedKmph", "?"),
            "description": current.get("weatherDesc", [{}])[0].get("value", "Unknown"),
            "rain_chance": forecast[0]["rain_chance"] if forecast else 0,
            "sunrise": astronomy.get("sunrise", "?"),
            "sunset": astronomy.get("sunset", "?"),
            "forecast": forecast,
            "updated": datetime.now().strftime("%H:%M:%S")
        })
    except Exception as e:
        return JSONResponse({"error": str(e), "city": USER_CITY}, status_code=500)

@app.get('/api/tracker')
async def api_tracker():
    """Returns ISS position and crypto prices."""
    
    def _fetch_iss():
        try:
            r = requests.get("http://api.open-notify.org/iss-now.json", timeout=5)
            if r.status_code == 200:
                pos = r.json().get("iss_position", {})
                return {"lat": float(pos.get("latitude", 0)), "lng": float(pos.get("longitude", 0))}
        except Exception:
            pass
        return {"lat": 0, "lng": 0}
    
    def _fetch_crypto():
        try:
            r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd&include_24hr_change=true", timeout=5)
            if r.status_code == 200:
                data = r.json()
                return {
                    "BTC": {"price": data.get("bitcoin", {}).get("usd", 0), "change": round(data.get("bitcoin", {}).get("usd_24h_change", 0), 2)},
                    "ETH": {"price": data.get("ethereum", {}).get("usd", 0), "change": round(data.get("ethereum", {}).get("usd_24h_change", 0), 2)},
                    "SOL": {"price": data.get("solana", {}).get("usd", 0), "change": round(data.get("solana", {}).get("usd_24h_change", 0), 2)}
                }
        except Exception:
            pass
        return {}
    
    # Run both fetches concurrently without blocking the event loop
    iss, crypto = await asyncio.gather(
        asyncio.to_thread(_fetch_iss),
        asyncio.to_thread(_fetch_crypto)
    )
    
    return JSONResponse({"iss": iss, "crypto": crypto, "updated": datetime.now().strftime("%H:%M:%S")})

# ── Cached process list (reduces psutil overhead from 3s polls) ──
_proc_cache = {"data": [], "ts": 0}

def _get_cached_procs():
    now = time.time()
    if now - _proc_cache["ts"] > 10:  # Cache for 10 seconds
        procs = []
        for p in psutil.process_iter(['name', 'memory_percent', 'cpu_percent']):
            try:
                info = p.info
                if info['memory_percent'] and info['memory_percent'] > 0.1:
                    procs.append({"name": info['name'][:20], "mem": round(info['memory_percent'], 1), "cpu": round(info['cpu_percent'] or 0, 1)})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        procs.sort(key=lambda x: x['mem'], reverse=True)
        _proc_cache["data"] = procs[:5]
        _proc_cache["ts"] = now
    return _proc_cache["data"]

@app.get('/api/spotify/now_playing')
async def api_spotify_now_playing():
    """Returns what is currently playing on Spotify."""
    try:
        from tools.core_tools import get_now_playing
        result = get_now_playing()
        if "not playing" in result.lower() or "error" in result.lower() or "no active" in result.lower():
            return JSONResponse({"playing": False})
        # Parse the result string
        parts = result.split(" by ")
        song = parts[0].replace("Currently playing: ", "").replace("Now playing: ", "").strip().strip('"').strip("'")
        artist = parts[1].strip() if len(parts) > 1 else "Unknown"
        # Clean up artist (remove trailing album info)
        if " from " in artist:
            artist = artist.split(" from ")[0].strip()
        if " on " in artist:
            artist = artist.split(" on ")[0].strip()
        return JSONResponse({"song": song, "artist": artist, "playing": True})
    except Exception as e:
        return JSONResponse({"playing": False, "error": str(e)})

# ==========================================
# Geospatial Tracker WebSockets
# ==========================================
connected_clients: list[WebSocket] = []

@app.websocket("/ws/live")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.append(ws)
    try:
        while True:
            await ws.receive_text()  # keep-alive
    except WebSocketDisconnect:
        connected_clients.remove(ws)
    except Exception as e:
        if ws in connected_clients:
            connected_clients.remove(ws)

async def broadcast_loop():
    """Runs every 10 seconds — pulls data from Gemini / OpenSky and broadcasts."""
    print("[System] Background Geospatial broadcast loop started.")
    while True:
        try:
            if connected_clients:
                geojson = await run_detection_cycle()
                payload = json.dumps(geojson)
                for client in connected_clients.copy():
                    try:
                        await client.send_text(payload)
                    except:
                        if client in connected_clients:
                            connected_clients.remove(client)
        except Exception as e:
            print(f"Cycle error: {e}")
        await asyncio.sleep(10)  # Polling interval

# The broadcast_loop is now started by the FastAPI lifespan manager above.

def run_uvicorn():
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

if __name__ == '__main__':
    # Start Alfred's logic loop in a background daemon thread
    alfred_thread = threading.Thread(target=alfred.main_loop, daemon=True)
    alfred_thread.start()
    
    # Start the FastAPI server in a background thread
    server_thread = threading.Thread(target=run_uvicorn, daemon=True)
    server_thread.start()
    
    # Start the Telegram Bot remote link
    try:
        import telegram_bot
        telegram_thread = threading.Thread(target=telegram_bot.start_telegram_bot_loop, daemon=True)
        telegram_thread.start()
    except Exception as e:
        print(f"[System] Failed to start Telegram Bot: {e}")
    
    # Start the Screen-Pipe Infinite Memory Daemon
    try:
        import screen_pipe
        screen_pipe.start_daemon()
    except Exception as e:
        print(f"[System] Failed to start Screen Pipe Daemon: {e}")
    
    # Launch Alfred as a standalone desktop app using Chrome/Edge --app mode
    # This creates a clean, frameless window (no tabs, no address bar) like Spotify
    import subprocess, shutil
    
    url = 'http://127.0.0.1:8000'
    launched = False
    
    # Try Microsoft Edge first (pre-installed on Windows), then Chrome
    browser_paths = [
        shutil.which('msedge') or r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        shutil.which('chrome') or r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        shutil.which('chromium'),
    ]
    
    for browser in browser_paths:
        if browser and os.path.exists(browser):
            print(f"\n[System] Launching Alfred Protocol as Desktop App via {os.path.basename(browser)}...")
            subprocess.Popen([browser, f'--app={url}', '--window-size=1400,850'])
            launched = True
            break
    
    if not launched:
        import webbrowser
        print(f"\n[System] Opening Alfred Protocol in default browser...")
        webbrowser.open(url)
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[System] Alfred shutting down. Goodbye, sir.")
