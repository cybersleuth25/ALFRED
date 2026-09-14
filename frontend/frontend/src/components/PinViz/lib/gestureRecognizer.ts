export interface HandLandmark {
  x: number;
  y: number;
  z: number;
}

export interface HandData {
  landmarks: HandLandmark[];
  handedness: 'Left' | 'Right';
}

export interface HandFrame {
  hands: HandData[];
  timestamp: number;
}

const THUMB_TIP = 4;
const INDEX_TIP = 8;
const INDEX_PIP = 6;
const INDEX_MCP = 5;
const MIDDLE_TIP = 12;
const MIDDLE_PIP = 10;
const MIDDLE_MCP = 9;
const RING_TIP = 16;
const RING_PIP = 14;
const PINKY_TIP = 20;
const PINKY_PIP = 18;
const PINKY_MCP = 17;
const WRIST = 0;

function dist2d(a: HandLandmark, b: HandLandmark): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

export function isPinching(landmarks: HandLandmark[], threshold: number): boolean {
  const t = landmarks[THUMB_TIP];
  const i = landmarks[INDEX_TIP];
  const dx = t.x - i.x;
  const dy = t.y - i.y;
  const dz = t.z - i.z;
  return dx * dx + dy * dy + dz * dz < threshold * threshold;
}

export function pinchPosition(landmarks: HandLandmark[]): { x: number; y: number } {
  const t = landmarks[THUMB_TIP];
  const i = landmarks[INDEX_TIP];
  return { x: (t.x + i.x) / 2, y: (t.y + i.y) / 2 };
}

/** Where the index fingertip is pointing — used as the "cursor" for selecting photos. */
export function indexTipPosition(landmarks: HandLandmark[]): { x: number; y: number } {
  const i = landmarks[INDEX_TIP];
  return { x: i.x, y: i.y };
}

/** Continuous thumb-tip↔index-tip distance. */
export function pinchSpread(landmarks: HandLandmark[]): number {
  return dist2d(landmarks[THUMB_TIP], landmarks[INDEX_TIP]);
}

/** Thumb-tip↔middle-tip distance — a single-hand scale dial that doesn't disturb the pinch. */
export function thumbMiddleDistance(landmarks: HandLandmark[]): number {
  return dist2d(landmarks[THUMB_TIP], landmarks[MIDDLE_TIP]);
}

/**
 * Palm width (index-knuckle ↔ pinky-knuckle). Roughly invariant to finger pose,
 * so it grows as the hand approaches the camera — a cheap depth proxy for "pull closer".
 */
export function palmWidth(landmarks: HandLandmark[]): number {
  return dist2d(landmarks[INDEX_MCP], landmarks[PINKY_MCP]);
}

/** Stable hand center (middle-finger knuckle) — used for swipe + two-hand distance. */
export function handCenter(landmarks: HandLandmark[]): { x: number; y: number } {
  const c = landmarks[MIDDLE_MCP];
  return { x: c.x, y: c.y };
}

/** Hand roll angle (radians) from the knuckle line — twisting the wrist changes it. */
export function handRoll(landmarks: HandLandmark[]): number {
  const a = landmarks[INDEX_MCP];
  const b = landmarks[PINKY_MCP];
  return Math.atan2(b.y - a.y, b.x - a.x);
}

/** Count extended fingers (index, middle, ring, pinky) via tip-vs-PIP distance from the wrist. */
export function extendedFingerCount(landmarks: HandLandmark[]): number {
  const w = landmarks[WRIST];
  const pairs: [number, number][] = [
    [INDEX_TIP, INDEX_PIP],
    [MIDDLE_TIP, MIDDLE_PIP],
    [RING_TIP, RING_PIP],
    [PINKY_TIP, PINKY_PIP],
  ];
  let count = 0;
  for (const [tip, pip] of pairs) {
    if (dist2d(landmarks[tip], w) > dist2d(landmarks[pip], w)) count++;
  }
  return count;
}

export function isFist(landmarks: HandLandmark[]): boolean {
  return extendedFingerCount(landmarks) === 0;
}

