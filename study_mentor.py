"""
Protocol Omega - Study Mentor Daemon
=====================================
When activated, Alfred becomes a strict study enforcer:
1. Vision Watcher: Uses webcam + Gemini to detect phone usage
2. OS Watcher: Monitors active windows and kills distracting apps (with warning)
3. Screen Watcher: Takes screenshots and asks Gemini if content is educational or not
"""

import threading
import time
import random
import os
import shared
import voice_engine
from llm_engine import USER_NAME

# Import push notification module (optional — graceful if not available)
try:
    import telegram_notifier
    _telegram_available = telegram_notifier.is_available()
except ImportError:
    _telegram_available = False

# -- CONFIGURATION --

BLACKLIST = [
    'netflix', 'prime video', 'hotstar', 'disney+',
    'instagram', 'tiktok', 'snapchat',
    'reddit', 'twitter', 'x.com', 'x - ',
    'facebook',
    'steam', 'epic games', 'riot client', 'valorant', 'cs', 'minecraft',
    'shorts', 'reels',
    'crunchyroll', 'funimation',
]

WHITELIST = [
    'youtube', 'discord',
    'vs code', 'visual studio', 'code -',
    'notion', 'obsidian', 'google docs', 'google sheets',
    'chatgpt', 'gemini', 'claude', 'ollama', 'lm studio',
    'stack overflow', 'stackoverflow', 'github', 'github desktop', 'git',
    'alfred protocol', 'antigravity',
    'word', 'excel', 'powerpoint', 'onenote',
    'pdf', 'acrobat', 'adobe scan',
    'zoom', 'meet', 'teams',
    'terminal', 'powershell', 'cmd', 'putty', 'mobaxterm',
    'file explorer', 'explorer',
    'buggyverse', 'buggyverse.com',
    'jupyter', 'pycharm', 'intellij', 'eclipse', 'android studio',
    'postman', 'wireshark', 'virtualbox', 'vmware', 'docker',
    'xampp', 'wamp', 'mysql', 'pgadmin', 'mongodb', 'redis',
    'matlab', 'autocad', 'canva', 'figma', 'unity', 'unreal',
    'zotero', 'mendeley'
]

WARNING_TIMEOUT = 15
VISION_CHECK_INTERVAL = 15  # Check every 15 seconds for phone/distraction
SCREEN_CHECK_INTERVAL = 120
OS_CHECK_INTERVAL = 8

# -- SCOLDING LINES --

PHONE_SCOLDS = [
    f"Master {USER_NAME}, I can see that phone in your hand. Whatever it is, it can wait. Focus on the task ahead.",
    f"Sir, I distinctly spotted you reaching for your phone. That is not part of our study agenda.",
    f"Put the phone down, Master {USER_NAME}. You activated this protocol for a reason.",
    f"I see you, sir. The phone goes down, or the productivity goes down. Your choice.",
    f"Master {USER_NAME}, that device in your hand is the enemy of progress right now. Set it aside.",
    f"Sir, the phone. I can see it. You know what you need to do.",
    f"Need I remind you, Master {USER_NAME}? Every minute on that phone is a minute stolen from your goals.",
    f"I am watching, sir. Put the phone away and get back to it.",
]

SCREEN_SCOLDS = [
    f"Master {USER_NAME}, that does not look like study material to me. I strongly suggest you get back on track.",
    f"Sir, I took a look at your screen. That content is not going to help you pass any exams.",
    f"I see entertainment on your screen, Master {USER_NAME}. Shall I remind you why you activated this protocol?",
    f"That is not productive content, sir. You are better than this. Refocus.",
    f"Master {USER_NAME}, your screen tells me you have drifted. Come back to your work.",
    f"Sir, I believe you opened that for study purposes, but what I see tells a different story. Back to work.",
]

APP_WARNING_LINES = [
    "Sir, you have opened {app}. I am giving you {sec} seconds to close it yourself.",
    "Master {USER_NAME}, I have detected {app} on your screen. You have {sec} seconds before I intervene.",
    "That does not look study-related, sir. {app} will be closed in {sec} seconds unless you do it first.",
    "{app} is open, sir. You have {sec} seconds. I suggest you use them wisely.",
    "I see {app} on your taskbar, Master {USER_NAME}. Close it in {sec} seconds or I will handle it.",
]

