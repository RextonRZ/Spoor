"use client";
/**
 * Go look (step 3), ops-console style: "Send staff to check". Two halves. Left, the supervisor's task: the places it
 * could be in the order they will be checked, each one waiting, being checked now, ruled out or found, "Send to the
 * floor", and what came back from the floor. Right, Spoor Floor, the worker's phone app (components/golook/FloorApp.tsx;
 * Rexton 3 Nov: a real app, light for the hall): tasks, the task (what to look for, where to walk), the search (where to
 * look, voice note), the barcode scan, found / not here. On a phone the app is the page. Each answer is recorded on the
 * case as a statement by floor staff.
 */
import Link from "next/link";
import { use, useEffect, useState } from "react";
import { api, invalidate, useResource } from "@/lib/api";
import type { Journey, XY } from "@/lib/journey";
import { hhmm } from "@/lib/words";
import { CaseSteps } from "@/components/flow/CaseSteps";
import { FloorApp } from "@/components/golook/FloorApp";
import { waited } from "@/components/hub/parts";
import { ZONE_NAMES } from "@/components/plan/HubPlan";
import "@/app/hub/hub.css";
import "./golook.css";

interface Place { area_id: string; name: string; zone_id: string | null; centroid_xy: XY; why: string[] }
interface SearchView {
  found: { area_id: string; name: string; by: string; at: string } | null;
  tasks: { search_task_id: string; created_by: string; created_at: string; places: Place[];
    outcomes: { area_id: string; outcome: "found" | "not_found"; note?: string | null; recorded_at?: string }[] }[];
}
interface CaseState { case: { target_description: string; complaint?: string | null; created_at: string } }
interface PossibleView { objects: { places: { area_id: string; name: string; zone_id: string | null; possible_share: number }[] }[] }

/** "the blind corner by the exception store" / "the cage staging". */
function where(p: Place): string {
  // a named place (the answer's own, e.g. "Exception store (Z11)") keeps its name; zone rows ("Z11 Exception store") read
  // from the zone list (it was "the blind corner by the exception store" for the store the answer names)
  if (!/^Z\d+ /.test(p.name)) return `the ${p.name.replace(/\s*\(Z\d+\)$/, "")}`;
  const zone = p.zone_id ? ZONE_NAMES[p.zone_id.replace(/^zone_/, "")] : undefined;
  const z = (zone ?? p.name.replace(/^Z\d+ /, "").replace(/\s*[(,;].*$/, "")).toLowerCase();
  return p.area_id.startsWith("BLIND") ? `the blind corner by the ${z}` : `the ${z}`;
}

export default function GoLookPage({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = use(params);
  const path = `/v1/cases/${caseId}/search-tasks`;
  const view = useResource<SearchView>(path);
  const st = useResource<CaseState>(`/v1/cases/${caseId}/state`);
  const jr = useResource<Journey>(`/v1/cases/${caseId}/journey`);
  const pr = useResource<PossibleView>(`/v1/cases/${caseId}/possible-locations`);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const replan: string | null = null; // (the app follows its own re-plan job; this side shows the plan once made)
  const task = view.data?.tasks.at(-1);
  const done = new Set(task?.outcomes.map((o) => o.area_id) ?? []);
  // one row per place: a zone row naming the same place as an earlier one (the answer's store, then its zone) is that place
  const places = (task?.places ?? []).filter((pl, i, all) => all.findIndex((q) => where(q as Place).toLowerCase() === where(pl as Place).toLowerCase()) === i);
  const place = places.find((p) => !done.has(p.area_id));
  const waybill = st.data?.case.target_description.split(" ").at(-1) ?? "";
  const scans = jr.data?.objects[0]?.scans ?? [];
  const last = scans.at(-1);
  const wait = last && st.data ? waited(last.t, st.data.case.created_at) : null;
  const narrow = useNarrow();
  const notes = (task?.outcomes ?? []).filter((o) => o.note);

  async function startTask() {
    setBusy("start"); setErr(null);
    try { await api(path, { method: "POST", json: {} }); invalidate(path); }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)); } finally { setBusy(null); }
  }
  // the queue: the sent task's places in order, else the places Spoor would send staff to (most likely first)
  const queue = task
    ? places.map((pl) => ({ key: pl.area_id, name: where(pl as Place), state: view.data?.found?.area_id === pl.area_id ? "found" : done.has(pl.area_id) ? "ruled" : pl.area_id === place?.area_id ? "now" : "next" }))
    : (pr.data?.objects[0]?.places ?? []).filter((x) => x.possible_share > 0).slice(0, 6).map((x) => ({ key: x.area_id, name: where(x as unknown as Place), state: "next" }));
  const left = queue.filter((q) => q.state === "next" || q.state === "now").length;
  const status = view.data?.found ? ["Found", "ok"] : !task ? ["Not sent yet", "idle"] : !place ? ["All checked", "warn"] : ["With floor staff", "now"];
  const sub = view.data?.found ? `Recorded by ${view.data.found.by} at ${hhmm(view.data.found.at)}`
    : !task ? "Spoor lists the places it could be, most likely first. Floor staff answer each one on their phone."
    : !place ? `Not found in any of the ${places.length} places. The case stays open with these ruled out.`
    : `Sent ${hhmm(task.created_at)} by the hub supervisor · ${left} place${left === 1 ? "" : "s"} left`;

  return (
    <div className="gs" data-narrow={narrow ? "" : undefined}>
      <CaseSteps caseId={caseId} waybill={waybill} said={st.data?.case.complaint ? "customer says it never arrived" : null} page="Go look" here={2} />
      <div className="gs-body">
        {narrow && <div className="gs-app"><FloorApp caseId={caseId} waybill={waybill} waited={wait} framed={false} /></div>}
        <section className="gs-task" aria-labelledby="gs-h">
          <span className="gs-chip" data-tone={status[1]}>{status[0]}</span>
          <h1 id="gs-h" className="gs-h1">{view.data?.found ? "Found. Thank you." : !task ? "Send someone to look" : !place ? "Every place checked" : `Checking ${queue.find((q) => q.state === "now")?.name ?? "the next place"}`}</h1>
          <p className="gs-sub">{sub}</p>
          <Replan key={replan ?? "none"} caseId={caseId} job={replan} misses={(task?.outcomes ?? []).filter((o) => o.outcome === "not_found").length} />
          {queue.length > 0 && (
            <ol className="gs-queue" aria-label="Places to check, in order">
              {queue.map((q, i) => (
                <li key={q.key} data-state={q.state}>
                  <span className="gs-qn" aria-hidden="true">{q.state === "ruled" ? <svg viewBox="0 0 16 16"><path d="M4 8h8" /></svg> : q.state === "found" ? <svg viewBox="0 0 16 16"><path d="m3.5 8.5 3 3 6-6.5" /></svg> : i + 1}</span>
                  <span className="gs-qt">{q.name.replace(/^the /, "").replace(/^\w/, (c) => c.toUpperCase())}</span>
                  <span className="gs-qs">{q.state === "now" ? "Being checked" : q.state === "ruled" ? "Not here" : q.state === "found" ? "Found" : task ? "Waiting" : ""}</span>
                </li>
              ))}
            </ol>
          )}
          <div className="gs-acts">
            {view.data?.found ? <Link className="hb-btn hb-btn-primary" href={`/cases/${caseId}/report`}>Open the report</Link>
              : !task ? <button type="button" className="hb-btn hb-btn-primary" onClick={startTask} disabled={busy === "start"}>{busy === "start" ? "Sending" : "Send to the floor"}</button>
              : !place ? <Link className="hb-btn" href={`/cases/${caseId}`}>Back to the case</Link>
              : <span className="gs-wait"><i aria-hidden="true" />Waiting for the floor staff to answer</span>}
          </div>
          {err && !task && <p className="gl-err" role="alert">{err}</p>}
          {notes.length > 0 && (
            <div className="gs-notes">
              <p className="gs-notes-h">From the floor</p>
              {notes.map((o, i) => (
                <p key={i} className="gs-note"><b>{queue.find((q) => q.key === o.area_id)?.name.replace(/^the /, "") ?? "A place"}</b>
                  {o.outcome === "found" ? " · found" : " · not here"}{o.recorded_at ? ` · ${hhmm(o.recorded_at)}` : ""}<span>“{o.note}”</span></p>
              ))}
            </div>
          )}
        </section>

        {!narrow && (
          <aside className="gs-phonewrap" aria-label="What floor staff see on their phone">
            <p className="gs-phone-h">Spoor Floor, on the worker&apos;s phone · <Link href={`/floor/${caseId}`} target="_blank">open it full screen</Link></p>
            <FloorApp caseId={caseId} waybill={waybill} waited={wait} />
          </aside>
        )}
      </div>
    </div>
  );
}

