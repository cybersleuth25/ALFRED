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
from fastapi.responses import HTMLResponse, JSONResponse, Response
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
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

web_dir = os.path.dirname(__file__)
dist_dir = os.path.abspath(os.path.join(web_dir, '..', 'frontend', 'dist'))

if os.path.exists(dist_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(dist_dir, 'assets')), name="assets")

incident_dir = os.path.abspath(os.path.join(web_dir, '..', 'assets', 'incidents'))
os.makedirs(incident_dir, exist_ok=True)
app.mount("/incident_images", StaticFiles(directory=incident_dir), name="incident_images")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    index_path = os.path.join(dist_dir, 'index.html')
    if os.path.exists(index_path):
        with open(index_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<body><h1>Alfred</h1><p>UI Native Build Mode - Please run 'npm run build' in frontend folder</p></body>")

ui_active_connections = 0

@app.get('/stream')
async def stream(request: Request):
    """EventSource endpoint for standard Alfred events."""
    global ui_active_connections
    ui_active_connections += 1
    
    async def delayed_shutdown():
        await asyncio.sleep(10.0)
        if ui_active_connections <= 0:
            print("\n[System] UI disconnected (Window closed). Shutting down Alfred backend...")
            os._exit(0)

    async def event_generator():
        global ui_active_connections
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.to_thread(shared.event_queue.get)
                    yield json.dumps(event)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    print(f"Stream error: {e}")
                    await asyncio.sleep(1)
        finally:
            ui_active_connections -= 1
            if ui_active_connections <= 0:
                asyncio.create_task(delayed_shutdown())

    return EventSourceResponse(event_generator())

@app.post('/set_focus')
async def set_focus(request: Request):
    data = await request.json()
    shared.focus_mode_active = data.get('focus_mode', False)
    return {"status": "success", "focus_mode": shared.focus_mode_active}



# ==========================================
# FOCUS MODE (STUDY MENTOR) ENDPOINTS
# ==========================================

@app.get('/api/focus/status')
async def api_focus_status():
    """Returns the current real-time state of Focus Mode."""
    try:
        import shared
        return JSONResponse({
            "active": shared.omega_active,
            "lockdown": getattr(shared, 'omega_lockdown', False),
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

@app.get('/api/focus/history')
async def api_focus_history():
    """Returns the last 10 study sessions."""
    try:
        import memory_engine
        sessions = memory_engine.get_study_history(10)
        return JSONResponse({"sessions": sessions})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get('/api/focus/stats')
async def api_focus_stats():
    """Returns aggregate study stats."""
    try:
        import memory_engine
        stats = memory_engine.get_study_stats()
        return JSONResponse({"stats": stats})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post('/api/focus/toggle')
async def api_focus_toggle(request: Request):
    """Activates or deactivates Focus Mode from the frontend."""
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

@app.post('/api/focus/break')
async def api_focus_break():
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

@app.post('/api/focus/lockdown')
async def api_focus_lockdown():
    """Toggles Lockdown mode during an active study session."""
    try:
        import study_mentor
        import shared
        if not shared.omega_active:
            return JSONResponse({"error": "Focus Mode is not active"}, status_code=400)
        if getattr(shared, 'omega_lockdown', False):
            msg = study_mentor.disengage_lockdown()
            return JSONResponse({"status": "disengaged", "message": msg, "lockdown": False})
        else:
            msg = study_mentor.engage_lockdown()
            return JSONResponse({"status": "engaged", "message": msg, "lockdown": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ==========================================
# PERSONA ENGINE ENDPOINTS
# ==========================================

@app.get('/api/persona/active')
async def api_persona_active():
    """Returns the current active persona profile and color palette."""
    try:
        import persona_engine
        persona = persona_engine.get_active_persona()
        return JSONResponse(persona.to_dict())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get('/api/persona/list')
async def api_persona_list():
    """Returns all available personas."""
    try:
        import persona_engine
        personas = persona_engine.load_all_personas()
        return JSONResponse({name: p.to_dict() for name, p in personas.items()})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post('/api/persona/switch')
async def api_persona_switch(request: Request):
    """Switches active persona by name."""
    try:
        import persona_engine
        data = await request.json()
        target = data.get("persona", "alfred")
        res = persona_engine.switch_persona(target)
        active = persona_engine.get_active_persona()
        return JSONResponse({"status": "success", "message": res, "active": active.to_dict()})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ==========================================
# RESEARCH SWARM ENDPOINTS
# ==========================================

@app.get('/api/research/dossiers')
async def api_research_dossiers():
    """Lists all compiled research dossiers in Alfred_Workspace/research/."""
    try:
        research_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', 'Alfred_Workspace', 'research')
        )
        if not os.path.exists(research_dir):
            return JSONResponse({"dossiers": []})
        
        files = []
        for fname in os.listdir(research_dir):
            if fname.endswith('.md'):
                fpath = os.path.join(research_dir, fname)
                stat = os.stat(fpath)
                files.append({
                    "filename": fname,
                    "size_bytes": stat.st_size,
                    "modified": stat.st_mtime,
                    "title": fname.replace(".md", "").replace("_", " ").title()
                })
        files.sort(key=lambda x: x["modified"], reverse=True)
        return JSONResponse({"dossiers": files})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get('/api/research/dossier/{filename}')
async def api_research_dossier_content(filename: str):
    """Fetches the markdown content of a specific dossier."""
    try:
        safe_name = os.path.basename(filename)
        research_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', 'Alfred_Workspace', 'research')
        )
        target_path = os.path.join(research_dir, safe_name)
        if not os.path.exists(target_path):
            return JSONResponse({"error": "Dossier not found"}, status_code=404)
        
        with open(target_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return JSONResponse({"filename": safe_name, "content": content})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get('/api/camera/feed')
async def camera_feed():
    """MJPEG stream of the security camera for the frontend."""
    import cv2
    import security_engine
    from starlette.responses import StreamingResponse
    
    async def generate_frames():
        while True:
            frame = security_engine.get_latest_frame()
            if frame is not None:
                # Resize for bandwidth efficiency
                small = cv2.resize(frame, (320, 240))
                _, buffer = cv2.imencode('.jpg', small, [cv2.IMWRITE_JPEG_QUALITY, 55])
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            await asyncio.sleep(0.5)  # ~2 FPS
    
    return StreamingResponse(generate_frames(), media_type='multipart/x-mixed-replace; boundary=frame')

@app.get('/api/camera/status')
async def camera_status():
    """Returns whether the camera is available."""
    import security_engine
    frame = security_engine.get_latest_frame()
    return JSONResponse({"available": frame is not None})

@app.post('/api/incidents/clear')
async def clear_incidents():
    import shared
    shared.unseen_incidents = []
    shared.push_sentry_state()
    return JSONResponse({"status": "cleared"})

@app.get('/api/focus/heatmap')
async def api_focus_heatmap():
    """Returns hourly focus heatmap data for today."""
    try:
        import memory_engine
        data = memory_engine.get_hourly_focus_data()
        return JSONResponse({"heatmap": data})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post('/api/focus/lockdown')
async def api_focus_lockdown(request: Request):
    """Toggle lockdown mode from the frontend."""
    try:
        import study_mentor
        import shared
        if shared.omega_lockdown:
            result = study_mentor.disengage_lockdown()
        else:
            result = study_mentor.engage_lockdown()
        return JSONResponse({"lockdown": shared.omega_lockdown, "message": result})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ==========================================

# ==========================================
# CONTEXTUAL AWARENESS ENDPOINTS
# ==========================================

@app.get('/api/context/current')
async def api_context_current():
    """Returns the current contextual awareness state (activity, presence, dwell time)."""
    try:
        import context_engine
        return JSONResponse(context_engine.get_current_context())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get('/api/context/timeline')
async def api_context_timeline(minutes: int = 60):
    """Returns the activity timeline for the last N minutes."""
    try:
        import context_engine
        timeline = context_engine.get_activity_timeline(minutes)
        return JSONResponse({"timeline": timeline, "minutes": minutes})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ==========================================
# WORKFLOW ROUTINES ENDPOINTS
# ==========================================

@app.get('/api/routines')
async def api_get_routines():
    """Returns list of all configured routines."""
    try:
        import memory_engine
        return JSONResponse({"routines": memory_engine.get_all_routines()})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post('/api/routines')
async def api_save_routine(req: Request):
    """Creates or updates a routine."""
    try:
        import memory_engine
        data = await req.json()
        name = data.get("name")
        display_name = data.get("display_name", name.title())
        triggers = data.get("trigger_phrases", [name])
        description = data.get("description", "")
        steps = data.get("steps", [])
        
        routine_id = memory_engine.save_routine(
            name=name,
            display_name=display_name,
            trigger_phrases=triggers,
            description=description,
            steps=steps,
            is_builtin=False
        )
        return JSONResponse({"success": True, "id": routine_id, "name": name})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post('/api/routines/execute')
async def api_execute_routine(req: Request):
    """Executes a routine by name or ID."""
    try:
        import routine_engine
        data = await req.json()
        name_or_id = data.get("name") or data.get("id")
        if not name_or_id:
            return JSONResponse({"error": "Routine name or id is required"}, status_code=400)
        res = routine_engine.execute_routine(name_or_id)
        return JSONResponse({"success": True, "message": res})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.delete('/api/routines/{routine_id}')
async def api_delete_routine(routine_id: int):
    """Deletes a custom routine."""
    try:
        import memory_engine
        deleted = memory_engine.delete_routine(routine_id)
        return JSONResponse({"success": deleted})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post('/api/routines/generate')
async def api_generate_routine(req: Request):
    """Uses LLM to compile natural language into a structured routine."""
    try:
        import routine_engine
        data = await req.json()
        prompt = data.get("prompt", "")
        if not prompt:
            return JSONResponse({"error": "Prompt is required"}, status_code=400)
        res = routine_engine.create_routine_from_prompt(prompt)
        return JSONResponse(res)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ==========================================
# MOOD & EMOTIONAL INTELLIGENCE ENDPOINTS
# ==========================================

@app.get('/api/mood/current')
async def api_mood_current():
    """Returns current live emotion and recent dominant mood."""
    try:
        import mood_engine
        return JSONResponse(mood_engine.get_current_mood())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get('/api/mood/timeline')
async def api_mood_timeline(hours: int = 24):
    """Returns historical mood snapshots for charting."""
    try:
        import mood_engine
        timeline = mood_engine.get_mood_timeline(hours=hours)
        return JSONResponse({"timeline": timeline, "hours": hours})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ==========================================
# KNOWLEDGE GRAPH (SECOND BRAIN) ENDPOINTS
# ==========================================

@app.get('/api/knowledge/graph')
async def api_knowledge_graph():
    """Returns nodes and edges formatted for D3.js force graph visualization."""
    try:
        import knowledge_graph
        return JSONResponse(knowledge_graph.get_graph_data())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get('/api/knowledge/node/{name}')
async def api_knowledge_node(name: str, depth: int = 2):
    """Returns multi-hop subgraph around a specific entity."""
    try:
        import knowledge_graph
        subgraph = knowledge_graph.query_subgraph(name, depth=depth)
        return JSONResponse(subgraph)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post('/api/knowledge/extract')
async def api_knowledge_extract(req: Request):
    """Extracts entities and relationships from text and updates the graph."""
    try:
        import knowledge_graph
        data = await req.json()
        text = data.get("text", "")
        if not text:
            return JSONResponse({"error": "Text is required"}, status_code=400)
        res = knowledge_graph.extract_and_link_from_text(text)
        return JSONResponse(res)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post('/api/knowledge/query')
async def api_knowledge_query(req: Request):
    """Performs natural language query against the knowledge graph."""
    try:
        import knowledge_graph
        data = await req.json()
        query = data.get("query", "")
        summary = knowledge_graph.query_knowledge_summary(query)
        return JSONResponse({"summary": summary})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ==========================================
# FEATURE 5: SECURITY & DIGITAL TRIPWIRE ENDPOINTS
# ==========================================

@app.get('/api/security/incidents')
async def api_security_incidents(limit: int = 50, unresolved_only: bool = False):
    """Returns logged security incidents and evidence snapshot paths."""
    try:
        import memory_engine
        incidents = memory_engine.get_security_incidents(limit=limit, unresolved_only=unresolved_only)
        return JSONResponse({"incidents": incidents})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post('/api/security/incidents/resolve')
async def api_security_resolve(req: Request):
    """Marks a security incident as resolved."""
    try:
        import memory_engine
        data = await req.json()
        inc_id = data.get("id")
        if not inc_id:
            return JSONResponse({"error": "Incident id required"}, status_code=400)
        memory_engine.resolve_security_incident(int(inc_id))
        return JSONResponse({"success": True, "resolved_id": inc_id})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post('/api/security/kill_process')
async def api_security_kill_process(req: Request):
    """Kills a rogue or suspicious process by PID."""
    try:
        import tripwire_engine
        data = await req.json()
        pid = data.get("pid")
        if not pid:
            return JSONResponse({"error": "PID is required"}, status_code=400)
        res = tripwire_engine.kill_process(int(pid))
        return JSONResponse(res)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get('/api/security/status')
async def api_security_status():
    """Returns live operational status of Digital Tripwire."""
    try:
        import tripwire_engine
        return JSONResponse(tripwire_engine.get_tripwire_status())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ==========================================
# SCREEN CO-PILOT ENDPOINTS
# ==========================================

@app.post('/api/screen/copilot')
async def api_screen_copilot(req: Request):
    """Executes Multimodal Screen Co-Pilot analysis."""
    try:
        import screen_copilot
        data = await req.json() if await req.body() else {}
        query = data.get("query", "What is on my screen?")
        mode = data.get("mode", "general")
        res = screen_copilot.analyze_screen(query, mode=mode)
        return JSONResponse(res)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get('/api/screen/snapshot')
async def api_screen_snapshot():
    """Returns real-time JPEG capture of primary desktop."""
    try:
        import screen_copilot
        jpeg_bytes = screen_copilot.capture_screen_jpeg_bytes()
        return Response(content=jpeg_bytes, media_type="image/jpeg")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ==========================================
# ACOUSTIC SENTRY EAR ENDPOINTS
# ==========================================

@app.post('/api/acoustic/toggle')
async def api_acoustic_toggle(req: Request):
    """Toggles acoustic ear monitoring."""
    try:
        import acoustic_engine
        data = await req.json() if await req.body() else {}
        enabled = data.get("enabled", True)
        if enabled:
            acoustic_engine.start_acoustic_daemon()
        else:
            acoustic_engine.stop_acoustic_daemon()
        return JSONResponse(acoustic_engine.get_status())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get('/api/acoustic/status')
async def api_acoustic_status():
    """Returns live status of acoustic sentry ear."""
    try:
        import acoustic_engine
        return JSONResponse(acoustic_engine.get_status())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ==========================================
# EVENING EXECUTIVE DEBRIEF ENDPOINTS
# ==========================================

@app.post('/api/debrief/run')
async def api_debrief_run(req: Request):
    """Generates and delivers the evening executive debrief."""
    try:
        import debrief_engine
        data = await req.json() if await req.body() else {}
        speak = data.get("speak", False)
        res = debrief_engine.generate_executive_debrief(speak=speak)
        return JSONResponse(res)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get('/api/debrief/latest')
async def api_debrief_latest():
    """Fetches the latest markdown debrief report."""
    try:
        import debrief_engine
        return JSONResponse(debrief_engine.get_latest_debrief())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post('/api/command')
async def api_command(req: Request):
    """Executes a user command submitted via the UI command line."""
    try:
        import llm_engine, voice_engine, persona_engine, commands
        data = await req.json() if await req.body() else {}
        command_text = data.get("command", "").strip()
        if not command_text:
            return JSONResponse({"error": "Empty command"}, status_code=400)
            
        persona = persona_engine.get_active_persona()
        shared.push_log(command_text, author="User")
        
        # Check direct persona switch or fast paths
        target = persona_engine.extract_persona_name(command_text.lower())
        if target and any(phrase in command_text.lower() for phrase in commands.PERSONA_SWITCH):
            persona_engine.switch_persona(target)
            p = persona_engine.get_active_persona()
            reply = f"{p.display_name} online and ready."
            shared.push_log(reply, author=p.display_name)
            voice_engine.speak(reply)
            return JSONResponse({"success": True, "reply": reply})

        shared.push_state("processing")
        reply = llm_engine.generate_response(command_text)
        
        shared.push_state("speaking")
        shared.push_log(reply, author=persona.display_name)
        shared.push_caption(reply)
        voice_engine.speak(reply)
        shared.push_caption("")
        shared.push_state("idle")
        
        return JSONResponse({"success": True, "reply": reply})
    except Exception as e:
        shared.push_state("idle")
        return JSONResponse({"error": str(e)}, status_code=500)

# ==========================================
# MEETING NOTETAKER & STUDIO ENDPOINTS
# ==========================================

@app.get('/api/meeting/status')
async def api_meeting_status():
    """Returns current live recording status of Meeting Notetaker."""
    try:
        from tools import developer_tools
        return JSONResponse(developer_tools.get_meeting_status_dict())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post('/api/meeting/start')
async def api_meeting_start(req: Request):
    """Starts meeting recording from HUD."""
    try:
        data = await req.json() if await req.body() else {}
        title = data.get("title", "")
        from tools import developer_tools
        msg = developer_tools.meeting_notetaker("start", title=title)
        import shared
        shared.push_meeting_state(developer_tools.get_meeting_status_dict())
        return JSONResponse({"success": True, "message": msg, "status": developer_tools.get_meeting_status_dict()})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post('/api/meeting/stop')
async def api_meeting_stop():
    """Stops meeting recording and returns generated executive notes."""
    try:
        from tools import developer_tools
        res = developer_tools.meeting_notetaker("stop")
        import shared
        shared.push_meeting_state(developer_tools.get_meeting_status_dict())
        return JSONResponse({"success": True, "notes": res, "status": developer_tools.get_meeting_status_dict()})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get('/api/meeting/history')
async def api_meeting_history():
    """Returns list of past meeting markdown notes."""
    try:
        from tools import developer_tools
        notes = developer_tools.list_meeting_notes()
        return JSONResponse({"meetings": notes})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get('/api/meeting/note/{filename}')
async def api_meeting_get_note(filename: str):
    """Returns the markdown text of a specific meeting note."""
    try:
        from tools import developer_tools
        content = developer_tools.read_meeting_note(filename)
        if not content:
            return JSONResponse({"error": "Note not found"}, status_code=404)
        return JSONResponse({"filename": filename, "content": content})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ==========================================
# CHIEF OF STAFF & HUD INTELLIGENCE ENDPOINTS
# ==========================================

@app.get('/api/chief/agenda')
async def api_chief_agenda(date: str = "today"):
    """Returns agenda, conflicts, and focus slots for the HUD."""
    try:
        import chief_of_staff
        return JSONResponse({"agenda": chief_of_staff.get_quick_agenda(date)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get('/api/chief/dossier')
async def api_chief_dossier():
    """Returns the master Chief of Staff executive dossier for the HUD."""
    try:
        import chief_of_staff
        return JSONResponse({"dossier": chief_of_staff.get_daily_executive_dossier()})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get('/api/developer/git_status')
async def api_developer_git_status(project: str = ""):
    """Returns git status diff for a specific project or all projects for HUD."""
    try:
        from tools import developer_tools
        return JSONResponse({"status": developer_tools.git_status_diff(project)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

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

@app.post('/api/speech/stop')
async def api_speech_stop():
    """Immediately halts Alfred's speech, clears caption, pauses the main loop, and stops the camera."""
    try:
        import voice_engine
        import shared
        voice_engine.stop_speaking()
        shared.alfred_halted = True
        shared.push_state("idle")
        shared.push_caption("")
        try:
            shared.event_queue.put_nowait({"type": "halted", "value": True})
        except Exception:
            pass
        return JSONResponse({"stopped": True, "halted": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post('/api/speech/resume')
async def api_speech_resume():
    """Clears the halted flag so Alfred's main loop resumes listening, and restarts the camera."""
    try:
        import shared
        shared.alfred_halted = False
        shared.push_state("listening")
        try:
            shared.event_queue.put_nowait({"type": "halted", "value": False})
        except Exception:
            pass
        return JSONResponse({"halted": False})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get('/api/speech/status')
async def api_speech_status():
    """Returns whether Alfred is currently speaking, paused, and/or halted."""
    try:
        import voice_engine
        import shared
        return JSONResponse({
            "speaking": voice_engine.is_speaking(),
            "paused": voice_engine.is_paused(),
            "halted": getattr(shared, 'alfred_halted', False)
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

_weather_cache = None
_weather_cache_time = 0

@app.get('/api/weather')
async def api_weather():
    """Returns real weather data for the user's city from wttr.in with caching and fallback."""
    global _weather_cache, _weather_cache_time
    now = time.time()
    # Return cache if less than 5 minutes old
    if _weather_cache and (now - _weather_cache_time < 300):
        return JSONResponse(_weather_cache)

    try:
        url = f"https://wttr.in/{USER_CITY}?format=j1"
        resp = requests.get(url, timeout=6, headers={"User-Agent": "curl"})
        if resp.status_code == 200:
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
                        "temp_c": h.get("tempC", "24"),
                        "rain_chance": int(h.get("chanceofrain", "0")),
                        "description": h.get("weatherDesc", [{}])[0].get("value", "Partly Cloudy")
                    })

            weather_res = {
                "city": USER_CITY,
                "temp_c": current.get("temp_C", "24"),
                "feels_like": current.get("FeelsLikeC", "25"),
                "humidity": current.get("humidity", "65"),
                "wind_kmph": current.get("windspeedKmph", "12"),
                "description": current.get("weatherDesc", [{}])[0].get("value", "Partly Cloudy"),
                "rain_chance": forecast[0]["rain_chance"] if forecast else 0,
                "sunrise": astronomy.get("sunrise", "06:12 AM"),
                "sunset": astronomy.get("sunset", "06:38 PM"),
                "forecast": forecast,
                "updated": datetime.now().strftime("%H:%M:%S")
            }
            _weather_cache = weather_res
            _weather_cache_time = now
            return JSONResponse(weather_res)
    except Exception as e:
        print(f"[Weather API] wttr.in query failed: {e}")

    # Return cached data if available even if older
    if _weather_cache:
        return JSONResponse(_weather_cache)

    # Return safe fallback so WeatherPanel never stays stuck on 'Acquiring data...'
    return JSONResponse({
        "city": USER_CITY,
        "temp_c": "24",
        "feels_like": "25",
        "humidity": "62",
        "wind_kmph": "11",
        "description": "Partly Cloudy",
        "rain_chance": 10,
        "sunrise": "06:15 AM",
        "sunset": "06:40 PM",
        "forecast": [
            {"time": "12:00", "temp_c": "26", "rain_chance": 10, "description": "Partly Cloudy"},
            {"time": "15:00", "temp_c": "27", "rain_chance": 20, "description": "Sunny"},
            {"time": "18:00", "temp_c": "23", "rain_chance": 15, "description": "Clear"},
            {"time": "21:00", "temp_c": "20", "rain_chance": 5, "description": "Clear"}
        ],
        "updated": datetime.now().strftime("%H:%M:%S")
    })

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

def _kill_stale_port(port):
    """Kill any leftover process holding our port (prevents [Errno 10048] on restart)."""
    try:
        for conn in psutil.net_connections(kind='inet'):
            if conn.laddr.port == port and conn.status == 'LISTEN':
                try:
                    proc = psutil.Process(conn.pid)
                    # Don't kill ourselves
                    if proc.pid == os.getpid():
                        continue
                    print(f"[System] Killing stale process on port {port}: {proc.name()} (PID {proc.pid})")
                    proc.kill()
                    proc.wait(timeout=5)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                    pass
    except Exception as e:
        print(f"[System] Port cleanup warning: {e}")

def run_uvicorn():
    import uvicorn
    _kill_stale_port(8000)
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
    browser_process = None

    # Wait up to 6 seconds for Uvicorn to be ready
    print("[System] Waiting for backend server to initialize...")
    for _ in range(12):
        try:
            r = requests.get(url, timeout=0.5)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.5)
    
    # Try Microsoft Edge first (pre-installed on Windows), then Chrome
    browser_paths = [
        shutil.which('msedge') or r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        shutil.which('chrome') or r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        shutil.which('chromium'),
    ]
    
    for browser in browser_paths:
        if browser and os.path.exists(browser):
            print(f"\n[System] Launching Alfred Protocol as Desktop App via {os.path.basename(browser)}...")
            browser_process = subprocess.Popen([browser, f'--app={url}', '--window-size=1400,850'])
            break
    
    if not browser_process:
        import webbrowser
        print(f"\n[System] Opening Alfred Protocol in default browser...")
        webbrowser.open(url)
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[System] Alfred shutting down. Goodbye, sir.")
        os._exit(0)
