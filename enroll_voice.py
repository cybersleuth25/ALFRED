import os
import sys
import json
import pyaudio
import time
from vosk import Model, SpkModel, KaldiRecognizer

VOSK_MODEL_PATH = "vosk_model"
VOSK_SPK_MODEL_PATH = "vosk_spk"
OUTPUT_FILE = "authorized_voice.json"

if not os.path.exists(VOSK_MODEL_PATH):
    print(f"Error: {VOSK_MODEL_PATH} not found.")
    sys.exit(1)

if not os.path.exists(VOSK_SPK_MODEL_PATH):
    print(f"Error: {VOSK_SPK_MODEL_PATH} not found.")
    sys.exit(1)

print("Loading Vosk models...")
model = Model(VOSK_MODEL_PATH)
spk_model = SpkModel(VOSK_SPK_MODEL_PATH)
rec = KaldiRecognizer(model, 16000)
rec.SetSpkModel(spk_model)

pa = pyaudio.PyAudio()
stream = pa.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=4000)

print("\n" + "="*50)
print("VOICE ENROLLMENT")
print("="*50)
print("Please read the following phrase clearly and naturally:")
print("\n   'Alfred, I am your authorized user. Please record my voice print.'\n")
print("Recording in 3 seconds...")
time.sleep(3)
print("Recording NOW... Speak!")

vectors = []
for i in range(50): # ~12 seconds max
    data = stream.read(4000, exception_on_overflow=False)
    if rec.AcceptWaveform(data):
        res = json.loads(rec.Result())
        if "spk" in res:
            vectors.append(res["spk"])
            print(f"Captured {len(vectors)} voice frames...")
            if len(vectors) >= 3:
                break

stream.stop_stream()
stream.close()
pa.terminate()

if not vectors:
    # Try getting the final partial/result
    final_res = json.loads(rec.FinalResult())
    if "spk" in final_res:
        vectors.append(final_res["spk"])

if vectors:
    # Average the vectors
    avg_vector = [sum(col) / len(col) for col in zip(*vectors)]
    with open(OUTPUT_FILE, "w") as f:
        json.dump({"voice_vector": avg_vector}, f)
    print(f"\n[Success] Voice vector saved to {OUTPUT_FILE}!")
else:
    print("\n[Error] Could not extract voice vector. Please try again and speak louder.")
