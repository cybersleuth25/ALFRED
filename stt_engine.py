"""
Speech-to-Text Engine for Alfred.
=================================
Uses a TWO-STAGE approach to eliminate false triggers from background noise:

  Stage 1 (Wake Word): VOSK offline model — runs 100% locally, very noise-resistant.
                        Only triggers on clear speech matching "Alfred" or synonyms.
                        Background TV, music, and conversations are ignored.

  Stage 2 (Command):   Google Cloud STT — high accuracy for full sentence transcription.
                        Only activates AFTER the wake word is confirmed.
"""

import os
import sys
import json
import time
import struct
import pyaudio
import voice_engine
import shared

# ── Vosk Offline Model (for wake word detection & speaker verification) ──
VOSK_MODEL_PATH = os.path.join(os.path.dirname(__file__), "vosk_model")
VOSK_SPK_MODEL_PATH = os.path.join(os.path.dirname(__file__), "vosk_spk")
AUTHORIZED_VOICE_FILE = os.path.join(os.path.dirname(__file__), "authorized_voice.json")

_vosk_model = None
_vosk_spk_model = None
_vosk_available = False
_authorized_voice = None

# Load authorized voice profile if it exists
if os.path.exists(AUTHORIZED_VOICE_FILE):
    try:
        with open(AUTHORIZED_VOICE_FILE, "r") as f:
            data = json.load(f)
            _authorized_voice = data.get("voice_vector")
            print("[STT] Authorized voice profile loaded for Speaker Verification.")
    except Exception as e:
        print(f"[STT] Could not load authorized voice profile: {e}")

try:
    from vosk import Model, SpkModel, KaldiRecognizer
    if os.path.exists(VOSK_MODEL_PATH):
        print("[STT] Loading Vosk offline model for wake word detection...")
        _vosk_model = Model(VOSK_MODEL_PATH)
        if os.path.exists(VOSK_SPK_MODEL_PATH):
            _vosk_spk_model = SpkModel(VOSK_SPK_MODEL_PATH)
            print("[STT] Vosk speaker model loaded successfully.")
        _vosk_available = True
        print("[STT] Vosk model loaded successfully.")
    else:
        print(f"[STT] Vosk model not found at {VOSK_MODEL_PATH}")
except ImportError:
    print("[STT] Vosk not installed. Wake word detection will use Google (less noise-resistant).")
except Exception as e:
    print(f"[STT] Vosk init error: {e}")

# ── Google STT (for command recognition — higher accuracy) ──
import speech_recognition as sr

recognizer = sr.Recognizer()
recognizer.pause_threshold = 1.4           # How long of silence = end of phrase (was 2.5s)
recognizer.non_speaking_duration = 0.6    # Min silence to consider phrase ended (was 1.2s)
recognizer.dynamic_energy_threshold = True
recognizer.energy_threshold = 200         # Lowered for better mic sensitivity (was 300)
recognizer.operation_timeout = None       # Don't time out mid-recognition

try:
    mic = sr.Microphone()
    with mic as source:
        print("[STT] Calibrating microphone for ambient noise...")
        recognizer.adjust_for_ambient_noise(source, duration=1.0)
except Exception as e:
    print(f"[STT Error] Microphone not found: {e}")
    mic = None

# ── Wake Word Configuration ──
WAKE_WORD = "alfred"
WAKE_SYNONYMS = [
    "alfred", "alford", "elfred", "alpha red", "all fred", "al fred",
    "albert", "elf red", "wake up", "hey alfred",
    "alfie", "alfy", "alfread", "off red", "hal fred",   # extra fuzzy variants
    "all right", "alfred please", "yo alfred",
    "friday", "hey friday", "fry day", "fri day",        # Friday persona
    "jarvis", "hey jarvis", "jar vis", "tarvis",         # Jarvis persona
]
# Interrupt-only synonyms: these will stop Alfred mid-speech but do NOT wake him from sleep
INTERRUPT_SYNONYMS = WAKE_SYNONYMS + [
    "buddy", "body", "but he", "but the",  # Common mis-transcriptions of "buddy"
    "stop", "enough", "shut up",           # Emergency interrupt words
]
FOCUS_SYNONYMS = [
    "begin focus mode", "focus mode", "start focus mode",
    "begin protocol omega", "protocol omega", "mega protocol", "omegaprotocol",
]

# Audio config for Vosk
VOSK_RATE = 16000
VOSK_CHUNK = 4000  # ~250ms chunks at 16kHz


def listen_for_wake_word() -> bool:
    """
    Listens for the wake word using Vosk (offline, noise-resistant).
    Falls back to Google STT if Vosk is unavailable.
    Returns True when the wake word is detected.
    """
    # Choose which wake words to listen for
    if shared.focus_mode_active:
        synonyms = FOCUS_SYNONYMS
        prompt = "[FOCUS MODE - Waiting for 'Focus Mode'...]"
    else:
        synonyms = WAKE_SYNONYMS
        prompt = "[Listening for 'Alfred'...]"

    # ── PRIMARY: Vosk offline detection (noise-resistant) ──
    if _vosk_available and _vosk_model:
        return _vosk_listen_for_wake(synonyms, prompt)

    # ── FALLBACK: Google STT (cloud-based, noise-sensitive) ──
    return _google_listen_for_wake(synonyms, prompt)


