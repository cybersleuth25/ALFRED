# Voice Reference Directory

Place a **5-15 second `.wav` file** here to enable zero-shot voice cloning with Chatterbox TTS.

## How to use

1. Record or obtain a clean audio clip of the desired voice (5-15 seconds, no background noise)
2. Save it as a `.wav` file in this directory (e.g., `alfred_voice.wav`)
3. Set the environment variable in `.env`:
   ```
   CHATTERBOX_VOICE_REF=models/voice_reference/alfred_voice.wav
   ```
4. Restart Alfred — Chatterbox will clone the voice from your reference

## Tips for best results

- Use **high-quality audio** (44.1kHz or higher, 16-bit)
- Keep the clip **clean** — no music, echoes, or background chatter
- A natural speaking style works better than reading robotically
- 10-15 seconds is the sweet spot for quality vs. brevity

## Without a reference

If no voice reference is set (`CHATTERBOX_VOICE_REF=""`), Chatterbox uses its default voice, which is already natural and expressive.
