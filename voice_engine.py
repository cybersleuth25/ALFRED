import edge_tts
import asyncio
import tempfile
import os
import re
import sys
import ctypes
import time
import threading
import queue as thread_queue

# Ensure UTF-8 console output on Windows to support Devanagari Hindi characters without crashing
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

print("[Loading Voice Engine (Edge TTS / Kokoro Offline)]")

# ── Voice Configuration ──
# en-GB-RyanNeural: Refined, calm, authoritative British butler voice (classic Alfred)
# en-IN-PrabhatNeural: Modern Indian male voice (optional/custom)
# hi-IN-MadhurNeural: Deep, resonant native Hindi male voice (for pure Devanagari/Hindi speech)
# hi-IN-SwaraNeural: Expressive, warm native Hindi female voice
VOICE = os.getenv("TTS_VOICE", "en-GB-RyanNeural")
RATE = os.getenv("TTS_RATE", "-4%")
PITCH = os.getenv("TTS_PITCH", "-5Hz")

def _resolve_voice_for_text(text: str, base_voice: str) -> str:
    """
    Intelligently select the best neural voice for the given text.
    If text contains Devanagari Hindi characters, switches to a native Hindi neural voice.
    Matches gender of the active voice (female -> Swara, male/neutral -> Madhur).
    """
    has_devanagari = bool(re.search(r'[\u0900-\u097F]', text))
    if not has_devanagari:
        return base_voice

    is_female = any(name in base_voice.lower() for name in ['female', 'neerja', 'emily', 'swara', 'bella', 'friday'])
    hindi_female = os.getenv("TTS_HINDI_VOICE_FEMALE", "hi-IN-SwaraNeural")
    hindi_male = os.getenv("TTS_HINDI_VOICE_MALE", "hi-IN-MadhurNeural")
    return hindi_female if is_female else hindi_male


def set_persona_voice(voice_name: str, rate: str = None, pitch: str = None):
    """Dynamically updates the Edge TTS voice parameters for the active persona."""
    global VOICE, RATE, PITCH, KOKORO_VOICE
    if voice_name:
        VOICE = voice_name
    if rate is not None:
        RATE = rate
    if pitch is not None:
        PITCH = pitch
    # Map Kokoro voices if Kokoro is used
    if any(k in str(voice_name).lower() for k in ['emily', 'friday', 'neerja', 'swara']):
        KOKORO_VOICE = 'af_bella'
    elif any(k in str(voice_name).lower() for k in ['thomas', 'jarvis', 'prabhat', 'madhur']):
        KOKORO_VOICE = 'bm_fable'
    else:
        KOKORO_VOICE = 'bm_george'
    print(f"[Voice Engine] Active voice set to: {VOICE} (rate: {RATE}, pitch: {PITCH})")


# ── Kokoro TTS Configuration ──
KOKORO_AVAILABLE = False
_kokoro_pipeline = None
KOKORO_VOICE = 'bm_george' # British male voice

def _get_kokoro_pipeline():
    global _kokoro_pipeline, KOKORO_AVAILABLE
    if _kokoro_pipeline is not None:
        return _kokoro_pipeline
    try:
        from kokoro import KPipeline
        print("[Voice Engine] Initializing Kokoro Pipeline...")
        _kokoro_pipeline = KPipeline(lang_code='b') # 'b' for British English
        KOKORO_AVAILABLE = True
        return _kokoro_pipeline
    except Exception as e:
        print(f"[Voice Engine] Kokoro init note: {e}")
        KOKORO_AVAILABLE = False
        return None

try:
    import kokoro
    import soundfile as sf
    KOKORO_AVAILABLE = True
except Exception:
    KOKORO_AVAILABLE = False


# ── Audio Cache System ──
AUDIO_CACHE_DIR = os.path.join(os.path.dirname(__file__), "Alfred_Workspace", "audio_cache")
os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)

# ── Interrupt & Pause System ──
_stop_flag = threading.Event()
_pause_flag = threading.Event()
_is_speaking = threading.Event()
_last_spoken_time = 0.0
_last_spoken_text = ""

