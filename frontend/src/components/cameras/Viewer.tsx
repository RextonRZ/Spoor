"use client";
/**
 * The big camera view: zoom with the wheel (or + and -), drag to pan, double-click to zoom in on a spot (again to
 * reset), 0 to reset, arrow keys to pan, full screen. Zoom is a transform on the picture (up to 5x), clamped so the
 * picture always covers the frame. The on-screen display (camera name, running clock, REC) stays put while the picture moves.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Clock, Feed } from "./Feed";

const MAX = 5;
type View = { s: number; x: number; y: number };

/** `image`: show this exact picture (a frame from a recording) instead of the camera's feed; `at`: a fixed time for the on-screen
 *  display (evidence of one moment) instead of the running live clock; `pill`: a status over the picture. */
export function Viewer({ id, label, src, baseMs = 0, image, at, pill, mark, clip }: {
  id: string; label: string; src?: string; baseMs?: number; image?: string; at?: string; pill?: { text: string; tone: string };
  /** a recording to play in place (the real video, not frame by frame): `time` in seconds into it; while paused an
   *  `image` (the outlined frame of the moment) may sit over it */
  clip?: { src: string; time: number; playing: boolean; rate: number; onTime: (s: number) => void; onEnd: () => void };
  /** an outline on the frame, in the frame's own pixels (wh); text is shown only when given (a label that is sure) */
  mark?: { box: number[]; wh: [number, number]; text?: string };
}) {
  const stage = useRef<HTMLDivElement>(null);
  const [v, setV] = useState<View>({ s: 1, x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number; vx: number; vy: number; moved: boolean } | null>(null);
  const [grab, setGrab] = useState(false);

  const clamp = useCallback((n: View): View => {
    const r = stage.current?.getBoundingClientRect();
    const w = r?.width ?? 0, h = r?.height ?? 0;
    const s = Math.min(MAX, Math.max(1, n.s));
    return { s, x: Math.min(0, Math.max(w - w * s, n.x)), y: Math.min(0, Math.max(h - h * s, n.y)) };
  }, []);
  // zoom by `f` keeping the point under (cx, cy) (frame pixels) still
  const zoomAt = useCallback((f: number, cx: number, cy: number) => {
    setV((o) => {
      const s = Math.min(MAX, Math.max(1, o.s * f));
      const k = s / o.s;
      return clamp({ s, x: cx - (cx - o.x) * k, y: cy - (cy - o.y) * k });
    });
  }, [clamp]);
  const centre = () => { const r = stage.current!.getBoundingClientRect(); return [r.width / 2, r.height / 2] as const; };
  const reset = () => setV({ s: 1, x: 0, y: 0 });

  useEffect(() => { // wheel must be non-passive to keep the page from scrolling while you zoom
    const el = stage.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      zoomAt(Math.exp(-e.deltaY * 0.0022), e.clientX - r.left, e.clientY - r.top);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [zoomAt]);

  const onKey = (e: React.KeyboardEvent) => {
    const [cx, cy] = centre();
    const step = 60;
    if (e.key === "+" || e.key === "=") zoomAt(1.4, cx, cy);
    else if (e.key === "-" || e.key === "_") zoomAt(1 / 1.4, cx, cy);
    else if (e.key === "0") reset();
    else if (e.key === "ArrowLeft") setV((o) => clamp({ ...o, x: o.x + step }));
    else if (e.key === "ArrowRight") setV((o) => clamp({ ...o, x: o.x - step }));
    else if (e.key === "ArrowUp") setV((o) => clamp({ ...o, y: o.y + step }));
    else if (e.key === "ArrowDown") setV((o) => clamp({ ...o, y: o.y - step }));
    else return;
    e.preventDefault();
  };
  const onDown = (e: React.PointerEvent) => {
    if (v.s <= 1) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { x: e.clientX, y: e.clientY, vx: v.x, vy: v.y, moved: false };
    setGrab(true);
  };
  const onMove = (e: React.PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    d.moved = true;
    setV((o) => clamp({ ...o, x: d.vx + e.clientX - d.x, y: d.vy + e.clientY - d.y }));
  };
  const onUp = () => { drag.current = null; setGrab(false); };
  const onDouble = (e: React.MouseEvent) => {
    const r = stage.current!.getBoundingClientRect();
    if (v.s > 1) reset();
    else zoomAt(2.5, e.clientX - r.left, e.clientY - r.top);
  };
  const full = () => {
    const el = stage.current;
    if (!el) return;
    if (document.fullscreenElement) void document.exitFullscreen();
    else void el.requestFullscreen?.();
  };

  return (
    <div className="cv">
      <div ref={stage} className={`cv-stage${grab ? " is-grab" : v.s > 1 ? " is-zoomed" : ""}`} tabIndex={0} role="application"
        aria-label={`${label}. Scroll to zoom, drag to move, plus and minus to zoom, zero to reset.`}
        onKeyDown={onKey} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp} onDoubleClick={onDouble}>
        <div className="cv-pic" style={{ transform: `translate(${v.x}px, ${v.y}px) scale(${v.s})` }}>
          {clip && <ClipVideo clip={clip} />}
          {image && !(clip && clip.playing) ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img className="cf-media" src={image} alt={`${id.replaceAll("_", " ")} at ${at ? at.slice(11, 19) : ""}`} draggable={false} />
          ) : clip ? null : <Feed id={id} src={src} eager />}
          {image && mark && (
            <svg className="cv-mark" viewBox={`0 0 ${mark.wh[0]} ${mark.wh[1]}`} preserveAspectRatio="xMidYMid slice" aria-hidden="true">
              <rect x={mark.box[0] - 6} y={mark.box[1] - 6} width={mark.box[2] - mark.box[0] + 12} height={mark.box[3] - mark.box[1] + 12} rx="6" />
              {mark.text && <text x={Math.min(Math.max(12, mark.box[0] - 6), mark.wh[0] - 16 * mark.text.length - 12)}
                y={mark.box[1] > 60 ? mark.box[1] - 16 : mark.box[3] + 36}>{mark.text}</text>}
            </svg>
          )}
        </div>
        {/* a recording carries its own burned-in name and clock */}
        <div className="cf-osd" aria-hidden="true" hidden={!!clip}>
          <span className="cf-name">{id.replaceAll("_", " ")}<em>{label}</em></span>
          {at ? <span className="cf-meta"><time className="cf-clock">{at}</time></span>
            : <span className="cf-meta"><i className="cf-rec" />REC<Clock baseMs={baseMs} /></span>}
        </div>
        {pill && <span className="cv-pill" data-tone={pill.tone}>{pill.text}</span>}
        <div className="cv-tools" onPointerDown={(e) => e.stopPropagation()} onDoubleClick={(e) => e.stopPropagation()}>
          <button type="button" onClick={() => { const [cx, cy] = centre(); zoomAt(1 / 1.4, cx, cy); }} aria-label="Zoom out" disabled={v.s <= 1}>
            <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 8h9" /></svg>
          </button>
          <span className="cv-zoom" aria-live="polite">{v.s.toFixed(1)}x</span>
          <button type="button" onClick={() => { const [cx, cy] = centre(); zoomAt(1.4, cx, cy); }} aria-label="Zoom in" disabled={v.s >= MAX}>
            <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 8h9M8 3.5v9" /></svg>
          </button>
          <button type="button" onClick={reset} aria-label="Reset zoom" disabled={v.s === 1}>
            <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 6.5V3h3.5M13 6.5V3H9.5M3 9.5V13h3.5M13 9.5V13H9.5" /></svg>
          </button>
          <button type="button" onClick={full} aria-label="Full screen">
            <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 6V2.5H6M10 2.5h3.5V6M13.5 10v3.5H10M6 13.5H2.5V10" /></svg>
          </button>
        </div>
      </div>
      <p className="cv-hint">Scroll to zoom · drag to move · double-click to zoom in on a spot</p>
    </div>
  );
}

/** The recording itself: seeks to `time` while paused, plays at `rate`, reports its time while playing. */
function ClipVideo({ clip }: { clip: NonNullable<Parameters<typeof Viewer>[0]["clip"]> }) {
  const v = useRef<HTMLVideoElement>(null);
  const { src, time, playing, rate, onTime, onEnd } = clip;
  useEffect(() => {
    const el = v.current;
    if (!el || playing) return;
    const seek = () => { if (Math.abs(el.currentTime - time) > 0.04) el.currentTime = Math.max(0, time); };
    if (el.readyState >= 1) seek(); else el.addEventListener("loadedmetadata", seek, { once: true });
  }, [time, playing, src]);
  useEffect(() => {
    const el = v.current;
    if (!el) return;
    el.playbackRate = rate;
    if (playing) el.play().catch(() => {}); else el.pause();
  }, [playing, rate]);
  return (
    <video ref={v} className="cf-media" src={src} muted playsInline preload="auto" aria-hidden="true"
      onTimeUpdate={(e) => playing && onTime(e.currentTarget.currentTime)} onEnded={onEnd} />
  );
}
