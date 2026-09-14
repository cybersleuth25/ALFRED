import { useState, useEffect } from 'react';

export default function OsintPanel() {
  const [news, setNews] = useState<string[]>([]);
  const [quakes, setQuakes] = useState<string[]>([]);
  const [updated, setUpdated] = useState('--:--');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const r = await fetch('/api/osint');
        const data = await r.json();
        setNews(data.news || []);
        setQuakes(data.earthquakes || []);
        if (data.updated) setUpdated(data.updated.slice(0, 5));
      } catch {}
      setLoading(false);
    };
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="card h-full flex flex-col overflow-hidden relative">
      
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2.5">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-cyan-400/80 drop-shadow-[0_0_5px_rgba(34,211,238,0.5)]">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          <span className="text-[11px] tracking-[0.25em] text-cyan-400/80 font-semibold uppercase text-shadow-glow">Global Intel</span>
        </div>
        <span className="text-[9px] text-white/15 font-mono tabular-nums">{updated}</span>
      </div>

      <div className="flex-1 overflow-hidden space-y-5">
        <div>
          <div className="section-header">
            <span>Headlines</span>
          </div>
          <div className="space-y-2.5">
            {loading && (
              <>
                {[1,2,3].map(i => (
                  <div key={i} className="h-3 bg-white/[0.04] rounded-full animate-pulse" style={{ width: `${80 - i * 15}%` }} />
                ))}
              </>
            )}
            {!loading && news.length === 0 && <div className="text-[11px] text-white/15 font-light">No headlines available</div>}
            {news.slice(0, 5).map((item, i) => (
              <div key={i} className="text-[11px] text-white/60 leading-snug line-clamp-1 hover:text-white transition-colors duration-300 flex gap-3 p-1.5 rounded bg-white/[0.02] border border-white/[0.02] hover:bg-white/[0.05]" title={item}>
                <span className="font-mono text-[9px] text-cyan-400/50 w-4 shrink-0 tabular-nums">{String(i + 1).padStart(2, '0')}</span>
                <span className="truncate font-medium tracking-wide">{item}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="h-px bg-white/[0.04]"></div>

        <div>
          <div className="section-header">
            <span>Seismic</span>
          </div>
          <div className="space-y-2">
            {!loading && quakes.length === 0 && <div className="text-[11px] text-white/15 font-light">No significant activity</div>}
            {quakes.slice(0, 4).map((item, i) => {
              const magMatch = item.match(/Magnitude\s+([\d.]+)/);
              const mag = magMatch ? parseFloat(magMatch[1]) : 0;
              const dotColor = mag >= 6 ? '#ef4444' : mag >= 5 ? '#f59e0b' : '#38bdf8';
              return (
                <div key={i} className="flex items-center gap-3 text-[11px] p-1.5 rounded bg-white/[0.02] border border-white/[0.02] hover:bg-white/[0.05] transition-colors">
                  {/* Colored dot indicator */}
                  <div className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: dotColor, boxShadow: `0 0 8px ${dotColor}` }} />
                  <span className={`font-mono text-[10px] w-7 shrink-0 tabular-nums font-medium text-shadow-glow ${mag >= 6 ? 'text-red-400' : mag >= 5 ? 'text-amber-400' : 'text-sky-400'}`}>
                    {mag > 0 ? mag.toFixed(1) : '--'}
                  </span>
                  <span className="text-white/50 line-clamp-1 font-medium tracking-wide">{item.replace(/Magnitude\s+[\d.]+\s*—?\s*/, '')}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
