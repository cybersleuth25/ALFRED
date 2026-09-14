# Future Upgrades & Research

This document tracks upcoming features, research directions, and major architectural upgrades planned for Alfred.

## ~~1. Emotional TTS Engine~~ ✅ COMPLETED
- **Implemented as**: Chatterbox TTS (Resemble AI) — voice cloning + emotion exaggeration
- **Note**: Miso One (8B) deferred to future (requires ≥12GB CUDA VRAM; current hardware: AMD Radeon 740M)
- **Files**: `voice_engine.py`, `models/voice_reference/`, `.env.example`

## ~~2. Open-Vocabulary Visual Grounding~~ ✅ COMPLETED
- **Implemented as**: YOLO-World (`yolov8s-worldv2.pt`) via `ultralytics`
- **Note**: NVIDIA LocateAnything-3B deferred (requires CUDA GPU)
- **Tools**: `locate_object_in_camera(target)`, `locate_object_on_screen(target)` in `tools/vision_tools.py`
- **Files**: `tools/vision_tools.py`, `tools/core_tools.py`

## ~~3. OSINT Visual Geolocation & Globe Mapping~~ ✅ COMPLETED
- **Implementation**: `get_geo_news(topic)` extracts locations → geocodes via geopy/Nominatim → pushes SSE markers → renders on Three.js wireframe globe
- **Files**: `tools/osint_tools.py`, `shared.py`, `frontend/src/App.tsx`, `frontend/src/components/GeoGlobe.tsx`

## 4. OpenJarvis Community Skills Integration
- **Reference**: [Stanford SAIL OpenJarvis](https://github.com/open-jarvis/OpenJarvis.git)
- **Goal**: Integrate the `agentskills.io` standard into Alfred's tool registry.
- **Why**: Allows Alfred to instantly inherit over 13,700 community-built skills (from the OpenClaw / Hermes Agent ecosystems) without writing them from scratch.
- **Status**: Pending.

## 5. True Presence & Vital Sign Monitoring (WiFi Sensing)
- **Reference**: [ruvnet/RuView](https://github.com/ruvnet/RuView) (WiFi DensePose)
- **Hardware Needed**: 2x ESP32-S3 N16R8 Development Boards.
- **Goal**: Implement passive Wi-Fi CSI sensing to allow Alfred to detect user presence, heart rate, and breathing rate without cameras or microphones.
- **Why**: Enables proactive greetings when entering a room, and allows for Emotional AI Feedback by inferring stress levels from elevated heart/breathing rates, automatically triggering calming routines or UI shifts.
- **Status**: Pending hardware arrival.

## 6. Advanced Protocol Omega Rulesets
- Add "Hardcore" OS Mode (instant termination of distracting apps instead of a 15-second warning).
- Add ambient focus LoFi auto-play via Spotify or YouTube upon activation.

## 7. Automated Daily Boot Sequence
- Auto-engage Protocol Omega based on a predefined schedule (e.g., automatically lock into study mode at 7:00 AM).

## 8. Smart Home Hub (IoT Integration)
- **Goal**: Connect Alfred to local Wi-Fi smart plugs/lights (like Philips Hue or Tuya).
- **Why**: Allow voice commands to dim physical room lights before "Sleep Mode" or "Protocol Omega".

## 9. Roboflow Trackers
- **Goal**: Add Object Persistence to YOLOv8 using `roboflow/trackers` (ByteTrack or BoT-SORT).
- **Why**: To track subjects across frames for robotics, drones, and Smart Mirror facial tracking.
- **Status**: Partially addressed — YOLOv8 person tracking now integrated via Sentry Mode (`vision_engine.py`). ByteTrack/BoT-SORT for multi-object persistence still pending.

## 10. PlayCanvas SuperSplat (3D Gaussian Splatting)
- **Goal**: Use SuperSplat to edit and compress photorealistic 3D scans.
- **Why**: Allowing hyper-realistic 3D holograms in the React-Three-Fiber UI instead of basic particles.

## 11. Multi-Agent RAG Swarm
- **Goal**: Introduce specialized "researcher" agents that can concurrently scrape multiple deep-web and surface-web sources, compile the data, and summarize it into a singular brief.
- **Why**: Currently, Alfred relies on linear OSINT scraping.

## 12. Physical Hardware Integration (Robotics/Drones)
- **Goal**: Connect Alfred to local hardware APIs (e.g., DJI SDK or Arduino serial ports).
- **Why**: Use the Dynamic Skill Engine to allow Alfred to teach himself how to fly a drone or control robotic arms purely via natural language commands.

## 13. Smart Mirror UI Mode (Phase 2)
- **Goal**: Create a secondary, high-contrast, minimalist black-and-white theme for the React Dashboard.
- **Why**: This allows the dashboard to be deployed on a Raspberry Pi behind a two-way mirror, creating a physical "Smart Mirror" that wakes up via facial recognition when the user looks at it.

## 14. Consumer-Hardware LLM Fine-Tuning & Training
- **Reference**: [FareedKhan-dev/train-llm-from-scratch](https://github.com/FareedKhan-dev/train-llm-from-scratch)
- **Goal**: Implement local, consumer-hardware optimized training/fine-tuning routines for custom 1B-3B parameter LLMs.
- **Why**: Allows Alfred to learn and specialize directly from the user's local documents, command logs, and coding files 100% offline.
- **Status**: Planned.

## 15. F.R.I.D.A.Y. & Custom Persona Integration
- **Goal**: Support hot-swappable custom personas (e.g., Tony Stark's FRIDAY, JARVIS, or custom characters).
- **Why**: Dynamically modifies response styling, voice tone/cloning profiles, and dashboard accent colors depending on the selected active assistant.
- **Status**: Planned.

## Completed Upgrades
- **Dockerized Skill Sandbox**: Moved the Dynamic Skill Engine into an isolated Docker container, preventing LLM-generated code from accessing host files.
- **Infinite Desktop Memory (Screen-Pipe OCR)**: Tesseract OCR daemon installed and active. Screen snapshots are parsed and saved to the FAISS vector database.
- **Smart Mirror UI Mode (Phase 1)**: Added voice-activated pure black-and-white minimalist theme for hardware mirror deployments.
