import memory_engine
from tools import system_tools
from tools import osint_tools
from tools import browser_tools
import scholar_engine
from datetime import datetime
import requests
import ctypes
import os
import subprocess
import webbrowser
import urllib.parse
import re as _re
import json as _json

def set_dynamic_reminder(minutes: int, topic: str) -> str:
    """
    Schedules a dynamic reminder for the given topic in the specified number of minutes.
    The background cron engine will voice the reminder.
    """
    from datetime import datetime, timedelta
    
    try:
        minutes = int(minutes)
    except:
        return "Failed. Ensure 'minutes' is a valid integer."
        
    deadline = (datetime.now() + timedelta(minutes=minutes)).isoformat()
    memory_engine.add_task(topic, deadline)
    return f"Reminder set successfully for {minutes} minutes from now: '{topic}'"

def add_reminder(task: str, deadline: str = None) -> str:
    """
    Saves a reminder or task to the database. Deadline is optional (ISO format string).
    """
    memory_engine.add_task(task, deadline)
    if deadline:
        return f"Task '{task}' added successfully with deadline: {deadline}"
    return f"Task '{task}' added successfully."

def list_reminders() -> str:
    """
    Returns a string of all pending reminders from the database.
    """
    tasks = memory_engine.get_pending_tasks()
    if not tasks:
        return "You have no pending tasks."
    
    output = "Here are the pending tasks:\n"
    for idx, t in enumerate(tasks):
        output += f"{idx + 1}. {t['task']} (Added: {t['added_at'][:10]})\n"
    return output

def complete_reminder(task_id: int) -> str:
    """
    Marks a task as completed in the database by its ID.
    """
    memory_engine.complete_task(task_id)
    return f"Task ID {task_id} completed successfully."

def delete_reminder(task_id: int) -> str:
    """
    Permanently deletes a task from the database by its ID.
    """
    memory_engine.delete_task(task_id)
    return f"Task ID {task_id} deleted successfully."

def clear_all_reminders() -> str:
    """
    Permanently deletes ALL tasks from the database.
    """
    memory_engine.clear_all_tasks()
    return "All tasks and reminders have been successfully deleted."

def remember_fact(fact: str) -> str:
    """
    Permanently saves a fact about the user (e.g. preferences, family members, location).
    """
    memory_engine.add_user_fact(fact)
    return f"I have committed this to memory: '{fact}'."

def forget_fact(fact_id: int) -> str:
    """
    Deletes a previously learned fact by its ID if it is incorrect or outdated.
    """
    memory_engine.delete_user_fact(fact_id)
    return f"Fact ID {fact_id} has been forgotten."

