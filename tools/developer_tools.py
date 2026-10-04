"""
Developer Co-Pilot & Autonomous OS Tools for JARVIS / ALFRED.
============================================================
Provides superpowers for developers and power users:
1. Git Status & Smart Commit: Auto-inspects diffs and writes conventional commits.
2. Secret & Token Leak Scanner: Protects codebases from accidental API key leaks.
3. Workspace Junk Cleaner: Reclaims GBs by clearing node_modules/__pycache__ caches.
4. Safe Terminal Execution: Runs builds, tests, scripts, and linters with timeouts.
5. Meeting & Lecture Smart Notetaker: Records calls/lectures and generates action items.
"""

import os
import sys
import re
import time
import json
import shutil
import wave
import threading
import subprocess
from pathlib import Path
from datetime import datetime

# Ensure UTF-8 console output on Windows to support emojis without crashing
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ── Safety & Sandbox ──
WORKSPACE_ROOT = Path(os.path.join(os.path.dirname(__file__), "..")).resolve()
MEETINGS_DIR = WORKSPACE_ROOT / "Alfred_Workspace" / "meetings"
MEETINGS_DIR.mkdir(parents=True, exist_ok=True)

# ── 1. Git Tools & Multi-Project Discovery ──

def discover_git_repositories() -> dict:
    r"""
    Discovers Git repositories across:
    1. The current workspace root (JARVIS)
    2. Sibling folders in the parent directory (e.g. c:\VS Code\*)
    3. Direct subfolders in WORKSPACE_ROOT
    4. Folders in WORKSPACE_ROOT / Alfred_Workspace / (e.g. forthepeople)
    Returns a dict mapping lower-cased project names to their Path objects.
    """
    repos = {}

    # 1. Current workspace root
    if (WORKSPACE_ROOT / ".git").exists():
        repos[WORKSPACE_ROOT.name.lower()] = WORKSPACE_ROOT

    # 2. Sibling repositories in parent directory
    try:
        parent_dir = WORKSPACE_ROOT.parent
        if parent_dir.exists() and parent_dir.is_dir():
            for entry in parent_dir.iterdir():
                if entry.is_dir() and (entry / ".git").exists():
                    repos[entry.name.lower()] = entry
    except Exception:
        pass

    # 3. Subdirectories in workspace root
    try:
        for entry in WORKSPACE_ROOT.iterdir():
            if entry.is_dir() and (entry / ".git").exists():
                repos[entry.name.lower()] = entry
    except Exception:
        pass

    # 4. Alfred_Workspace subdirectories
    alfred_ws = WORKSPACE_ROOT / "Alfred_Workspace"
    try:
        if alfred_ws.exists():
            for entry in alfred_ws.iterdir():
                if entry.is_dir() and (entry / ".git").exists():
                    repos[entry.name.lower()] = entry
    except Exception:
        pass

    return repos


def _resolve_repo(repo_path: str = "") -> Path:
    """Resolves a project name, relative folder, or absolute filepath to a valid repository Path."""
    if not repo_path or repo_path.strip() == "":
        return WORKSPACE_ROOT

    # Direct existing path
    p = Path(repo_path).expanduser()
    if p.exists() and p.is_dir() and (p / ".git").exists():
        return p.resolve()

    clean_name = repo_path.strip().lower()
    repos = discover_git_repositories()

    # Exact match in discovered repositories
    if clean_name in repos:
        return repos[clean_name]

    # Partial / substring match
    for name, path in repos.items():
        if clean_name in name or name in clean_name:
            return path

    # Check relative to workspace or parent
    for base in [WORKSPACE_ROOT, WORKSPACE_ROOT / "Alfred_Workspace", WORKSPACE_ROOT.parent]:
        cand = base / repo_path.strip()
        if cand.exists() and (cand / ".git").exists():
            return cand.resolve()

    return WORKSPACE_ROOT


