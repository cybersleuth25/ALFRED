import { useRef, useMemo, useEffect, useState } from "react";
import { useFrame, Canvas } from "@react-three/fiber";
import * as THREE from "three";
import { OrbitControls, Html, Line } from "@react-three/drei";
import { EffectComposer, Bloom } from "@react-three/postprocessing";

interface GeoMarker {
  lat: number;
  lng: number;
  label: string;
  type: string;
}

interface GeoGlobeProps {
  markers: GeoMarker[];
  onClose: () => void;
}

/* ── Utilities ── */
const GLOBE_RADIUS = 2.2;

function latLngToVec3(lat: number, lng: number, radius: number): THREE.Vector3 {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lng + 180) * (Math.PI / 180);
  return new THREE.Vector3(
    -(radius * Math.sin(phi) * Math.cos(theta)),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta)
  );
}

/* ── Simplified World Continent Outlines ── */
// Highly simplified polygon outlines for all major continents
const CONTINENT_DATA: number[][][] = [
  // North America
  [[-130,55],[-125,60],[-120,60],[-110,65],[-100,65],[-90,70],[-80,70],[-70,65],[-60,55],[-65,45],[-70,44],[-70,40],[-75,35],[-80,30],[-85,30],[-90,28],[-95,28],[-100,25],[-105,20],[-100,18],[-90,15],[-85,10],[-80,8],[-80,15],[-82,20],[-85,25],[-90,30],[-100,32],[-110,35],[-120,40],[-125,50],[-130,55]],
  // South America
  [[-80,8],[-75,10],[-70,12],[-60,10],[-55,5],[-50,0],[-45,-5],[-40,-10],[-38,-15],[-38,-20],[-42,-23],[-45,-25],[-48,-28],[-50,-30],[-55,-35],[-60,-38],[-65,-40],[-68,-46],[-70,-50],[-73,-53],[-75,-50],[-72,-45],[-70,-40],[-70,-35],[-72,-30],[-72,-25],[-75,-20],[-78,-15],[-80,-5],[-80,0],[-78,5],[-80,8]],
  // Europe
  [[-10,35],[-5,36],[0,38],[5,40],[5,43],[3,46],[0,48],[-5,48],[-8,44],[-10,40],[-10,35]],
  [[-5,48],[0,48],[2,51],[5,52],[8,54],[12,55],[15,55],[20,55],[25,58],[28,60],[30,62],[32,65],[30,70],[25,70],[20,68],[15,62],[12,57],[8,54],[5,52],[2,51],[0,48],[-5,48]],
  // Italy+Greece peninsula
  [[10,46],[12,44],[14,42],[16,40],[15,38],[18,37],[20,38],[22,37],[25,38],[28,40],[30,42],[28,45],[25,45],[22,42],[20,40],[18,40],[16,42],[14,46],[10,46]],
  // Africa
  [[-15,30],[-10,32],[-5,35],[0,35],[5,37],[10,37],[12,35],[10,32],[10,28],[12,25],[15,22],[18,20],[20,18],[22,15],[25,12],[30,10],[35,10],[40,12],[42,10],[45,12],[50,10],[50,5],[48,0],[42,-5],[40,-10],[38,-15],[35,-20],[33,-25],[30,-30],[28,-32],[25,-34],[20,-35],[18,-32],[17,-28],[15,-25],[12,-18],[10,-10],[8,-5],[5,0],[5,5],[2,6],[0,5],[-5,5],[-10,5],[-15,8],[-17,12],[-18,15],[-18,20],[-17,25],[-15,30]],
  // Asia (simplified outline)
  [[30,42],[35,40],[40,38],[42,37],[45,35],[48,30],[50,25],[55,22],[60,25],[65,25],[68,22],[70,20],[75,15],[78,10],[80,8],[82,15],[85,20],[88,22],[90,22],[92,20],[95,18],[100,15],[103,5],[105,0],[108,-5],[110,-8],[115,-8],[120,0],[120,5],[115,10],[110,15],[108,18],[105,22],[102,18],[100,22],[98,20],[95,25],[90,28],[88,28],[85,28],[80,30],[75,35],[70,38],[65,40],[60,42],[55,45],[50,48],[45,42],[42,42],[38,45],[35,42],[30,42]],
  // Asia (northern stretch - Russia)
  [[30,62],[35,60],[40,55],[45,50],[50,52],[55,55],[60,58],[70,60],[80,62],[90,65],[100,68],[110,70],[120,68],[130,65],[140,60],[145,55],[150,58],[155,55],[160,58],[170,62],[180,65]],
  [[180,65],[170,68],[160,70],[150,72],[140,70],[130,70],[120,72],[110,72],[100,70],[90,68],[80,68],[70,65],[60,62],[50,55],[45,50],[40,55],[35,60],[30,62]],
  // India subcontinent
  [[68,25],[70,28],[72,30],[75,30],[78,28],[80,25],[80,20],[78,15],[77,10],[78,8],[80,12],[82,15],[85,22],[88,22],[90,22],[92,18],[88,15],[85,10],[82,8],[80,8],[78,8],[77,10],[75,12],[72,18],[70,22],[68,25]],
  // Southeast Asia / Indonesia
  [[100,5],[105,0],[106,-2],[108,-5],[110,-8],[112,-8],[115,-5],[118,-2],[120,2],[118,5],[115,5],[112,3],[108,2],[105,5],[100,5]],
  // Japan
  [[130,32],[132,34],[134,35],[136,36],[138,38],[140,40],[142,43],[140,45],[138,43],[136,40],[134,38],[132,36],[130,32]],
  // Australia
  [[115,-35],[120,-35],[125,-33],[130,-32],[132,-14],[135,-12],[138,-15],[140,-18],[142,-15],[145,-18],[148,-20],[150,-24],[152,-28],[153,-30],[150,-35],[148,-38],[145,-39],[140,-38],[135,-35],[130,-34],[125,-33],[120,-35],[115,-35]],
  // New Zealand
  [[172,-35],[174,-37],[176,-38],[178,-42],[176,-46],[172,-44],[170,-42],[170,-38],[172,-35]],
  // UK + Ireland
  [[-6,50],[-5,52],[-3,55],[-5,57],[-3,58],[-2,57],[0,52],[0,51],[-2,50],[-6,50]],
  [[-10,52],[-8,54],[-6,55],[-7,52],[-10,52]],
  // Scandinavia
  [[5,58],[8,60],[10,62],[12,65],[15,68],[18,70],[20,70],[22,68],[25,65],[28,62],[30,62],[25,58],[20,56],[15,56],[10,58],[5,58]],
  // Madagascar
  [[44,-13],[46,-16],[48,-20],[48,-24],[46,-26],[44,-24],[44,-20],[43,-17],[44,-13]],
  // Greenland
  [[-55,60],[-50,62],[-45,65],[-40,68],[-35,72],[-30,75],[-25,78],[-20,80],[-25,82],[-30,82],[-40,80],[-45,78],[-50,75],[-55,70],[-55,60]],
  // Lat grid lines (equator + tropics)
];

