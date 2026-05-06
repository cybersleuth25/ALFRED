import os
import time
import threading
import sys
from PIL import ImageGrab

try:
    import imagehash
    import pytesseract
except ImportError:
    pass # Will be handled by the daemon gracefully

# Append the current directory to path so we can import memory_engine
sys.path.append(os.path.dirname(__file__))
import memory_engine

# Windows default Tesseract installation path
try:
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
except Exception:
    pass

class ScreenPipeDaemon:
    def __init__(self, interval_seconds=15):
        self.interval = interval_seconds
        self.running = False
        self.thread = None
        self.last_hash = None
        self.has_warned = False
        
    def _run_loop(self):
        print(f"[ScreenPipe] OCR Daemon started. Taking a screenshot every {self.interval} seconds.")
        while self.running:
            try:
                # Ensure dependencies are available
                if 'pytesseract' not in sys.modules or 'imagehash' not in sys.modules:
                    if not self.has_warned:
                        print("[ScreenPipe] Error: pytesseract or imagehash module missing. Please restart.")
                        self.has_warned = True
                    time.sleep(self.interval)
                    continue

                # 1. Take screenshot
                screenshot = ImageGrab.grab()
                
                # 2. Compute visual hash to detect if screen changed
                current_hash = imagehash.average_hash(screenshot)
                
                # If hash difference is > 5, it means the screen has visibly changed (e.g. scrolled or new window)
                if self.last_hash is None or current_hash - self.last_hash > 5:
                    self.last_hash = current_hash
                    
                    # 3. Extract text using Tesseract CPU OCR
                    try:
                        text = pytesseract.image_to_string(screenshot).strip()
                    except pytesseract.pytesseract.TesseractNotFoundError:
                        if not self.has_warned:
                            print("[ScreenPipe] ERROR: Tesseract is not installed!")
                            print("[ScreenPipe] Please download and install from: https://github.com/UB-Mannheim/tesseract/wiki")
                            self.has_warned = True
                        time.sleep(self.interval)
                        continue
                        
                    # 4. Filter empty or garbage text (needs at least some characters to be useful)
                    if len(text) > 30:
                        # Clean up text (remove excessive newlines)
                        clean_text = " ".join(text.split())
                        # Truncate to a reasonable length to avoid embedding model overload
                        clean_text = clean_text[:2000] 
                        
                        # 5. Store in vector memory silently
                        memory_engine.store_memory(f"Screen content: {clean_text}", category="screen_memory")
                        
            except Exception as e:
                pass # Fail silently so we don't spam the console if the screen is locked
                
            time.sleep(self.interval)

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)

# Singleton instance
daemon = ScreenPipeDaemon(interval_seconds=15)

def start_daemon():
    daemon.start()

def stop_daemon():
    daemon.stop()

if __name__ == "__main__":
    start_daemon()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_daemon()