def _vosk_listen_for_wake(synonyms: list, prompt: str) -> bool:
    """Uses Vosk offline model for wake word detection. Very noise-resistant."""
    pa = None
    stream = None
    try:
        pa = pyaudio.PyAudio()
        
        # Find the default input device
        dev_info = pa.get_default_input_device_info()
        
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=VOSK_RATE,
            input=True,
            frames_per_buffer=VOSK_CHUNK,
        )

        rec = KaldiRecognizer(_vosk_model, VOSK_RATE)
        if _vosk_spk_model:
            rec.SetSpkModel(_vosk_spk_model)
        rec.SetWords(False)  # We only need the text, not word-level timestamps

        print(f"\n{prompt} (Vosk offline - noise resistant)")

        def cosine_similarity(v1, v2):
            dot_product = sum(a * b for a, b in zip(v1, v2))
            magnitude1 = sum(a * a for a in v1) ** 0.5
            magnitude2 = sum(b * b for b in v2) ** 0.5
            if magnitude1 * magnitude2 == 0: return 0
            return dot_product / (magnitude1 * magnitude2)

        # Listen in a loop — each iteration processes ~250ms of audio
        # 200 iterations = ~50 seconds before recycling (prevents dead zones)
        max_iterations = 200
        for _ in range(max_iterations):
            # Check for Facial Auto-Wake
            if getattr(shared, "force_wake", False):
                shared.force_wake = False
                print("\n[Auto-Wake Triggered by Facial Recognition]")
                return True

            # Don't listen while Alfred is speaking (prevents self-trigger)
            if voice_engine.is_speaking():
                time.sleep(0.1)
                continue

            data = stream.read(VOSK_CHUNK, exception_on_overflow=False)

            # Feed audio to Vosk
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text = result.get("text", "").lower().strip()
                
                if text:
                    print(f"   (Vosk heard: '{text}')", end="\r")
                    
                    # Check for wake word
                    if any(word in text for word in synonyms):
                        # Verify Speaker if profile exists
                        if _authorized_voice and "spk" in result:
                            sim = cosine_similarity(result["spk"], _authorized_voice)
                            print(f"\n[Speaker Verification] Sim: {sim:.2f}")
                            if sim < 0.35: # Threshold for Vosk speaker model
                                print(f"[Wake word rejected] Unauthorized voice detected.")
                                voice_engine.speak("Unauthorized user detected. Ignoring command.")
                                # Don't return True, keep listening
                                continue

                        print(f"\n[Wake word detected!] (Vosk: '{text}')")
                        return True
                    
            else:
                # Partial result — check these too for faster response
                partial = json.loads(rec.PartialResult())
                partial_text = partial.get("partial", "").lower().strip()
                if partial_text:
                    # Quick check on partial for faster wake detection
                    if any(word in partial_text for word in synonyms):
                        print(f"\n[Wake word detected!] (Vosk partial: '{partial_text}')")
                        return True

        return False

    except Exception as e:
        print(f"[STT] Vosk wake error: {e}")
        return False
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


def _google_listen_for_wake(synonyms: list, prompt: str) -> bool:
    """Fallback: Google STT for wake word detection (less noise-resistant)."""
    if not mic:
        time.sleep(1)
        return False

    with mic as source:
        print(f"\n{prompt} (Google cloud fallback)")
        recognizer.adjust_for_ambient_noise(source, duration=0.1)
        try:
            audio = recognizer.listen(source, timeout=1, phrase_time_limit=3)
            text = recognizer.recognize_google(audio).lower()
            print(f"   (Heard: '{text}')", end="\r")

            if any(word in text for word in synonyms):
                print(f"\n[Wake word detected!]")
                return True

            # (Removed aggressive voice exit from background listener)

        except sr.WaitTimeoutError:
            pass
        except sr.UnknownValueError:
            pass
        except sr.RequestError:
            pass

    return False


def listen_for_command() -> str:
    """
    Listens for the actual user command AFTER the wake word is confirmed.
    Uses Google STT for maximum transcription accuracy.
    """
    if not mic:
        return ""

    # Wait for Alfred to finish speaking before listening (prevents self-echo
    # from bleeding into the mic and miscalibrating the noise floor)
    _wait_start = time.time()
    while voice_engine.is_speaking():
        time.sleep(0.1)
        if time.time() - _wait_start > 10:  # Safety timeout
            break
    # Brief pause after speech ends to let audio reverb die down
    time.sleep(0.15)

    with mic as source:
        print("\n[Alfred is listening...]")
        # Ambient noise recalibration before each command (catches drift)
        try:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
        except Exception:
            pass
        try:
            audio = recognizer.listen(source, timeout=15, phrase_time_limit=18)
            text = recognizer.recognize_google(audio)
            print(f"You (Voice): {text}")
            return text
        except sr.WaitTimeoutError:
            print("[Alfred heard nothing...]")
            return ""
        except sr.UnknownValueError:
            print("[Alfred couldn't understand...]")
            return ""
        except sr.RequestError as e:
            print(f"[STT Error] Google STT failed (possibly offline): {e}")
            if _vosk_available and _vosk_model:
                print("[STT] Falling back to offline Vosk transcription...")
                try:
                    # Convert audio to Vosk format (16kHz, 1 channel, 16-bit PCM)
                    raw_data = audio.get_raw_data(convert_rate=16000, convert_width=2)
                    from vosk import KaldiRecognizer
                    import json
                    rec = KaldiRecognizer(_vosk_model, 16000)
                    rec.AcceptWaveform(raw_data)
                    result = json.loads(rec.Result())
                    text = result.get("text", "").strip()
                    if text:
                        print(f"You (Voice - Offline Fallback): {text}")
                        return text
                except Exception as ex:
                    print(f"[STT] Offline fallback failed: {ex}")
            return ""