def _sanitize_for_tts(text: str) -> str:
    """Strip problematic characters for TTS while preserving Latin and Devanagari Hindi characters."""
    # Fix garbled UTF-8 degree symbols and arrows
    text = text.replace("Â°", "°").replace("â", "→")
    # Replace degree symbol with word for clean speech
    text = text.replace("°C", " degrees Celsius").replace("°F", " degrees Fahrenheit").replace("°", " degrees")
    # Strip non-printable control characters, but PRESERVE Devanagari (\u0900-\u097F), Latin, numbers, and punctuation
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    # Strip markdown symbols (*, **, #, `, ~)
    text = re.sub(r'[*#`~_]', '', text)
    # Remove [MOOD: xxx] tags
    text = re.sub(r'\[MOOD:\s*\w+\]', '', text, flags=re.IGNORECASE)
    # Collapse extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

async def _speak_async(text: str):
    """Generate speech using Edge TTS and play it (interruptible)."""
    import re
    chunks = [c.strip() for c in re.split(r'(?<=[.!?\n])\s+', text) if c.strip()]
    if not chunks:
        chunks = [text]
        
    mci = ctypes.windll.winmm.mciSendStringW
    queue = asyncio.Queue()
    
    async def producer():
        import hashlib
        v_key = KOKORO_VOICE if KOKORO_AVAILABLE else VOICE
        text_hash = hashlib.md5(f"{v_key}_{RATE}_{PITCH}_{text}".encode('utf-8')).hexdigest()
        cache_path = os.path.join(AUDIO_CACHE_DIR, text_hash)
        os.makedirs(cache_path, exist_ok=True)
        
        cached_files = sorted([f for f in os.listdir(cache_path) if f.endswith('.wav') or f.endswith('.mp3')])
        if len(cached_files) > 0:
            for f in cached_files:
                if _stop_flag.is_set(): break
                await queue.put(os.path.join(cache_path, f))
            await queue.put(None)
            return

        if KOKORO_AVAILABLE:
            try:
                for i, chunk in enumerate(chunks):
                    if _stop_flag.is_set(): break
                    # Pass the pre-split sentence chunk to Kokoro so it yields audio immediately
                    generator = kokoro_pipeline(chunk, voice=KOKORO_VOICE, speed=0.9)
                    for j, (gs, ps, audio) in enumerate(generator):
                        if _stop_flag.is_set(): break
                        if audio is not None:
                            tmp_path = os.path.join(cache_path, f"{i:03d}_{j:03d}.wav")
                            sf.write(tmp_path, audio, 24000)
                            await queue.put(tmp_path)
                await queue.put(None)
                return
            except Exception as e:
                print(f"[Voice Error] Kokoro failed, falling back to Edge TTS: {e}")

        # Edge TTS (supports Indian English, Hinglish, and Hindi)
        for i, chunk in enumerate(chunks):
            if _stop_flag.is_set(): break
            chunk_voice = _resolve_voice_for_text(chunk, VOICE)
            tmp_path = os.path.join(cache_path, f"{i:03d}.mp3")
            for attempt in range(3):
                try:
                    await edge_tts.Communicate(chunk, chunk_voice, rate=RATE, pitch=PITCH).save(tmp_path)
                    if os.path.exists(tmp_path) and os.path.getsize(tmp_path) >= 100:
                        await queue.put(tmp_path)
                        break
                except Exception as e:
                    if attempt == 2: print(f"[Voice Error] Edge TTS failed on chunk {i} ({chunk_voice}): {e}")
                    await asyncio.sleep(0.2)
        await queue.put(None) # Signal EOF

    async def consumer():
        import ctypes
        from ctypes import wintypes
        _GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
        _GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        _GetShortPathNameW.restype = wintypes.DWORD

        def get_short_path(long_name):
            output_buf_size = 0
            while True:
                output_buf = ctypes.create_unicode_buffer(output_buf_size)
                needed = _GetShortPathNameW(long_name, output_buf, output_buf_size)
                if output_buf_size >= needed:
                    return output_buf.value
                else:
                    output_buf_size = needed

        while True:
            if _stop_flag.is_set(): break
            tmp_path = await queue.get()
            if tmp_path is None: break
            
            short_tmp_path = get_short_path(tmp_path)
            
            mci('close alfred_audio', None, 0, 0)
            audio_type = "waveaudio" if short_tmp_path.lower().endswith(".wav") else "mpegvideo"
            if mci(f'open "{short_tmp_path}" type {audio_type} alias alfred_audio', None, 0, 0) != 0:
                continue
                
            mci('play alfred_audio', None, 0, 0)
            _is_speaking.set()
            
            buf = ctypes.create_unicode_buffer(128)
            while not _stop_flag.is_set():
                # Handle pause: if paused, pause MCI playback and wait
                if _pause_flag.is_set():
                    mci('pause alfred_audio', None, 0, 0)
                    while _pause_flag.is_set() and not _stop_flag.is_set():
                        await asyncio.sleep(0.1)
                    if not _stop_flag.is_set():
                        mci('resume alfred_audio', None, 0, 0)
                
                mci('status alfred_audio mode', buf, 128, 0)
                if buf.value.strip().lower() != 'playing':
                    break
                await asyncio.sleep(0.05)
                
            mci('close alfred_audio', None, 0, 0)
            
    await asyncio.gather(producer(), consumer())
    global _last_spoken_time
    _last_spoken_time = time.time()
    _is_speaking.clear()