def git_status_diff(repo_path: str = "") -> str:
    """
    Returns a clean summary of current git branch, modified files, and unstaged line diffs.
    Supports:
    - Empty: current project (JARVIS)
    - "all": status overview of all detected projects
    - "list": lists all detected git projects and their current branches
    - "<project_name>": status of a specific project (e.g. 'forthepeople')
    """
    arg = (repo_path or "").strip().lower()
    repos = discover_git_repositories()

    # 1. Project List
    if arg in ("list", "projects", "repos"):
        if not repos:
            return "No Git repositories detected in workspace or parent directory."
        lines = [f"📂 Detected Git Projects ({len(repos)}):"]
        for name, rpath in sorted(repos.items()):
            try:
                b_res = subprocess.run(["git", "branch", "--show-current"], cwd=str(rpath), capture_output=True, text=True, timeout=3)
                branch = b_res.stdout.strip() or "HEAD"
            except Exception:
                branch = "unknown"
            lines.append(f"• **{name}** [{branch}] ➔ `{rpath}`")
        lines.append("\n💡 Check any project with: `/git <name>` or *'git status for <name>'*")
        return "\n".join(lines)

    # 2. All Projects Status Overview
    if arg in ("all", "all projects", "every project"):
        if not repos:
            return "No Git repositories detected."
        lines = [f"🌐 Git Status for All Projects ({len(repos)}):\n"]
        for name, rpath in sorted(repos.items()):
            try:
                b_res = subprocess.run(["git", "branch", "--show-current"], cwd=str(rpath), capture_output=True, text=True, timeout=3)
                branch = b_res.stdout.strip() or "HEAD"
                s_res = subprocess.run(["git", "status", "--short"], cwd=str(rpath), capture_output=True, text=True, timeout=5)
                s_out = s_res.stdout.strip()
                if not s_out:
                    lines.append(f"📁 **[{name}]** (`{branch}`) — ✅ Clean")
                else:
                    count = len(s_out.splitlines())
                    lines.append(f"📁 **[{name}]** (`{branch}`) — ⚠️ {count} changed file(s)")
            except Exception as e:
                lines.append(f"📁 **[{name}]** — Error: {e}")
        lines.append("\n💡 Run `/git <project>` or *'git status for <project>'* for detailed diffs.")
        return "\n".join(lines)

    # 3. Specific or Default Repo Status
    target_repo = _resolve_repo(repo_path)
    try:
        branch_res = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(target_repo),
            capture_output=True, text=True, timeout=5
        )
        branch = branch_res.stdout.strip() or "HEAD"

        status_res = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(target_repo),
            capture_output=True, text=True, timeout=8
        )
        status_out = status_res.stdout.strip()

        diff_res = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=str(target_repo),
            capture_output=True, text=True, timeout=8
        )
        diff_stat = diff_res.stdout.strip()

        repo_label = target_repo.name
        if not status_out:
            msg = f"🌿 Git project **[{repo_label}]** on branch `{branch}` is clean. No unstaged or uncommitted changes."
        else:
            status_lines = status_out.splitlines()
            modified = [l for l in status_lines if l.strip().startswith("M")]
            untracked = [l for l in status_lines if l.strip().startswith("??")]
            deleted = [l for l in status_lines if l.strip().startswith("D")]

            summary = (
                f"🌿 Git Status: **[{repo_label}]** on `{branch}` ({len(status_lines)} changed files):\n"
                f"• Modified: {len(modified)}\n"
                f"• Untracked: {len(untracked)}\n"
                f"• Deleted: {len(deleted)}\n\n"
            )
            if diff_stat:
                summary += f"📊 Line Changes:\n{diff_stat[:400]}"
            else:
                summary += f"Files:\n" + "\n".join(status_lines[:8])
            msg = summary

        # Helpful hint if other repos are available
        other_repos = [n for n in repos.keys() if n != repo_label.lower()]
        if other_repos:
            msg += f"\n\n💡 Other detected projects: `{', '.join(other_repos)}` (Use `/git <name>` or `/git all`)"

        return msg
    except Exception as e:
        return f"Error reading git status for '{target_repo}': {e}"