/* ── Continent Wireframe Component ── */
function ContinentOutlines({ radius = GLOBE_RADIUS }: { radius?: number }) {
  const lines = useMemo(() => {
    return CONTINENT_DATA.map((coords) => {
      const points = coords.map(([lng, lat]) => latLngToVec3(lat, lng, radius * 1.002));
      return points;
    });
  }, [radius]);

  return (
    <group>
      {lines.map((pts, i) => (
        <Line
          key={i}
          points={pts}
          color="#00ccff"
          lineWidth={1.2}
          transparent
          opacity={0.7}
          toneMapped={false}
        />
      ))}
    </group>
  );
}

/* ── Latitude/Longitude Grid ── */
function GlobeGrid({ radius = GLOBE_RADIUS }: { radius?: number }) {
  const lines = useMemo(() => {
    const result: THREE.Vector3[][] = [];
    // Latitude lines every 30 degrees
    for (let lat = -60; lat <= 60; lat += 30) {
      const points: THREE.Vector3[] = [];
      for (let lng = -180; lng <= 180; lng += 5) {
        points.push(latLngToVec3(lat, lng, radius * 1.001));
      }
      result.push(points);
    }
    // Longitude lines every 30 degrees
    for (let lng = -180; lng < 180; lng += 30) {
      const points: THREE.Vector3[] = [];
      for (let lat = -90; lat <= 90; lat += 5) {
        points.push(latLngToVec3(lat, lng, radius * 1.001));
      }
      result.push(points);
    }
    return result;
  }, [radius]);

  return (
    <group>
      {lines.map((pts, i) => (
        <Line
          key={i}
          points={pts}
          color="#1a3a5c"
          lineWidth={0.5}
          transparent
          opacity={0.3}
          toneMapped={false}
        />
      ))}
    </group>
  );
}

