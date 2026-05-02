import { useEffect, useState, useRef } from 'react'
import ShaderBackground from './components/ui/shader-background'
import CommandCenter from './components/CommandCenter'
import './index.css'

type AppState = "idle" | "listening" | "processing" | "speaking";

interface TranscriptLine {
  author: string;
  text: string;
  id: number;
}

interface NowPlayingData {
  song: string;
  artist: string;
  playing: boolean;
}

function App() {
  const [orbState, setOrbState] = useState<AppState>("idle");
  const [commandCenter, setCommandCenter] = useState(false);
  const [caption, setCaption] = useState("");
  const [transcript, setTranscript] = useState<TranscriptLine[]>([]);
  const [connected, setConnected] = useState(false);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [nowPlaying, setNowPlaying] = useState<NowPlayingData | null>(null);
  const [mood, setMood] = useState("standby");
  const [commandCount, setCommandCount] = useState(0);
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
      else if (commandCount > 10) setMood("engaged");
      else setMood("standby");
    }, 1000);
    return () => clearInterval(moodTimer);
  }, [commandCount]);

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
        } else if (data.type === 'caption') {
          setCaption(data.value || "");
        } else if (data.type === 'transcript') {
          lineIdRef.current += 1;
          setTranscript(prev => {
            const updated = [...prev, { author: data.author, text: data.value, id: lineIdRef.current }];
            return updated.slice(-50);
          });
        }
      } catch (e) {}
    };

    return () => evtSource.close();
  }, []);

  // Auto-scroll transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcript]);

  const formatTime = (d: Date) => {
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
  };

  const formatDate = (d: Date) => {
    return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
  };

  const moodLabel = mood === 'engaged' ? 'ENGAGED' : mood === 'dormant' ? 'DORMANT' : mood === 'idle' ? 'IDLE' : 'STANDBY';

  // State-reactive ambient color
  const ambientColor = orbState === 'listening' ? 'rgba(0, 232, 198, 0.05)' 
    : orbState === 'processing' ? 'rgba(255, 170, 0, 0.05)' 
    : orbState === 'speaking' ? 'rgba(180, 190, 255, 0.04)' 
    : 'rgba(80, 90, 140, 0.015)';

  // State accent color for bottom bar
  const stateColor = orbState === 'listening' ? '#00e8c6' 
    : orbState === 'processing' ? '#ffaa00' 
    : orbState === 'speaking' ? '#b4beff' 
    : 'rgba(255,255,255,0.3)';

  return (
    <div className="w-screen h-screen bg-cinematic flex flex-col items-center justify-center relative overflow-hidden font-sans text-white">
      
      {/* State-reactive ambient overlay */}
      <div className="absolute inset-0 z-0 transition-all duration-[2000ms] pointer-events-none" style={{ background: `radial-gradient(circle at 50% 45%, ${ambientColor} 0%, transparent 70%)` }} />

      <CommandCenter active={commandCenter} />

      {/* ── Top Bar ── */}
      <div className="absolute top-0 left-0 right-0 z-40 pointer-events-auto px-8 py-5 flex items-center justify-between">
        
        {/* Left: Brand + Link Status + Mood */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <div className={`w-1.5 h-1.5 rounded-full transition-colors duration-500 ${
              connected ? 'bg-emerald-400/80 status-breathe text-emerald-400' : 'bg-red-400/60 text-red-400'
            }`} />
            <span className="text-[10px] tracking-[0.3em] text-white/25 font-light uppercase">Alfred</span>
          </div>
          <div className="w-px h-3 bg-white/[0.06]"></div>
          <span className={`text-[9px] tracking-[0.2em] font-light uppercase transition-colors duration-500 ${
            connected ? 'text-emerald-400/40' : 'text-red-400/40'
          }`}>{connected ? 'LINK' : 'OFFLINE'}</span>
          <div className="w-px h-3 bg-white/[0.06]"></div>
          <span className="text-[9px] tracking-[0.15em] text-white/15 font-light uppercase">{moodLabel}</span>
        </div>

        {/* Center: Command Center toggle */}
        <button 
          onClick={() => setCommandCenter(!commandCenter)}
          className={`px-5 py-2 text-[9px] tracking-[0.2em] font-light rounded-full transition-all duration-500 ${
            commandCenter 
            ? 'bg-white/[0.08] text-white/80 border border-white/15 shadow-[0_0_20px_rgba(255,255,255,0.03)]' 
            : 'bg-transparent text-white/30 border border-white/[0.06] hover:text-white/60' 
          }`}
        >
          {commandCenter ? 'CLOSE' : 'COMMAND CENTER'}
        </button>

        {/* Right: Clock */}
        <div className="text-right">
          <div className="text-[11px] font-mono text-white/30 tracking-wider tabular-nums">{formatTime(currentTime)}</div>
          <div className="text-[9px] text-white/12 tracking-widest font-light">{formatDate(currentTime)}</div>
        </div>
      </div>

      {/* ── Sentinel 3D Crystal ── */}
      <div className={`absolute inset-0 pointer-events-none flex items-center justify-center transition-all duration-[800ms] ease-[cubic-bezier(0.16,1,0.3,1)] ${
        commandCenter 
          ? 'scale-[0.95] opacity-40 z-0' 
          : 'scale-100 opacity-100 z-20' 
      }`}>
        <ShaderBackground state={orbState} />
        {/* Protocol Watermark */}
        {!commandCenter && (
          <div className="absolute bottom-[18vh] left-1/2 -translate-x-1/2 z-25">
            <div className="text-[9px] tracking-[0.5em] text-white/10 font-light uppercase sentinel-watermark">Alfred Protocol</div>
          </div>
        )}
      </div>

      {/* ── Caption Overlay ── */}
      {caption && !commandCenter && (
        <div className="absolute bottom-24 left-1/2 -translate-x-1/2 z-30 max-w-2xl px-8">
          <div className="caption-container">
            <div className="sentinel-caption text-center text-[13px] font-light leading-relaxed tracking-wide">
              {caption}
            </div>
          </div>
        </div>
      )}

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

      {/* ── Bottom Bar: Status + Transcript ── */}
      <div className={`absolute bottom-0 left-0 right-0 z-40 transition-all duration-700 ${commandCenter ? 'opacity-0 translate-y-4' : 'opacity-100'}`}>
        <div className="px-8 py-4 flex items-end justify-between">
          
          {/* Left: State indicator with colored underline */}
          <div className="text-left">
            <div className="text-[8px] text-white/15 tracking-[0.3em] mb-1.5 uppercase font-light">Status</div>
            <div className="relative inline-block">
              <div className="text-sm font-extralight tracking-[0.2em] capitalize transition-colors duration-500" style={{ color: stateColor }}>
                {orbState}
              </div>
              <div className="absolute bottom-[-3px] left-0 right-0 h-[1px] transition-colors duration-500" style={{ background: `linear-gradient(90deg, ${stateColor}, transparent)` }} />
            </div>
          </div>

          {/* Right: Mini transcript log */}
          <div className="max-w-md w-80 max-h-20 overflow-hidden">
            <div className="space-y-1">
              {transcript.slice(-3).map((line) => (
                <div key={line.id} className="text-[10px] leading-snug animate-fade-in flex gap-2">
                  <span className={`shrink-0 font-mono tracking-wider w-6 ${
                    line.author === 'User' ? 'text-cyan-400/40' : line.author === 'Alfred' ? 'text-white/30' : 'text-amber-400/30'
                  }`}>{line.author === 'User' ? 'YOU' : line.author === 'Alfred' ? 'ALF' : 'SYS'}</span>
                  <span className="w-px h-3 bg-white/[0.06] shrink-0 mt-0.5"></span>
                  <span className="text-white/25 truncate">{line.text}</span>
                </div>
              ))}
              <div ref={transcriptEndRef} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
