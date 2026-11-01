"use client";
/**
 * The parcel passport (six checkpoints, addendum 4): one stamp per scan of this parcel, in time order. Where a camera
 * met the scan (the scan-to-camera handshake: the barcode says which parcel, the scan point and the clock fit say where
 * and when on the picture, SAM outlines the carton there), the stamp is that carton's crop, labelled "Scanned here".
 * Where it could not be, the stamp says why in plain words (no camera sees the point, no footage of that moment, two
 * cartons and no way to tell). A checkpoint camera is preferred over a wide one when both outlined it.
 * From GET /v1/parcels/{waybill}/passport (ScanHandshake records); nothing here is the evaluator's truth.
 */
import { useEffect, useMemo, useState } from "react";
import { api, signedUrl, useResource } from "@/lib/api";
import { hms, momentLabel } from "@/lib/words";
import "./passport.css";

interface Stamp {
  scan_event_id: string; event_kind: string; scan_point_id: string; camera_id: string; media_id: string | null;
  at_utc: string; rule: string; outcome: string; frame_index: number | null; box_px: number[] | null; frames_followed: number;
  followed_s: number; note: string;
}

const WHY: Record<string, string> = { not_found: "Not seen at the point", cant_tell: "Two cartons, can't tell",
  no_footage: "No footage of this moment", not_on_camera: "Scanned, not on camera", failed: "Camera check failed" };
const cam = (c: string) => c.replace(/^cam_/, "").replace("_", " ");

function Crop({ s }: { s: Stamp }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!s.media_id || s.frame_index == null || !s.box_px) return;
    const [x1, y1, x2, y2] = s.box_px;
    const w = Math.max(x2 - x1, y2 - y1) * 2.4 + 40, cx = (x1 + x2) / 2, cy = (y1 + y2) / 2;
    const box = [cx - w * 0.66, cy - w / 2, cx + w * 0.66, cy + w / 2].map((v) => Math.max(0, Math.round(v))).join(",");
    let live = true;
    api<{ crop_url: string }>(`/v1/media/${s.media_id}/frames/${s.frame_index}/crop?box=${box}`)
      .then((r) => live && setUrl(signedUrl(r.crop_url))).catch(() => {});
    return () => { live = false; };
  }, [s]);
  // eslint-disable-next-line @next/next/no-img-element -- a signed crop of the original frame
  return url ? <img src={url} alt="" /> : <span className="pp-wait" aria-hidden />;
}

export function Passport({ waybill }: { waybill: string }) {
  const r = useResource<{ stamps: Stamp[] }>(waybill ? `/v1/parcels/${waybill}/passport` : null);
  const stamps = useMemo(() => {
    const by = new Map<string, Stamp[]>();
    for (const s of r.data?.stamps ?? []) by.set(s.scan_event_id, [...(by.get(s.scan_event_id) ?? []), s]);
    const rank = (s: Stamp) => (s.outcome === "outlined" ? 0 : 2) + (s.camera_id.startsWith("cam_CHK_") ? 0 : 1);
    return [...by.values()].map((xs) => xs.sort((a, b) => rank(a) - rank(b))[0]).sort((a, b) => a.at_utc.localeCompare(b.at_utc));
  }, [r.data]);
  if (!stamps.length) return null;
  const met = stamps.filter((s) => s.outcome === "outlined").length;
  return (
    <div className="pp" aria-label="Parcel passport">
      <p className="pp-head"><b>On camera at its scans</b><span>{met} of {stamps.length} scans met on camera</span></p>
      <ol className="pp-row">
        {stamps.map((s) => (
          <li key={s.scan_event_id} className="pp-stamp" data-outcome={s.outcome}>
            <span className="pp-pic">{s.outcome === "outlined" ? <Crop s={s} /> : <span className="pp-none">{WHY[s.outcome] ?? s.outcome}</span>}</span>
            <span className="pp-what">{momentLabel(s.event_kind, s.scan_point_id)}</span>
            <span className="pp-meta"><time>{hms(s.at_utc)}</time>{s.camera_id && <> · {cam(s.camera_id)}</>}</span>
            {s.outcome === "outlined" && <span className="pp-tag">Scanned here{s.followed_s > 0 ? ` · followed ${s.followed_s.toFixed(0)} s` : ""}</span>}
          </li>
        ))}
      </ol>
      <p className="pp-note">The barcode says which parcel; SAM 3.1 outlines the carton at the scan instant on the camera that sees that scanner.</p>
    </div>
  );
}
