import type { CSSProperties } from 'react';

/** Discord + Bluey Lite call-to-action pill buttons, shared across the landing and space views. */
export function CommunityLinks({ style }: { style?: CSSProperties }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        flexWrap: 'wrap',
        justifyContent: 'center',
        ...style,
      }}
    >
      <a
        href="https://discord.com/invite/SndB4Psg"
        target="_blank"
        rel="noopener noreferrer"
        style={DISCORD_STYLE}
      >
        💬 Join our Discord
      </a>
      <a
        href="https://www.trybluey.com/products/bluey-lite"
        target="_blank"
        rel="noopener noreferrer"
        style={BLUEY_STYLE}
      >
        ✨ Get Bluey Lite
      </a>
    </div>
  );
}

const BUTTON_BASE: CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 8,
  padding: '14px 28px',
  borderRadius: 999,
  fontSize: 'var(--font-size-lg)',
  fontWeight: 700,
  letterSpacing: '0.01em',
  textDecoration: 'none',
  boxShadow: '0 6px 20px rgba(0, 0, 0, 0.12)',
};

const DISCORD_STYLE: CSSProperties = {
  ...BUTTON_BASE,
  background: '#5865F2',
  color: '#ffffff',
};

const BLUEY_STYLE: CSSProperties = {
  ...BUTTON_BASE,
  background: 'var(--color-accent)',
  color: 'var(--text-primary)',
};
