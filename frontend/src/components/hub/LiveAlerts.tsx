"use client";
/**
 * Live alerts on the Hub (six checkpoints, addendum 4 #2): "a carton left without a scan". A camera watching a
 * container point saw a carton leave its work area, and the parcels last scanned into a container there have no scan
 * since: the alert names who it could be (their last scan), never that it is one of them. Raised from the footage at
 * that moment, before anyone complains. From GET /v1/sites/{site}/alerts (LiveAlert records).
 */
import Link from "next/link";
import { useResource } from "@/lib/api";
import { inCrop, pointsIn, useBestView, useContours, useFocusCrop } from "@/lib/focus";
import { hms } from "@/lib/words";
import "./livealerts.css";

interface Alert {
  alert_id: string; scan_point_id: string; camera_id: string; media_id: string; at_utc: string; frame_index: number; track_id: string;
  box_px: number[] | null; candidates: { waybill: string; container: string | null; scanned_in: string }[];
}
interface CaseRow { case: { case_id: string; target_description: string } }

const cam = (c: string) => c.replace(/^cam_/, "").replaceAll("_", " ");
const PLACE: Record<string, string> = { "SP-CAGE-W": "the west cage bays", "SP-CAGE-E": "the east cage bays" };

/** the moment it left, cropped around SAM's outline of the carton (the full frame opens in the case) */
function Shot({ a }: { a: Alert }) {
  // the carton as it is carried out, wholly in the picture (the alert's own frame is where it leaves the view)
  const view = useBestView(a.media_id, a.track_id, a.frame_index);
  const frame = view?.frame ?? a.frame_index, box = view?.box ?? a.box_px;
  const got = useFocusCrop(a.media_id, frame, box);
  const edge = useContours(a.media_id, a.track_id).get(frame);
  if (!got || !box) return <span className="la-wait" aria-hidden />;
  const b = inCrop(box, got.rect);
  return (
    <>
      {/* eslint-disable-next-line @next/next/no-img-element -- a signed crop of the original frame around SAM's box */}
      <img src={got.url} alt="" />
      <svg className="la-mark" viewBox={`0 0 ${b.vw} ${b.vh}`} preserveAspectRatio="xMidYMid slice" aria-hidden="true">
        {edge ? <polygon points={pointsIn(edge, got.rect)} /> : <rect x={b.x - 3} y={b.y - 3} width={b.w + 6} height={b.h + 6} rx="3" />}
      </svg>
    </>
  );
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
