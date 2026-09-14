import { create } from 'zustand';

export type View = 'landing' | 'processing' | 'space';

interface ViewState {
  view: View;
  loaded: number;
  total: number;
  resetCounter: number;
  setView: (v: View) => void;
  setProgress: (loaded: number, total: number) => void;
  triggerReset: () => void;
}

export const useViewStore = create<ViewState>((set) => ({
  view: 'landing',
  loaded: 0,
  total: 0,
  resetCounter: 0,
  setView: (v) => set({ view: v }),
  setProgress: (loaded, total) => set({ loaded, total }),
  triggerReset: () => set((s) => ({ resetCounter: s.resetCounter + 1 })),
}));
