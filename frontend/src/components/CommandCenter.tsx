import { useState, useEffect } from 'react';
import OsintPanel from './panels/OsintPanel';
import WeatherPanel from './panels/WeatherPanel';
import SystemPanel from './panels/SystemPanel';
import TrackerPanel from './panels/TrackerPanel';
import CivicPanel from './panels/CivicPanel';
import FocusPanel from './panels/FocusPanel';

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

interface CommandCenterProps {
  active: boolean;
  focusState: FocusState | null;
  lockdown: boolean;
  onClose?: () => void;
}

export default function CommandCenter({ active, focusState, lockdown, onClose }: CommandCenterProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    if (active) {
      // Small delay to trigger CSS animation
      requestAnimationFrame(() => setMounted(true));
    } else {
      setMounted(false);
    }
  }, [active]);

  if (!active) return null;

  const isFocus = focusState?.active || false;

  return (
    <div className="command-center-overlay" data-mounted={mounted}>
      {/* Cinematic backdrop blur */}
      <div className="command-center-backdrop" />

      {/* Scanline effect overlay */}
      <div className="command-center-scanlines" />

      {/* Main grid container */}
      <div className="command-center-grid-wrapper">
        {/* Tactical Dashboard Header */}
        <div className="flex items-center justify-between mb-4 px-2">
          <div className="flex items-center gap-3">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_8px_rgba(6,182,212,0.8)]" />
            <span className="text-[11px] tracking-[0.25em] font-semibold text-white/70 uppercase">
              Tactical Command Center
            </span>
            <span className="text-[9px] tracking-[0.15em] font-mono text-white/30 border border-white/10 px-2 py-0.5 rounded-full">
              TELEMETRY V2.4
            </span>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="flex items-center gap-1.5 px-3 py-1 text-[10px] tracking-[0.15em] font-mono text-white/60 hover:text-white bg-white/[0.04] hover:bg-white/[0.1] border border-white/10 hover:border-white/25 rounded-full transition-all duration-200 shadow-sm"
              title="Close Tactical Command Center"
            >
              <span>✕</span>
              <span>CLOSE</span>
            </button>
          )}
        </div>

        <div className="bento-grid">

          {/* Weather — Spans 2 columns */}
          <div className={`area-weather bento-cell ${isFocus ? 'focus-mode-dim' : ''}`} style={{ animationDelay: '50ms' }}>
            <WeatherPanel />
          </div>

          {/* System Vitals */}
          <div className={`area-system bento-cell ${isFocus ? 'focus-mode-dim' : ''}`} style={{ animationDelay: '120ms' }}>
            <SystemPanel />
          </div>

          {/* Focus Mode */}
          <div className="area-focus bento-cell" style={{ animationDelay: '180ms' }}>
            <FocusPanel focusState={focusState} lockdown={lockdown} />
          </div>

          {/* OSINT Intel */}
          <div className={`area-osint bento-cell ${isFocus ? 'focus-mode-dim' : ''}`} style={{ animationDelay: '200ms' }}>
            <OsintPanel />
          </div>

          {/* Civic Health */}
          <div className={`area-civic bento-cell ${isFocus ? 'focus-mode-dim' : ''}`} style={{ animationDelay: '260ms' }}>
            <CivicPanel />
          </div>

          {/* Live Tracker */}
          <div className="area-tracker bento-cell" style={{ animationDelay: '360ms' }}>
            <TrackerPanel />
          </div>

        </div>
      </div>
    </div>
  );
}
