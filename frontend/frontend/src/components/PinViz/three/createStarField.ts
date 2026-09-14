import {
  BufferAttribute,
  BufferGeometry,
  Points,
  PointsMaterial,
  Color,
} from 'three';

export interface StarField {
  points: Points;
  dispose: () => void;
}

export function createStarField(count = 2500, radius = 50): StarField {
  const positions = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    // Sample on a sphere uniformly
    const u = Math.random();
    const v = Math.random();
    const theta = 2 * Math.PI * u;
    const phi = Math.acos(2 * v - 1);
    const r = radius * (0.6 + 0.4 * Math.random()); // shell with thickness
    const x = r * Math.sin(phi) * Math.cos(theta);
    const y = r * Math.sin(phi) * Math.sin(theta);
    const z = r * Math.cos(phi);
    positions[i * 3 + 0] = x;
    positions[i * 3 + 1] = y;
    positions[i * 3 + 2] = z;
  }

  const geom = new BufferGeometry();
  geom.setAttribute('position', new BufferAttribute(positions, 3));

  const mat = new PointsMaterial({
    color: new Color(0xffffff),
    size: 0.04,
    sizeAttenuation: true,
    transparent: true,
    opacity: 0.7,
    depthWrite: false,
  });

  const points = new Points(geom, mat);

  function dispose() {
    geom.dispose();
    mat.dispose();
  }

  return { points, dispose };
}
