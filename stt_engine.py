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
recognizer.pause_threshold = 2.0
recognizer.non_speaking_duration = 1.0
recognizer.dynamic_energy_threshold = True

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
]
OMEGA_SYNONYMS = [
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
        synonyms = OMEGA_SYNONYMS
        prompt = "[FOCUS MODE - Waiting for 'Protocol Omega'...]"
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
        max_iterations = 40  # ~10 seconds before recycling (to keep responsive)
        for _ in range(max_iterations):
            # Check for Facial Auto-Wake
            if getattr(shared, "force_wake", False):
                shared.force_wake = False
                print("\n[Auto-Wake Triggered by Facial Recognition]")
                stream.stop_stream()
                stream.close()
                pa.terminate()
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
                        stream.stop_stream()
                        stream.close()
                        pa.terminate()
                        return True
                    
                    # Allow voice exit
                    if "quit" in text or "exit" in text or "shut down" in text:
                        print("\n[System] Shutting down via voice command.")
                        stream.stop_stream()
                        stream.close()
                        pa.terminate()
                        sys.exit(0)
            else:
                # Partial result — check these too for faster response
                partial = json.loads(rec.PartialResult())
                partial_text = partial.get("partial", "").lower().strip()
                if partial_text:
                    # Quick check on partial for faster wake detection
                    if any(word in partial_text for word in synonyms):
                        print(f"\n[Wake word detected!] (Vosk partial: '{partial_text}')")
                        stream.stop_stream()
                        stream.close()
                        pa.terminate()
                        return True

        stream.stop_stream()
        stream.close()
        pa.terminate()
        return False

    except Exception as e:
        print(f"[STT] Vosk wake error: {e}")
        return False


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

            if "quit" in text or "exit" in text or "shut down" in text:
                print("\n[System] Shutting down via voice command.")
                sys.exit(0)

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

    with mic as source:
        print("\n[Alfred is listening...]")
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=30)
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
            print(f"[Error fetching STT results]: {e}")
            return ""