APP_KILLED_LINES = [
    "Time is up. I have closed {app} for you, sir. Back to work.",
    "{app} has been shut down, Master {USER_NAME}. No more distractions.",
    "I warned you, sir. {app} is now closed. Let us refocus.",
    "{app} is gone. Now, where were we? Back to studying, sir.",
    "Consider {app} dealt with, Master {USER_NAME}. Your textbook awaits.",
]

MOTIVATION_LINES = [
    f"You are doing well, Master {USER_NAME}. Stay focused and the results will follow.",
    f"Keep it up, sir. Discipline is the bridge between goals and accomplishment.",
    f"I am impressed by your dedication, Master {USER_NAME}. Carry on.",
    f"Excellent focus, sir. This is the version of yourself that achieves great things.",
    f"Steady progress, Master {USER_NAME}. Remember, consistency beats intensity.",
    f"You have been focused for a while now, sir. That takes real discipline. Well done.",
    f"Your future self will thank you for this effort, Master {USER_NAME}. Keep going.",
    f"Sir, just a reminder. You are building something great right now. Stay the course.",
    f"The hardest part is sitting down and starting. You have already done that, sir. Keep pushing.",
    f"Master {USER_NAME}, focus is a muscle. And yours is getting stronger today.",
]

# -- GLOBALS --
_running = False
_warned_windows = {}
_session_start_time = 0
_distraction_count = 0

_omega_lock = __import__('threading').Lock()
_vision_thread = None
_os_thread = None
_screen_thread = None
_mot_thread = None
_pomodoro_thread = None



def _safe_speak(message):
    if shared.current_state in ("idle", "listening"):
        shared.push_state("speaking")
        shared.push_log(message, "Alfred")
        shared.push_caption(message)
        voice_engine.speak(message)
        shared.push_caption("")
        shared.push_state("idle")
        return True
    return False


def _is_blacklisted(title):
    lower = title.lower()
    # Check strict BLACKLIST first
    for blocked in BLACKLIST:
        if blocked in lower:
            return True
            
    # Check WHITELIST next
    is_whitelisted = False
    for allowed in WHITELIST:
        if allowed in lower:
            is_whitelisted = True
            break
            
    if is_whitelisted:
        return False
        
    # If unknown, intelligently classify it
    import study_intelligence
    classification = study_intelligence.classify_app_title(title)
    if classification == "DISTRACTING":
        return True
        
    return False


def _get_blacklist_match(title):
    lower = title.lower()
    for blocked in BLACKLIST:
        if blocked in lower:
            return blocked.title()
    # If we classified it dynamically
    import study_intelligence
    if study_intelligence.classify_app_title(title) == "DISTRACTING":
        return title[:30]
    return title[:30]


def _init_gemini():
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception as e:
        print(f"[Protocol Omega] Gemini init failed: {e}")
        return None



# ============================
#  POMODORO TIMER ENGINE
# ============================

def _pomodoro_loop():
    print("[Protocol Omega] Pomodoro Timer active.")
    FOCUS_TIME = 25 * 60
    SHORT_BREAK = 5 * 60
    LONG_BREAK = 15 * 60
    
    # Health reminder counters (in seconds)
    EYE_BREAK_INTERVAL = 20 * 60    # 20-20-20 rule: every 20 minutes
    HYDRATION_INTERVAL = 45 * 60    # Drink water every 45 minutes
    eye_break_timer = 0
    hydration_timer = 0
    
    with _omega_lock:
        shared.omega_phase = "focus"
        shared.omega_phase_remaining = FOCUS_TIME
        shared.push_omega_state()
        
    while True:
        speak_msg = None
        with _omega_lock:
            if not _running:
                break
                
            shared.omega_phase_remaining -= 1
            
            if shared.omega_phase_remaining <= 0:
                if shared.omega_phase == "focus":
                    shared.omega_pomodoro_cycle += 1
                    if shared.omega_pomodoro_cycle % 4 == 0:
                        shared.omega_phase = "long_break"
                        shared.omega_phase_remaining = LONG_BREAK
                        speak_msg = f"Excellent work, sir. You have completed 4 focus cycles. I recommend a {LONG_BREAK//60}-minute long break to hydrate and stretch."
                    else:
                        shared.omega_phase = "short_break"
                        shared.omega_phase_remaining = SHORT_BREAK
                        speak_msg = f"Cycle {shared.omega_pomodoro_cycle} complete. Take a {SHORT_BREAK//60}-minute short break, sir."
                else:
                    shared.omega_phase = "focus"
                    shared.omega_phase_remaining = FOCUS_TIME
                    speak_msg = f"Break time is over, Master {USER_NAME}. Back to your studies."
            
            # Health reminders (only during focus phase to not interrupt breaks)
            if shared.omega_phase == "focus" and speak_msg is None:
                eye_break_timer += 1
                hydration_timer += 1
                
                if eye_break_timer >= EYE_BREAK_INTERVAL:
                    speak_msg = f"Quick eye break, Master {USER_NAME}. Look at something 20 feet away for 20 seconds. Your eyes need it."
                    eye_break_timer = 0
                elif hydration_timer >= HYDRATION_INTERVAL:
                    speak_msg = f"Hydration check, sir. Take a sip of water. A hydrated brain is a focused brain."
                    hydration_timer = 0
            
            # Broadcast state every second
            shared.push_omega_state()
        
        # Speak OUTSIDE the lock to avoid deadlock
        if speak_msg:
            _safe_speak(speak_msg)
            
        time.sleep(1)
        
    print("[Protocol Omega] Pomodoro Timer stopped.")


