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

# Ensure UTF-8 console output on Windows to support Devanagari Hindi characters without crashing
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


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
recognizer.pause_threshold = 0.85          # Natural conversational pause (was 0.65s, prevents premature cutoffs)
recognizer.non_speaking_duration = 0.45    # Clean silence cutoff
recognizer.dynamic_energy_threshold = True
recognizer.energy_threshold = 150         # Responsive mic calibration
recognizer.operation_timeout = None       # Don't time out mid-recognition

# ── Groq Whisper Turbo Low-Latency Engine (<250ms) ──
_groq_client = None

def _get_groq_client():
    """Lazily initializes and reuses Groq client for low-latency Whisper STT."""
    global _groq_client
    if _groq_client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if api_key and not api_key.startswith("your_"):
            try:
                import groq
                _groq_client = groq.Groq(api_key=api_key)
            except Exception as e:
                print(f"[STT] Groq client initialization failed: {e}")
    return _groq_client


def _transcribe_with_groq(audio) -> str:
    """
    Ultra-low latency multilingual transcription (<250ms) using Groq whisper-large-v3-turbo.
    Supports English, Hindi, and Hinglish with extreme speed and acoustic precision.
    """
    client = _get_groq_client()
    if not client:
        return ""
    try:
        import io
        wav_bytes = audio.get_wav_data(convert_rate=16000, convert_width=2)
        bio = io.BytesIO(wav_bytes)
        bio.name = "speech.wav"
        
        model_name = os.getenv("STT_MODEL", "whisper-large-v3-turbo")
        prompt = (
            "Voice commands for personal AI assistant ALFRED / JARVIS. User is Master Mihir in Chikkamagaluru, India. "
            "Accurately transcribes technical terms, code snippets, Indian English accents, Hindi, Hinglish, Spotify song titles, "
            "calendar events, emails, system commands, and conversational dialogue."
        )
        
        t0 = time.time()
        resp = client.audio.transcriptions.create(
            file=("speech.wav", bio.getvalue()),
            model=model_name,
            prompt=prompt,
            temperature=0.0
        )
        text = resp.text.strip()
        elapsed = round(time.time() - t0, 3)
        if text:
            print(f"You (Groq {model_name}, {elapsed}s): {text}")
            return text
        return ""
    except Exception as e:
        error_type = type(e).__name__
        print(f"[STT Groq {error_type}]: {e}")
        return ""

try:
    mic = sr.Microphone()
    with mic as source:
        print("[STT] Calibrating microphone for ambient noise...")
        recognizer.adjust_for_ambient_noise(source, duration=0.8)
except Exception as e:
    print(f"[STT Error] Microphone not found: {e}")
    mic = None

