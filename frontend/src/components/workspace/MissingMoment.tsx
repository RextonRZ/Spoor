"use client";
/**
 * The missing moment (QUEUE H10): where the chain of evidence stops, and the frames where the parcel should have
 * appeared next, with an empty dashed box at the predicted place and time. "Not seen" is shown only when the backend
 * returns a typed negative observation (the clip was analysed); otherwise the row says what is missing.
 */
import { useEffect, useState } from "react";
import { api, signedUrl } from "@/lib/api";
import { cam, clock, lastConfirmedWords, RESULT_WORDS, ROLE_WORDS, type ExpectedNext, type FrameRef } from "@/lib/journey";
import { toMs } from "@/lib/time";
import { Loading, FadeImg } from "@/components/ui";
import { useWorkspace } from "./context";
import RecordsVsVideo from "@/components/RecordsVsVideo";

const TONE: Record<ExpectedNext["result"], string> = {
  seen: "sp-chip-safe", not_seen: "sp-chip-alert", unresolved_candidates: "sp-chip-warn", not_analysed: "", no_footage: "",
};

export default function MissingMoment() {
  const { missing, journey, select, caseId, range } = useWorkspace();
  if (missing.loading && !missing.data) return <Loading label="Working out the missing moment" lines={4} />;
  const o = missing.data?.objects[0];
  const j = journey.data?.objects[0];
  if (!o || !o.last_confirmed || !j) {
    return <p className="sp-muted">Nothing is confirmed yet, so there is no break point to show.</p>;
  }
  const rows = o.expected_next.filter((r) => r.result !== "no_footage");
  const dark = o.expected_next.filter((r) => r.result === "no_footage");
  return (
    <div className="mm sp-stack" data-testid="missing-moment">
      <div>
        <p className="sp-micro">Where the evidence stops</p>
        <p className="mm-last">{lastConfirmedWords(j)}</p>
        {/* a scan's context frames are the "watching" rows below (with the dashed box); only a sighting shows here */}
        {(o.last_confirmed.frames ?? []).filter((f) => f.role === "last_sighting").map((f) => (
          <Shot key={`${f.camera_id}${f.frame_index}`} frame={f}
            caption={`${cam(f.camera_id)} · ${f.role === "context_at_scan_time" ? "frame at the scan time, parcel not yet identified in it" : "last sighting"}`}
            onOpen={() => select({ kind: "camera", cameraId: f.camera_id, time: toMs(o.last_confirmed!.t) })} />
        ))}
      </div>
      <div>
        <p className="sp-micro">Where it should have appeared next</p>
        <ul className="sp-list mm-rows">
          {rows.map((r) => <Row key={r.camera_id} r={r} onOpen={() => select({ kind: "camera", cameraId: r.camera_id, time: toMs(r.predicted_t) })} />)}
        </ul>
        {dark.length > 0 && (
          <ul className="sp-list mm-dark" aria-label="Cameras predicted next without footage in this case">
            {dark.map((r) => (
              <li key={r.camera_id}>
                <span className="sp-strong sp-num">{cam(r.camera_id)}</span> · {ROLE_WORDS[r.role]} · expected {clock(r.window.start, true).replace(" MYT", "")}–{clock(r.window.end, true)}
                <span className="sp-caption"> · {r.how} · no footage in this case, so it cannot show where it went</span>
              </li>
            ))}
          </ul>
        )}
        <p className="sp-caption">Predicted from the site plan (belt speed, walking speed, clock tolerance). A prediction is not an observation.</p>
      </div>
      <RecordsVsVideo caseId={caseId} range={range ?? undefined} />
    </div>
  );
}

function Row({ r, onOpen }: { r: ExpectedNext; onOpen: () => void }) {
  return (
    <li className="mm-row" data-result={r.result}>
      <div className="sp-row sp-wrap" style={{ gap: 8, justifyContent: "space-between" }}>
        <span className="sp-strong sp-num" style={{ fontWeight: 620 }}>{cam(r.camera_id)}</span>
        <span className={`sp-chip ${TONE[r.result]}`}>{RESULT_WORDS[r.result]}</span>
      </div>
      <p className="sp-caption" style={{ margin: 0 }}>{ROLE_WORDS[r.role]} · expected {clock(r.predicted_t, true)} · {r.how}</p>
      {r.frame && <Shot frame={r.frame} row={r} caption={`frame ${r.frame.frame_index} at the predicted time`} onOpen={onOpen} />}
      {r.frame && r.expected_region_px && <CloseUp frame={r.frame} row={r} />}
      {r.result === "not_seen" && r.negative_observation && (
        <p className="mm-neg">Not seen: frames {r.negative_observation.frame_indices[0]}–{r.negative_observation.frame_indices.at(-1)} analysed, the parcel was not confirmed. Negative evidence.</p>
      )}
      {r.needs && <p className="sp-caption" style={{ margin: 0 }}>Needs {r.needs}.</p>}
    </li>
  );
}

function Shot({ frame, row, caption, onOpen }: { frame: FrameRef; row?: ExpectedNext; caption: string; onOpen: () => void }) {
  const reg = row?.expected_region_px;
  const b = row?.region_basis_wh_px;
  return (
    <button className="mm-shot" onClick={onOpen} aria-label={`${caption}. Open in the source panel.`}>
      <FadeImg src={signedUrl(frame.frame_url)} alt="" />
      {reg && b && <span className="mm-box" style={{ left: `${(reg[0] / b[0]) * 100}%`, top: `${(reg[1] / b[1]) * 100}%`,
        width: `${((reg[2] - reg[0]) / b[0]) * 100}%`, height: `${((reg[3] - reg[1]) / b[1]) * 100}%` }} />}
      <span className="mm-cap">{caption}</span>
    </button>
  );
}

interface Crop { crop_url: string; crop_rect_px: [number, number, number, number]; box_px: [number, number, number, number] }

/** The expected place, close up: original pixels around the dashed box (scaled in the viewer, labelled). */
function CloseUp({ frame, row }: { frame: FrameRef; row: ExpectedNext }) {
  const [crop, setCrop] = useState<Crop | null>(null);
  const [figW, setFigW] = useState<number | null>(null);
  const reg = row.expected_region_px!;
  const b = row.region_basis_wh_px;
  useEffect(() => {
    let live = true;
    const q = `box=${reg.join(",")}${b ? `&basis=${b.join(",")}` : ""}`;
    api<Crop>(`/v1/media/${frame.media_id}/frames/${frame.frame_index}/crop?${q}`).then((c) => live && setCrop(c)).catch(() => {});
    return () => { live = false; };
  }, [frame.media_id, frame.frame_index, reg, b]);
  if (!crop) return null;
  const [cx1, cy1, cx2, cy2] = crop.crop_rect_px;
  const [bx1, by1, bx2, by2] = crop.box_px;
  const w = cx2 - cx1;
  const h = cy2 - cy1;
  return (
    <figure className="mm-close" ref={(el) => { if (el && el.clientWidth !== figW) setFigW(el.clientWidth); }}>
      <FadeImg src={signedUrl(crop.crop_url)} alt={`Close-up where ${cam(row.camera_id)} should show the parcel`} />
      <span className="mm-box" style={{ left: `${((bx1 - cx1) / w) * 100}%`, top: `${((by1 - cy1) / h) * 100}%`,
        width: `${((bx2 - bx1) / w) * 100}%`, height: `${((by2 - by1) / h) * 100}%` }} />
      <figcaption className="mm-cap">close-up · original pixels{figW ? `, shown ${(figW / w).toFixed(1)}× (browser scaling, no AI upscale)` : ""}</figcaption>
    </figure>
  );
}
