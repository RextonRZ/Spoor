"use client";

/**
 * The parcel's journey (Rexton, 2 Nov): ONE player and a step strip. The video is the case's journey reel, built by
 * the API from stored evidence only (every checkpoint's clip in time order, SAM's own outline on the carton where it
 * followed it, the number only on a labelled handshake, cards where nothing can be seen). A step seeks the player to
 * its chapter and stops at its end; "Play the whole journey" runs every chapter in order.
 * Rexton, 3 Nov: each step shows its own frame (a thumbnail the API cut from the reel), and the player has its own
 * controls: a scrubber split into the steps (hover shows the step's frame), play, time, full screen.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, signedUrl, useResource } from "@/lib/api";
import "./journeyreel.css";

// red only where the records fail (not scanned in at the store; a record the cameras contradict); seen on camera is grey
type Tone = "scan" | "seen" | "noscan" | "record" | "wait" | "card";
const BADGE: Record<Tone, string> = { scan: "Scanned", seen: "On camera", noscan: "Not scanned in", record: "Records disagree",
  wait: "No camera", card: "Answer" };
export interface Chapter { title: string; tone: Tone; t: string; start_s: number; end_s: number; camera: string;
  label: string | null; sub: string; xy?: [number, number] | null; last_scan?: boolean; thumb_url?: string }
export interface Reel { reel_id: string; seconds: number; chapters: Chapter[]; url: string }

const hms = (iso: string) => new Date(iso).toLocaleTimeString("en-GB", { timeZone: "Asia/Kuala_Lumpur", hour12: false });
const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
// who saw it, short ("CAM 11", "Unload close-up", "Tunnel photo"); the full words go in the tooltip
const CLOSE: Record<string, string> = { UNLOAD: "Unload", TUNNEL: "Tunnel", CAGE_W: "Cage", CAGE_E: "Cage", STORE: "Store door",
  DOCK: "Dock", CHUTE: "Chute" };
const camShort = (c: string) => c === "Tunnel reader" ? "Tunnel photo"
  : c.startsWith("CHK_") ? `${CLOSE[c.slice(4)] ?? c.slice(4).toLowerCase().replace("_", " ")} close-up` : c.replace("_", " ");
const camLong = (c: string) => c === "Tunnel reader" ? "The tunnel reader's own photo"
  : c.startsWith("CHK_") ? `Seen on the ${camShort(c).toLowerCase()} camera` : `Seen on ${c.replace("_", " ")}`;

function gapWords(ms: number): string {
  const s = Math.round(ms / 1000);
  if (s < 90) return `${s} s`;
  const m = Math.round(s / 60);
  return m < 90 ? `${m} min` : `${Math.round(m / 60)} h`;
}

/** "Watch the proof" on the answer plays this reel in place (it was a second, frame-by-frame player of the same clips) */
export const PLAY_JOURNEY = "spoor:play-journey";

/** a map stop (Proof) seeks the reel to its chapter: detail = the chapter's index */
export const SEEK_JOURNEY = "spoor:seek-journey";

const Icon = {
  play: <svg viewBox="0 0 24 24" aria-hidden><path d="M8 5.6v12.8a1 1 0 0 0 1.5.86l10.4-6.4a1 1 0 0 0 0-1.72L9.5 4.74A1 1 0 0 0 8 5.6Z" fill="currentColor" /></svg>,
  pause: <svg viewBox="0 0 24 24" aria-hidden><rect x="6.5" y="5" width="4" height="14" rx="1.3" fill="currentColor" /><rect x="13.5" y="5" width="4" height="14" rx="1.3" fill="currentColor" /></svg>,
  full: <svg viewBox="0 0 24 24" aria-hidden><path d="M4.5 9V5.5a1 1 0 0 1 1-1H9M15 4.5h3.5a1 1 0 0 1 1 1V9M19.5 15v3.5a1 1 0 0 1-1 1H15M9 19.5H5.5a1 1 0 0 1-1-1V15" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>,
  shrink: <svg viewBox="0 0 24 24" aria-hidden><path d="M9 4.5V8a1 1 0 0 1-1 1H4.5M19.5 9H16a1 1 0 0 1-1-1V4.5M15 19.5V16a1 1 0 0 1 1-1h3.5M4.5 15H8a1 1 0 0 1 1 1v3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>,
  check: <svg viewBox="0 0 12 12" aria-hidden><path d="M2.5 6.2 5 8.6l4.5-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>,
};

