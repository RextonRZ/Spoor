"use client";
/**
 * Follow-cam close-up (QUEUE H1): while the playhead is inside a seen segment, the ORIGINAL frame cut around the
 * parcel (backend I1 crop: native pixels, its SHA-256), enlarged by the browser and labelled with the factor, corner
 * brackets on the box, and why we know it is this parcel (the scans that name the object the track is linked to).
 * Outside a seen segment it says so; it never invents a sighting.
 */
import { FadeImg } from "@/components/ui";
import { useEffect, useMemo, useState } from "react";
import { api, signedUrl } from "@/lib/api";
import { cam, clock, type ObservedSegment } from "@/lib/journey";
import { describeScan } from "@/lib/scans";
import { useWorkspace } from "./context";

interface TrackCrop {
  crop_url: string;
  crop_rect_px: [number, number, number, number];
  box_px: [number, number, number, number];
  media_id: string;
  media_sha256: string;
  crop_sha256: string;
  frame_index: number;
  camera_id: string;
  t: string | null;
  identity: {
    label?: string;
    identity_keys?: string[];
    association: { status: string; confirmed: boolean; reason: string; by: string } | null;
    scans: { scan_event_id: string; t: string; event_kind: string; raw_code: string | null; raw_description?: string | null;
      station_id: string }[];
    note?: string;
  };
}

const LINK_WORDS: Record<string, string> = {
  human_confirmed: "linked by an investigator",
  verified_same_camera: "same camera track",
  scan_anchored: "identified at a read point",
};

export default function FollowCam() {
  const { journey, playhead, caseId, caps, select } = useWorkspace();
  const j = journey.data?.objects[0];
  const hit = useMemo(() => {
    if (!j || playhead === null) return null;
    const seg = j.segments.find((s): s is ObservedSegment => s.kind === "observed"
      && Date.parse(s.start) - 150 <= playhead && playhead <= Date.parse(s.end) + 150);
    if (!seg) return null;
    const p = seg.points.reduce((b, x) => Math.abs(Date.parse(x.t) - playhead) < Math.abs(Date.parse(b.t) - playhead) ? x : b);
    return { seg, obs: p };
  }, [j, playhead]);
  const [crop, setCrop] = useState<{ key: string; c: TrackCrop } | null>(null);
  const [figW, setFigW] = useState(0);
  const key = hit ? `${hit.seg.track_id}@${hit.obs.observation_id}` : null;

  useEffect(() => {
    if (!hit || !key || crop?.key === key) return;
    let live = true;
    api<TrackCrop>(`/v1/cases/${caseId}/tracks/${hit.seg.track_id}/crop?t=${encodeURIComponent(hit.obs.t)}`)
      .then((c) => live && setCrop({ key, c })).catch(() => {});
    return () => { live = false; };
  }, [key, hit, caseId, crop?.key]);

  if (!j) return null;
  if (!hit) {
    // in the hero, an idle follow-cam is one quiet line above the camera frame (the frame itself is the context)
    return (
      <p className="fc-idle sp-caption" data-testid="followcam-idle">
        Follow-cam: no confirmed sighting at this moment{caps.data && !caps.data.sam && !j.observed_segments ? " · tracking needs SAM" : ""}
      </p>
    );
  }
  const c = crop?.c;
  if (!c) return <div className="fc-pill">Follow-cam: loading the original frame</div>;
  const [x1, y1, x2, y2] = c.crop_rect_px;
  const [bx1, by1, bx2, by2] = c.box_px;
  const w = x2 - x1;
  const h = y2 - y1;
  const zoom = figW ? figW / w : null;
  const chain = c.identity.scans.map((s) => `${describeScan({ event_kind: s.event_kind, raw_code: s.raw_code, device_id: s.station_id,
    station_id: s.station_id, raw_description: s.raw_description }).title} ${clock(s.t, true)}`);
  const waybill = c.identity.identity_keys?.find((k) => k.startsWith("carrier_waybill:"))?.split(":")[1];
  return (
    <figure className="fc" data-testid="followcam" style={{ maxWidth: 4 * w }}
      ref={(el) => { if (el && el.clientWidth !== figW) setFigW(el.clientWidth); }}>
      <button className="fc-shot" style={{ aspectRatio: `${w} / ${h}` }} aria-label="Open the full original frame in the source panel"
        onClick={() => select({ kind: "observation", observationId: hit.obs.observation_id })}>
          <FadeImg src={signedUrl(c.crop_url)} alt={`Follow-cam: original pixels of ${cam(c.camera_id)} frame ${c.frame_index} around the parcel`} />
        <span className="fc-brackets" style={{ left: `${((bx1 - x1) / w) * 100}%`, top: `${((by1 - y1) / h) * 100}%`,
          width: `${((bx2 - bx1) / w) * 100}%`, height: `${((by2 - by1) / h) * 100}%` }} aria-hidden />
        <span className="fc-tag">{cam(c.camera_id)} · frame {c.frame_index} · {zoom ? `${zoom.toFixed(1)}× browser zoom of original pixels` : "original pixels"}</span>
      </button>
      <figcaption className="fc-cap">
        <span><span className="fc-id sp-num">{waybill ?? c.identity.label ?? "unlinked track"}</span>
          {c.identity.association
            ? ` · ${LINK_WORDS[c.identity.association.status] ?? c.identity.association.status}${chain.length ? `, named by ${chain.join(" → ")}` : ""}`
            : ` · ${c.identity.note}`}</span>
        <span className="fc-hash sp-num">source {c.media_sha256.slice(0, 12)}… · crop {c.crop_sha256.slice(0, 12)}…</span>
      </figcaption>
    </figure>
  );
}
