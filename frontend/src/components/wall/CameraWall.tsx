"use client";
/**
 * Synchronized camera wall (review 007 #1): 2x2 or 3x3 tiles of ORIGINAL clips, played through their working proxies,
 * all on one wall clock. Each clip sits at its recorded start on the timeline (declared, unverified), so the burned-in
 * OSD of every tile shows its own camera clock. Tiles without footage say so; nothing is drawn in their place.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { signedUrl, useResource } from "@/lib/api";
import { wallColumns, wallLocalTime, type Playback } from "@/lib/playback";
import { fmtTime, TZ_LABEL } from "@/lib/time";
import "./wall.css";

export interface WallTile {
  key: string;
  camera: string;
  osd?: string;
  mediaId?: string;
  /** shown instead of footage when there is none */
  note?: string;
  noteTitle?: string;
}

interface Clock {
  playing: boolean;
  t: number;
}

const PAGE = 9;

export default function CameraWall({ tiles, title }: { tiles: WallTile[]; title: string }) {
  const [page, setPage] = useState(0);
  const pages = Math.max(1, Math.ceil(tiles.length / PAGE));
  const shown = tiles.slice(page * PAGE, page * PAGE + PAGE);
  const cols = wallColumns(shown.length);
  const videos = useRef(new Map<string, HTMLVideoElement>());
  const [spans, setSpans] = useState<Record<string, { start: number; duration: number }>>({});
  const clockRef = useRef<Clock>({ playing: false, t: 0 });
  const [clock, setClockState] = useState<Clock>({ playing: false, t: 0 });
  const setClock = useCallback((c: Clock) => {
    clockRef.current = c;
    setClockState(c);
  }, []);
  const wallRef = useRef<HTMLDivElement>(null);

  const starts = Object.values(spans).map((s) => s.start);
  const origin = starts.length ? Math.min(...starts) : null;
  const end = origin === null ? 0 : Math.max(...Object.values(spans).map((s) => (s.start - origin) / 1000 + s.duration));

  const report = useCallback((key: string, start: number, duration: number) => {
    setSpans((s) => (s[key]?.start === start && s[key]?.duration === duration ? s : { ...s, [key]: { start, duration } }));
  }, []);
  const register = useCallback((key: string, el: HTMLVideoElement | null) => {
    if (el) videos.current.set(key, el);
    else videos.current.delete(key);
  }, []);

  // Keep every registered video at the wall time (drift > 0.2 s is corrected; paused = exact seek).
  const sync = useCallback((t: number, playing: boolean) => {
    if (origin === null) return;
    for (const [key, el] of videos.current) {
      const span = spans[key];
      if (!span) continue;
      const local = wallLocalTime(t, (span.start - origin) / 1000, span.duration);
      el.setAttribute("data-out", local === null ? "true" : "false");
      if (local === null) {
        if (!el.paused) el.pause();
        continue;
      }
      if (!playing) {
        if (!el.paused) el.pause();
        if (Math.abs(el.currentTime - local) > 0.01) seekVideo(el, local);
      } else {
        if (Math.abs(el.currentTime - local) > 0.2) seekVideo(el, local);
        if (el.paused) void el.play().catch(() => {});
      }
    }
  }, [origin, spans]);

  useEffect(() => {
    if (!clock.playing) sync(clock.t, false);
  }, [clock, sync]);

  useEffect(() => {
    if (!clock.playing) return;
    let raf = 0;
    let last = performance.now();
    let lastSync = 0;
    const tick = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      let t = clockRef.current.t + dt;
      if (t > end) t = 0; // loop: the wall is the demo's opening hook
      clockRef.current = { playing: true, t };
      if (now - lastSync > 250) {
        lastSync = now;
        setClockState(clockRef.current);
        sync(t, true);
      }
      raf = requestAnimationFrame(tick);
    };
    sync(clockRef.current.t, true);
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [clock.playing, sync, end]);

  const ready = Object.keys(spans).length;
  const toggle = () => setClock({ ...clockRef.current, playing: !clockRef.current.playing && ready > 0 });
  const seek = (t: number) => setClock({ playing: clockRef.current.playing, t });
  const turn = (p: number) => {
    setClock({ ...clockRef.current, playing: false });
    setPage(p);
  };

  return (
    <div className="sp-wall" ref={wallRef} data-cols={cols} data-ready={ready > 0}
      onKeyDown={(e) => { if (e.key === " " && (e.target as HTMLElement).tagName !== "BUTTON") { e.preventDefault(); toggle(); } }}>
      <div className="sp-wall-grid" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }} aria-label={title}>
        {shown.map((tile) => (
          <Tile key={tile.key} tile={tile} report={report} register={register} />
        ))}
      </div>
      <div className="sp-wall-bar" role="group" aria-label="Wall playback">
        <button className="sp-btn sp-btn-primary sp-btn-sm" onClick={toggle} disabled={!ready} data-testid="wall-play"
          aria-label={clock.playing ? "Pause all cameras" : "Play all cameras"}>{clock.playing ? "❚❚ Pause" : "▶ Play"}</button>
        <input type="range" className="sp-wall-scrub" min={0} max={Math.max(end, 0.1)} step={0.1} value={Math.min(clock.t, end)}
          disabled={!ready} aria-label="Wall time" onChange={(e) => seek(Number(e.target.value))} />
        <span className="sp-num sp-wall-time" aria-live="off">
          {origin === null ? "no footage loaded" : `${fmtTime(new Date(origin + clock.t * 1000).toISOString())} ${TZ_LABEL} · +${clock.t.toFixed(1)} s`}
        </span>
        {pages > 1 && (
          <span className="sp-row" style={{ gap: 6 }}>
            <button className="sp-btn sp-btn-sm" onClick={() => turn(Math.max(0, page - 1))} disabled={page === 0}>Previous 9</button>
            <span className="sp-caption">cameras {page * PAGE + 1}–{Math.min(tiles.length, page * PAGE + PAGE)} of {tiles.length}</span>
            <button className="sp-btn sp-btn-sm" onClick={() => turn(Math.min(pages - 1, page + 1))} disabled={page >= pages - 1}>Next 9</button>
          </span>
        )}
        <button className="sp-btn sp-btn-sm" onClick={() => {
          const el = wallRef.current;
          if (!el) return;
          if (document.fullscreenElement) void document.exitFullscreen();
          else void el.requestFullscreen?.().catch(() => {});
        }}>Full screen</button>
      </div>
      <p className="sp-caption" style={{ margin: 0 }}>
        Synchronized on each clip&apos;s recorded start (uploader-declared, clock not verified); every tile&apos;s burned-in OSD shows that
        camera&apos;s own clock. Footage is synthetic (SYNTHETIC mark burned in). Playback uses each original&apos;s H.264 working proxy,
        frame for frame the same clip. Context only: nothing in these tiles has been detected or observed.
      </p>
    </div>
  );
}

