"use client";
/**
 * Live alerts on the Hub (six checkpoints, addendum 4 #2): "a carton left without a scan". A camera watching a
 * container point saw a carton leave its work area, and the parcels last scanned into a container there have no scan
 * since: the alert names who it could be (their last scan), never that it is one of them. Raised from the footage at
 * that moment, before anyone complains. From GET /v1/sites/{site}/alerts (LiveAlert records).
 */
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, signedUrl, useResource } from "@/lib/api";
import { hms } from "@/lib/words";
import "./livealerts.css";

interface Alert {
  alert_id: string; scan_point_id: string; camera_id: string; media_id: string; at_utc: string; frame_index: number;
  box_px: number[] | null; candidates: { waybill: string; container: string | null; scanned_in: string }[];
}
interface CaseRow { case: { case_id: string; target_description: string } }

const cam = (c: string) => c.replace(/^cam_/, "").replaceAll("_", " ");
const PLACE: Record<string, string> = { "SP-CAGE-W": "the west cage bays", "SP-CAGE-E": "the east cage bays" };

function Shot({ a }: { a: Alert }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!a.box_px) return;
    const [x1, y1, x2, y2] = a.box_px;
    const w = Math.max(x2 - x1, y2 - y1) * 4 + 80, cx = (x1 + x2) / 2, cy = (y1 + y2) / 2;
    const box = [cx - w * 0.66, cy - w / 2, cx + w * 0.66, cy + w / 2].map((v) => Math.max(0, Math.round(v))).join(",");
    let live = true;
    api<{ crop_url: string }>(`/v1/media/${a.media_id}/frames/${a.frame_index}/crop?box=${box}`)
      .then((r) => live && setUrl(signedUrl(r.crop_url))).catch(() => {});
    return () => { live = false; };
  }, [a]);
  // eslint-disable-next-line @next/next/no-img-element -- a signed crop of the original frame
  return url ? <img src={url} alt="" /> : <span className="la-wait" aria-hidden />;
}

export function LiveAlerts({ siteId }: { siteId?: string }) {
  const r = useResource<Alert[]>(siteId ? `/v1/sites/${siteId}/alerts` : null);
  const cases = useResource<CaseRow[]>("/v1/cases");
  const alerts = r.data ?? [];
  if (!alerts.length) return null;
  const caseOf = (wb: string) => (cases.data ?? []).find((c) => c.case.target_description.endsWith(wb))?.case.case_id;
  return (
    <section className="la" aria-label="Live alerts">
      {alerts.map((a) => (
        <article key={a.alert_id} className="la-row">
          <span className="la-pic"><Shot a={a} /></span>
          <div className="la-body">
            <p className="la-h"><span className="la-dot" aria-hidden />A carton left {PLACE[a.scan_point_id] ?? "a container area"} without a scan</p>
            <p className="la-meta"><time>{hms(a.at_utc)}</time> · {cam(a.camera_id)}</p>
            {a.candidates.map((c) => (
              <p key={c.waybill} className="la-who">Could be <b>{c.waybill}</b>: last scanned into {c.container ?? "a container"} here at {hms(c.scanned_in)}, no scan since.</p>
            ))}
          </div>
          {a.candidates[0] && caseOf(a.candidates[0].waybill) && (
            <Link className="hb-btn hb-btn-primary la-go" href={`/cases/${caseOf(a.candidates[0].waybill)}`}>Open the case</Link>
          )}
        </article>
      ))}
    </section>
  );
}
