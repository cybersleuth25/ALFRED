import {
  Scene,
  PerspectiveCamera,
  WebGLRenderer,
  ACESFilmicToneMapping,
} from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { SMAAPass } from 'three/examples/jsm/postprocessing/SMAAPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import type { OutlinePass } from 'three/examples/jsm/postprocessing/OutlinePass.js';
import { createOutlinePass } from './passes/outlinePassFactory';

export interface SceneBundle {
  scene: Scene;
  camera: PerspectiveCamera;
  renderer: WebGLRenderer;
  composer: EffectComposer;
  outline: OutlinePass;
  resize: (w: number, h: number) => void;
  dispose: () => void;
}

export function createScene(canvas: HTMLCanvasElement): SceneBundle {
  const scene = new Scene();
  // Transparent — the live webcam shows through behind the canvas (AR passthrough).
  scene.background = null;

  const camera = new PerspectiveCamera(45, 1, 0.1, 1000);
  camera.position.set(0, 0, 8);

  const renderer = new WebGLRenderer({ canvas, antialias: false, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x000000, 0);
  renderer.toneMapping = ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;

  const composer = new EffectComposer(renderer);
  const renderPass = new RenderPass(scene, camera);
  renderPass.clearAlpha = 0; // keep the render target transparent so the webcam shows through
  composer.addPass(renderPass);

  const outline = createOutlinePass(scene, camera, window.innerWidth, window.innerHeight);
  composer.addPass(outline);

  const smaa = new SMAAPass(window.innerWidth, window.innerHeight);
  composer.addPass(smaa);

  composer.addPass(new OutputPass());

  function resize(w: number, h: number) {
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h, false);
    composer.setSize(w, h);
  }

  function dispose() {
    composer.dispose();
    renderer.dispose();
  }

  return { scene, camera, renderer, composer, outline, resize, dispose };
}
