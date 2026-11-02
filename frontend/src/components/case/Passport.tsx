"use client";
/**
 * The parcel passport (six checkpoints, addendum 4): one stamp per scan of this parcel, in time order. Where a camera
 * met the scan (the scan-to-camera handshake: the barcode says which parcel, the scan point and the clock fit say where
 * and when on the picture, SAM outlines the carton there), the stamp is that carton, zoomed on its outline, with its
 * tracking number. The number goes on an outline only when the handshake is labelled (its rule rules out a neighbour;
 * checked against the render truth); otherwise the stamp shows the camera's frame at the scan's moment as the scan
 * record, with no number on any carton and the reason in plain words. At the scan tunnel the stamp is the tunnel's own
 * photo, taken by the reader at the read. A checkpoint camera is preferred. After the scans, the page can add what the
 * cameras showed with no scan at all (carried into the store, the cage leaving without it): `after`.
 * From GET /v1/parcels/{waybill}/passport (ScanHandshake records); nothing here is the evaluator's truth.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { api, previewUrl, signedUrl, useResource } from "@/lib/api";
import { hms, momentLabel } from "@/lib/words";
import { inCrop, useFocusCrop } from "@/lib/focus";
import "./passport.css";

interface Stamp {
  scan_event_id: string; event_kind: string; scan_point_id: string; camera_id: string; media_id: string | null;
  at_utc: string; rule: string; outcome: string; frame_index: number | null; box_px: number[] | null; frames_followed: number;
  followed_s: number; labelled: boolean; note: string; track_id: string | null;
}
/** a moment the cameras showed with no scan (the page passes it in): its clip, time and words */
export interface AfterStamp { key: string; what: string; media: string; cam: string; iso: string; tag: string }

const WHY: Record<string, string> = { not_found: "No carton outlined at the point", cant_tell: "More than one carton could be it",
  no_footage: "No footage of this moment", not_on_camera: "Scanned, not on camera", failed: "Camera check failed",
  clock_not_fitted: "Camera clock not fitted to the scanners" };
const cam = (c: string) => c.replace(/^cam_/, "").replaceAll("_", " ");

/** the labelled carton, zoomed on SAM's outline (a crop of the original frame, the outline drawn on it) */
function Crop({ s, label }: { s: Stamp; label: string }) {
  const got = useFocusCrop(s.media_id, s.frame_index, s.box_px);
  if (!got || !s.box_px) return <span className="pp-wait" aria-hidden />;
  const b = inCrop(s.box_px, got.rect);
  return (
    <>
      {/* eslint-disable-next-line @next/next/no-img-element -- a signed crop of the original frame around SAM's box */}
      <img src={got.url} alt="" />
      <svg className="pp-mark" viewBox={`0 0 ${b.vw} ${b.vh}`} preserveAspectRatio="xMidYMid slice" aria-hidden="true">
        <rect x={b.x - 3} y={b.y - 3} width={b.w + 6} height={b.h + 6} rx="3" />
      </svg>
      <span className="pp-num">{label}</span>
    </>
  );
}

interface Boxes { boxes: number[][] }

/** a stamp's clip, played with SAM's box following the carton frame by frame through the follow window; when it
 *  ends it hands over to the next met stamp (`onDone`). Reduced motion: rests on the scan's frame. */