export function JourneyReel({ caseId, onStep }: { caseId: string; onStep?: (i: number) => void }) {
  const r = useResource<Reel>(`/v1/cases/${caseId}/journey-reel`);
  const [made, setMade] = useState<Reel | null>(null);
  const [failed, setFailed] = useState(false);
  const started = useRef(false);
  const reel = made ?? r.data ?? null;
  const missing = !r.data && !!r.error;
  useEffect(() => {  // built from stored evidence only (no model calls): made the first time a case is opened
    if (!missing || started.current) return;
    started.current = true;
    api<Reel>(`/v1/cases/${caseId}/journey-reel`, { method: "POST" }).then(setMade).catch(() => setFailed(true));
  }, [missing, caseId]);
  const making = missing && !made && !failed;

  const video = useRef<HTMLVideoElement>(null);
  const stage = useRef<HTMLElement>(null);
  const strip = useRef<HTMLOListElement>(null);
  const [on, setOn] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [idle, setIdle] = useState(false);
  const [full, setFull] = useState(false);
  const [now, setNow] = useState(0);
  const [hover, setHover] = useState<{ i: number; x: number } | null>(null);
  const stopAt = useRef<number | null>(null);
  const steps = useMemo(() => (reel?.chapters ?? []), [reel]);
  const total = reel?.seconds ?? 1;
  const fills = useRef<(HTMLSpanElement | null)[]>([]);
  const tileFills = useRef<(HTMLSpanElement | null)[]>([]);
  const firstGap = steps.findIndex((c) => c.tone !== "scan");

  // progress drawn every frame while playing (transform only), the step and the clock at 4 Hz through state
  useEffect(() => {
    const v = video.current;
    if (!v || !steps.length) return;
    let raf = 0;
    const draw = () => {
      const t = v.currentTime;
      steps.forEach((c, i) => {
        const p = Math.min(1, Math.max(0, (t - c.start_s) / Math.max(0.01, c.end_s - c.start_s)));
        const f = fills.current[i];
        if (f) f.style.transform = `scaleX(${p})`;
        const g = tileFills.current[i];
        if (g) g.style.transform = `scaleX(${t >= c.start_s && t < c.end_s ? p : 0})`;
      });
      if (stopAt.current !== null && t >= stopAt.current - 0.05) { v.pause(); stopAt.current = null; }
      if (!v.paused) raf = requestAnimationFrame(draw);
    };
    const tick = () => {
      const i = steps.findIndex((c) => v.currentTime >= c.start_s && v.currentTime < c.end_s);
      if (i >= 0) setOn(i);
      setNow(v.currentTime);
      if (v.paused) draw();
    };
    const onPlay = () => { setPlaying(true); cancelAnimationFrame(raf); raf = requestAnimationFrame(draw); };
    const onPause = () => { setPlaying(false); setIdle(false); draw(); };
    v.addEventListener("timeupdate", tick);
    v.addEventListener("seeked", tick);
    v.addEventListener("play", onPlay);
    v.addEventListener("pause", onPause);
    v.addEventListener("ended", onPause);
    return () => {
      cancelAnimationFrame(raf);
      v.removeEventListener("timeupdate", tick); v.removeEventListener("seeked", tick);
      v.removeEventListener("play", onPlay); v.removeEventListener("pause", onPause); v.removeEventListener("ended", onPause);
    };
  }, [steps]);

  const play = useCallback((i: number | null) => {
    const v = video.current;
    if (!v) return;
    const c = i === null ? null : steps[i];
    v.currentTime = c ? c.start_s + 0.01 : 0;
    stopAt.current = c ? c.end_s : null;
    if (c) setOn(i!);
    void v.play().catch(() => undefined);
  }, [steps]);

  const toggle = () => {
    const v = video.current;
    if (!v) return;
    if (v.paused) {
      if (v.ended || v.currentTime >= total - 0.1) v.currentTime = 0;
      void v.play().catch(() => undefined);
    } else v.pause();
  };

  const fullscreen = () => {
    const el = stage.current, v = video.current as (HTMLVideoElement & { webkitEnterFullscreen?: () => void }) | null;
    if (document.fullscreenElement) { void document.exitFullscreen(); return; }
    if (el?.requestFullscreen) void el.requestFullscreen().catch(() => undefined);
    else v?.webkitEnterFullscreen?.();  // iPhone Safari: only the video itself can go full screen
  };
  useEffect(() => {
    const f = () => setFull(document.fullscreenElement === stage.current);
    document.addEventListener("fullscreenchange", f);
    return () => document.removeEventListener("fullscreenchange", f);
  }, []);

  // the controls step aside after 2.2 s without the pointer moving, only while playing
  const idleT = useRef<number>(0);
  const wake = () => {
    setIdle(false);
    window.clearTimeout(idleT.current);
    idleT.current = window.setTimeout(() => setIdle(true), 2200);
  };
  useEffect(() => () => window.clearTimeout(idleT.current), []);

  // the scrubber: a press or drag anywhere on it seeks; the steps keep their share of the length
  const scrub = useRef<HTMLDivElement>(null);
  const timeAt = (x: number) => {
    const b = scrub.current!.getBoundingClientRect();
    return Math.min(1, Math.max(0, (x - b.left) / b.width)) * total;
  };
  const stepAt = (t: number) => Math.max(0, steps.findIndex((c) => t >= c.start_s && t < c.end_s));
  const seekTo = (x: number) => {
    const v = video.current;
    if (!v) return;
    stopAt.current = null;
    v.currentTime = timeAt(x);
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === " " || e.key === "k") { e.preventDefault(); toggle(); }
    else if (e.key === "f") { e.preventDefault(); fullscreen(); }
    else if (e.key === "ArrowRight") { e.preventDefault(); play(Math.min(steps.length - 1, on + 1)); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); play(Math.max(0, on - 1)); }
  };

  const box = useRef<HTMLDivElement>(null);
  const playRef = useRef(play);
  useEffect(() => { playRef.current = play; });
  useEffect(() => {
    const go = () => {
      box.current?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
      playRef.current(null);
    };
    const seek = (e: Event) => playRef.current((e as CustomEvent<number>).detail);
    window.addEventListener(PLAY_JOURNEY, go);
    window.addEventListener(SEEK_JOURNEY, seek);
    return () => { window.removeEventListener(PLAY_JOURNEY, go); window.removeEventListener(SEEK_JOURNEY, seek); };
  }, []);
  useEffect(() => { onStep?.(on); }, [on, onStep]);
  // the strip scrolls itself (never the page) so the step playing stays in view on a phone
  useEffect(() => {
    const s = strip.current, li = s?.children[on] as HTMLElement | undefined;
    if (!s || !li || s.scrollWidth <= s.clientWidth) return;
    const left = li.offsetLeft - (s.clientWidth - li.offsetWidth) / 2;
    s.scrollTo({ left, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }, [on]);

  if (!reel) {
    return (
      <div className="jr" aria-busy="true">
        <div className="jr-stage jr-wait"><span>{failed ? "The journey video could not be made. Try again later" : making ? "Putting the clips together, a few seconds" : "Loading the journey"}</span></div>
      </div>
    );
  }
  const cur = steps[on];
  const hv = hover ? steps[hover.i] : null;
  return (
    <div className="jr" ref={box}>
      <div className="jr-top">
        <button type="button" className="hb-btn hb-btn-primary jr-all" onClick={() => play(null)}>Play the whole journey</button>
        <span className="jr-meta">{steps.length} steps · {Math.round(reel.seconds)} s · green outline: SAM 3.1 following the carton</span>
        <a className="jr-dl" href={signedUrl(reel.url)} download={`${reel.reel_id}.mp4`}>Download MP4</a>
      </div>
      <figure ref={stage} className="jr-stage" tabIndex={0} onKeyDown={onKey} onPointerMove={wake}
        data-playing={playing ? "" : undefined} data-idle={playing && idle && !hover ? "" : undefined} data-full={full ? "" : undefined}
        aria-label={`Journey player. ${cur ? `Step ${on + 1} of ${steps.length}: ${cur.title}` : ""}. Space plays or pauses, arrows move between steps, F for full screen`}>
        <video ref={video} src={signedUrl(reel.url)} muted playsInline preload="auto" onClick={toggle}
          onLoadedMetadata={(e) => { if (e.currentTarget.currentTime === 0) e.currentTarget.currentTime = 1.2; }} />
        <button type="button" className="jr-big" onClick={toggle} aria-label="Play" tabIndex={playing ? -1 : 0} aria-hidden={playing}>{Icon.play}</button>
        <div className="jr-bar">
          <div ref={scrub} className="jr-scrub" role="slider" aria-label="Position in the journey" aria-valuemin={0}
            aria-valuemax={Math.round(total)} aria-valuenow={Math.round(now)} aria-valuetext={`${clock(now)}, step ${on + 1}`}
            onPointerDown={(e) => { e.currentTarget.setPointerCapture(e.pointerId); seekTo(e.clientX); }}
            onPointerMove={(e) => {
              const b = e.currentTarget.getBoundingClientRect();
              setHover({ i: stepAt(timeAt(e.clientX)), x: Math.min(Math.max(e.clientX - b.left, 92), b.width - 92) });
              if (e.currentTarget.hasPointerCapture(e.pointerId)) seekTo(e.clientX);
            }}
            onPointerLeave={() => setHover(null)}>
            {steps.map((c, i) => (
              <span key={i} className="jr-seg" style={{ flexGrow: Math.max(0.2, c.end_s - c.start_s) }} data-tone={c.tone}
                data-on={i === on ? "" : undefined} data-hover={hover?.i === i ? "" : undefined}>
                <span className="jr-seg-fill" ref={(el) => { fills.current[i] = el; }} />
              </span>
            ))}
            {hv && hover && (
              <span className="jr-peek" style={{ left: hover.x }} aria-hidden>
                {hv.thumb_url ? <img src={signedUrl(hv.thumb_url)} alt="" /> : <span className="jr-peek-none" />}
                <span className="jr-peek-t"><b>{hover.i + 1}</b>{hv.title}</span>
              </span>
            )}
          </div>
          <div className="jr-row">
            <button type="button" className="jr-ic" onClick={toggle} aria-label={playing ? "Pause" : "Play"}>{playing ? Icon.pause : Icon.play}</button>
            <span className="jr-clock">{clock(now)} <span>/ {clock(total)}</span></span>
            {cur && <span className="jr-now">Step {on + 1} of {steps.length}</span>}
            <button type="button" className="jr-ic jr-fs" onClick={fullscreen} aria-label={full ? "Exit full screen" : "Full screen"}>{full ? Icon.shrink : Icon.full}</button>
          </div>
        </div>
      </figure>
      <ol ref={strip} className="jr-rail" aria-label="The journey, step by step">
        {steps.map((c, i) => {
          const prev = steps[i - 1];
          // the time between two filmed steps (a card names its own stretch, so no gap beside it)
          const gap = prev ? Date.parse(c.t) - Date.parse(prev.t) : 0;
          const showGap = prev && gap >= 2000 && c.camera && prev.camera;
          const status = c.last_scan ? "Last scan" : BADGE[c.tone] ?? "On camera";
          const number = c.label ? (c.camera === "Tunnel reader" ? "Number read by the tunnel" : "Number confirmed on camera") : "";
          return (
            <li key={`${c.t}-${i}`} className="jr-step" data-tone={c.tone} data-on={i === on ? "" : undefined}
              data-after={firstGap >= 0 && i >= firstGap ? "" : undefined}>
              <span className="jr-gap">{showGap ? `+${gapWords(gap)}` : ""}</span>
              <button type="button" className="jr-btn" aria-pressed={i === on} onClick={() => play(i)}
                title={[c.camera ? camLong(c.camera) : "", number].filter(Boolean).join(" · ") || undefined}>
                <span className="jr-thumb">
                  {c.thumb_url ? <img src={signedUrl(c.thumb_url)} alt="" decoding="async" /> : <span className="jr-thumb-none" />}
                  <span className="jr-n" aria-hidden>{i + 1}</span>
                  <span className="jr-time">{hms(c.t)}</span>
                  {number && <span className="jr-id" aria-label={number}>{Icon.check}</span>}
                  <span className="jr-tfill" ref={(el) => { tileFills.current[i] = el; }} />
                </span>
                <span className="jr-title">{c.title}</span>
                <span className="jr-status" data-last={c.last_scan ? "" : undefined}>{status}</span>
                {c.camera && <span className="jr-cam">{camShort(c.camera)}</span>}
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
