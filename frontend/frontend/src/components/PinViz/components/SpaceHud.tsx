import { FrostPanel } from './ui/FrostPanel';
import { CommunityLinks } from './CommunityLinks';
import { useViewStore } from '../store/viewStore';
import { usePhotoStore } from '../store/photoStore';
import { useHandStore } from '../store/handStore';

export function SpaceHud() {
  const setView = useViewStore((s) => s.setView);
  const triggerReset = useViewStore((s) => s.triggerReset);
  const photos = usePhotoStore((s) => s.photos);
  const handEnabled = useHandStore((s) => s.enabled);
  const toggleHand = useHandStore((s) => s.toggle);
  const clear = usePhotoStore((s) => s.clear);

  const onClear = () => {
    clear();
    setView('landing');
  };

  return (
    <>
      <div
        style={{
          position: 'absolute',
          top: 24,
          left: 24,
          zIndex: 10,
          display: 'flex',
          gap: 12,
        }}
      >
        <FrostPanel style={{ padding: '8px 14px' }}>
          <button
            onClick={onClear}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-primary)',
              fontSize: 'var(--font-size-md)',
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
            }}
          >
            ← New space
          </button>
        </FrostPanel>
        <FrostPanel style={{ padding: '8px 14px' }}>
          <button
            onClick={triggerReset}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-primary)',
              fontSize: 'var(--font-size-md)',
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
            }}
          >
            ⊙ Reset view
          </button>
        </FrostPanel>
        <FrostPanel style={{ padding: '8px 14px' }}>
          <button
            onClick={toggleHand}
            style={{
              background: 'transparent',
              border: 'none',
              color: handEnabled ? 'var(--color-accent)' : 'var(--text-primary)',
              fontSize: 'var(--font-size-md)',
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              fontWeight: handEnabled ? 600 : 400,
            }}
          >
            🖐 Hands
          </button>
        </FrostPanel>
        <FrostPanel style={{ padding: '8px 14px' }}>
          <span
            style={{
              fontSize: 'var(--font-size-md)',
              color: 'var(--text-secondary)',
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {photos.length} {photos.length === 1 ? 'photo' : 'photos'}
          </span>
        </FrostPanel>
      </div>
      <CommunityLinks style={{ position: 'fixed', top: 24, right: 24, zIndex: 10 }} />
    </>
  );
}