/* ── Holographic Globe Shell ── */
function HologramGlobe({ radius = GLOBE_RADIUS }: { radius?: number }) {
  return (
    <group>
      {/* Atmospheric edge glow (BackSide) */}
      <mesh>
        <sphereGeometry args={[radius * 1.08, 64, 64]} />
        <meshBasicMaterial
          color="#00aaff"
          transparent
          opacity={0.08}
          side={THREE.BackSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>

      {/* Mid glow layer */}
      <mesh>
        <sphereGeometry args={[radius * 1.04, 64, 64]} />
        <meshBasicMaterial
          color="#0088cc"
          transparent
          opacity={0.12}
          side={THREE.BackSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>

      {/* Dark Ocean Core */}
      <mesh>
        <sphereGeometry args={[radius, 64, 64]} />
        <meshBasicMaterial
          color="#050d18"
          transparent
          opacity={0.95}
        />
      </mesh>
    </group>
  );
}

/* ── Orbital Data Rings ── */
function OrbitalRings({ radius = GLOBE_RADIUS }: { radius?: number }) {
  const ringGroup = useRef<THREE.Group>(null);

  useFrame((_, delta) => {
    if (ringGroup.current) {
      ringGroup.current.children[0].rotation.x += delta * 0.2;
      ringGroup.current.children[0].rotation.y += delta * 0.3;
      ringGroup.current.children[1].rotation.y -= delta * 0.15;
      ringGroup.current.children[1].rotation.z -= delta * 0.4;
      ringGroup.current.children[2].rotation.x += delta * 0.5;
    }
  });

  return (
    <group ref={ringGroup}>
      <mesh rotation={[Math.PI / 4, 0, 0]}>
        <torusGeometry args={[radius * 1.3, 0.005, 16, 100]} />
        <meshBasicMaterial color="#00ffcc" transparent opacity={0.3} blending={THREE.AdditiveBlending} toneMapped={false} />
      </mesh>
      <mesh rotation={[0, Math.PI / 3, Math.PI / 6]}>
        <torusGeometry args={[radius * 1.15, 0.003, 16, 100]} />
        <meshBasicMaterial color="#4488ff" transparent opacity={0.2} blending={THREE.AdditiveBlending} toneMapped={false} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[radius * 1.5, 0.002, 16, 100]} />
        <meshBasicMaterial color="#ffffff" transparent opacity={0.1} blending={THREE.AdditiveBlending} toneMapped={false} />
      </mesh>
    </group>
  );
}

/* ── Geo Laser Pin ── */
function GeoLaserPin({ marker, radius = GLOBE_RADIUS }: { marker: GeoMarker; radius?: number }) {
  const pos = useMemo(() => latLngToVec3(marker.lat, marker.lng, radius), [marker.lat, marker.lng, radius]);
  const normal = useMemo(() => pos.clone().normalize(), [pos]);
  const laserLength = 0.45;
  const laserEnd = useMemo(() => pos.clone().add(normal.clone().multiplyScalar(laserLength)), [pos, normal]);
  const laserGeo = useMemo(() => new THREE.BufferGeometry().setFromPoints([pos, laserEnd]), [pos, laserEnd]);

  // Pulsating dot
  const dotRef = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => {
    if (dotRef.current) {
      const s = 1 + Math.sin(clock.getElapsedTime() * 3) * 0.3;
      dotRef.current.scale.setScalar(s);
    }
  });

  return (
    <group>
      {/* Surface pulse dot */}
      <mesh ref={dotRef} position={pos}>
        <sphereGeometry args={[0.025, 8, 8]} />
        <meshBasicMaterial color="#00ffcc" toneMapped={false} />
      </mesh>

      {/* Laser beam */}
      <primitive object={new THREE.Line(laserGeo, new THREE.LineBasicMaterial({ color: "#00ffcc", transparent: true, opacity: 0.6, blending: THREE.AdditiveBlending }))} />

      {/* HUD Label */}
      <Html position={laserEnd} occlude={false} zIndexRange={[100, 0]}>
        <div style={{
          background: "rgba(0, 15, 30, 0.8)",
          border: "1px solid rgba(0, 255, 204, 0.35)",
          padding: "3px 7px",
          color: "#00ffcc",
          fontSize: "8px",
          fontFamily: "'Courier New', monospace",
          letterSpacing: "0.12em",
          whiteSpace: "nowrap",
          transform: "translate3d(12px, -12px, 0)",
          pointerEvents: "none",
          boxShadow: "0 0 8px rgba(0,255,204,0.15)",
          textTransform: "uppercase",
          borderLeft: "2px solid #00ffcc",
          display: "flex",
          flexDirection: "column",
          gap: "1px"
        }}>
          <span style={{ fontWeight: 700, fontSize: "8px" }}>{marker.label}</span>
          <span style={{ fontSize: "6px", color: "rgba(0,255,204,0.4)" }}>
            {marker.lat.toFixed(1)}° {marker.lat >= 0 ? "N" : "S"} / {Math.abs(marker.lng).toFixed(1)}° {marker.lng >= 0 ? "E" : "W"}
          </span>
        </div>
      </Html>
    </group>
  );
}

