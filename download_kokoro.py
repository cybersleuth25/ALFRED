import os
import urllib.request
import subprocess
import sys

def install_packages():
    print("Installing kokoro and soundfile...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "kokoro", "soundfile"])

def download_models():
    # Kokoro uses huggingface hub to download its models automatically when KPipeline is initialized,
    # so we just need to initialize it once to force the download.
    print("Downloading Kokoro models via KPipeline...")
    try:
        from kokoro import KPipeline
        # 'b' for British English, fitting the Butler persona
        pipeline = KPipeline(lang_code='b') 
        print("Models downloaded successfully!")
    except Exception as e:
        print(f"Error downloading models: {e}")
        print("Please ensure you have espeak-ng installed on your system if requested by Kokoro.")

if __name__ == "__main__":
    print("=== Kokoro TTS Setup ===")
    install_packages()
    download_models()
    print("Setup complete. JARVIS will now use Kokoro for offline TTS.")
