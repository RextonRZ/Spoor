"use client";
/**
 * "Compare with what really happened" (reviewer 01:25, Rexton). The simulation's own story parcel, rendered from the
 * hub with its people and moving cartons (assets/tour/truth_render.py), played behind its own button and never inside
 * Spoor's answer: ground truth used only to grade. The label stays on screen the whole time. When the clip ends,
 * Spoor's evidence route and the place it names are drawn over the last frame (with that frame's own projection), so
 * the two can be compared by eye; the one line under it compares the place Spoor names with the true one, and says so
 * plainly if they ever differ.
 */
import { useEffect, useRef, useState } from "react";
import { onFrame, volume } from "./spin";

export interface Truth { label: string; fps: number; frames: number; P: number[][]; marker: [number, number][];
  truth: { zone: string; zone_name: string; where: string } }
type XY = [number, number];
const PLAY_FPS = 20;   // the simulation runs at 10 fps: the clip plays at twice its speed

export function TruthCompare({ src, truth, legs, zone, answerZone, answerName, onClose }: {
  src: string; truth: Truth; legs: [number, number, number?][][]; zone?: number[][]; answerZone: string | null; answerName: string; onClose: () => void;
}) {
  const v = useRef<HTMLVideoElement>(null);
  const [f, setF] = useState(0);
  const [ended, setEnded] = useState(false);
  useEffect(() => {
    const el = v.current; if (!el) return;
    let id = 0;
    const tick = () => {
      setF(Math.min(truth.frames - 1, Math.round(el.currentTime * PLAY_FPS)));
      id = el.requestVideoFrameCallback(tick);
    };
    id = el.requestVideoFrameCallback(tick);
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", k);
    return () => { el.cancelVideoFrameCallback(id); window.removeEventListener("keydown", k); };
  }, [truth.frames, onClose]);

  const P = truth.P[f];
  const mk = truth.marker[f];
  const line = (pts: [number, number, number?][]) => pts.map(([x, y, z]) => onFrame(P, x, y, z ?? 0)).filter((q): q is XY => !!q)
    .map(([x, y]) => `${x.toFixed(4)},${y.toFixed(4)}`).join(" ");
  const vol = ended && zone ? volume(P, zone, 2.4) : null;
  const same = answerZone != null && answerZone === truth.truth.zone;
  return (
    <div className="tc" role="dialog" aria-label="What really happened in the simulation">
      <video ref={v} className="tc-v" src={src} autoPlay muted playsInline onEnded={() => setEnded(true)} />
      {mk && (
        <span className="tc-mk" style={{ left: `${mk[0] * 100}%`, top: `${(1 - mk[1]) * 100}%` }}><i />{ended ? "Where it really is" : "The parcel"}</span>
      )}
      {ended && (
        <svg className="tc-ev" viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden>
          {vol?.floor && <polygon className="tc-zone" points={vol.floor} />}
          {vol?.top && <polygon className="tc-zone-top" points={vol.top} />}
          {legs.map((pts, i) => <polyline key={i} points={line(pts)} />)}
        </svg>
      )}
      <p className="tc-label">{truth.label}</p>
      <div className="tc-foot">
        <p className="tc-line" data-same={same ? "" : undefined}>
          <span>Spoor&apos;s answer: <b>{answerName || "none yet"}</b></span>
          <span>Truth: <b>{truth.truth.zone_name}</b></span>
          <em>{same ? "Same place" : answerZone ? "They differ" : "No answer to compare"}</em>
        </p>
        {ended && <p className="tc-key"><i />Spoor&apos;s evidence route and the place it names <b className="tc-key-t" />the parcel in the simulation</p>}
        <div className="tc-acts">
          <button type="button" className="hc-x" onClick={onClose}><svg viewBox="0 0 24 24" aria-hidden><path d="M15 5l-7 7 7 7" /></svg>Back to the answer</button>
          {ended && <button type="button" className="hc-x" onClick={() => { setEnded(false); const el = v.current; if (el) { el.currentTime = 0; void el.play(); } }}>Play again</button>}
        </div>
      </div>
    </div>
  );
}
