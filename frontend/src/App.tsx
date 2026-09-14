import { useEffect, useState, useRef } from 'react'
import ShaderBackground from './components/ui/shader-background'
import CommandCenter from './components/CommandCenter'

import SentryDashboard from './components/SentryDashboard'
import './index.css'

type AppState = "idle" | "listening" | "processing" | "speaking";

interface TranscriptLine {
  author: string;
  text: string;
  id: number;
}

interface PersonaState {
  name: string;
  display_name: string;
  color: string;
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
}

function App() {
  const [orbState, setOrbState] = useState<AppState>("idle");
  const [alfredStopped, setAlfredStopped] = useState(false);
  const [commandCenter, setCommandCenter] = useState(false);
  const [transcript, setTranscript] = useState<TranscriptLine[]>([]);
  const [connected, setConnected] = useState(false);
  const [mirrorMode, setMirrorMode] = useState(false);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [nowPlaying, setNowPlaying] = useState<NowPlayingData | null>(null);
  const [mood, setMood] = useState("standby");
  const [commandCount, setCommandCount] = useState(0);
  const [focusState, setFocusState] = useState<FocusState | null>(null);
  const [lockdown, setLockdown] = useState(false);
  const [persona, setPersona] = useState<PersonaState>({
    name: "alfred",
    display_name: "A.L.F.R.E.D.",
    color: "#00b4d8"
  });

  const [sentry, setSentry] = useState<SentryState | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const lineIdRef = useRef(0);
  const idleTimerRef = useRef(0);

  // Clock
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Mood tracker
  useEffect(() => {
    if (orbState === 'processing' || orbState === 'listening') {
      setCommandCount(c => c + 1);
      idleTimerRef.current = 0;
    }
  }, [orbState]);

  useEffect(() => {
    const moodTimer = setInterval(() => {
      idleTimerRef.current += 1;
      if (idleTimerRef.current > 120) setMood("dormant");
      else if (idleTimerRef.current > 60) setMood("idle");
      // Don't auto-set to standby if the AI has expressed an active emotion
      else if (['happy', 'sad', 'alert', 'angry', 'thinking'].includes(mood)) {
        // Keep the AI's emotion
      }
      else if (commandCount > 10) setMood("engaged");
      else setMood("standby");
    }, 1000);
    return () => clearInterval(moodTimer);
  }, [commandCount, mood]);

  // Spotify Now Playing
  useEffect(() => {
    const fetchNowPlaying = async () => {
      try {
        const r = await fetch('/api/spotify/now_playing');
        const d = await r.json();
        if (d && d.song && d.playing) setNowPlaying(d);
        else setNowPlaying(null);
      } catch { setNowPlaying(null); }
    };
    fetchNowPlaying();
    const interval = setInterval(fetchNowPlaying, 8000);
    return () => clearInterval(interval);
  }, []);

  // SSE Stream
  useEffect(() => {
    const evtSource = new EventSource("/stream");
    
    evtSource.onopen = () => setConnected(true);
    evtSource.onerror = () => setConnected(false);
    
    evtSource.onmessage = function(event) {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'state') {
          setOrbState(data.value as AppState);
        } else if (data.type === 'mood') {
          setMood(data.value || "calm");
          idleTimerRef.current = 0; // Reset idle timer on mood change
        } else if (data.type === 'mirror') {
          setMirrorMode(data.value === true);
          if (data.value) document.body.classList.add('mirror-mode');
          else document.body.classList.remove('mirror-mode');
        } else if (data.type === 'omega') {
          setFocusState(data.value as FocusState);
        } else if (data.type === 'lockdown') {
          setLockdown(data.value === true);
        } else if (data.type === 'halted') {
          setAlfredStopped(data.value === true);
        } else if (data.type === 'transcript') {
          lineIdRef.current += 1;
          setTranscript(prev => {
            const updated = [...prev, { author: data.author, text: data.value, id: lineIdRef.current }];
            return updated.slice(-50);
          });
        } else if (data.type === 'globe') {
          // Globe removed temporarily
        } else if (data.type === 'sentry') {
          setSentry(data.value as SentryState);
        } else if (data.type === 'persona') {
          setPersona(data.value as PersonaState);
          // Apply persona color to root CSS variables for global styling
          document.documentElement.style.setProperty('--persona-color', data.value.color);
        }
      } catch (e) {}
    };

    return () => evtSource.close();
  }, []);

  // Auto-scroll transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcript]);

  // Initial speech status fetch
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const r = await fetch('/api/speech/status');
        const d = await r.json();
        if (d && d.halted !== undefined) {
          setAlfredStopped(d.halted);
        }
      } catch (e) { console.error('Failed to fetch speech status:', e); }
    };
    fetchStatus();
  }, []);

  const toggleStop = async () => {
    if (!alfredStopped) {
      try {
        await fetch('/api/speech/stop', { method: 'POST' });
        setAlfredStopped(true);
      } catch (e) { console.error('Stop failed:', e); }
    } else {
      try {
        await fetch('/api/speech/resume', { method: 'POST' });
      } catch (e) { console.error('Resume failed:', e); }
      setAlfredStopped(false);
    }
  };

  const formatTime = (d: Date) => {
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
  };

  const formatDate = (d: Date) => {
    return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
  };

  const moodLabel = mood === 'engaged' ? 'ENGAGED' : mood === 'dormant' ? 'DORMANT' : mood === 'idle' ? 'IDLE' : 'STANDBY';

  // State-reactive ambient color — warm palette
  const ambientColor = orbState === 'listening' ? 'rgba(77, 168, 218, 0.04)' 
    : orbState === 'processing' ? 'rgba(212, 169, 86, 0.04)' 
    : orbState === 'speaking' ? 'rgba(226, 228, 234, 0.03)' 
    : 'rgba(255, 255, 255, 0.01)';

  // State accent color — warm palette
  const stateColor = orbState === 'listening' ? '#4da8da' 
    : orbState === 'processing' ? '#d4a956' 
    : orbState === 'speaking' ? '#e2e4ea' 
    : 'rgba(255,255,255,0.2)';

  const clearIncidents = async () => {
    try {
      await fetch('http://localhost:8000/api/incidents/clear', { method: 'POST' });
      setSentry(s => s ? { ...s, unseen_incidents: [] } : null);
    } catch (e) {
      console.error("Failed to clear incidents", e);
    }
  };

  const isGlitchActive = sentry?.threat_level === 'high' || sentry?.hidden;
  const isFocusActive = focusState?.active;

  return (
    <div className={`w-screen h-screen flex flex-col items-center justify-center relative overflow-hidden font-sans text-white ${mirrorMode ? 'bg-black' : 'bg-cinematic'} ${isFocusActive ? 'focus-mode-active' : ''} ${isGlitchActive ? 'glitch-overlay' : ''}`}>
      
      {/* State-reactive ambient overlay */}
      <div className="absolute inset-0 z-0 transition-all duration-[2000ms] pointer-events-none mirror-hide" style={{ background: `radial-gradient(circle at 50% 45%, ${ambientColor} 0%, transparent 70%)` }} />

      <CommandCenter active={commandCenter} focusState={focusState} lockdown={lockdown} />

      {/* ── Top Bar ── */}
      <div className="absolute top-0 left-0 right-0 z-40 pointer-events-auto px-8 py-6 flex items-center justify-between">
        
        {/* Left: Brand + Mood */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className={`w-1.5 h-1.5 rounded-full transition-colors duration-500 ${
              connected ? 'bg-emerald-400/80 status-breathe' : 'bg-red-400/80'
            }`} />
            <span className="text-[10px] tracking-[0.2em] text-white/50 font-medium uppercase">{persona.display_name}</span>
          </div>
          <div className="w-px h-3 bg-white/[0.08]"></div>
          <span className="text-[9px] tracking-[0.15em] text-white/30 font-light uppercase">{moodLabel}</span>
          {focusState?.active && (
            <>
              <div className="w-px h-3 bg-white/[0.08]"></div>
              <div className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-red-500 focus-pulse" />
                <span className="text-[9px] tracking-[0.15em] text-red-400/80 font-medium uppercase">FOCUS</span>
              </div>
            </>
          )}
        </div>

        {/* Center: Dashboard toggle */}
        <button 
          onClick={() => setCommandCenter(!commandCenter)}
          className={`px-6 py-2 text-[9px] tracking-[0.2em] font-medium rounded-full transition-all duration-500 ${
            commandCenter 
            ? 'bg-white/[0.08] text-white/90 border border-white/20 shadow-[0_0_20px_rgba(255,255,255,0.05)]' 
            : 'bg-transparent text-white/40 border border-white/[0.08] hover:text-white/80 hover:border-white/15 hover:bg-white/[0.03]' 
          }`}
        >
          {commandCenter ? 'CLOSE' : 'DASHBOARD'}
        </button>

        {/* Right: Clock & Debug */}
        <div className={`text-right flex items-center gap-4 ${mirrorMode ? 'mirror-text-glow' : ''}`}>

          <div>
            <div className={`font-mono tabular-nums ${mirrorMode ? 'text-4xl text-white font-bold' : 'text-[12px] text-white/60 tracking-wider font-medium'}`}>{formatTime(currentTime)}</div>
            <div className={`${mirrorMode ? 'text-xl text-white/80 mt-1 font-medium' : 'text-[9px] text-white/20 tracking-widest font-light mt-0.5'}`}>{formatDate(currentTime)}</div>
          </div>
        </div>
      </div>

      {/* ── Intruder Snapshot Modal ── */}
      {sentry?.unseen_incidents && sentry.unseen_incidents.length > 0 && (
        <div className="absolute inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-md">
          <div className="bg-[#0a0c14] border border-red-500/50 shadow-[0_0_50px_rgba(255,0,0,0.2)] rounded-2xl p-8 max-w-2xl w-full flex flex-col gap-6">
            <div className="flex items-center gap-3 border-b border-red-500/20 pb-4">
              <div className="w-3 h-3 rounded-full bg-red-500 animate-pulse" />
              <h2 className="text-xl tracking-widest uppercase text-red-500 font-bold">Security Alert: Intruder Detected</h2>
            </div>
            <p className="text-white/70 text-sm tracking-wide">
              An unauthorized person was detected while you were away. Snapshots have been captured.
            </p>
            <div className="grid grid-cols-2 gap-4">
              {sentry.unseen_incidents.map((filename, idx) => (
                <div key={idx} className="relative rounded-lg overflow-hidden border border-white/10">
                  <img src={`http://localhost:8000/incident_images/${filename}`} alt="Intruder Snapshot" className="w-full h-auto object-cover" />
                </div>
              ))}
            </div>
            <button 
              onClick={clearIncidents}
              className="mt-4 py-3 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-400 font-medium tracking-[0.2em] uppercase rounded-lg transition-colors"
            >
              Dismiss Alert
            </button>
          </div>
        </div>
      )}

      {/* ── Sentinel 3D Crystal ── */}
      <div className={`absolute inset-0 pointer-events-none flex items-center justify-center transition-all duration-[800ms] ease-[cubic-bezier(0.16,1,0.3,1)] mirror-hide ${
        commandCenter 
          ? 'scale-[0.9] opacity-0 z-0' 
          : 'scale-100 opacity-100 z-20' 
      }`}>
        <ShaderBackground 
          state={orbState} 
          face_x={sentry?.face_x}
          face_y={sentry?.face_y}
        />
      </div>



      {/* ── Alfred Stop Toggle ── */}
      {!commandCenter && (
        <button
          id="alfred-stop-toggle"
          onClick={toggleStop}
          className={`alfred-stop-toggle ${alfredStopped ? 'alfred-stop-active' : ''}`}
          title={alfredStopped ? 'Alfred halted — click to resume' : 'Stop all Alfred activity'}
        >
          <span className="stop-toggle-track">
            <span className="stop-toggle-knob" />
          </span>
          <span className="stop-toggle-label">
            {alfredStopped ? 'HALTED' : 'ACTIVE'}
          </span>
        </button>
      )}



      {/* ── Sentry Dashboard ── */}
      {sentry && !commandCenter && <SentryDashboard sentry={sentry} />}

      {/* ── Spotify Now Playing — bottom left ── */}
      {nowPlaying && !commandCenter && (
        <div className="absolute bottom-[100px] left-8 z-30 flex items-center gap-3 px-4 py-2.5 rounded-2xl bg-white/[0.03] border border-white/[0.06] backdrop-blur-md animate-fade-in">
          {/* Equalizer bars */}
          <div className="flex items-end h-3">
            <span className="eq-bar"></span>
            <span className="eq-bar"></span>
            <span className="eq-bar"></span>
            <span className="eq-bar"></span>
          </div>
          <div>
            <div className="text-[10px] text-white/60 font-light truncate max-w-[180px]">{nowPlaying.song}</div>
            <div className="text-[8px] text-white/25 truncate max-w-[180px]">{nowPlaying.artist}</div>
          </div>
          <span className="text-[8px] tracking-[0.15em] text-emerald-400/40 font-mono uppercase">Live</span>
        </div>
      )}

      {/* ── Bottom Bar: Transcript ── */}
      <div className={`absolute bottom-0 left-0 right-0 z-40 transition-all duration-700 mirror-hide ${commandCenter ? 'opacity-0 translate-y-4 pointer-events-none' : 'opacity-100'}`}>
        <div className="w-full bg-gradient-to-t from-[#0a0c14] to-transparent pt-24 pb-6 px-12 flex items-end justify-between">
          
          {/* Left: State indicator */}
          <div className="text-left shrink-0 w-48">
            <div className="text-[9px] text-white/20 tracking-[0.2em] mb-1.5 uppercase font-medium">Status</div>
            <div className="relative inline-block">
              <div className="text-sm font-medium tracking-[0.15em] capitalize transition-colors duration-500" style={{ color: stateColor }}>
                {orbState}
              </div>
            </div>
          </div>

          {/* Center/Right: Transcript log */}
          <div className="flex-1 max-w-3xl flex justify-center">
            <div className="w-full max-h-28 overflow-hidden flex flex-col justify-end" style={{ maskImage: 'linear-gradient(to bottom, transparent, black 20%)', WebkitMaskImage: 'linear-gradient(to bottom, transparent, black 20%)' }}>
              <div className="space-y-3 pb-2 flex flex-col items-center">
                {transcript.slice(-4).map((line) => (
                  <div key={line.id} className="text-[12px] leading-relaxed animate-slide-up flex gap-3 w-full max-w-2xl">
                    <span className={`shrink-0 font-mono tracking-wider w-12 text-right ${
                      line.author === 'User' ? 'text-blue-400/60' : line.author === 'Alfred' ? 'text-white/50' : 'text-[#d4a956]/50'
                    }`}>{line.author === 'User' ? 'YOU' : line.author === 'Alfred' ? 'ALF' : 'SYS'}</span>
                    <span className="w-px h-auto bg-white/[0.08] shrink-0"></span>
                    <span className={`flex-1 text-left ${line.author === 'User' ? 'text-white/50' : 'text-white/80 font-medium'}`}>{line.text}</span>
                  </div>
                ))}
                <div ref={transcriptEndRef} />
              </div>
            </div>
          </div>
          
          {/* Right spacer for centering */}
          <div className="w-48 shrink-0"></div>
        </div>
      </div>
    </div>
  )
}

export default App
