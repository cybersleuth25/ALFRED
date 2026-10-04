"""
Tripwire Engine for Alfred (Feature 5: Anomaly Detection & Digital Tripwire).
=============================================================================
Provides active cyber-defense and physical sentinel capabilities:
1. USB / Removable Drive Insertion Monitoring
2. Rogue / Suspicious Process Anomaly Detection (Miners, Obfuscated Scripts, CPU Spikes)
3. After-Hours Sentry (1 AM - 6 AM Unauthorized Physical Access Detection)
4. Automated Evidence Capture (Webcam Snapshots) & Telegram Photo Dispatch
"""

import os
import time
import threading
import datetime
import psutil
import cv2
from dotenv import load_dotenv

import shared
import memory_engine

try:
    import telegram_notifier
    _telegram_available = telegram_notifier.is_available()
except ImportError:
    _telegram_available = False

INCIDENTS_DIR = os.path.join(os.path.dirname(__file__), "assets", "incidents")
os.makedirs(INCIDENTS_DIR, exist_ok=True)
WORKSPACE_INCIDENTS_DIR = os.path.join(os.path.dirname(__file__), "Alfred_Workspace", "incidents")
os.makedirs(WORKSPACE_INCIDENTS_DIR, exist_ok=True)

# Whitelist for legitimate high-CPU processes
_SAFE_PROCESS_NAMES = frozenset([
    "python.exe", "pythonw.exe", "code.exe", "chrome.exe", "msedge.exe", "brave.exe",
    "firefox.exe", "ollama.exe", "ollama_llama_server.exe", "explorer.exe",
    "taskmgr.exe", "system idle process", "system", "vmmem", "dwm.exe"
])

# Known cryptominer or malicious signatures
_SUSPICIOUS_NAMES = frozenset([
    "xmrig.exe", "ethminer.exe", "minergate.exe", "ccminer.exe", "cpuminer.exe",
    "phoenixminer.exe", "nbminer.exe", "t-rex.exe", "nanominer.exe"
])

_tripwire_running = False
_known_drives = set()
_alerted_pids = set()
_last_after_hours_alert = 0
_lock = threading.Lock()


def _get_current_drives() -> set:
    """Returns set of all currently mounted partition mountpoints."""
    try:
        return {p.mountpoint.upper() for p in psutil.disk_partitions(all=True) if p.mountpoint}
    except Exception:
        return set()