# ============================
#  OS WATCHER
# ============================

def _os_watcher_loop():
    global _warned_windows
    try:
        import pygetwindow as gw
    except ImportError:
        print("[Protocol Omega] pygetwindow not installed. OS watcher disabled.")
        return

    print("[Protocol Omega] OS Watcher active.")

    while _running:
        try:
            active_win = gw.getActiveWindow()
            if not active_win or not active_win.title:
                time.sleep(OS_CHECK_INTERVAL)
                continue

            title = active_win.title

            if _is_blacklisted(title):
                match_name = _get_blacklist_match(title)

                if title in _warned_windows:
                    elapsed = time.time() - _warned_windows[title]
                    if elapsed >= WARNING_TIMEOUT:
                        print(f"[Protocol Omega] Closing: {title}")
                        try:
                            active_win.close()
                        except Exception as e:
                            print(f"[Protocol Omega] Failed to close window: {e}")
                        kill_msg = random.choice(APP_KILLED_LINES).format(app=match_name, USER_NAME=USER_NAME)
                        _safe_speak(kill_msg)
                        del _warned_windows[title]
                        with _omega_lock:
                            shared.omega_distractions += 1
                            if shared.omega_session_id:
                                import memory_engine
                                memory_engine.log_study_distraction(shared.omega_session_id, 'app', match_name)
                else:
                    _warned_windows[title] = time.time()
                    warn_msg = random.choice(APP_WARNING_LINES).format(app=match_name, sec=WARNING_TIMEOUT, USER_NAME=USER_NAME)
                    print(f"[Protocol Omega] WARNING: {title}")
                    _safe_speak(warn_msg)
            else:
                current_titles = set()
                try:
                    for w in gw.getAllWindows():
                        if w.title:
                            current_titles.add(w.title)
                except Exception:
                    pass
                for warned_title in list(_warned_windows.keys()):
                    if warned_title not in current_titles:
                        del _warned_windows[warned_title]

        except Exception as e:
            print(f"[Protocol Omega] OS watcher error: {e}")

        time.sleep(OS_CHECK_INTERVAL)

    print("[Protocol Omega] OS Watcher stopped.")


# ============================
#  VISION WATCHER (Webcam)
# ============================

