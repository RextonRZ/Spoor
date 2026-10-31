"use client";
/**
 * Go look, ported from review/refs/flow/Search.dc.html (owner 09:22): a phone screen for floor staff. One place at a
 * time from the search task, how to get in, a picture, what to look for (from the parcel's own scan facts), a voice
 * note, and two big answers. "Not here" moves to the next place; "Found it" closes the case's search and opens the
 * report. Each answer is recorded on the case as a statement by floor staff.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useRef, useState } from "react";
import { api, invalidate, signedUrl, useResource } from "@/lib/api";
import type { Journey, MissingMoment, XY } from "@/lib/journey";
import { hhmm } from "@/lib/words";
import { toWav16k } from "@/lib/wav";
import HubPlan, { ZONE_NAMES } from "@/components/plan/HubPlan";
import "./golook.css";

interface Place { area_id: string; name: string; zone_id: string | null; centroid_xy: XY; why: string[] }
interface SearchView {
  found: { area_id: string; name: string; by: string; at: string } | null;
  tasks: { search_task_id: string; created_by: string; created_at: string; places: Place[];
    outcomes: { area_id: string; outcome: "found" | "not_found" }[] }[];
}
interface CaseState { case: { target_description: string } }

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

  return (
    <div className="gl">
      <header className="gl-head">
        <Link href={`/cases/${caseId}/proof`} aria-label="Back to the case" className="gl-back">
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><path d="M11 3.5L5.5 9l5.5 5.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </Link>
        <div className="gl-head-text">
          <span>{task ? `Search task · from the hub supervisor · ${hhmm(task.created_at)}` : "Search task"}</span>
          <span className="gl-wb">{waybill}</span>
        </div>
      </header>

      <div className="gl-main">
        {view.data?.found ? (
          <div className="gl-done">
            <h1 className="gl-h1">Found. Thank you.</h1>
            <p className="gl-p">Recorded by {view.data.found.by} at {hhmm(view.data.found.at)}. The case now shows Found.</p>
            <Link className="gl-btn gl-btn-found" href={`/cases/${caseId}/report`}>Open the report</Link>
          </div>
        ) : !task ? (
          <div className="gl-done">
            <h1 className="gl-h1">Send someone to look</h1>
            <p className="gl-p">Spoor lists the places it could be, most likely first. Floor staff answer each one on their phone.</p>
            <button type="button" className="gl-btn gl-btn-primary" onClick={startTask} disabled={busy === "start"}>{busy === "start" ? "Sending" : "Send to the floor"}</button>
          </div>
        ) : !place ? (
          <div className="gl-done">
            <h1 className="gl-h1">Every place checked</h1>
            <p className="gl-p">Not found in any of the {task.places.length} places. The case stays open with these places ruled out.</p>
            <Link className="gl-btn" href={`/cases/${caseId}`}>Back to the case</Link>
          </div>
        ) : (
          <>
            <div className="gl-title">
              <h1 className="gl-h1">Check {where(place)}</h1>
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
