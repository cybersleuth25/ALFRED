import { useFrame } from "@react-three/fiber";
import { useRef, useMemo } from "react";
import * as THREE from "three";

interface OrbProps {
  state: "idle" | "listening" | "processing" | "speaking";
}

/* ─────────────────────────────────────────────
   GLSL: Smooth plasma core with gentle distortion
   ───────────────────────────────────────────── */
const coreVertex = `
  uniform float uTime;
  uniform float uDistortion;
  varying vec3 vNormal;
  varying vec3 vWorldPos;
  varying float vFresnel;

  // Smooth simplex noise
  vec3 mod289(vec3 x){return x-floor(x*(1./289.))*289.;}
  vec4 mod289(vec4 x){return x-floor(x*(1./289.))*289.;}
  vec4 permute(vec4 x){return mod289(((x*34.)+1.)*x);}
  vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-.85373472095314*r;}
  float snoise(vec3 v){
    const vec2 C=vec2(1./6.,1./3.);const vec4 D=vec4(0.,.5,1.,2.);
    vec3 i=floor(v+dot(v,C.yyy));vec3 x0=v-i+dot(i,C.xxx);
    vec3 g=step(x0.yzx,x0.xyz);vec3 l=1.-g;
    vec3 i1=min(g.xyz,l.zxy);vec3 i2=max(g.xyz,l.zxy);
    vec3 x1=x0-i1+C.xxx;vec3 x2=x0-i2+C.yyy;vec3 x3=x0-D.yyy;
    i=mod289(i);
    vec4 p=permute(permute(permute(i.z+vec4(0.,i1.z,i2.z,1.))+i.y+vec4(0.,i1.y,i2.y,1.))+i.x+vec4(0.,i1.x,i2.x,1.));
    float n_=.142857142857;vec3 ns=n_*D.wyz-D.xzx;
    vec4 j=p-49.*floor(p*ns.z*ns.z);vec4 x_=floor(j*ns.z);vec4 y_=floor(j-7.*x_);
    vec4 x=x_*ns.x+ns.yyyy;vec4 y=y_*ns.x+ns.yyyy;vec4 h=1.-abs(x)-abs(y);
    vec4 b0=vec4(x.xy,y.xy);vec4 b1=vec4(x.zw,y.zw);
    vec4 s0=floor(b0)*2.+1.;vec4 s1=floor(b1)*2.+1.;
    vec4 sh=-step(h,vec4(0.));
    vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy;vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
    vec3 p0=vec3(a0.xy,h.x);vec3 p1=vec3(a0.zw,h.y);vec3 p2=vec3(a1.xy,h.z);vec3 p3=vec3(a1.zw,h.w);
    vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));
    p0*=norm.x;p1*=norm.y;p2*=norm.z;p3*=norm.w;
    vec4 m=max(.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.);m=m*m;
    return 42.*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));
  }

  void main(){
    vNormal = normalize(normalMatrix * normal);
    vec3 worldNorm = normalize((modelMatrix * vec4(normal, 0.0)).xyz);
    vec3 worldPos = (modelMatrix * vec4(position, 1.0)).xyz;
    vec3 viewDir = normalize(cameraPosition - worldPos);
    vFresnel = pow(1.0 - max(dot(viewDir, worldNorm), 0.0), 2.5);
    
    // Very gentle surface breathing
    float n = snoise(position * 1.2 + uTime * 0.15) * 0.4
            + snoise(position * 2.5 - uTime * 0.1) * 0.15;
    vec3 displaced = position + normal * n * uDistortion;
    vWorldPos = displaced;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
  }
`;

const coreFragment = `
  uniform vec3 uColor1;
  uniform vec3 uColor2;
  uniform float uTime;
  varying vec3 vNormal;
  varying vec3 vWorldPos;
  varying float vFresnel;

  void main(){
    // Soft gradient based on vertical position
    float grad = smoothstep(-4.0, 4.0, vWorldPos.y);
    vec3 base = mix(uColor1, uColor2, grad);
    
    // Fresnel edge glow
    vec3 rimColor = uColor2 * 2.5; // Brighter rim
    base = mix(base, rimColor, vFresnel * 0.9);
    
    // Stronger inner glow
    float core = smoothstep(0.8, 0.0, vFresnel) * 0.4;
    base += core;
    
    float alpha = 0.85 + vFresnel * 0.15; // Higher base opacity
    gl_FragColor = vec4(base, alpha);
  }
`;

/* ─────────────────────────────────────────────
   Aura: Soft outer halo
   ───────────────────────────────────────────── */
