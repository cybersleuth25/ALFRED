import { useEffect, useState, useRef } from 'react';
import TacticalCore from './components/TacticalCore';
import SentryDashboard, { type TrackedSubject } from './components/SentryDashboard';
import ResearchViewer from './components/panels/ResearchViewer';
import FocusPanel from './components/panels/FocusPanel';
import MeetingNotetaker from './components/panels/MeetingNotetaker';
import './index.css';

type AppState = "idle" | "listening" | "processing" | "speaking";
type ViewMode = "cockpit" | "sentry" | "study" | "notetaker" | "archive";

interface TranscriptLine {
  author: string;
  text: string;
  id: number;
  time: string;
}

interface PersonaState {
  name: string;
  display_name: string;
  color: string;
  secondary_color?: string;
}

interface NowPlayingData {
  song: string;
  artist: string;
  playing: boolean;
}

interface FocusState {
  active: boolean;
  phase: string;
  remaining: number;
  cycle: number;
  distractions: number;
  session_id: number | null;
  session_start: number;
  daily_goal: number;
  daily_progress: number;
  streak: number;
}

interface SentryState {
  active: boolean;
  threat_level: string;
  threat_score: number;
  persons: number;
  hidden: boolean;
  gesture: string;
  emotion: string;
  face_x?: number;
  face_y?: number;
  unseen_incidents?: string[];
  tracked_subjects?: TrackedSubject[];
}

interface AcousticStatus {
  active?: boolean;
  ambient_rms?: number;
  min_rms_threshold?: number;
}

interface ScreenAnalysis {
  success?: boolean;
  analysis?: string;
  window?: { title: string; process: string };
}

interface DebriefMetrics {
  focus_minutes?: number;
  study_streak_days?: number;
  completed_tasks?: unknown[];
  security_incidents_count?: number;
}

interface DebriefData {
  success?: boolean;
  spoken_text?: string;
  metrics?: DebriefMetrics;
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Unknown error';
}

