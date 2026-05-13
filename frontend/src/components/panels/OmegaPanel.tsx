import { useState, useEffect } from 'react';

interface OmegaState {
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

interface OmegaStats {
  total_sessions: number;
  total_hours: number;
  avg_focus_score: number;
  total_distractions: number;
  total_pomodoros: number;
  longest_session_min: number;
}

interface OmegaPanelProps {
  omegaState: OmegaState | null;
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
  const size = 140;
  const strokeWidth = 3;
  const radius = (size - strokeWidth * 2) / 2;
  const circumference = radius * 2 * Math.PI;
  const progress = total > 0 ? remaining / total : 0;
  const dashOffset = circumference * (1 - progress);

  const phaseColor = phase === 'focus' ? '#ef4444' : phase === 'short_break' ? '#22c55e' : phase === 'long_break' ? '#3b82f6' : '#555';

  return (
    <svg width={size} height={size} className="omega-timer-ring" style={{ transform: 'rotate(-90deg)' }}>
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

export default function OmegaPanel({ omegaState }: OmegaPanelProps) {
  const [stats, setStats] = useState<OmegaStats | null>(null);
  const [toggling, setToggling] = useState(false);

  // Fetch aggregate stats
  useEffect(() => {
    const fetchStats = async () => {
      try {
        const r = await fetch('/api/omega/stats');
        const d = await r.json();
        if (d.stats) setStats(d.stats);
      } catch {}
    };
    fetchStats();
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleToggle = async () => {
    setToggling(true);
    try {
      await fetch('/api/omega/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'toggle' })
      });
    } catch {}
    setTimeout(() => setToggling(false), 1000);
  };

  const handleBreak = async () => {
    try {
      await fetch('/api/omega/break', { method: 'POST' });
    } catch {}
  };

  const isActive = omegaState?.active ?? false;
  const phase = omegaState?.phase ?? 'idle';
  const remaining = omegaState?.remaining ?? 0;
  const cycle = omegaState?.cycle ?? 0;
  const distractions = omegaState?.distractions ?? 0;

  const phaseLabel = phase === 'focus' ? 'FOCUS' : phase === 'short_break' ? 'SHORT BREAK' : phase === 'long_break' ? 'LONG BREAK' : 'STANDBY';
  const phaseColorClass = phase === 'focus' ? 'text-red-400/80' : phase === 'short_break' ? 'text-emerald-400/80' : phase === 'long_break' ? 'text-blue-400/80' : 'text-white/30';
  const accentClass = phase === 'focus' ? 'accent-red' : phase === 'short_break' ? 'accent-green' : phase === 'long_break' ? 'accent-blue' : 'accent-cyan';

  const totalForPhase = phase === 'focus' ? 25 * 60 : phase === 'long_break' ? 15 * 60 : phase === 'short_break' ? 5 * 60 : 0;

  const distractionColor = distractions === 0 ? 'text-emerald-400/70' : distractions <= 3 ? 'text-amber-400/70' : 'text-red-400/80';

  return (
    <div className={`glass-panel ${accentClass} h-full flex flex-col overflow-hidden`}>
      <div className="scanline-effect" />

      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <div className={`w-2 h-2 rounded-full ${isActive ? 'bg-red-500 omega-pulse' : 'bg-white/15'}`} />
          <span className="text-[11px] tracking-[0.15em] text-white/50 font-light">
            Protocol Omega {omegaState?.streak ? <span className="text-amber-400/80 ml-1">🔥 {omegaState.streak}</span> : ''}
          </span>
        </div>
        <span className={`text-[9px] tracking-[0.2em] font-light uppercase ${phaseColorClass}`}>{phaseLabel}</span>
      </div>

      {/* Daily Progress Bar */}
      {omegaState?.daily_goal ? (
        <div className="mb-4">
          <div className="flex justify-between text-[8px] tracking-[0.15em] text-white/40 mb-1.5 uppercase">
            <span>Daily Goal</span>
            <span>{omegaState.daily_progress} / {omegaState.daily_goal} MIN</span>
          </div>
          <div className="h-1 bg-white/5 rounded-full overflow-hidden">
            <div 
              className="h-full bg-emerald-400/60 transition-all duration-1000 ease-out rounded-full"
              style={{ width: `${Math.min(100, (omegaState.daily_progress / omegaState.daily_goal) * 100)}%` }}
            />
          </div>
        </div>
      ) : null}

      {isActive ? (
        <>
          {/* Timer Ring + Countdown */}
          <div className="flex-1 flex flex-col items-center justify-center relative">
            <div className="relative">
              <TimerRing remaining={remaining} total={totalForPhase} phase={phase} />
              <div className="absolute inset-0 flex flex-col items-center justify-center" style={{ transform: 'none' }}>
                <div className="text-[28px] font-extralight text-white/90 font-mono tabular-nums leading-none">
                  {formatTimer(remaining)}
                </div>
                <div className="text-[9px] text-white/25 mt-1.5 tracking-[0.15em] font-light">
                  CYCLE {cycle + 1}
                </div>
              </div>
            </div>

            {/* Pomodoro dots */}
            <div className="flex items-center gap-1.5 mt-3">
              {[0, 1, 2, 3].map(i => (
                <div key={i} className={`w-2 h-2 rounded-full transition-all duration-500 ${
                  i < (cycle % 4) ? 'bg-red-400/70 shadow-[0_0_4px_rgba(239,68,68,0.3)]' : 'bg-white/10'
                }`} />
              ))}
            </div>
          </div>

          {/* Session Stats Row */}
          <div className="flex justify-between items-center py-2 border-t border-white/[0.04] mt-2">
            <div>
              <div className="label mb-0.5">Elapsed</div>
              <div className="value text-[11px] font-mono tabular-nums">{formatElapsed(omegaState?.session_start ?? 0)}</div>
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
          <div className="flex gap-2 mt-2">
            {phase === 'focus' && (
              <button onClick={handleBreak} className="omega-btn flex-1 text-[9px] tracking-[0.15em] text-emerald-400/60 border-emerald-400/20 hover:border-emerald-400/40 hover:text-emerald-400/90">
                TAKE BREAK
              </button>
            )}
            <button onClick={handleToggle} disabled={toggling} className="omega-btn flex-1 text-[9px] tracking-[0.15em] text-red-400/60 border-red-400/20 hover:border-red-400/40 hover:text-red-400/90">
              {toggling ? '...' : 'DISENGAGE'}
            </button>
          </div>
        </>
      ) : (
        <>
          {/* Inactive — Show Stats + Activate */}
          <div className="flex-1 flex flex-col justify-center">
            {stats && stats.total_sessions > 0 ? (
              <div className="space-y-3">
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
              </div>
            ) : (
              <div className="text-center">
                <div className="text-[11px] text-white/20 font-light mb-1">No sessions recorded yet</div>
                <div className="text-[9px] text-white/10 font-light">Activate to begin tracking</div>
              </div>
            )}
          </div>

          {/* Activate Button */}
          <button onClick={handleToggle} disabled={toggling} className="omega-btn-activate w-full mt-3 py-2.5 text-[10px] tracking-[0.2em] font-light">
            {toggling ? 'ENGAGING...' : 'ENGAGE PROTOCOL OMEGA'}
          </button>
        </>
      )}
    </div>
  );
}