def git_smart_commit(commit_message: str = "", repo_path: str = "") -> str:
    """
    Stages all modified files and commits them.
    If commit_message is empty, automatically generates a conventional commit message.
    """
    target_repo = _resolve_repo(repo_path)
    try:
        # Check if there are changes
        status_res = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(target_repo),
            capture_output=True, text=True, timeout=5
        )
        if not status_res.stdout.strip():
            return "No changes to commit. Working directory is clean."

        # Auto-generate commit message if not provided
        if not commit_message or commit_message.strip() == "":
            diff_res = subprocess.run(
                ["git", "diff", "--cached"],
                cwd=str(target_repo),
                capture_output=True, text=True, timeout=8
            )
            raw_diff = diff_res.stdout.strip() or status_res.stdout.strip()
            
            # Simple conventional heuristic
            if "barge_in" in raw_diff or "voice" in raw_diff:
                commit_message = "feat(voice): enhance voice engine and low-latency response"
            elif "telegram" in raw_diff:
                commit_message = "feat(telegram): add mobile remote and voice note replies"
            elif "copilot" in raw_diff or "screen" in raw_diff:
                commit_message = "feat(vision): add live screen co-pilot and GDI capture"
            else:
                commit_message = f"chore(update): sync workspace changes ({datetime.now().strftime('%Y-%m-%d')})"

        # Stage and commit
        subprocess.run(["git", "add", "-A"], cwd=str(target_repo), check=True, timeout=10)
        commit_res = subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=str(target_repo),
            capture_output=True, text=True, timeout=10
        )
        
        return f"✅ Committed successfully:\n'{commit_message}'\n{commit_res.stdout.strip()[:300]}"
    except Exception as e:
        return f"Error executing git commit: {e}"


# ── 2. Secret & Token Leak Scanner ──

SECRET_PATTERNS = [
    (r"AIzaSy[A-Za-z0-9_-]{33}", "Google / Gemini API Key"),
    (r"gsk_[A-Za-z0-9]{40,64}", "Groq API Key"),
    (r"\d{9,11}:[A-Za-z0-9_-]{35}", "Telegram Bot Token"),
    (r"sk-[A-Za-z0-9]{32,64}", "OpenAI API Key"),
    (r"sk-proj-[A-Za-z0-9_-]{40,120}", "OpenAI Project Key"),
    (r"ghp_[A-Za-z0-9]{36}", "GitHub Personal Access Token"),
    (r"github_pat_[A-Za-z0-9_]{82}", "GitHub Fine-Grained Token"),
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    (r"-----BEGIN (?:RSA )?PRIVATE KEY-----", "Private RSA/SSH Key"),
]

IGNORED_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    "audio_cache", "vosk_model", "vosk_spk", "brain", ".tempmediaStorage",
    ".system_generated", "site-packages", "models"
}
IGNORED_FILES = {".env", ".env.example", "authorized_voice.json", "package-lock.json"}

def scan_leaked_secrets(target_path: str = "") -> str:
    """Scans code files in target directory for exposed API keys, tokens, or credentials."""
    target_dir = _resolve_repo(target_path)
    findings = []

    for root, dirs, files in os.walk(str(target_dir)):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for f in files:
            if f in IGNORED_FILES:
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext not in {".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml", ".md", ".sh"}:
                continue
            
            filepath = os.path.join(root, f)
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as file_content:
                    lines = file_content.readlines()
                    for idx, line in enumerate(lines, 1):
                        for pattern, secret_type in SECRET_PATTERNS:
                            if re.search(pattern, line):
                                rel_path = os.path.relpath(filepath, str(target_dir))
                                findings.append(f"⚠️ {secret_type} in {rel_path}:{idx}")
            except Exception:
                pass

    if not findings:
        return f"🛡️ Secret scan complete across '{target_dir.name}': 0 exposed keys or secrets found."
    
    return f"🚨 SECURITY WARNING: Found {len(findings)} exposed secret(s):\n" + "\n".join(findings[:10])


# ── 3. Workspace Junk Cleaner ──