function Follow({ s, label, onDone }: { s: Stamp; label: string; onDone: () => void }) {
  const play = useResource<{ url: string; pts_ms: number[] }>(s.media_id ? `/v1/media/${s.media_id}/playback` : null);
  const track = useResource<Boxes>(s.media_id && s.track_id ? `/v1/media/${s.media_id}/tracks/${s.track_id}/boxes` : null);
  const video = useRef<HTMLVideoElement>(null);
  const rect = useRef<SVGRectElement>(null);
  // the follow up to the scan instant only: after it SAM's propagation can latch onto what is left at the point (the
  // empty tray once the carton has gone down the chute: seen in the truth check), so nothing past it is shown
  const f0 = s.frame_index ?? 0;
  const boxes = (track.data?.boxes ?? []).filter((b) => b[0] >= f0 - 25 && b[0] <= f0 + 2);
  const reduced = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const span = boxes.length > 1 ? (boxes[boxes.length - 1][1] - boxes[0][1]) / 1000 : 0;
  useEffect(() => {
    const v = video.current;
    if (!v || !boxes.length) return;
    const from = Math.max(0, boxes[0][1] / 1000 - 0.4), to = boxes[boxes.length - 1][1] / 1000 + 0.6;
    const start = () => { v.currentTime = reduced ? (s.frame_index != null ? (play.data?.pts_ms[s.frame_index] ?? 0) / 1000 : from) : from; if (!reduced) v.play().catch(() => {}); };
    if (v.readyState >= 1) start(); else v.addEventListener("loadedmetadata", start, { once: true });
    let id = 0;
    const draw = () => {
      const ms = v.currentTime * 1000;
      const near = boxes.reduce((a, b) => (Math.abs(b[1] - ms) < Math.abs(a[1] - ms) ? b : a));
      const r = rect.current;
      if (r) {
        const on = Math.abs(near[1] - ms) <= 120;
        r.style.opacity = on ? "1" : "0";
        r.setAttribute("x", String(near[2] - 6)); r.setAttribute("y", String(near[3] - 6));
        r.setAttribute("width", String(near[4] - near[2] + 12)); r.setAttribute("height", String(near[5] - near[3] + 12));
      }
      if (!reduced && v.currentTime >= to) { v.pause(); onDone(); return; }
      id = requestAnimationFrame(draw);
    };
    id = requestAnimationFrame(draw);
    return () => { cancelAnimationFrame(id); v.removeEventListener("loadedmetadata", start); };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- restarts per stamp and clip
  }, [s.scan_event_id, play.data?.url, boxes.length]);
  return (
    <figure className="pp-follow">
      <div className="pp-follow-stage">
        {play.data ? <video ref={video} src={signedUrl(play.data.url)} muted playsInline preload="auto" aria-label={`${cam(s.camera_id)}: SAM 3.1 following ${label}`} />
          : <span className="pp-wait" aria-hidden />}
        <svg viewBox="0 0 1920 1086" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
          <rect ref={rect} rx="4" style={{ opacity: 0 }} />
        </svg>
      </div>
      <figcaption><b>{cam(s.camera_id)}</b> {momentLabel(s.event_kind, s.scan_point_id)} at {hms(s.at_utc)} · Outlined by SAM 3.1{span > 0.5 ? `, followed on camera for ${span.toFixed(1)} s up to the scan` : ""}</figcaption>
    </figure>
  );
}

/** the camera's whole frame at a moment (a scan record with no number on it, or a moment with no scan) */
function Frame({ media, iso }: { media: string; iso: string }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    api<{ frame_url: string }>(`/v1/media/${media}/frame-at?time=${encodeURIComponent(iso)}`)
      .then((r) => live && setUrl(previewUrl(r.frame_url, 560))).catch(() => {});
    return () => { live = false; };
  }, [media, iso]);
  // eslint-disable-next-line @next/next/no-img-element -- a signed original frame
  return url ? <img src={url} alt="" /> : <span className="pp-wait" aria-hidden />;
}

function TunnelPhoto({ waybill }: { waybill: string }) {
  const [ok, setOk] = useState(true);
  // eslint-disable-next-line @next/next/no-img-element -- the scan tunnel's own photo of this parcel at its read
  return ok ? <img src={`/scanner/${waybill}.jpg`} alt="" onError={() => setOk(false)} /> : <span className="pp-none">Scanned in the tunnel</span>;
}

