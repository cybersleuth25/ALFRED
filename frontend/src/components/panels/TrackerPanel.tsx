import { useState, useEffect } from 'react';

interface CryptoData {
  price: number;
  change: number;
}

export default function TrackerPanel() {
  const [iss, setIss] = useState({ lat: 0, lng: 0 });
  const [crypto, setCrypto] = useState<Record<string, CryptoData>>({});
  const [updated, setUpdated] = useState('--:--');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const r = await fetch('/api/tracker');
        const data = await r.json();
        setIss(data.iss || { lat: 0, lng: 0 });
        setCrypto(data.crypto || {});
        if (data.updated) setUpdated(data.updated.slice(0, 5));
      } catch {
        return;
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, []);

  const formatPrice = (price: number) => {
    if (price >= 1000) return `$${price.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
    return `$${price.toFixed(2)}`;
  };

  return (
    <div className="card h-full flex flex-col overflow-hidden relative">
      
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2.5">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-slate-400/60">
            <circle cx="12" cy="12" r="10"/>
            <path d="M2 12h20"/>
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
          </svg>
          <span className="text-[11px] tracking-[0.15em] text-white/50 font-light">Tracker</span>
        </div>
        <span className="text-[9px] text-white/15 font-mono tabular-nums">{updated}</span>
      </div>

      {/* ISS — readout grid */}
      <div className="mb-5">
        <div className="section-header">
          <span>ISS Position</span>
        </div>
        <div className="readout-grid bg-black/20 p-4 rounded-xl border border-white/5 shadow-inner">
          <div className="flex gap-8">
            <div>
              <div className="label mb-1.5 text-cyan-400/70">Latitude</div>
              <div className="text-[18px] font-mono text-cyan-50 font-light tabular-nums tracking-widest text-shadow-glow">{iss.lat.toFixed(3)}°</div>
            </div>
            <div>
              <div className="label mb-1.5 text-cyan-400/70">Longitude</div>
              <div className="text-[18px] font-mono text-cyan-50 font-light tabular-nums tracking-widest text-shadow-glow">{iss.lng.toFixed(3)}°</div>
            </div>
          </div>
          <div className="text-[9px] text-cyan-400/40 mt-3 font-mono tracking-widest uppercase">27,600 km/h orbital velocity</div>
        </div>
      </div>

      <div className="h-px bg-white/[0.04] mb-4"></div>

      {/* Crypto */}
      <div>
        <div className="section-header">
          <span>Markets</span>
        </div>
        <div className="space-y-3">
          {Object.entries(crypto).map(([symbol, data]) => (
            <div key={symbol} className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-white/[0.02] border border-white/[0.02] hover:bg-white/[0.04] transition-colors">
              <span className="text-[11px] text-white/60 font-medium tracking-widest">{symbol}</span>
              <div className="flex items-center gap-4">
                <span className="text-[13px] font-mono text-white/80 tabular-nums">{formatPrice(data.price)}</span>
                <span className={`text-[10px] font-mono tabular-nums flex items-center tracking-wider w-12 justify-end ${data.change >= 0 ? 'text-emerald-400 drop-shadow-[0_0_5px_rgba(52,211,153,0.5)]' : 'text-red-400 drop-shadow-[0_0_5px_rgba(248,113,113,0.5)]'}`}>
                  <span className={data.change >= 0 ? 'tri-up' : 'tri-down'}></span>
                  {Math.abs(data.change).toFixed(1)}%
                </span>
              </div>
            </div>
          ))}
          {Object.keys(crypto).length === 0 && (
            <div className="text-[11px] text-white/15 animate-pulse font-light tracking-wider">Loading markets...</div>
          )}
        </div>
      </div>
    </div>
  );
}
