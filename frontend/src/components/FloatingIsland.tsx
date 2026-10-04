import React, { useState, useEffect } from 'react';

interface FloatingIslandProps {
  orbState: "idle" | "listening" | "processing" | "speaking";
  persona: {
    name: string;
    display_name: string;
    color: string;
    secondary_color?: string;
    glow_color?: string;
    theme_class?: string;
  };
  latestTranscript?: string;
  onSwitchPersona: (name: string) => void;
  sentryActive?: boolean;
}

export const FloatingIsland: React.FC<FloatingIslandProps> = ({
  orbState,
  persona,
  latestTranscript = "",
  onSwitchPersona,
  sentryActive = false
}) => {
  const [expanded, setExpanded] = useState(false);
  const [screenModalOpen, setScreenModalOpen] = useState(false);
  const [screenAnalysis, setScreenAnalysis] = useState<any>(null);
  const [screenLoading, setScreenLoading] = useState(false);

  const [debriefModalOpen, setDebriefModalOpen] = useState(false);
  const [debriefData, setDebriefData] = useState<any>(null);
  const [debriefLoading, setDebriefLoading] = useState(false);

  const [acousticActive, setAcousticActive] = useState(false);
  const [acousticStatus, setAcousticStatus] = useState<any>(null);

  // Poll acoustic status
  useEffect(() => {
    const fetchAcoustic = async () => {
      try {
        const res = await fetch('/api/acoustic/status');
        if (res.ok) {
          const d = await res.json();
          setAcousticStatus(d);
          setAcousticActive(d.active);
        }
      } catch {}
    };
    fetchAcoustic();
    const iv = setInterval(fetchAcoustic, 4000);
    return () => clearInterval(iv);
  }, []);

  const handleInspectScreen = async (mode: string = "general") => {
    setScreenLoading(true);
    setScreenModalOpen(true);
    try {
      const res = await fetch('/api/screen/copilot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: "What is on my screen?", mode })
      });
      const data = await res.json();
      setScreenAnalysis(data);
    } catch (e: any) {
      setScreenAnalysis({ success: false, analysis: "Error connecting to Screen Co-Pilot: " + e.message });
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
      const data = await res.json();
      setDebriefData(data);
    } catch (e: any) {
      setDebriefData({ success: false, spoken_text: "Debrief failed to generate: " + e.message });
    } finally {
      setDebriefLoading(false);
    }
  };

  const toggleAcousticSentry = async () => {
    try {
      const nextState = !acousticActive;
      const res = await fetch('/api/acoustic/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: nextState })
      });
      if (res.ok) {
        const d = await res.json();
        setAcousticActive(d.active);
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Color mappings based on persona
  const accent = persona.color || "#00e5ff";
  const glow = persona.glow_color || "rgba(0, 229, 255, 0.3)";

  return (
    <>
      {/* Floating Island Top-Center Pill */}
      <div 
        className="fixed top-3 left-1/2 -translate-x-1/2 z-50 transition-all duration-500 ease-out select-none"
        style={{ maxWidth: expanded ? '760px' : '520px', width: '92vw' }}
      >
        <div 
          className="relative rounded-2xl bg-black/75 backdrop-blur-2xl border border-white/10 shadow-2xl overflow-hidden transition-all duration-300"
          style={{
            borderColor: `${accent}40`,
            boxShadow: `0 8px 32px 0 ${glow}, inset 0 0 12px ${accent}15`
          }}
        >
          {/* Main Top Header Bar */}
          <div 
            onClick={() => setExpanded(!expanded)}
            className="flex items-center justify-between px-4 py-2.5 cursor-pointer hover:bg-white/5 transition-colors gap-3"
          >
            {/* Persona Indicator & State Pulse */}
            <div className="flex items-center gap-2.5 shrink-0">
              <div className="relative flex items-center justify-center w-6 h-6">
                <div 
                  className={`absolute w-full h-full rounded-full animate-ping opacity-60`}
                  style={{
                    backgroundColor: accent,
                    animationDuration: orbState === 'speaking' ? '1s' : orbState === 'listening' ? '1.5s' : '3s'
                  }}
                />
                <div 
                  className="relative w-3.5 h-3.5 rounded-full border-2 border-black"
                  style={{ backgroundColor: accent }}
                />
              </div>

              <div className="flex flex-col">
                <span className="text-xs font-black tracking-wider uppercase" style={{ color: accent }}>
                  {persona.display_name}
                </span>
                <span className="text-[9px] uppercase tracking-widest text-zinc-400 font-mono">
                  {orbState}
                </span>
              </div>
            </div>

            {/* Holographic Reactive Audio Waveform */}
            <div className="flex items-center gap-1 h-5 px-2 shrink-0">
              {[40, 75, 55, 90, 60, 85, 45, 100, 65, 50].map((h, i) => {
                const isActive = orbState === 'speaking' || orbState === 'listening';
                const computedH = isActive ? Math.max(15, (h * (Math.sin(Date.now() / 200 + i) + 1.2)) / 2) : 18;
                return (
                  <div
                    key={i}
                    className="w-1 rounded-full transition-all duration-150"
                    style={{
                      height: `${computedH}%`,
                      backgroundColor: isActive ? accent : '#52525b',
                      opacity: isActive ? 0.9 : 0.4
                    }}
                  />
                );
              })}
            </div>

            {/* Subtitle / Caption Stream */}
            <div className="flex-1 overflow-hidden min-w-0 mx-1">
              <p className="text-[11px] font-mono text-zinc-300 truncate">
                {latestTranscript || `Online. Standing by for commands, ${persona.name === 'friday' ? 'boss' : 'sir'}.`}
              </p>
            </div>

            {/* Expand / Minimize Toggle Arrow */}
            <div className="text-zinc-400 hover:text-white shrink-0 text-xs px-1">
              {expanded ? '▲' : '▼'}
            </div>
          </div>

          {/* Expanded Cyberpunk Command Deck */}
          {expanded && (
            <div className="px-4 pb-3.5 pt-1 border-t border-white/5 flex flex-col gap-2.5 animate-fadeIn">
              {/* Quick Actions Row */}
              <div className="flex items-center justify-between gap-2 text-xs pt-1 flex-wrap">
                {/* Screen Co-Pilot */}
                <button
                  onClick={() => handleInspectScreen("general")}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900/90 border border-zinc-700/60 hover:border-cyan-500 hover:bg-cyan-950/40 text-zinc-200 transition-all shadow-sm"
                >
                  <span className="text-cyan-400 font-bold">👁️</span>
                  <span>Inspect Screen</span>
                </button>

                {/* Debug Code on Screen */}
                <button
                  onClick={() => handleInspectScreen("debug")}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900/90 border border-zinc-700/60 hover:border-amber-500 hover:bg-amber-950/40 text-zinc-200 transition-all shadow-sm"
                >
                  <span className="text-amber-400 font-bold">⚡</span>
                  <span>Debug Code</span>
                </button>

                {/* Acoustic Sentry Ear Toggle with live ambient RMS */}
                <button
                  onClick={toggleAcousticSentry}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border transition-all shadow-sm ${
                    acousticActive 
                      ? 'bg-rose-950/50 border-rose-500/80 text-rose-200 shadow-rose-950/50' 
                      : 'bg-zinc-900/90 border-zinc-700/60 text-zinc-400 hover:text-zinc-200'
                  }`}
                  title={acousticStatus?.ambient_rms ? `Ambient Noise: ${acousticStatus.ambient_rms} RMS` : 'Acoustic Ear'}
                >
                  <span>{acousticActive ? '🎧' : '🔇'}</span>
                  <span>Ear {acousticActive ? `Armed (${acousticStatus?.ambient_rms || 0} RMS)` : 'Off'}</span>
                </button>

                {/* Sentry Visual Indicator */}
                <div 
                  className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg border text-[11px] font-mono ${
                    sentryActive ? 'border-amber-500/50 bg-amber-950/20 text-amber-300' : 'border-zinc-800 bg-zinc-900/40 text-zinc-500'
                  }`}
                >
                  <span>🛡️</span>
                  <span>Sentry: {sentryActive ? 'ACTIVE' : 'STANDBY'}</span>
                </div>

                {/* Evening Debrief */}
                <button
                  onClick={handleRunDebrief}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900/90 border border-zinc-700/60 hover:border-purple-500 hover:bg-purple-950/40 text-zinc-200 transition-all shadow-sm"
                >
                  <span className="text-purple-400">🌙</span>
                  <span>Executive Debrief</span>
                </button>
              </div>

              {/* Persona Quick Switcher Deck */}
              <div className="flex items-center justify-between pt-2 border-t border-white/5 text-[11px]">
                <div className="flex items-center gap-2 text-zinc-400 font-mono">
                  <span>ACTIVE PROTOCOL:</span>
                  <span className="font-bold text-white uppercase">{persona.name}</span>
                </div>

                <div className="flex items-center gap-1.5">
                  {[
                    { id: 'alfred', label: 'Alfred', color: '#d4a956' },
                    { id: 'jarvis', label: 'Jarvis', color: '#00e5ff' },
                    { id: 'friday', label: 'Friday', color: '#ff3b30' }
                  ].map(p => (
                    <button
                      key={p.id}
                      onClick={() => onSwitchPersona(p.id)}
                      className={`px-2.5 py-1 rounded-md text-[10px] font-bold tracking-wider uppercase transition-all ${
                        persona.name === p.id 
                          ? 'text-black shadow-md' 
                          : 'bg-zinc-900/80 text-zinc-400 hover:text-white border border-zinc-800'
                      }`}
                      style={{
                        backgroundColor: persona.name === p.id ? p.color : undefined,
                        borderColor: persona.name === p.id ? p.color : undefined
                      }}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Screen Co-Pilot Modal */}
      {screenModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4 animate-fadeIn">
          <div className="w-full max-w-2xl bg-zinc-950/95 border border-cyan-500/40 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
            <div className="px-5 py-3.5 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/50">
              <div className="flex items-center gap-2 text-cyan-400 font-bold">
                <span>👁️ Live Screen Co-Pilot</span>
                {screenAnalysis?.window && (
                  <span className="text-xs font-mono text-zinc-400">
                    [{screenAnalysis.window.process} - {screenAnalysis.window.title?.slice(0, 30)}...]
                  </span>
                )}
              </div>
              <button 
                onClick={() => setScreenModalOpen(false)}
                className="text-zinc-400 hover:text-white px-2 py-0.5 text-sm"
              >
                ✕
              </button>
            </div>

            <div className="p-5 overflow-y-auto space-y-4 text-sm text-zinc-200 font-sans leading-relaxed">
              {screenLoading ? (
                <div className="flex flex-col items-center justify-center py-12 gap-3">
                  <div className="w-8 h-8 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
                  <p className="text-zinc-400 font-mono text-xs">Capturing screen and analyzing via Gemini 2.5 Flash...</p>
                </div>
              ) : (
                <div className="whitespace-pre-wrap font-mono text-xs bg-zinc-900/70 p-4 rounded-xl border border-zinc-800/80">
                  {screenAnalysis?.analysis || "No analysis available."}
                </div>
              )}
            </div>

            <div className="px-5 py-3 border-t border-zinc-800/60 bg-zinc-900/30 flex justify-end gap-2">
              <button
                onClick={() => handleInspectScreen("general")}
                className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-white transition-colors"
              >
                Re-scan Screen
              </button>
              <button
                onClick={() => setScreenModalOpen(false)}
                className="px-4 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-xs font-bold text-white transition-colors"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Evening Debrief Modal */}
      {debriefModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4 animate-fadeIn">
          <div className="w-full max-w-2xl bg-zinc-950/95 border border-purple-500/40 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
            <div className="px-5 py-3.5 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/50">
              <div className="flex items-center gap-2 text-purple-400 font-bold">
                <span>🌙 Executive Evening Debrief</span>
                {debriefData?.timestamp && (
                  <span className="text-xs font-mono text-zinc-400">({debriefData.timestamp})</span>
                )}
              </div>
              <button 
                onClick={() => setDebriefModalOpen(false)}
                className="text-zinc-400 hover:text-white px-2 py-0.5 text-sm"
              >
                ✕
              </button>
            </div>

            <div className="p-5 overflow-y-auto space-y-4 text-sm text-zinc-200 leading-relaxed">
              {debriefLoading ? (
                <div className="flex flex-col items-center justify-center py-12 gap-3">
                  <div className="w-8 h-8 rounded-full border-2 border-purple-400 border-t-transparent animate-spin" />
                  <p className="text-zinc-400 font-mono text-xs">Synthesizing tasks, focus time, and security telemetry...</p>
                </div>
              ) : (
                <>
                  <div className="p-4 rounded-xl bg-purple-950/20 border border-purple-900/40 text-purple-200 font-sans text-sm italic">
                    "{debriefData?.spoken_text}"
                  </div>
                  {debriefData?.metrics && (
                    <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                      <div className="bg-zinc-900/80 p-2.5 rounded-lg border border-zinc-800">
                        <span className="text-zinc-400 block">Focus Progress:</span>
                        <span className="text-white font-bold">{debriefData.metrics.focus_minutes} / {debriefData.metrics.focus_goal_minutes} mins</span>
                      </div>
                      <div className="bg-zinc-900/80 p-2.5 rounded-lg border border-zinc-800">
                        <span className="text-zinc-400 block">Study Streak:</span>
                        <span className="text-white font-bold">{debriefData.metrics.study_streak_days} days</span>
                      </div>
                      <div className="bg-zinc-900/80 p-2.5 rounded-lg border border-zinc-800">
                        <span className="text-zinc-400 block">Tasks Completed:</span>
                        <span className="text-white font-bold">{debriefData.metrics.completed_tasks?.length || 0}</span>
                      </div>
                      <div className="bg-zinc-900/80 p-2.5 rounded-lg border border-zinc-800">
                        <span className="text-zinc-400 block">Security Incidents:</span>
                        <span className="text-white font-bold">{debriefData.metrics.security_incidents_count || 0}</span>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            <div className="px-5 py-3 border-t border-zinc-800/60 bg-zinc-900/30 flex justify-end">
              <button
                onClick={() => setDebriefModalOpen(false)}
                className="px-4 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-xs font-bold text-white transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default FloatingIsland;
