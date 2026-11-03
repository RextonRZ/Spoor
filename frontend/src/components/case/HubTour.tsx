"use client";
/**
 * The route in the Blender hub (Rexton 3 Nov: "the 3D should be from Blender", "click a point and see what the box was
 * doing"). A drone fly-through rendered in Blender from the hub model only (people, moving cartons and roof hidden:
 * assets/tour/tour_render.py), with a table of where every step's point falls on each frame. The pins and the carton
 * marker are drawn here from that table, so every mark is the case's evidence (camera and scan positions) and the
 * picture underneath is just the building.
 *
 * Navigation is one row of numbered steps (no free orbit to get lost in): the next step flies there, any other step
 * cross-fades to it; Play flies the whole route. The card beside it is the step's own camera frame and words.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { signedUrl, useResource } from "@/lib/api";
import { SEEK_JOURNEY, type Chapter, type Reel } from "./JourneyReel";
import { CameraSetup } from "./CameraSetup";
import "./hubtour.css";

interface Tour { fps: number; frames: number; size: [number, number]; steps: { n: number; arrive: number; title: string; tone: string }[];
  pins: [number, number][][]; marker: [number, number][] }

const hms = (iso: string) => new Date(iso).toLocaleTimeString("en-GB", { timeZone: "Asia/Kuala_Lumpur", hour12: false });
const CHIP: Record<string, string> = { scan: "Scanned", seen: "On camera", noscan: "Not scanned in", record: "Records disagree", wait: "No camera" };
const camWords = (c: string) => !c ? "No camera" : c === "Tunnel reader" ? "The tunnel reader's photo"
  : c.startsWith("CHK_") ? `${c.slice(4).toLowerCase().replace("_w", "").replace("_e", "").replace("_", " ")} close-up camera`.replace(/^\w/, (x) => x.toUpperCase()) : c.replace("_", " ");
const REDUCED = () => typeof window !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;

export function HubTour({ caseId }: { caseId: string }) {
  const [tour, setTour] = useState<Tour | null | "none">(null);
  const [mode, setMode] = useState<"route" | "cameras">("route");
  const reel = useResource<Reel>(`/v1/cases/${caseId}/journey-reel`);
  const steps: Chapter[] = useMemo(() => (reel.data?.chapters ?? []).filter((c) => c.tone !== "card"), [reel.data]);
  const video = useRef<HTMLVideoElement>(null);
  const [frame, setFrame] = useState(0);
  const [on, setOn] = useState(0);
  const [playing, setPlaying] = useState<"all" | "to" | null>(null);
  const [fading, setFading] = useState(false);
  const stopAt = useRef<number | null>(null);

  useEffect(() => {
    let live = true;
    fetch(`/tour/${caseId}/tour.json`).then((r) => r.ok ? r.json() : "none").then((j) => { if (live) setTour(j); }).catch(() => live && setTour("none"));
    return () => { live = false; };
  }, [caseId]);
  const t = tour && tour !== "none" ? tour : null;

  // steps that share a place share one pin ("8-10"); the pin shows the step you are on when it is one of them
  const groups = useMemo(() => {
    const g: number[][] = [];
    steps.forEach((c, i) => {
      const prev = g.at(-1);
      const same = prev && steps[prev[0]].xy && c.xy && Math.hypot(steps[prev[0]].xy![0] - c.xy[0], steps[prev[0]].xy![1] - c.xy[1]) < 0.5;
      if (same || (prev && !c.xy)) prev!.push(i); else g.push([i]);
    });
    return g;
  }, [steps]);

  // follow the video frame by frame: the marks move with the picture, and the step is whichever was last arrived at
  useEffect(() => {
    const v = video.current; if (!v || !t) return;
    let id = 0;
    const tick = () => {
      const f = Math.min(t.frames - 1, Math.round(v.currentTime * t.fps));
      setFrame(f);
      const k = t.steps.reduce((best, s, i) => s.arrive <= f ? i : best, 0);
      if (playing === "all") setOn(k);
      if (stopAt.current !== null && f >= stopAt.current) { v.pause(); stopAt.current = null; setPlaying(null); }
      if (v.ended) setPlaying(null);
      id = "requestVideoFrameCallback" in v ? (v as HTMLVideoElement & { requestVideoFrameCallback: (cb: () => void) => number }).requestVideoFrameCallback(tick) : requestAnimationFrame(tick);
    };
    tick();
    return () => { if ("cancelVideoFrameCallback" in v) (v as HTMLVideoElement & { cancelVideoFrameCallback: (n: number) => void }).cancelVideoFrameCallback(id); else cancelAnimationFrame(id); };
  }, [t, playing]);

  const goTo = useCallback((k: number) => {
    const v = video.current; if (!v || !t || k < 0 || k >= t.steps.length) return;
    const target = t.steps[k].arrive / t.fps + 0.01;
    setOn(k);
    if (k === on + 1 && !REDUCED()) {          // the next step: fly there
      stopAt.current = t.steps[k].arrive; setPlaying("to"); void v.play();
      return;
    }
    v.pause(); stopAt.current = null; setPlaying(null);
    if (REDUCED()) { v.currentTime = target; return; }
    setFading(true);                           // any other step: a short blurred cross-fade, no long rewind
    window.setTimeout(() => { v.currentTime = target; }, 120);
  }, [t, on]);
  const playAll = () => {
    const v = video.current; if (!v || !t) return;
    if (playing) { v.pause(); setPlaying(null); stopAt.current = null; return; }
    if (v.ended || frame >= t.frames - 2) v.currentTime = 0;
    stopAt.current = null; setPlaying("all"); void v.play();
  };

  const cur = steps[on];
  // the cameras this route was seen on, with their step numbers (for the camera setup's highlight)
  const used: Record<string, number[]> = {};
  steps.forEach((c, i) => { if (/^(CAM|CHK)_/.test(c.camera)) (used[c.camera] ??= []).push(i + 1); });
  const modes = (
    <div className="ht-modes" role="tablist" aria-label="3D hub view">
      <button type="button" role="tab" aria-selected={mode === "route"} onClick={() => setMode("route")}>The parcel&apos;s route</button>
      <button type="button" role="tab" aria-selected={mode === "cameras"} onClick={() => { video.current?.pause(); setPlaying(null); setMode("cameras"); }}>Camera setup</button>
    </div>
  );
  if (mode === "cameras") return <div className="ht">{modes}<CameraSetup used={used} /></div>;
  if (tour === "none") return <div className="ht">{modes}<p className="ht-none">The 3D route has not been exported for this case yet.</p></div>;
  const pins = t?.pins[Math.min(frame, t.pins.length - 1)] ?? [];
  const mk = t?.marker[Math.min(frame, t.marker.length - 1)];

  return (
    <div className="ht" onKeyDown={(e) => { if (e.key === "ArrowRight") goTo(on + 1); if (e.key === "ArrowLeft") goTo(on - 1); }}>
      {modes}
      <div className="ht-main">
        <div className="ht-stage" data-fading={fading ? "" : undefined} style={t ? { aspectRatio: `${t.size[0]} / ${t.size[1]}` } : undefined}>
          {t && <video ref={video} className="ht-video" src={`/tour/${caseId}/tour.mp4`} muted playsInline preload="auto"
            onSeeked={() => setFading(false)} aria-label="Fly-through of the hub model along the parcel's route" />}
          {t && (
            <div className="ht-marks" aria-hidden>
              {groups.map((g) => {
                const p = pins[g[0]]; if (!p) return null;
                const [u, v] = p; if (u < 0.02 || u > 0.98 || v < 0.03 || v > 0.97) return null;
                const here = g.includes(on), c = steps[here ? on : g[0]];
                const label = g.length > 1 ? `${g[0] + 1}–${g.at(-1)! + 1}` : `${g[0] + 1}`;
                return (
                  <button key={g[0]} type="button" tabIndex={-1} className="ht-pin" data-tone={c.tone} data-on={here ? "" : undefined}
                    style={{ left: `${u * 100}%`, top: `${(1 - v) * 100}%` }} onClick={() => goTo(here ? on : g[0])}>
                    <span className="ht-pin-n">{here ? on + 1 : label}</span>
                    {here && <span className="ht-pin-tag"><b>{c.title}</b><small>{hms(c.t)}</small></span>}
                  </button>
                );
              })}
              {mk && mk[0] > 0 && mk[0] < 1 && mk[1] > 0 && mk[1] < 1 && (
                <span className="ht-carton" style={{ left: `${mk[0] * 100}%`, top: `${(1 - mk[1]) * 100}%` }}>
                  <svg viewBox="0 0 32 32"><path className="ht-c-top" d="M16 4 28 10 16 16 4 10z" /><path className="ht-c-l" d="M4 10 16 16v13L4 23z" /><path className="ht-c-r" d="M28 10 16 16v13l12-6z" /><path className="ht-c-tape" d="M10 7 22 13v3" /></svg>
                </span>
              )}
            </div>
          )}
          {!t && <span className="ht-wait" />}
          <div className="ht-ctl">
            <button type="button" className="ht-play" onClick={playAll} disabled={!t}>
              {playing === "all" ? <svg viewBox="0 0 24 24" aria-hidden><rect x="6.5" y="5" width="4" height="14" rx="1.3" /><rect x="13.5" y="5" width="4" height="14" rx="1.3" /></svg>
                : <svg viewBox="0 0 24 24" aria-hidden><path d="M8 5.6v12.8a1 1 0 0 0 1.5.86l10.4-6.4a1 1 0 0 0 0-1.72L9.5 4.74A1 1 0 0 0 8 5.6Z" /></svg>}
              {playing === "all" ? "Pause" : "Fly the route"}
            </button>
          </div>
        </div>
        <ol className="ht-rail" aria-label="Steps">
          {steps.map((c, i) => (
            <li key={i}>
              <button type="button" className="ht-step" data-tone={c.tone} aria-current={on === i ? "step" : undefined} onClick={() => goTo(i)}>
                <span className="ht-step-n">{i + 1}</span><span className="ht-step-t">{hms(c.t).slice(0, 5)}</span>
              </button>
            </li>
          ))}
        </ol>
      </div>

      {cur && (
        <aside className="ht-card" aria-live="polite">
          <figure className="ht-frame">
            {/* eslint-disable-next-line @next/next/no-img-element -- the step's own frame, cut from its camera by the API */}
            {cur.thumb_url ? <img key={on} src={signedUrl(cur.thumb_url)} alt={`${cur.title}, ${camWords(cur.camera)}`} /> : <span className="ht-frame-none">No camera saw this step</span>}
          </figure>
          <div className="ht-card-top"><span className="ht-n">Step {on + 1} of {steps.length}</span><span className="ht-chip" data-tone={cur.tone}>{cur.last_scan ? "Last scan" : CHIP[cur.tone]}</span></div>
          <h3 className="ht-title">{cur.title}</h3>
          {cur.sub && <p className="ht-sub">{cur.sub}</p>}
          <p className="ht-meta">{hms(cur.t)} · {camWords(cur.camera)}</p>
          <div className="ht-acts">
            <button type="button" className="ht-btn" onClick={() => goTo(on - 1)} disabled={on === 0} aria-label="Previous step">
              <svg viewBox="0 0 24 24" aria-hidden><path d="M15 5l-7 7 7 7" /></svg></button>
            <button type="button" className="ht-btn ht-btn-main" onClick={() => {
              window.dispatchEvent(new CustomEvent(SEEK_JOURNEY, { detail: on }));
              document.querySelector(".pf-reel")?.scrollIntoView({ behavior: REDUCED() ? "auto" : "smooth", block: "center" });
            }}>Watch it on camera</button>
            <button type="button" className="ht-btn" onClick={() => goTo(on + 1)} disabled={on >= steps.length - 1} aria-label="Next step">
              <svg viewBox="0 0 24 24" aria-hidden><path d="M9 5l7 7-7 7" /></svg></button>
          </div>
        </aside>
      )}
      <p className="ht-note">The hub model, rendered in Blender. The pins and the carton are placed from the cameras and scans; the moves between steps are drawn, not filmed.</p>
    </div>
  );
}
