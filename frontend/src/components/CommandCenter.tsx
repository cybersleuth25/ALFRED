import OsintPanel from './panels/OsintPanel';
import WeatherPanel from './panels/WeatherPanel';
import SystemPanel from './panels/SystemPanel';
import TrackerPanel from './panels/TrackerPanel';
import CivicPanel from './panels/CivicPanel';

interface CommandCenterProps {
  active: boolean;
}

export default function CommandCenter({ active }: CommandCenterProps) {
  return (
    <div className={`absolute inset-0 z-30 pointer-events-none transition-opacity duration-700 ${active ? 'opacity-100' : 'opacity-0'}`}>
      {/* 5-Panel Grid */}
      <div className="w-full h-full grid grid-cols-3 grid-rows-2 gap-4 p-6 pt-24">
        {/* Top-Left: Weather */}
        <div className={`pointer-events-auto transform transition-all duration-700 ease-out ${active ? 'translate-x-0 opacity-100' : '-translate-x-10 opacity-0'}`}
             style={{ transitionDelay: active ? '100ms' : '0ms' }}>
          <WeatherPanel />
        </div>

        {/* Top-Middle: System Vitals */}
        <div className={`pointer-events-auto transform transition-all duration-700 ease-out ${active ? 'translate-x-0 opacity-100' : 'translate-y-10 opacity-0'}`}
             style={{ transitionDelay: active ? '200ms' : '0ms' }}>
          <SystemPanel />
        </div>
        
        {/* Top-Right: Civic Health */}
        <div className={`pointer-events-auto transform transition-all duration-700 ease-out ${active ? 'translate-x-0 opacity-100' : 'translate-x-10 opacity-0'}`}
             style={{ transitionDelay: active ? '250ms' : '0ms' }}>
          <CivicPanel />
        </div>

        {/* Bottom-Left: OSINT Intel */}
        <div className={`pointer-events-auto transform transition-all duration-700 ease-out ${active ? 'translate-x-0 opacity-100' : '-translate-x-10 opacity-0'}`}
             style={{ transitionDelay: active ? '300ms' : '0ms' }}>
          <OsintPanel />
        </div>

        {/* Bottom-Middle: Live Tracker */}
        <div className={`col-span-2 pointer-events-auto transform transition-all duration-700 ease-out ${active ? 'translate-x-0 opacity-100' : 'translate-x-10 opacity-0'}`}
             style={{ transitionDelay: active ? '400ms' : '0ms' }}>
          <TrackerPanel />
        </div>
      </div>
    </div>
  );
}