def journal_entry(content: str) -> str:
    """
    Appends a new entry to the user's journal file with a timestamp.
    """
    journal_path = "C:/VS code/JARVIS/Alfred_Workspace/journal.txt"
    try:
        with open(journal_path, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {content}\n")
        return "Journal entry saved successfully."
    except Exception as e:
        return f"Failed to write to journal: {str(e)}"

def read_journal() -> str:
    """
    Reads the user's journal file. Returns the last 10 entries if it exists.
    """
    journal_path = "C:/VS code/JARVIS/Alfred_Workspace/journal.txt"
    try:
        with open(journal_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if not lines:
                return "The journal is currently empty."
            # Return the last 10 lines to prevent context window overflow
            return "".join(lines[-10:])
    except FileNotFoundError:
        return "The journal file does not exist yet."
    except Exception as e:
        return f"Failed to read journal: {str(e)}"

def check_weather(city: str = None) -> str:
    """
    Fetches the current weather for the user's city.
    Uses USER_CITY from .env (defaults to Chikkamagaluru) instead of IP geolocation.
    """
    try:
        from dotenv import load_dotenv
        load_dotenv()
        if not city:
            city = os.getenv("USER_CITY", "Chikkamagaluru")
        
        url = f"https://wttr.in/{city}?format=%l:+%C,+%t,+feels+like+%f,+humidity+%h,+wind+%w"
        resp = requests.get(url, timeout=5, headers={"User-Agent": "curl"})
        resp.raise_for_status()
        return resp.text.strip()
    except Exception as e:
        return f"Failed to fetch weather: {e}"

def launch_application(app_name: str) -> str:
    """
    Launches a desktop application asynchronously without blocking the AI.
    For Chromium browsers, automatically enables CDP debugging port.
    """
    app_lower = app_name.lower().strip()
    
    # Browser debug port mapping for CDP (Chrome DevTools Protocol)
    _CDP_PORTS = {'chrome': 9223, 'google chrome': 9223, 'edge': 9222, 'msedge': 9222, 'brave': 9224}
    
    # Very heavy synonym map to catch LLM typos and common intents
    app_map = {
        'spotify': ['spotify', 'spotify:'],
        'spotifi': ['spotify', 'spotify:'], 
        'chrome': ['chrome'],
        'google chrome': ['chrome'],
        'notepad': ['notepad'],
        'calculator': ['calc'],
        'explorer': ['explorer'],
        'files': ['explorer'],
        'edge': ['msedge', 'microsoft-edge:'],
        'youtube': ['https://youtube.com'],
        'discord': ['discord', 'Discord'],
        'brave': ['brave'],
    }
    
    targets = app_map.get(app_lower, [app_lower])
    
    try:
        # If it's a Chromium browser, kill existing instances first then launch with remote debugging
        if app_lower in _CDP_PORTS:
            port = _CDP_PORTS[app_lower]
            # Map app name to process name for taskkill
            _PROCESS_NAMES = {'chrome': 'chrome.exe', 'google chrome': 'chrome.exe', 'edge': 'msedge.exe', 'msedge': 'msedge.exe', 'brave': 'brave.exe'}
            proc_name = _PROCESS_NAMES.get(app_lower)
            if proc_name:
                subprocess.run(f"taskkill /F /IM {proc_name}", shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                import time as _time; _time.sleep(2)
            for target in targets:
                subprocess.Popen(f"start {target} --remote-debugging-port={port}", shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return f"Launch signal sent for {app_name} (with tab control enabled on port {port})."
        
        for target in targets:
            subprocess.Popen(f"start {target}", shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
        return f"Launch signal sent for {app_name}."
    except Exception as e:
        return f"Failed to send launch signal for {app_name}. Error: {e}"

def toggle_system_volume(action: str) -> str:
    """
    Controls the Windows system volume. action can be 'mute' or 'unmute'.
    """
    VK_VOLUME_MUTE = 0xAD
    KEYEVENTF_KEYUP = 0x0002
    
    # Send the hardware keystroke for Mute/Unmute toggle
    ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, 0, 0)
    ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, KEYEVENTF_KEYUP, 0)
    
    return f"System volume has been toggled ({action})."

def play_music(song_query: str) -> str:
    """
    Searches Spotify via official API. If 'on youtube' is in query, or if Spotify fails,
    it falls back to scraping and launching YouTube fullscreen in the browser.
    """
    import base64
    import webbrowser
    import re

    def _play_on_youtube(q: str):
        q_clean = q.lower().replace("on youtube", "").replace("in youtube", "").replace("youtube", "").strip()
        query_string = urllib.parse.urlencode({"search_query": q_clean})
        try:
            import urllib.request
            req = urllib.request.Request("https://www.youtube.com/results?" + query_string, headers={'User-Agent': 'Mozilla/5.0'})
            html_content = urllib.request.urlopen(req)
            search_results = re.findall(r'watch\?v=(\S{11})', html_content.read().decode('utf-8', errors='ignore'))
            if search_results:
                video_url = "https://www.youtube.com/watch?v=" + search_results[0]
                webbrowser.open(video_url)
                return f"Now playing '{q_clean}' on YouTube."
        except Exception:
            pass
        # Final fallback: just open search
        webbrowser.open("https://www.youtube.com/results?" + query_string)
        return f"Opened YouTube search for '{q_clean}'."

    if "youtube" in song_query.lower():
        return _play_on_youtube(song_query)
    
    # User's Spotify Developer Credentials
    CLIENT_ID = "20caa4dbf24e4c288bbaad1e2c0d576d"
    CLIENT_SECRET = "6bf42c1ee9c647d3be1978467910576c"
    
    try:
        # Step 1: Get an Access Token using Client Credentials Flow
        auth_string = f"{CLIENT_ID}:{CLIENT_SECRET}"
        auth_bytes = auth_string.encode('utf-8')
        auth_base64 = str(base64.b64encode(auth_bytes), 'utf-8')
        
        token_resp = requests.post(
            "https://accounts.spotify.com/api/token",
            headers={
                "Authorization": f"Basic {auth_base64}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={"grant_type": "client_credentials"},
            timeout=5
        )
        token_resp.raise_for_status()
        access_token = token_resp.json().get("access_token", "")
        
        if not access_token:
            return _play_on_youtube(song_query)
        
        # Step 2: Search for the track using the Spotify Web API
        search_resp = requests.get(
            f"https://api.spotify.com/v1/search?q={urllib.parse.quote_plus(song_query)}&type=track&limit=1",
            timeout=5,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        search_resp.raise_for_status()
        search_data = search_resp.json()
        tracks = search_data.get("tracks", {}).get("items", [])
        
        if tracks:
            track = tracks[0]
            track_uri = track["uri"]  # e.g. "spotify:track:7ytR5pFWmSjzHJIeQkgog4"
            track_name = track["name"]
            artist_name = track["artists"][0]["name"] if track["artists"] else "Unknown"
            
            # Step 3: Open the track directly — this auto-plays in Spotify!
            subprocess.Popen(f'start {track_uri}', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return f"Now playing: {track_name} by {artist_name} on Spotify."
        else:
            # Fallback to YouTube if Spotify has no tracks
            return _play_on_youtube(song_query)
            
    except Exception as e:
        print(f"[Error] Spotify search failed: {e}. Falling back to YouTube.")
        return _play_on_youtube(song_query)


# ─────────────────────────────────────────────
# SPOTIFY PLAYBACK CONTROLS (OAuth User Token)
# ─────────────────────────────────────────────

def _get_spotify_user_token() -> str:
    """
    Gets a fresh Spotify access token using the stored refresh token.
    Requires running spotify_auth.py once to set SPOTIFY_REFRESH_TOKEN in .env.
    Returns access token string, or empty string on failure.
    """
    import base64
    from dotenv import load_dotenv
    load_dotenv()
    
    refresh_token = os.getenv("SPOTIFY_REFRESH_TOKEN", "")
    if not refresh_token:
        return ""
    
    CLIENT_ID = "20caa4dbf24e4c288bbaad1e2c0d576d"
    CLIENT_SECRET = "6bf42c1ee9c647d3be1978467910576c"
    
    try:
        auth_b64 = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
        resp = requests.post(
            "https://accounts.spotify.com/api/token",
            headers={
                "Authorization": f"Basic {auth_b64}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token
            },
            timeout=5
        )
        resp.raise_for_status()
        return resp.json().get("access_token", "")
    except Exception as e:
        print(f"[Spotify] Token refresh failed: {e}")
        return ""


def get_now_playing() -> str:
    """Returns what is currently playing on Spotify."""
    token = _get_spotify_user_token()
    if not token:
        return "Spotify playback access not set up. Run 'python spotify_auth.py' to connect your account."
    
    try:
        resp = requests.get(
            "https://api.spotify.com/v1/me/player/currently-playing",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5
        )
        
        if resp.status_code == 204 or not resp.content:
            return "Nothing is currently playing on Spotify."
        
        data = resp.json()
        if not data.get("item"):
            return "Nothing is currently playing on Spotify."
        
        track = data["item"]
        track_name = track.get("name", "Unknown")
        artists = ", ".join(a["name"] for a in track.get("artists", []))
        album = track.get("album", {}).get("name", "")
        is_playing = data.get("is_playing", False)
        
        # Progress
        progress_ms = data.get("progress_ms", 0)
        duration_ms = track.get("duration_ms", 0)
        progress_str = f"{progress_ms // 60000}:{(progress_ms // 1000) % 60:02d}"
        duration_str = f"{duration_ms // 60000}:{(duration_ms // 1000) % 60:02d}"
        
        status = "Playing" if is_playing else "Paused"
        result = f"{status}: {track_name} by {artists}"
        if album:
            result += f" (from {album})"
        result += f" [{progress_str}/{duration_str}]"
        return result
    except Exception as e:
        return f"Failed to get Spotify playback: {e}"


def spotify_pause() -> str:
    """Pauses Spotify playback."""
    token = _get_spotify_user_token()
    if not token:
        return "Spotify playback access not set up."
    try:
        resp = requests.put(
            "https://api.spotify.com/v1/me/player/pause",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5
        )
        if resp.status_code in (200, 204):
            return "Spotify paused."
        return f"Could not pause Spotify (status {resp.status_code})."
    except Exception as e:
        return f"Failed to pause Spotify: {e}"


def spotify_resume() -> str:
    """Resumes Spotify playback."""
    token = _get_spotify_user_token()
    if not token:
        return "Spotify playback access not set up."
    try:
        resp = requests.put(
            "https://api.spotify.com/v1/me/player/play",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5
        )
        if resp.status_code in (200, 204):
            return "Spotify resumed."
        return f"Could not resume Spotify (status {resp.status_code})."
    except Exception as e:
        return f"Failed to resume Spotify: {e}"


def spotify_skip() -> str:
    """Skips to the next track on Spotify."""
    token = _get_spotify_user_token()
    if not token:
        return "Spotify playback access not set up."
    try:
        resp = requests.post(
            "https://api.spotify.com/v1/me/player/next",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5
        )
        if resp.status_code in (200, 204):
            return "Skipped to next track."
        return f"Could not skip track (status {resp.status_code})."
    except Exception as e:
        return f"Failed to skip track: {e}"


def spotify_previous() -> str:
    """Goes back to the previous track on Spotify."""
    token = _get_spotify_user_token()
    if not token:
        return "Spotify playback access not set up."
    try:
        resp = requests.post(
            "https://api.spotify.com/v1/me/player/previous",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5
        )
        if resp.status_code in (200, 204):
            return "Playing previous track."
        return f"Could not go back (status {resp.status_code})."
    except Exception as e:
        return f"Failed to go to previous track: {e}"


def send_whatsapp(contact_name: str, message: str) -> str:
    """
    Opens WhatsApp Web/Desktop with a pre-filled message for the given contact.
    Looks up the phone number from Alfred_Workspace/contacts.json.
    """
    contacts_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Alfred_Workspace", "contacts.json")
    try:
        with open(contacts_path, "r", encoding="utf-8") as f:
            contacts = _json.load(f)
    except FileNotFoundError:
        return "Contacts file not found. Please create Alfred_Workspace/contacts.json."
    except Exception as e:
        return f"Failed to read contacts: {e}"
    
    # Case-insensitive lookup with comma-separated alias support AND fuzzy matching
    phone = None
    matched_name = None
    for name_key, number in contacts.items():
        aliases = [a.strip().lower() for a in name_key.split(",")]
        contact_lower = contact_name.lower().strip()
        # Exact match first
        if contact_lower in aliases:
            phone = number
            matched_name = name_key
            break
        # Fuzzy match: check if the contact name starts with or contains any alias
        for alias in aliases:
            if alias.startswith(contact_lower) or contact_lower.startswith(alias):
                phone = number
                matched_name = alias
                break
        if phone:
            break
    
    if not phone or "XXXX" in phone:
        available = ", ".join(contacts.keys())
        return f"Contact '{contact_name}' not found or has a placeholder number. Available contacts: {available}"
    
    encoded_msg = urllib.parse.quote_plus(message)
    url = f"https://wa.me/{phone.replace('+', '')}?text={encoded_msg}"
    webbrowser.open(url)
    return f"WhatsApp message to {contact_name} opened and ready to send."

# ==========================================
# PHASE 13: LOCAL COMPUTER VISION (YOLOv8)
# ==========================================

def analyze_webcam_local() -> str:
    """
    Captures a frame from the webcam and runs local YOLOv8 inference.
    Returns a natural language string describing the detected objects.
    """
    import cv2
    import os
    try:
        from ultralytics import YOLO
    except ImportError:
        return "Ultralytics is not installed. Cannot run local vision."

    model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "yolov8n.pt")
    if not os.path.exists(model_path):
        return f"YOLOv8 model not found at {model_path}."

    print("[Vision Engine] Accessing latest frame from Security Engine...")
    import security_engine
    frame = security_engine.get_latest_frame()

    if frame is None:
        return "Failed to grab a frame. The security camera daemon might not be running."

    print("[Vision Engine] Running YOLOv8 inference...")
    try:
        # Load model quietly
        model = YOLO(model_path)
        results = model(frame, verbose=False)
        
        detected_counts = {}
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                class_name = model.names[cls_id]
                # Filter out very low confidence detections just in case
                if float(box.conf[0]) > 0.4:
                    detected_counts[class_name] = detected_counts.get(class_name, 0) + 1

        if not detected_counts:
            return "I don't see anything notable in front of the camera right now, sir."

        # Format into a nice sentence
        items = []
        for name, count in detected_counts.items():
            if count == 1:
                items.append(f"a {name}")
            else:
                items.append(f"{count} {name}s")
                
        # Join with commas and 'and'
        if len(items) == 1:
            desc = items[0]
        elif len(items) == 2:
            desc = f"{items[0]} and {items[1]}"
        else:
            desc = ", ".join(items[:-1]) + f", and {items[-1]}"
            
        return f"Looking through the camera, I can see {desc}."
        
    except Exception as e:
        return f"An error occurred during local vision processing: {str(e)}"

# A registry mapping tool names (as expected from LLM JSON) to their python functions
TOOL_REGISTRY = {
    # Phase 1: Reminders & Tasks
    "set_dynamic_reminder": set_dynamic_reminder,
    "add_reminder": add_reminder,
    "list_reminders": list_reminders,
    "complete_reminder": complete_reminder,
    "delete_reminder": delete_reminder,
    "clear_all_reminders": clear_all_reminders,
    
    # Phase 1b: Persistent User Facts
    "remember_fact": remember_fact,
    "forget_fact": forget_fact,
    
    # Phase 3: System File Controls
    "create_file": system_tools.create_file,
    "delete_file": system_tools.delete_file,
    "rename_file": system_tools.rename_file,
    "move_file": system_tools.move_file,
    "organize_workspace": system_tools.organize_workspace,
    
    # Phase 4: Journaling & Knowledge Base
    "journal_entry": journal_entry,
    "read_journal": read_journal,
    "query_library": scholar_engine.query_library,
    
    # Phase 5: Information tools
    "check_weather": check_weather,
    
    # Phase 6: System Control
    "launch_application": launch_application,
    "toggle_system_volume": toggle_system_volume,
    
    # Phase 7: Media & Communication
    "play_music": play_music,
    "send_whatsapp": send_whatsapp,
    
    # Phase 8: OSINT & Intelligence
    "search_web": osint_tools.search_web,
    "get_news": osint_tools.get_news,
    "get_earthquakes": osint_tools.get_earthquakes,
    "daily_briefing": osint_tools.daily_briefing,
    "reverse_email_lookup": osint_tools.reverse_email_lookup,
    "generate_district_health_score": osint_tools.generate_district_health_score,
    
    # Phase 9: Deep OS Control
    "get_battery_status": system_tools.get_battery_status,
    "set_brightness": system_tools.set_brightness,
    "get_brightness": system_tools.get_brightness,
    "toggle_wifi": system_tools.toggle_wifi,
    "toggle_bluetooth": system_tools.toggle_bluetooth,
    "lock_pc": system_tools.lock_pc,
    "sleep_pc": system_tools.sleep_pc,
    "shutdown_pc": system_tools.shutdown_pc,
    "cancel_shutdown": system_tools.cancel_shutdown,
    "set_volume": system_tools.set_volume,
    "take_screenshot": system_tools.take_screenshot,
    
    # Phase 10: Browser Tab Control
    "list_browser_tabs": browser_tools.list_browser_tabs,
    "close_browser_tab": browser_tools.close_browser_tab,
    "switch_browser_tab": browser_tools.switch_browser_tab,
    "open_browser_tab": browser_tools.open_browser_tab,
    "read_browser_tab": browser_tools.read_browser_tab,
    
    # Phase 11: Semantic Memory
    "recall_memories": None,  # Placeholder — set after llm_engine loads to avoid circular import
    
    # Phase 12: Spotify Playback Controls
    "get_now_playing": get_now_playing,
    "spotify_pause": spotify_pause,
    "spotify_resume": spotify_resume,
    "spotify_skip": spotify_skip,
    "spotify_previous": spotify_previous,
    
    # Phase 13: Local Computer Vision
    "analyze_webcam_local": analyze_webcam_local,
}

def execute_tool(tool_name: str, kwargs: dict) -> str:
    """
    Dynamically executes a tool based on the string name from the LLM.
    """
    if tool_name not in TOOL_REGISTRY:
        return f"Error: Tool '{tool_name}' not found."
    
    try:
        # Call the tool with the mapped arguments
        func = TOOL_REGISTRY[tool_name]
        return func(**kwargs)
    except Exception as e:
        return f"Error executing '{tool_name}': {e}"
