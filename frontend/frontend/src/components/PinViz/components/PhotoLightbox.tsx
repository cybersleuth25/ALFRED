import { useEffect } from 'react';
import { usePhotoStore } from '../store/photoStore';

export function PhotoLightbox() {
  const selectedId = usePhotoStore((s) => s.selectedId);
  const photos = usePhotoStore((s) => s.photos);
  const setSelected = usePhotoStore((s) => s.setSelected);

  const photo = selectedId ? photos.find((p) => p.id === selectedId) : null;

  useEffect(() => {
    if (!photo) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSelected(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [photo, setSelected]);

  if (!photo) return null;

  return (
    <div
      onClick={() => setSelected(null)}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(237, 237, 237, 0.85)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        zIndex: 100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 48,
        cursor: 'zoom-out',
      }}
    >
      <img
        src={photo.blobUrl}
        alt={photo.name}
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth: '100%',
          maxHeight: '100%',
          objectFit: 'contain',
          borderRadius: 8,
          boxShadow: '0 20px 60px rgba(0, 0, 0, 0.18)',
          cursor: 'default',
        }}
      />
    </div>
  );
}
