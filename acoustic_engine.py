"""
Acoustic Sentry Ear for JARVIS / ALFRED.
========================================
Passive ambient audio anomaly intelligence:
- Continuous background microphone monitoring with adaptive rolling RMS noise floor.
- FFT frequency spectrum transient analysis (detects glass break, door slams, shouting).
- Automated physical defense: webcam capture, SQLite incident logging, and Telegram photo dispatch.
- Integrates with Sentry Mode and Tripwire Engine.
"""

import os
import time
import math
import struct
import threading
import datetime
import numpy as np
import pyaudio
from dotenv import load_dotenv

import shared
import memory_engine

load_dotenv()

# Audio stream settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK_SIZE = 1024  # ~64ms buffer

_acoustic_running = False
_thread = None
_lock = threading.Lock()

# Anomaly state tracking
_ambient_rms = 150.0       # Dynamic baseline floor
_sensitivity_multiplier = 4.0  # Spike must exceed 4x ambient
_min_absolute_rms = 1200.0    # Absolute loudness floor (prevents false trips in dead silence)
_cooldown_seconds = 10.0      # Minimum seconds between alerts
_last_alert_time = 0.0
_last_anomaly = {}

def is_active() -> bool:
    """Returns True if acoustic sentry is actively listening."""
    return _acoustic_running

def get_status() -> dict:
    """Returns real-time telemetry of the acoustic sentry ear."""
    return {
        "active": _acoustic_running,
        "ambient_rms": round(_ambient_rms, 1),
        "sensitivity": _sensitivity_multiplier,
        "min_rms_threshold": _min_absolute_rms,
        "last_anomaly": _last_anomaly,
        "cooldown_remaining": max(0.0, round(_cooldown_seconds - (time.time() - _last_alert_time), 1))
    }

def set_sensitivity(multiplier: float):
    """Adjusts sensitivity multiplier (e.g., 3.0 for high sensitivity, 6.0 for low)."""
    global _sensitivity_multiplier
    _sensitivity_multiplier = max(1.5, min(10.0, float(multiplier)))

def _classify_transient(samples: np.ndarray, rate: int) -> tuple[str, float]:
    """
    Performs FFT spectral analysis on audio chunk.
    Returns (anomaly_type, confidence_score).
    """
    if len(samples) == 0:
        return "unknown_spike", 0.5
    
    # Compute FFT magnitude spectrum
    fft_vals = np.abs(np.fft.rfft(samples))
    freqs = np.fft.rfftfreq(len(samples), 1.0 / rate)

    total_energy = np.sum(fft_vals) + 1e-6
    # Frequency bands
    low_energy = np.sum(fft_vals[freqs < 800])
    mid_energy = np.sum(fft_vals[(freqs >= 800) & (freqs < 3000)])
    high_energy = np.sum(fft_vals[freqs >= 3000])

    high_ratio = high_energy / total_energy
    low_ratio = low_energy / total_energy

    # Spectral centroid
    centroid = np.sum(freqs * fft_vals) / total_energy

    if high_ratio > 0.40 and centroid > 3200:
        return "glass_shatter", round(float(high_ratio), 2)
    elif low_ratio > 0.65 and centroid < 900:
        return "door_impact_knock", round(float(low_ratio), 2)
    elif mid_energy / total_energy > 0.55:
        return "voice_shout_distress", round(float(mid_energy / total_energy), 2)
    else:
        return "acoustic_transient_spike", round(float(max(high_ratio, low_ratio)), 2)