const auraVertex = `
  varying vec3 vNormal;
  void main(){
    vNormal = normalize(normalMatrix * normal);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;
const auraFragment = `
  uniform vec3 uColor;
  uniform float uOpacity;
  varying vec3 vNormal;
  void main(){
    float rim = pow(0.75 - dot(vNormal, vec3(0,0,1)), 2.5); // Wider spread
    gl_FragColor = vec4(uColor, rim * uOpacity * 1.5); // Brighter aura
  }
`;

/* ─────────────────────────────────────────────
   State presets: calm color palettes
   ───────────────────────────────────────────── */
const PRESETS = {
  idle:       { c1: [0.00, 0.30, 0.80], c2: [0.00, 0.80, 1.00], aura: [0.00, 0.50, 1.00], dist: 0.30, pSpeed: 0.002 },
  listening:  { c1: [0.00, 0.80, 0.40], c2: [0.20, 1.00, 0.60], aura: [0.00, 1.00, 0.50], dist: 0.45, pSpeed: 0.005 },
  processing: { c1: [0.80, 0.00, 0.50], c2: [1.00, 0.50, 0.00], aura: [1.00, 0.20, 0.20], dist: 0.65, pSpeed: 0.010 },
  speaking:   { c1: [0.50, 0.20, 1.00], c2: [1.00, 1.00, 1.00], aura: [0.70, 0.40, 1.00], dist: 0.50, pSpeed: 0.004 },
} as const;

export default function Orb({ state }: OrbProps) {
  const coreRef = useRef<THREE.Mesh>(null);
  const auraRef = useRef<THREE.Mesh>(null);
  const dustRef = useRef<THREE.Points>(null);
  const ringRef = useRef<THREE.Points>(null);

  // ── Smooth interpolation state ──
  const lerped = useRef({
    dist: 0.25,
    c1: new THREE.Color(0.06, 0.10, 0.28),
    c2: new THREE.Color(0.15, 0.30, 0.70),
    aura: new THREE.Color(0.10, 0.18, 0.50),
    pSpeed: 0.0012,
  });

  // ── Core material ──
  const coreMat = useMemo(() => new THREE.ShaderMaterial({
    vertexShader: coreVertex,
    fragmentShader: coreFragment,
    uniforms: {
      uTime: { value: 0 },
      uDistortion: { value: 0.30 },
      uColor1: { value: new THREE.Color(0.00, 0.30, 0.80) },
      uColor2: { value: new THREE.Color(0.00, 0.80, 1.00) },
    },
    transparent: true,
  }), []);

  // ── Aura material ──
  const auraMat = useMemo(() => new THREE.ShaderMaterial({
    vertexShader: auraVertex,
    fragmentShader: auraFragment,
    uniforms: {
      uColor: { value: new THREE.Color(0.00, 0.50, 1.00) },
      uOpacity: { value: 0.5 },
    },
    transparent: true,
    side: THREE.BackSide,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  }), []);

  // ── Ambient dust (small count, slow drift) ──
  const dustCount = 4000;
  const dustData = useMemo(() => {
    const pos = new Float32Array(dustCount * 3);
    const col = new Float32Array(dustCount * 3);
    const vel = new Float32Array(dustCount * 3); // orbital angles: radius, theta, speed
    for (let i = 0; i < dustCount; i++) {
      const r = 5.5 + Math.random() * 10;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      pos[i*3]   = r * Math.sin(phi) * Math.cos(theta);
      pos[i*3+1] = r * Math.sin(phi) * Math.sin(theta);
      pos[i*3+2] = r * Math.cos(phi);
      vel[i*3]   = r;          // radius
      vel[i*3+1] = theta;      // angle
      vel[i*3+2] = 0.0003 + Math.random() * 0.001; // individual speed
      const b = 0.25 + Math.random() * 0.25;
      col[i*3] = b * 0.5; col[i*3+1] = b * 0.7; col[i*3+2] = b;
    }
    return { pos, col, vel };
  }, []);

  // ── Single elegant ring ──
  const ringCount = 1500;
  const ringD = useMemo(() => {
    const pos = new Float32Array(ringCount * 3);
    const col = new Float32Array(ringCount * 3);
    const angles = new Float32Array(ringCount);
    for (let i = 0; i < ringCount; i++) {
      const a = (i / ringCount) * Math.PI * 2;
      const r = 7.5 + (Math.random() - 0.5) * 0.4;
      angles[i] = a;
      pos[i*3]   = r * Math.cos(a);
      pos[i*3+1] = (Math.random() - 0.5) * 0.15;
      pos[i*3+2] = r * Math.sin(a);
      const b = 0.3 + Math.random() * 0.3;
      col[i*3] = b * 0.6; col[i*3+1] = b * 0.8; col[i*3+2] = b;
    }
    return { pos, col, angles };
  }, []);

  // ── Animation loop ──
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    const pre = PRESETS[state] || PRESETS.idle;
    const L = lerped.current;
    const lerpRate = 0.02; // Very slow transitions — no jarring jumps

    // Smooth lerp targets
    L.dist += (pre.dist - L.dist) * lerpRate;
    L.c1.lerp(new THREE.Color(...pre.c1), lerpRate);
    L.c2.lerp(new THREE.Color(...pre.c2), lerpRate);
    L.aura.lerp(new THREE.Color(...pre.aura), lerpRate);
    L.pSpeed += (pre.pSpeed - L.pSpeed) * lerpRate;

    // Core sphere
    if (coreRef.current) {
      coreMat.uniforms.uTime.value = t;
      coreMat.uniforms.uDistortion.value = L.dist;
      (coreMat.uniforms.uColor1.value as THREE.Color).copy(L.c1);
      (coreMat.uniforms.uColor2.value as THREE.Color).copy(L.c2);

      // Gentle breathing
      const breathe = 1.0 + Math.sin(t * 0.6) * 0.015;
      coreRef.current.scale.setScalar(breathe);
      coreRef.current.rotation.y = t * 0.08;
      coreRef.current.rotation.x = Math.sin(t * 0.04) * 0.08;
    }

    // Aura
    if (auraRef.current) {
      (auraMat.uniforms.uColor.value as THREE.Color).copy(L.aura);
      auraMat.uniforms.uOpacity.value = state === 'speaking' ? 0.4 : 0.25;
      const aBreath = 1.0 + Math.sin(t * 0.9) * 0.02;
      auraRef.current.scale.setScalar(aBreath);
    }

    // Dust particles — smooth orbital drift
    if (dustRef.current) {
      const P = dustData.pos;
      const V = dustData.vel;
      for (let i = 0; i < dustCount; i++) {
        const r = V[i*3];
        V[i*3+1] += V[i*3+2] + L.pSpeed; // advance angle
        const theta = V[i*3+1];
        const phi = Math.acos(((i / dustCount) * 2 - 1) * 0.95); // spread
        const wobble = Math.sin(t * 0.3 + i * 0.01) * 0.5;
        P[i*3]   = (r + wobble) * Math.sin(phi) * Math.cos(theta);
        P[i*3+1] = (r + wobble) * Math.sin(phi) * Math.sin(theta) * 0.6;
        P[i*3+2] = (r + wobble) * Math.cos(phi);
      }
      dustRef.current.geometry.attributes.position.needsUpdate = true;
    }

    // Ring — smooth rotation
    if (ringRef.current) {
      const P = ringD.pos;
      const A = ringD.angles;
      const ringSpeed = state === 'processing' ? 0.25 : state === 'listening' ? 0.15 : 0.06;
      for (let i = 0; i < ringCount; i++) {
        const angle = A[i] + t * ringSpeed;
        const r = 7.5 + Math.sin(angle * 6 + t) * 0.15;
        P[i*3]   = r * Math.cos(angle);
        P[i*3+1] = Math.sin(angle * 3 + t * 0.5) * 0.4;
        P[i*3+2] = r * Math.sin(angle);
      }
      ringRef.current.geometry.attributes.position.needsUpdate = true;
      ringRef.current.rotation.x = 0.35; // Gentle tilt
    }
  });

  return (
    <group>
      {/* Core Sphere */}
      <mesh ref={coreRef} material={coreMat}>
        <icosahedronGeometry args={[4, 48]} />
      </mesh>

      {/* Soft Aura */}
      <mesh ref={auraRef} material={auraMat}>
        <icosahedronGeometry args={[6, 24]} />
      </mesh>

      {/* Ambient Dust */}
      <points ref={dustRef}>
        <bufferGeometry>
          {/* @ts-ignore */}
          <bufferAttribute attach="attributes-position" count={dustCount} array={dustData.pos} itemSize={3} />
          {/* @ts-ignore */}
          <bufferAttribute attach="attributes-color" count={dustCount} array={dustData.col} itemSize={3} />
        </bufferGeometry>
        <pointsMaterial size={0.06} vertexColors transparent opacity={0.35} blending={THREE.AdditiveBlending} depthWrite={false} />
      </points>

      {/* Elegant Ring */}
      <points ref={ringRef}>
        <bufferGeometry>
          {/* @ts-ignore */}
          <bufferAttribute attach="attributes-position" count={ringCount} array={ringD.pos} itemSize={3} />
          {/* @ts-ignore */}
          <bufferAttribute attach="attributes-color" count={ringCount} array={ringD.col} itemSize={3} />
        </bufferGeometry>
        <pointsMaterial size={0.08} vertexColors transparent opacity={0.45} blending={THREE.AdditiveBlending} depthWrite={false} />
      </points>
    </group>
  );
}