# ── Wake Word Configuration ──
WAKE_WORD = "alfred"
WAKE_SYNONYMS = [
    "alfred", "alford", "elfred", "alpha red", "all fred", "al fred",
    "albert", "elf red", "wake up", "hey alfred",
    "alfie", "alfy", "alfread", "off red", "hal fred",
    "alferd", "aal-fred", "alfred please", "yo alfred",
    "el fred", "all friend", "our friend", "al freid", "el ford",
    "ulfrad", "al fret", "al freed", "halford", "all-fred",
    "suno alfred", "sun alfred", "suno",                          # Indian bilingual wake triggers
    "friday", "hey friday", "fry day", "fri day", "fryday", "suno friday",
    "jarvis", "hey jarvis", "jar vis", "tarvis", "jarwis", "yaarvis", "jharvis", "suno jarvis"
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

            # Don't listen while Alfred is speaking or during echo reverb cooldown (prevents self-wake)
            if voice_engine.is_speaking() or (time.time() - voice_engine.get_last_spoken_time() < 0.6):
                time.sleep(0.1)
                # Flush any mic buffer accumulated during speech so we don't process old speaker audio
                try:
                    avail = stream.get_read_available()
                    if avail > 0:
                        stream.read(avail, exception_on_overflow=False)
                except Exception:
                    pass
                continue

            data = stream.read(VOSK_CHUNK, exception_on_overflow=False)

            # Feed audio to Vosk
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text = result.get("text", "").lower().strip()
                
                if text:
                    print(f"   (Vosk heard: '{text}')", end="\r")
                    
                    # Reject self-echo (e.g. Alfred saying his own name in greeting/status)
                    if voice_engine.is_self_echo(text):
                        continue

                    # Check for wake word
                    if any(word in text for word in synonyms):
                        # Verify Speaker only if explicitly enabled via SPEAKER_VERIFICATION=true
                        enable_spk = os.getenv("SPEAKER_VERIFICATION", "false").lower() == "true"
                        if enable_spk and _authorized_voice and "spk" in result:
                            sim = cosine_similarity(result["spk"], _authorized_voice)
                            print(f"\n[Speaker Verification] Sim: {sim:.2f}")
                            if sim < 0.25: # Relaxed threshold so legitimate user is never blocked
                                print(f"[Wake word rejected] Unauthorized voice detected.")
                                voice_engine.speak("Unauthorized user detected. Ignoring command.")
                                # Don't return True, keep listening
                                continue

                        shared.last_wake_phrase = text
                        print(f"\n[Wake word detected!] (Vosk: '{text}')")
                        return True
                    
            else:
                # Partial result — check these too for faster response
                partial = json.loads(rec.PartialResult())
                partial_text = partial.get("partial", "").lower().strip()
                if partial_text:
                    if voice_engine.is_self_echo(partial_text):
                        continue
                    # Quick check on partial for faster wake detection
                    if any(word in partial_text for word in synonyms):
                        shared.last_wake_phrase = partial_text
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
            # Use Indian English acoustic model for accurate wake recognition
            text = recognizer.recognize_google(audio, language="en-IN").lower()
            print(f"   (Heard: '{text}')", end="\r")

            if any(word in text for word in synonyms):
                shared.last_wake_phrase = text
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
    # Generous pause after speech ends to let audio reverb and hardware buffers drain completely
    time.sleep(0.5)

    with mic as source:
        print("\n[Alfred is listening... (English & Hindi enabled)]")
        # NOTE: Do NOT call adjust_for_ambient_noise here — it eats the first 500ms of user speech!
        # Background dynamic_energy_threshold handles noise floor tracking automatically.
        try:
            audio = recognizer.listen(source, timeout=15, phrase_time_limit=25)
        except sr.WaitTimeoutError:
            print("[Alfred heard nothing...]")
            return ""

        # ── Stage 1: Ultra-Fast Groq Whisper Turbo (<250ms) ──
        groq_text = _transcribe_with_groq(audio)
        if groq_text:
            if voice_engine.is_self_echo(groq_text):
                print(f"[STT] Ignored acoustic self-echo from speakers: '{groq_text}'")
                return ""
            return groq_text

        # ── Stage 2: Fallback to Google STT Dual-Pass (en-IN + hi-IN) ──
        primary_lang = os.getenv("STT_PRIMARY_LANGUAGE", "en-IN")
        secondary_lang = os.getenv("STT_SECONDARY_LANGUAGE", "hi-IN")

        # Pass 1: Primary Indian English (covers Indian accents, Hinglish, loanwords, song titles)
        try:
            text = recognizer.recognize_google(audio, language=primary_lang)
            if voice_engine.is_self_echo(text):
                print(f"[STT] Ignored acoustic self-echo from speakers: '{text}'")
                return ""
            print(f"You (Voice [{primary_lang}]): {text}")
            return text
        except sr.UnknownValueError:
            # Pass 2: Fallback to Hindi if primary didn't match (handles native Hindi speech)
            if secondary_lang and secondary_lang != primary_lang:
                try:
                    text = recognizer.recognize_google(audio, language=secondary_lang)
                    if text:
                        if voice_engine.is_self_echo(text):
                            print(f"[STT] Ignored acoustic self-echo from speakers: '{text}'")
                            return ""
                        print(f"You (Voice [{secondary_lang}]): {text}")
                        return text
                except sr.UnknownValueError:
                    pass
                except Exception as e:
                    print(f"[STT Secondary Error]: {e}")
            print("[Alfred couldn't understand...]")
            return ""
        except sr.RequestError as e:
            print(f"[STT Error] Google STT network error: {e}")
            if _vosk_available and _vosk_model:
                print("[STT] Falling back to offline Vosk transcription...")
                try:
                    raw_data = audio.get_raw_data(convert_rate=16000, convert_width=2)
                    from vosk import KaldiRecognizer
                    rec = KaldiRecognizer(_vosk_model, 16000)
                    rec.AcceptWaveform(raw_data)
                    result = json.loads(rec.Result())
                    text = result.get("text", "").strip()
                    if text:
                        if voice_engine.is_self_echo(text):
                            print(f"[STT] Ignored acoustic self-echo from speakers: '{text}'")
                            return ""
                        print(f"You (Voice - Offline Fallback): {text}")
                        return text
                except Exception as ex:
                    print(f"[STT] Offline fallback failed: {ex}")
            return ""

