import type { Camera } from 'three';
import { MOUSE, TOUCH } from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

export interface ControlsBundle {
  controls: OrbitControls;
  update: () => void;
  dispose: () => void;
}

export function setupControls(camera: Camera, dom: HTMLElement): ControlsBundle {
  const controls = new OrbitControls(camera, dom);

  controls.enableDamping = true;
  controls.dampingFactor = 0.18;

  controls.enableRotate = false;
  controls.enablePan = true;
  controls.enableZoom = false; // smooth zoom is handled in SpaceScene
  controls.panSpeed = 1.0;
  controls.screenSpacePanning = true;

  controls.minDistance = 0.01;
  controls.maxDistance = 5000;

  controls.mouseButtons = {
    LEFT: MOUSE.PAN,
    MIDDLE: MOUSE.PAN,
    RIGHT: MOUSE.PAN,
  };
  controls.touches = {
    ONE: TOUCH.PAN,
    TWO: TOUCH.PAN,
  };

  return {
    controls,
    update: () => controls.update(),
    dispose: () => controls.dispose(),
  };
}