export interface HandSnapshot {
  present: boolean;
  pinching: boolean;
  fist: boolean;
  pointer: { x: number; y: number };
  center: { x: number; y: number };
  spread: number;
  thumbMiddle: number;
  span: number;
  roll: number;
}

export interface FrameSnapshot {
  Left: HandSnapshot | null;
  Right: HandSnapshot | null;
}

export type GestureEvent =
  | {
      type: 'pinchStart';
      hand: 'Left' | 'Right';
      pointer: { x: number; y: number };
      spread: number;
      span: number;
      roll: number;
      thumbMiddle: number;
    }
  | {
      type: 'pinchMove';
      hand: 'Left' | 'Right';
      pointer: { x: number; y: number };
      delta: { x: number; y: number };
      spread: number;
      span: number;
      roll: number;
      thumbMiddle: number;
    }
  | { type: 'pinchEnd'; hand: 'Left' | 'Right' }
  // Both hands open and moving together/apart → zoom the whole photo cloud.
  | { type: 'twoHandMove'; distance: number; distanceDelta: number }
  // Both hands pinched and rotating relative to each other → rotate the whole cloud.
  | { type: 'twoHandTwist'; angleDelta: number }
  // A fast flick of a single open hand → impart spin to the photo cloud.
  | { type: 'swipe'; hand: 'Left' | 'Right'; velocity: { x: number; y: number } }
  // A hand closing into a fist → brake all motion.
  | { type: 'fist'; hand: 'Left' | 'Right' };

interface PinchState {
  active: boolean;
  pointer: { x: number; y: number } | null;
}

const PINCH_THRESHOLD = 0.06;
// Minimum per-frame hand travel (normalized) to count as a swipe rather than drift.
const SWIPE_THRESHOLD = 0.035;

function snapshotHand(hand: HandData): HandSnapshot {
  return {
    present: true,
    pinching: isPinching(hand.landmarks, PINCH_THRESHOLD),
    fist: isFist(hand.landmarks),
    pointer: indexTipPosition(hand.landmarks),
    center: handCenter(hand.landmarks),
    spread: pinchSpread(hand.landmarks),
    thumbMiddle: thumbMiddleDistance(hand.landmarks),
    span: palmWidth(hand.landmarks),
    roll: handRoll(hand.landmarks),
  };
}

export class GestureRecognizer {
  private leftPinch: PinchState = { active: false, pointer: null };
  private rightPinch: PinchState = { active: false, pointer: null };
  private twoHandZoomActive = false;
  private twoHandLastDistance = 0;
  private twoHandTwistActive = false;
  private twoHandLastAngle = 0;
  private lastCenter: Record<'Left' | 'Right', { x: number; y: number } | null> = {
    Left: null,
    Right: null,
  };
  private wasFist: Record<'Left' | 'Right', boolean> = { Left: false, Right: false };

  /** Latest per-hand derived features — read this for continuous, mode-dependent control. */
  snapshot: FrameSnapshot = { Left: null, Right: null };

  process(frame: HandFrame): GestureEvent[] {
    const events: GestureEvent[] = [];

    const left = frame.hands.find((h) => h.handedness === 'Left');
    const right = frame.hands.find((h) => h.handedness === 'Right');

    this.snapshot = {
      Left: left ? snapshotHand(left) : null,
      Right: right ? snapshotHand(right) : null,
    };

    this.processHand('Left', left, this.leftPinch, events);
    this.processHand('Right', right, this.rightPinch, events);
    this.processFist('Left', left, events);
    this.processFist('Right', right, events);

    const bothPresent = !!left && !!right;
    const neitherPinching = !this.leftPinch.active && !this.rightPinch.active;
    const bothPinching = this.leftPinch.active && this.rightPinch.active;

    if (bothPresent && neitherPinching) {
      this.endTwist();
      this.processTwoHandZoom(left!, right!, events);
    } else if (bothPresent && bothPinching) {
      this.endZoom();
      this.processTwoHandTwist(left!, right!, events);
    } else {
      this.endZoom();
      this.endTwist();
      this.processSwipe('Left', left, this.leftPinch, events);
      this.processSwipe('Right', right, this.rightPinch, events);
    }

    this.lastCenter.Left = left ? handCenter(left.landmarks) : null;
    this.lastCenter.Right = right ? handCenter(right.landmarks) : null;

    return events;
  }

