import memory_engine
from tools import system_tools
from tools import osint_tools
from tools import browser_tools
from tools import desktop_tools
from tools import swarm_engine
from tools import vision_tools
from tools import calendar_tools
from tools import developer_tools
from tools import email_tools
from tools import market_tools
import chief_of_staff
import scholar_engine
from datetime import datetime
import requests
import ctypes
import os
import threading
import time
import subprocess
import webbrowser
import urllib.parse
import re as _re
import json as _json
from tools import skill_loader

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

def clear_all_memories() -> str:
    """
    Nuclear memory wipe: clears ALL facts, semantic memories, conversation history,
    FAISS vector index, in-memory caches, and TTS audio cache.
    Use when the user says 'forget everything', 'clear all memories', 'wipe memory', etc.
    """
    try:
        # 1. Wipe all DB tables + rebuild FAISS
        memory_engine.clear_everything()
        
        # 2. Clear in-memory caches in llm_engine
        try:
            import llm_engine
            llm_engine.clear_memory_caches()
        except Exception:
            pass
        
        # 3. Clear TTS audio cache (old responses cached on disk)
        try:
            import shutil
            cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Alfred_Workspace", "audio_cache")
            if os.path.exists(cache_dir):
                shutil.rmtree(cache_dir)
                os.makedirs(cache_dir, exist_ok=True)
        except Exception:
            pass
        
        return "All memories have been completely erased, sir. Facts, conversations, semantic memories, and audio cache — all wiped clean. I am a blank slate."
    except Exception as e:
        return f"Memory wipe partially failed: {str(e)}"

