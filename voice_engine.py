import edge_tts
import asyncio
import tempfile
import os
import re
import ctypes
import time
import threading

print("[Loading Voice Engine (Edge TTS - British Butler Neural Voice)]")

# ── Voice Configuration ──
# en-GB-RyanNeural: The most natural British male voice available
# Calm, refined, steady — perfect for a distinguished butler persona
VOICE = "en-GB-RyanNeural"
# Slightly slower for warmth and gravitas, lowered pitch for authority
RATE = "-8%"
PITCH = "-5Hz"

# ── Interrupt System ──
_stop_flag = threading.Event()
_is_speaking = threading.Event()

def _sanitize_for_tts(text: str) -> str:
    """Strip problematic Unicode chars that crash TTS or PowerShell."""
    # Fix garbled UTF-8 degree symbols and arrows
    text = text.replace("Â°", "°").replace("â", "→")
    # Replace degree symbol with word for clean speech
    text = text.replace("°C", " degrees Celsius").replace("°F", " degrees Fahrenheit").replace("°", " degrees")
    # Strip remaining non-ASCII that could break PowerShell
    text = text.encode('ascii', errors='ignore').decode('ascii')
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
        for i, chunk in enumerate(chunks):
            if _stop_flag.is_set(): break
            tmp_path = os.path.join(tempfile.gettempdir(), f"alfred_speech_{i}.mp3")
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
        while True:
            if _stop_flag.is_set(): break
            tmp_path = await queue.get()
            if tmp_path is None: break
            
            mci('close alfred_audio', None, 0, 0)
            if mci(f'open "{tmp_path}" type mpegvideo alias alfred_audio', None, 0, 0) != 0:
                continue
                
            mci('play alfred_audio', None, 0, 0)
            _is_speaking.set()
            
            buf = ctypes.create_unicode_buffer(128)
            while not _stop_flag.is_set():
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
        clean_text = _sanitize_for_tts(text)
        print(f"[Voice] Speaking: {clean_text[:80]}...")
        asyncio.run(_speak_async(clean_text))
    except Exception as e:
        _is_speaking.clear()
        print(f"[Voice Error]: {e}")

def stop_speaking():
    """Immediately stops Alfred mid-sentence."""
    if _is_speaking.is_set():
        _stop_flag.set()

def is_speaking() -> bool:
    """Check if Alfred is currently speaking."""
    return _is_speaking.is_set()
