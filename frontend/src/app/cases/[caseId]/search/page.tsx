"use client";
/**
 * Go look (step 3), ops-console style: "Send staff to check". Two halves. Left, the supervisor's task: the places it
 * could be in the order they will be checked, each one waiting, being checked now, ruled out or found, and "Send to the
 * floor". Right, what floor staff see on their phone (the same screen, shown in a phone frame so the supervisor sees
 * exactly what was sent): one place at a time, how to get in, a picture, what to look for (from the parcel's own scan
 * facts), a voice note, and two big answers. "Not here" moves to the next place; "Found it" closes the case's search and
 * opens the report. Each answer is recorded on the case as a statement by floor staff.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useRef, useState } from "react";
import { api, invalidate, signedUrl, useResource } from "@/lib/api";
import type { Journey, MissingMoment, XY } from "@/lib/journey";
import { hhmm } from "@/lib/words";
import { CaseSteps } from "@/components/flow/CaseSteps";
import "@/app/hub/hub.css";
import { toWav16k } from "@/lib/wav";
import HubPlan, { ZONE_NAMES } from "@/components/plan/HubPlan";
import "./golook.css";

interface Place { area_id: string; name: string; zone_id: string | null; centroid_xy: XY; why: string[] }
interface SearchView {
  found: { area_id: string; name: string; by: string; at: string } | null;
  tasks: { search_task_id: string; created_by: string; created_at: string; places: Place[];
    outcomes: { area_id: string; outcome: "found" | "not_found" }[] }[];
}
interface CaseState { case: { target_description: string; complaint?: string | null } }
interface PossibleView { objects: { places: { area_id: string; name: string; zone_id: string | null; possible_share: number }[] }[] }

/** "the blind corner by the exception store" / "the cage staging". */
function where(p: Place): string {
  const zone = p.zone_id ? ZONE_NAMES[p.zone_id.replace(/^zone_/, "")] : undefined;
  const z = (zone ?? p.name.replace(/^Z\d+ /, "").replace(/\s*[(,;].*$/, "")).toLowerCase();
  return p.area_id.startsWith("BLIND") ? `the blind corner by the ${z}` : `the ${z}`;
}
/** How to get in, from the place's own description in the site plan: "Inside corner of the L-flow, behind 3 m sack racks." */
function howIn(p: Place): string {
  const d = p.name.replace(/^Z\d+ [^(]*\(?/, "").replace(/\(.*?\)/g, "").split(/[;)]/)[0].trim();
  return d ? `${d.charAt(0).toUpperCase()}${d.slice(1).replace(/[.,\s]+$/, "")}.` : "";
}

export default function GoLookPage({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = use(params);
  const router = useRouter();
  const path = `/v1/cases/${caseId}/search-tasks`;
  const view = useResource<SearchView>(path);
  const st = useResource<CaseState>(`/v1/cases/${caseId}/state`);
  const jr = useResource<Journey>(`/v1/cases/${caseId}/journey`);
  const mr = useResource<MissingMoment>(`/v1/cases/${caseId}/missing-moment`);
  const pr = useResource<PossibleView>(`/v1/cases/${caseId}/possible-locations`);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const task = view.data?.tasks.at(-1);
  const done = new Set(task?.outcomes.map((o) => o.area_id) ?? []);
  const place = task?.places.find((p) => !done.has(p.area_id));
  const waybill = st.data?.case.target_description.split(" ").at(-1) ?? "";
  const scans = jr.data?.objects[0]?.scans ?? [];
  const dims = scans.find((s) => s.dims_mm)?.dims_mm;
  const grams = scans.find((s) => s.weight_g)?.weight_g;
  const frame = mr.data?.objects[0]?.last_confirmed?.frames?.[0];

  async function startTask() {
    setBusy("start"); setErr(null);
    try { await api(path, { method: "POST", json: {} }); invalidate(path); }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)); } finally { setBusy(null); }
  }
  async function answer(outcome: "found" | "not_found") {
    if (!task || !place) return;
    setBusy(outcome); setErr(null);
    try {
      await api(`${path}/${task.search_task_id}/outcome`, { method: "POST", json: { area_id: place.area_id, outcome } });
      invalidate(path);
      invalidate(`/v1/cases/${caseId}/possible-locations`);
      if (outcome === "found") router.push(`/cases/${caseId}/report`);
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); } finally { setBusy(null); }
  }

  // the queue: the sent task's places in order, else the places Spoor would send staff to (most likely first)
  const queue = task
    ? task.places.map((pl) => ({ key: pl.area_id, name: where(pl as Place), state: view.data?.found?.area_id === pl.area_id ? "found" : done.has(pl.area_id) ? "ruled" : pl.area_id === place?.area_id ? "now" : "next" }))
    : (pr.data?.objects[0]?.places ?? []).filter((x) => x.possible_share > 0).slice(0, 6).map((x) => ({ key: x.area_id, name: where(x as unknown as Place), state: "next" }));
  const left = queue.filter((q) => q.state === "next" || q.state === "now").length;
  const status = view.data?.found ? ["Found", "ok"] : !task ? ["Not sent yet", "idle"] : !place ? ["All checked", "warn"] : ["With floor staff", "now"];
  const sub = view.data?.found ? `Recorded by ${view.data.found.by} at ${hhmm(view.data.found.at)}`
    : !task ? "Spoor lists the places it could be, most likely first. Floor staff answer each one on their phone."
    : !place ? `Not found in any of the ${task.places.length} places. The case stays open with these ruled out.`
    : `Sent ${hhmm(task.created_at)} by the hub supervisor · ${left} place${left === 1 ? "" : "s"} left`;

  return (
    <div className="gs">
      <CaseSteps caseId={caseId} waybill={waybill} said={st.data?.case.complaint ? "customer says it never arrived" : null} page="Go look" here={2} />
      <div className="gs-body">
        <section className="gs-task" aria-labelledby="gs-h">
          <span className="gs-chip" data-tone={status[1]}>{status[0]}</span>
          <h1 id="gs-h" className="gs-h1">{view.data?.found ? "Found. Thank you." : !task ? "Send someone to look" : !place ? "Every place checked" : `Checking ${queue.find((q) => q.state === "now")?.name ?? "the next place"}`}</h1>
          <p className="gs-sub">{sub}</p>
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
        </section>

        <aside className="gs-phonewrap" aria-label="What floor staff see">
          <p className="gs-phone-h">What the floor staff see</p>
          <div className="gs-phone">
            <div className="gs-notch" aria-hidden="true" />
            <div className="gl gs-screen">
              <header className="gl-head">
                <div className="gl-head-text">
                  <span>{task ? `Search task · from the hub supervisor · ${hhmm(task.created_at)}` : "Search task"}</span>
                  <span className="gl-wb">{waybill}</span>
                </div>
              </header>
              <div className="gl-main">
                {view.data?.found ? (
                  <div className="gl-done">
                    <h2 className="gl-h1">Found. Thank you.</h2>
                    <p className="gl-p">Recorded by {view.data.found.by} at {hhmm(view.data.found.at)}. The case now shows Found.</p>
                  </div>
                ) : !task ? (
                  <div className="gl-done">
                    <h2 className="gl-h1">Waiting for a task</h2>
                    <p className="gl-p">The first place to check appears here once the hub supervisor sends the search.</p>
                  </div>
                ) : !place ? (
                  <div className="gl-done">
                    <h2 className="gl-h1">Every place checked</h2>
                    <p className="gl-p">Not found in any of the {task.places.length} places.</p>
                  </div>
                ) : (
                  <>
                    <div className="gl-title">
                      <h2 className="gl-h1">Check {where(place)}</h2>
                      {howIn(place) && <p className="gl-p">{howIn(place)}</p>}
                    </div>
                    <div className="gl-pic">
                      {frame ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={signedUrl(frame.frame_url)} alt="The last camera frame of the parcel" />
                      ) : (
                        <HubPlan label={`Where to look: ${where(place)}`} focus={{ xy: place.centroid_xy, radius_m: 9, tone: "warn" }} legend={false} fit="width" minHeight={0} />
                      )}
                    </div>
                    <div className="gl-look">
                      <span className="gl-look-l">Look for</span>
                      <span className="gl-look-h">{dims ? `Parcel, ${dims.map((d) => Math.round(d / 10)).join(" × ")} cm` : "This parcel"}</span>
                      <span className="gl-look-s">{grams ? `${(grams / 1000).toFixed(1)} kg · ` : ""}label ends in …{waybill.slice(-4)}</span>
                    </div>
                    <HoldToRecord caseId={caseId} taskId={task.search_task_id} areaId={place.area_id} />
                    <span className="gl-spacer" />
                    {err && <p className="gl-err" role="alert">{err}</p>}
                    <div className="gl-answers">
                      <button type="button" className="gl-btn" onClick={() => answer("not_found")} disabled={!!busy}>{busy === "not_found" ? "Saving" : "Not here"}</button>
                      <button type="button" className="gl-btn gl-btn-found" onClick={() => answer("found")} disabled={!!busy}>{busy === "found" ? "Saving" : "Found it"}</button>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

/** Press and hold to speak; let go to send. The audio is kept as the original and transcribed (statement by floor staff). */
function HoldToRecord({ caseId, taskId, areaId }: { caseId: string; taskId: string; areaId: string }) {
  const voice = useResource<{ available: boolean; items: { area_id: string | null; transcript: string }[] }>(`/v1/cases/${caseId}/voice`);
  const [state, setState] = useState<"idle" | "rec" | "send" | "sent">("idle");
  const rec = useRef<MediaRecorder | null>(null);
  const ok = voice.data?.available ?? false;
  const mine = (voice.data?.items ?? []).filter((v) => v.area_id === areaId);
  async function down() {
    if (!ok || state === "rec") return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks: Blob[] = [];
      const r = new MediaRecorder(stream);
      r.ondataavailable = (e) => chunks.push(e.data);
      r.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setState("send");
        const fd = new FormData();
        fd.append("file", await toWav16k(new Blob(chunks, { type: r.mimeType })), "note.wav");
        fd.append("kind", "search_note");
        fd.append("search_task_id", taskId);
        fd.append("area_id", areaId);
        try { await api(`/v1/cases/${caseId}/voice`, { method: "POST", body: fd }); invalidate(`/v1/cases/${caseId}/voice`); setState("sent"); }
        catch { setState("idle"); }
      };
      rec.current = r;
      r.start();
      setState("rec");
    } catch { setState("idle"); }
  }
  const up = () => { if (state === "rec") rec.current?.stop(); };
  return (
    <>
      <button type="button" className="gl-btn gl-voice" disabled={!ok || state === "send"} onPointerDown={down} onPointerUp={up} onPointerLeave={up}
        title={ok ? undefined : "Voice notes aren't connected in this demo mode."}>
        <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><rect x="5.5" y="1.5" width="5" height="8" rx="2.5" fill="none" stroke="currentColor" strokeWidth="1.5" /><path d="M3 7.5a5 5 0 0010 0M8 12.5v2" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
        {state === "rec" ? "Recording… let go to send" : state === "send" ? "Sending" : ok ? "Hold to add a voice note" : "Voice notes are off in this demo"}
      </button>
      {mine.map((v, i) => <p key={i} className="gl-note">Statement by floor staff: “{v.transcript}”</p>)}
    </>
  );
}
