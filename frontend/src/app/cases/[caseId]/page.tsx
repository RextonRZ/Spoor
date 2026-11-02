"use client";
/**
 * Answer (step 1): where is it, and what do I do now (Rexton 2 Nov: Answer and Proof each get ONE job). Every case the
 * same shape: the verdict (status, one sentence, its limit), one picture (the store door with SAM's outline once the
 * run placed it; otherwise its last scan point), a few facts one line each, the two actions and the customer's note;
 * an unplaced case adds the cameras to check next. The step by step, the plan and the identity checks are the Proof's.
 * Everything comes from the case's read models; without model keys it says what is really known (lib/answer).
 */
import Link from "next/link";
import { use } from "react";
import { useResource } from "@/lib/api";
import type { Journey, MissingMoment, Possible } from "@/lib/journey";
import { caseAnswer, type InvestigationView } from "@/lib/answer";
import { conflictWords, type Conflict } from "@/lib/conflict";
import type { CaseRecord } from "@/lib/checkpoints";
import { hms, momentLabel, placeOf } from "@/lib/words";
import type { Site } from "@/lib/types";
import { CaseSteps } from "@/components/flow/CaseSteps";
import { NextCams, View } from "@/components/hub/parts";
import { CaseStory } from "@/components/case/CaseStory";
import { CustomerBox } from "@/components/case/CustomerBox";
import { ZONE_NAMES } from "@/components/plan/HubPlan";
import "./answer.css";

