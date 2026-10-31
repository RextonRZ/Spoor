"use client";
/**
 * Answer, ported from review/refs/flow/Case.dc.html (owner 09:22). The answer first: a status pill, one sentence, a
 * plain explanation, "How sure" with three reasons, one primary action (Watch the proof), the key frame, and the moments
 * in order. Everything comes from the case's read models (journey, missing moment, possible places, records conflicts,
 * floor search); in no-key mode it says what is really known.
 */
import Link from "next/link";
import { use } from "react";
import { signedUrl, useResource } from "@/lib/api";
import type { Journey, MissingMoment } from "@/lib/journey";
import { hms, momentLabel, placeOf, shortPlace } from "@/lib/words";
import { CaseSteps } from "@/components/flow/CaseSteps";
import HubPlan, { ZONE_NAMES } from "@/components/plan/HubPlan";
import "./answer.css";

interface CaseState { case: { case_id: string; target_description: string; complaint?: string | null } }
interface Possible { objects: { places: { area_id: string; name: string; zone_id: string | null; possible_share: number }[] }[] }
interface Conflicts { objects: { conflicts: { kind: string; divergence_t: string; statement: string }[] }[] }
interface SearchView { found: { name: string; by: string; at: string } | null }

const low = (t: string) => t.charAt(0).toLowerCase() + t.slice(1); // "Into chute C12" -> "into chute C12"
const clean = (name: string) => name.replace(/^Z\d+ /, "").replace(/\s*\(.*$/, "");

export default function AnswerPage({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = use(params);
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
  const lc = mm?.last_confirmed;
  const places = (pr.data?.objects[0]?.places ?? []).filter((p) => p.possible_share > 0);
  const conflicts = cr.data?.objects[0]?.conflicts ?? [];
  const found = sr.data?.found ?? null;
  const next = mm?.expected_next ?? [];
  const withFootage = next.filter((r) => r.result !== "no_footage");
  const seen = next.filter((r) => r.result === "seen");
  const waybill = st.data?.case.target_description.split(" ").at(-1) ?? "";
  const ready = !!(j && mm && pr.data);

  // the answer, in the prototype's shape: pill, one sentence, two sentences of why
  let pill: [string, string] = ["Lost track", "bad"];
  let head = "Checking the records";
  let why = "";
  if (ready && found) {
    pill = ["Found", "ok"];
    head = `Found at ${low(clean(found.name))} at ${hms(found.at)}.`;
    why = `Floor staff (${found.by}) found it there during the search. The last record before that was ${last ? `${low(momentLabel(last.event_kind, last.station_id))} at ${hms(last.t)}` : "none"}.`;
  } else if (ready && seen.length) {
    pill = ["Likely location found", "ok"];
    head = `Seen on ${seen[0].camera_id.replace("cam_", "").replace("_", " ")} at ${hms(seen[0].predicted_t)}.`;
    why = "A camera that should show it next did. Watch the proof to see the frame.";
  } else if (ready && last) {
    head = `Lost track after ${placeOf(last.event_kind, last.station_id)} at ${hms(last.t)}.`;
    why = `The last record is ${low(momentLabel(last.event_kind, last.station_id))} at ${hms(last.t)}. ${withFootage.length
      ? "The cameras that would show where it went next have footage that hasn't been checked yet."
      : "None of the cameras that would show where it went next has footage yet, so nothing after that is confirmed."}`;
  } else if (ready) {
    head = "No scans of this parcel at this hub.";
  }

  // how sure: three plain reasons from the evidence
  const level = found ? "high" : seen.length ? "medium" : "low";
  const reasons: { text: string; tone: "ok" | "bad" | "plain" }[] = [];
  if (last) reasons.push({ text: `Last scan: ${low(momentLabel(last.event_kind, last.station_id))} at ${hms(last.t)}.`, tone: "ok" });
  if (next.length) reasons.push({ text: withFootage.length
    ? `${withFootage.length} of ${next.length} cameras that would show it next have footage, not checked yet.`
    : `None of the ${next.length} cameras that would show it next has footage yet.`, tone: "plain" });
  if (conflicts.length) reasons.push({ text: `The sorter's own times don't fit the belt: ${conflicts[0].statement.replace(/: the records conflict$/, "")}.`, tone: "bad" });
  else if (places.length) reasons.push({ text: `It could be in ${places.length} place${places.length === 1 ? "" : "s"}. Most likely: ${shortPlace(places[0], ZONE_NAMES)}.`, tone: "plain" });

  const frame = lc?.frames?.[0];
  const conflictAt = conflicts[0]?.divergence_t;

  return (
    <div className="an">
      <CaseSteps caseId={caseId} waybill={waybill} said={st.data?.case.complaint ? "customer says it never arrived" : null} here={0} />
      <div className="an-main">
        <section className="an-left">
          <div className="an-answer">
            <span className="an-pill" data-tone={pill[1]}>{pill[0]}</span>
            <h1 className="an-h1">{head}</h1>
            {why && <p className="an-why">{why}</p>}
          </div>
          {ready && reasons.length > 0 && (
            <div className="an-sure">
              <p className="an-sure-h">How sure: <span data-level={level}>{level}</span></p>
              {reasons.slice(0, 3).map((r) => (
                <div key={r.text} className="an-reason"><span className="an-dot" data-tone={r.tone} /><span>{r.text}</span></div>
              ))}
            </div>
          )}
          <div className="an-acts">
            <Link className="an-btn an-btn-primary" href={`/cases/${caseId}/proof`}>Watch the proof</Link>
            <Link className="an-btn" href={`/cases/${caseId}/search`}>Send someone to look</Link>
          </div>
        </section>

        <section className="an-right">
          <Link href={`/cases/${caseId}/proof`} className="an-frame">
            {frame ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={signedUrl(frame.frame_url)} alt={`${frame.camera_id} at the last scan`} />
            ) : lc?.xy ? (
              <HubPlan label="Where it stopped" focus={{ xy: lc.xy, radius_m: 10, tone: "bad" }} legend={false} fit="width" journey={j} quiet />
            ) : <span className="an-frame-none" />}
          </Link>
          <p className="an-cap">{frame ? `${frame.camera_id.replace("cam_", "").replace("_", " ")} · ${lc ? hms(lc.t) : ""}` : lc ? `Where it stopped · ${last ? placeOf(last.event_kind, last.station_id) : ""} · ${hms(lc.t)} · no footage yet` : ""}</p>
        </section>

        {scans.length > 0 && (
          <section aria-label="What happened, in order" className="an-moments">
            {[...scans.map((s) => ({ key: s.scan_event_id, t: s.t, label: momentLabel(s.event_kind, s.station_id), tone: undefined as string | undefined })),
              ...(conflictAt ? [{ key: "conflict", t: conflictAt, label: "Records disagree. The sorter's times don't fit the belt.", tone: "bad" }] : [])]
              .sort((x, y) => x.t.localeCompare(y.t)).map((m) => (
                <div key={m.key} className="an-moment" data-tone={m.tone}>
                  <span className="an-moment-t">{hms(m.t)}</span>
                  <span className="an-moment-l">{m.label}</span>
                </div>
              ))}
            {found ? (
              <div className="an-moment" data-tone="ok"><span className="an-moment-t">{hms(found.at)}</span><span className="an-moment-l">Found by floor staff</span></div>
            ) : last && (
              <div className="an-moment" data-tone="unknown"><span className="an-moment-t">after {hms(last.t)}</span><span className="an-moment-l">Not seen since</span></div>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