def _trigger_acoustic_breach(anomaly_type: str, rms: float, confidence: float):
    """Executes defensive response: snapshots, incident logging, Telegram dispatch, and voice alert."""
    global _last_alert_time, _last_anomaly
    now = time.time()
    if now - _last_alert_time < _cooldown_seconds:
        return  # In cooldown

    _last_alert_time = now
    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    readable_type = anomaly_type.replace("_", " ").title()

    _last_anomaly = {
        "type": anomaly_type,
        "readable": readable_type,
        "rms": round(rms, 1),
        "confidence": confidence,
        "timestamp": timestamp_str
    }

    print(f"\n[Acoustic Sentry] [ALERT] ANOMALY DETECTED: {readable_type} (RMS: {rms:.1f}, Conf: {confidence})")

    # 1. Capture physical evidence via tripwire snapshot
    snapshot_path = ""
    try:
        import tripwire_engine
        snapshot_path = tripwire_engine.capture_security_snapshot(reason=f"acoustic_{anomaly_type}")
    except Exception as e:
        print(f"[Acoustic Sentry] Snapshot error: {e}")

    # 2. Log incident to database
    inc_id = 0
    try:
        details = f"Acoustic perimeter alert: {readable_type} (RMS: {rms:.1f}, Confidence: {confidence*100:.0f}%)"
        inc_id = memory_engine.log_security_incident(
            incident_type="acoustic_anomaly",
            severity="high",
            details=details,
            snapshot_path=snapshot_path
        )
    except Exception as e:
        print(f"[Acoustic Sentry] DB log error: {e}")

    # 3. Push real-time event to Frontend UI
    try:
        shared.push_log(f"🚨 Acoustic Breach: {readable_type} (RMS: {rms:.0f})", "Security")
        shared.event_queue.put({
            "type": "acoustic_breach",
            "anomaly": readable_type,
            "rms": round(rms, 1),
            "timestamp": timestamp_str
        })
    except Exception:
        pass

    # 4. Dispatch Telegram Photo Alert
    try:
        import telegram_notifier
        if telegram_notifier.is_available():
            caption = (
                f"🚨 *ACOUSTIC PERIMETER BREACH*\n\n"
                f"Event: *{readable_type}*\n"
                f"Decibel Metric (RMS): `{rms:.1f}`\n"
                f"Confidence: `{confidence*100:.0f}%`\n"
                f"Time: {timestamp_str}\n"
                f"Incident: #{inc_id}\n\nPhoto evidence captured."
            )
            if snapshot_path and os.path.exists(snapshot_path):
                telegram_notifier.send_photo_alert(snapshot_path, caption)
            else:
                telegram_notifier.send_alert(caption)
    except Exception as e:
        print(f"[Acoustic Sentry] Telegram alert error: {e}")

    # 5. Spoken warning if appropriate
    try:
        shared.safe_speak(f"Security notice: {readable_type} detected at perimeter.", author="Security")
    except Exception:
        pass


def _acoustic_loop():
    """Background monitoring thread reading raw PCM audio."""
    global _acoustic_running, _ambient_rms
    pa = pyaudio.PyAudio()
    stream = None

    try:
        stream = pa.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )
        print("[Acoustic Sentry] Microphone stream active. Monitoring ambient acoustics...")
    except Exception as e:
        print(f"[Acoustic Sentry] Audio hardware open failed: {e}")
        pa.terminate()
        _acoustic_running = False
        return

    # Warmup calibration (first 1 second to establish ambient baseline)
    warmup_chunks = int(RATE / CHUNK_SIZE)
    ambient_buffer = []

    try:
        while _acoustic_running:
            try:
                raw_data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            except Exception:
                time.sleep(0.05)
                continue

            if len(raw_data) < CHUNK_SIZE * 2:
                continue

            # Unpack 16-bit PCM
            count = len(raw_data) // 2
            shorts = struct.unpack(f"{count}h", raw_data)
            np_data = np.array(shorts, dtype=np.float32)

            # Calculate RMS energy
            rms = math.sqrt(np.mean(np_data ** 2))

            # Calibrate / update slow rolling ambient baseline
            if len(ambient_buffer) < warmup_chunks:
                ambient_buffer.append(rms)
                _ambient_rms = float(np.mean(ambient_buffer))
                continue
            else:
                # Exponential moving average for baseline (~30 second window)
                _ambient_rms = 0.98 * _ambient_rms + 0.02 * min(rms, _ambient_rms * 1.5)

            # Check for sudden explosive transient
            threshold = max(_ambient_rms * _sensitivity_multiplier, _min_absolute_rms)
            if rms > threshold:
                anomaly_type, confidence = _classify_transient(np_data, RATE)
                _trigger_acoustic_breach(anomaly_type, rms, confidence)

            # Yield slightly to avoid burning 100% CPU on tight audio loop
            time.sleep(0.005)

    except Exception as e:
        print(f"[Acoustic Sentry] Monitoring loop encountered error: {e}")
    finally:
        try:
            if stream:
                stream.stop_stream()
                stream.close()
        except Exception:
            pass
        pa.terminate()
        _acoustic_running = False
        print("[Acoustic Sentry] Daemon terminated.")


def start_acoustic_daemon():
    """Starts the Acoustic Sentry Ear background daemon."""
    global _acoustic_running, _thread
    with _lock:
        if _acoustic_running:
            return True
        _acoustic_running = True
        _thread = threading.Thread(target=_acoustic_loop, daemon=True, name="AcousticSentryThread")
        _thread.start()
        print("[Acoustic Sentry] Background ear armed and operational.")
        return True


def stop_acoustic_daemon():
    """Stops the Acoustic Sentry Ear background daemon."""
    global _acoustic_running
    with _lock:
        _acoustic_running = False
        print("[Acoustic Sentry] Background ear disarmed.")
        return True


if __name__ == "__main__":
    print("Testing Acoustic Sentry Ear for 5 seconds...")
    start_acoustic_daemon()
    time.sleep(5)
    print("Status:", get_status())
    stop_acoustic_daemon()
    time.sleep(1)
    print("Test complete.")
