import React, { useEffect, useRef } from "react";
import { ButlerBot, type BotMood } from "../mascot/butlerBot";

interface ButlerMascotProps {
  mood: BotMood;
  /** Canvas size in CSS px (the body is ~68% of this) */
  size: number;
  accent?: string;
  /** Hover / click / triple-click reactions */
  interactive?: boolean;
  className?: string;
  style?: React.CSSProperties;
  onClick?: () => void;
}

// Window-wide pointer so he watches you anywhere on the page
const pointer = { x: -1, y: -1 };
if (typeof window !== "undefined") {
  window.addEventListener("pointermove", (e) => {
    pointer.x = e.clientX;
    pointer.y = e.clientY;
  }, { passive: true });
}

export const ButlerMascot: React.FC<ButlerMascotProps> = ({ mood, size, accent = "#d4a956", interactive = false, className = "", style, onClick }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const live = useRef({ mood, accent, hovered: false, override: null as BotMood | null, overrideUntil: 0, clicks: [] as number[], hoverSince: 0, lastLove: 0 });
  const botRef = useRef<ButlerBot | null>(null);

  useEffect(() => {
    live.current.mood = mood;
    live.current.accent = accent;
  }, [mood, accent]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const bot = new ButlerBot();
    botRef.current = bot;
    const ctx = canvas.getContext("2d")!;
    let raf = 0;
    let last = performance.now();

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      const dt = (now - last) / 1000;
      last = now;
      if (document.hidden) return;

      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const cssW = canvas.clientWidth;
      const cssH = canvas.clientHeight;
      if (!cssW || !cssH) return;
      if (canvas.width !== Math.round(cssW * dpr) || canvas.height !== Math.round(cssH * dpr)) {
        canvas.width = Math.round(cssW * dpr);
        canvas.height = Math.round(cssH * dpr);
      }

      const L = live.current;
      const t = now / 1000;
      // Hovering patiently for ~1.9 s earns some love (at most every 6 s)
      if (interactive && L.hovered && L.hoverSince && t - L.hoverSince > 1.9 && t - L.lastLove > 6 && !L.override) {
        L.override = "love";
        L.overrideUntil = t + 1.6;
        L.lastLove = t;
      }
      if (L.override && t > L.overrideUntil) L.override = null;
      const effMood = L.override ?? L.mood;

      const rect = canvas.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const lookX = pointer.x < 0 ? 0 : Math.tanh((pointer.x - cx) / 260);
      const lookY = pointer.y < 0 ? 0 : -Math.tanh((pointer.y - cy) / 200);

      const input = { mood: effMood, lookX, lookY, hovered: L.hovered, accent: L.accent };
      const rollYaw = bot.update(dt, input);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, cssW, cssH);
      bot.draw(ctx, cssW, cssH, input, rollYaw);
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [interactive]);

  const handleEnter = () => {
    if (!interactive) return;
    live.current.hovered = true;
    live.current.hoverSince = performance.now() / 1000;
    botRef.current?.blink();
  };
  const handleLeave = () => {
    live.current.hovered = false;
    live.current.hoverSince = 0;
  };
  const handleClick = () => {
    onClick?.();
    if (!interactive) return;
    const L = live.current;
    const t = performance.now() / 1000;
    L.hoverSince = t;
    L.clicks = [...L.clicks.filter((c) => t - c < 0.8), t];
    botRef.current?.squish();
    if (L.clicks.length >= 3) {
      L.clicks = [];
      L.override = "dizzy";
      L.overrideUntil = t + 3.3;
    } else if (L.override !== "dizzy") {
      L.override = "annoyed";
      L.overrideUntil = t + 0.8;
    }
  };

  return (
    <canvas
      ref={canvasRef}
      className={className}
      style={{ width: size, height: size, display: "block", cursor: interactive || onClick ? "pointer" : undefined, ...style }}
      onPointerEnter={handleEnter}
      onPointerLeave={handleLeave}
      onClick={handleClick}
    />
  );
};

export default ButlerMascot;