def _vision_watcher_loop():
    try:
        from ultralytics import YOLO
    except ImportError:
        print("[Protocol Omega] ultralytics not installed. Vision watcher disabled.")
        return

    try:
        print("[Protocol Omega] Loading YOLOv8 object detection model...")
        model = YOLO("yolov8n.pt")
    except Exception as e:
        print(f"[Protocol Omega] YOLO model load failed: {e}")
        return

    import security_engine
    import study_intelligence
    import cv2
    
    print("[Protocol Omega] Vision Watcher active (local YOLOv8 engaged).")

    last_scold_time = 0
    SCOLD_COOLDOWN = 60
    
    # Absence Tracking
    last_person_seen_time = time.time()
    person_missing_alerted = False

    # Drowsiness Tracking
    face_mesh = study_intelligence.init_drowsiness_detector()
    DROWSY_EAR_THRESHOLD = 0.22
    drowsy_start_time = None
    DROWSY_MAX_TIME = 10.0 # 10 seconds of eyes closed or drooping
    
    # Distracting items
    DISTRACTING_CLASSES = ['cell phone', 'remote', 'tv']
    DETECTION_CONFIDENCE = 0.35  # Minimum confidence to trigger a detection

    while _running:
        try:
            frame = security_engine.get_latest_frame()
            if frame is None:
                time.sleep(VISION_CHECK_INTERVAL)
                continue

            # Run inference locally using YOLO
            results = model(frame, verbose=False)
            detected_distraction = False
            detected_distraction_name = ""
            person_detected = False

            for r in results:
                for box in r.boxes:
                    class_name = model.names[int(box.cls)]
                    conf = float(box.conf)
                    if class_name == 'person':
                        person_detected = True
                    if class_name in DISTRACTING_CLASSES and conf >= DETECTION_CONFIDENCE:
                        detected_distraction = True
                        detected_distraction_name = class_name
                        print(f"[Protocol Omega] Vision check detected: {class_name} (conf: {conf:.2f})")

            # 1. Absence Detection
            if person_detected:
                last_person_seen_time = time.time()
                person_missing_alerted = False
            else:
                if time.time() - last_person_seen_time > 120 and not person_missing_alerted:
                    # Absent for 2 minutes
                    scold = study_intelligence.generate_dynamic_scold("Master has left their desk and is absent from the study session.")
                    print("[Protocol Omega] ABSENCE DETECTED!")
                    _safe_speak(scold)
                    person_missing_alerted = True
                    if _telegram_available:
                        try:
                            telegram_notifier.send_alert(f"⚠️ PROTOCOL OMEGA: Absence detected! {scold}")
                        except Exception:
                            pass
                    # Skip drowsiness/distraction checks if person is absent
                    time.sleep(VISION_CHECK_INTERVAL)
                    continue

            # 2. Drowsiness Detection
            if face_mesh and person_detected:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                fm_results = face_mesh.process(rgb_frame)
                if fm_results.multi_face_landmarks:
                    ear = study_intelligence.calculate_ear(fm_results.multi_face_landmarks[0], frame.shape[1], frame.shape[0])
                    if ear < DROWSY_EAR_THRESHOLD:
                        if drowsy_start_time is None:
                            drowsy_start_time = time.time()
                        elif time.time() - drowsy_start_time > DROWSY_MAX_TIME:
                            scold = study_intelligence.generate_dynamic_scold("Master appears to be falling asleep at their desk. Tell them to wake up immediately.")
                            print("[Protocol Omega] DROWSINESS DETECTED!")
                            _safe_speak(scold)
                            drowsy_start_time = None # Reset
                            if _telegram_available:
                                try:
                                    telegram_notifier.send_alert(f"😴 PROTOCOL OMEGA: Sleep detected! {scold}")
                                except Exception:
                                    pass
                    else:
                        drowsy_start_time = None
                else:
                    drowsy_start_time = None

            # 3. Distraction Detection
            if detected_distraction:
                now = time.time()
                if now - last_scold_time > SCOLD_COOLDOWN:
                    with _omega_lock:
                        shared.omega_distractions += 1
                        if shared.omega_session_id:
                            import memory_engine
                            memory_engine.log_study_distraction(shared.omega_session_id, 'phone', detected_distraction_name)
                    scold = study_intelligence.generate_dynamic_scold(f"holding or looking at a {detected_distraction_name}")
                    print("[Protocol Omega] PHONE/DEVICE DETECTED!")
                    _safe_speak(scold)
                    last_scold_time = now
                    if _telegram_available:
                        try:
                            telegram_notifier.send_alert(f"📱 PROTOCOL OMEGA: Device detected! {scold}")
                        except Exception:
                            pass

        except Exception as e:
            print(f"[Protocol Omega] Vision error: {e}")

        time.sleep(VISION_CHECK_INTERVAL)

    print("[Protocol Omega] Vision Watcher stopped.")


# ============================
#  SCREEN WATCHER (Screenshot)
# ============================