/** "14:21" on the hub clock */
const hm = (iso: string) => hms(iso).slice(0, 5);

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
  const reel = useResource<{ seconds: number }>(`/v1/cases/${caseId}/journey-reel`);
  const j = jr.data?.objects[0];
  const mm = mr.data?.objects[0];
  const scans = j?.scans ?? [];
  const last = scans.at(-1);
  const places = (pr.data?.objects[0]?.places ?? []).filter((p) => p.possible_share > 0);
  const conflicts = cr.data?.objects[0]?.conflicts ?? [];
  const found = sr.data?.found ?? null;
  const next = mm?.expected_next ?? [];
  const waybill = st.data?.case.target_description.split(" ").at(-1) ?? "";
  const ready = !!(j && mm); // (the places it could have reached take longer: they add a line when they come)
  const siteId = sites.data?.[0]?.site_id;

  const view = st.data?.answer;
  // the investigation's verified answer leads when there is one (a floor find still wins); otherwise the read models
  const inside = !found ? view?.objects.find((o) => o.inside)?.inside : null;
  const lastScan = !found && !inside ? view?.objects.find((o) => o.last_scan)?.last_scan ?? null : null;
  const { pill, head, why, level } = caseAnswer({ ready, last, next, places, conflicts, found, zoneNames: ZONE_NAMES, lastScan });
  // the truck record, and whether the cameras show it still inside the store when it was made
  const records = cr.data?.objects[0]?.records ?? [];
  const truckRec = records.find((r) => r.event_kind === "container_loaded" || r.event_kind === "departed_facility");
  const truck = truckRec ? { t: truckRec.t, door: truckRec.station_id?.match(/D\d{2}/)?.[0] ?? null } : null;
  const insideAtTruck = !!(inside && truck && Date.parse(truck.t) > Date.parse(inside.iso.carried_in_at) && Date.parse(truck.t) < Date.parse(inside.iso.until));

  if (!st.data) {  // the case is still loading: a neutral skeleton (it flashed the unplaced layout, "Checking", first)
    return (
      <div className="an">
        <CaseSteps caseId={caseId} waybill="" here={0} />
        <div className="an-body"><div className="an-main">
          <div className="an-skel an-skel-h" aria-busy="true" />
          <div className="an-one-grid"><div className="an-skel an-skel-pic" aria-busy="true" /><div className="an-skel an-skel-row" aria-busy="true" /></div>
        </div></div>
      </div>
    );
  }

  if (inside && view) {
    // three facts, one line each, in the records' and cameras' own terms (the step-by-step is the Proof's)
    const caged = [...records].reverse().find((r) => r.event_kind === "container_add" && Date.parse(r.t) <= Date.parse(inside.iso.carried_in_at));
    const lastT = caged?.t ?? last?.t;
    const facts: { text: string; bad?: boolean }[] = [
      ...(lastT ? [{ text: `Last scan: ${caged?.container ? `put into cage ${caged.container}` : momentLabel(last!.event_kind, last!.station_id).toLowerCase()} at ${hm(lastT)}.` }] : []),
      { text: `${hm(inside.iso.carried_in_at)}: carried into the ${inside.place.replace(/ \(Z\d+\)$/, "")}, not scanned in.`, bad: true },
      ...(truck && insideAtTruck ? [{ text: `${hm(truck.t)}: the truck record says loaded on ${truck.door ?? "a truck"}. The cameras show it never left.`, bad: true }] : []),
    ];
    return (
      <div className="an">
        <CaseSteps caseId={caseId} waybill={waybill} said={st.data?.case.complaint ? "customer says it never arrived" : null} here={0} />
        <div className="an-body" data-answered="">
          <div className="an-main">
            <section className="an-verdict an-one" aria-labelledby="an-h" data-level="medium">
              <span className="an-chip" data-tone="ok">Likely location found</span>
              <h1 id="an-h" className="an-h1">Most likely in the {inside.place}.</h1>
              <p className="an-why">No camera sees inside. This assumes the door is the only way in.</p>
              <div className="an-one-grid">
                <CaseStory caseId={caseId} inside={inside} view={view} journey={j} truck={truck} strip={false} plan={false} />
                <div className="an-one-side">
                  <ol className="an-facts" aria-label="What the records and cameras show">
                    {facts.map((f) => <li key={f.text} data-bad={f.bad ? "" : undefined}>{f.text}</li>)}
                  </ol>
                  <div className="an-one-acts">
                    <Link className="hb-btn hb-btn-primary" href={`/cases/${caseId}/search`}>Send someone to look</Link>
                    <Link className="hb-btn" href={`/cases/${caseId}/proof`}>Watch the proof{reel.data ? ` (${Math.round(reel.data.seconds)} s)` : ""}</Link>
                  </div>
                </div>
              </div>
            </section>
            {st.data?.case.complaint && <CustomerBox caseId={caseId} complaint={st.data.case.complaint} opened={st.data.case.created_at} lastScan={last?.t} waybill={waybill} />}
          </div>
        </div>
      </div>
    );
  }

  // the same shape as an answered case (Rexton 2 Nov): verdict, one picture (its last scan point), facts one line each,
  // two actions, the customer note; then the cameras to check next. The step by step is the Proof's.
  const cam = (id: string) => id.replace(/^cam_/i, "").replace("_", " ");
  const seenNext = next.filter((r) => r.result === "seen"), notSeen = next.filter((r) => r.result === "not_seen");
  const noFootage = next.filter((r) => r.result === "no_footage");
  const unwatched = places.filter((p) => !p.covered_by.length).length;
  const facts: { text: string; bad?: boolean }[] = found ? [{ text: `Found by floor staff at ${hm(found.at)}.` }] : [
    ...(last ? [{ text: `Last scan: ${momentLabel(last.event_kind, last.station_id).toLowerCase()} at ${hm(last.t)}.` }] : []),
    ...(seenNext.length ? [{ text: `${hm(seenNext[0].predicted_t)}: seen on ${cam(seenNext[0].camera_id)}.` }]
      : notSeen.length ? [{ text: `Not seen on ${[...new Set(notSeen.map((r) => cam(r.camera_id)))].slice(0, 2).join(" or ")}, where it should have appeared next.`, bad: true }]
      : noFootage.length ? [{ text: `No footage yet from the ${new Set(noFootage.map((r) => r.camera_id)).size} cameras that would show where it went.` }] : []),
    ...(conflicts.length ? [{ text: `Records disagree: ${conflictWords(conflicts[0]).short}.`, bad: true }] : []),
    ...(places.length ? [{ text: `${places.length} place${places.length === 1 ? "" : "s"} it could have reached${unwatched ? `, ${unwatched} with no camera` : ""}.` }] : []),
  ];
  return (
    <div className="an">
      <CaseSteps caseId={caseId} waybill={waybill} said={st.data?.case.complaint ? "customer says it never arrived" : null} here={0} />
      <div className="an-body" data-answered="">
        <div className="an-main">
          <section className="an-verdict an-one" aria-labelledby="an-h" data-level={level}>
            <span className="an-chip" data-tone={pill[1]}>{pill[0]}</span>
            {ready ? <h1 id="an-h" className="an-h1">{head}</h1> : <div className="an-skel an-skel-h" aria-busy="true" />}
            {why && <p className="an-why">{why}</p>}
            <div className="an-one-grid">
              <div className="an-one-pic">
                {siteId && last ? <View siteId={siteId} point={last.station_id ?? last.device_id} at={last.t} tone={level === "high" ? "ok" : "bad"}
                  place={placeOf(last.event_kind, last.station_id).replace(/^the /, "")} /> : <div className="an-skel an-skel-pic" aria-busy="true" />}
              </div>
              <div className="an-one-side">
                {ready ? (
                  <ol className="an-facts" aria-label="What the records and cameras show">
                    {facts.map((f) => <li key={f.text} data-bad={f.bad ? "" : undefined}>{f.text}</li>)}
                  </ol>
                ) : <div className="an-skel an-skel-row" aria-busy="true" />}
                <div className="an-one-acts">
                  <Link className="hb-btn hb-btn-primary" href={`/cases/${caseId}/search`}>Send someone to look</Link>
                  <Link className="hb-btn" href={`/cases/${caseId}/proof`}>Watch the proof</Link>
                </div>
              </div>
            </div>
          </section>
          {st.data?.case.complaint && <CustomerBox caseId={caseId} complaint={st.data.case.complaint} opened={st.data.case.created_at} lastScan={last?.t} waybill={waybill} settled={!!found} />}
          {!found && mm && next.length > 0 && <section className="an-card an-next"><NextCams caseId={caseId} /></section>}
        </div>
      </div>
    </div>
  );
}
