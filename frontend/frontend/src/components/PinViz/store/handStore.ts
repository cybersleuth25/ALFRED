import { create } from 'zustand';

export type HandStatus = 'off' | 'requesting-permission' | 'loading-model' | 'active' | 'error';

interface HandState {
  enabled: boolean;
  status: HandStatus;
  errorMessage: string | null;
  toggle: () => void;
  setStatus: (status: HandStatus, errorMessage?: string | null) => void;
}

export const useHandStore = create<HandState>((set) => ({
  enabled: true,
  status: 'off',
  errorMessage: null,
  toggle: () => set((s) => ({ enabled: !s.enabled, errorMessage: null })),
  setStatus: (status, errorMessage = null) => set({ status, errorMessage }),
}));
