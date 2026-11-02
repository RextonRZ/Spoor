"use client";
/**
 * Answer (step 1), ops-console style. The answer first: a verdict (status, one sentence, why) with a "how sure" meter
 * and its reasons; then the six scan checkpoints (what the hub's scanners recorded, and where it stopped); where it
 * could be (the places it could have reached, and whether any camera watches each); and what happened in order. On the
 * right, docked: the camera view of the place it was last scanned, which cameras to check next, and the two actions.
 * Everything comes from the case's read models (journey, missing moment, possible places, conflicts, floor search);
 * without model keys it says what is really known. The same words as the Hub and the landing page (lib/answer).
 */
import { JourneyReel } from "@/components/case/JourneyReel";
import Link from "next/link";
import { use } from "react";
import { useResource } from "@/lib/api";
import type { Journey, MissingMoment, Possible } from "@/lib/journey";
import { caseAnswer, type InvestigationView } from "@/lib/answer";
import { conflictWords, type Conflict } from "@/lib/conflict";
import { buildCheckpoints, CHECKPOINT_LINE, type CaseRecord } from "@/lib/checkpoints";
import { hms, momentLabel, placeOf, shortPlace } from "@/lib/words";
import type { Site } from "@/lib/types";
import { CaseSteps } from "@/components/flow/CaseSteps";
import { CheckpointStrip, ScannerScreen } from "@/components/checkpoints/Checkpoints";
import { NextCams, View } from "@/components/hub/parts";
import { Identity } from "@/components/case/Identity";
import { CaseStory } from "@/components/case/CaseStory";
import { CustomerBox } from "@/components/case/CustomerBox";
import { ZONE_NAMES } from "@/components/plan/HubPlan";
import "./answer.css";

interface CaseState { case: { case_id: string; target_description: string; complaint?: string | null; created_at: string }; answer?: InvestigationView | null }
interface Conflicts { objects: { conflicts: Conflict[]; records?: CaseRecord[] }[] }
interface SearchView { found: { name: string; by: string; at: string } | null }