/* ── Flight Arc ── */
function HolographicFlightArc({ startGeo, endGeo, radius = GLOBE_RADIUS }: { startGeo: GeoMarker; endGeo: GeoMarker; radius?: number }) {
  const lineRef = useRef<any>(null);

  const curve = useMemo(() => {
    const start = latLngToVec3(startGeo.lat, startGeo.lng, radius);
    const end = latLngToVec3(endGeo.lat, endGeo.lng, radius);
    const mid = start.clone().lerp(end, 0.5);
    const dist = start.distanceTo(end);
    mid.normalize().multiplyScalar(radius + dist * 0.35);
    return new THREE.QuadraticBezierCurve3(start, mid, end);
  }, [startGeo, endGeo, radius]);

  const points = useMemo(() => curve.getPoints(50), [curve]);

  useFrame((_, delta) => {
    if (lineRef.current?.material) {
      lineRef.current.material.dashOffset -= delta * 0.5;
    }
  });

  return (
    <Line
      ref={lineRef}
      points={points}
      color="#00eeff"
      lineWidth={2}
      transparent
      opacity={0.9}
      dashed
      dashScale={8}
      dashSize={1.5}
      dashOffset={0}
      toneMapped={false}
    />
  );
}

/* ── Scene (auto-rotates) ── */
function GlobeScene({ markers }: { markers: GeoMarker[] }) {
  const groupRef = useRef<THREE.Group>(null);

  useFrame((_, delta) => {
    if (groupRef.current) {
      groupRef.current.rotation.y += delta * 0.08;
    }
  });

  const hub = markers.length > 0 ? markers[0] : null;
  const arcs = useMemo(() => {
    if (!hub || markers.length <= 1) return [];
    return markers.slice(1).map(m => ({ start: hub, end: m }));
  }, [markers, hub]);

  return (
    <>
      <ambientLight intensity={0.3} />
      <OrbitControls
        enableZoom
        enablePan={false}
        autoRotate={false}
        minDistance={3.5}
        maxDistance={10}
      />

      <group ref={groupRef}>
        <HologramGlobe />
        <ContinentOutlines />
        <GlobeGrid />

        {markers.map((m, i) => (
          <GeoLaserPin key={i} marker={m} />
        ))}

        {arcs.map((arc, i) => (
          <HolographicFlightArc key={i} startGeo={arc.start} endGeo={arc.end} />
        ))}
      </group>

      <OrbitalRings />

      <EffectComposer>
        <Bloom luminanceThreshold={0.1} luminanceSmoothing={0.9} intensity={1.2} mipmapBlur />
      </EffectComposer>
    </>
  );
}

