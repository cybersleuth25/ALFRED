import { useState, useEffect } from 'react';

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

interface FocusStats {
  total_sessions: number;
  total_hours: number;
  avg_focus_score: number;
  total_distractions: number;
  total_pomodoros: number;
  longest_session_min: number;
}

interface HeatmapCell {
  hour: number;
  distractions: number;
  active: boolean;
}

interface FocusPanelProps {
  focusState: FocusState | null;
  lockdown: boolean;
}

function formatTimer(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function formatElapsed(startTs: number): string {
  if (!startTs) return '00:00';
  const elapsed = Math.floor(Date.now() / 1000 - startTs);
  const h = Math.floor(elapsed / 3600);
  const m = Math.floor((elapsed % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

// Circular progress ring component
function TimerRing({ remaining, total, phase }: { remaining: number; total: number; phase: string }) {
  const size = 110;
  const strokeWidth = 3;
  const radius = (size - strokeWidth * 2) / 2;
  const circumference = radius * 2 * Math.PI;
  const progress = total > 0 ? remaining / total : 0;
  const dashOffset = circumference * (1 - progress);

  const phaseColor = phase === 'focus' ? '#ef4444' : phase === 'short_break' ? '#22c55e' : phase === 'long_break' ? '#3b82f6' : '#555';

  return (
    <svg width={size} height={size} className="focus-timer-ring" style={{ transform: 'rotate(-90deg)' }}>
      {/* Background ring */}
      <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth={strokeWidth} />
      {/* Progress ring */}
      <circle
        cx={size / 2} cy={size / 2} r={radius} fill="none"
        stroke={phaseColor}
        strokeWidth={strokeWidth}
        strokeDasharray={circumference}
        strokeDashoffset={dashOffset}
        strokeLinecap="round"
        style={{ transition: 'stroke-dashoffset 1s linear', filter: `drop-shadow(0 0 6px ${phaseColor}40)` }}
      />
    </svg>
  );
}

// Focus Heatmap component
function FocusHeatmap({ data }: { data: HeatmapCell[] }) {
  return (
    <div className="mt-3">
      <div className="label mb-1.5">Today's Focus</div>
      <div className="flex gap-[2px]">
        {data.map((cell) => {
          let bg = 'rgba(255,255,255,0.03)'; // inactive
          if (cell.active) {
            if (cell.distractions === 0) bg = 'rgba(34,197,94,0.5)';       // focused
            else if (cell.distractions <= 3) bg = 'rgba(255,170,0,0.5)';   // moderate
            else bg = 'rgba(239,68,68,0.5)';                               // distracted
          }
          return (
            <div
              key={cell.hour}
              className="flex-1 h-2 rounded-[1px] transition-colors duration-500"
              style={{ background: bg }}
              title={`${cell.hour}:00 — ${cell.active ? `${cell.distractions} distractions` : 'no session'}`}
            />
          );
        })}
      </div>
      <div className="flex justify-between mt-0.5">
        <span className="text-[7px] text-white/15 font-mono">00</span>
        <span className="text-[7px] text-white/15 font-mono">12</span>
        <span className="text-[7px] text-white/15 font-mono">23</span>
      </div>
    </div>
  );
}

export default function FocusPanel({ focusState, lockdown }: FocusPanelProps) {
  const [stats, setStats] = useState<FocusStats | null>(null);
  const [toggling, setToggling] = useState(false);
  const [camAvailable, setCamAvailable] = useState(false);
  const [camExpanded, setCamExpanded] = useState(false);
  const [heatmap, setHeatmap] = useState<HeatmapCell[]>([]);

  // Fetch aggregate stats
  useEffect(() => {
    const fetchStats = async () => {
      try {
        const r = await fetch('/api/focus/stats');
        const d = await r.json();
        if (d.stats) setStats(d.stats);
      } catch {
        return;
      }
    };
    fetchStats();
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, []);

  // Check camera availability
  useEffect(() => {
    const checkCam = async () => {
      try {
        const r = await fetch('/api/camera/status');
        const d = await r.json();
        setCamAvailable(d.available === true);
      } catch { setCamAvailable(false); }
    };
    checkCam();
    const interval = setInterval(checkCam, 15000);
    return () => clearInterval(interval);
  }, []);

  // Fetch heatmap data
  useEffect(() => {
    const fetchHeatmap = async () => {
      try {
        const r = await fetch('/api/focus/heatmap');
        const d = await r.json();
        if (d.heatmap) setHeatmap(d.heatmap);
      } catch {
        return;
      }
    };
    fetchHeatmap();
    const interval = setInterval(fetchHeatmap, 60000);
    return () => clearInterval(interval);
  }, []);

  const handleToggle = async () => {
    setToggling(true);
    try {
      await fetch('/api/focus/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'toggle' })
      });
    } catch {
      setToggling(false);
      return;
    }
    setTimeout(() => setToggling(false), 1000);
  };

  const handleBreak = async () => {
    try {
      await fetch('/api/focus/break', { method: 'POST' });
    } catch {
      return;
    }
  };

  const handleLockdown = async () => {
    try {
      await fetch('/api/focus/lockdown', { method: 'POST' });
    } catch {
      return;
    }
  };

  const isActive = focusState?.active ?? false;
  const phase = focusState?.phase ?? 'idle';
  const remaining = focusState?.remaining ?? 0;
  const cycle = focusState?.cycle ?? 0;
  const distractions = focusState?.distractions ?? 0;

  const phaseLabel = phase === 'focus' ? 'FOCUS' : phase === 'short_break' ? 'SHORT BREAK' : phase === 'long_break' ? 'LONG BREAK' : 'STANDBY';
  const phaseColorClass = phase === 'focus' ? 'text-red-400/80' : phase === 'short_break' ? 'text-emerald-400/80' : phase === 'long_break' ? 'text-blue-400/80' : 'text-white/30';

  const totalForPhase = phase === 'focus' ? 25 * 60 : phase === 'long_break' ? 15 * 60 : phase === 'short_break' ? 5 * 60 : 0;

  const distractionColor = distractions === 0 ? 'text-emerald-400/70' : distractions <= 3 ? 'text-amber-400/70' : 'text-red-400/80';

  return (
    <div className={`card h-full flex flex-col overflow-hidden relative ${lockdown ? 'focus-lockdown-border' : ''}`}>

      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${isActive ? 'bg-red-500 focus-pulse drop-shadow-[0_0_8px_rgba(239,68,68,0.8)]' : 'bg-white/15'}`} />
          <span className="text-[11px] tracking-[0.25em] text-red-500/80 font-semibold uppercase text-shadow-glow">
            Focus Mode {focusState?.streak ? <span className="text-amber-400/80 ml-1">🔥 {focusState.streak}</span> : ''}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {lockdown && (
            <span className="focus-lockdown-badge drop-shadow-[0_0_5px_rgba(239,68,68,0.5)]">🔒 LOCKED</span>
          )}
          <span className={`text-[10px] tracking-[0.25em] font-medium uppercase text-shadow-glow ${phaseColorClass}`}>{phaseLabel}</span>
        </div>
      </div>

      {/* Daily Progress Bar */}
      {focusState?.daily_goal ? (
        <div className="mb-2">
          <div className="flex justify-between text-[8px] tracking-[0.15em] text-white/40 mb-1 uppercase">
            <span>Daily Goal</span>
            <span>{focusState.daily_progress} / {focusState.daily_goal} MIN</span>
          </div>
          <div className="h-1 bg-white/5 rounded-full overflow-hidden">
            <div 
              className="h-full bg-emerald-400/60 transition-all duration-1000 ease-out rounded-full"
              style={{ width: `${Math.min(100, (focusState.daily_progress / focusState.daily_goal) * 100)}%` }}
            />
          </div>
        </div>
      ) : null}

      {isActive ? (
        <>
          {/* Webcam Preview */}
          {camAvailable && (
            <div 
              className={`focus-cam-preview ${camExpanded ? 'focus-cam-expanded' : ''} ${phase === 'focus' ? 'border-red-500/30' : 'border-emerald-400/30'}`}
              onClick={() => setCamExpanded(!camExpanded)}
            >
              <img src="/api/camera/feed" alt="Webcam" className="focus-cam-feed" />
              <div className="focus-cam-scanline" />
              <div className="focus-cam-live-dot">
                <div className="w-1.5 h-1.5 rounded-full bg-red-500 focus-pulse" />
                <span className="text-[7px] tracking-[0.15em] text-red-400/80 font-mono">LIVE</span>
              </div>
            </div>
          )}

          {/* Timer Ring + Countdown */}
          <div className="flex-1 flex flex-col items-center justify-center relative">
            <div className="relative">
              <TimerRing remaining={remaining} total={totalForPhase} phase={phase} />
              <div className="absolute inset-0 flex flex-col items-center justify-center" style={{ transform: 'none' }}>
                <div className="text-[24px] font-extralight text-white/90 font-mono tabular-nums leading-none">
                  {formatTimer(remaining)}
                </div>
                <div className="text-[9px] text-white/25 mt-1 tracking-[0.15em] font-light">
                  CYCLE {cycle + 1}
                </div>
              </div>
            </div>

            {/* Pomodoro dots */}
            <div className="flex items-center gap-1.5 mt-2">
              {[0, 1, 2, 3].map(i => (
                <div key={i} className={`w-2 h-2 rounded-full transition-all duration-500 ${
                  i < (cycle % 4) ? 'bg-red-400/70 shadow-[0_0_4px_rgba(239,68,68,0.3)]' : 'bg-white/10'
                }`} />
              ))}
            </div>
          </div>

          {/* Session Stats Row */}
          <div className="flex justify-between items-center py-1.5 border-t border-white/[0.04] mt-1">
            <div>
              <div className="label mb-0.5">Elapsed</div>
              <div className="value text-[11px] font-mono tabular-nums">{formatElapsed(focusState?.session_start ?? 0)}</div>
            </div>
            <div className="text-center">
              <div className="label mb-0.5">Distractions</div>
              <div className={`value text-[11px] font-mono tabular-nums ${distractionColor}`}>{distractions}</div>
            </div>
            <div className="text-right">
              <div className="label mb-0.5">Pomodoros</div>
              <div className="value text-[11px] font-mono tabular-nums">{cycle}</div>
            </div>
          </div>

          {/* Controls */}
          <div className="flex gap-2 mt-1.5">
            {phase === 'focus' && (
              <button onClick={handleBreak} className="focus-btn flex-1 text-[9px] tracking-[0.15em] text-emerald-400/60 border-emerald-400/20 hover:border-emerald-400/40 hover:text-emerald-400/90">
                BREAK
              </button>
            )}
            <button onClick={handleLockdown} className={`focus-btn flex-1 text-[9px] tracking-[0.15em] ${
              lockdown 
                ? 'text-amber-400/80 border-amber-400/30 hover:border-amber-400/50' 
                : 'text-amber-400/40 border-amber-400/15 hover:border-amber-400/30 hover:text-amber-400/70'
            }`}>
              {lockdown ? '🔓 UNLOCK' : '🔒 LOCKDOWN'}
            </button>
            <button onClick={handleToggle} disabled={toggling} className="focus-btn flex-1 text-[9px] tracking-[0.15em] text-red-400/60 border-red-400/20 hover:border-red-400/40 hover:text-red-400/90">
              {toggling ? '...' : 'END'}
            </button>
          </div>
        </>
      ) : (
        <>
          {/* Inactive — Show Stats + Heatmap + Activate */}
          <div className="flex-1 flex flex-col justify-center">
            {stats && stats.total_sessions > 0 ? (
              <div className="space-y-2.5">
                <div className="flex justify-between">
                  <div>
                    <div className="label mb-0.5">Total Sessions</div>
                    <div className="value text-[13px] font-mono tabular-nums">{stats.total_sessions}</div>
                  </div>
                  <div className="text-right">
                    <div className="label mb-0.5">Total Hours</div>
                    <div className="value text-[13px] font-mono tabular-nums">{stats.total_hours}</div>
                  </div>
                </div>
                <div className="flex justify-between">
                  <div>
                    <div className="label mb-0.5">Avg Focus</div>
                    <div className={`value text-[13px] font-mono tabular-nums ${
                      stats.avg_focus_score >= 80 ? 'text-emerald-400/70' : stats.avg_focus_score >= 50 ? 'text-amber-400/70' : 'text-red-400/70'
                    }`}>{stats.avg_focus_score}/100</div>
                  </div>
                  <div className="text-right">
                    <div className="label mb-0.5">Pomodoros</div>
                    <div className="value text-[13px] font-mono tabular-nums">{stats.total_pomodoros}</div>
                  </div>
                </div>
                <div className="flex justify-between">
                  <div>
                    <div className="label mb-0.5">Longest Session</div>
                    <div className="value text-[11px] font-mono tabular-nums">{stats.longest_session_min}m</div>
                  </div>
                  <div className="text-right">
                    <div className="label mb-0.5">Total Distractions</div>
                    <div className="value text-[11px] font-mono tabular-nums">{stats.total_distractions}</div>
                  </div>
                </div>

                {/* Focus Heatmap */}
                {heatmap.length > 0 && <FocusHeatmap data={heatmap} />}
              </div>
            ) : (
              <div className="text-center">
                <div className="text-[11px] text-white/20 font-light mb-1">No sessions recorded yet</div>
                <div className="text-[9px] text-white/10 font-light">Activate to begin tracking</div>
              </div>
            )}
          </div>

          {/* Activate Button */}
          <button onClick={handleToggle} disabled={toggling} className="focus-btn-activate w-full mt-3 py-2.5 text-[10px] tracking-[0.2em] font-light">
            {toggling ? 'ENGAGING...' : 'ACTIVATE FOCUS MODE'}
          </button>
        </>
      )}
    </div>
  );
}