def _screen_watcher_loop():
    try:
        from PIL import ImageGrab
    except ImportError:
        print("[Protocol Omega] Pillow not installed. Screen watcher disabled.")
        return

    client = _init_gemini()
    if not client:
        print("[Protocol Omega] No Gemini API. Screen watcher disabled.")
        return

    print("[Protocol Omega] Screen Content Watcher active.")

    last_scold_time = 0
    SCOLD_COOLDOWN = 90

    while _running:
        try:
            screenshot = ImageGrab.grab()
            screenshot = screenshot.resize((1280, 720))

            import io
            buf = io.BytesIO()
            screenshot.save(buf, format='JPEG', quality=50)
            image_bytes = buf.getvalue()

            prompt = (
                "You are a study focus monitor. Look at this screenshot of a computer screen. "
                "Determine if the user is doing something PRODUCTIVE (coding, reading docs, studying, "
                "writing notes, research, educational video, tutorial) or something DISTRACTING "
                "(watching entertainment, social media scrolling, gaming, memes, non-educational videos, "
                "movie or TV shows, music videos, funny clips, vlogs). "
                "Answer with ONLY one word: PRODUCTIVE or DISTRACTING."
            )

            from google.genai import types
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    prompt,
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
                ]
            )

            answer = response.text.strip().upper()
            print(f"[Protocol Omega] Screen check: {answer}")

            if "DISTRACTING" in answer:
                now = time.time()
                if now - last_scold_time > SCOLD_COOLDOWN:
                    with _omega_lock:
                        shared.omega_distractions += 1
                        if shared.omega_session_id:
                            import memory_engine
                            memory_engine.log_study_distraction(shared.omega_session_id, 'phone', detected_distraction_name)
                    import study_intelligence
                    scold = study_intelligence.generate_dynamic_scold("Master is looking at non-educational, distracting content on their computer screen.")
                    print("[Protocol Omega] DISTRACTION ON SCREEN DETECTED!")
                    _safe_speak(scold)
                    last_scold_time = now
                    # Push to phone too
                    if _telegram_available:
                        try:
                            telegram_notifier.send_alert(f"🖥️ PROTOCOL OMEGA: Distraction detected on screen! {scold}")
                        except Exception:
                            pass

        except Exception as e:
            print(f"[Protocol Omega] Screen watcher error: {e}")

        time.sleep(SCREEN_CHECK_INTERVAL)

    print("[Protocol Omega] Screen Content Watcher stopped.")


# ============================
#  MOTIVATION ENGINE
# ============================

def _motivation_loop():
    print("[Protocol Omega] Motivation engine active.")
    while _running:
        wait_time = random.randint(1200, 1800)
        elapsed = 0
        while elapsed < wait_time and _running:
            time.sleep(10)
            elapsed += 10
        if _running:
            msg = random.choice(MOTIVATION_LINES)
            _safe_speak(msg)
    print("[Protocol Omega] Motivation engine stopped.")


# ============================
#  PUBLIC API
# ============================


def activate():
    global _running, _vision_thread, _os_thread, _screen_thread, _mot_thread, _pomodoro_thread, _warned_windows

    with _omega_lock:
        if _running:
            return "Protocol Omega is already active, sir."

        _running = True
        _warned_windows = {}
        shared.focus_mode_active = True
        
        # Initialize Shared State
        shared.omega_active = True
        shared.omega_pomodoro_cycle = 0
        shared.omega_distractions = 0
        shared.omega_session_start = int(time.time())
        
        # Create Persistent DB Session
        import memory_engine
        memory_engine.close_orphaned_sessions() # Cleanup any crashed sessions
        shared.omega_session_id = memory_engine.create_study_session()
        
        # Load daily stats
        shared.omega_daily_progress = memory_engine.get_daily_study_minutes()
        shared.omega_streak = memory_engine.get_study_streak()
        shared.push_omega_state()

        # Auto-DND: Mute system volume on Windows
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            shared.omega_pre_mute_vol = volume.GetMasterVolumeLevel()
            volume.SetMute(1, None)
            print("[Protocol Omega] Auto-DND Engaged (System Audio Muted).")
        except Exception as e:
            print(f"[Protocol Omega] Auto-DND failed: {e}")

    # --- Browser Tab Cleanup ---
    try:
        from tools import browser_tools
        from concurrent.futures import ThreadPoolExecutor
        import requests as _requests
        all_tabs = browser_tools._get_all_tabs()
        
        # Identify tabs to close
        tabs_to_close = []
        for tab in all_tabs:
            title = tab.get("title", "").lower()
            url = tab.get("url", "").lower()
            
            is_whitelisted = any(w in title or w in url for w in WHITELIST)
            
            if not is_whitelisted:
                print(f"[Protocol Omega] Closing non-study tab: {title}")
                tabs_to_close.append(tab)
        
        # Close all non-study tabs concurrently
        def _close_tab(t):
            try:
                _requests.get(f"http://127.0.0.1:{t['_port']}/json/close/{t['id']}", timeout=2)
                return True
            except Exception:
                return False
        
        closed_count = 0
        if tabs_to_close:
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(_close_tab, tabs_to_close))
                closed_count = sum(1 for r in results if r)
        
        if closed_count > 0:
            print(f"[Protocol Omega] Cleaned up {closed_count} non-study browser tabs.")
    except Exception as e:
        print(f"[Protocol Omega] Browser cleanup failed: {e}")

    _os_thread = threading.Thread(target=_os_watcher_loop, daemon=True, name="OmegaOS")
    _os_thread.start()

    _vision_thread = threading.Thread(target=_vision_watcher_loop, daemon=True, name="OmegaVision")
    _vision_thread.start()

    _screen_thread = threading.Thread(target=_screen_watcher_loop, daemon=True, name="OmegaScreen")
    _screen_thread.start()

    _mot_thread = threading.Thread(target=_motivation_loop, daemon=True, name="OmegaMotivation")
    _mot_thread.start()
    
    _pomodoro_thread = threading.Thread(target=_pomodoro_loop, daemon=True, name="OmegaPomodoro")
    _pomodoro_thread.start()

    print("\n" + "=" * 50)
    print(" PROTOCOL OMEGA ENGAGED ".center(50, "="))
    print("=" * 50)

    return "Protocol Omega is now active. Unnecessary tabs closed. Let the studying commence."

