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
import { useEffect, useMemo, useState } from "react";
import { api, signedUrl, useResource } from "@/lib/api";
import { hms, momentLabel } from "@/lib/words";
import "./passport.css";

interface Stamp {
  scan_event_id: string; event_kind: string; scan_point_id: string; camera_id: string; media_id: string | null;
  at_utc: string; rule: string; outcome: string; frame_index: number | null; box_px: number[] | null; frames_followed: number;
  followed_s: number; labelled: boolean; note: string;
}
/** a moment the cameras showed with no scan (the page passes it in): its clip, time and words */
export interface AfterStamp { key: string; what: string; media: string; cam: string; iso: string; tag: string }

const WHY: Record<string, string> = { not_found: "No carton outlined at the point", cant_tell: "More than one carton could be it",
  no_footage: "No footage of this moment", not_on_camera: "Scanned, not on camera", failed: "Camera check failed",
  clock_not_fitted: "Camera clock not fitted to the scanners" };
const cam = (c: string) => c.replace(/^cam_/, "").replaceAll("_", " ");

/** the labelled carton, zoomed on its outline (a crop of the original frame) */
function Crop({ s }: { s: Stamp }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!s.media_id || s.frame_index == null || !s.box_px) return;
    const [x1, y1, x2, y2] = s.box_px;
    const w = Math.max(Math.max(x2 - x1, y2 - y1) * 1.7 + 24, 120), cx = (x1 + x2) / 2, cy = (y1 + y2) / 2;
    const box = [cx - w * 0.66, cy - w / 2, cx + w * 0.66, cy + w / 2].map((v) => Math.max(0, Math.round(v))).join(",");
    let live = true;
    api<{ crop_url: string }>(`/v1/media/${s.media_id}/frames/${s.frame_index}/crop?box=${box}`)
      .then((r) => live && setUrl(signedUrl(r.crop_url))).catch(() => {});
    return () => { live = false; };
  }, [s]);
  // eslint-disable-next-line @next/next/no-img-element -- a signed crop of the original frame
  return url ? <img src={url} alt="" /> : <span className="pp-wait" aria-hidden />;
}

/** the camera's whole frame at a moment (a scan record with no number on it, or a moment with no scan) */
function Frame({ media, iso }: { media: string; iso: string }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    api<{ frame_url: string }>(`/v1/media/${media}/frame-at?time=${encodeURIComponent(iso)}`)
      .then((r) => live && setUrl(signedUrl(r.frame_url))).catch(() => {});
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
  if (!stamps.length) return null;
  const tunnel = (s: Stamp) => s.rule === "tunnel_exit" && s.outcome === "outlined";
  const met = stamps.filter((s) => s.labelled || tunnel(s)).length;
  const why = (s: Stamp) => (s.outcome === "cant_tell" && s.note.endsWith(" here") ? s.note : WHY[s.outcome] ?? s.outcome);
  return (
    <div className="pp" aria-label="Parcel passport">
      <p className="pp-head"><b>Its journey on camera</b><span>{met} of {stamps.length} scans met on camera{after.length ? `, then ${after.length} moments with no scan` : ""}</span></p>
      <ol className="pp-row">
        {stamps.map((s) => (
          <li key={s.scan_event_id} className="pp-stamp" data-outcome={s.labelled || tunnel(s) ? "outlined" : "record"}>
            <span className="pp-pic">{s.labelled ? <Crop s={s} /> : tunnel(s) ? <TunnelPhoto waybill={waybill} />
              : s.media_id ? <Frame media={s.media_id} iso={s.at_utc} /> : <span className="pp-none">{why(s)}</span>}</span>
            <span className="pp-what">{momentLabel(s.event_kind, s.scan_point_id)}</span>
            <span className="pp-meta"><time>{hms(s.at_utc)}</time>{s.camera_id && <> · {cam(s.camera_id)}</>}</span>
            {s.labelled ? <span className="pp-tag">{waybill} · scanned here</span>
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
      <p className="pp-note">The barcode says which parcel; SAM 3.1 outlines the carton at the scan instant on the camera that sees that scanner. A number goes on an outline only when no other carton could be the one scanned.</p>
    </div>
  );
}
