import React, { useCallback, useEffect, useRef, useState } from "react";
import ButlerMascot from "./ButlerMascot";
import type { BotMood } from "../mascot/butlerBot";

// Coucou-style notch for Alfred.
// hidden (only a 240×6 wake strip) → compact 288×32 (peek / live activity) → expanded 640×176.
// The little butler springs between his compact and expanded spots, like Mochi.

type OrbState = "idle" | "listening" | "processing" | "speaking";
type Mode = "hidden" | "compact" | "expanded";
type View = "overview" | "approval";

export interface PendingApproval {
  tool: string;
  summary: string;
  expires_in: number;
  can_always?: boolean;
}

export interface DynamicIslandProps {
  orbState: OrbState;
  persona: { name: string; display_name: string; color: string; secondary_color?: string };
  latestTranscript?: string;
  onSwitchPersona: (name: string) => void;
  sentryActive?: boolean;
  approval?: PendingApproval | null;
  /** Rendered inside the frameless desktop window (desktop_island.py) */
  standalone?: boolean;
  onClose?: () => void;
}

interface FocusState {
  active: boolean;
  phase: string;
  remaining: number;
}

interface NowPlaying {
  song: string;
  artist: string;
  playing: boolean;
}

declare global {
  interface Window {
    pywebview?: {
      api?: {
        set_shape?: (x: number, y: number, w: number, h: number, r: number, hidden: boolean) => void;
        close?: () => void;
      };
    };
  }
}

// ── Layout ──
const EXPANDED = { w: 640, h: 176, r: 22 };
const HIDDEN = { w: 184, h: 0, r: 14 };
const BOT_CANVAS = 100; // drawn once at this size, then scaled
const BOT_SPOT = {
  hidden: { cx: 46, cy: 16, d: 6 },
  compact: { cx: 24, cy: 16, d: 22 },
  capsule: { cx: 26, cy: 16, d: 22 },
  expanded: { cx: 70, cy: 92, d: 60 },
};
const SPRING = "cubic-bezier(0.3, 1.25, 0.4, 1)";
const SETTLE = "cubic-bezier(0.4, 0, 0.2, 1)";
const PERSONAS = [
  { id: "alfred", label: "Alfred", col: "#d4a956" },
  { id: "jarvis", label: "Jarvis", col: "#00e5ff" },
  { id: "friday", label: "Friday", col: "#ff3b30" },
];

const CSS = `
.ci { --ink:#f5f6f8; --dim:#9398a1; --dim3:#6b7079; --card:#141518; --flat:#0e0f11; font-family: system-ui, "Segoe UI Variable Text", "Segoe UI", sans-serif; }
.ci .view { position:absolute; inset:0; opacity:0; transform: translateY(-4px) scale(.985); transition: opacity .16s ease-in, transform .16s ease-in; pointer-events:none; }
.ci .view.on { opacity:1; transform:none; transition: opacity .3s ease-out .16s, transform .3s ${SPRING} .16s; pointer-events:auto; }
.ci .pill { height:28px; border-radius:999px; background:var(--flat); border:1px solid rgba(255,255,255,.14); color:var(--ink); font:600 11px/1 system-ui,"Segoe UI",sans-serif; padding:0 11px; display:inline-flex; align-items:center; gap:6px; transition: transform .2s ${SPRING}, background .18s, border-color .18s; white-space:nowrap; }
.ci .pill:hover { background:#17181c; border-color:rgba(255,255,255,.24); transform: translateY(-1px); }
.ci .pill:active { transform: scale(.96); }
.ci .pill.primary { background:var(--accent); border-color:transparent; color:#0b0b0d; }
.ci .round { width:22px; height:22px; border-radius:999px; background:var(--flat); border:1px solid rgba(255,255,255,.12); color:var(--dim3); display:grid; place-items:center; font-size:11px; }
.ci .round:hover { color:var(--ink); }
@keyframes ci-eq { 0%,100% { transform: scaleY(.3) } 50% { transform: scaleY(1) } }
.ci .eq i { display:block; width:2.5px; height:12px; border-radius:2px; animation: ci-eq .8s ease-in-out infinite; transform-origin:center; }
`;

const greeting = (h: string) => {
  const hr = new Date().getHours();
  return `${hr < 5 ? "Up late" : hr < 12 ? "Good morning" : hr < 18 ? "Good afternoon" : "Good evening"}, ${h}.`;
};

