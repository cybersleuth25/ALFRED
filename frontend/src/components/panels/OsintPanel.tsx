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
    <div className="glass-panel accent-blue h-full flex flex-col overflow-hidden">
      <div className="scanline-effect" />
      
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2.5">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-cyan-400/60">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          <span className="text-[11px] tracking-[0.15em] text-white/50 font-light">Intel</span>
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
              <div key={i} className="text-[11px] text-white/45 leading-snug line-clamp-1 hover:text-white/70 transition-colors duration-300 flex gap-3" title={item}>
                <span className="font-mono text-[9px] text-white/15 w-4 shrink-0 tabular-nums">{String(i + 1).padStart(2, '0')}</span>
                <span className="truncate font-light">{item}</span>
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
              const dotColor = mag >= 6 ? '#ff4466' : mag >= 5 ? '#ffaa00' : '#7b8cde';
              return (
                <div key={i} className="flex items-center gap-3 text-[11px]">
                  {/* Colored dot indicator */}
                  <div className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: dotColor, boxShadow: `0 0 6px ${dotColor}40` }} />
                  <span className={`font-mono text-[10px] w-7 shrink-0 tabular-nums ${mag >= 6 ? 'text-red-400/80' : mag >= 5 ? 'text-amber-400/70' : 'text-blue-300/50'}`}>
                    {mag > 0 ? mag.toFixed(1) : '--'}
                  </span>
                  <span className="text-white/35 line-clamp-1 font-light">{item.replace(/Magnitude\s+[\d.]+\s*—?\s*/, '')}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
