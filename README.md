# 🎩 ALFRED: Autonomous AI Orchestration & Sentry System

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-0078D6.svg?logo=windows&logoColor=white)](https://microsoft.com)
[![React](https://img.shields.io/badge/Frontend-React%2019%20%2B%20Vite%208-61DAFB.svg?logo=react&logoColor=black)](https://react.dev)
[![Three.js](https://img.shields.io/badge/3D%20HUD-Three.js%20%2F%20R3F-black.svg?logo=three.js&logoColor=white)](https://threejs.org)
[![Groq](https://img.shields.io/badge/LLM-Groq%20Llama%203.3%2070B-f55036.svg)](https://groq.com)
[![MediaPipe](https://img.shields.io/badge/Vision-MediaPipe%20%2B%20YOLOv8-0097A7.svg)](https://developers.google.com/mediapipe)

**ALFRED** is a local-first, multi-agent AI personal operating system and sentry command center built for Windows. It couples ultra-low latency cloud LLM reasoning (via Groq) with completely offline neural models for biometric security, computer vision, continuous speech recognition, and 3D air-gesture tracking.

---

## 🌟 Key Highlights

```
                       ┌────────────────────────────────────────┐
                       │           USER INTERACTION             │
                       │   Voice (Vosk)  •  Gestures (MediaPipe) │
                       │   React 19 HUD  •  Telegram Uplink     │
                       └───────────────────┬────────────────────┘
                                           │
                                           ▼
                       ┌────────────────────────────────────────┐
                       │          INTENT & ROUTING CORE         │
                       │   Fast-Path Hardware Direct Execution  │
                       │   Proactive Context & Emotion Engine   │
                       └───────────────────┬────────────────────┘
                                           │
                                           ▼
    ┌──────────────────────────────────────┴──────────────────────────────────────┐
    │                        ALFRED REASONING & SWARM CORE                        │
    │              Manager Agent (Llama 3.3-70B) • Dynamic ReAct Loop             │
    │         Self-Correcting Stack Ingestion • Dynamic Tool/Skill Authoring      │
    └──────┬─────────────────┬──────────────────┬─────────────────┬───────────────┘
           │                 │                  │                 │
           ▼                 ▼                  ▼                 ▼
   ┌───────────────┐ ┌───────────────┐  ┌───────────────┐ ┌───────────────┐
   │ Sentry Engine │ │ Vision & 3D   │  │ Dual Memory   │ │ OS & Swarm    │
   │ • USB Watcher │ │ • Hand Track  │  │ • FAISS RAG   │ │ • Desktop Win │
   │ • Face ID     │ │ • YOLOv8      │  │ • Knowledge   │ │ • OSINT Suite │
   │ • Tripwires   │ │ • PinViz 3D   │  │   Graph DB    │ │ • Scholar PDF │
   └───────────────┘ └───────────────┘  └───────────────┘ └───────────────┘
```

### 🧠 1. Multi-Agent Reasoning & Self-Upgrading ReAct Loop
* **Manager & Swarm Hierarchy:** High-level tasks are broken into dependency-ordered execution graphs executed by specialized sub-agents (`System`, `Memory`, `Browser`, `OSINT`, `Scholar`, `Communications`).
* **Self-Healing Code Execution:** When a tool call or command errors out, Alfred intercepts the raw Python stack trace, injects it back into LLM memory, and self-corrects without crashing.
* **On-the-Fly Dynamic Skills:** Capable of synthesizing novel Python tool modules at runtime, verifying them in an isolated sandbox, and mounting them live into the running engine.

### 🎙️ 2. Zero-Latency Voice Pipeline & Dynamic Personas
* **Offline Continuous STT:** Built on Vosk offline acoustic models with smart wake-word detection and interrupt detection during active speech playback.
* **Neural TTS (Piper & Chatterbox):** Local neural voice generation using Piper (`en_GB-alan`, `en_GB-northern_english_male`) and emotional speech synthesis with customizable voice references.
* **Switchable Personas:** Hot-swap between **Alfred** (loyal, refined butler), **JARVIS** (analytical, futuristic engineer), and **FRIDAY** (tactical, concise) with adaptive emotional tone detection via the Mood Engine.

### 👁️ 3. Computer Vision & Air-Gesture Engine
* **MediaPipe Hand & Face Tracking:** Real-time skeletal landmark detection enabling touchless air gestures (pinch to zoom, swipe to pan, fist to close, peace sign).
* **PinViz 3D Spatial Visualizer:** A Three.js and React Three Fiber 3D photo universe controlled completely via spatial air gestures from your webcam.
* **Local YOLOv8 & SFace Recognition:** Runs real-time object detection and ONNX facial biometrics by multiplexing background camera feeds without hardware contention.

### 🛡️ 4. Sentry Tripwire & Hardware Defense
* **Hardware Insertion Tripwire:** Instant detection and telemetry logging of unknown USB storage insertion, auto-capturing webcam snapshots of whoever plugged it in.
* **Process Anomaly Watcher:** Monitors suspicious background processes, elevated CPU/network spikes, and unauthorized desktop access.
* **Telegram Incident Alerts:** Dispatches security snapshots and incident reports straight to your authorized Telegram handle with remote kill/lock commands.

### 🌐 5. Cyberpunk HUD Command Center (V3)
* **Vite + React 19 + TailwindCSS v4:** High-performance dashboard featuring custom GLSL shader backgrounds and live telemetry streaming.
* **Interactive 3D GeoGlobe:** Three.js globe visualizing OSINT targets, active nodes, weather data, and coordinate mapping.
* **Modular HUD Panels:**
  * **System Panel:** Real-time CPU, RAM, thermal metrics, and network activity.
  * **Sentry Dashboard:** Live tripwire logs, biometric authentication state, and intrusion captures.
  * **Focus Panel (Protocol Omega):** Pomodoro tracking, distraction app blocker, and study analytics.
  * **OSINT Hub:** Integrated Shodan, DuckDuckGo, Wikipedia, and DNS reconnaissance streaming.

### 📚 6. Protocol Omega & Scholar Mentor
* **Automated Study Sessions:** One-command lock-in mode that auto-plays your Spotify Lo-Fi study playlist, triggers dark ambient themes, and enforces distraction blocking.
* **Hardcore App Killer:** Detects and immediately terminates blacklisted distraction apps (games, social media) with optional countdown warnings.
* **Scholar Engine:** Extracts, indexes, and summarizes academic PDFs, research documents, and web briefings into structured markdown notes.

### 💾 7. Dual Memory: Semantic Vector RAG + Knowledge Graph
* **FAISS Vector Search:** Local `sentence-transformers` (`all-MiniLM-L6-v2`) embeddings with SQLite storage for semantic recall of past conversations, preferences, and commands.
* **Knowledge Graph:** Discovers entities and relationships dynamically from user conversations and links them into an associative graph database (`knowledge_graph.py`).

---

## 📁 Project Structure

```
JARVIS/
├── alfred.py                  # Core runtime loop, speech routing & event bus
├── context_engine.py          # Proactive awareness, user state & screen monitoring
├── tripwire_engine.py         # Hardware, USB, face & process anomaly tripwires
├── gesture_engine.py          # MediaPipe hand landmark & gesture recognition
├── vision_engine.py           # YOLOv8 object detection & camera stream daemon
├── persona_engine.py          # Multi-persona switcher (Alfred, Jarvis, Friday)
├── mood_engine.py             # User emotional state classifier
├── memory_engine.py           # FAISS semantic vector memory & SQLite store
├── knowledge_graph.py         # Entity-relation graph extraction & query engine
├── task_orchestrator.py       # Multi-agent planner & hierarchical task runner
├── briefing_engine.py         # Daily morning/evening briefings & agenda compiler
├── study_mentor.py            # Protocol Omega, focus timer & app restriction
├── scholar_engine.py          # Academic paper search & PDF research digest
├── routine_engine.py          # Scheduled automations & background routines
├── telegram_bot.py            # Mobile remote control & incident push uplink
├── models/                    # Local ONNX biometrics, Piper voices & personas
│   ├── personas/              # JSON prompt definitions for Alfred, Jarvis, Friday
│   └── piper/                 # Neural TTS ONNX models and configs
├── tools/                     # Modular tool suite for ReAct execution
│   ├── core_tools.py          # System, web search, memory query tools
│   ├── desktop_tools.py       # Windows automation, volume, power, shortcuts
│   ├── osint_tools.py         # Network scan, WHOIS, DNS & OSINT utilities
│   ├── swarm_engine.py        # Sub-agent coordination & delegation
│   └── vision_tools.py        # Image inspection & scene parsing
├── web/                       # FastAPI / Flask backend serving API & WebSocket
│   └── app.py                 # Core server entrypoint (port 8000)
└── frontend/                  # React 19 + Vite 8 Cyberpunk HUD
    ├── src/
    │   ├── App.tsx            # Main HUD container & WebSocket client
    │   ├── components/
    │   │   ├── GeoGlobe.tsx   # 3D Three.js interactive earth globe
    │   │   ├── SentryDashboard.tsx # Real-time tripwire & security viewer
    │   │   ├── panels/        # System, Focus, OSINT, Weather, Tracker
    │   │   └── PinViz/        # 3D spatial hand-controlled photo universe
    │   └── index.css          # Cyberpunk design system & HUD styles
```

---

## 🛠️ Prerequisites & Hardware

* **Operating System:** Windows 10 / 11 (64-bit)
* **Python:** 3.10 or 3.11
* **Node.js:** 18+ and npm
* **Hardware:**
  * Webcam (required for face unlock, tripwire security & air gestures)
  * Microphone (required for offline voice commands)
* **Groq API Key:** Free tier account at [console.groq.com](https://console.groq.com)

---

## 🚀 Installation & Quickstart

### 1. Clone the Repository
```powershell
git clone https://github.com/cybersleuth25/ALFRED.git
cd ALFRED
```

### 2. Set Up Python Virtual Environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
copy .env.example .env
```

Open `.env` and fill in your keys:
```ini
# Required: LLM Inference
GROQ_API_KEY="gsk_your_groq_api_key_here"

# User Profile
ALFRED_USER_NAME="Your Name"
ALFRED_USER_LOCATION="Your City, Country"

# Optional: Mobile Remote Control
TELEGRAM_BOT_TOKEN="your_bot_token"
TELEGRAM_ALLOWED_USER_ID="your_telegram_id"

# Optional: Spotify Integration
SPOTIFY_CLIENT_ID="your_spotify_client_id"
SPOTIFY_CLIENT_SECRET="your_spotify_client_secret"
SPOTIFY_REFRESH_TOKEN="your_refresh_token"
```

### 4. Enroll Biometrics (Face & Voice)
Run the enrollment utilities once to generate your local security signatures:
```powershell
python enroll_face.py
python enroll_voice.py
```

### 5. Build the Frontend UI
```powershell
cd frontend
npm install
npm run build
cd ..
```

### 6. Verify the Checkout
Run the Python test suite and production frontend build before committing changes:
```powershell
python -m pytest -q
npm --prefix frontend run build
```

---

## 💻 Running Alfred

### Option 1: Full System (Backend + Background Daemons + Voice)
```powershell
python web\app.py
```
* Backend REST & WebSocket server opens at **`http://localhost:8000`**.
* Background daemons (Sentry Tripwire, Context Monitor, Voice Engine) boot automatically.

### Option 2: Live Frontend Development Mode
To hot-reload the React 19 dashboard while developing:
```powershell
# In terminal 1 (Backend):
python web\app.py

# In terminal 2 (Vite Dev Server):
cd frontend
npm run dev
```
Open **`http://localhost:5173`** in your browser.

### Option 3: Silent Windows Boot Launcher
Add a shortcut of [`start_alfred.bat`](file:///c:/VS%20Code/JARVIS/start_alfred.bat) to `shell:startup` for automatic silent boot with Windows.

---

## 🗣️ Common Voice Commands

| Voice Trigger | Action Performed |
| :--- | :--- |
| `"Hey Alfred"` / `"Alfred"` | Wake up and listen for instructions |
| `"Switch persona to Jarvis / Friday"` | Swaps system personality, attitude, and TTS voice |
| `"Engage Protocol Omega"` | Activates focus mode, kills distraction apps, plays Lo-Fi |
| `"What's my status / briefing"` | Runs morning briefing (weather, system telemetry, tasks) |
| `"Lock system / sleep PC"` | Instantly triggers native Windows security lock or sleep |
| `"Open PinViz"` | Launches 3D spatial photo visualizer with webcam gesture control |
| `"Who is at my desk?"` | Runs face detection and reports present individuals |
| `"What's on my calendar / schedule?"` | Reads today's meetings and events synced from Google & Samsung Calendar |
| `"Schedule a meeting [title] at [time]"` | Schedules a new event on Google Calendar (syncs down to your phone) |
| `"Research [topic]"` | Delegates to Scholar & OSINT sub-agents to generate a briefing |

---

## 🛡️ Privacy & Local-First Philosophy

* **Sensory Isolation:** Audio streams, video frames, and webcam feeds **never leave your device**.
* **Local Biometrics:** Facial embeddings (`SFace`), hand tracking (`MediaPipe`), and voice models (`Vosk`) run strictly in offline memory.
* **Air-Gapped Memory:** SQLite databases (`alfred_memory.db`), personal journals, and knowledge graphs reside on your physical SSD.
* **Cloud Calls (HTTPS):** Text prompts go to Groq for reasoning. Features that analyze images — Screen Co-Pilot, Telegram photo analysis, the geospatial tracker and dynamic skill authoring — send data to Google Gemini when `GEMINI_API_KEY` is set. Leave it empty to keep images on-device.
* **Locked-Down Local API:** The backend only answers to `localhost`/`127.0.0.1`, and every state-changing request needs a per-launch session token, so other websites can't drive Alfred.
* **Human-in-the-Loop for Risky Tools:** Terminal commands, file deletion, git commits, shutdown, WhatsApp messages, memory wipes and new skills wait for you to say **"confirm"** (or "cancel") before running.

---

## 📄 License
This project is licensed under the [MIT License](file:///c:/VS%20Code/JARVIS/LICENSE).
