import { HandLandmarker, FilesetResolver } from '@mediapipe/tasks-vision';
import type { HandFrame, HandLandmark } from './gestureRecognizer';

const WASM_BASE = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18/wasm';
const MODEL_URL =
  'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task';

type FrameListener = (frame: HandFrame) => void;

export class HandTracker {
  private landmarker: HandLandmarker | null = null;
  private video: HTMLVideoElement | null = null;
  private stream: MediaStream | null = null;
  private listeners = new Set<FrameListener>();
  private running = false;
  private rafHandle: number | null = null;

  /**
   * Start webcam + load MediaPipe model. Resolves once tracking is live.
   * Throws if webcam permission denied or model fails to load.
   */
  async start(): Promise<void> {
    if (this.running) return;

    // 1. Webcam
    // Higher resolution — the feed is now the full-screen AR background, not a thumbnail.
    this.stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
      audio: false,
    });
    this.video = document.createElement('video');
    this.video.srcObject = this.stream;
    this.video.muted = true;
    this.video.playsInline = true;
    await this.video.play();

    // 2. MediaPipe model
    const fileset = await FilesetResolver.forVisionTasks(WASM_BASE);
    this.landmarker = await HandLandmarker.createFromOptions(fileset, {
      baseOptions: {
        modelAssetPath: MODEL_URL,
        delegate: 'GPU',
      },
      runningMode: 'VIDEO',
      numHands: 2,
    });

    // 3. Start frame loop
    this.running = true;
    this.tick();
  }

  stop(): void {
    this.running = false;
    if (this.rafHandle != null) {
      cancelAnimationFrame(this.rafHandle);
      this.rafHandle = null;
    }
    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
    }
    if (this.landmarker) {
      this.landmarker.close();
      this.landmarker = null;
    }
    if (this.video) {
      this.video.srcObject = null;
      this.video = null;
    }
  }

  /**
   * Subscribe to landmark frames. Returns an unsubscribe function.
   */
  onFrame(listener: FrameListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  /**
   * Returns the underlying <video> element so a preview can render it.
   * Null if not started.
   */
  getVideoElement(): HTMLVideoElement | null {
    return this.video;
  }

  private tick = (): void => {
    if (!this.running || !this.landmarker || !this.video) return;
    if (this.video.readyState >= 2) {
      const result = this.landmarker.detectForVideo(this.video, performance.now());

      const hands = result.landmarks.map((landmarks, i) => ({
        // Mirror x so movement matches user's mental model (their right hand → world's right side).
        landmarks: landmarks.map(
          (l) => ({ x: 1 - l.x, y: l.y, z: l.z }) as HandLandmark,
        ),
        handedness: (result.handedness[i]?.[0]?.categoryName ?? 'Right') as 'Left' | 'Right',
      }));

      const frame: HandFrame = { hands, timestamp: performance.now() };
      this.listeners.forEach((l) => l(frame));
    }
    this.rafHandle = requestAnimationFrame(this.tick);
  };
}

export const handTracker = new HandTracker();