def speak(text: str):
    """Generates audio from text using Microsoft Edge Neural TTS with Full-Duplex Barge-In support."""
    try:
        _stop_flag.clear()
        _pause_flag.clear()
        clean_text = _sanitize_for_tts(text)
        global _last_spoken_text
        _last_spoken_text = clean_text
        try:
            print(f"[Voice] Speaking ({VOICE}): {clean_text[:80]}...")
        except Exception:
            print(f"[Voice] Speaking ({VOICE}): [multilingual speech]...")
        
        # Activate full-duplex voice interruption monitor
        try:
            import barge_in_engine
            barge_in_engine.start_monitoring()
        except Exception:
            pass

        asyncio.run(_speak_async(clean_text))
    except Exception as e:
        _is_speaking.clear()
        print(f"[Voice Error]: {e}")
    finally:
        try:
            import barge_in_engine
            barge_in_engine.stop_monitoring()
        except Exception:
            pass


async def synthesize_to_file_async(text: str, output_path: str, voice: str = None) -> str:
    """
    Synthesizes speech directly into an audio file (e.g. mp3/ogg) asynchronously.
    Used for Telegram voice note replies, audio clips, and remote alerts.
    """
    clean_text = _sanitize_for_tts(text)
    if not clean_text:
        clean_text = "Task completed, sir."
    selected_voice = voice or _resolve_voice_for_text(clean_text, VOICE)
    communicate = edge_tts.Communicate(clean_text, selected_voice, rate=RATE, pitch=PITCH)
    await communicate.save(output_path)
    return output_path


def synthesize_to_file(text: str, output_path: str = None, voice: str = None) -> str:
    """Synchronous helper for synthesize_to_file_async."""
    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
    asyncio.run(synthesize_to_file_async(text, output_path, voice))
    return output_path


# ── Streaming TTS: accepts a queue of sentences and speaks them with true overlap ──

def speak_streamed(sentence_queue: thread_queue.Queue, first_chunk: str = None):
    """
    Streaming TTS pipeline: pulls sentences from a thread-safe queue, 
    generates audio for each in real-time, and plays them back with overlap
    between generation and playback. Much faster than calling speak() per sentence.
    
    Args:
        sentence_queue: Queue of sentence strings (None = EOF marker)
        first_chunk: Optional first sentence to speak immediately (already pulled from queue)
    """
    try:
        _stop_flag.clear()
        _pause_flag.clear()
        global _last_spoken_text
        # Track the first chunk immediately so is_self_echo() can detect
        # speaker audio leaking into the mic during streamed LLM responses
        if first_chunk:
            _last_spoken_text = first_chunk
        try:
            import barge_in_engine
            barge_in_engine.start_monitoring()
        except Exception:
            pass
        asyncio.run(_speak_streamed_async(sentence_queue, first_chunk))
    except Exception as e:
        _is_speaking.clear()
        print(f"[Voice Streaming Error]: {e}")
    finally:
        try:
            import barge_in_engine
            barge_in_engine.stop_monitoring()
        except Exception:
            pass


