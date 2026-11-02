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
import FloorPlan, { type FPLeg, type FPStop } from "@/components/plan/FloorPlan";
import "@/app/hub/hub.css";
import "./proof.css";

interface CaseState { case: { case_id: string; site_id: string; target_description: string }; answer?: InvestigationView | null }
interface Conflicts { objects: { records?: CaseRecord[] }[] }

const STOP_TONE: Record<string, NonNullable<FPStop["tone"]>> = { scan: "scan", seen: "seen", noscan: "bad", record: "bad", wait: "none", card: "none" };

export default function ProofPage({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = use(params);
  const st = useResource<CaseState>(`/v1/cases/${caseId}/state`);
  const reel = useResource<Reel>(`/v1/cases/${caseId}/journey-reel`);
  const jr = useResource<Journey>(`/v1/cases/${caseId}/journey`);
  const cr = useResource<Conflicts>(`/v1/cases/${caseId}/conflicts`);
  const sites = useResource<Site[]>("/v1/sites");
  const siteId = st.data?.case.site_id ?? sites.data?.[0]?.site_id;
  const waybill = st.data?.case.target_description.split(" ").at(-1) ?? "";
  const inside = st.data?.answer?.objects.find((o) => o.inside)?.inside ?? null;
  const [on, setOn] = useState(0);
  const onStep = useCallback((i: number) => setOn(i), []);

  const chapters = reel.data?.chapters ?? [];
  const stops: FPStop[] = chapters.flatMap((c, i) => c.xy ? [{ xy: c.xy, n: i + 1, tone: STOP_TONE[c.tone] ?? "none",
    on: i === on, label: c.title }] : []);
  const seek = (n: FPStop["n"]) => window.dispatchEvent(new CustomEvent(SEEK_JOURNEY, { detail: Number(n) - 1 }));
  // the route between the stops: solid where both ends were on camera, dashed across a stretch no camera saw
  const legs: FPLeg[] = stops.slice(1).map((st, i) => {
    const a = chapters[Number(stops[i].n) - 1], b = chapters[Number(st.n) - 1];
    const between = chapters.slice(Number(stops[i].n), Number(st.n) - 1);
    return { from: stops[i].xy, to: st.xy, seen: !!a?.camera && !!b?.camera && b.tone !== "wait" && !between.some((c) => c.tone === "wait") };
  });
  const zone = (inside?.place ?? "").match(/Z\d+/)?.[0];

  // how we know: the tunnel's own record (its screen and photo) for this parcel
  const scans = jr.data?.objects[0]?.scans ?? [];
  const tunnel = scans.length ? buildCheckpoints({ scans, records: cr.data?.objects[0]?.records ?? [], barcode: waybill || null })
    .find((c) => c.id === "tunnel") : undefined;


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
                <FloorPlan label="Floor plan: each step of the journey, numbered" stops={stops} legs={legs} highlight={zone} labels="major" onStop={seek} />
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
            <Identity siteId={siteId} waybill={waybill} photo={!tunnel?.screen} />
          </div>
        </section>

      </div>
    </div>
  );
}