export function App() {
  const [orbState, setOrbState] = useState<AppState>("idle");
  const [activeView, setActiveView] = useState<ViewMode>("cockpit");
  const [alfredStopped, setAlfredStopped] = useState(false);
  const [connected, setConnected] = useState(false);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [transcript, setTranscript] = useState<TranscriptLine[]>([]);
  const [nowPlaying, setNowPlaying] = useState<NowPlayingData | null>(null);
  const [focusState, setFocusState] = useState<FocusState | null>(null);
  const [sentry, setSentry] = useState<SentryState | null>(null);
  const [meetingState, setMeetingState] = useState<{ active: boolean; elapsed_seconds: number; title: string }>({
    active: false,
    elapsed_seconds: 0,
    title: ''
  });

  // Persona State
  const [persona, setPersona] = useState<PersonaState>({
    name: "jarvis",
    display_name: "J.A.R.V.I.S.",
    color: "#00e5ff",
    secondary_color: "#0284c7"
  });

  // Acoustic & Screen Co-Pilot telemetry
  const [acousticActive, setAcousticActive] = useState(false);
  const [acousticStatus, setAcousticStatus] = useState<AcousticStatus | null>(null);
  const [screenAnalysis, setScreenAnalysis] = useState<ScreenAnalysis | null>(null);
  const [screenLoading, setScreenLoading] = useState(false);
  const [screenModalOpen, setScreenModalOpen] = useState(false);

  // Debrief Modal
  const [debriefModalOpen, setDebriefModalOpen] = useState(false);
  const [debriefData, setDebriefData] = useState<DebriefData | null>(null);
  const [debriefLoading, setDebriefLoading] = useState(false);

  // Command input box
  const [commandInput, setCommandInput] = useState("");
  const [commandSending, setCommandSending] = useState(false);

  // Active foreground window
  const [activeWindow, setActiveWindow] = useState<{ title: string; process: string }>({
    title: "Primary Console",
    process: "explorer.exe"
  });

  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const lineIdRef = useRef(0);

  // Clock tick
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Poll Spotify
  useEffect(() => {
    const fetchNowPlaying = async () => {
      try {
        const r = await fetch('/api/spotify/now_playing');
        const d = await r.json();
        if (d && d.song && d.playing) setNowPlaying(d);
        else setNowPlaying(null);
      } catch {
        setNowPlaying(null);
      }
    };
    fetchNowPlaying();
    const interval = setInterval(fetchNowPlaying, 8000);
    return () => clearInterval(interval);
  }, []);

  // Poll Acoustic Status
  useEffect(() => {
    const fetchAcoustic = async () => {
      try {
        const res = await fetch('/api/acoustic/status');
        if (res.ok) {
          const d = await res.json() as AcousticStatus;
          setAcousticStatus(d);
          setAcousticActive(d.active ?? false);
        }
      } catch {
        return;
      }
    };
    fetchAcoustic();
    const iv = setInterval(fetchAcoustic, 4000);
    return () => clearInterval(iv);
  }, []);

  // SSE Stream
  useEffect(() => {
    const evtSource = new EventSource("/stream");
    evtSource.onopen = () => setConnected(true);
    evtSource.onerror = () => setConnected(false);

    evtSource.onmessage = function (event) {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'state') {
          setOrbState(data.value as AppState);
        } else if (data.type === 'omega') {
          setFocusState(data.value as FocusState);
        } else if (data.type === 'halted') {
          setAlfredStopped(data.value === true);
        } else if (data.type === 'sentry') {
          setSentry(data.value as SentryState);
        } else if (data.type === 'transcript') {
          lineIdRef.current += 1;
          const nowStr = new Date().toLocaleTimeString('en-US', { hour12: false });
          setTranscript(prev => [
            ...prev,
            { author: data.author, text: data.value, id: lineIdRef.current, time: nowStr }
          ].slice(-60));
        } else if (data.type === 'persona') {
          const p = data.value;
          setPersona({
            name: p.name,
            display_name: p.display_name,
            color: p.color || "#00e5ff",
            secondary_color: p.secondary_color || "#0284c7"
          });
          applyTheme(p.name, p.color, p.secondary_color);
        } else if (data.type === 'meeting') {
          setMeetingState(data.value);
        }
      } catch {
        return;
      }
    };

    return () => evtSource.close();
  }, []);

  // Poll / sync initial meeting status
  useEffect(() => {
    const fetchMeeting = async () => {
      try {
        const res = await fetch('/api/meeting/status');
        if (res.ok) {
          const d = await res.json();
          setMeetingState(d);
        }
      } catch {
        return;
      }
    };
    fetchMeeting();
  }, []);

  // Smooth local timer increment when meeting is actively recording
  useEffect(() => {
    if (!meetingState.active) return;
    const timer = setInterval(() => {
      setMeetingState(prev => prev.active ? { ...prev, elapsed_seconds: (prev.elapsed_seconds || 0) + 1 } : prev);
    }, 1000);
    return () => clearInterval(timer);
  }, [meetingState.active]);

  // Initial Persona fetch
  useEffect(() => {
    const fetchPersona = async () => {
      try {
        const r = await fetch('/api/persona/active');
        const d = await r.json();
        if (d && d.name) {
          setPersona({
            name: d.name,
            display_name: d.display_name,
            color: d.accent_color || "#00e5ff",
            secondary_color: d.secondary_color || "#0284c7"
          });
          applyTheme(d.name, d.accent_color, d.secondary_color);
        }
      } catch {
        return;
      }
    };
    fetchPersona();
  }, []);

  // Auto-scroll transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcript]);

  const applyTheme = (name: string, color?: string, secondary?: string) => {
    if (color) document.documentElement.style.setProperty('--persona-color', color);
    if (secondary) document.documentElement.style.setProperty('--persona-secondary', secondary);
    document.body.classList.remove('theme-alfred', 'theme-jarvis', 'theme-friday');
    document.body.classList.add(`theme-${name}`);
  };

  const switchPersona = async (target: string) => {
    try {
      const r = await fetch('/api/persona/switch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ persona: target })
      });
      const res = await r.json();
      if (res.active) {
        const d = res.active;
        setPersona({
          name: d.name,
          display_name: d.display_name,
          color: d.accent_color || "#00e5ff",
          secondary_color: d.secondary_color || "#0284c7"
        });
        applyTheme(d.name, d.accent_color, d.secondary_color);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const toggleStop = async () => {
    try {
      const endpoint = alfredStopped ? '/api/speech/resume' : '/api/speech/stop';
      await fetch(endpoint, { method: 'POST' });
      setAlfredStopped(!alfredStopped);
    } catch (e) {
      console.error(e);
    }
  };

  const handleInspectScreen = async (mode: string = "general") => {
    setScreenLoading(true);
    setScreenModalOpen(true);
    try {
      const res = await fetch('/api/screen/copilot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: "Analyze my screen", mode })
      });
      const data = await res.json() as ScreenAnalysis;
      setScreenAnalysis(data);
      if (data.window) {
        setActiveWindow(data.window);
      }
    } catch (error: unknown) {
      setScreenAnalysis({ success: false, analysis: "Error connecting to Screen Co-Pilot: " + getErrorMessage(error) });
    } finally {
      setScreenLoading(false);
    }
  };

  const handleRunDebrief = async () => {
    setDebriefLoading(true);
    setDebriefModalOpen(true);
    try {
      const res = await fetch('/api/debrief/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ speak: true })
      });
      const data = await res.json() as DebriefData;
      setDebriefData(data);
    } catch (error: unknown) {
      setDebriefData({ success: false, spoken_text: "Debrief generation failed: " + getErrorMessage(error) });
    } finally {
      setDebriefLoading(false);
    }
  };

  const toggleAcousticSentry = async () => {
    try {
      const next = !acousticActive;
      const res = await fetch('/api/acoustic/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: next })
      });
      if (res.ok) {
        const d = await res.json();
        setAcousticActive(d.active);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSendCommand = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!commandInput.trim() || commandSending) return;
    const cmd = commandInput.trim();
    setCommandInput("");
    setCommandSending(true);

    try {
      await fetch('/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: cmd })
      });
    } catch (err) {
      console.error("Command send error:", err);
    } finally {
      setCommandSending(false);
    }
  };

  // Latest caption text
  const latestCaption = transcript.length > 0 ? transcript[transcript.length - 1].text : "System online and standing by.";

  return (
    <div className="w-screen h-screen flex flex-col bg-[#08090d] text-zinc-100 overflow-hidden select-none font-sans">
      
      {/* ── TOP HEADER BAR (Height: 52px, Flat, Zero Gradients, Zero Overlap) ── */}
      <header className="h-[52px] shrink-0 border-b border-[#1c2230] bg-[#0c0e14] px-5 flex items-center justify-between z-30">
        
        {/* Left: System Identity */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-400' : 'bg-rose-500'}`}
            />
            <span 
              className="text-xs font-mono font-bold tracking-wider uppercase"
              style={{ color: persona.color }}
            >
              {persona.display_name} // OS
            </span>
          </div>

          <div className="w-px h-3.5 bg-[#222838]" />

          <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">
            {connected ? 'ONLINE // DIRECT LINK' : 'OFFLINE // STANDALONE'}
          </span>

          {meetingState.active && (
            <>
              <div className="w-px h-3.5 bg-[#222838]" />
              <button
                onClick={() => setActiveView('notetaker')}
                className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-rose-950/80 border border-rose-500/80 text-rose-300 text-[10px] font-mono font-bold animate-pulse hover:bg-rose-900 transition-colors"
                title="Active Session Recording — Click to open Notetaker Studio"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping" />
                <span>REC {Math.floor((meetingState.elapsed_seconds || 0) / 60).toString().padStart(2, '0')}:{((meetingState.elapsed_seconds || 0) % 60).toString().padStart(2, '0')}</span>
              </button>
            </>
          )}
        </div>

        {/* Center: Structured View Tabs */}
        <nav className="flex items-center bg-[#121620] border border-[#222838] rounded p-0.5 gap-1">
          {[
            { id: 'cockpit', label: '1 // COCKPIT' },
            { id: 'sentry', label: '2 // SENTRY' },
            { id: 'study', label: '3 // STUDY' },
            { id: 'notetaker', label: meetingState.active ? '● 4 // NOTETAKER [REC]' : '4 // NOTETAKER' },
            { id: 'archive', label: '5 // DOSSIERS' }
          ].map(tab => {
            const isActive = activeView === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveView(tab.id as ViewMode)}
                className={`px-3 py-1 text-[10px] font-mono tracking-wider transition-colors rounded ${
                  isActive
                    ? 'bg-[#202738] text-white font-semibold border border-[#333d54]'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-[#181d2a]'
                }`}
                style={{
                  color: isActive ? persona.color : (tab.id === 'notetaker' && meetingState.active ? '#fb7185' : undefined)
                }}
              >
                {tab.label}
              </button>
            );
          })}
        </nav>

        {/* Right: Clock & Persona Selectors & Halt Toggle */}
        <div className="flex items-center gap-3">
          {/* Persona Switcher Pills */}
          <div className="flex items-center bg-[#121620] border border-[#222838] rounded p-0.5 gap-1">
            {[
              { id: 'alfred', label: 'ALFRED', color: '#d4a956' },
              { id: 'jarvis', label: 'JARVIS', color: '#00e5ff' },
              { id: 'friday', label: 'FRIDAY', color: '#ff3b5c' }
            ].map(p => {
              const isSelected = persona.name.toLowerCase() === p.id;
              return (
                <button
                  key={p.id}
                  onClick={() => switchPersona(p.id)}
                  className={`px-2 py-0.5 text-[9px] font-mono font-bold tracking-wider rounded transition-colors ${
                    isSelected
                      ? 'bg-zinc-800 text-white'
                      : 'text-zinc-500 hover:text-zinc-300'
                  }`}
                  style={{
                    color: isSelected ? p.color : undefined,
                    borderBottom: isSelected ? `2px solid ${p.color}` : '2px solid transparent'
                  }}
                >
                  {p.label}
                </button>
              );
            })}
          </div>

          <div className="w-px h-3.5 bg-[#222838]" />

          {/* Master Halt Toggle Button */}
          <button
            onClick={toggleStop}
            className={`px-2.5 py-1 text-[9px] font-mono font-bold tracking-wider border rounded transition-colors ${
              alfredStopped
                ? 'bg-rose-950 border-rose-600 text-rose-300'
                : 'bg-zinc-900 border-zinc-700 text-zinc-300 hover:border-zinc-500'
            }`}
          >
            {alfredStopped ? 'HALTED' : 'STANDBY'}
          </button>

          <div className="w-px h-3.5 bg-[#222838]" />

          {/* Precision Digital Clock */}
          <div className="text-right">
            <span className="font-mono text-xs text-zinc-300 tracking-wider font-semibold tabular-nums">
              {currentTime.toLocaleTimeString('en-US', { hour12: false })}
            </span>
          </div>
        </div>
      </header>

      {/* ── MAIN WORKSPACE VIEWPORT (Height: calc(100vh - 52px - 32px), Zero Overlap) ── */}
      <main className="flex-1 min-h-0 flex overflow-hidden">
        
        {/* VIEW 1: COCKPIT (Structured 3-Column Layout) */}
        {activeView === 'cockpit' && (
          <div className="w-full h-full flex overflow-hidden">
            
            {/* ── LEFT PANE: SYSTEM TELEMETRY & ACTIONS (Width: 320px) ── */}
            <aside className="w-[320px] shrink-0 border-r border-[#1c2230] bg-[#0c0e14] flex flex-col p-4 gap-4 overflow-y-auto">
              
              {/* System State Card */}
              <div className="panel p-3 flex flex-col gap-2">
                <div className="flex items-center justify-between border-b border-[#1c2230] pb-1.5">
                  <span className="text-[10px] font-mono text-zinc-400 font-bold uppercase tracking-wider">
                    OPERATIONAL TELEMETRY
                  </span>
                  <span className="text-[9px] font-mono text-emerald-400 font-semibold">NOMINAL</span>
                </div>

                <div className="grid grid-cols-2 gap-2 text-[11px] font-mono pt-1">
                  <div className="flex flex-col">
                    <span className="text-[9px] text-zinc-500 uppercase">STATE BUS</span>
                    <span className="font-bold text-zinc-200 capitalize">{orbState}</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[9px] text-zinc-500 uppercase">ACTIVE WINDOW</span>
                    <span className="font-bold text-zinc-200 truncate" title={activeWindow.title}>
                      {activeWindow.process}
                    </span>
                  </div>
                </div>
              </div>

              {/* Acoustic Ear & Sentry Card */}
              <div className="panel p-3 flex flex-col gap-2.5">
                <div className="flex items-center justify-between border-b border-[#1c2230] pb-1.5">
                  <span className="text-[10px] font-mono text-zinc-400 font-bold uppercase tracking-wider">
                    ACOUSTIC SENTRY EAR
                  </span>
                  <span 
                    className={`text-[9px] font-mono font-bold uppercase ${
                      acousticActive ? 'text-emerald-400' : 'text-zinc-500'
                    }`}
                  >
                    {acousticActive ? 'ARMED' : 'DISARMED'}
                  </span>
                </div>

                {/* Noise Floor Meter: 16 Flat Discrete Level Bars */}
                <div className="flex flex-col gap-1">
                  <div className="flex justify-between text-[9px] font-mono text-zinc-500">
                    <span>AMBIENT RMS: {acousticStatus?.ambient_rms || 0}</span>
                    <span>THRESHOLD: {acousticStatus?.min_rms_threshold || 1200}</span>
                  </div>

                  <div className="flex items-center gap-1 h-3 bg-[#08090d] p-1 border border-[#1e2433]">
                    {Array.from({ length: 16 }).map((_, i) => {
                      const level = (acousticStatus?.ambient_rms || 150) / 100;
                      const active = i < Math.min(16, Math.max(1, Math.round(level)));
                      return (
                        <div
                          key={i}
                          className="flex-1 h-full rounded-none"
                          style={{
                            backgroundColor: active ? (i > 12 ? '#ef4444' : i > 8 ? '#f59e0b' : persona.color) : '#1a202c'
                          }}
                        />
                      );
                    })}
                  </div>
                </div>

                <div className="flex items-center justify-between pt-1">
                  <button
                    onClick={toggleAcousticSentry}
                    className={`px-3 py-1 rounded text-[10px] font-mono font-bold border transition-colors ${
                      acousticActive
                        ? 'bg-rose-950 border-rose-600 text-rose-300'
                        : 'bg-[#161a24] border-[#293244] text-zinc-300 hover:border-zinc-500'
                    }`}
                  >
                    {acousticActive ? 'DISARM EAR' : 'ARM ACOUSTIC EAR'}
                  </button>

                  <span className="text-[9px] font-mono text-zinc-500">
                    {sentry?.active ? 'VISION SENTRY: ON' : 'VISION SENTRY: IDLE'}
                  </span>
                </div>
              </div>

              {/* Spotify / Media Card */}
              <div className="panel p-3 flex flex-col gap-2">
                <div className="flex items-center justify-between border-b border-[#1c2230] pb-1.5">
                  <span className="text-[10px] font-mono text-zinc-400 font-bold uppercase tracking-wider">
                    MEDIA DECK
                  </span>
                  <span className="text-[9px] font-mono text-zinc-500">
                    {nowPlaying ? 'PLAYING' : 'IDLE'}
                  </span>
                </div>

                {nowPlaying ? (
                  <div className="flex items-center justify-between gap-2 pt-0.5">
                    <div className="flex flex-col min-w-0">
                      <span className="text-xs font-semibold text-zinc-200 truncate">{nowPlaying.song}</span>
                      <span className="text-[10px] text-zinc-400 truncate">{nowPlaying.artist}</span>
                    </div>
                    {/* Discrete 4-bar equalizer */}
                    <div className="flex items-end gap-1 h-3 shrink-0">
                      <div className="w-1 h-3 bg-emerald-400 animate-pulse" />
                      <div className="w-1 h-2 bg-emerald-400" />
                      <div className="w-1 h-3 bg-emerald-400 animate-pulse" />
                      <div className="w-1 h-1 bg-emerald-400" />
                    </div>
                  </div>
                ) : (
                  <p className="text-[10px] font-mono text-zinc-500 italic py-1">
                    No active audio stream connected.
                  </p>
                )}
              </div>

              {/* Quick Actions Deck */}
              <div className="panel p-3 flex flex-col gap-2 mt-auto">
                <span className="text-[10px] font-mono text-zinc-400 font-bold uppercase tracking-wider border-b border-[#1c2230] pb-1.5">
                  DIRECT ACTION COMMANDS
                </span>

                <div className="flex flex-col gap-1.5 pt-1">
                  <button
                    onClick={() => handleInspectScreen("general")}
                    className="flex items-center justify-between px-3 py-2 rounded bg-[#131722] border border-[#222a3a] hover:border-cyan-500 text-xs font-mono text-zinc-200 transition-colors"
                  >
                    <span>[ 👁️ INSPECT SCREEN ]</span>
                    <span className="text-cyan-400 text-[10px]">COPILOT</span>
                  </button>

                  <button
                    onClick={() => handleInspectScreen("debug")}
                    className="flex items-center justify-between px-3 py-2 rounded bg-[#131722] border border-[#222a3a] hover:border-amber-500 text-xs font-mono text-zinc-200 transition-colors"
                  >
                    <span>[ ⚡ DEBUG CODE ]</span>
                    <span className="text-amber-400 text-[10px]">VISION</span>
                  </button>

                  <button
                    onClick={handleRunDebrief}
                    className="flex items-center justify-between px-3 py-2 rounded bg-[#131722] border border-[#222a3a] hover:border-purple-500 text-xs font-mono text-zinc-200 transition-colors"
                  >
                    <span>[ 🌙 EXECUTIVE DEBRIEF ]</span>
                    <span className="text-purple-400 text-[10px]">SYNTHESIS</span>
                  </button>
                </div>
              </div>
            </aside>

            {/* ── CENTER PANE: TACTICAL VECTOR CORE & REAL-TIME CAPTION (Flex-1) ── */}
            <section className="flex-1 flex flex-col justify-between p-6 overflow-hidden bg-[#08090d]">
              
              {/* Top Banner Status */}
              <div className="flex items-center justify-between border-b border-[#1a202c] pb-3">
                <div className="flex flex-col">
                  <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">
                    SYSTEM DIRECTIVE
                  </span>
                  <span className="text-xs font-mono font-bold text-zinc-200 uppercase">
                    {orbState === 'speaking' ? 'TRANSMITTING SPOKEN VOCAL RESPONSE' : orbState === 'listening' ? 'AWAITING VOCAL INSTRUCTION // BUFFER ACTIVE' : 'DIRECTIVE BUS NOMINAL // STANDBY'}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono text-zinc-500 uppercase">OPERATOR:</span>
                  <span className="text-xs font-mono font-bold text-zinc-300">MASTER MIHIR</span>
                </div>
              </div>

              {/* Precision Vector Tactical Core */}
              <div className="flex-1 flex items-center justify-center py-4">
                <TacticalCore
                  state={orbState}
                  personaColor={persona.color}
                  personaName={persona.display_name}
                  honorific={persona.name === 'friday' ? 'BOSS' : 'SIR'}
                />
              </div>

              {/* Bottom Real-time Subtitle & Caption Terminal */}
              <div className="panel p-4 flex flex-col gap-1.5 border border-[#222838] bg-[#0c0e14]">
                <div className="flex items-center justify-between text-[9px] font-mono text-zinc-500 uppercase tracking-wider">
                  <span>LIVE VOCAL CAPTION FEED</span>
                  <span style={{ color: persona.color }}>{persona.display_name}</span>
                </div>
                <p className="font-mono text-xs text-zinc-200 leading-relaxed min-h-[38px] flex items-center">
                  "{latestCaption}"
                </p>
              </div>
            </section>

            {/* ── RIGHT PANE: EVENT TRANSCRIPT & COMMAND TERMINAL (Width: 380px) ── */}
            <aside className="w-[380px] shrink-0 border-l border-[#1c2230] bg-[#0c0e14] flex flex-col overflow-hidden">
              
              {/* Header */}
              <div className="p-3 border-b border-[#1c2230] flex items-center justify-between bg-[#0e1118]">
                <span className="text-[10px] font-mono text-zinc-400 font-bold uppercase tracking-wider">
                  EVENT STREAM & TRANSCRIPT
                </span>
                <span className="text-[9px] font-mono text-zinc-500">
                  {transcript.length} ENTRIES
                </span>
              </div>

              {/* Scrollable Event Log */}
              <div className="flex-1 p-3 overflow-y-auto flex flex-col gap-2 font-mono text-xs">
                {transcript.map((line) => {
                  const isUser = line.author === 'User';
                  const isAlfred = line.author === persona.display_name || line.author === 'Alfred';
                  return (
                    <div
                      key={line.id}
                      className="p-2 rounded border border-[#1a202c] bg-[#11141d] flex flex-col gap-1"
                    >
                      <div className="flex items-center justify-between text-[9px] text-zinc-500">
                        <span
                          className="font-bold uppercase tracking-wider"
                          style={{
                            color: isUser ? '#38bdf8' : isAlfred ? persona.color : '#94a3b8'
                          }}
                        >
                          {isUser ? 'YOU' : line.author}
                        </span>
                        <span>{line.time}</span>
                      </div>
                      <p className="text-zinc-300 text-[11px] leading-relaxed break-words whitespace-pre-wrap">
                        {line.text}
                      </p>
                    </div>
                  );
                })}
                <div ref={transcriptEndRef} />
              </div>

              {/* Bottom Command Prompt Box */}
              <form 
                onSubmit={handleSendCommand} 
                className="p-2.5 border-t border-[#1c2230] bg-[#0e1118] flex items-center gap-2"
              >
                <input
                  type="text"
                  value={commandInput}
                  onChange={(e) => setCommandInput(e.target.value)}
                  placeholder="Enter directive or question..."
                  className="flex-1 bg-[#141824] border border-[#232a3c] rounded px-3 py-1.5 text-xs font-mono text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-400"
                />
                <button
                  type="submit"
                  disabled={commandSending || !commandInput.trim()}
                  className="px-3 py-1.5 rounded bg-[#1e2638] hover:bg-[#28324a] text-xs font-mono font-bold text-zinc-200 border border-[#2e374c] disabled:opacity-40 transition-colors"
                >
                  {commandSending ? 'SENDING...' : 'DISPATCH'}
                </button>
              </form>
            </aside>
          </div>
        )}

        {/* VIEW 2: SENTRY & SECURITY */}
        {activeView === 'sentry' && (
          <div className="w-full h-full p-4 overflow-y-auto">
            {sentry ? (
              <SentryDashboard sentry={sentry} />
            ) : (
              <div className="panel p-8 text-center text-zinc-500 font-mono text-sm">
                Sentry visual sensor is currently on standby. Say "Engage Sentry Mode" to activate camera tracking.
              </div>
            )}
          </div>
        )}

        {/* VIEW 3: STUDY & PROTOCOL OMEGA */}
        {activeView === 'study' && (
          <div className="w-full h-full p-6 overflow-y-auto flex items-center justify-center">
            <div className="w-full max-w-4xl">
              <FocusPanel focusState={focusState} lockdown={false} />
            </div>
          </div>
        )}

        {/* VIEW 4: LIVE NOTETAKER STUDIO */}
        {activeView === 'notetaker' && (
          <div className="w-full h-full overflow-hidden">
            <MeetingNotetaker personaColor={persona.color} />
          </div>
        )}

        {/* VIEW 5: RESEARCH DOSSIERS */}
        {activeView === 'archive' && (
          <div className="w-full h-full overflow-hidden">
            <ResearchViewer onClose={() => setActiveView('cockpit')} />
          </div>
        )}
      </main>

      {/* ── FOOTER STATUS BAR (Height: 32px, Flat, Zero Gradients, Zero Overlap) ── */}
      <footer className="h-8 shrink-0 border-t border-[#1c2230] bg-[#0c0e14] px-5 flex items-center justify-between text-[10px] font-mono text-zinc-500 z-30">
        <div className="flex items-center gap-3">
          <span>AUDIO ENGINE: EDGE-TTS</span>
          <div className="w-px h-3 bg-[#1e2434]" />
          <span>ACTIVE VOICE: {persona.name.toUpperCase()}_NEURAL</span>
        </div>

        {/* Flat Discrete 16-bar Spectrum Monitor */}
        <div className="flex items-center gap-1 h-2.5">
          {[20, 45, 30, 60, 40, 80, 50, 70, 90, 65, 45, 80, 35, 60, 25, 40].map((h, i) => {
            const isLive = orbState === 'speaking' || orbState === 'listening';
            return (
              <div
                key={i}
                className="w-1 rounded-none transition-all duration-100"
                style={{
                  height: isLive ? `${Math.max(20, h * pulseLevel(i))}%` : '25%',
                  backgroundColor: isLive ? persona.color : '#283144'
                }}
              />
            );
          })}
        </div>

        <div className="flex items-center gap-3">
          <span>FOCUS: {focusState?.daily_progress || 0} / {focusState?.daily_goal || 240}m</span>
          <div className="w-px h-3 bg-[#1e2434]" />
          <span>SYS HEALTH: 100% NOMINAL</span>
        </div>
      </footer>

      {/* ── SCREEN CO-PILOT MODAL (Bounded, Zero Gradients) ── */}
      {screenModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/85 flex items-center justify-center p-4">
          <div className="w-full max-w-2xl bg-[#0e1118] border border-[#2b3548] rounded p-5 flex flex-col max-h-[85vh] gap-3">
            <div className="flex items-center justify-between border-b border-[#222a3a] pb-2">
              <span className="text-xs font-mono font-bold text-cyan-400">
                LIVE SCREEN CO-PILOT // VISION REASONING
              </span>
              <button 
                onClick={() => setScreenModalOpen(false)}
                className="text-zinc-400 hover:text-white font-mono text-xs px-2"
              >
                [CLOSE ✕]
              </button>
            </div>

            <div className="flex-1 overflow-y-auto font-mono text-xs text-zinc-300 leading-relaxed whitespace-pre-wrap p-3 bg-[#08090d] border border-[#1a202c]">
              {screenLoading ? (
                <div className="py-12 text-center text-zinc-500 font-mono">
                  [ CAPTURING GDI SCREENSHOT & INFERRING VIA GEMINI 2.5 FLASH... ]
                </div>
              ) : (
                screenAnalysis?.analysis || "No analysis generated."
              )}
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-[#222a3a]">
              <button
                onClick={() => handleInspectScreen("general")}
                className="px-3 py-1.5 rounded bg-[#161a24] hover:bg-[#202738] border border-[#293244] text-xs font-mono text-zinc-300"
              >
                RE-SCAN SCREEN
              </button>
              <button
                onClick={() => setScreenModalOpen(false)}
                className="px-4 py-1.5 rounded bg-cyan-700 hover:bg-cyan-600 text-xs font-mono font-bold text-white"
              >
                DONE
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── EVENING DEBRIEF MODAL (Bounded, Zero Gradients) ── */}
      {debriefModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/85 flex items-center justify-center p-4">
          <div className="w-full max-w-2xl bg-[#0e1118] border border-[#2b3548] rounded p-5 flex flex-col max-h-[85vh] gap-3">
            <div className="flex items-center justify-between border-b border-[#222a3a] pb-2">
              <span className="text-xs font-mono font-bold text-purple-400">
                EXECUTIVE EVENING DEBRIEF // TELEMETRY RECONCILIATION
              </span>
              <button 
                onClick={() => setDebriefModalOpen(false)}
                className="text-zinc-400 hover:text-white font-mono text-xs px-2"
              >
                [CLOSE ✕]
              </button>
            </div>

            <div className="flex-1 overflow-y-auto flex flex-col gap-3 font-mono text-xs text-zinc-300 p-3 bg-[#08090d] border border-[#1a202c]">
              {debriefLoading ? (
                <div className="py-12 text-center text-zinc-500 font-mono">
                  [ RECONCILING COMPLETED TASKS, SCREENPIPE DWELL & SECURITY TELEMETRY... ]
                </div>
              ) : (
                <>
                  <div className="p-3 bg-[#131722] border border-[#232b3c] text-purple-200 italic">
                    "{debriefData?.spoken_text}"
                  </div>
                  {debriefData?.metrics && (
                    <div className="grid grid-cols-2 gap-2 text-[11px] pt-2">
                      <div className="p-2 bg-[#10141e] border border-[#1e2434]">
                        <span className="text-zinc-500 block text-[9px]">FOCUS LOGGED</span>
                        <span className="font-bold text-white">{debriefData.metrics.focus_minutes} mins</span>
                      </div>
                      <div className="p-2 bg-[#10141e] border border-[#1e2434]">
                        <span className="text-zinc-500 block text-[9px]">STUDY STREAK</span>
                        <span className="font-bold text-white">{debriefData.metrics.study_streak_days} days</span>
                      </div>
                      <div className="p-2 bg-[#10141e] border border-[#1e2434]">
                        <span className="text-zinc-500 block text-[9px]">COMPLETED TASKS</span>
                        <span className="font-bold text-white">{debriefData.metrics.completed_tasks?.length || 0}</span>
                      </div>
                      <div className="p-2 bg-[#10141e] border border-[#1e2434]">
                        <span className="text-zinc-500 block text-[9px]">SECURITY INCIDENTS</span>
                        <span className="font-bold text-white">{debriefData.metrics.security_incidents_count || 0}</span>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            <div className="flex justify-end pt-2 border-t border-[#222a3a]">
              <button
                onClick={() => setDebriefModalOpen(false)}
                className="px-4 py-1.5 rounded bg-purple-700 hover:bg-purple-600 text-xs font-mono font-bold text-white"
              >
                DONE
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

function pulseLevel(i: number): number {
  return 0.5 + Math.sin(Date.now() / 200 + i) * 0.5;
}

export default App;
