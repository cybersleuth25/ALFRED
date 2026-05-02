# Alfred: Autonomous Local AI Orchestration Engine

Alfred is an advanced, fully offline, multi-agent AI personal assistant built in Python. Designed to run locally on Windows, it uses a multi-agent orchestration architecture powered by an offline LLM (via Ollama) to execute hardware control, semantic memory recall, real-time web scraping (OSINT), and biometric security.

## 🌟 Key Features

*   **Multi-Agent LLM Orchestration:** A Manager Agent delegates tasks dynamically to specialized sub-agents (System, Memory, Browser, OSINT, Communications), executing complex multi-step workflows with strict JSON schemas.
*   **Zero-Latency Voice Architecture:** Custom "fast-path" intent detection bypasses LLM inference for common hardware commands. Features continuous offline wake-word detection (Vosk) and interruptible Text-to-Speech playback.
*   **Dynamic Skill Engine (Self-Upgrading):** Alfred has the ability to write his own Python functions on the fly via LLM and dynamically inject them into his running `ReAct` loop to learn physical skills.
*   **Self-Correcting ReAct Loop:** Intelligent tool error handling. If a tool fails, Alfred automatically injects the stack trace back into his context to self-correct and try a new parameter/approach.
*   **Local Computer Vision Engine:** Offline YOLOv8 object detection runs efficiently by borrowing the background security daemon's camera frame, avoiding hardware contention.
*   **Persistent Semantic Memory (RAG):** Uses vector embeddings (`nomic-embed-text`) and cosine similarity search backed by SQLite to organically recall past conversations, facts, and tasks.
*   **Biometric Security Engine:** Integrates ONNX computer vision models (Yunet for face detection, SFace for face recognition) alongside voice biometrics to monitor system access and enforce screen locking.
*   **Protocol Omega (Productivity Mode):** An automated study mode utilizing background computer vision daemons to track user focus, block distracting applications, and dynamically generate post-session performance briefings.
*   **Deep OS & Hardware Control:** Natively interacts with Windows APIs to control power states (lock, sleep, shutdown), adjust brightness, toggle WiFi/Bluetooth, and manage local media.
*   **Full React Dashboard:** A complete GUI command center built with React, Vite, and Three.js for real-time visualization of Alfred's logs, system telemetry, and OSINT data streams.
*   **Cross-Platform Mobile Link:** Integrated Telegram Bot running concurrently in an `asyncio` event loop for secure, remote hardware control and push notifications.

## ⚙️ Architecture

The system is built entirely on local, offline inference to ensure maximum privacy and zero reliance on cloud LLMs for core logic.
*   **Core LLM:** `qwen2.5-coder:3b` running via Ollama.
*   **Embeddings:** `nomic-embed-text` for semantic vector search.
*   **Speech-to-Text:** Vosk offline models.
*   **Computer Vision:** OpenCV + pre-trained ONNX models.

## 🛠️ Prerequisites

*   **OS:** Windows 10/11
*   **Python:** 3.10+
*   **Ollama:** Must be installed and running locally.
*   A webcam and microphone for biometric security and voice interaction.

## 🚀 Installation & Setup

**1. Clone the repository**
```bash
git clone https://github.com/your-username/alfred.git
cd alfred
```

**2. Setup Virtual Environment**
```bash
python -m venv venv
venv\Scripts\activate
```

**3. Install Dependencies**
*(Note: A `requirements.txt` will need to be generated if not present, primarily requiring `ollama`, `opencv-python`, `psutil`, `python-telegram-bot`, `python-dotenv`, `vosk`, `pyaudio`, etc.)*
```bash
pip install -r requirements.txt
```

**4. Pull Required Local Models**
Make sure Ollama is running, then download the necessary models:
```bash
ollama pull qwen2.5-coder:3b
ollama pull nomic-embed-text
```

**5. Environment Variables**
Create a `.env` file in the root directory (use the provided `.env.example` as a template) and add your keys:
```env
ALFRED_USER_NAME="Your Name"
ALFRED_USER_LOCATION="Your City, Country"

# Optional external integrations
TELEGRAM_BOT_TOKEN="your_bot_token"
TELEGRAM_ALLOWED_USER_ID="your_telegram_id"
GEMINI_API_KEY="your_api_key" # Fallback for vision tasks
```

## 💻 Usage

To start Alfred's background daemons, security monitor, and voice engine:
```bash
python alfred.py
```
*(Alternatively, run the included `start_alfred.bat` script).*

Once running, simply say **"Alfred"** to wake the system.

## 🛡️ Privacy Note
This system was built with privacy as the core philosophy. All conversation history (`alfred_memory.db`), biometric models, and LLM inference run entirely on your local hardware.

---
*Disclaimer: This is a personal project tailored to a specific Windows environment. Some OS-level tools may require modification to run on Linux or macOS.*
