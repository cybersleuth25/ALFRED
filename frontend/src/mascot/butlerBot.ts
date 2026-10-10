// A tiny butler mascot drawn in Canvas 2D, modelled on Coucou's Mochi engine:
// a soft squircle body whose features slide over a pseudo-sphere (yaw/pitch),
// ink pill eyes, frame-rate independent easing, springs and little particles.

export type BotMood =
  | "idle"
  | "listening"
  | "thinking"
  | "talking"
  | "approval"
  | "finished"
  | "sleeping"
  | "dizzy"
  | "annoyed"
  | "love";

type EyeShape = "pill" | "wide" | "happy" | "closed" | "line" | "spiral";

interface MoodSpec {
  eyes: EyeShape;
  tint: number;
  color: string;
  tilt: number;
}

const MOODS: Record<BotMood, MoodSpec> = {
  idle: { eyes: "pill", tint: 0, color: "#ffffff", tilt: 0 },
  listening: { eyes: "wide", tint: 0.32, color: "#38bdf8", tilt: 0.17 },
  thinking: { eyes: "pill", tint: 0.42, color: "#6aa8ff", tilt: -0.05 },
  talking: { eyes: "pill", tint: 0.22, color: "#ffd27a", tilt: 0 },
  approval: { eyes: "wide", tint: 0.62, color: "#f5a524", tilt: 0 },
  finished: { eyes: "happy", tint: 0.35, color: "#4ade80", tilt: 0 },
  sleeping: { eyes: "closed", tint: 0.22, color: "#a78bfa", tilt: 0 },
  dizzy: { eyes: "spiral", tint: 0.4, color: "#f472b6", tilt: 0 },
  annoyed: { eyes: "line", tint: 0.38, color: "#fb7185", tilt: -0.08 },
  love: { eyes: "happy", tint: 0.45, color: "#fb7185", tilt: 0.06 },
};

const INK = "rgb(26,20,18)";
const LINE = "#2b2320"; // ink outline colour
const EYE_W = 0.25;
const EYE_H = 0.27;
const EYE_SP = 0.37;
const EYE_P = 0.1;

interface Particle {
  kind: "spark" | "z" | "heart";
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  max: number;
  rot: number;
}

const ease = (k: number, dt: number) => 1 - Math.pow(k, dt);
const easeInOut = (p: number) => (p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2);

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export interface BotInput {
  mood: BotMood;
  lookX: number; // -1..1
  lookY: number; // -1..1
  hovered: boolean;
  accent: string; // bow tie colour (persona)
  talkLevel?: number; // 0..1, mouth opening while talking
}

export class ButlerBot {
  private t = 0;
  private yaw = 0;
  private pitch = 0;
  private tilt = 0;
  private open = 1;
  private nextBlink = 1.5;
  private blinkPhase = -1;
  private doubleBlink = false;
  private eyeScale = 1;
  private tint = 0;
  private tintRgb: [number, number, number] = [255, 255, 255];
  // squash spring (sx/sy deviations)
  private sq = 0;
  private sqV = 0;
  // soft body sway spring
  private physDx = 0;
  private physVx = 0;
  private lastYaw = 0;
  private mouth = 0;
  private mouthV = 0;
  private roll = -1; // 0..1 progress of a yaw roll, -1 = none
  private rollDur = 0.95;
  private rolls = 1;
  private particles: Particle[] = [];
  private emitT = 0;
  private prevMood: BotMood = "idle";

  blink() {
    if (this.blinkPhase < 0) this.blinkPhase = 0;
  }

  squish(amount = 0.22) {
    this.sqV -= amount * 14;
  }

