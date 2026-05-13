import edge_tts
import asyncio
import tempfile
import os
import re
import ctypes
import time
import threading
import queue as thread_queue

print("[Loading Voice Engine (Edge TTS / Kokoro Offline)]")

# ── Voice Configuration ──
# en-GB-RyanNeural: The most natural British male voice available
VOICE = "en-GB-RyanNeural"
RATE = "-8%"
PITCH = "-5Hz"

# ── Kokoro TTS Configuration ──
KOKORO_AVAILABLE = False
try:
    from kokoro import KPipeline
    import soundfile as sf
    KOKORO_AVAILABLE = True
    print("[Voice Engine] Kokoro Offline TTS detected. Initializing Pipeline...")
    kokoro_pipeline = KPipeline(lang_code='b') # 'b' for British English
    KOKORO_VOICE = 'bm_george' # British male voice
except ImportError:
    pass

# ── Audio Cache System ──
AUDIO_CACHE_DIR = os.path.join(os.path.dirname(__file__), "Alfred_Workspace", "audio_cache")
os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)

# ── Interrupt & Pause System ──
_stop_flag = threading.Event()
_pause_flag = threading.Event()
_is_speaking = threading.Event()

def _sanitize_for_tts(text: str) -> str:
    """Strip problematic Unicode chars that crash TTS or PowerShell."""
    # Fix garbled UTF-8 degree symbols and arrows
    text = text.replace("Â°", "°").replace("â", "→")
    # Replace degree symbol with word for clean speech
    text = text.replace("°C", " degrees Celsius").replace("°F", " degrees Fahrenheit").replace("°", " degrees")
    # Strip remaining non-ASCII that could break PowerShell
    text = text.encode('ascii', errors='ignore').decode('ascii')
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
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
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

        # Fallback to Edge TTS
        for i, chunk in enumerate(chunks):
            if _stop_flag.is_set(): break
            tmp_path = os.path.join(cache_path, f"{i:03d}.mp3")
            for attempt in range(3):
                try:
                    await edge_tts.Communicate(chunk, VOICE, rate=RATE, pitch=PITCH).save(tmp_path)
                    if os.path.exists(tmp_path) and os.path.getsize(tmp_path) >= 100:
                        await queue.put(tmp_path)
                        break
                except Exception as e:
                    if attempt == 2: print(f"[Voice Error] Edge TTS failed on chunk {i}: {e}")
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
    _is_speaking.clear()

def speak(text: str):
    """Generates audio from text using Microsoft Edge Neural TTS."""
    try:
        _stop_flag.clear()
        _pause_flag.clear()
        clean_text = _sanitize_for_tts(text)
        print(f"[Voice] Speaking: {clean_text[:80]}...")
        asyncio.run(_speak_async(clean_text))
    except Exception as e:
        _is_speaking.clear()
        print(f"[Voice Error]: {e}")


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
        asyncio.run(_speak_streamed_async(sentence_queue, first_chunk))
    except Exception as e:
        _is_speaking.clear()
        print(f"[Voice Streaming Error]: {e}")


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
            
            # Generate audio for this sentence
            text_hash = hashlib.md5(clean.encode('utf-8')).hexdigest()
            cache_path = os.path.join(AUDIO_CACHE_DIR, text_hash)
            os.makedirs(cache_path, exist_ok=True)
            
            cached_files = sorted([f for f in os.listdir(cache_path) if f.endswith('.wav') or f.endswith('.mp3')])
            
            if cached_files:
                # Cache hit — push all cached audio files immediately
                for f in cached_files:
                    if _stop_flag.is_set(): break
                    await audio_queue.put(os.path.join(cache_path, f))
            elif KOKORO_AVAILABLE:
                try:
                    generator = kokoro_pipeline(clean, voice=KOKORO_VOICE, speed=0.9)
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
                        await edge_tts.Communicate(clean, VOICE, rate=RATE, pitch=PITCH).save(tmp_path)
                        if os.path.exists(tmp_path) and os.path.getsize(tmp_path) >= 100:
                            await audio_queue.put(tmp_path)
                    except Exception as e2:
                        print(f"[Voice Streaming] Edge TTS also failed: {e2}")
            else:
                # Edge TTS only
                tmp_path = os.path.join(cache_path, f"000.mp3")
                for attempt in range(3):
                    try:
                        await edge_tts.Communicate(clean, VOICE, rate=RATE, pitch=PITCH).save(tmp_path)
                        if os.path.exists(tmp_path) and os.path.getsize(tmp_path) >= 100:
                            await audio_queue.put(tmp_path)
                            break
                    except Exception as e:
                        if attempt == 2: print(f"[Voice Streaming] Edge TTS failed on chunk {chunk_index}: {e}")
                        await asyncio.sleep(0.2)
            
            chunk_index += 1
            # Get next sentence from the thread-safe queue (blocking, wrapped for async)
            chunk = await asyncio.to_thread(sentence_queue.get)
        
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
    _is_speaking.clear()


def stop_speaking():
    """Immediately stops Alfred mid-sentence."""
    if _is_speaking.is_set():
        _stop_flag.set()

def is_speaking() -> bool:
    """Check if Alfred is currently speaking."""
    return _is_speaking.is_set()

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
