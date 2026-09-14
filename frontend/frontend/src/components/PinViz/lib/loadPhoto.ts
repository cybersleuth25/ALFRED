import type { Photo } from '../types/photo';
import { photoContentHash } from './photoHash';

const MAX_TEXTURE_EDGE = 512;

async function decodeAndCanvas(file: File): Promise<{ canvas: HTMLCanvasElement; aspectRatio: number }> {
  if (!file.type.startsWith('image/')) {
    throw new Error(`Not an image: ${file.name} (type=${file.type})`);
  }

  const original = await createImageBitmap(file);
  const aspectRatio = original.width / original.height;

  let targetW = original.width;
  let targetH = original.height;
  if (Math.max(targetW, targetH) > MAX_TEXTURE_EDGE) {
    if (aspectRatio >= 1) {
      targetW = MAX_TEXTURE_EDGE;
      targetH = Math.round(MAX_TEXTURE_EDGE / aspectRatio);
    } else {
      targetH = MAX_TEXTURE_EDGE;
      targetW = Math.round(MAX_TEXTURE_EDGE * aspectRatio);
    }
  }

  const bitmap = await createImageBitmap(file, {
    resizeWidth: targetW,
    resizeHeight: targetH,
    resizeQuality: 'high',
  });
  original.close?.();

  const canvas = document.createElement('canvas');
  canvas.width = targetW;
  canvas.height = targetH;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Could not get 2D context');
  ctx.drawImage(bitmap, 0, 0);
  bitmap.close?.();

  return { canvas, aspectRatio };
}

export async function loadPhoto(file: File): Promise<Photo> {
  const { canvas, aspectRatio } = await decodeAndCanvas(file);
  const blobUrl = URL.createObjectURL(file);
  return {
    id: `${file.name}-${file.size}-${file.lastModified}`,
    name: file.name,
    blobUrl,
    canvas,
    aspectRatio,
  };
}

export async function loadPhotoWithHash(file: File): Promise<{ photo: Photo; contentHash: string }> {
  const [{ canvas, aspectRatio }, contentHash] = await Promise.all([
    decodeAndCanvas(file),
    photoContentHash(file),
  ]);
  const blobUrl = URL.createObjectURL(file);
  return {
    photo: {
      id: `${file.name}-${file.size}-${file.lastModified}`,
      name: file.name,
      blobUrl,
      canvas,
      aspectRatio,
    },
    contentHash,
  };
}
