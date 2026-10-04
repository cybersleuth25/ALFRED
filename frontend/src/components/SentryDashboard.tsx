export interface TrackedSubject {
  id: number;
  dwell: string;
  dwell_seconds: number;
  active: boolean;
}

interface SentryState {
  active: boolean;
  threat_level: string;
  threat_score: number;
  persons: number;
  hidden: boolean;
  gesture: string;
  emotion: string;
  tracked_subjects?: TrackedSubject[];
}

interface Props {
  sentry: SentryState;
}

export default function SentryDashboard({ sentry }: Props) {
  if (!sentry.active) return null;

  const getThreatColor = (level: string) => {
    switch (level) {
      case 'high': return 'text-rose-500';
      case 'medium': return 'text-amber-500';
      default: return 'text-emerald-400';
    }
  };

  return (
    <div className="w-full max-w-6xl mx-auto flex flex-col gap-4 font-mono select-none">
      
      {/* Top Banner */}
      <div className="panel p-3 flex items-center justify-between border-b border-[#1c2230] bg-[#0c0e14]">
        <div className="flex items-center gap-2.5">
          <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
          <span className="text-xs font-bold text-zinc-200 uppercase tracking-wider">
            SENTRY VISION & PERIMETER SURVEILLANCE
          </span>
        </div>
        <div className="flex items-center gap-3 text-[10px] text-zinc-500">
          <span>AI MODEL: YUNET + SFACE</span>
          <div className="w-px h-3 bg-[#222838]" />
          <span>STATUS: REAL-TIME ACTIVE</span>
        </div>
      </div>

      {/* Main Grid: 2 Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        
        {/* Left 2 Cols: Large Live Video Feed */}
        <div className="lg:col-span-2 panel p-3 bg-[#0c0e14] flex flex-col gap-2">
          <div className="flex items-center justify-between text-[10px] text-zinc-400 border-b border-[#1c2230] pb-1.5">
            <span>LIVE CAMERA STREAM [DSHOW // DEVICE 0]</span>
            <span className="text-emerald-400">FEED ACTIVE</span>
          </div>

          <div className="relative w-full aspect-video bg-[#050608] border border-[#1e2434] overflow-hidden flex items-center justify-center">
            <img 
              src="/api/camera/feed" 
              alt="Sentry Live Feed" 
              className="w-full h-full object-cover"
              onError={(e) => {
                // If camera image fails to stream, show standby placeholder
                (e.target as HTMLElement).style.display = 'none';
              }}
            />

            {/* Tactical Vector Brackets */}
            <div className="absolute inset-2 pointer-events-none border border-zinc-800">
              <div className="absolute top-0 left-0 w-4 h-4 border-t-2 border-l-2 border-cyan-400" />
              <div className="absolute top-0 right-0 w-4 h-4 border-t-2 border-r-2 border-cyan-400" />
              <div className="absolute bottom-0 left-0 w-4 h-4 border-b-2 border-l-2 border-cyan-400" />
              <div className="absolute bottom-0 right-0 w-4 h-4 border-b-2 border-r-2 border-cyan-400" />
            </div>

            {/* Gesture Badge */}
            {sentry.gesture && (
              <div className="absolute top-4 left-4 bg-[#0e1118] border border-cyan-500 px-3 py-1 text-xs text-cyan-300 font-bold uppercase">
                GESTURE: {sentry.gesture}
              </div>
            )}
          </div>
        </div>

        {/* Right Col: Threat Telemetry & Tracked Entities */}
        <div className="panel p-4 bg-[#0c0e14] flex flex-col gap-4">
          <span className="text-xs font-bold text-zinc-300 border-b border-[#1c2230] pb-2">
            THREAT TELEMETRY
          </span>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="p-2.5 bg-[#121520] border border-[#1e2434] rounded flex flex-col gap-0.5">
              <span className="text-[9px] text-zinc-500 uppercase">THREAT LEVEL</span>
              <span className={`font-bold tracking-wider uppercase ${getThreatColor(sentry.threat_level)}`}>
                {sentry.threat_level}
              </span>
            </div>

            <div className="p-2.5 bg-[#121520] border border-[#1e2434] rounded flex flex-col gap-0.5">
              <span className="text-[9px] text-zinc-500 uppercase">ENTITIES COUNT</span>
              <span className="font-bold text-zinc-200">
                {sentry.persons} DETECTED
              </span>
            </div>

            <div className="p-2.5 bg-[#121520] border border-[#1e2434] rounded flex flex-col gap-0.5">
              <span className="text-[9px] text-zinc-500 uppercase">FACIAL EMOTION</span>
              <span className="font-bold text-cyan-400 uppercase">
                {sentry.emotion || 'NEUTRAL'}
              </span>
            </div>

            <div className="p-2.5 bg-[#121520] border border-[#1e2434] rounded flex flex-col gap-0.5">
              <span className="text-[9px] text-zinc-500 uppercase">OPERATOR PRESENCE</span>
              <span className={`font-bold uppercase ${sentry.hidden ? 'text-amber-400' : 'text-emerald-400'}`}>
                {sentry.hidden ? 'AWAY' : 'PRESENT'}
              </span>
            </div>
          </div>

          {/* Threat Score Bar */}
          <div className="flex flex-col gap-1.5 pt-1">
            <div className="flex justify-between text-[10px]">
              <span className="text-zinc-500">THREAT PROBABILITY</span>
              <span className="text-zinc-300 font-bold">{Math.round(sentry.threat_score)}%</span>
            </div>
            <div className="w-full bg-[#141824] h-2 border border-[#202738] overflow-hidden">
              <div 
                className={`h-full transition-all duration-300 ${
                  sentry.threat_score > 70 ? 'bg-rose-500' : sentry.threat_score > 35 ? 'bg-amber-500' : 'bg-emerald-500'
                }`}
                style={{ width: `${sentry.threat_score}%` }}
              />
            </div>
          </div>

          {/* Tracked Subjects Table */}
          <div className="flex flex-col gap-2 pt-2 border-t border-[#1c2230]">
            <div className="flex items-center justify-between text-[10px]">
              <span className="text-zinc-400 font-bold uppercase">TRACKED ENTITIES</span>
              <span className="text-zinc-500">{sentry.tracked_subjects?.length || 0} active</span>
            </div>

            <div className="flex flex-col gap-1.5 max-h-48 overflow-y-auto">
              {sentry.tracked_subjects && sentry.tracked_subjects.length > 0 ? (
                sentry.tracked_subjects.map((sub) => (
                  <div 
                    key={sub.id}
                    className="p-2 bg-[#121520] border border-[#1e2434] rounded flex items-center justify-between text-xs"
                  >
                    <span className="text-zinc-300 font-semibold">Subject #{sub.id}</span>
                    <span className="text-cyan-400 text-[10px]">DWELL: {sub.dwell}</span>
                  </div>
                ))
              ) : (
                <div className="text-[10px] text-zinc-600 italic py-2">
                  No active unidentified subjects in field of view.
                </div>
              )}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
