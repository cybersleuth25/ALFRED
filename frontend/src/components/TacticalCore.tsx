import { useEffect, useState } from 'react';

interface TacticalCoreProps {
  state: "idle" | "listening" | "processing" | "speaking";
  personaColor: string;
  personaName: string;
  honorific: string;
}

export const TacticalCore: React.FC<TacticalCoreProps> = ({
  state,
  personaColor,
  personaName,
  honorific
}) => {
  const [rotation, setRotation] = useState(0);
  const [pulse, setPulse] = useState(1);

  // Smooth rotation tick
  useEffect(() => {
    const timer = setInterval(() => {
      setRotation(r => (r + (state === 'processing' ? 3 : state === 'listening' ? 1.5 : 0.5)) % 360);
    }, 30);
    return () => clearInterval(timer);
  }, [state]);

  // Audio waveform pulse
  useEffect(() => {
    if (state === 'speaking' || state === 'listening') {
      const pTimer = setInterval(() => {
        setPulse(0.85 + Math.random() * 0.3);
      }, 100);
      return () => clearInterval(pTimer);
    } else {
      setPulse(1);
    }
  }, [state]);

  const isSpeaking = state === 'speaking';
  const isListening = state === 'listening';
  const isProcessing = state === 'processing';

  // Generate ticks for 360 degrees
  const ticks = Array.from({ length: 48 }, (_, i) => i * 7.5);
  const secondaryTicks = Array.from({ length: 12 }, (_, i) => i * 30);

  return (
    <div className="relative flex flex-col items-center justify-center select-none w-full max-w-[420px] aspect-square mx-auto">
      {/* Outer Tactical Calibrated Ring */}
      <div className="relative w-full h-full flex items-center justify-center">
        {/* Outer Circular SVG Grid */}
        <svg className="absolute inset-0 w-full h-full" viewBox="0 0 400 400">
          {/* Static Outer Reference Border */}
          <circle
            cx="200"
            cy="200"
            r="190"
            fill="none"
            stroke="#1c2230"
            strokeWidth="1"
          />

          {/* Calibrated Tick Marks */}
          {ticks.map((deg, idx) => {
            const rad = (deg * Math.PI) / 180;
            const r1 = idx % 4 === 0 ? 182 : 185;
            const r2 = 190;
            const x1 = 200 + r1 * Math.cos(rad);
            const y1 = 200 + r1 * Math.sin(rad);
            const x2 = 200 + r2 * Math.cos(rad);
            const y2 = 200 + r2 * Math.sin(rad);
            return (
              <line
                key={idx}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke={idx % 4 === 0 ? '#475569' : '#1e293b'}
                strokeWidth={idx % 4 === 0 ? 1.5 : 1}
              />
            );
          })}

          {/* Degree Text Labels at 4 cardinal positions */}
          <text x="200" y="24" fill="#64748b" fontSize="8" fontFamily="monospace" textAnchor="middle">000°</text>
          <text x="382" y="203" fill="#64748b" fontSize="8" fontFamily="monospace" textAnchor="start">090°</text>
          <text x="200" y="386" fill="#64748b" fontSize="8" fontFamily="monospace" textAnchor="middle">180°</text>
          <text x="18" y="203" fill="#64748b" fontSize="8" fontFamily="monospace" textAnchor="end">270°</text>

          {/* Rotating Reticle Ring */}
          <g transform={`rotate(${rotation} 200 200)`}>
            <circle
              cx="200"
              cy="200"
              r="165"
              fill="none"
              stroke="#242c3d"
              strokeWidth="1"
              strokeDasharray="8 12"
            />
            {/* Cardinal Reticle Notches */}
            {[0, 90, 180, 270].map((deg, i) => {
              const rad = (deg * Math.PI) / 180;
              const x1 = 200 + 155 * Math.cos(rad);
              const y1 = 200 + 155 * Math.sin(rad);
              const x2 = 200 + 175 * Math.cos(rad);
              const y2 = 200 + 175 * Math.sin(rad);
              return (
                <line
                  key={i}
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  stroke={personaColor}
                  strokeWidth="2"
                />
              );
            })}
          </g>

          {/* Counter-rotating Inner Ring */}
          <g transform={`rotate(${-rotation * 0.7} 200 200)`}>
            <circle
              cx="200"
              cy="200"
              r="135"
              fill="none"
              stroke={isListening || isSpeaking ? personaColor : '#1e293b'}
              strokeWidth="1.5"
              strokeDasharray={isProcessing ? "14 8 2 8" : "40 10"}
            />
          </g>

          {/* Static Inner Bracket Frame */}
          <circle
            cx="200"
            cy="200"
            r="105"
            fill="none"
            stroke="#222b3d"
            strokeWidth="1"
          />

          {secondaryTicks.map((deg, idx) => {
            const rad = (deg * Math.PI) / 180;
            const x1 = 200 + 98 * Math.cos(rad);
            const y1 = 200 + 98 * Math.sin(rad);
            const x2 = 200 + 105 * Math.cos(rad);
            const y2 = 200 + 105 * Math.sin(rad);
            return (
              <line
                key={idx}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke="#475569"
                strokeWidth="1"
              />
            );
          })}
        </svg>

        {/* Core Center Display: Audio Waveform & Status */}
        <div 
          className="relative w-44 h-44 rounded-full bg-[#0c0e14] border border-[#232b3c] flex flex-col items-center justify-center transition-all duration-300 z-10"
          style={{ transform: `scale(${pulse})` }}
        >
          {/* Status Label */}
          <span 
            className="text-[9px] font-mono tracking-widest uppercase font-semibold mb-1"
            style={{ color: personaColor }}
          >
            {state}
          </span>

          {/* 16-band Discrete Waveform Bars */}
          <div className="flex items-center gap-[3px] h-10 px-4">
            {[35, 60, 45, 80, 50, 95, 70, 100, 85, 65, 90, 40, 75, 55, 30, 45].map((val, idx) => {
              const active = isSpeaking || isListening;
              const barHeight = active
                ? Math.max(15, Math.min(100, val * (Math.sin(Date.now() / 150 + idx * 0.8) + 1.2) * 0.5))
                : 15;
              return (
                <div
                  key={idx}
                  className="w-[3px] rounded-none transition-all duration-75"
                  style={{
                    height: `${barHeight}%`,
                    backgroundColor: active ? personaColor : '#334155'
                  }}
                />
              );
            })}
          </div>

          {/* Subtext info */}
          <span className="text-[8px] font-mono text-zinc-500 uppercase tracking-wider mt-1">
            {personaName} // {honorific}
          </span>
        </div>
      </div>
    </div>
  );
};

export default TacticalCore;