def capture_security_snapshot(reason: str = "tripwire") -> str:
    """
    Captures a webcam frame or screenshot as evidence, saves it, and returns the filepath.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(INCIDENTS_DIR, f"{reason}_{timestamp}.jpg")

    captured = False

    # 1. Try to grab frame from shared vision / security engine if active
    try:
        import security_engine
        if hasattr(security_engine, "get_latest_frame"):
            frame = security_engine.get_latest_frame()
            if frame is not None and frame.size > 0:
                cv2.imwrite(filepath, frame)
                captured = True
    except Exception:
        pass

    # 2. If not captured, open webcam directly for a quick frame grab
    if not captured:
        try:
            cam_idx = int(os.getenv("CAMERA_INDEX", "0"))
            cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    cv2.imwrite(filepath, frame)
                    captured = True
                cap.release()
        except Exception:
            pass

    # 3. Fallback: Screen capture if webcam unavailable
    if not captured:
        try:
            import pyautogui
            screenshot = pyautogui.screenshot()
            screenshot.save(filepath)
            captured = True
        except Exception:
            pass

    return filepath if (captured and os.path.exists(filepath)) else ""


# ==========================================
# SUB-MONITOR 1: USB / HARDWARE TRIPWIRE
# ==========================================

def _usb_monitor_loop():
    """Continuously checks for newly attached drives and flash disks."""
    global _known_drives
    _known_drives = _get_current_drives()
    print(f"[Tripwire Engine] USB Monitor active. Known drives: {_known_drives}")

    while _tripwire_running:
        try:
            time.sleep(3)
            current_drives = _get_current_drives()
            new_drives = current_drives - _known_drives
            _known_drives = current_drives  # Update immediately to avoid repeating

            if new_drives:
                drive_str = ", ".join(new_drives)
                print(f"[Tripwire Engine] 🚨 USB INSERTION DETECTED: {drive_str}")

                # 1. Capture photo evidence immediately
                snapshot_path = ""
                try:
                    snapshot_path = capture_security_snapshot(reason="usb_insertion")
                    print(f"[Tripwire Engine] Snapshot captured: {snapshot_path}")
                except Exception as e:
                    print(f"[Tripwire Engine] Snapshot capture error: {e}")

                # 2. Log incident to database
                inc_id = 0
                try:
                    details = f"New removable hardware / drive connected: {drive_str}"
                    inc_id = memory_engine.log_security_incident(
                        incident_type="usb_insertion",
                        severity="high",
                        details=details,
                        snapshot_path=snapshot_path
                    )
                except Exception as e:
                    print(f"[Tripwire Engine] Incident logging error: {e}")

                # 3. Push system notification and speech
                try:
                    shared.push_notification(f"USB Device Detected: {drive_str}", "Security")
                except Exception as e:
                    print(f"[Tripwire Engine] Push notification error: {e}")

                try:
                    shared.safe_speak(f"Security alert: New USB storage device {drive_str} has been connected to the system.")
                except Exception as e:
                    print(f"[Tripwire Engine] Speech alert error: {e}")

                # 4. Dispatch Telegram Photo Alert
                try:
                    import telegram_notifier
                    if telegram_notifier.is_available():
                        caption = (
                            f"🚨 *DIGITAL TRIPWIRE ALERT: USB INSERTION*\n\n"
                            f"Drive(s): `{drive_str}`\n"
                            f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}\n"
                            f"Incident ID: #{inc_id}\n\nPhoto evidence attached."
                        )
                        if snapshot_path and os.path.exists(snapshot_path):
                            print(f"[Tripwire Engine] Sending photo alert to Telegram: {snapshot_path}")
                            sent = telegram_notifier.send_photo_alert(snapshot_path, caption)
                            print(f"[Tripwire Engine] Telegram photo alert sent: {sent}")
                        else:
                            telegram_notifier.send_alert(caption)
                except Exception as e:
                    print(f"[Tripwire Engine] Telegram alert failed: {e}")

        except Exception as e:
            print(f"[Tripwire Engine] USB monitor loop error: {e}")
            time.sleep(5)


# ==========================================
# SUB-MONITOR 2: PROCESS ANOMALY SCANNER
# ==========================================

def _is_suspicious_cmdline(cmdline_list: list) -> bool:
    """Checks if a command line string indicates obfuscated or hidden execution."""
    if not cmdline_list:
        return False
    full_cmd = " ".join(cmdline_list).lower()
    suspicious_flags = [
        "-enc ", "-encodedcommand ", "-w hidden", "-windowstyle hidden",
        "-nop -w hidden", "downloadstring", "iex(new-object", "iex (new-object",
        "bypass -c", "-exec bypass"
    ]
    return any(flag in full_cmd for flag in suspicious_flags)


def _process_scanner_loop():
    """Periodically scans for high CPU rogue processes and hidden scripts."""
    global _alerted_pids

    while _tripwire_running:
        try:
            time.sleep(30)
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'cmdline', 'exe']):
                try:
                    pinfo = proc.info
                    pid = pinfo['pid']
                    name = (pinfo['name'] or '').lower()
                    cmdline = pinfo.get('cmdline') or []

                    if pid in _alerted_pids or pid <= 4:
                        continue

                    is_rogue = False
                    severity = "medium"
                    reason = ""

                    # 1. Known miner signature
                    if name in _SUSPICIOUS_NAMES:
                        is_rogue = True
                        severity = "critical"
                        reason = f"Known cryptomining process detected: {name}"

                    # 2. Obfuscated PowerShell / hidden execution
                    elif _is_suspicious_cmdline(cmdline):
                        is_rogue = True
                        severity = "high"
                        reason = f"Suspicious obfuscated command line: {' '.join(cmdline)[:150]}"

                    # 3. High CPU anomaly from unrecognized executable
                    elif name not in _SAFE_PROCESS_NAMES and pinfo.get('cpu_percent', 0) > 85.0:
                        is_rogue = True
                        severity = "high"
                        reason = f"Unrecognized process consuming extreme CPU ({pinfo['cpu_percent']}%): {name}"

                    if is_rogue:
                        _alerted_pids.add(pid)
                        print(f"[Tripwire Engine] 🚨 PROCESS ANOMALY (PID {pid}): {reason}")

                        snapshot_path = capture_security_snapshot(reason="process_anomaly")
                        details = f"{reason} | PID: {pid} | Exe: {pinfo.get('exe', 'Unknown')}"

                        inc_id = memory_engine.log_security_incident(
                            incident_type="rogue_process",
                            severity=severity,
                            details=details,
                            snapshot_path=snapshot_path
                        )

                        shared.push_notification(f"Process Anomaly: {name} (PID {pid})", "Security")

                        if _telegram_available:
                            try:
                                msg = (
                                    f"⚠️ *SECURITY ALERT: ROGUE PROCESS*\n\n"
                                    f"Process: `{name}` (PID: `{pid}`)\n"
                                    f"Reason: {reason}\n"
                                    f"Severity: {severity.upper()}\n"
                                    f"Incident ID: #{inc_id}"
                                )
                                if snapshot_path:
                                    telegram_notifier.send_photo_alert(snapshot_path, msg)
                                else:
                                    telegram_notifier.send_alert(msg)
                            except Exception as e:
                                print(f"[Tripwire Engine] Telegram alert failed: {e}")

                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

        except Exception as e:
            print(f"[Tripwire Engine] Process scanner error: {e}")
            time.sleep(10)


# ==========================================
# SUB-MONITOR 3: AFTER-HOURS SENTRY
# ==========================================

def _after_hours_sentry_loop():
    """Checks for unauthorized desktop access outside regular active hours."""
    global _last_after_hours_alert

    while _tripwire_running:
        try:
            time.sleep(15)
            now = datetime.datetime.now()
            hour = now.hour

            # After-hours defined as 01:00 to 06:00
            start_hour = int(os.getenv("AFTER_HOURS_START", "1"))
            end_hour = int(os.getenv("AFTER_HOURS_END", "6"))

            is_after_hours = False
            if start_hour < end_hour:
                is_after_hours = start_hour <= hour < end_hour
            else:
                is_after_hours = hour >= start_hour or hour < end_hour

            if not is_after_hours:
                continue

            # Check if there is active activity right now
            if shared.context_presence == "present" and shared.context_current_activity != "idle":
                # Rate limit to once every 10 minutes
                if time.time() - _last_after_hours_alert > 600:
                    _last_after_hours_alert = time.time()
                    print("[Tripwire Engine] 🚨 AFTER-HOURS DESKTOP ACTIVITY DETECTED!")

                    snapshot_path = capture_security_snapshot(reason="after_hours_access")
                    details = f"Physical desktop activity detected at {now.strftime('%I:%M %p')}. Activity: {shared.context_current_activity}"

                    inc_id = memory_engine.log_security_incident(
                        incident_type="after_hours_access",
                        severity="critical",
                        details=details,
                        snapshot_path=snapshot_path
                    )

                    if _telegram_available and snapshot_path:
                        try:
                            telegram_notifier.send_photo_alert(
                                snapshot_path,
                                f"🚨 *SECURITY BREACH: AFTER-HOURS ACCESS*\n\n"
                                f"Workstation activity detected at `{now.strftime('%I:%M:%S %p')}`.\n"
                                f"Activity: {shared.context_current_activity}\n"
                                f"Incident ID: #{inc_id}\n\nPhoto of current user attached."
                            )
                        except Exception as e:
                            print(f"[Tripwire Engine] Telegram alert failed: {e}")

                    # Auto-lock if configured in .env
                    if os.getenv("AFTER_HOURS_AUTO_LOCK", "false").lower() == "true":
                        try:
                            import ctypes
                            ctypes.windll.user32.LockWorkStation()
                            print("[Tripwire Engine] Workstation locked automatically.")
                        except Exception as e:
                            print(f"[Tripwire Engine] Auto-lock failed: {e}")

        except Exception as e:
            print(f"[Tripwire Engine] After-hours sentry error: {e}")
            time.sleep(15)


# ==========================================
# PUBLIC API & CONTROL
# ==========================================

def kill_process(pid: int) -> dict:
    """Terminates a process by PID."""
    try:
        proc = psutil.Process(pid)
        proc_name = proc.name()
        proc.kill()
        return {"success": True, "message": f"Process {proc_name} (PID {pid}) successfully terminated."}
    except psutil.NoSuchProcess:
        return {"success": False, "error": f"PID {pid} no longer exists."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_tripwire_status() -> dict:
    """Returns the operational status of the Digital Tripwire subsystem."""
    now = datetime.datetime.now()
    start_hour = int(os.getenv("AFTER_HOURS_START", "1"))
    end_hour = int(os.getenv("AFTER_HOURS_END", "6"))
    if start_hour < end_hour:
        is_after_hours = start_hour <= now.hour < end_hour
    else:
        is_after_hours = now.hour >= start_hour or now.hour < end_hour

    return {
        "running": _tripwire_running,
        "monitored_drives": list(_known_drives),
        "after_hours_active": is_after_hours,
        "telegram_alerts_enabled": _telegram_available
    }


def start_tripwire_daemon():
    """Starts all Tripwire sentinel sub-threads in the background."""
    global _tripwire_running
    with _lock:
        if _tripwire_running:
            return
        _tripwire_running = True

    t_usb = threading.Thread(target=_usb_monitor_loop, daemon=True, name="Tripwire-USB")
    t_proc = threading.Thread(target=_process_scanner_loop, daemon=True, name="Tripwire-Proc")
    t_sentry = threading.Thread(target=_after_hours_sentry_loop, daemon=True, name="Tripwire-Sentry")

    t_usb.start()
    t_proc.start()
    t_sentry.start()

    print("[Tripwire Engine] 🛡️ Digital Tripwire & Cyber Sentinel active.")


def stop_tripwire_daemon():
    """Stops the Tripwire daemon."""
    global _tripwire_running
    with _lock:
        _tripwire_running = False
    print("[Tripwire Engine] Stopped.")
