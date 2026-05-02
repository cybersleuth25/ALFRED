import { useState, useEffect } from 'react';

interface SystemData {
  cpu: number;
  ram_used: number;
  ram_total: number;
  ram_percent: number;
  disk_used: number;
  disk_total: number;
  disk_percent: number;
  net_sent: number;
  net_recv: number;
  battery: { percent: number; plugged: boolean } | null;
  top_procs: { name: string; mem: number; cpu: number }[];
}

function Bar({ label, pct }: { label: string; pct: number }) {
  const barClass = pct > 85 ? 'bar-gradient-danger' : pct > 60 ? 'bar-gradient-warn' : 'bar-gradient-normal';
  return (
    <div className="flex items-center gap-3 mb-3">
      <span className="label w-8 shrink-0">{label}</span>
      <div className="flex-1 h-[5px] bg-white/[0.04] rounded-full overflow-hidden">
        <div 
          className={`h-full rounded-full transition-all duration-[1500ms] ease-out ${barClass}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className="text-[10px] font-mono text-white/40 w-9 text-right tabular-nums">{pct}%</span>
    </div>
  );
}

/* CSS-drawn battery icon */
function BatteryIcon({ percent, plugged }: { percent: number; plugged: boolean }) {
  const color = percent <= 20 ? '#ff4466' : plugged ? '#00e8c6' : '#7b8cde';
  return (
    <div className="relative flex items-center" style={{ width: 20, height: 10 }}>
      <div className="w-[16px] h-[8px] border border-white/20 rounded-[2px] relative overflow-hidden">
        <div 
          className="absolute left-0 top-0 bottom-0 rounded-[1px] transition-all duration-1000"
          style={{ width: `${percent}%`, background: color }}
        />
      </div>
      <div className="w-[2px] h-[4px] bg-white/20 rounded-r-[1px]" />
      {plugged && (
        <svg width="6" height="8" viewBox="0 0 10 16" className="absolute left-[5px]" fill={color} opacity="0.8">
          <polygon points="6,0 2,7 5,7 4,16 8,9 5,9" />
        </svg>
      )}
    </div>
  );
}

export default function SystemPanel() {
  const [data, setData] = useState<SystemData | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const r = await fetch('/api/system');
        const d = await r.json();
        setData(d);
      } catch {}
    };
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, []);

  if (!data) {
    return (
      <div className="glass-panel accent-amber h-full flex items-center justify-center">
        <div className="scanline-effect" />
        <div className="text-[11px] text-white/15 animate-pulse font-light tracking-wider">Connecting...</div>
      </div>
    );
  }

  return (
    <div className="glass-panel accent-amber h-full flex flex-col overflow-hidden">
      <div className="scanline-effect" />
      
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2.5">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-emerald-400/60">
            <rect x="4" y="4" width="16" height="16" rx="2"/>
            <rect x="9" y="9" width="6" height="6" rx="1" opacity="0.5"/>
          </svg>
          <span className="text-[11px] tracking-[0.15em] text-white/50 font-light">System</span>
        </div>
        <div className="w-1.5 h-1.5 rounded-full bg-emerald-400/60 status-breathe text-emerald-400"></div>
      </div>

      <Bar label="CPU" pct={data.cpu} />
      <Bar label="RAM" pct={data.ram_percent} />
      <Bar label="Disk" pct={data.disk_percent} />

      {/* Battery with CSS icon */}
      {data.battery && (
        <div className="flex items-center gap-3 mb-3 mt-1">
          <span className="label w-8 shrink-0">Batt</span>
          <div className="flex-1 h-[5px] bg-white/[0.04] rounded-full overflow-hidden">
            <div 
              className={`h-full rounded-full transition-all duration-[1500ms] ease-out ${
                data.battery.percent <= 20 ? 'bar-gradient-danger' : data.battery.plugged ? 'bar-gradient-normal' : 'bar-gradient-normal'
              }`}
              style={{ width: `${data.battery.percent}%` }}
            />
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-mono text-white/40 tabular-nums">{data.battery.percent}%</span>
            <BatteryIcon percent={data.battery.percent} plugged={data.battery.plugged} />
          </div>
        </div>
      )}

      <div className="flex gap-6 mt-2 mb-4">
        <div>
          <div className="label mb-1">Upload</div>
          <div className="value text-[11px]">{data.net_sent} MB</div>
        </div>
        <div>
          <div className="label mb-1">Download</div>
          <div className="value text-[11px]">{data.net_recv} MB</div>
        </div>
      </div>

      <div className="h-px bg-white/[0.04] mb-3"></div>

      <div className="flex-1 overflow-hidden">
        <div className="section-header">
          <span>Processes</span>
        </div>
        {data.top_procs.map((p, i) => (
          <div key={i} className={`flex items-center justify-between text-[10px] py-1.5 px-2 row-alt`}>
            <span className="text-white/35 truncate flex-1 mr-3 font-light">{p.name}</span>
            <span className="font-mono text-white/20 text-[9px] tabular-nums">{p.mem}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