def journal_entry(content: str) -> str:
    """
    Appends a new entry to the user's journal file with a timestamp.
    """
    journal_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Alfred_Workspace", "journal.txt")
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
    journal_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Alfred_Workspace", "journal.txt")
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
        text = resp.text.strip()
        for arrow in ["→", "↗", "↘", "↑", "↓", "←", "↔"]:
            text = text.replace(arrow, "->")
        return text
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
        'spotify': ['spotify:', 'spotify'],
        'spotifi': ['spotify:', 'spotify'], 
        'antigravity': [
            os.path.expandvars(r'%LOCALAPPDATA%\Programs\Antigravity IDE\Antigravity IDE.exe'),
            os.path.expandvars(r'%LOCALAPPDATA%\Programs\Antigravity\Antigravity.exe'),
            'antigravity-ide',
            'antigravity'
        ],
        'antygravity': [
            os.path.expandvars(r'%LOCALAPPDATA%\Programs\Antigravity IDE\Antigravity IDE.exe'),
            os.path.expandvars(r'%LOCALAPPDATA%\Programs\Antigravity\Antigravity.exe'),
            'antigravity-ide',
            'antigravity'
        ],
        'antigravity ide': [
            os.path.expandvars(r'%LOCALAPPDATA%\Programs\Antigravity IDE\Antigravity IDE.exe'),
            os.path.expandvars(r'%LOCALAPPDATA%\Programs\Antigravity\Antigravity.exe'),
            'antigravity-ide',
            'antigravity'
        ],
        'chatgpt': ['https://chatgpt.com'],
        'chat gpt': ['https://chatgpt.com'],
        'claude': ['https://claude.ai'],
        'claud': ['https://claude.ai'],
        'claude ai': ['https://claude.ai'],
        'code': ['code', os.path.expandvars(r'%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe'), 'vscode:'],
        'vs code': ['code', os.path.expandvars(r'%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe'), 'vscode:'],
        'vscode': ['code', os.path.expandvars(r'%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe'), 'vscode:'],
        'cursor': ['cursor', os.path.expandvars(r'%LOCALAPPDATA%\Programs\cursor\Cursor.exe')],
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
                subprocess.run(['taskkill', '/F', '/IM', proc_name], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                import time as _time; _time.sleep(2)
            for target in targets:
                try:
                    os.startfile(target, arguments=f'--remote-debugging-port={port}')
                    return f"Launch signal sent for {app_name} (with tab control enabled on port {port})."
                except Exception:
                    continue

        launched = False
        last_error = None
        for target in targets:
            try:
                if isinstance(target, str) and (target.startswith('http://') or target.startswith('https://')):
                    import webbrowser
                    webbrowser.open(target)
                    launched = True
                    break
                if os.path.isabs(target) and not os.path.exists(target):
                    continue
                os.startfile(target)
                launched = True
                break
            except Exception as e:
                last_error = e
                continue
            
        if launched:
            return f"Launch signal sent for {app_name}."
        return f"Failed to send launch signal for {app_name}. Error: {last_error}"
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

    # Intercept generic phrases like "some song", "some music", "a song"
    generic_terms = {
        'some song', 'some songs', 'a song', 'music', 'some music',
        'something', 'something good', 'good music', 'tunes', 'some tunes',
        'random song', 'random music', 'song', 'songs', 'anything'
    }
    if song_query.lower().strip().rstrip("?!., ") in generic_terms:
        return play_music_by_mood()

    def _play_on_youtube(q: str):
        q_clean = q.lower().replace("on youtube", "").replace("in youtube", "").replace("youtube", "").strip()
        query_string = urllib.parse.urlencode({"search_query": q_clean})
        try:
            import urllib.request
            req = urllib.request.Request("https://www.youtube.com/results?" + query_string, headers={'User-Agent': 'Mozilla/5.0'})
            html_content = urllib.request.urlopen(req)
            html_str = html_content.read().decode('utf-8', errors='ignore')
            # Look for videoId in the JSON payload rather than watch?v= which catches random recommendations
            search_results = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html_str)
            
            if search_results:
                # Filter out channel IDs and duplicates to ensure we get the first actual search result
                unique_results = list(dict.fromkeys(search_results))
                video_url = "https://www.youtube.com/watch?v=" + unique_results[0]
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
    from dotenv import load_dotenv
    load_dotenv()
    CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
    CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    
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
            os.startfile(track_uri)
            return f"Now playing: {track_name} by {artist_name} on Spotify."
        else:
            # Fallback to YouTube if Spotify has no tracks
            return _play_on_youtube(song_query)
            
    except Exception as e:
        print(f"[Error] Spotify search failed: {e}. Falling back to YouTube.")
        return _play_on_youtube(song_query)

def play_music_by_mood() -> str:
    """
    Retrieves the user's current facial emotion from shared state and plays matching music.
    """
    import shared
    mood = shared.dominant_emotion.lower()
    
    mood_to_query = {
        'happy': 'happy upbeat playlist',
        'sad': 'sad melancholic songs',
        'angry': 'heavy metal angry music',
        'fear': 'calm relaxing ambient music',
        'surprise': 'exciting pop music',
        'disgust': 'chill lofi hip hop',
        'neutral': 'lofi beats'
    }
    
    query = mood_to_query.get(mood, 'lofi beats')
    return play_music(query)