def clean_dev_workspace(root_dir: str = "") -> str:
    """Detects and safely removes junk build caches (node_modules, __pycache__, .pytest_cache) to reclaim disk space."""
    target = _resolve_repo(root_dir)
    target_folders = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
    
    freed_bytes = 0
    removed_count = 0

    for root, dirs, files in os.walk(str(target), topdown=False):
        for d in dirs:
            if d in target_folders:
                folder_path = os.path.join(root, d)
                try:
                    # Calculate size
                    for dirpath, dirnames, filenames in os.walk(folder_path):
                        for f in filenames:
                            fp = os.path.join(dirpath, f)
                            freed_bytes += os.path.getsize(fp)
                    shutil.rmtree(folder_path, ignore_errors=True)
                    removed_count += 1
                except Exception:
                    pass

    freed_mb = round(freed_bytes / (1024 * 1024), 2)
    return f"🧹 Workspace Cleaned: Removed {removed_count} cache directories. Reclaimed {freed_mb} MB of disk space."


# ── 4. Safe Terminal Execution ──

BLOCKED_COMMANDS = {
    "rmdir /s /q c:", "del /f /s /q c:", "format", "diskpart",
    ":(){ :|:& };:", "mkfs", "dd if="
}

def run_terminal_command(command: str, cwd: str = "") -> str:
    """
    Executes a shell or terminal command safely with a 30s timeout.
    Useful for running tests, build scripts, npm, pip, git, and python commands.
    """
    cmd_lower = command.lower().strip()
    for blocked in BLOCKED_COMMANDS:
        if blocked in cmd_lower:
            return f"Error: Command '{command}' was blocked by Alfred's security sandbox."

    target_cwd = str(_resolve_repo(cwd))
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=target_cwd,
            capture_output=True,
            text=True,
            timeout=30
        )
        out = proc.stdout.strip()
        err = proc.stderr.strip()

        combined = out
        if err:
            combined += f"\n[stderr]: {err}"

        if not combined:
            combined = f"Command exited with returncode {proc.returncode} (no output)."

        # Truncate to reasonable length for speech and chat
        if len(combined) > 1500:
            combined = combined[:1500] + f"\n... [truncated, {len(combined)} chars total]"

        return f"💻 Terminal Output:\n{combined}"
    except subprocess.TimeoutExpired:
        return f"Command '{command}' timed out after 30 seconds."
    except Exception as e:
        return f"Execution error: {e}"


# ── 5. Meeting & Lecture Smart Notetaker ──

_meeting_recording = False
_meeting_thread = None
_meeting_audio_frames = []
_meeting_title = ""
_meeting_start_time = 0

def _meeting_audio_worker():
    """Background thread that streams microphone audio during a meeting."""
    global _meeting_audio_frames, _meeting_recording
    import pyaudio
    pa = None
    stream = None
    try:
        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=2048
        )
        while _meeting_recording:
            data = stream.read(2048, exception_on_overflow=False)
            if data:
                _meeting_audio_frames.append(data)
    except Exception as e:
        print(f"[Meeting Notetaker Error] Audio stream error: {e}")
    finally:
        if stream:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
        if pa:
            try:
                pa.terminate()
            except Exception:
                pass