export const DynamicIsland: React.FC<DynamicIslandProps> = ({
  orbState,
  persona,
  latestTranscript = "",
  onSwitchPersona,
  sentryActive = false,
  approval = null,
  standalone = false,
  onClose,
}) => {
  const [hovered, setHovered] = useState(false);
  const [open, setOpen] = useState(false);
  const [approvalFolded, setApprovalFolded] = useState(false);
  const [recentCaption, setRecentCaption] = useState(false);
  const [finished, setFinished] = useState(false);
  const [sleepy, setSleepy] = useState(false);
  const [focus, setFocus] = useState<FocusState | null>(null);
  const [music, setMusic] = useState<NowPlaying | null>(null);
  const [earOn, setEarOn] = useState(false);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [reply, setReply] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const rootRef = useRef<HTMLDivElement>(null);
  const islandRef = useRef<HTMLDivElement>(null);
  const textMeasureRef = useRef<HTMLSpanElement>(null);
  const [measuredTextWidth, setMeasuredTextWidth] = useState(110);
  const [idleCapsule, setIdleCapsule] = useState<boolean>(() => {
    try {
      return localStorage.getItem("alfred_notch_idle_capsule") === "true";
    } catch {
      return false;
    }
  });

  // Open on hover (Coucou's "Open on hover"): resting on the notch opens it; it folds
  // shortly after the pointer leaves unless you clicked inside.
  const [openOnHover, setOpenOnHover] = useState<boolean>(() => {
    try {
      return localStorage.getItem("alfred_notch_open_on_hover") === "true";
    } catch {
      return false;
    }
  });
  const hoverOpened = useRef(false);
  const [trusted, setTrusted] = useState(0);
  const toggleOpenOnHover = () => {
    setOpenOnHover((prev) => {
      try {
        localStorage.setItem("alfred_notch_open_on_hover", String(!prev));
      } catch {
        // storage unavailable; setting lasts for this session
      }
      return !prev;
    });
  };

  const toggleIdleCapsule = () => {
    setIdleCapsule((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("alfred_notch_idle_capsule", String(next));
      } catch {
        // storage unavailable (private mode); the toggle still works for this session
      }
      return next;
    });
  };

  const leaveTimer = useRef<number | undefined>(undefined);
  const prevOrb = useRef(orbState);

  const accent = persona.color || "#d4a956";
  const honorific = persona.name === "friday" ? "boss" : "sir";

  const handleClose = () => {
    if (standalone && window.pywebview?.api?.close) {
      window.pywebview.api.close();
    } else if (standalone) {
      window.close();
    }
    onClose?.();
  };

  // ── Caption determination ──
  const focusClock = focus?.remaining ? `${Math.floor(focus.remaining / 60)}:${String(focus.remaining % 60).padStart(2, "0")}` : "";

  const caption =
    reply ??
    (orbState === "listening"
      ? `Listening, ${honorific}…`
      : orbState === "processing"
      ? "One moment…"
      : latestTranscript && (recentCaption || orbState === "speaking")
      ? latestTranscript
      : music?.playing
      ? `♪ ${music.song} — ${music.artist}`
      : approval && !approvalFolded
      ? "Something needs your approval."
      : greeting(honorific));

  useEffect(() => {
    if (textMeasureRef.current) {
      const w = Math.ceil(textMeasureRef.current.getBoundingClientRect().width);
      if (w > 0) setMeasuredTextWidth(w);
    }
  }, [caption]);

  // ── Mode / view resolution ──
  const live = orbState !== "idle" || recentCaption || !!focus?.active || !!music?.playing || finished;
  const showApproval = !!approval && !approvalFolded;
  const mode: Mode = open || showApproval ? "expanded" : hovered || live || approval ? "compact" : "hidden";
  const view: View = approval && (showApproval || open) ? "approval" : "overview";

  // Flexible width: wraps content snugly instead of a rigid 288px box
  const isCapsule = idleCapsule && mode === "compact" && !hovered && orbState === "idle" && !recentCaption && !music?.playing && !approval && !focus?.active;
  const hasActivity = orbState !== "idle" || !!focus?.active || sentryActive || !!approval;
  const compactWidth = isCapsule
    ? 52
    : Math.max(160, Math.min(460, measuredTextWidth + 48 + (hasActivity ? 26 : 0) + 36));
  const compactRadius = isCapsule ? 16 : 14;

  const size =
    mode === "expanded"
      ? EXPANDED
      : mode === "compact"
      ? { w: compactWidth, h: 32, r: compactRadius }
      : HIDDEN;

  const spot =
    mode === "expanded" && view === "approval"
      ? { cx: 64, cy: 92, d: 56 }
      : mode === "expanded"
      ? BOT_SPOT.expanded
      : mode === "compact"
      ? isCapsule
        ? BOT_SPOT.capsule
        : BOT_SPOT.compact
      : BOT_SPOT.hidden;

  const mood: BotMood = approval
    ? "approval"
    : finished
    ? "finished"
    : orbState === "listening"
    ? "listening"
    : orbState === "processing"
    ? "thinking"
    : orbState === "speaking"
    ? "talking"
    : sleepy && !hovered && !open
    ? "sleeping"
    : "idle";

  // ── Background polling ──
  useEffect(() => {
    const poll = async () => {
      const get = (u: string) => fetch(u).then((r) => (r.ok ? r.json() : null)).catch(() => null);
      const [f, s, a] = await Promise.all([get("/api/focus/status"), get("/api/spotify/now_playing"), get("/api/acoustic/status")]);
      if (f) setFocus(f);
      setMusic(s && s.song && s.playing ? s : null);
      if (a) setEarOn(!!a.active);
    };
    poll();
    const id = window.setInterval(poll, 6000);
    return () => window.clearInterval(id);
  }, []);

  // ── New caption peeks for a few seconds ──
  useEffect(() => {
    if (!latestTranscript) return;
    setRecentCaption(true);
    setReply(null);
    const id = window.setTimeout(() => setRecentCaption(false), 5000);
    return () => window.clearTimeout(id);
  }, [latestTranscript]);

  // ── Finished speaking → happy roll ──
  useEffect(() => {
    const was = prevOrb.current;
    prevOrb.current = orbState;
    if (was === "speaking" && orbState === "idle") {
      setFinished(true);
      const id = window.setTimeout(() => setFinished(false), 1600);
      return () => window.clearTimeout(id);
    }
  }, [orbState]);

  // ── Dozes off after two quiet minutes ──
  useEffect(() => {
    setSleepy(false);
    if (orbState !== "idle") return;
    const id = window.setTimeout(() => setSleepy(true), 120_000);
    return () => window.clearTimeout(id);
  }, [orbState, latestTranscript]);

  // ── A new approval always opens its card ──
  useEffect(() => {
    if (approval) setApprovalFolded(false);
  }, [approval?.summary]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Close: Esc, click outside, window blur (desktop) ──
  const fold = useCallback(() => {
    setOpen(false);
    if (approval) setApprovalFolded(true);
  }, [approval]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") fold();
      if (e.ctrlKey && e.altKey && e.key.toLowerCase() === "a") setOpen((o) => !o);
    };
    const onDown = (e: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onBlur = () => standalone && setOpen(false);
    window.addEventListener("keydown", onKey);
    window.addEventListener("pointerdown", onDown);
    window.addEventListener("blur", onBlur);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("pointerdown", onDown);
      window.removeEventListener("blur", onBlur);
    };
  }, [fold, standalone]);

  // ── Desktop window: report the island's live shape so the window can clip to it ──
  useEffect(() => {
    if (!standalone) return;
    let raf = 0;
    const tick = () => {
      raf = requestAnimationFrame(tick);
      const el = islandRef.current;
      const api = window.pywebview?.api;
      if (!el || !api?.set_shape) return;
      const r = el.getBoundingClientRect();
      const radius = parseFloat(getComputedStyle(el).borderBottomLeftRadius) || 0;
      api.set_shape(r.left, r.top, r.width, r.height, radius, r.height < 2);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [standalone]);

  // ── Hover with a 14px forgiving margin (padding on the root) ──
  const onEnter = () => {
    window.clearTimeout(leaveTimer.current);
    setHovered(true);
    if (openOnHover && !open) {
      hoverOpened.current = true;
      setOpen(true);
    }
  };
  const onLeave = () => {
    window.clearTimeout(leaveTimer.current);
    leaveTimer.current = window.setTimeout(() => {
      setHovered(false);
      if (hoverOpened.current) {
        hoverOpened.current = false;
        setOpen(false);
      }
    }, openOnHover ? 650 : 550);
  };

  // How many commands are trusted with "Always" (shown so they can be forgotten)
  useEffect(() => {
    if (mode !== "expanded") return;
    fetch("/api/approval")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setTrusted(d?.trusted ?? 0))
      .catch(() => undefined);
  }, [mode, approval]);

  // ── Actions ──
  const post = (url: string, body: unknown) =>
    fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    const cmd = input.trim();
    if (!cmd || sending) return;
    setInput("");
    setSending(true);
    try {
      const d = await (await post("/api/command", { command: cmd })).json();
      setReply(d.reply || d.error || null);
    } catch {
      setReply(`I couldn't reach the house, ${honorific}.`);
    } finally {
      setSending(false);
    }
  };

  const decide = async (decision: "confirm" | "cancel" | "always") => {
    setBusy(decision);
    try {
      const d = await (await post("/api/approval", { decision })).json();
      if (d.result) setReply(String(d.result).slice(0, 220));
    } catch {
      setReply("That didn't go through.");
    } finally {
      setBusy(null);
    }
  };

  const quick = async (key: string, fn: () => Promise<unknown>) => {
    setBusy(key);
    try {
      await fn();
    } catch {
      setReply("That didn't go through.");
    } finally {
      setBusy(null);
    }
  };

  // Bot transform: canvas is BOT_CANVAS px; the drawn body is ~60% of it
  const botScale = spot.d / 0.6 / BOT_CANVAS;
  const glowSize = spot.d * 2.2;
  const screen = (mode: string) =>
    post("/api/screen/copilot", { query: "Analyze my screen for actionable assistance", mode })
      .then((r) => r.json())
      .then((d) => setReply(d.analysis ? String(d.analysis).slice(0, 220) : null));

  return (
    <div
      ref={rootRef}
      className={`ci ${standalone ? "absolute" : "fixed"} top-0 left-1/2 -translate-x-1/2 z-[60] select-none`}
      style={{ padding: "0 14px 14px", ["--accent" as string]: accent } as React.CSSProperties}
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
    >
      <style>{CSS}</style>

      {/* Hidden text measurer for dynamic width */}
      <span
        ref={textMeasureRef}
        className="invisible absolute -top-[9999px] left-0 pointer-events-none whitespace-nowrap text-[12px] font-normal tracking-tight"
        style={{ fontFamily: 'system-ui, "Segoe UI Variable Text", "Segoe UI", sans-serif' }}
        aria-hidden
      >
        {caption}
      </span>

      {/* Wake strip: the only hit area while hidden */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2" style={{ width: 240, height: 6 }} />

      {/* Island */}
      <div
        ref={islandRef}
        className="group relative mx-auto bg-black/95 backdrop-blur-md border-b border-x border-white/10 shadow-[0_8px_30px_rgba(0,0,0,0.6)]"
        style={{
          width: size.w,
          height: size.h,
          borderRadius: `0 0 ${size.r}px ${size.r}px`,
          transition:
            mode === "hidden"
              ? `width .38s ${SETTLE}, height .32s ${SETTLE}, border-radius .3s`
              : `width .45s ${SPRING}, height .45s ${SPRING}, border-radius .35s`,
          cursor: mode === "compact" ? "pointer" : "default",
        }}
        onClick={() => mode === "compact" && setOpen(true)}
        onPointerDownCapture={() => {
          hoverOpened.current = false; // clicking inside keeps a hover-opened notch open
        }}
      >
        <div className="absolute inset-0 overflow-hidden" style={{ borderRadius: "inherit" }}>
          {/* ── Compact ── */}
          <div className={`view ${mode === "compact" ? "on" : ""}`}>
            <div
              className={`h-full flex items-center gap-2 pl-[44px] pr-2.5 transition-opacity duration-200 ${
                isCapsule ? "opacity-0 pointer-events-none" : "opacity-100"
              }`}
            >
              <p className="flex-1 min-w-0 truncate text-[12px] tracking-tight" style={{ color: "var(--dim)" }}>
                {caption}
              </p>
              <CompactActivity orbState={orbState} accent={accent} approval={!!approval} focusClock={focus?.active ? focusClock : ""} sentry={sentryActive} />
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  handleClose();
                }}
                className="w-4 h-4 rounded-full flex items-center justify-center text-zinc-400 hover:text-white hover:bg-white/15 transition-all opacity-0 group-hover:opacity-100 shrink-0 text-[10px]"
                title="Remove / Hide Notch"
              >
                ✕
              </button>
            </div>
          </div>

          {/* ── Expanded: overview ── */}
          <div className={`view ${mode === "expanded" && view === "overview" ? "on" : ""}`}>
            <div className="h-full flex flex-col gap-2 pl-[140px] pr-4 pt-3 pb-3.5">
              <div className="flex items-center gap-2 h-5">
                <span className="text-[13px] font-semibold" style={{ color: "var(--ink)" }}>{persona.display_name}</span>
                <span className="text-[10px] uppercase tracking-[.14em]" style={{ color: accent }}>{mood === "talking" ? "speaking" : mood}</span>
                <div className="ml-auto flex items-center gap-1.5">
                  {focus?.active && <span className="text-[10.5px] tabular-nums text-amber-300">⏱ {focusClock}</span>}
                  {sentryActive && <span className="text-[10.5px] text-rose-300">⛨</span>}
                  {PERSONAS.map((p) => (
                    <button
                      key={p.id}
                      title={p.label}
                      onClick={() => onSwitchPersona(p.id)}
                      className="w-3 h-3 rounded-full transition-transform hover:scale-125"
                      style={{ background: p.col, boxShadow: persona.name === p.id ? `0 0 0 2px #000, 0 0 0 3.5px ${p.col}` : "none", opacity: persona.name === p.id ? 1 : 0.45 }}
                    />
                  ))}
                  {trusted > 0 && (
                    <button
                      className="round ml-1 !w-auto px-2 text-[10px]"
                      title={`${trusted} command(s) trusted with "Always" — click to forget them`}
                      onClick={(e) => {
                        e.stopPropagation();
                        post("/api/approval/forget", {}).then(() => setTrusted(0));
                      }}
                    >
                      🔓 {trusted}
                    </button>
                  )}
                  <button
                    className={`round ml-1 ${openOnHover ? "!text-cyan-300 !border-cyan-500/50" : ""}`}
                    title={openOnHover ? "Opens on hover (click to require a click)" : "Opens on click (click to open on hover)"}
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleOpenOnHover();
                    }}
                  >
                    {openOnHover ? "◉" : "○"}
                  </button>
                  <button
                    className="round ml-1 hover:!text-rose-400 hover:!border-rose-400/40"
                    title="Remove / Hide Notch"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleClose();
                    }}
                  >
                    ✕
                  </button>
                  <button className="round ml-0.5" title="Fold (Esc)" onClick={(e) => { e.stopPropagation(); fold(); }}>⌃</button>
                </div>
              </div>

              <p className="text-[12.5px] leading-[17px] line-clamp-2 min-h-[34px]" style={{ color: "var(--ink)" }}>{caption}</p>

              <form onSubmit={send} className="flex items-center gap-1.5">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={`Ask ${persona.display_name}…`}
                  className="flex-1 h-8 px-3.5 rounded-full outline-none text-[12.5px] placeholder:text-[#6b7079]"
                  style={{ background: "var(--flat)", border: "1px solid rgba(255,255,255,.14)", color: "var(--ink)" }}
                />
                <button type="submit" className="pill primary" style={{ height: 32 }} disabled={sending || !input.trim()}>
                  {sending ? "…" : "Ask"}
                </button>
              </form>

              <div className="flex items-center gap-1.5 overflow-hidden">
                <button
                  type="button"
                  className={`pill ${idleCapsule ? "!border-cyan-500/60 !text-cyan-300" : ""}`}
                  onClick={toggleIdleCapsule}
                  title={idleCapsule ? "Mini-Capsule on idle is enabled (click for Auto-Hug)" : "Auto-Hug width enabled (click for Mini-Capsule)"}
                >
                  {idleCapsule ? "💊 Mini Capsule" : "↔ Auto-Hug"}
                </button>
                <button className="pill" onClick={() => quick("screen", () => screen("general"))}>
                  {busy === "screen" ? "Looking…" : "👁 Screen"}
                </button>
                <button className="pill" onClick={() => quick("debug", () => screen("debug"))}>
                  {busy === "debug" ? "Reading…" : "⚡ Debug"}
                </button>
                <button className="pill" onClick={() => quick("ear", () => post("/api/acoustic/toggle", { enabled: !earOn }).then((r) => r.json()).then((d) => setEarOn(!!d.active)))}>
                  {earOn ? "🎧 Ear on" : "🔇 Ear"}
                </button>
                <button className="pill" onClick={() => quick("focus", () => post("/api/focus/toggle", { action: "toggle" }).then(() => fetch("/api/focus/status")).then((r) => r.json()).then(setFocus))}>
                  ⏱ {focus?.active ? focusClock : "Focus"}
                </button>
                <button className="pill" onClick={() => quick("debrief", () => post("/api/debrief/run", { speak: true }).then((r) => r.json()).then((d) => setReply(d.spoken_text ?? "Debrief delivered.")))}>
                  {busy === "debrief" ? "Preparing…" : "🌙 Debrief"}
                </button>
              </div>
            </div>
          </div>

          {/* ── Expanded: approval card ── */}
          <div className={`view ${mode === "expanded" && view === "approval" ? "on" : ""}`}>
            <div className="h-full flex flex-col justify-center gap-2.5 pl-[132px] pr-4 py-3.5">
              <div className="flex items-center gap-2">
                <span className="text-[13px] font-semibold" style={{ color: "var(--ink)" }}>May I proceed, {honorific}?</span>
                <span className="ml-auto text-[10.5px] tabular-nums" style={{ color: "var(--dim3)" }}>{approval?.expires_in ?? 0}s</span>
                <button
                  className="round hover:!text-rose-400 hover:!border-rose-400/40"
                  title="Remove / Hide Notch"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleClose();
                  }}
                >
                  ✕
                </button>
                <button className="round" title="Fold (Esc)" onClick={(e) => { e.stopPropagation(); fold(); }}>⌃</button>
              </div>
              <code
                className="block text-[11.5px] leading-4 rounded-xl px-3 py-2 max-h-[52px] overflow-auto break-all"
                style={{ background: "var(--card)", border: "1px solid rgba(255,255,255,.08)", color: "#e4e6ea", fontFamily: '"Cascadia Mono", Consolas, monospace' }}
              >
                {approval?.summary}
              </code>
              <div className="flex gap-1.5">
                <button className="pill primary flex-1 justify-center" disabled={!!busy} onClick={() => decide("confirm")}>
                  {busy === "confirm" ? "Running…" : "Allow"}
                </button>
                {approval?.can_always && (
                  <button
                    className="pill justify-center"
                    disabled={!!busy}
                    title="Allow now and never ask again for this exact command"
                    onClick={() => decide("always")}
                  >
                    {busy === "always" ? "Running…" : "Always"}
                  </button>
                )}
                <button className="pill flex-1 justify-center" disabled={!!busy} onClick={() => decide("cancel")}>
                  Deny
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Mood glow behind the butler (expanded only) */}
        <div
          aria-hidden
          className="absolute rounded-full pointer-events-none"
          style={{
            left: spot.cx - glowSize / 2,
            top: spot.cy - glowSize / 2,
            width: glowSize,
            height: glowSize,
            background: `radial-gradient(circle, ${mood === "approval" ? "#f5a524" : accent}55 0%, transparent 62%)`,
            filter: "blur(6px)",
            opacity: mode === "expanded" ? 0.8 : 0,
            transition: `opacity .4s ease-in-out, left .5s ${SPRING}, top .5s ${SPRING}, width .5s ${SPRING}, height .5s ${SPRING}`,
          }}
        />

        {/* The butler: one canvas that springs between spots */}
        <div
          className="absolute left-0 top-0"
          style={{
            width: BOT_CANVAS,
            height: BOT_CANVAS,
            transformOrigin: "50% 50%",
            transform: `translate(${spot.cx - BOT_CANVAS / 2}px, ${spot.cy - BOT_CANVAS / 2}px) scale(${botScale})`,
            opacity: mode === "hidden" ? 0 : 1,
            transition: `transform .55s ${SPRING}, opacity .25s ease`,
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <ButlerMascot mood={mood} size={BOT_CANVAS} accent={accent} interactive={mode !== "hidden"} onClick={() => mode === "compact" && setOpen(true)} />
        </div>
      </div>
    </div>
  );
};

const CompactActivity: React.FC<{ orbState: OrbState; accent: string; approval: boolean; focusClock: string; sentry: boolean }> = ({
  orbState,
  accent,
  approval,
  focusClock,
  sentry,
}) => {
  if (approval) return <span className="text-[10.5px] font-semibold text-amber-300">Approve?</span>;
  if (orbState === "speaking" || orbState === "listening")
    return (
      <span className="eq flex items-center gap-[2.5px]">
        {[0, 1, 2, 3].map((i) => (
          <i key={i} style={{ background: orbState === "listening" ? "#38bdf8" : accent, animationDelay: `${i * 0.13}s` }} />
        ))}
      </span>
    );
  if (orbState === "processing") return <span className="w-3 h-3 rounded-full border-[1.5px] animate-spin" style={{ borderColor: accent, borderTopColor: "transparent" }} />;
  if (focusClock) return <span className="text-[10.5px] tabular-nums text-amber-300">{focusClock}</span>;
  if (sentry) return <span className="text-[10.5px] text-rose-300">⛨</span>;
  return null;
};

export default DynamicIsland;