/* ── Main Export ── */
export default function GeoGlobe({ markers, onClose }: GeoGlobeProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setVisible(true), 50);
    return () => clearTimeout(timer);
  }, []);

  const handleClose = () => {
    setVisible(false);
    setTimeout(onClose, 400);
  };

  return (
    <div
      className="geo-globe-container"
      style={{
        position: "absolute",
        top: "50px",
        right: "30px",
        width: "420px",
        height: "420px",
        zIndex: 35,
        opacity: visible ? 1 : 0,
        transform: visible ? "scale(1) translateY(0)" : "scale(0.8) translateY(20px)",
        transition: "all 0.4s cubic-bezier(0.16, 1, 0.3, 1)",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "16px",
          background: "linear-gradient(145deg, rgba(4,10,25,0.9) 0%, rgba(8,16,35,0.75) 100%)",
          border: "1px solid rgba(0,170,255,0.12)",
          borderTop: "1px solid rgba(0,170,255,0.25)",
          backdropFilter: "blur(24px)",
          overflow: "hidden",
          boxShadow: "0 24px 60px rgba(0,0,0,0.7), inset 0 1px 0 rgba(0,200,255,0.05)"
        }}
      >
        {/* Header */}
        <div style={{ padding: "14px 18px 0", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <div style={{
              width: "5px", height: "5px",
              background: "#00ccff",
              boxShadow: "0 0 8px #00ccff, 0 0 16px rgba(0,200,255,0.3)",
              borderRadius: "50%",
              animation: "pulse-glow 2s ease-in-out infinite"
            }} />
            <span style={{
              fontSize: "9px", letterSpacing: "0.25em",
              color: "rgba(255,255,255,0.4)", fontWeight: 600,
              textTransform: "uppercase", fontFamily: "'Courier New', monospace"
            }}>
              GEO INTELLIGENCE
            </span>
            <span style={{
              fontSize: "9px", color: "#00ccff", fontWeight: 700,
              background: "rgba(0,200,255,0.08)",
              padding: "2px 6px", borderRadius: "3px",
              border: "1px solid rgba(0,200,255,0.15)"
            }}>
              {markers.length}
            </span>
          </div>
          <button
            onClick={handleClose}
            style={{
              background: "none", border: "1px solid rgba(255,255,255,0.08)",
              color: "rgba(255,255,255,0.3)", cursor: "pointer",
              fontSize: "14px", padding: "2px 8px", lineHeight: 1,
              borderRadius: "4px", transition: "all 0.2s"
            }}
            onMouseOver={e => { e.currentTarget.style.color = "#00ccff"; e.currentTarget.style.borderColor = "rgba(0,200,255,0.3)"; }}
            onMouseOut={e => { e.currentTarget.style.color = "rgba(255,255,255,0.3)"; e.currentTarget.style.borderColor = "rgba(255,255,255,0.08)"; }}
          >
            ×
          </button>
        </div>

        {/* 3D Canvas */}
        <div style={{ width: "100%", height: "320px", marginTop: "6px" }}>
          <Canvas camera={{ position: [0, 1.5, 5.5], fov: 45 }} style={{ background: "transparent" }}>
            <GlobeScene markers={markers} />
          </Canvas>
        </div>

        {/* Footer */}
        <div style={{
          position: "absolute", bottom: "10px", left: "18px", right: "18px",
          display: "flex", justifyContent: "space-between", alignItems: "center"
        }}>
          <div style={{ fontSize: "7px", color: "rgba(0,200,255,0.25)", letterSpacing: "0.2em", fontFamily: "'Courier New', monospace" }}>
            UPLINK ● AES-256 ● ORBITAL
          </div>
          <div style={{
            width: "60px", height: "1px",
            background: "linear-gradient(90deg, transparent, rgba(0,200,255,0.3), transparent)"
          }} />
        </div>
      </div>
    </div>
  );
}
