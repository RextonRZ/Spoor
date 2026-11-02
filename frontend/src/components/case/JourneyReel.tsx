"use client";

/**
 * The parcel's journey (Rexton, 2 Nov): ONE player and a step rail. The video is the case's journey reel, built by
 * the API from stored evidence only (every checkpoint's clip in time order, SAM's own outline on the carton where it
 * followed it, the number only on a labelled handshake, cards where nothing can be seen). A step seeks the player to
 * its chapter and stops at its end; "Play the whole journey" runs every chapter in order. Gaps between steps are the
 * time between them; the part after the last scan is red.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { api, signedUrl, useResource } from "@/lib/api";
import "./journeyreel.css";

interface Chapter { title: string; tone: "scan" | "noscan" | "card"; t: string; start_s: number; end_s: number; camera: string;
  label: string | null; sub: string }
interface Reel { reel_id: string; seconds: number; chapters: Chapter[]; url: string }

const hms = (iso: string) => new Date(iso).toLocaleTimeString("en-GB", { timeZone: "Asia/Kuala_Lumpur", hour12: false });
const camWords = (c: string) => c.replace("CHK_", "close-up ").replace("_", " ").replace("close-up CAGE W", "close-up cage W");

function gapWords(ms: number): string {
  const s = Math.round(ms / 1000);
  if (s < 90) return `${s} s`;
  const m = Math.round(s / 60);
  return m < 90 ? `${m} min` : `${Math.round(m / 60)} h`;
}

export function JourneyReel({ caseId }: { caseId: string }) {
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
  const [on, setOn] = useState(0);
  const [stopAt, setStopAt] = useState<number | null>(null);
  const steps = useMemo(() => (reel?.chapters ?? []), [reel]);
  const firstGap = steps.findIndex((c) => c.tone !== "scan");

  useEffect(() => {
    const v = video.current;
    if (!v || !steps.length) return;
    const tick = () => {
      const i = steps.findIndex((c) => v.currentTime >= c.start_s && v.currentTime < c.end_s);
      if (i >= 0) setOn(i);
      if (stopAt !== null && v.currentTime >= stopAt - 0.05) { v.pause(); setStopAt(null); }
    };
    v.addEventListener("timeupdate", tick);
    return () => v.removeEventListener("timeupdate", tick);
  }, [steps, stopAt]);

  const play = (i: number | null) => {
    const v = video.current;
    if (!v) return;
    const c = i === null ? null : steps[i];
    v.currentTime = c ? c.start_s + 0.01 : 0;
    setStopAt(c ? c.end_s : null);
    if (c) setOn(i!);
    void v.play().catch(() => undefined);
  };

  if (!reel) {
    return (
      <div className="jr" aria-busy="true">
        <div className="jr-stage jr-wait"><span>{failed ? "The journey video could not be made. Try again later" : making ? "Putting the clips together, a few seconds" : "Loading the journey"}</span></div>
      </div>
    );
  }
  const cur = steps[on];
  return (
    <div className="jr">
      <div className="jr-top">
        <button type="button" className="hb-btn hb-btn-primary jr-all" onClick={() => play(null)}>Play the whole journey</button>
        <span className="jr-meta">{steps.length} steps · {Math.round(reel.seconds)} s · outline: SAM 3.1, where it followed the carton</span>
        <a className="jr-dl" href={signedUrl(reel.url)} download={`${reel.reel_id}.mp4`}>Download MP4</a>
      </div>
      <figure className="jr-stage">
        <video ref={video} src={signedUrl(reel.url)} muted playsInline preload="metadata" controls
          aria-label={cur ? `${hms(cur.t)}: ${cur.title}` : "The parcel's journey"} />
      </figure>
      <ol className="jr-rail" aria-label="The journey, step by step">
        {steps.map((c, i) => {
          const prev = steps[i - 1];
          // the time between two filmed steps (a card names its own stretch, so no connector beside it)
          const gap = prev ? Date.parse(c.t) - Date.parse(prev.t) : 0;
          return (
            <li key={`${c.t}-${i}`} className="jr-step" data-tone={c.tone} data-on={i === on ? "" : undefined}
              data-after={firstGap >= 0 && i >= firstGap ? "" : undefined}>
              {prev && gap >= 2000 && c.camera && prev.camera && <span className="jr-gap" aria-label={`${gapWords(gap)} later`}>{gapWords(gap)}</span>}
              <button type="button" className="jr-btn" aria-pressed={i === on} onClick={() => play(i)}>
                <span className="jr-time">{hms(c.t)}</span>
                <span className="jr-title">{c.title}</span>
                <span className="jr-badge">{c.tone === "scan" ? "Scanned here" : c.tone === "noscan" ? "No scan" : "Answer"}</span>
                {c.camera && <span className="jr-cam">{camWords(c.camera)}</span>}
                {c.label && <span className="jr-num">{c.label}</span>}
              </button>
            </li>
          );
        })}
      </ol>
      {cur?.sub && <p className="jr-sub">{cur.sub}</p>}
    </div>
  );
}