def deactivate():
    global _running, _warned_windows

    with _omega_lock:
        if not _running:
            return "Protocol Omega is not currently active, sir."

        _running = False
        _warned_windows = {}
        shared.focus_mode_active = False
        
        session_id = shared.omega_session_id
        distractions = shared.omega_distractions
        cycles = shared.omega_pomodoro_cycle
        elapsed_minutes = max(1, int((time.time() - shared.omega_session_start) / 60))
        
        shared.omega_active = False
        shared.omega_phase = "idle"
        shared.omega_session_id = None
        shared.push_omega_state()

        # Restore System Volume
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMute(0, None)
            if hasattr(shared, 'omega_pre_mute_vol'):
                volume.SetMasterVolumeLevel(shared.omega_pre_mute_vol, None)
            print("[Protocol Omega] Auto-DND Disengaged (System Audio Restored).")
        except Exception:
            pass

    print("\n" + "=" * 50)
    print(" PROTOCOL OMEGA DISENGAGED ".center(50, "="))
    print(f" Session Time: {elapsed_minutes} mins | Distractions: {distractions} | Pomodoros: {cycles}")
    print("=" * 50)

    # Generate Post-Study Briefing via LLM
    try:
        import memory_engine
        import llm_engine
        
        breakdown_str = ""
        if distractions > 0 and session_id:
            breakdown = memory_engine.get_distraction_breakdown(session_id)
            if breakdown:
                items = [f"{k} ({v} times)" for k,v in breakdown.items()]
                breakdown_str = f"Specific Distractions caught: {', '.join(items)}."

        prompt = f"""You are Alfred, a loyal AI butler. Master {USER_NAME} just finished a study session with Protocol Omega.
Session length: {elapsed_minutes} minutes.
Distractions detected (phone or off-topic browsing): {distractions}.
{breakdown_str}
Pomodoro cycles completed: {cycles}.

If distractions are 0 and time is good, praise them.
If distractions are high, give them constructive, motivational advice and specifically call out their main distraction from the breakdown.
If time is very short, ask if they felt unmotivated and offer a word of encouragement.
Keep it under 3 sentences, be professional and supportive, spoken format."""
        
        res = llm_engine.chat(messages=[{'role': 'user', 'content': prompt}], options={'temperature': 0.6, 'num_predict': 100})
        briefing = res['message']['content'].strip()
        print(f"[Protocol Omega] Post-Study Report:\n{briefing}")
        
        # Save to DB
        if session_id:
            memory_engine.end_study_session(session_id, briefing, cycles)
            
        if _telegram_available:
            try:
                msg = f"📊 PROTOCOL OMEGA SESSION ENDED\n\n"
                msg += f"⏱ Time: {elapsed_minutes} minutes\n"
                msg += f"🍅 Pomodoros: {cycles}\n"
                msg += f"❌ Distractions: {distractions}\n\n"
                msg += f"🤖 Alfred says:\n{briefing}"
                telegram_notifier.send_alert(msg)
            except Exception:
                pass
            
        _safe_speak(briefing)
        return f"Protocol Omega deactivated. {briefing}"
    except Exception as e:
        print(f"[Protocol Omega] Briefing generation failed: {e}")
        if session_id:
            import memory_engine
            memory_engine.end_study_session(session_id, "Briefing failed.", cycles)
        return f"Protocol Omega has been deactivated. You studied for {elapsed_minutes} minutes with {distractions} recorded distractions."

def is_active():
    return _running
