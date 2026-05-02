import { useState, useEffect } from 'react';

interface WeatherData {
  city: string;
  temp_c: string;
  feels_like: string;
  humidity: string;
  wind_kmph: string;
  description: string;
  rain_chance: number;
  sunrise: string;
  sunset: string;
  forecast: { time: string; temp_c: string; rain_chance: number; description: string }[];
  updated: string;
}

/* Minimalist SVG weather icons */
function WeatherIcon({ desc, size = 18 }: { desc: string; size?: number }) {
  const d = desc.toLowerCase();
  const s = { width: size, height: size, strokeWidth: 1.5, fill: 'none', stroke: 'currentColor' };

  if (d.includes('rain') || d.includes('drizzle')) {
    return (
      <svg {...s} viewBox="0 0 24 24" className="text-blue-300/60">
        <path d="M16 13a4 4 0 0 1-8 0c0-2.2 4-6 4-6s4 3.8 4 6z" />
        <line x1="8" y1="19" x2="8" y2="21" opacity="0.5" />
        <line x1="12" y1="17" x2="12" y2="21" opacity="0.5" />
        <line x1="16" y1="19" x2="16" y2="21" opacity="0.5" />
      </svg>
    );
  }
  if (d.includes('thunder') || d.includes('storm')) {
    return (
      <svg {...s} viewBox="0 0 24 24" className="text-amber-300/60">
        <polyline points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
      </svg>
    );
  }
  if (d.includes('cloud') || d.includes('overcast')) {
    return (
      <svg {...s} viewBox="0 0 24 24" className="text-white/40">
        <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z" />
      </svg>
    );
  }
  if (d.includes('clear') || d.includes('sunny')) {
    return (
      <svg {...s} viewBox="0 0 24 24" className="text-amber-200/60">
        <circle cx="12" cy="12" r="5" />
        <line x1="12" y1="1" x2="12" y2="3" /><line x1="12" y1="21" x2="12" y2="23" />
        <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" /><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
        <line x1="1" y1="12" x2="3" y2="12" /><line x1="21" y1="12" x2="23" y2="12" />
        <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" /><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
      </svg>
    );
  }
  // Default: partly cloudy
  return (
    <svg {...s} viewBox="0 0 24 24" className="text-white/35">
      <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z" />
    </svg>
  );
}

export default function WeatherPanel() {
  const [data, setData] = useState<WeatherData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const r = await fetch('/api/weather');
        const d = await r.json();
        if (!d.error) setData(d);
      } catch {}
      setLoading(false);
    };
    fetchData();
    const interval = setInterval(fetchData, 120000);
    return () => clearInterval(interval);
  }, []);

  if (loading || !data) {
    return (
      <div className="glass-panel accent-cyan h-full flex flex-col">
        <div className="scanline-effect" />
        <div className="flex items-center gap-2.5 mb-5">
          <WeatherIcon desc="clear" size={16} />
          <span className="text-[11px] tracking-[0.15em] text-white/50 font-light">Weather</span>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-[11px] text-white/15 animate-pulse font-light tracking-wider">Acquiring data...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="glass-panel accent-cyan h-full flex flex-col overflow-hidden">
      <div className="scanline-effect" />
      
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <WeatherIcon desc={data.description} size={16} />
          <span className="text-[11px] tracking-[0.15em] text-white/50 font-light">{data.city}</span>
        </div>
        <span className="text-[9px] text-white/15 font-mono tabular-nums">{data.updated?.slice(0, 5)}</span>
      </div>

      {/* Current Conditions */}
      <div className="flex items-baseline gap-3 mb-1">
        <span className="text-[34px] font-extralight text-white/90 leading-none tabular-nums">{data.temp_c}</span>
        <span className="text-[13px] font-extralight text-white/25">°C</span>
        <span className="text-[11px] text-white/30 font-light capitalize ml-1">{data.description}</span>
      </div>

      <div className="flex gap-6 mb-4 mt-3">
        <div>
          <div className="label mb-1">Feels Like</div>
          <div className="value text-[12px]">{data.feels_like}°</div>
        </div>
        <div>
          <div className="label mb-1">Humidity</div>
          <div className="value text-[12px]">{data.humidity}%</div>
        </div>
        <div>
          <div className="label mb-1">Wind</div>
          <div className="value text-[12px]">{data.wind_kmph} km/h</div>
        </div>
      </div>

      {/* Rain Advisory — left accent border instead of emoji */}
      {data.rain_chance >= 30 && (
        <div className={`alert-border flex items-center gap-2 py-2 mb-3 text-[10px] font-light ${
          data.rain_chance >= 60 
            ? 'border-blue-400/50 text-blue-300/70' 
            : 'border-amber-400/40 text-amber-300/60'
        }`}>
          <span>{data.rain_chance >= 60 ? 'Rain likely — carry an umbrella' : 'Possible rain later'}</span>
          <span className="ml-auto font-mono tabular-nums text-white/30">{data.rain_chance}%</span>
        </div>
      )}

      <div className="h-px bg-white/[0.04] mb-3"></div>

      {/* Forecast */}
      <div className="flex-1 overflow-hidden">
        <div className="section-header">
          <span>Forecast</span>
        </div>
        <div className="flex gap-0">
          {data.forecast.slice(0, 4).map((f, i) => (
            <div key={i} className={`flex-1 text-center py-2 ${i > 0 ? 'border-l border-white/[0.04]' : ''}`}>
              <div className="text-[9px] text-white/20 font-mono mb-1.5 tabular-nums">{f.time}</div>
              <div className="flex justify-center mb-1"><WeatherIcon desc={f.description} size={14} /></div>
              <div className="text-[11px] font-mono text-white/50 tabular-nums">{f.temp_c}°</div>
              {f.rain_chance > 20 && (
                <div className="text-[8px] text-blue-400/40 font-mono mt-1 tabular-nums">{f.rain_chance}%</div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Sunrise/Sunset */}
      <div className="flex gap-6 mt-3 pt-2 border-t border-white/[0.04]">
        <div className="flex items-center gap-2 text-[9px] text-white/20">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-amber-300/40">
            <path d="M17 18a5 5 0 0 0-10 0" /><line x1="12" y1="9" x2="12" y2="2" />
            <line x1="4.22" y1="10.22" x2="5.64" y2="11.64" /><line x1="1" y1="18" x2="3" y2="18" />
            <line x1="21" y1="18" x2="23" y2="18" /><line x1="18.36" y1="11.64" x2="19.78" y2="10.22" />
          </svg>
          <span className="font-mono tabular-nums">{data.sunrise}</span>
        </div>
        <div className="flex items-center gap-2 text-[9px] text-white/20">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-orange-300/40">
            <path d="M17 18a5 5 0 0 0-10 0" /><line x1="12" y1="2" x2="12" y2="9" />
            <line x1="4.22" y1="10.22" x2="5.64" y2="11.64" /><line x1="1" y1="18" x2="3" y2="18" />
            <line x1="21" y1="18" x2="23" y2="18" /><line x1="18.36" y1="11.64" x2="19.78" y2="10.22" />
          </svg>
          <span className="font-mono tabular-nums">{data.sunset}</span>
        </div>
      </div>
    </div>
  );
}
