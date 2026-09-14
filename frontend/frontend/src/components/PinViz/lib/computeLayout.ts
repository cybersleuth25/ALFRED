export interface LayoutOptions {
  spread?: number;          // standard deviation of the Gaussian scatter on x/y
  depthRatio?: number;      // z spread as a fraction of `spread`
  scaleMin?: number;        // minimum random scale per card
  scaleMax?: number;        // maximum random scale per card
  minXyDistance?: number;   // enforce a minimum xy distance between any two photos
  maxPlacementAttempts?: number; // bail-out for rejection sampling
}

export interface PhotoSlot {
  index: number;
  position: { x: number; y: number; z: number };
  scale: number;
}

function gaussian(rng: () => number): number {
  const u = 1 - rng();
  const v = rng();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

export function computeLayout(
  count: number,
  options: LayoutOptions = {},
  rng: () => number = Math.random,
): PhotoSlot[] {
  if (count <= 0) return [];

  const spread = options.spread ?? Math.max(2.5, Math.cbrt(count) * 1.4);
  const depthRatio = options.depthRatio ?? 0.6;
  const scaleMin = options.scaleMin ?? 0.5;
  const scaleMax = options.scaleMax ?? 2.0;
  const minXyDistance = options.minXyDistance ?? 1.2;
  const maxAttempts = options.maxPlacementAttempts ?? 50;

  const minXyDistSq = minXyDistance * minXyDistance;
  const slots: PhotoSlot[] = [];

  for (let i = 0; i < count; i++) {
    let x = 0;
    let y = 0;
    let placed = false;
    for (let attempt = 0; attempt < maxAttempts && !placed; attempt++) {
      x = gaussian(rng) * spread;
      y = gaussian(rng) * spread;
      let conflicts = false;
      for (let j = 0; j < slots.length; j++) {
        const dx = slots[j].position.x - x;
        const dy = slots[j].position.y - y;
        if (dx * dx + dy * dy < minXyDistSq) {
          conflicts = true;
          break;
        }
      }
      if (!conflicts) placed = true;
    }
    const z = gaussian(rng) * spread * depthRatio;
    const scale = scaleMin + rng() * (scaleMax - scaleMin);
    slots.push({
      index: i,
      position: { x, y, z },
      scale,
    });
  }

  return slots;
}
