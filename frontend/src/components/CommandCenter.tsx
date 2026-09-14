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
}

export default function CommandCenter({ active, focusState, lockdown }: CommandCenterProps) {
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
