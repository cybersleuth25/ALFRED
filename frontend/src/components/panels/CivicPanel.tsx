import { useState, useEffect } from 'react';

interface CivicData {
  score: number;
  grade: string;
  summary: string;
  updated: string;
}

export default function CivicPanel() {
  const [data, setData] = useState<CivicData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const r = await fetch('/api/civic');
        const json = await r.json();
        if (json && !json.error) {
          setData(json);
        }
      } catch (e) {
        console.error("Failed to fetch civic data", e);
      }
      setLoading(false);
    };
    fetchData();
    // Refresh every 1 hour (since it's cached on backend for 12h anyway)
    const interval = setInterval(fetchData, 3600000);
    return () => clearInterval(interval);
  }, []);

  const getGradeColor = (grade: string) => {
    if (grade.startsWith('A')) return 'text-emerald-400';
    if (grade.startsWith('B')) return 'text-emerald-400/80';
    if (grade.startsWith('C')) return 'text-amber-400';
    if (grade.startsWith('D')) return 'text-orange-400';
    if (grade.startsWith('F')) return 'text-red-400';
    return 'text-white/50';
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'stroke-emerald-400/50';
    if (score >= 60) return 'stroke-amber-400/50';
    return 'stroke-red-400/50';
  };

  return (
    <div className="glass-panel accent-emerald h-full flex flex-col overflow-hidden relative group">
      <div className="scanline-effect opacity-50" />
      
      {/* Header */}
      <div className="flex items-center justify-between mb-4 relative z-10">
        <div className="flex items-center gap-2.5">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-emerald-400/60">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
          <span className="text-[11px] tracking-[0.15em] text-white/50 font-light">CIVIC HEALTH</span>
        </div>
        <span className="text-[9px] text-white/15 font-mono tabular-nums">{data?.updated || '--:--'}</span>
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="w-8 h-8 rounded-full border-2 border-white/10 border-t-emerald-400/50 animate-spin" />
        </div>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center relative z-10">
          
          {/* Circular Score Display */}
          <div className="relative w-32 h-32 flex items-center justify-center mb-6">
            <svg className="absolute inset-0 w-full h-full -rotate-90">
              <circle cx="64" cy="64" r="58" className="stroke-white/5 fill-none" strokeWidth="4" />
              <circle 
                cx="64" cy="64" r="58" 
                className={`fill-none transition-all duration-1000 ease-out ${getScoreColor(data?.score || 0)}`}
                strokeWidth="4"
                strokeDasharray="364"
                strokeDashoffset={364 - (364 * (data?.score || 0)) / 100}
                strokeLinecap="round"
              />
            </svg>
            <div className="flex flex-col items-center justify-center">
              <span className={`text-4xl font-light tracking-tight ${getGradeColor(data?.grade || 'N/A')}`}>
                {data?.grade || '-'}
              </span>
              <span className="text-[10px] text-white/30 font-mono mt-1">SCORE: {data?.score || 0}</span>
            </div>
          </div>

          {/* AI Summary */}
          <div className="px-4 text-center">
            <p className="text-[11px] text-white/60 font-light leading-relaxed">
              {data?.summary || 'No civic data available at the moment.'}
            </p>
          </div>
        </div>
      )}

      {/* Decorative background glow */}
      <div className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-48 h-48 blur-[80px] rounded-full mix-blend-screen pointer-events-none transition-opacity duration-1000 opacity-0 group-hover:opacity-20 ${data?.grade?.startsWith('A') ? 'bg-emerald-500' : data?.grade?.startsWith('F') ? 'bg-red-500' : 'bg-amber-500'}`} />
    </div>
  );
}