export default function AnswerPage({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = use(params);
  const sites = useResource<Site[]>("/v1/sites");
  const st = useResource<CaseState>(`/v1/cases/${caseId}/state`);
  const jr = useResource<Journey>(`/v1/cases/${caseId}/journey`);
  const mr = useResource<MissingMoment>(`/v1/cases/${caseId}/missing-moment`);
  const pr = useResource<Possible>(`/v1/cases/${caseId}/possible-locations`);
  const cr = useResource<Conflicts>(`/v1/cases/${caseId}/conflicts`);
  const sr = useResource<SearchView>(`/v1/cases/${caseId}/search-tasks`);
  const j = jr.data?.objects[0];
  const mm = mr.data?.objects[0];
  const scans = j?.scans ?? [];
  const last = scans.at(-1);
  const places = (pr.data?.objects[0]?.places ?? []).filter((p) => p.possible_share > 0);
  const conflicts = cr.data?.objects[0]?.conflicts ?? [];
  const found = sr.data?.found ?? null;
  const next = mm?.expected_next ?? [];
  const waybill = st.data?.case.target_description.split(" ").at(-1) ?? "";
  const ready = !!(j && mm && pr.data);
  const siteId = sites.data?.[0]?.site_id;

  const view = st.data?.answer;
  // the investigation's verified answer leads when there is one (a floor find still wins); otherwise the read models
  const inside = !found ? view?.objects.find((o) => o.inside)?.inside : null;
  const lastScan = !found && !inside ? view?.objects.find((o) => o.last_scan)?.last_scan ?? null : null;
  const { pill, head, why, level, reasons } = caseAnswer({ ready, last, next, places, conflicts, found, zoneNames: ZONE_NAMES, lastScan });
  // one source of truth: once the run verified where it went, the checkpoints read from it too (the store's missing
  // scan-in, and a truck record made while the cameras show it still inside)
  const records = cr.data?.objects[0]?.records ?? [];
  const truckRec = records.find((r) => r.event_kind === "container_loaded" || r.event_kind === "departed_facility");
  const truck = truckRec ? { t: truckRec.t, door: truckRec.station_id?.match(/D\d{2}/)?.[0] ?? null } : null;
  const insideAtTruck = !!(inside && truck && Date.parse(truck.t) > Date.parse(inside.iso.carried_in_at) && Date.parse(truck.t) < Date.parse(inside.iso.until));
  const cps = j ? buildCheckpoints({ scans, records, barcode: waybill || null, truckSeen: inside ? !insideAtTruck : undefined,
    storeSeenAt: inside ? inside.iso.carried_in_at : undefined }) : null;
  const tunnel = cps?.find((c) => c.id === "tunnel");
  const conflictAt = conflicts[0]?.divergence_t;
  const meter = level === "high" ? 3 : level === "medium" ? 2 : 1;
  const events = [
    ...scans.map((s) => ({ key: s.scan_event_id, t: s.t, label: momentLabel(s.event_kind, s.station_id), tone: "" })),
    ...(conflictAt ? [{ key: "conflict", t: conflictAt, label: `Records disagree: ${conflictWords(conflicts[0]).short}`, tone: "bad" }] : []),
  ].sort((a, b) => a.t.localeCompare(b.t));

  if (inside && view) {
    return (
      <div className="an">
        <CaseSteps caseId={caseId} waybill={waybill} said={st.data?.case.complaint ? "customer says it never arrived" : null} here={0} />
        <div className="an-body" data-answered="">
          <div className="an-main">
            <section className="an-verdict" aria-labelledby="an-h" data-level="medium">
              <div className="an-verdict-top">
                <span className="an-chip" data-tone="ok">Likely location found</span>
                <div className="an-acts">
                  <Link className="hb-btn" href={`/cases/${caseId}/proof`}>Watch the proof</Link>
                  <Link className="hb-btn hb-btn-primary" href={`/cases/${caseId}/search`}>Send someone to look</Link>
                </div>
              </div>
              <h1 id="an-h" className="an-h1">Most likely in the {inside.place}.</h1>
              <p className="an-why">No camera sees inside. This assumes the door is the only way in.</p>
              <CaseStory caseId={caseId} inside={inside} view={view} journey={j} truck={truck} strip={false} />
            </section>
            {st.data?.case.complaint && <CustomerBox caseId={caseId} complaint={st.data.case.complaint} opened={st.data.case.created_at} lastScan={last?.t} />}

            <section className="an-card" aria-labelledby="an-scans">
              <h2 id="an-scans" className="an-h2">The parcel&apos;s journey</h2>
              <JourneyReel caseId={caseId} />
              {tunnel?.screen && (
                <details className="an-more">
                  <summary>Scan tunnel screen for this parcel</summary>
                  <div className="an-dws"><ScannerScreen s={tunnel.screen} at={tunnel.t} /></div>
                </details>
              )}
            </section>

            <details className="an-card an-fold">
              <summary className="an-h2">How we know it&apos;s this parcel</summary>
              <Identity siteId={siteId} waybill={waybill} />
            </details>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="an">
      <CaseSteps caseId={caseId} waybill={waybill} said={st.data?.case.complaint ? "customer says it never arrived" : null} here={0} />
      <div className="an-body">
        <div className="an-main">
          {(
            <section className="an-verdict" aria-labelledby="an-h" data-level={level}>
              <span className="an-chip" data-tone={pill[1]}>{pill[0]}</span>
              {ready ? <h1 id="an-h" className="an-h1">{head}</h1> : <div className="an-skel an-skel-h" aria-busy="true" />}
              {why && <p className="an-why">{why}</p>}
              {ready && reasons.length > 0 && (
                <div className="an-sure">
                  <p className="an-sure-h">
                    How sure
                    <span className="an-meter" role="img" aria-label={`${level} confidence`}>
                      {[1, 2, 3].map((i) => <i key={i} data-on={i <= meter ? "" : undefined} data-level={level} />)}
                    </span>
                    <b data-level={level}>{level}</b>
                  </p>
                  <ul>
                    {reasons.slice(0, 3).map((r) => <li key={r.text} data-tone={r.tone}>{r.text}</li>)}
                  </ul>
                </div>
              )}
            </section>
          )}
          {st.data?.case.complaint && <CustomerBox caseId={caseId} complaint={st.data.case.complaint} opened={st.data.case.created_at} lastScan={last?.t} />}

          <section className="an-card" aria-labelledby="an-scans">
            <h2 id="an-scans" className="an-h2">Where it was scanned</h2>
            {cps ? <CheckpointStrip cps={cps} compact gaps where /> : <div className="an-skel an-skel-row" aria-busy="true" />}
            <p className="an-line">{CHECKPOINT_LINE}</p>
            {tunnel?.screen && (
              <details className="an-more">
                <summary>Scan tunnel screen for this parcel</summary>
                <div className="an-dws"><ScannerScreen s={tunnel.screen} at={tunnel.t} /></div>
              </details>
            )}
          </section>

          <section className="an-card" aria-labelledby="an-id">
            <h2 id="an-id" className="an-h2">How we know it&apos;s this parcel</h2>
            <Identity siteId={siteId} waybill={waybill} />
          </section>

          {places.length > 0 && (
            <section className="an-card" aria-labelledby="an-where">
              <h2 id="an-where" className="an-h2">Where it could be</h2>
              <ul className="an-places">
                {places.slice(0, 5).map((p, i) => (
                  <li key={p.area_id}>
                    <span className="an-place-n" aria-hidden="true">{i + 1}</span>
                    <span className="an-place-t">{shortPlace(p, ZONE_NAMES).replace(/^\w/, (c) => c.toUpperCase())}{i === 0 && <em>most likely</em>}</span>
                    <span className="an-place-c" data-seen={p.covered_by.length ? "" : undefined}>
                      {p.covered_by.length ? `Watched by ${p.covered_by.slice(0, 2).map((c) => c.replace(/^cam_/i, "").replace("_", " ")).join(", ")}` : "No camera watches this"}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {events.length > 0 && (
            <section className="an-card" aria-labelledby="an-order">
              <h2 id="an-order" className="an-h2">What happened, in order</h2>
              <ol className="an-tl">
                {events.map((m) => (
                  <li key={m.key} data-tone={m.tone || undefined}><time>{hms(m.t)}</time><span>{m.label}</span></li>
                ))}
                {found ? (
                  <li data-tone="ok"><time>{hms(found.at)}</time><span>Found by floor staff</span></li>
                ) : last && (
                  <li data-tone="unknown"><time>after {hms(last.t)}</time><span>Not seen since</span></li>
                )}
              </ol>
            </section>
          )}
        </div>

        <aside className="an-side" aria-label="Where it stopped">
          {siteId && last && (
            <View siteId={siteId} point={last.station_id ?? last.device_id} at={last.t} tone={level === "high" ? "ok" : "bad"} place={placeOf(last.event_kind, last.station_id).replace(/^the /, "")} />
          )}
          <div className="an-acts">
            <Link className="hb-btn hb-btn-primary" href={`/cases/${caseId}/proof`}>Watch the proof</Link>
            <Link className="hb-btn" href={`/cases/${caseId}/search`}>Send someone to look</Link>
          </div>
          {mm && next.length > 0 && <NextCams caseId={caseId} />}
        </aside>
      </div>
    </div>
  );
}