function Tile({ tile, register, report }: { tile: WallTile; report: (key: string, start: number, duration: number) => void;
  register: (key: string, el: HTMLVideoElement | null) => void }) {
  const videoRef = useCallback((el: HTMLVideoElement | null) => register(tile.key, el), [register, tile.key]);
  const pb = useResource<Playback>(tile.mediaId ? `/v1/media/${tile.mediaId}/playback` : null);
  const [failed, setFailed] = useState(false);
  const [retried, setRetried] = useState(false);
  const data = pb.data;
  const duration = data && data.pts_ms.length ? (data.pts_ms[data.pts_ms.length - 1] - data.pts_ms[0]) / 1000 : 0;
  const start = data?.start_utc ? Date.parse(data.start_utc) : null;
  useEffect(() => {
    if (start !== null && duration > 0) report(tile.key, start, duration);
  }, [start, duration, report, tile.key]);
  return (
    <figure className="sp-wall-tile" data-state={!tile.mediaId ? "empty" : failed ? "error" : data ? "ready" : "loading"}>
      {tile.mediaId && data && !failed && (
        <video ref={videoRef} src={signedUrl(data.url)} muted playsInline preload="auto"
          aria-label={`${tile.camera} original footage (working proxy)`}
          onError={() => { if (!retried) { setRetried(true); void pb.reload(); } else setFailed(true); }} />
      )}
      {tile.mediaId && !data && !pb.error && <div className="sp-skel" style={{ position: "absolute", inset: 0 }} aria-hidden />}
      {(!tile.mediaId || failed || pb.error) && (
        <div className="sp-wall-empty">
          <span className="sp-strong">{failed || pb.error ? "Footage could not be loaded" : tile.noteTitle ?? "No footage"}</span>
          <span className="sp-caption">{failed || pb.error ? (pb.error?.message ?? "the playback link may have expired") : tile.note}</span>
        </div>
      )}
      <figcaption className="sp-wall-cap">
        <span className="sp-strong">{tile.camera}</span>
        {tile.osd && <span className="sp-muted">{tile.osd}</span>}
        {tile.mediaId && <span className="sp-chip sp-chip-sim">synthetic</span>}
      </figcaption>
      <span className="sp-wall-out" aria-hidden>no footage at this time</span>
    </figure>
  );
}

/** Imperative seek on a registered element (kept outside the component: media elements are not React state). */
function seekVideo(el: HTMLVideoElement, seconds: number) {
  el.currentTime = seconds;
}