  private processHand(
    handedness: 'Left' | 'Right',
    hand: HandData | undefined,
    state: PinchState,
    events: GestureEvent[],
  ): void {
    const pinching = hand ? isPinching(hand.landmarks, PINCH_THRESHOLD) : false;
    const pointer = hand && pinching ? indexTipPosition(hand.landmarks) : null;

    if (pinching && !state.active) {
      events.push({
        type: 'pinchStart',
        hand: handedness,
        pointer: pointer!,
        spread: pinchSpread(hand!.landmarks),
        span: palmWidth(hand!.landmarks),
        roll: handRoll(hand!.landmarks),
        thumbMiddle: thumbMiddleDistance(hand!.landmarks),
      });
      state.active = true;
      state.pointer = pointer;
    } else if (pinching && state.active) {
      const last = state.pointer!;
      const delta = { x: pointer!.x - last.x, y: pointer!.y - last.y };
      events.push({
        type: 'pinchMove',
        hand: handedness,
        pointer: pointer!,
        delta,
        spread: pinchSpread(hand!.landmarks),
        span: palmWidth(hand!.landmarks),
        roll: handRoll(hand!.landmarks),
        thumbMiddle: thumbMiddleDistance(hand!.landmarks),
      });
      state.pointer = pointer;
    } else if (!pinching && state.active) {
      events.push({ type: 'pinchEnd', hand: handedness });
      state.active = false;
      state.pointer = null;
    }
  }

  private processFist(
    handedness: 'Left' | 'Right',
    hand: HandData | undefined,
    events: GestureEvent[],
  ): void {
    const fist = hand ? isFist(hand.landmarks) : false;
    if (fist && !this.wasFist[handedness]) {
      events.push({ type: 'fist', hand: handedness });
    }
    this.wasFist[handedness] = fist;
  }

  private processTwoHandZoom(left: HandData, right: HandData, events: GestureEvent[]): void {
    const distance = dist2d(left.landmarks[MIDDLE_MCP], right.landmarks[MIDDLE_MCP]);
    if (!this.twoHandZoomActive) {
      this.twoHandZoomActive = true;
      this.twoHandLastDistance = distance;
      return;
    }
    const distanceDelta = distance - this.twoHandLastDistance;
    events.push({ type: 'twoHandMove', distance, distanceDelta });
    this.twoHandLastDistance = distance;
  }

  private processTwoHandTwist(left: HandData, right: HandData, events: GestureEvent[]): void {
    const lc = handCenter(left.landmarks);
    const rc = handCenter(right.landmarks);
    const angle = Math.atan2(rc.y - lc.y, rc.x - lc.x);
    if (!this.twoHandTwistActive) {
      this.twoHandTwistActive = true;
      this.twoHandLastAngle = angle;
      return;
    }
    // Shortest signed angular difference.
    let angleDelta = angle - this.twoHandLastAngle;
    while (angleDelta > Math.PI) angleDelta -= 2 * Math.PI;
    while (angleDelta < -Math.PI) angleDelta += 2 * Math.PI;
    events.push({ type: 'twoHandTwist', angleDelta });
    this.twoHandLastAngle = angle;
  }

  private endZoom(): void {
    this.twoHandZoomActive = false;
  }

  private endTwist(): void {
    this.twoHandTwistActive = false;
  }

  private processSwipe(
    handedness: 'Left' | 'Right',
    hand: HandData | undefined,
    state: PinchState,
    events: GestureEvent[],
  ): void {
    if (!hand || state.active || isFist(hand.landmarks)) return;
    const last = this.lastCenter[handedness];
    if (!last) return;
    const center = handCenter(hand.landmarks);
    const vx = center.x - last.x;
    const vy = center.y - last.y;
    if (Math.hypot(vx, vy) >= SWIPE_THRESHOLD) {
      events.push({ type: 'swipe', hand: handedness, velocity: { x: vx, y: vy } });
    }
  }
}
