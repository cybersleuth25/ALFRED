import { useFrame } from "@react-three/fiber";
import { useRef, useMemo } from "react";
import * as THREE from "three";

interface SentinelProps {
  state: "idle" | "listening" | "processing" | "speaking";
}

/* ═══════════════════════════════════════════════
   ALFRED — The Crystal Mind
   
   A sharp geometric diamond that floats, rotates,
   and breathes. Edges glow. Monochrome blue.
   Feels like precision intelligence.
   
   Layers:
   1. Inner crystal — small bright octahedron
   2. Outer crystal — larger wireframe, counter-rotates
   3. Edge glow lines — the "nervous system"
   4. Sparse orbital motes — subtle life
   ═══════════════════════════════════════════════ */

const PRESETS = {
  idle:       { color: "#77aaff", edgeColor: "#ccddff", speed: 0.15, innerSpeed: 0.3,  pulse: 0.012, edgeOpacity: 0.8 },
  listening:  { color: "#66eedd", edgeColor: "#bbffee", speed: 0.08, innerSpeed: 0.15, pulse: 0.02,  edgeOpacity: 0.85 },
  processing: { color: "#ffbb44", edgeColor: "#ffeeaa", speed: 0.6,  innerSpeed: 1.2,  pulse: 0.035, edgeOpacity: 0.95 },
  speaking:   { color: "#aabbff", edgeColor: "#ddeeff", speed: 0.2,  innerSpeed: 0.5,  pulse: 0.025, edgeOpacity: 0.9 },
} as const;

export default function Sentinel({ state }: SentinelProps) {
  const groupRef = useRef<THREE.Group>(null);
  const innerRef = useRef<THREE.Mesh>(null);
  const outerRef = useRef<THREE.LineSegments>(null);
  const motesRef = useRef<THREE.Points>(null);

  const lerped = useRef({
    color: new THREE.Color("#77aaff"),
    edgeColor: new THREE.Color("#ccddff"),
    speed: 0.15,
    innerSpeed: 0.3,
    pulse: 0.012,
    edgeOpacity: 0.6,
    voiceAmp: 0,
  });

  // Outer wireframe crystal — octahedron
  const outerGeom = useMemo(() => {
    const geo = new THREE.OctahedronGeometry(5.0, 0);
    return new THREE.EdgesGeometry(geo);
  }, []);

  // Sparse orbital motes
  const moteCount = 300;
  const moteData = useMemo(() => {
    const pos = new Float32Array(moteCount * 3);
    const vel = new Float32Array(moteCount * 3);
    for (let i = 0; i < moteCount; i++) {
      const r = 5 + Math.random() * 6;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      pos[i * 3 + 2] = r * Math.cos(phi);
      vel[i * 3] = r;
      vel[i * 3 + 1] = theta;
      vel[i * 3 + 2] = 0.0001 + Math.random() * 0.0002;
    }
    return { pos, vel };
  }, []);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    const pre = PRESETS[state] || PRESETS.idle;
    const L = lerped.current;
    const lr = 0.025;

    L.color.lerp(new THREE.Color(pre.color), lr);
    L.edgeColor.lerp(new THREE.Color(pre.edgeColor), lr);
    L.speed += (pre.speed - L.speed) * lr;
    L.innerSpeed += (pre.innerSpeed - L.innerSpeed) * lr;
    L.pulse += (pre.pulse - L.pulse) * lr;
    L.edgeOpacity += (pre.edgeOpacity - L.edgeOpacity) * lr;

    // Voice
    if (state === "speaking") {
      const p = Math.abs(Math.sin(t * 12) * Math.sin(t * 7));
      L.voiceAmp += (p - L.voiceAmp) * 0.2;
    } else {
      L.voiceAmp += (0 - L.voiceAmp) * 0.1;
    }

    // Group: gentle hover
    if (groupRef.current) {
      groupRef.current.position.y = Math.sin(t * 0.4) * 0.15;
    }

    // Inner crystal — solid, glowing
    if (innerRef.current) {
      innerRef.current.rotation.y += L.innerSpeed * 0.004;
      innerRef.current.rotation.x += L.innerSpeed * 0.002;
      const scale = 1.0 + Math.sin(t * 0.8) * L.pulse + L.voiceAmp * 0.08;
      innerRef.current.scale.setScalar(scale);
      const mat = innerRef.current.material as THREE.MeshBasicMaterial;
      mat.color.copy(L.color);
      mat.opacity = 0.85 + L.voiceAmp * 0.15;
    }

    // Outer wireframe — counter-rotate
    if (outerRef.current) {
      outerRef.current.rotation.y -= L.speed * 0.003;
      outerRef.current.rotation.z += L.speed * 0.002;
      outerRef.current.rotation.x = Math.sin(t * 0.3) * 0.1;
      const scale = 1.0 + Math.sin(t * 0.6) * L.pulse * 0.5 + L.voiceAmp * 0.04;
      outerRef.current.scale.setScalar(scale);
      const mat = outerRef.current.material as THREE.LineBasicMaterial;
      mat.color.copy(L.edgeColor);
      mat.opacity = L.edgeOpacity;
    }

    // Motes — slow drift
    if (motesRef.current) {
      const P = moteData.pos;
      const V = moteData.vel;
      for (let i = 0; i < moteCount; i++) {
        const r = V[i * 3];
        V[i * 3 + 1] += V[i * 3 + 2] + L.speed * 0.004;
        const theta = V[i * 3 + 1];
        const phi = Math.acos(((i / moteCount) * 2 - 1) * 0.9);
        P[i * 3] = r * Math.sin(phi) * Math.cos(theta);
        P[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta) * 0.6;
        P[i * 3 + 2] = r * Math.cos(phi);
      }
      motesRef.current.geometry.attributes.position.needsUpdate = true;
      const mat = motesRef.current.material as THREE.PointsMaterial;
      mat.color.copy(L.edgeColor);
    }
  });

  return (
    <group ref={groupRef}>

      {/* Inner crystal — solid glowing octahedron */}
      <mesh ref={innerRef}>
        <octahedronGeometry args={[3.0, 0]} />
        <meshBasicMaterial
          color="#77aaff"
          transparent
          opacity={0.9}
        />
      </mesh>

      {/* Outer wireframe crystal — sharp edges */}
      <lineSegments ref={outerRef} geometry={outerGeom}>
        <lineBasicMaterial
          color="#ccddff"
          transparent
          linewidth={2}
          opacity={0.6}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </lineSegments>

      {/* Sparse ambient motes */}
      <points ref={motesRef}>
        <bufferGeometry>
          {/* @ts-ignore */}
          <bufferAttribute attach="attributes-position" count={moteCount} array={moteData.pos} itemSize={3} />
        </bufferGeometry>
        <pointsMaterial
          color="#ccddff"
          size={0.05}
          transparent
          opacity={0.3}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </points>
    </group>
  );
}