export function Passport({ waybill, after = [] }: { waybill: string; after?: AfterStamp[] }) {
  const r = useResource<{ stamps: Stamp[] }>(waybill ? `/v1/parcels/${waybill}/passport` : null);
  const stamps = useMemo(() => {
    const by = new Map<string, Stamp[]>();
    for (const s of r.data?.stamps ?? []) by.set(s.scan_event_id, [...(by.get(s.scan_event_id) ?? []), s]);
    const rank = (s: Stamp) => (s.labelled ? 0 : s.rule === "tunnel_exit" && s.outcome === "outlined" ? 2 : s.media_id ? 3 : 5)
      + (s.camera_id.startsWith("cam_CHK_") ? 0 : 1);
    return [...by.values()].map((xs) => xs.sort((a, b) => rank(a) - rank(b))[0]).sort((a, b) => Date.parse(a.at_utc) - Date.parse(b.at_utc));
  }, [r.data]);
  const [open, setOpen] = useState<string | null>(null);
  if (!stamps.length) return null;
  const tunnel = (s: Stamp) => s.rule === "tunnel_exit" && s.outcome === "outlined";
  const followable = stamps.filter((s) => s.labelled && s.track_id);
  const playing = followable.find((s) => s.scan_event_id === open);
  const next = () => { const i = followable.findIndex((s) => s.scan_event_id === open); setOpen(followable[i + 1]?.scan_event_id ?? null); };
  const met = stamps.filter((s) => s.labelled || tunnel(s)).length;
  const why = (s: Stamp) => (s.outcome === "cant_tell" && s.note.endsWith(" here") ? s.note : WHY[s.outcome] ?? s.outcome);
  return (
    <div className="pp" aria-label="Parcel passport">
      <p className="pp-head"><b>Its journey on camera</b><span>{met} of {stamps.length} scans met on camera{after.length ? `, then ${after.length} moments with no scan` : ""}</span></p>
      <ol className="pp-row">
        {stamps.map((s) => (
          <li key={s.scan_event_id} className="pp-stamp" data-outcome={s.labelled || tunnel(s) ? "outlined" : "record"}
            data-open={open === s.scan_event_id || undefined}>
            <span className="pp-pic">{s.labelled ? (
              <button type="button" className="pp-play" onClick={() => setOpen(open === s.scan_event_id ? null : s.scan_event_id)}
                aria-label={`Play ${cam(s.camera_id)} with SAM's outline following ${waybill}`} aria-pressed={open === s.scan_event_id}>
                <Crop s={s} label={waybill} />
              </button>) : tunnel(s) ? <TunnelPhoto waybill={waybill} />
              : s.media_id ? <Frame media={s.media_id} iso={s.at_utc} /> : <span className="pp-none">{why(s)}</span>}</span>
            <span className="pp-what">{momentLabel(s.event_kind, s.scan_point_id)}</span>
            <span className="pp-meta"><time>{hms(s.at_utc)}</time>{s.camera_id && <> · {cam(s.camera_id)}</>}</span>
            {s.labelled ? <span className="pp-tag">Outlined by SAM 3.1 · scanned here</span>
              : tunnel(s) ? <span className="pp-tag">{waybill} · the tunnel&apos;s own photo</span>
              : s.media_id ? <span className="pp-tag pp-tag-rec" title={why(s)}>{s.outcome === "cant_tell" && s.note.endsWith(" here") ? `Scan record · ${s.note.charAt(0).toLowerCase()}${s.note.slice(1)}` : "Scan record"}</span> : null}
          </li>
        ))}
        {after.map((a) => (
          <li key={a.key} className="pp-stamp" data-outcome="bad">
            <span className="pp-pic"><Frame media={a.media} iso={a.iso} /></span>
            <span className="pp-what">{a.what}</span>
            <span className="pp-meta"><time>{hms(a.iso)}</time> · {cam(a.cam)}</span>
            <span className="pp-tag pp-tag-bad">{a.tag}</span>
          </li>
        ))}
      </ol>
      {playing && <Follow key={playing.scan_event_id} s={playing} label={waybill} onDone={() => window.setTimeout(next, 900)} />}
      <p className="pp-note">The barcode says which parcel; SAM 3.1 outlines the carton at the scan instant on the camera that sees that scanner. A number goes on an outline only when no other carton could be the one scanned.</p>
    </div>
  );
}