/** The loop after a miss (tick 2315): "Not here" sends Muse Wonder back to plan where it went next, with the staff's
 *  check in its evidence. While it plans: one quiet line; then its plan (a plan for what to analyse, not evidence). */
interface LeadPlan { plan: { summary: string; steps: { camera_id: string; what_to_check: string }[]; at: string } | null }
function Replan({ caseId, job, misses }: { caseId: string; job: string | null; misses: number }) {
  const [state, setState] = useState<"done" | "failed" | null>(null); // (keyed by the job: a new miss starts fresh)
  const lp = useResource<LeadPlan>(misses > 0 || job ? `/v1/cases/${caseId}/lead-plan` : null);
  useEffect(() => {
    if (!job) return;
    let live = true;
    const tick = async () => {
      try {
        const j = await api<{ status: string }>(`/v1/jobs/${job}`);
        if (!live) return;
        if (j.status === "done" || j.status === "succeeded") { setState("done"); invalidate(`/v1/cases/${caseId}/lead-plan`); return; }
        if (j.status === "failed" || j.status === "error") { setState("failed"); return; }
      } catch { if (live) { setState("failed"); return; } }
      window.setTimeout(tick, 2000);
    };
    void tick();
    return () => { live = false; };
  }, [job, caseId]);
  const plan = lp.data?.plan;
  if (job && state === null) return <p className="gs-replan" role="status"><span className="gs-replan-dot" />Muse Wonder is planning where it went next, with this check in its evidence.</p>;
  if (state === "failed") return <p className="gs-replan" role="status">The new plan could not be made. Try Investigate again from the case.</p>;
  if (!plan || (misses === 0 && !job)) return null;
  return (
    <div className="gs-replan-box">
      <p className="gs-replan-h">New plan from Muse Wonder, after the miss</p>
      <p className="gs-replan-s">{plan.summary}</p>
      {plan.steps.length > 0 && (
        <ol>{plan.steps.slice(0, 3).map((s, i) => <li key={i}><b>{s.camera_id.replace(/^cam_/, "").replaceAll("_", " ")}</b> {s.what_to_check}</li>)}</ol>
      )}
      <span className="gs-replan-note">A plan for what to watch next, not evidence.</span>
    </div>
  );
}

/** A phone-width screen: the worker app is the page there (no phone drawn around it). */
function useNarrow() {
  const [n, setN] = useState(false);
  useEffect(() => {
    const m = window.matchMedia("(max-width: 700px)");
    const f = () => setN(m.matches);
    f(); m.addEventListener("change", f);
    return () => m.removeEventListener("change", f);
  }, []);
  return n;
}