async def _speak_streamed_async(sentence_queue: thread_queue.Queue, first_chunk: str = None):
    """Async streaming pipeline: producer generates audio, consumer plays it — true overlap."""
    import hashlib
    
    mci = ctypes.windll.winmm.mciSendStringW
    audio_queue = asyncio.Queue()  # internal queue of audio file paths
    
    async def producer():
        """Pull sentences from the thread queue, generate TTS, push audio paths."""
        chunk = first_chunk
        chunk_index = 0
        
        while chunk is not None:
            if _stop_flag.is_set():
                break
            
            clean = _sanitize_for_tts(chunk)
            if not clean.strip():
                # Get next sentence
                chunk = await asyncio.to_thread(sentence_queue.get)
                continue
            
            # Resolve voice for this specific chunk (handles Hindi/Devanagari switching mid-stream)
            chunk_voice = _resolve_voice_for_text(clean, VOICE)
            v_key = KOKORO_VOICE if (KOKORO_AVAILABLE and not re.search(r'[\u0900-\u097F]', clean)) else chunk_voice
            text_hash = hashlib.md5(f"{v_key}_{RATE}_{PITCH}_{clean}".encode('utf-8')).hexdigest()
            cache_path = os.path.join(AUDIO_CACHE_DIR, text_hash)
            os.makedirs(cache_path, exist_ok=True)
            
            cached_files = sorted([f for f in os.listdir(cache_path) if f.endswith('.wav') or f.endswith('.mp3')])
            
            if cached_files:
                # Cache hit — push all cached audio files immediately
                for f in cached_files:
                    if _stop_flag.is_set(): break
                    await audio_queue.put(os.path.join(cache_path, f))
            elif KOKORO_AVAILABLE and not re.search(r'[\u0900-\u097F]', clean):
                pipeline = _get_kokoro_pipeline()
                if pipeline is not None:
                    try:
                        import soundfile as sf
                        generator = pipeline(clean, voice=KOKORO_VOICE, speed=0.9)
                        for j, (gs, ps, audio) in enumerate(generator):
                            if _stop_flag.is_set(): break
                            if audio is not None:
                                tmp_path = os.path.join(cache_path, f"000_{j:03d}.wav")
                                sf.write(tmp_path, audio, 24000)
                                await audio_queue.put(tmp_path)
                    except Exception as e:
                        print(f"[Voice Streaming] Kokoro failed on chunk {chunk_index}, trying Edge: {e}")
                        # Fallback to Edge for this chunk
                        tmp_path = os.path.join(cache_path, f"000.mp3")
                        try:
                            await edge_tts.Communicate(clean, chunk_voice, rate=RATE, pitch=PITCH).save(tmp_path)
                            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) >= 100:
                                await audio_queue.put(tmp_path)
                        except Exception as e2:
                            print(f"[Voice Streaming] Edge TTS also failed: {e2}")
                else:
                    # Kokoro not available, fallback to Edge
                    tmp_path = os.path.join(cache_path, f"000.mp3")
                    try:
                        await edge_tts.Communicate(clean, chunk_voice, rate=RATE, pitch=PITCH).save(tmp_path)
                        if os.path.exists(tmp_path) and os.path.getsize(tmp_path) >= 100:
                            await audio_queue.put(tmp_path)
                    except Exception as e2:
                        print(f"[Voice Streaming] Edge TTS failed: {e2}")
            else:
                # Edge TTS
                tmp_path = os.path.join(cache_path, f"000.mp3")
                for attempt in range(3):
                    try:
                        await edge_tts.Communicate(clean, chunk_voice, rate=RATE, pitch=PITCH).save(tmp_path)
                        if os.path.exists(tmp_path) and os.path.getsize(tmp_path) >= 100:
                            await audio_queue.put(tmp_path)
                            break
                    except Exception as e:
                        if attempt == 2: print(f"[Voice Streaming] Edge TTS failed on chunk {chunk_index} ({chunk_voice}): {e}")
                        await asyncio.sleep(0.2)
            
            chunk_index += 1
            # Get next sentence from the thread-safe queue (blocking, wrapped for async)
            chunk = await asyncio.to_thread(sentence_queue.get)
            # Keep _last_spoken_text current so is_self_echo detects the latest sentence
            if chunk is not None:
                global _last_spoken_text
                _last_spoken_text = chunk
        
        await audio_queue.put(None)  # Signal EOF to consumer
    
    async def consumer():
        """Play audio files as they arrive from the producer."""
        from ctypes import wintypes
        _GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
        _GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        _GetShortPathNameW.restype = wintypes.DWORD

        def get_short_path(long_name):
            output_buf_size = 0
            while True:
                output_buf = ctypes.create_unicode_buffer(output_buf_size)
                needed = _GetShortPathNameW(long_name, output_buf, output_buf_size)
                if output_buf_size >= needed:
                    return output_buf.value
                else:
                    output_buf_size = needed

        while True:
            if _stop_flag.is_set(): break
            tmp_path = await audio_queue.get()
            if tmp_path is None: break
            
            short_tmp_path = get_short_path(tmp_path)
            
            mci('close alfred_audio', None, 0, 0)
            audio_type = "waveaudio" if short_tmp_path.lower().endswith(".wav") else "mpegvideo"
            if mci(f'open "{short_tmp_path}" type {audio_type} alias alfred_audio', None, 0, 0) != 0:
                continue
            
            mci('play alfred_audio', None, 0, 0)
            _is_speaking.set()
            
            buf = ctypes.create_unicode_buffer(128)
            while not _stop_flag.is_set():
                # Handle pause
                if _pause_flag.is_set():
                    mci('pause alfred_audio', None, 0, 0)
                    while _pause_flag.is_set() and not _stop_flag.is_set():
                        await asyncio.sleep(0.1)
                    if not _stop_flag.is_set():
                        mci('resume alfred_audio', None, 0, 0)
                
                mci('status alfred_audio mode', buf, 128, 0)
                if buf.value.strip().lower() != 'playing':
                    break
                await asyncio.sleep(0.05)
            
            mci('close alfred_audio', None, 0, 0)
    
    await asyncio.gather(producer(), consumer())
    global _last_spoken_time
    _last_spoken_time = time.time()
    _is_speaking.clear()


