"""
Full-Duplex Barge-In Engine for JARVIS / ALFRED.
================================================
Monitors microphone input concurrently while Alfred is speaking.
If the user speaks or utters an interrupt keyword (e.g., "stop", "wait", "ruko",
"jarvis", "alfred", "hold on", "chup"), speech playback is stopped in <50ms,
allowing natural, fluid, full-duplex conversational flow.
"""

import threading
import time
import json
import math
import struct
import os
import sys

# Ensure parent directory is in path
sys.path.append(os.path.join(os.path.dirname(__file__)))

# ── Interruption Trigger Registry ──
INTERRUPT_KEYWORDS = {
    # English commands
    "stop", "wait", "hold on", "pause", "quiet", "shut up", "cancel", "halt",
    "enough", "nevermind", "never mind", "excuse me",
    # Wake words (calling Alfred while he speaks redirects him immediately)
    "alfred", "alford", "jarvis", "tarvis", "friday", "fryday", "hey",
    # Hindi & Hinglish commands
    "ruko", "ruk jao", "chup", "chup raho", "chup ho jao", "ek second",
    "bas", "bas karo", "suno", "arre suno", "shh", "aaram se", "thehro"
}

_monitor_thread = None
_stop_monitoring_flag = threading.Event()
_interrupted_event = threading.Event()
_last_interruption_phrase = ""
_lock = threading.Lock()

# Vosk offline recognizer reference (borrowed from stt_engine if available)
_vosk_model = None

def _get_vosk_model():
    global _vosk_model
    if _vosk_model is None:
        try:
            import stt_engine
            if getattr(stt_engine, '_vosk_available', False) and getattr(stt_engine, '_vosk_model', None):
                _vosk_model = stt_engine._vosk_model
        except Exception:
            pass
    return _vosk_model


def _calculate_rms(audio_chunk: bytes) -> float:
    """Calculates Root Mean Square (RMS) amplitude of PCM audio chunk."""
    count = len(audio_chunk) // 2
    if count == 0:
        return 0.0
    shorts = struct.unpack(f"{count}h", audio_chunk)
    sum_squares = sum(s * s for s in shorts)
    return math.sqrt(sum_squares / count)


def _barge_in_worker():
    """Background thread that actively listens to the mic during speech playback."""
    global _last_interruption_phrase
    import pyaudio
    import voice_engine

    pa = None
    stream = None
    try:
        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1600  # ~100ms chunks
        )

        model = _get_vosk_model()
        rec = None
        if model:
            from vosk import KaldiRecognizer
            rec = KaldiRecognizer(model, 16000)
            rec.SetWords(False)

        consecutive_voice_frames = 0
        energy_threshold = 850.0  # RMS threshold for loud user interruption

        while not _stop_monitoring_flag.is_set():
            if not voice_engine.is_speaking():
                break

            try:
                data = stream.read(1600, exception_on_overflow=False)
            except Exception:
                continue

            if not data:
                continue

            # 1. Phonetic / Keyword Interruption via Vosk
            if rec:
                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result())
                    text = res.get("text", "").lower().strip()
                else:
                    part = json.loads(rec.PartialResult())
                    text = part.get("partial", "").lower().strip()

                if text:
                    # Ignore Alfred's own voice leaking from computer speakers
                    if voice_engine.is_self_echo(text):
                        continue

                    # Check for explicit user interrupt words only
                    matched = [w for w in INTERRUPT_KEYWORDS if w in text]

                    if matched:
                        _last_interruption_phrase = text
                        _interrupted_event.set()
                        print(f"\n[Barge-In] 🛑 User interrupted with '{matched[0]}': '{text}' -> Stopping speech immediately.")
                        voice_engine.stop_speaking()
                        break

            # 2. RMS Energy Fallback — raised threshold (2500) to prevent speaker audio from self-triggering
            rms = _calculate_rms(data)
            if rms > 2500.0:
                consecutive_voice_frames += 1
                if consecutive_voice_frames >= 4:  # ~400ms of sustained loud external voice
                    _last_interruption_phrase = "[voice energy cutoff]"
                    _interrupted_event.set()
                    print(f"\n[Barge-In] 🛑 Loud voice cutoff detected (RMS: {int(rms)}) -> Stopping speech.")
                    voice_engine.stop_speaking()
                    break
            else:
                consecutive_voice_frames = max(0, consecutive_voice_frames - 1)

    except Exception as e:
        # Silently fail if microphone device is locked or unavailable
        pass
    finally:
        if stream:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
        if pa:
            try:
                pa.terminate()
            except Exception:
                pass


def start_monitoring():
    """Starts the concurrent microphone monitor while speech is active."""
    global _monitor_thread, _last_interruption_phrase
    with _lock:
        stop_monitoring()  # Stop any prior monitor
        _stop_monitoring_flag.clear()
        _interrupted_event.clear()
        _last_interruption_phrase = ""
        _monitor_thread = threading.Thread(target=_barge_in_worker, daemon=True, name="BargeInMonitor")
        _monitor_thread.start()


def stop_monitoring():
    """Stops the mic monitor thread."""
    global _monitor_thread
    _stop_monitoring_flag.set()
    if _monitor_thread and _monitor_thread.is_alive():
        if threading.current_thread() != _monitor_thread:
            _monitor_thread.join(timeout=0.3)
    _monitor_thread = None


def was_interrupted() -> bool:
    """Returns True if the last speech session was interrupted by the user."""
    return _interrupted_event.is_set()


def get_last_interruption_phrase() -> str:
    """Returns the text or phrase that triggered the interruption."""
    return _last_interruption_phrase
