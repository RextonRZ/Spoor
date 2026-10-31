"use client";
/**
 * The camera moment (QUEUE H11): the 2-4 cameras around the break point in one synced grid, on the workspace's single
 * scrubber (the timeline playhead). Backend I5 places each clip by its own clock sync, so a tile shows the same instant
 * on every camera. Boxes: solid green = the subject's confirmed track; thin grey = something else tracked; dashed =
 * where it was expected (red only for a typed "not seen").
 */
import { ExpectedMark } from "./ExpectedMark";
import { useEffect, useState } from "react";
import { signedUrl, useResource } from "@/lib/api";
import { cam, clock, RESULT_WORDS, type ExpectedResult, type FrameRef } from "@/lib/journey";
import { FadeImg, Loading } from "@/components/ui";
import { useWorkspace } from "./context";

interface Grid {
  t: string;
  label: string;
  cameras: { camera_id: string; name: string; frame: FrameRef | null; role: string | null; result: ExpectedResult | null;
    clock: { offset_ms: number; uncertainty_ms: number; method: string } | null;
    boxes: { observation_id: string; box_px: [number, number, number, number]; frame_wh_px: [number, number]; subject: boolean }[];
    expected_region_px: [number, number, number, number] | null; region_basis_wh_px: [number, number] | null }[];
}

export default function CameraGrid() {
  const { caseId, playhead, journey } = useWorkspace();
  const lcT = journey.data?.objects[0]?.last_confirmed?.t;
  const [t, setT] = useState<number | null>(null);
  useEffect(() => { // one request per ~350 ms of scrubbing or replay
    const target = playhead ?? (lcT ? Date.parse(lcT) : null);
    const h = setTimeout(() => setT(target), 350);
    return () => clearTimeout(h);
  }, [playhead, lcT]);
  const grid = useResource<Grid>(t !== null ? `/v1/cases/${caseId}/sync-grid?t=${encodeURIComponent(new Date(Math.round(t / 100) * 100).toISOString())}` : null);
  if (!grid.data) return grid.error ? <p className="sp-muted">The camera moment needs a confirmed point first.</p> : <Loading label="Loading the camera moment" lines={3} />;
  const g = grid.data;
  return (
    <div className="cg sp-stack" data-testid="camera-grid">
      <p className="sp-caption" style={{ margin: 0 }}>The camera moment · {clock(g.t, true)} on every camera · each clip placed by its own clock sync</p>
      <div className="cg-grid" data-n={g.cameras.length}>
        {g.cameras.map((c) => (
          <figure key={c.camera_id} className="cg-tile">
            <div className="cg-shot">
              {c.frame ? <FadeImg src={signedUrl(c.frame.frame_url)} alt={`${cam(c.camera_id)} original frame ${c.frame.frame_index}`} />
                : <span className="cg-none">{c.result === "no_footage" ? "no footage imported for this camera" : "no footage at this instant"}</span>}
              {c.frame && c.boxes.map((b) => (
                <span key={b.observation_id} className={b.subject ? "cg-box cg-subject" : "cg-box"} style={pct(b.box_px, b.frame_wh_px)} />
              ))}
              {c.frame && !c.boxes.some((b) => b.subject) && <ExpectedMark row={c} compact />}
            </div>
            <figcaption className="cg-cap">
              <span className="sp-strong sp-num">{cam(c.camera_id)}</span>
              {c.result && <span className={`sp-chip ${c.result === "not_seen" ? "sp-chip-alert" : ""}`} style={{ height: 20 }}>{RESULT_WORDS[c.result]}</span>}
              <span className="sp-caption" style={{ margin: 0 }}>{c.frame ? `frame ${c.frame.frame_index}` : ""}
                {c.clock ? ` · clock ±${(c.clock.uncertainty_ms / 1000).toFixed(1)} s${/UNVERIFIED/i.test(c.clock.method) ? ", unverified" : ""}` : " · no clock sync"}</span>
            </figcaption>
          </figure>
        ))}
      </div>
      <p className="sp-caption">{g.label.charAt(0).toUpperCase() + g.label.slice(1)}. Scrub the timeline to move every camera together.</p>
    </div>
  );
}

function pct(b: [number, number, number, number], wh: [number, number]) {
  return { left: `${(b[0] / wh[0]) * 100}%`, top: `${(b[1] / wh[1]) * 100}%`,
    width: `${((b[2] - b[0]) / wh[0]) * 100}%`, height: `${((b[3] - b[1]) / wh[1]) * 100}%` };
}