def stop_speaking():
    """Immediately stops Alfred mid-sentence."""
    if _is_speaking.is_set():
        _stop_flag.set()

def is_speaking() -> bool:
    """Check if Alfred is currently speaking."""
    return _is_speaking.is_set()

def get_last_spoken_time() -> float:
    """Returns timestamp when speech playback last stopped."""
    return _last_spoken_time

def get_last_spoken_text() -> str:
    """Returns the text Alfred last spoke."""
    return _last_spoken_text

def is_self_echo(text: str) -> bool:
    """
    Determines if an incoming transcribed text matches Alfred's recent speech output.
    Prevents acoustic feedback loops where the microphone hears computer speakers.
    Checks within the last 8 seconds for substring match or high word overlap.
    """
    if not text or not text.strip():
        return False
    # If more than 8 seconds have passed since speech ended, unlikely to be echo
    if time.time() - _last_spoken_time > 8.0:
        return False
    
    clean_in = re.sub(r'[^\w\s]', '', text.lower()).strip()
    clean_spoken = re.sub(r'[^\w\s]', '', _last_spoken_text.lower()).strip()
    
    if not clean_in or not clean_spoken:
        return False
        
    # 1. Exact match or substring containment
    if clean_in in clean_spoken or clean_spoken in clean_in:
        return True
        
    # 2. Word overlap / Jaccard similarity
    words_in = set(clean_in.split())
    words_spoken = set(clean_spoken.split())
    if not words_in:
        return False
        
    overlap = len(words_in.intersection(words_spoken))
    ratio = overlap / len(words_in)
    # If 50%+ of words in user_input were just spoken by Alfred, it is self-echo
    if len(words_in) >= 2 and ratio >= 0.50:
        return True
        
    return False

def pause_speaking():
    """Pause Alfred's speech (can be resumed)."""
    if _is_speaking.is_set() and not _pause_flag.is_set():
        _pause_flag.set()
        print("[Voice] Speech paused.")

def resume_speaking():
    """Resume Alfred's speech after pause."""
    if _pause_flag.is_set():
        _pause_flag.clear()
        print("[Voice] Speech resumed.")

def is_paused() -> bool:
    """Check if Alfred's speech is currently paused."""
    return _pause_flag.is_set()

def toggle_pause():
    """Toggle pause/resume. Returns new paused state."""
    if _pause_flag.is_set():
        resume_speaking()
        return False
    elif _is_speaking.is_set():
        pause_speaking()
        return True
    return False

