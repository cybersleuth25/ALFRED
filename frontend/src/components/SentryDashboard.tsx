import React from 'react';

interface SentryState {
  active: boolean;
  threat_level: string;
  threat_score: number;
  persons: number;
  hidden: boolean;
  gesture: string;
  emotion: string;
}

interface Props {
  sentry: SentryState;
}

export default function SentryDashboard({ sentry }: Props) {
  if (!sentry.active) return null;

  const cardStyle: React.CSSProperties = {
    // Flattened 3D skew for v3
    boxShadow: '0 20px 40px rgba(0,0,0,0.5), inset 0 0 10px rgba(255,255,255,0.05)'
  };

  const getThreatColor = (level: string) => {
    switch (level) {
      case 'high': return 'text-red-500';
      case 'medium': return 'text-amber-500';
      default: return 'text-emerald-400';
    }
  };

  return (
    <div className="absolute top-24 right-12 z-30 pointer-events-none transition-all duration-1000">
      <div 
        className="bg-black/40 backdrop-blur-xl border border-white/10 rounded-2xl p-6 w-72 flex flex-col gap-4"
        style={cardStyle}
      >
        <div className="flex items-center justify-between border-b border-white/10 pb-3" style={{ transform: 'translateZ(30px)' }}>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            <span className="text-[10px] tracking-[0.2em] font-light text-white/60 uppercase">Sentry Vision</span>
          </div>
          <span className="text-[10px] tracking-widest text-white/30 uppercase">LIVE HUD</span>
        </div>

        {/* Live Camera Feed */}
        <div className="relative w-full h-32 bg-black rounded-lg overflow-hidden border border-white/5" style={{ transform: 'translateZ(35px)' }}>
          <img 
            src="http://localhost:8000/api/camera/feed" 
            alt="Sentry Live Feed" 
            className="w-full h-full object-cover opacity-80"
          />
          {/* Cyberpunk HUD Overlay */}
          <div className="absolute inset-0 pointer-events-none">
            <div className="absolute top-0 left-0 w-4 h-4 border-t border-l border-white/40" />
            <div className="absolute top-0 right-0 w-4 h-4 border-t border-r border-white/40" />
            <div className="absolute bottom-0 left-0 w-4 h-4 border-b border-l border-white/40" />
            <div className="absolute bottom-0 right-0 w-4 h-4 border-b border-r border-white/40" />
            <div className="absolute top-1/2 left-0 w-full h-[1px] bg-red-500/20 animate-pulse" />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 mt-2" style={{ transform: 'translateZ(40px)' }}>
          {/* Threat Level */}
          <div className="flex flex-col gap-1">
            <span className="text-[8px] tracking-[0.2em] text-white/30 uppercase">Threat Level</span>
            <span className={`text-sm font-medium tracking-widest uppercase ${getThreatColor(sentry.threat_level)}`}>
              {sentry.threat_level}
            </span>
          </div>

          {/* Emotion */}
          <div className="flex flex-col gap-1">
            <span className="text-[8px] tracking-[0.2em] text-white/30 uppercase">Detected Emotion</span>
            <span className="text-sm font-medium text-cyan-400 tracking-widest uppercase">
              {sentry.emotion}
            </span>
          </div>

          {/* Persons Detected */}
          <div className="flex flex-col gap-1">
            <span className="text-[8px] tracking-[0.2em] text-white/30 uppercase">Entities</span>
            <span className="text-sm font-medium text-white/80">
              {sentry.persons} <span className="text-[10px] text-white/40">detected</span>
            </span>
          </div>

          {/* Hidden Status */}
          <div className="flex flex-col gap-1">
            <span className="text-[8px] tracking-[0.2em] text-white/30 uppercase">Target Status</span>
            <span className={`text-sm font-medium tracking-widest uppercase ${sentry.hidden ? 'text-amber-400' : 'text-emerald-400/60'}`}>
              {sentry.hidden ? 'HIDDEN' : 'VISIBLE'}
            </span>
          </div>
        </div>

        {/* Threat Score Bar */}
        <div className="mt-2" style={{ transform: 'translateZ(20px)' }}>
          <div className="flex justify-between mb-1">
            <span className="text-[8px] tracking-[0.2em] text-white/30 uppercase">Threat Score</span>
            <span className="text-[8px] text-white/50">{Math.round(sentry.threat_score)}%</span>
          </div>
          <div className="w-full bg-white/5 h-1 rounded-full overflow-hidden">
            <div 
              className={`h-full transition-all duration-500 ${
                sentry.threat_score > 70 ? 'bg-red-500' : sentry.threat_score > 30 ? 'bg-amber-500' : 'bg-emerald-400'
              }`}
              style={{ width: `${sentry.threat_score}%` }}
            />
          </div>
        </div>

        {/* Gesture Indicator */}
        {sentry.gesture && (
          <div className="absolute -left-4 -top-4 w-12 h-12 bg-white/10 backdrop-blur-md rounded-full flex items-center justify-center border border-white/20 animate-bounce shadow-[0_0_15px_rgba(255,255,255,0.2)]" style={{ transform: 'translateZ(50px)' }}>
            <span className="text-xl">
              {sentry.gesture === 'palm' ? '✋' : sentry.gesture === 'fist' ? '✊' : sentry.gesture === 'ok' ? '👌' : ''}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
