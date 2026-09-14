import { create } from 'zustand';
import type { Photo } from '../types/photo';
import type { PhotoSlot } from '../lib/computeLayout';

interface PhotoState {
  photos: Photo[];
  files: File[];          // parallel — original files (for upload). Empty when loaded from cloud.
  hashes: string[];       // parallel — content hashes
  selectedId: string | null;
  layout: PhotoSlot[] | null;
  setPhotos: (photos: Photo[], files: File[], hashes: string[]) => void;
  setLayout: (layout: PhotoSlot[] | null) => void;
  clear: () => void;
  setSelected: (id: string | null) => void;
}

export const usePhotoStore = create<PhotoState>((set, get) => ({
  photos: [],
  files: [],
  hashes: [],
  selectedId: null,
  layout: null,
  setPhotos: (photos, files, hashes) => set({ photos, files, hashes }),
  setLayout: (layout) => set({ layout }),
  clear: () => {
    for (const p of get().photos) {
      URL.revokeObjectURL(p.blobUrl);
    }
    set({ photos: [], files: [], hashes: [], selectedId: null, layout: null });
  },
  setSelected: (id) => set({ selectedId: id }),
}));
