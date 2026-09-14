import {
  Mesh,
  PlaneGeometry,
  MeshBasicMaterial,
  CanvasTexture,
  LinearFilter,
  SRGBColorSpace,
  Color,
  Group,
} from 'three';
import type { Photo } from '../types/photo';

export interface PhotoCard {
  group: Group;
  mesh: Mesh;          // the photo plane (raycast target)
  photoId: string;
  dispose: () => void;
}

const CARD_BASE_HEIGHT = 0.8;
// Border thickness as a fraction of the photo's smaller edge.
// 0.05 ≈ a thin white frame (polaroid-style).
const BORDER_RATIO = 0.05;

export function createPhotoCard(photo: Photo, scale = 1.0): PhotoCard {
  const height = CARD_BASE_HEIGHT * scale;
  const width = height * photo.aspectRatio;

  // Border plane (white, slightly larger, behind the photo)
  const borderInset = Math.min(width, height) * BORDER_RATIO;
  const borderGeom = new PlaneGeometry(width + borderInset * 2, height + borderInset * 2);
  const borderMat = new MeshBasicMaterial({ color: new Color(0xffffff), toneMapped: false });
  const borderMesh = new Mesh(borderGeom, borderMat);

  // Photo plane
  const photoGeom = new PlaneGeometry(width, height);
  const texture = new CanvasTexture(photo.canvas);
  texture.colorSpace = SRGBColorSpace;
  texture.minFilter = LinearFilter;
  texture.magFilter = LinearFilter;
  texture.needsUpdate = true;

  const photoMat = new MeshBasicMaterial({ map: texture, toneMapped: false });
  const photoMesh = new Mesh(photoGeom, photoMat);
  photoMesh.position.z = 0.001; // avoid z-fighting with the border
  photoMesh.userData.photoId = photo.id;
  photoMesh.userData.kind = 'photoCard';

  const group = new Group();
  group.add(borderMesh);
  group.add(photoMesh);
  group.userData.photoId = photo.id;

  return {
    group,
    mesh: photoMesh,
    photoId: photo.id,
    dispose: () => {
      borderGeom.dispose();
      borderMat.dispose();
      photoGeom.dispose();
      photoMat.dispose();
      texture.dispose();
    },
  };
}
