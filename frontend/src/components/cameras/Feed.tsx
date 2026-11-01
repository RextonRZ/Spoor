"use client";
/**
 * One camera's picture and the pieces every camera view shares.
 * - useFeeds: which cameras have a moving feed (public/cameras/feeds.json, camera id -> mp4). The rest show their still.
 *   When the final S2 render lands its MP4s go in public/cameras/ and into feeds.json, and every tile moves.
 * - Feed: the video (muted, looping, only while visible, the tab is shown and motion is allowed) or the still.
 * - Clock: one running time for every view, from one interval (a live clock, like a recorder's on-screen display).
 */
import { useEffect, useRef, useState, useSyncExternalStore } from "react";

export function useFeeds(): Record<string, string> {
  const [feeds, setFeeds] = useState<Record<string, string>>({});
  useEffect(() => {
    let live = true;
    fetch("/cameras/feeds.json").then((r) => (r.ok ? r.json() : {})).then((j) => live && setFeeds(j)).catch(() => {});
    return () => { live = false; };
  }, []);
  return feeds;
}

export const stillOf = (id: string) => `/cameras/${id}.jpg`;
export const posterOf = (id: string) => `/landing/posters/${id}.jpg`; // the older 640 px still, used if the full-size one is missing

const reduced = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export function Feed({ id, src, className = "", eager = false }: { id: string; src?: string; className?: string; eager?: boolean }) {
  const box = useRef<HTMLSpanElement>(null);
  const vid = useRef<HTMLVideoElement>(null);
  const [still, setStill] = useState(stillOf(id));
  useEffect(() => {
    const v = vid.current;
    const el = box.current;
    if (!v || !el) return;
    let visible = false;
    const sync = () => (visible && !document.hidden && !reduced() ? v.play().catch(() => {}) : v.pause());
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; sync(); }, { threshold: 0.15 });
    io.observe(el);
    document.addEventListener("visibilitychange", sync);
    return () => { io.disconnect(); document.removeEventListener("visibilitychange", sync); };
  }, [src]);
  return (
    <span ref={box} className={`cf ${className}`}>
      {src ? (
        <video ref={vid} className="cf-media" src={src} poster={still} muted loop playsInline preload={eager ? "auto" : "metadata"} aria-label={`${id.replace("_", " ")} live view`} />
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img className="cf-media" src={still} alt={`${id.replace("_", " ")} live view`} draggable={false} decoding="async"
          onError={() => setStill((s) => (s === posterOf(id) ? s : posterOf(id)))} />
      )}
    </span>
  );
}

// ---- the running clock: one interval for every view ----
const subs = new Set<() => void>();
let ticks = 0;
let timer: number | null = null;
const subscribe = (cb: () => void) => {
  subs.add(cb);
  if (timer === null) timer = window.setInterval(() => { ticks += 1; subs.forEach((f) => f()); }, 1000);
  return () => {
    subs.delete(cb);
    if (!subs.size && timer !== null) { window.clearInterval(timer); timer = null; }
  };
};

/** "14:34:07": the footage's clock, running from `baseMs` (the recorder's time at page open). */
export function Clock({ baseMs }: { baseMs: number }) {
  const t = useSyncExternalStore(subscribe, () => ticks, () => 0);
  const d = new Date(baseMs + t * 1000);
  return <time className="cf-clock" dateTime={d.toISOString()}>{d.toLocaleTimeString("en-GB", { timeZone: "Asia/Kuala_Lumpur", hour12: false })}</time>;
}