def play_user_daily_rotation() -> str:
    """
    Fetches the user's actual Spotify listening history and frequent daily tracks,
    and starts playback directly.
    """
    token = _get_spotify_user_token()
    if not token:
        return play_music_by_mood()
    
    try:
        resp = requests.get(
            "https://api.spotify.com/v1/me/player/recently-played?limit=50",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            if items:
                from collections import Counter
                import random
                
                track_info = {}
                track_uris = []
                for item in items:
                    t = item.get("track")
                    if t and t.get("uri"):
                        uri = t["uri"]
                        track_info[uri] = {
                            "name": t.get("name", "Unknown Track"),
                            "artist": t.get("artists", [{}])[0].get("name", "Unknown Artist")
                        }
                        track_uris.append(uri)
                
                if track_uris:
                    counts = Counter(track_uris)
                    most_common = [uri for uri, _ in counts.most_common(10)]
                    selected_uri = random.choice(most_common[:5]) if most_common else track_uris[0]
                    selected_track = track_info[selected_uri]
                    
                    # Launch playback in Spotify
                    try:
                        play_resp = requests.put(
                            "https://api.spotify.com/v1/me/player/play",
                            headers={"Authorization": f"Bearer {token}"},
                            json={"uris": [selected_uri]},
                            timeout=5
                        )
                        if play_resp.status_code not in (200, 204):
                            os.startfile(selected_uri)
                    except Exception:
                        os.startfile(selected_uri)

                    # Learn user music taste into memory
                    try:
                        import memory_engine
                        top_artists = [item['track']['artists'][0]['name'] for item in items if item.get('track')]
                        common_artists = [art for art, cnt in Counter(top_artists).most_common(3)]
                        if common_artists:
                            memory_engine.store_user_fact(f"User frequently listens to: {', '.join(common_artists)} on Spotify.")
                    except Exception:
                        pass

                    return f"Now playing from your daily rotation: {selected_track['name']} by {selected_track['artist']} on Spotify."
    except Exception as e:
        print(f"[Spotify] Failed to get user rotation: {e}")
        
    return play_music_by_mood()


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
    
    CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
    CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    
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
            timeout=15
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
            timeout=15
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

# ==========================================
# PHASE 14: DYNAMIC SKILL ENGINE (Self-Upgrading Brain)
# ==========================================

def learn_new_skill(skill_description: str) -> str:
    """
    Uses Gemini to write a self-contained Python function for the requested skill,
    saves it to the Dockerized sandbox_skills directory, and integrates it.
    """
    import os
    import re
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "I need a GEMINI_API_KEY in my .env file to write code for myself, sir."
        
    print(f"[Skill Engine] Writing code for: '{skill_description}'...")
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
        You are Alfred, a highly advanced local AI assistant. The user wants you to learn a new skill: "{skill_description}".
        Write a single, safe, self-contained Python function to accomplish this.
        
        RULES:
        1. Function must take NO arguments or only arguments that can be easily parsed from natural language.
        2. Must return a clear, natural language string describing the result to the user.
        3. Do NOT use dangerous imports (like os.system or shutil to delete system files).
        4. Name the function clearly with snake_case.
        5. Provide ONLY the raw Python code. NO markdown formatting, NO backticks, NO explanations.
        """
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        code = response.text.strip()
        if code.startswith("```python"):
            code = code.replace("```python\n", "").replace("```", "")
        if code.startswith("```"):
            code = code.replace("```\n", "").replace("```", "")
            
        code = code.strip()
        
        # Validate AST and imports to prevent dangerous code execution
        import ast
        try:
            tree = ast.parse(code)
            blocklisted = {'os', 'subprocess', 'shutil', 'pty', 'socket', 'ctypes', 'sys', 'builtins', 'importlib'}
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        name = alias.name.split('.')[0]
                        if name in blocklisted:
                            return f"Security check failed: import of module '{name}' is not allowed in dynamic skills."
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        name = node.module.split('.')[0]
                        if name in blocklisted:
                            return f"Security check failed: import from module '{name}' is not allowed in dynamic skills."
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in {'eval', 'exec', '__import__', 'compile', 'getattr', 'setattr', 'delattr', 'globals', 'locals', 'vars'}:
                        return f"Security check failed: use of built-in function '{node.func.id}' is not allowed in dynamic skills."
                elif isinstance(node, ast.Attribute) and node.attr.startswith('__'):
                    return f"Security check failed: dunder attribute access '{node.attr}' is not allowed in dynamic skills."
                elif isinstance(node, ast.Name) and node.id in {'__builtins__', '__loader__', '__spec__'}:
                    return f"Security check failed: access to '{node.id}' is not allowed in dynamic skills."
        except SyntaxError as se:
            return f"Syntax validation failed for generated code: {se}"
        
        # Parse the function name
        match = re.search(r"def\s+([a-zA-Z_]\w*)\s*\(", code)
        if not match:
            return "Failed to identify function name in generated code."
        func_name = match.group(1)
        
        sandbox_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Alfred_Workspace", "sandbox_skills")
        os.makedirs(sandbox_dir, exist_ok=True)
        script_path = os.path.join(sandbox_dir, f"{func_name}.py")
        
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)
            f.write(f"\n\nif __name__ == '__main__':\n")
            f.write(f"    import json, sys\n")
            f.write(f"    kwargs = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {{}}\n")
            f.write(f"    result = {func_name}(**kwargs)\n")
            f.write(f"    print(result)\n")
            
        print("[Skill Engine] Code written and saved to sandbox_skills.")
        
        TOOL_REGISTRY[func_name] = make_docker_wrapper(func_name)
        return f"I have successfully learned a new isolated skill: {func_name}. You may now ask me to perform it."
            
    except Exception as e:
        return f"I encountered an error while trying to write my new skill: {e}"

def make_docker_wrapper(skill_name: str):
    def wrapper(**kwargs):
        import subprocess, json, os
        sandbox_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Alfred_Workspace", "sandbox_skills")
        cmd = [
            "docker", "run", "--rm",
            "--network", os.getenv("ALFRED_SKILL_NETWORK", "bridge"),  # set to "none" to fully air-gap skills
            "--read-only", "--tmpfs", "/tmp",  # immutable container filesystem
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--memory", "256m", "--cpus", "1", "--pids-limit", "64",
            "-v", f"{sandbox_dir}:/skills:ro",
            "alfred-sandbox",
            "python", f"/skills/{skill_name}.py", json.dumps(kwargs)
        ]
        try:
            # Check if docker is installed
            res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
            return res.stdout.strip()
        except subprocess.TimeoutExpired:
            return "Error: Skill timed out after 60 seconds inside the sandbox."
        except FileNotFoundError:
            # Docker not installed
            return "Error: Docker is not installed or not running. I cannot safely execute this skill without my sandbox."
        except subprocess.CalledProcessError as e:
            # Execution failed inside Docker
            return f"Error executing skill inside sandbox: {e.stderr if e.stderr else e.stdout}"
        except Exception as e:
            return f"Error executing docker skill: {e}"
    return wrapper

# A registry mapping tool names (as expected from LLM JSON) to their python functions
TOOL_REGISTRY = {
    # Phase 1: Reminders & Tasks
    "set_dynamic_reminder": set_dynamic_reminder,
    "add_reminder": add_reminder,
    "list_reminders": list_reminders,
    "complete_reminder": complete_reminder,
    "delete_reminder": delete_reminder,
    "clear_all_reminders": clear_all_reminders,
    
    # Phase 1c: Calendar & Schedule (Google & Samsung Calendar)
    "get_calendar_events": calendar_tools.get_calendar_events,
    "create_calendar_event": calendar_tools.create_calendar_event,
    "delete_calendar_event": calendar_tools.delete_calendar_event,
    
    # Phase 1b: Persistent User Facts
    "remember_fact": remember_fact,
    "forget_fact": forget_fact,
    "clear_all_memories": clear_all_memories,
    
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
    "play_music_by_mood": play_music_by_mood,
    "play_user_daily_rotation": play_user_daily_rotation,
    "send_whatsapp": send_whatsapp,
    
    # Phase 8: OSINT & Intelligence
    "search_web": osint_tools.search_web,
    "get_news": osint_tools.get_news,
    "get_earthquakes": osint_tools.get_earthquakes,
    "daily_briefing": osint_tools.daily_briefing,
    "reverse_email_lookup": osint_tools.reverse_email_lookup,
    "generate_district_health_score": osint_tools.generate_district_health_score,
    "stealth_fetch_url": osint_tools.stealth_fetch_url,
    "deep_research_swarm": swarm_engine.deep_research_swarm,
    
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
    
    # Phase 14: Dynamic Skill Engine
    "learn_new_skill": learn_new_skill,
    
    # Phase 15: Autonomous Desktop Control & Vision
    "get_screen_info": desktop_tools.get_screen_info,
    "mouse_move_and_click": desktop_tools.mouse_move_and_click,
    "keyboard_type": desktop_tools.keyboard_type,
    "keyboard_press": desktop_tools.keyboard_press,
    "keyboard_hotkey": desktop_tools.keyboard_hotkey,
    "analyze_screen": desktop_tools.analyze_screen,
    "read_screen_text": desktop_tools.read_screen_text,

    # Phase 16: Open-Vocabulary Visual Grounding (YOLO-World)
    "locate_object_in_camera": vision_tools.locate_object_in_camera,
    "locate_object_on_screen": vision_tools.locate_object_on_screen,

    # Phase 17: OSINT Geo-Intelligence
    "get_geo_news": osint_tools.get_geo_news,
    
    # Phase 18: Instagram Integration
    "fetch_instagram_posts": osint_tools.fetch_instagram_posts,

    # Phase 19: Workflow Macros & Routines Engine
    "run_routine": lambda routine_name: __import__("routine_engine").execute_routine(routine_name),
    "create_routine": lambda prompt: str(__import__("routine_engine").create_routine_from_prompt(prompt)),

    # Phase 20: Second Brain / Knowledge Graph
    "query_knowledge_graph": lambda entity_name: str(__import__("knowledge_graph").query_subgraph(entity_name)),
    "extract_knowledge_from_text": lambda text: str(__import__("knowledge_graph").extract_and_link_from_text(text)),

    # Phase 21: Developer Co-Pilot & Autonomous Workspace Agent
    "git_status_diff": developer_tools.git_status_diff,
    "git_smart_commit": developer_tools.git_smart_commit,
    "scan_leaked_secrets": developer_tools.scan_leaked_secrets,
    "clean_dev_workspace": developer_tools.clean_dev_workspace,
    "run_terminal_command": developer_tools.run_terminal_command,
    "meeting_notetaker": developer_tools.meeting_notetaker,

    # Phase 22: Calendar, Email & Daily Chief of Staff
    "detect_schedule_conflicts": calendar_tools.detect_schedule_conflicts,
    "find_focus_slots": calendar_tools.find_focus_slots,
    "get_unread_emails": email_tools.get_unread_emails,
    "triage_inbox": email_tools.triage_inbox,
    "draft_email_reply": email_tools.draft_email_reply,
    "get_daily_executive_dossier": chief_of_staff.get_daily_executive_dossier,
    "get_quick_agenda": chief_of_staff.get_quick_agenda,

    # Phase 23: Market Intelligence & Financial Predictions (Amazon Chronos)
    "get_stock_quote": market_tools.get_stock_quote,
    "forecast_stock": market_tools.forecast_stock,

    # Phase 24: Reverse Face Search & OSINT Facial Intelligence
    "reverse_face_search": osint_tools.reverse_face_search,
}


# --- Dynamic Import of Custom Skills on Startup ---
try:
    import os
    sandbox_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Alfred_Workspace", "sandbox_skills")
    if os.path.exists(sandbox_dir):
        for file in os.listdir(sandbox_dir):
            if file.endswith(".py") and not file.startswith("__"):
                func_name = file[:-3]
                TOOL_REGISTRY[func_name] = make_docker_wrapper(func_name)
except Exception as e:
    print(f"[Warning] Failed to load sandbox skills on startup: {e}")

# --- Register Community Skills (agentskills.io) ---
def install_community_skill(source_path: str) -> str:
    """
    Installs a community skill from a local path.
    The path must contain a manifest.json and main.py.
    """
    return skill_loader.install_skill(source_path)

TOOL_REGISTRY["install_community_skill"] = install_community_skill

try:
    skill_loader.register_skills_to_registry(TOOL_REGISTRY)
except Exception as e:
    print(f"[Warning] Failed to register community skills: {e}")

# --- Human-in-the-loop gate for destructive / outward-facing tools ---
# The LLM can be steered by prompt injection (web pages, emails, OSINT results),
# so these never run without the user explicitly confirming.
CONFIRMATION_REQUIRED_TOOLS = {
    "run_terminal_command", "delete_file", "git_smart_commit", "clean_dev_workspace",
    "shutdown_pc", "learn_new_skill", "install_community_skill", "clear_all_memories",
    "delete_calendar_event", "send_whatsapp",
}
CONFIRM_WORDS = {"confirm", "yes confirm", "confirm it", "proceed", "yes proceed", "do it", "approved"}
CANCEL_WORDS = {"cancel", "no", "abort", "don't", "do not", "stop"}
_PENDING_TTL_SECONDS = 120
_pending_action = None  # (tool_name, kwargs, created_at)
_pending_lock = threading.RLock()  # re-entrant: _announce_pending reads state while held


def _describe_call(tool_name: str, kwargs: dict) -> str:
    args = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
    return f"{tool_name}({args})"


def has_pending_action() -> bool:
    with _pending_lock:
        return _pending_action is not None and time.time() - _pending_action[2] < _PENDING_TTL_SECONDS


def pending_action_info():
    """Pending gated call as a dict for the HUD notch, or None."""
    with _pending_lock:
        if _pending_action is None or time.time() - _pending_action[2] >= _PENDING_TTL_SECONDS:
            return None
        tool_name, kwargs, created = _pending_action
        return {
            "tool": tool_name,
            "summary": _describe_call(tool_name, kwargs),
            "expires_in": int(_PENDING_TTL_SECONDS - (time.time() - created)),
        }


def _announce_pending():
    try:
        import shared
        shared.event_queue.put({"type": "approval", "value": pending_action_info()})
    except Exception:
        pass


def handle_confirmation_reply(text: str):
    """If a gated action is pending and `text` confirms/cancels it, act and return a reply; else None."""
    global _pending_action
    reply = text.lower().strip().rstrip(".!")
    with _pending_lock:
        pending = _pending_action
        if pending is None or time.time() - pending[2] >= _PENDING_TTL_SECONDS:
            _pending_action = None
            return None
        if reply in CONFIRM_WORDS:
            _pending_action = None
        elif reply in CANCEL_WORDS:
            _pending_action = None
            _announce_pending()
            return f"Cancelled: {_describe_call(pending[0], pending[1])}."
        else:
            return None
    _announce_pending()
    return _run_tool(pending[0], pending[1])


def _run_tool(tool_name: str, kwargs: dict) -> str:
    try:
        return TOOL_REGISTRY[tool_name](**kwargs)
    except Exception as e:
        return f"Error executing '{tool_name}': {e}"


def execute_tool(tool_name: str, kwargs: dict) -> str:
    """
    Dynamically executes a tool based on the string name from the LLM.
    Tools in CONFIRMATION_REQUIRED_TOOLS are parked until the user says "confirm".
    """
    global _pending_action
    if tool_name not in TOOL_REGISTRY:
        return f"Error: Tool '{tool_name}' not found."

    if tool_name in CONFIRMATION_REQUIRED_TOOLS:
        with _pending_lock:
            _pending_action = (tool_name, dict(kwargs), time.time())
        _announce_pending()
        return (f"CONFIRMATION REQUIRED: I need your approval to run {_describe_call(tool_name, kwargs)}. "
                f"Say 'confirm' to proceed or 'cancel' to abort.")

    try:
        # Call the tool with the mapped arguments
        func = TOOL_REGISTRY[tool_name]
        return func(**kwargs)
    except Exception as e:
        return f"Error executing '{tool_name}': {e}"


def get_all_tool_names() -> list:
    """Returns a sorted list of all registered tool names. Used by the task orchestrator."""
    return sorted(TOOL_REGISTRY.keys())

