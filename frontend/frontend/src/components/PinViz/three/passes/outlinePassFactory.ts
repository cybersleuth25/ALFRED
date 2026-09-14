import { Color, Vector2, type Object3D } from 'three';
import { OutlinePass } from 'three/examples/jsm/postprocessing/OutlinePass.js';
import type { Scene, Camera } from 'three';

const ACCENT_HEX = 0xecff0f;

export function createOutlinePass(scene: Scene, camera: Camera, w: number, h: number): OutlinePass {
  const pass = new OutlinePass(new Vector2(w, h), scene, camera);
  pass.edgeStrength = 10;
  pass.edgeGlow = 1.4;
  pass.edgeThickness = 1.2;
  pass.pulsePeriod = 0;
  pass.visibleEdgeColor = new Color(ACCENT_HEX);
  pass.hiddenEdgeColor = new Color(ACCENT_HEX).multiplyScalar(0.3);
  pass.selectedObjects = [] as Object3D[];
  return pass;
}