  celebrate() {
    this.roll = 0;
    this.rollDur = 0.95;
    this.rolls = 1;
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * Math.PI * 2;
      this.particles.push({ kind: "spark", x: 0, y: -0.2, vx: Math.cos(a) * 1.6, vy: Math.sin(a) * 1.6 - 0.6, life: 0, max: 0.75, rot: a });
    }
  }

  dizzy() {
    this.roll = 0;
    this.rollDur = 1.3;
    this.rolls = 2;
  }

  update(dt: number, inp: BotInput) {
    dt = Math.min(dt, 0.05);
    this.t += dt;
    const spec = MOODS[inp.mood];

    if (inp.mood !== this.prevMood) {
      if (inp.mood === "finished") this.celebrate();
      if (inp.mood === "dizzy") this.dizzy();
      if (inp.mood === "approval" || inp.mood === "listening") this.blink();
      this.prevMood = inp.mood;
    }

    // ── Look target ──
    let ty = inp.lookX * 0.62;
    let tp = inp.lookY * 0.5;
    if (inp.mood === "thinking") {
      ty = 0.55 + Math.sin(this.t * 0.8) * 0.06;
      tp = 0.55;
    } else if (inp.mood === "sleeping") {
      ty = 0;
      tp = -0.14;
    } else if (inp.mood === "dizzy") {
      ty = Math.sin(this.t * 9) * 0.25;
      tp = 0;
    }
    const kLook = ease(0.0025, dt);
    this.yaw += (ty - this.yaw) * kLook;
    this.pitch += (tp - this.pitch) * kLook;

    // ── Roll (finished / dizzy): features travel all the way round the body ──
    let rollYaw = 0;
    if (this.roll >= 0) {
      this.roll += dt / this.rollDur;
      if (this.roll >= 1) this.roll = -1;
      else rollYaw = easeInOut(this.roll) * Math.PI * 2 * this.rolls;
    }

    // ── Tilt & tint ──
    const kGen = ease(0.0008, dt);
    let tiltTarget = spec.tilt;
    if (inp.mood === "listening") tiltTarget = 0.17 + Math.sin(this.t * 1.6) * 0.03;
    this.tilt += (tiltTarget - this.tilt) * kGen;
    this.tint += (spec.tint - this.tint) * ease(0.002, dt);
    const target = hexToRgb(spec.color);
    const kc = ease(0.002, dt);
    this.tintRgb = this.tintRgb.map((c, i) => c + (target[i] - c) * kc) as [number, number, number];

    // ── Blinks (2.2–5.4 s, sometimes double) ──
    if (inp.mood !== "sleeping" && this.blinkPhase < 0 && this.t > this.nextBlink) {
      this.blinkPhase = 0;
      this.nextBlink = this.t + 2.2 + Math.random() * 3.2;
      this.doubleBlink = Math.random() < 0.22;
    }
    if (this.blinkPhase >= 0) {
      this.blinkPhase += dt;
      const p = this.blinkPhase;
      if (p < 0.07) this.open = 1 - (p / 0.07) * 0.94;
      else if (p < 0.2) this.open = 0.06 + ((p - 0.07) / 0.13) * 0.94;
      else {
        this.open = 1;
        this.blinkPhase = -1;
        if (this.doubleBlink) {
          this.doubleBlink = false;
          this.nextBlink = this.t + 0.23;
        }
      }
    }
    this.eyeScale += ((inp.hovered ? 1.08 : 1) - this.eyeScale) * kGen;

    // ── Springs: squash, sway, mouth ──
    this.sqV += (-120 * this.sq - 11 * this.sqV) * dt;
    this.sq += this.sqV * dt;
    const yawVel = (this.yaw + rollYaw - this.lastYaw) / Math.max(dt, 1e-3);
    this.lastYaw = this.yaw + rollYaw;
    const tDx = Math.max(-1, Math.min(1, -yawVel * 0.35 - this.tilt * 2));
    this.physVx += (60 * (tDx - this.physDx) - 9 * this.physVx) * dt;
    this.physDx += this.physVx * dt;
    const mouthTarget = inp.mood === "talking" ? 0.15 + (inp.talkLevel ?? (Math.abs(Math.sin(this.t * 13)) * 0.6 + Math.abs(Math.sin(this.t * 7.7)) * 0.4)) * 0.85 : 0;
    const w0 = (2 * Math.PI) / 0.25;
    this.mouthV += (w0 * w0 * (mouthTarget - this.mouth) - 2 * 0.6 * w0 * this.mouthV) * dt;
    this.mouth += this.mouthV * dt;

    // ── Particles ──
    this.emitT += dt;
    if (inp.mood === "sleeping" && this.emitT > 1.1) {
      this.emitT = 0;
      this.particles.push({ kind: "z", x: 0.55, y: -0.7, vx: 0.18, vy: -0.35, life: 0, max: 2.2, rot: 0 });
    }
    if (inp.mood === "love" && this.emitT > 0.35) {
      this.emitT = 0;
      this.particles.push({ kind: "heart", x: (Math.random() - 0.5) * 1.2, y: -0.6, vx: (Math.random() - 0.5) * 0.3, vy: -0.6, life: 0, max: 1.3, rot: 0 });
    }
    for (const p of this.particles) {
      p.life += dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      if (p.kind === "spark") {
        p.vx *= 0.9;
        p.vy = p.vy * 0.9 + 0.4 * dt;
      }
    }
    this.particles = this.particles.filter((p) => p.life < p.max);

    return rollYaw;
  }

  draw(ctx: CanvasRenderingContext2D, W: number, H: number, inp: BotInput, rollYaw: number) {
    const spec = MOODS[inp.mood];
    const R = Math.min(W, H) * 0.3;
    const rx = R * 1.06;
    const ry = R * 0.96;
    const t = this.t;
    const boil = Math.floor(t * 8); // hand-animated "line boil", 8 drawings a second

    // Body motion: breathing, approval bounce, squash
    const breathe = Math.sin(t * (inp.mood === "sleeping" ? 1.8 : 2.2)) * (inp.mood === "sleeping" ? 0.035 : 0.014);
    const oy = inp.mood === "approval" ? -Math.abs(Math.sin(5.2 * t)) * 0.07 : 0;
    const sy = 1 + breathe + this.sq;
    const sx = 1 - breathe * 0.57 - this.sq * 0.6;
    const wobble = inp.mood === "annoyed" ? Math.sin(t * 30) * 0.03 * R : 0;

    ctx.save();
    ctx.translate(W / 2 + wobble, H / 2 + R * 0.12 + oy * R * 2 + (1 - sy) * ry);
    ctx.rotate(this.tilt);
    ctx.scale(sx, sy);

    // Soft ground shadow
    ctx.fillStyle = "rgba(0,0,0,0.22)";
    ctx.beginPath();
    ctx.ellipse(0, ry * 1.08, rx * 0.78, ry * 0.12, 0, 0, Math.PI * 2);
    ctx.fill();

    // Body: a slightly egg-shaped blob, drawn as a smooth hand-inked curve that "boils"
    const yaw = this.yaw + rollYaw;
    const front = Math.cos(yaw);
    const N = 40;
    const pts: [number, number][] = [];
    for (let i = 0; i < N; i++) {
      const a = (i / N) * Math.PI * 2;
      const c = Math.cos(a);
      const s = Math.sin(a);
      let x = Math.sign(c) * Math.pow(Math.abs(c), 0.86) * rx;
      const y = Math.sign(s) * Math.pow(Math.abs(s), 0.9) * ry;
      x *= 1 + 0.07 * (y / ry); // narrower at the top, fuller at the bottom
      const j = 1 + (hash(i * 7.13 + boil * 3.71) - 0.5) * 0.022;
      pts.push([x * j, y * j]);
    }
    const body = new Path2D();
    const mid = (p: [number, number], q: [number, number]): [number, number] => [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2];
    const m0 = mid(pts[N - 1], pts[0]);
    body.moveTo(m0[0], m0[1]);
    for (let i = 0; i < N; i++) {
      const p = pts[i];
      const m = mid(p, pts[(i + 1) % N]);
      body.quadraticCurveTo(p[0], p[1], m[0], m[1]);
    }
    body.closePath();

    // Flat cel shading: shadow tone, then the lit area offset towards the light (upper left)
    ctx.fillStyle = "#d9cbb8";
    ctx.fill(body);
    ctx.save();
    ctx.clip(body);
    ctx.fillStyle = "#f3ebdf";
    ctx.beginPath();
    ctx.ellipse(-rx * 0.1, -ry * 0.12, rx * 1.0, ry * 0.98, 0, 0, Math.PI * 2);
    ctx.fill();

    // ── Tailcoat: black lapels wrap the lower body, white shirt-front shows in the V ──
    const fx = Math.sin(yaw) * Math.cos(this.pitch) * rx * 0.9; // front centre on the sphere
    const vis = Math.max(0, front);
    const halfV = R * 0.34 * Math.max(0.25, Math.abs(front));
    const coatTop = ry * 0.5 - this.pitch * ry * 0.2;
    ctx.fillStyle = "#16161b";
    ctx.beginPath();
    ctx.moveTo(-rx * 1.3, coatTop + ry * 0.12);
    ctx.quadraticCurveTo(-rx * 0.6, coatTop - ry * 0.05, fx - halfV, coatTop);
    ctx.lineTo(fx, ry * 1.05);
    ctx.lineTo(fx + halfV, coatTop);
    ctx.quadraticCurveTo(rx * 0.6, coatTop - ry * 0.05, rx * 1.3, coatTop + ry * 0.12);
    ctx.lineTo(rx * 1.3, ry * 1.4);
    ctx.lineTo(-rx * 1.3, ry * 1.4);
    ctx.closePath();
    if (vis < 0.05) ctx.fillRect(-rx * 1.3, coatTop - ry * 0.05, rx * 2.6, ry * 1.5);
    else ctx.fill();
    // inked lapel edges + a little satin sheen
    ctx.strokeStyle = LINE;
    ctx.lineWidth = R * 0.04;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    if (vis > 0.05) {
      ctx.beginPath();
      ctx.moveTo(-rx * 1.3, coatTop + ry * 0.12);
      ctx.quadraticCurveTo(-rx * 0.6, coatTop - ry * 0.05, fx - halfV, coatTop);
      ctx.lineTo(fx, ry * 1.05);
      ctx.lineTo(fx + halfV, coatTop);
      ctx.quadraticCurveTo(rx * 0.6, coatTop - ry * 0.05, rx * 1.3, coatTop + ry * 0.12);
      ctx.stroke();
    }
    ctx.strokeStyle = "rgba(255,255,255,0.13)";
    ctx.lineWidth = R * 0.025;
    if (vis > 0.05) {
      ctx.beginPath();
      ctx.moveTo(fx - halfV * 1.05, coatTop + ry * 0.02);
      ctx.lineTo(fx - R * 0.02, ry * 0.95);
      ctx.moveTo(fx + halfV * 1.05, coatTop + ry * 0.02);
      ctx.lineTo(fx + R * 0.02, ry * 0.95);
      ctx.stroke();
      // shirt studs
      ctx.fillStyle = `rgba(26,20,18,${0.75 * vis})`;
      for (const k of [0.74, 0.88]) {
        ctx.beginPath();
        ctx.arc(fx, ry * k, R * 0.028, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Mood tint: a flat wash, no gloss
    if (this.tint > 0.01) {
      const [r, g, b] = this.tintRgb;
      ctx.fillStyle = `rgba(${r},${g},${b},${0.22 * this.tint})`;
      ctx.fill(body);
    }
    // Paper grain so it reads as an illustration, not a render
    ctx.fillStyle = grainPattern(ctx);
    ctx.globalAlpha = 0.07;
    ctx.fillRect(-rx * 1.5, -ry * 1.5, rx * 3, ry * 3);
    ctx.globalAlpha = 1;
    // A single hand-drawn shine stroke
    ctx.strokeStyle = "rgba(255,255,255,0.75)";
    ctx.lineWidth = R * 0.045;
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.arc(-rx * 0.1, -ry * 0.1, R * 0.78, 1.18 * Math.PI, 1.36 * Math.PI);
    ctx.stroke();

    // ── Cheeks ──
    const blush = Math.max(inp.mood === "love" || inp.mood === "finished" ? 0.9 : 0.35, this.tint * 0.5);
    for (const side of [-1, 1]) {
      const cy = Math.cos(yaw + side * 0.75);
      if (cy <= 0.05) continue;
      ctx.fillStyle = `rgba(255,120,150,${0.5 * blush * cy})`;
      ctx.beginPath();
      ctx.ellipse(Math.sin(yaw + side * 0.75) * rx * 0.85, -Math.sin(this.pitch + EYE_P) * ry + R * 0.2, R * 0.17 * cy, R * 0.1, 0, 0, Math.PI * 2);
      ctx.fill();
    }

    // ── Eyes ──
    const eyeShape: EyeShape = this.roll >= 0 && inp.mood === "finished" ? "happy" : spec.eyes;
    const eyePts: { x: number; y: number; fx: number; fy: number; visible: boolean }[] = [];
    for (const side of [-1, 1]) {
      const ey = yaw + side * EYE_SP;
      const ep = this.pitch + EYE_P;
      const facing = Math.cos(ey) * Math.cos(ep);
      const x = Math.sin(ey) * Math.cos(ep) * rx;
      const y = -Math.sin(ep) * ry;
      eyePts.push({ x, y, fx: Math.max(0.18, Math.cos(ey)), fy: Math.max(0.18, Math.cos(ep)), visible: facing > 0.04 });
    }
    const ew = EYE_W * R * this.eyeScale;
    const eh = EYE_H * R * this.eyeScale;
    eyePts.forEach((e, i) => {
      if (!e.visible) return;
      ctx.save();
      ctx.translate(e.x + this.physDx * R * 0.04, e.y);
      ctx.scale(e.fx, e.fy);
      ctx.fillStyle = INK;
      ctx.strokeStyle = INK;
      ctx.lineCap = "round";
      ctx.lineWidth = ew * 0.32;
      switch (eyeShape) {
        case "pill":
        case "wide": {
          const h = Math.max(eh * (eyeShape === "wide" ? 1.18 : 1) * this.open, ew * 0.3);
          const w = ew * (eyeShape === "wide" ? 1.08 : 1);
          roundRect(ctx, -w / 2, -h / 2, w, h, Math.min(w, h) / 2);
          ctx.fill();
          // tiny catch-light makes him look alive
          if (this.open > 0.6) {
            ctx.fillStyle = "rgba(255,255,255,0.85)";
            ctx.beginPath();
            ctx.arc(w * 0.16, -h * 0.2, w * 0.11, 0, Math.PI * 2);
            ctx.fill();
          }
          break;
        }
        case "happy":
          ctx.beginPath();
          ctx.arc(0, ew * 0.45, ew * 0.82 * 0.6, 1.12 * Math.PI, 1.88 * Math.PI);
          ctx.stroke();
          break;
        case "closed":
          ctx.beginPath();
          ctx.arc(0, -ew * 0.25, ew * 0.5, 0.15 * Math.PI, 0.85 * Math.PI);
          ctx.stroke();
          break;
        case "line":
          ctx.beginPath();
          ctx.moveTo(-ew * 0.5, i === 0 ? -ew * 0.12 : ew * 0.0);
          ctx.lineTo(ew * 0.5, i === 0 ? ew * 0.0 : -ew * 0.12);
          ctx.stroke();
          break;
        case "spiral": {
          ctx.lineWidth = ew * 0.16;
          ctx.beginPath();
          for (let k = 0; k < 60; k++) {
            const a = k * 0.32 + t * 8 * (i === 0 ? 1 : -1);
            const r = (k / 60) * ew * 0.6;
            const px = Math.cos(a) * r;
            const py = Math.sin(a) * r;
            if (k === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
          }
          ctx.stroke();
          break;
        }
      }
      ctx.restore();
    });

    // ── Monocle on his right eye (viewer's left) + chain ──
    const m = eyePts[0];
    if (m.visible) {
      ctx.save();
      ctx.translate(m.x + this.physDx * R * 0.04, m.y);
      ctx.scale(m.fx, m.fy);
      const mr = Math.max(ew, eh) * 0.82;
      ctx.fillStyle = "rgba(200,225,255,0.14)";
      ctx.beginPath();
      ctx.arc(0, 0, mr, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = LINE;
      ctx.lineWidth = R * 0.07;
      ctx.stroke();
      ctx.strokeStyle = "#d8ad4c";
      ctx.lineWidth = R * 0.035;
      ctx.stroke();
      ctx.restore();
      // little chain of links draping to the lapel
      ctx.save();
      ctx.strokeStyle = "#c79a3c";
      ctx.lineWidth = R * 0.022;
      ctx.lineCap = "round";
      ctx.setLineDash([R * 0.035, R * 0.028]);
      ctx.beginPath();
      const cx0 = m.x - Math.max(ew, eh) * 0.6 * m.fx;
      const cy0 = m.y + Math.max(ew, eh) * 0.55;
      ctx.moveTo(cx0, cy0);
      ctx.quadraticCurveTo(cx0 - R * 0.14, cy0 + R * 0.5, fx - halfV * 0.9, coatTop + ry * 0.08);
      ctx.stroke();
      ctx.restore();
    }

    // ── Curled moustache + mouth ──
    const fFace = Math.cos(yaw) * Math.cos(this.pitch);
    if (fFace > 0.05) {
      const mx = Math.sin(yaw) * Math.cos(this.pitch) * rx;
      const my = -Math.sin(this.pitch + EYE_P) * ry + R * 0.27;
      const k = Math.max(0.2, Math.cos(yaw));
      ctx.save();
      ctx.translate(mx, my);
      ctx.scale(k, 1);
      // mouth (under the moustache) opens while talking
      if (this.mouth > 0.03) {
        ctx.fillStyle = "#5a2a2a";
        ctx.beginPath();
        ctx.ellipse(0, R * 0.1, R * 0.11, R * 0.13 * Math.min(1, this.mouth), 0, 0, Math.PI * 2);
        ctx.fill();
      } else if (inp.mood === "finished" || inp.mood === "love") {
        ctx.strokeStyle = INK;
        ctx.lineWidth = R * 0.035;
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.arc(0, R * 0.04, R * 0.1, 0.15 * Math.PI, 0.85 * Math.PI);
        ctx.stroke();
      }
      ctx.fillStyle = "#9a928b";
      ctx.strokeStyle = LINE;
      ctx.lineWidth = R * 0.03;
      ctx.lineJoin = "round";
      for (const s of [-1, 1]) {
        ctx.beginPath();
        ctx.moveTo(0, -R * 0.01);
        ctx.bezierCurveTo(s * R * 0.12, -R * 0.08, s * R * 0.26, -R * 0.02, s * R * 0.3, -R * 0.12);
        ctx.bezierCurveTo(s * R * 0.33, -R * 0.02, s * R * 0.2, R * 0.08, 0, R * 0.04);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        ctx.save();
        ctx.strokeStyle = "rgba(60,50,46,0.45)";
        ctx.lineWidth = R * 0.012;
        for (const k of [0.08, 0.15]) {
          ctx.beginPath();
          ctx.moveTo(s * R * k, 0);
          ctx.lineTo(s * R * (k + 0.05), -R * 0.035);
          ctx.stroke();
        }
        ctx.restore();
      }
      ctx.restore();
    }

    ctx.restore(); // end clip

    // Hand-inked outline
    ctx.strokeStyle = LINE;
    ctx.lineWidth = R * 0.055;
    ctx.lineJoin = "round";
    ctx.stroke(body);

    // Grey side tufts (an old butler's hair), drawn over the outline
    for (const side of [-1, 1]) {
      const a = yaw + side * 1.25;
      if (Math.cos(a) < -0.35) continue;
      const k = Math.max(0.35, Math.abs(Math.cos(yaw)));
      ctx.save();
      ctx.translate(Math.sin(a) * rx * 1.0, -ry * 0.36);
      ctx.scale(-side * k, 1);
      // three soft wisps: ink pass first (thick), then fill, so only the union is outlined
      const wisps: [number, number, number][] = [
        [-R * 0.02, -R * 0.16, R * 0.085],
        [-R * 0.08, -R * 0.03, R * 0.095],
        [-R * 0.02, R * 0.09, R * 0.075],
      ];
      ctx.fillStyle = LINE;
      for (const [x, y, r] of wisps) {
        ctx.beginPath();
        ctx.arc(x, y, r + R * 0.03, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.fillStyle = "#cfccc8";
      for (const [x, y, r] of wisps) {
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.strokeStyle = "rgba(90,84,80,0.55)";
      ctx.lineWidth = R * 0.014;
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.arc(-R * 0.05, -R * 0.05, R * 0.06, 0.6 * Math.PI, 1.4 * Math.PI);
      ctx.moveTo(-R * 0.02, R * 0.05);
      ctx.arc(-R * 0.04, R * 0.08, R * 0.04, 1.6 * Math.PI, 0.4 * Math.PI);
      ctx.stroke();
      ctx.restore();
    }

    // ── Bow tie (persona colour), sits on the collar, outside the clip so it pops ──
    if (vis > 0.05) {
      const bw = R * 0.26 * Math.max(0.3, Math.abs(front));
      const by = coatTop + ry * 0.02;
      const [r, g, b] = hexToRgb(inp.accent);
      ctx.fillStyle = `rgb(${r},${g},${b})`;
      ctx.beginPath();
      ctx.moveTo(fx, by);
      ctx.lineTo(fx - bw, by - R * 0.12);
      ctx.quadraticCurveTo(fx - bw * 1.15, by, fx - bw, by + R * 0.12);
      ctx.closePath();
      ctx.moveTo(fx, by);
      ctx.lineTo(fx + bw, by - R * 0.12);
      ctx.quadraticCurveTo(fx + bw * 1.15, by, fx + bw, by + R * 0.12);
      ctx.closePath();
      ctx.fill();
      ctx.strokeStyle = LINE;
      ctx.lineWidth = R * 0.03;
      ctx.lineJoin = "round";
      ctx.stroke();
      ctx.fillStyle = `rgb(${Math.max(0, r - 60)},${Math.max(0, g - 60)},${Math.max(0, b - 60)})`;
      roundRect(ctx, fx - R * 0.055, by - R * 0.06, R * 0.11, R * 0.12, R * 0.03);
      ctx.fill();
      ctx.stroke();
    }

    // ── Badges ──
    if (inp.mood === "thinking") {
      for (let i = 0; i < 3; i++) {
        const a = 0.35 + 0.65 * Math.max(0, Math.sin(t * 5 - i * 0.7));
        ctx.fillStyle = `rgba(106,168,255,${a})`;
        ctx.beginPath();
        ctx.arc(rx * 0.55 + i * R * 0.17, -ry * 1.18, R * 0.065, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    if (inp.mood === "approval") badge(ctx, rx * 0.86, -ry * 0.92, R * 0.2, "#f5a524", "!");
    if (inp.mood === "listening") {
      ctx.strokeStyle = "rgba(56,189,248,0.8)";
      ctx.lineWidth = R * 0.05;
      ctx.lineCap = "round";
      for (let i = 0; i < 2; i++) {
        const p = (t * 1.2 + i * 0.5) % 1;
        ctx.globalAlpha = 1 - p;
        ctx.beginPath();
        ctx.arc(rx * 1.05, -ry * 0.1, R * (0.18 + p * 0.3), -0.6, 0.6);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }

    // ── Particles ──
    for (const p of this.particles) {
      const a = 1 - p.life / p.max;
      ctx.save();
      ctx.translate(p.x * R * 1.6, p.y * R * 1.6);
      ctx.globalAlpha = a;
      if (p.kind === "spark") {
        ctx.fillStyle = "#ffd36b";
        star(ctx, R * 0.09 * (0.6 + a * 0.4));
      } else if (p.kind === "z") {
        ctx.fillStyle = "#c4b5fd";
        ctx.font = `600 ${R * (0.22 + p.life * 0.08)}px system-ui, "Segoe UI", sans-serif`;
        ctx.fillText("z", 0, 0);
      } else {
        ctx.fillStyle = "#fb7185";
        heart(ctx, R * 0.12);
      }
      ctx.restore();
    }

    ctx.restore();
  }
}

function hash(n: number) {
  const x = Math.sin(n) * 43758.5453;
  return x - Math.floor(x);
}

const grainCache = new WeakMap<CanvasRenderingContext2D, CanvasPattern>();
function grainPattern(ctx: CanvasRenderingContext2D): CanvasPattern | string {
  const hit = grainCache.get(ctx);
  if (hit) return hit;
  const c = document.createElement("canvas");
  c.width = c.height = 96;
  const g = c.getContext("2d")!;
  for (let i = 0; i < 1400; i++) {
    g.fillStyle = hash(i * 1.7) > 0.5 ? "#000" : "#fff";
    g.fillRect(Math.floor(hash(i * 3.1) * 96), Math.floor(hash(i * 5.3) * 96), 1, 1);
  }
  const p = ctx.createPattern(c, "repeat");
  if (!p) return "transparent";
  grainCache.set(ctx, p);
  return p;
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function badge(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, color: string, text: string) {
  ctx.fillStyle = "#0b0c0e";
  ctx.beginPath();
  ctx.arc(x, y, r * 1.18, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#111";
  ctx.font = `800 ${r * 1.35}px system-ui, "Segoe UI", sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, x, y + r * 0.05);
  ctx.textAlign = "start";
  ctx.textBaseline = "alphabetic";
}

function star(ctx: CanvasRenderingContext2D, s: number) {
  ctx.beginPath();
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * Math.PI * 2;
    const r = i % 2 === 0 ? s : s * 0.35;
    ctx.lineTo(Math.cos(a) * r, Math.sin(a) * r);
  }
  ctx.closePath();
  ctx.fill();
}

function heart(ctx: CanvasRenderingContext2D, s: number) {
  ctx.beginPath();
  ctx.moveTo(0, s * 0.35);
  ctx.bezierCurveTo(-s * 1.2, -s * 0.4, -s * 0.4, -s * 1.1, 0, -s * 0.45);
  ctx.bezierCurveTo(s * 0.4, -s * 1.1, s * 1.2, -s * 0.4, 0, s * 0.35);
  ctx.fill();
}
