"use client";
/**
 * Proof (step 2): "show me, step by step, so I can check it myself" (Rexton 2 Nov: Answer and Proof each get ONE job).
 * The journey reel with its step rail, the plan beside it with each step as a numbered stop (a stop seeks the reel),
 * then how we know it is this parcel (the tunnel's record and photo, size, look-alikes ruled out by their own scans)
 * and how sure (camera clocks, calibrations, where a number is shown, the limits). Runtime data only: the case's reel,
 * read models and records; never the evaluator's truth.
 */
import Link from "next/link";
import { use, useCallback, useState } from "react";
import { useResource } from "@/lib/api";
import type { Journey } from "@/lib/journey";
import type { InvestigationView } from "@/lib/answer";
import { buildCheckpoints, type CaseRecord } from "@/lib/checkpoints";
import type { Site } from "@/lib/types";
import { CaseSteps } from "@/components/flow/CaseSteps";
import { ScannerScreen } from "@/components/checkpoints/Checkpoints";
import { Identity } from "@/components/case/Identity";
import { JourneyReel, SEEK_JOURNEY, type Reel } from "@/components/case/JourneyReel";
import HubPlan, { type Stop } from "@/components/plan/HubPlan";
import "@/app/hub/hub.css";
import "./proof.css";

interface CaseState { case: { case_id: string; site_id: string; target_description: string }; answer?: InvestigationView | null }
interface Conflicts { objects: { records?: CaseRecord[] }[] }
interface CamRow { camera: { camera_id: string }; clock_sync: { anchor_count: number; uncertainty_ms: number; residual_ms_p95: number | null } | null;
  calibration: { holdout_error_median_m: number | null; invalidated: boolean } | null }
interface RunView { steps: { tool: string; status: string; receipt?: { output?: { said?: string | null; answer?: string | null } } | null }[] }

const STOP_TONE: Record<string, Stop["tone"]> = { scan: "scan", seen: "seen", noscan: "bad", record: "bad", wait: "none", card: "none" };
const camKey = (c: string) => `cam_${c}`;