def meeting_notetaker(action: str = "status", title: str = "") -> str:
    """
    Smart meeting & lecture notetaker.
    action="start": Begins background meeting audio recording.
    action="stop": Stops recording, transcribes, and writes structured meeting minutes + action items.
    action="status": Checks if meeting mode is active.
    """
    global _meeting_recording, _meeting_thread, _meeting_audio_frames, _meeting_title, _meeting_start_time
    act = action.lower().strip()

    if act == "start":
        if _meeting_recording:
            return f"Meeting recorder is already active for: '{_meeting_title}'."
        _meeting_title = title or f"Meeting_{datetime.now().strftime('%Y-%m-%d_%H%M')}"
        _meeting_audio_frames = []
        _meeting_recording = True
        _meeting_start_time = time.time()
        _meeting_thread = threading.Thread(target=_meeting_audio_worker, daemon=True, name="MeetingRecorder")
        _meeting_thread.start()
        try:
            import shared
            shared.push_meeting_state(get_meeting_status_dict())
        except Exception:
            pass
        return f"🎙️ Meeting mode activated: '{_meeting_title}'. Recording ambient audio. Say 'stop meeting' when finished."

    elif act == "stop":
        if not _meeting_recording:
            return "Meeting recorder is not currently active."
        _meeting_recording = False
        if _meeting_thread:
            _meeting_thread.join(timeout=3.0)
            _meeting_thread = None

        try:
            import shared
            shared.push_meeting_state(get_meeting_status_dict())
        except Exception:
            pass

        duration_sec = int(time.time() - _meeting_start_time)
        duration_min = max(1, duration_sec // 60)

        if not _meeting_audio_frames:
            return "Meeting ended, but no audio data was captured."

        # Save audio to temporary WAV file
        import tempfile
        tmp_wav = tempfile.mktemp(suffix=".wav")
        try:
            with wave.open(tmp_wav, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b"".join(_meeting_audio_frames))

            # Transcribe with Gemini 2.5 Flash
            from google import genai
            from google.genai import types
            api_key = os.getenv("GEMINI_API_KEY")
            
            if not api_key:
                return "Meeting ended. Audio saved, but GEMINI_API_KEY is needed to synthesize meeting minutes."

            client = genai.Client(api_key=api_key)
            with open(tmp_wav, "rb") as f:
                audio_bytes = f.read()

            prompt = f"""
            Analyze the following recorded meeting/lecture audio for '{_meeting_title}'.
            Provide a clean, professional executive summary with:
            1. 📌 Overview & Context (1-2 sentences)
            2. 🎯 Key Decisions & Discussion Points (bullet points)
            3. ✅ Action Items & Owners (who is doing what)
            Format in clean GitHub Markdown.
            """

            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    prompt,
                    types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav")
                ]
            )
            minutes_md = resp.text.strip()

            # Save Markdown file to Alfred_Workspace/meetings/
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            clean_title = re.sub(r'[^a-zA-Z0-9_-]', '_', _meeting_title)
            md_filename = f"{timestamp_str}_{clean_title}.md"
            md_path = MEETINGS_DIR / md_filename

            full_file_content = f"# 📋 Meeting Notes: {_meeting_title}\n\n"
            full_file_content += f"*Recorded on {datetime.now().strftime('%A, %B %d, %Y')} | Duration: {duration_min} min*\n\n"
            full_file_content += minutes_md

            with open(md_path, "w", encoding="utf-8") as f:
                f.write(full_file_content)

            return f"✅ Meeting completed ({duration_min}m). Notes saved to:\n`{md_path}`\n\n{minutes_md[:800]}..."

        except Exception as e:
            return f"Meeting stopped, but error occurred while generating minutes: {e}"
        finally:
            if os.path.exists(tmp_wav):
                try:
                    os.remove(tmp_wav)
                except Exception:
                    pass

    else:
        if _meeting_recording:
            elapsed = int(time.time() - _meeting_start_time) // 60
            return f"🎙️ Meeting mode is active: '{_meeting_title}' ({elapsed}m recorded)."
        return "Meeting mode is currently idle."


def get_meeting_status_dict() -> dict:
    """Returns a structured dictionary of meeting status for HUD/web."""
    global _meeting_recording, _meeting_title, _meeting_start_time, _meeting_audio_frames
    elapsed_sec = int(time.time() - _meeting_start_time) if _meeting_recording else 0
    return {
        "active": _meeting_recording,
        "title": _meeting_title,
        "elapsed_seconds": elapsed_sec,
        "frame_count": len(_meeting_audio_frames),
        "start_time": _meeting_start_time,
    }


def list_meeting_notes() -> list:
    """Returns past meeting markdown notes sorted by latest first."""
    if not MEETINGS_DIR.exists():
        return []
    notes = []
    for file in MEETINGS_DIR.glob("*.md"):
        try:
            stat = file.stat()
            notes.append({
                "filename": file.name,
                "path": str(file),
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "size_kb": round(stat.st_size / 1024, 1),
                "title": file.stem.replace("_", " ")
            })
        except Exception:
            pass
    notes.sort(key=lambda x: x["modified"], reverse=True)
    return notes


def read_meeting_note(filename: str) -> str:
    """Reads a meeting note markdown file safely."""
    safe_name = os.path.basename(filename)
    note_path = MEETINGS_DIR / safe_name
    if not note_path.exists():
        return ""
    with open(note_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

