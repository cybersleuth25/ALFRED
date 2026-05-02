import { useEffect, useState, useRef } from "react";
import Map, { Marker, Popup } from "react-map-gl";
import "maplibre-gl/dist/maplibre-gl.css";

export default function LiveMap() {
  const [features, setFeatures] = useState<any[]>([]);
  const [stats, setStats] = useState({ aircraft: 0, vehicles: 0 });
  const mapRef = useRef<any>(null);

  useEffect(() => {
    // WebSocket connection to FastAPI backend
    const ws = new WebSocket("ws://localhost:8000/ws/live");
    
    ws.onmessage = (event) => {
      try {
        const geojson = JSON.parse(event.data);
        if (geojson.features) {
          setFeatures(geojson.features);
          // Update stats
          setStats({
            aircraft: geojson.features.filter((f: any) => f.properties.category === "aircraft").length,
            vehicles: geojson.features.filter((f: any) => f.properties.category === "vehicles" || f.properties.category === "vehicle").length,
          });
        }
      } catch (e) {
        console.error("GeoJSON parse error", e);
      }
    };

    return () => {
      ws.close();
    };
  }, []);

  const [hoverInfo, setHoverInfo] = useState<any>(null);

  return (
    <div className="absolute inset-0 z-0 flex">
      <Map
        ref={mapRef}
        initialViewState={{
          longitude: 78.9629,
          latitude: 20.5937,
          zoom: 3.5,
          pitch: 30
        }}
        mapStyle="https://tiles.openfreemap.org/styles/dark"
        style={{ width: "100%", height: "100%", background: "#060606" }}
        attributionControl={false}
      >
        {/* Render Aircraft and Vehicles */}
        {features.map((feature, idx) => {
            const isAircraft = feature.properties.category === "aircraft";
            const [lon, lat] = feature.geometry.coordinates;

            // Simple altitude-based coloring for aircraft
            let color = "#00d4ff"; // default vehicle
            let radius = 4;
            
            if (isAircraft) {
                radius = 8;
                const alt = feature.properties.altitude || 0;
                if (alt < 5000) color = "#00ff88"; // green
                else if (alt < 10000) color = "#ffaa00"; // orange
                else color = "#ff0044"; // red
            }

            return (
                <Marker
                    key={`marker-${idx}`}
                    longitude={lon}
                    latitude={lat}
                    anchor="center"
                    onClick={(e: any) => {
                        e.originalEvent.stopPropagation();
                        setHoverInfo(feature);
                    }}
                >
                    <div 
                        style={{
                            width: radius * 2,
                            height: radius * 2,
                            backgroundColor: color,
                            borderRadius: "50%",
                            opacity: 0.8,
                            border: isAircraft ? "1px solid #fff" : "none",
                            cursor: "pointer",
                            boxShadow: "0 0 10px " + color
                        }}
                        onMouseEnter={() => setHoverInfo(feature)}
                        onMouseLeave={() => setHoverInfo(null)}
                    />
                </Marker>
            );
        })}

        {hoverInfo && (
            <Popup
                longitude={hoverInfo.geometry.coordinates[0]}
                latitude={hoverInfo.geometry.coordinates[1]}
                anchor="bottom"
                onClose={() => setHoverInfo(null)}
                closeButton={false}
                closeOnClick={false}
                className="z-[2000]"
            >
                <div className="text-black p-1 text-xs font-mono">
                    <strong>{hoverInfo.properties.category.toUpperCase()}</strong><br/>
                    {hoverInfo.properties.category === "aircraft" && <>
                        Callsign: {hoverInfo.properties.callsign}<br/>
                        Alt: {hoverInfo.properties.altitude}m<br/>
                        SPD: {hoverInfo.properties.velocity}m/s
                    </>}
                    {hoverInfo.properties.category !== "aircraft" && <>
                        Source: {hoverInfo.properties.source}<br/>
                        Conf: {(hoverInfo.properties.confidence * 100).toFixed(1)}%
                    </>}
                </div>
            </Popup>
        )}
      </Map>

      {/* Surveillance HUD Overlay - Cinematic Glassmorphism */}
      <div className="absolute top-12 left-12 z-[1000] bg-white/5 backdrop-blur-2xl text-white/90 px-8 py-6 rounded-3xl border border-white/10 font-sans font-light text-sm pointer-events-auto shadow-2xl">
        <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-[#00ffcc] shadow-[0_0_15px_#00ffcc] animate-pulse"></div>
                <span className="tracking-[0.2em] font-medium text-xs opacity-80">GLOBAL SYNC</span>
            </div>
        </div>
        <div className="space-y-4">
          <div className="flex justify-between items-center gap-8">
              <span className="opacity-60 text-xs tracking-wider uppercase">Aircraft</span>
              <span className="text-xl font-light">{stats.aircraft}</span>
          </div>
          <div className="w-full h-px bg-white/10"></div>
          <div className="flex justify-between items-center gap-8">
              <span className="opacity-60 text-xs tracking-wider uppercase">Vehicles</span>
              <span className="text-xl font-light">{stats.vehicles}</span>
          </div>
        </div>
        <div className="text-[9px] opacity-40 mt-8 tracking-widest uppercase">OpenSky Network • Vision AI</div>
      </div>
    </div>
  );
}