export default function ProofPage({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = use(params);
  const st = useResource<CaseState>(`/v1/cases/${caseId}/state`);
  const reel = useResource<Reel>(`/v1/cases/${caseId}/journey-reel`);
  const jr = useResource<Journey>(`/v1/cases/${caseId}/journey`);
  const cr = useResource<Conflicts>(`/v1/cases/${caseId}/conflicts`);
  const run = useResource<RunView>(`/v1/cases/${caseId}/run`);
  const sites = useResource<Site[]>("/v1/sites");
  const siteId = st.data?.case.site_id ?? sites.data?.[0]?.site_id;
  const cams = useResource<CamRow[]>(siteId ? `/v1/sites/${siteId}/cameras` : null);
  const waybill = st.data?.case.target_description.split(" ").at(-1) ?? "";
  const inside = st.data?.answer?.objects.find((o) => o.inside)?.inside ?? null;
  const [on, setOn] = useState(0);
  const onStep = useCallback((i: number) => setOn(i), []);

  const chapters = reel.data?.chapters ?? [];
  const stops: Stop[] = chapters.flatMap((c, i) => c.xy ? [{ key: String(i), xy: c.xy, n: i + 1, tone: STOP_TONE[c.tone] ?? "none",
    on: i === on, label: c.title }] : []);
  const seek = (key: string) => window.dispatchEvent(new CustomEvent(SEEK_JOURNEY, { detail: Number(key) }));

  // how we know: the tunnel's own record (its screen and photo) for this parcel
  const scans = jr.data?.objects[0]?.scans ?? [];
  const tunnel = scans.length ? buildCheckpoints({ scans, records: cr.data?.objects[0]?.records ?? [], barcode: waybill || null })
    .find((c) => c.id === "tunnel") : undefined;

  // how sure, from the route's own cameras and the run's records
  const routeCams = [...new Set(chapters.map((c) => c.camera).filter((c) => /^(CHK|CAM)_/.test(c)))];
  const rows = (cams.data ?? []).filter((r) => routeCams.some((c) => camKey(c) === r.camera.camera_id));
  const fitted = rows.filter((r) => (r.clock_sync?.anchor_count ?? 0) > 0);
  const worst = Math.max(0, ...rows.filter((r) => !(r.clock_sync?.anchor_count)).map((r) => r.clock_sync?.uncertainty_ms ?? 0));
  const calib = rows.map((r) => r.calibration?.holdout_error_median_m).filter((x): x is number => x != null).sort((a, b) => a - b);
  const scanSteps = chapters.filter((c) => c.tone === "scan");
  const numbered = scanSteps.filter((c) => c.label && c.camera !== "Tunnel reader").length;
  const spark = (run.data?.steps ?? []).map((s) => s.receipt?.output).find((o) => o?.answer);
  const place = inside?.place.replace(/ \(Z\d+\)$/, "") ?? "store";

  return (
    <div className="pf">
      <CaseSteps caseId={caseId} waybill={waybill} page="Proof" here={1} />
      <div className="pf-wrap">
        <section className="pf-sec" aria-labelledby="pf-steps">
          <header className="pf-head">
            <h1 id="pf-steps" className="pf-h1">Step by step</h1>
            <p>Every step on its own camera, in order. Pick a step below the video, or its number on the plan.</p>
          </header>
          <div className="pf-grid">
            <div className="pf-reel"><JourneyReel caseId={caseId} onStep={onStep} /></div>
            <aside className="pf-side" aria-label="Where each step happened">
              <div className="pf-plan">
                <HubPlan label="Floor plan: each step of the journey, numbered" fit="width" legend={false} quiet stops={stops} onStop={seek} />
              </div>
              <p className="pf-plan-note">Numbers follow the steps. Red: where the records fail.</p>
              <Link className="hb-btn hb-btn-primary pf-go" href={`/cases/${caseId}/search`}>{inside ? `Go look: ${inside.place}` : "Start a floor search"}</Link>
            </aside>
          </div>
        </section>

        <section className="pf-sec" aria-labelledby="pf-know">
          <h2 id="pf-know" className="pf-h2">How we know it&apos;s this parcel</h2>
          <div className="pf-know">
            {tunnel?.screen && <div className="pf-dws"><ScannerScreen s={tunnel.screen} at={tunnel.t} /></div>}
            <Identity siteId={siteId} waybill={waybill} />
          </div>
        </section>

        <section className="pf-sec" aria-labelledby="pf-sure">
          <h2 id="pf-sure" className="pf-h2">How sure</h2>
          <ul className="pf-sure">
            {rows.length > 0 && (
              <li><b>Camera clocks.</b> {fitted.length} of {rows.length} cameras on this route checked against the sorter&apos;s own events
                {fitted.length < rows.length ? `; the rest can be off by up to ${Math.round(worst / 1000)} s, so no number goes on a carton there by time alone` : ""}.</li>
            )}
            {calib.length > 0 && <li><b>Positions.</b> Camera calibrations checked on points held back from fitting: median error {Math.round(calib[calib.length >> 1] * 100)} cm.</li>}
            {scanSteps.length > 0 && (
              <li><b>The number on a carton.</b> Shown on {numbered} of {scanSteps.length} scans, only where no other carton could have been the one
                scanned. The other steps show the place at that moment with no number. Outlines are SAM 3.1&apos;s, carton-sized.</li>
            )}
            <li><b>Limits.</b> No camera sees inside the {place}: this assumes its door is the only way in.
              {spark?.answer === "can't see" ? " Muse Spark could not see the carrier's hands in the clip it checked, so empty hands coming out are not claimed." : ""}
              {" "}The footage is synthetic, of a fictional hub.</li>
          </ul>
        </section>
      </div>
    </div>
  );
}
