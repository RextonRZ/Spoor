"use client";
/**
 * Floor search checklist (QUEUE H12): "go look here", built for a phone in one column with big buttons. Places come
 * from the backend's ranked possible places in walking order; each outcome is recorded as a human observation (your
 * pseudonymous id, the time, a content hash) and revises the case: "not here" removes the place from the possible area,
 * "found it here" makes the case Found.
 */
import Link from "next/link";
import { use, useState } from "react";
import { api, invalidate, useResource } from "@/lib/api";
import { clock } from "@/lib/journey";
import { ErrorState, Loading } from "@/components/ui";
import { Transcript, VoiceRecorder, useVoice } from "@/components/VoiceNote";
import "./search.css";

interface SearchView {
  status: "found" | "searching" | "none";
  found: { area_id: string; name: string; by: string; at: string } | null;
  not_here: string[];
  tasks: { search_task_id: string; created_by: string; created_at: string;
    places: { area_id: string; name: string; zone_id: string | null; why: string[] }[];
    outcomes: { area_id: string; outcome: "found" | "not_found"; recorded_by: string; recorded_at: string }[] }[];
}

const short = (name: string) => name.replace(/^Z\d+ /, "").replace(/ \(.*\)$/, "");

export default function SearchPage({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = use(params);
  const path = `/v1/cases/${caseId}/search-tasks`;
  const view = useResource<SearchView>(path);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const task = view.data?.tasks[view.data.tasks.length - 1];
  const voice = useVoice(caseId);

  async function create() {
    setBusy("create");
    setErr(null);
    try {
      await api(path, { method: "POST", json: {} });
      invalidate(path);
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); } finally { setBusy(null); }
  }
  async function record(areaId: string, outcome: "found" | "not_found") {
    if (!task) return;
    setBusy(areaId + outcome);
    setErr(null);
    try {
      await api(`${path}/${task.search_task_id}/outcome`, { method: "POST", json: { area_id: areaId, outcome } });
      invalidate(path);
      invalidate(`/v1/cases/${caseId}/possible-locations`);
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); } finally { setBusy(null); }
  }

  if (view.error) return <div className="sp-page"><ErrorState error={view.error} what="the floor search" onRetry={view.reload} /></div>;
  if (!view.data) return <div className="sp-page"><Loading label="Loading the floor search" lines={4} /></div>;
  const done = new Map((task?.outcomes ?? []).map((o) => [o.area_id, o]));
  return (
    <div className="sp-page srch" data-testid="search-page">
      <header className="srch-head">
        <p className="sp-eyebrow">Floor search</p>
        <h1 className="sp-h1">{view.data.found ? `Found at ${short(view.data.found.name)}` : "Go look here"}</h1>
        <p className="sp-caption">{view.data.found
          ? `Recorded by ${view.data.found.by} at ${clock(view.data.found.at, false)}. The case now shows Found.`
          : "Places it could be, in walking order. Each answer is recorded on the case with your user id and the time."}</p>
      </header>
      {!task && (
        <div className="srch-empty">
          <p>No search started for this case.</p>
          <button className="sp-btn sp-btn-primary srch-big" onClick={create} disabled={!!busy}>{busy ? "Starting" : "Start a floor search"}</button>
        </div>
      )}
      {task && (
        <ol className="srch-list">
          {task.places.map((pl, i) => {
            const o = done.get(pl.area_id);
            return (
              <li key={pl.area_id} className="srch-item" data-outcome={o?.outcome}>
                <div className="srch-top">
                  <span className="srch-n sp-num">{i + 1}</span>
                  <div>
                    <p className="srch-name">{short(pl.name)}</p>
                    <p className="sp-caption" style={{ margin: 0 }}>{pl.why.slice(0, 2).join(" · ")}</p>
                  </div>
                </div>
                {o ? (
                  <p className="srch-done">{o.outcome === "found" ? "Found here" : "Not here"} · {o.recorded_by} · {clock(o.recorded_at, false)}</p>
                ) : (
                  <div className="srch-actions">
                    <button className="sp-btn srch-big srch-found" onClick={() => record(pl.area_id, "found")} disabled={!!busy || !!view.data?.found}>Found it here</button>
                    <button className="sp-btn srch-big" onClick={() => record(pl.area_id, "not_found")} disabled={!!busy}>Not here</button>
                  </div>
                )}
                {(voice.data?.items ?? []).filter((v) => v.kind === "search_note" && v.area_id === pl.area_id).map((v) => <Transcript key={v.voice_transcript_id} v={v} />)}
                <VoiceRecorder caseId={caseId} kind="search_note" taskId={task.search_task_id} areaId={pl.area_id} label="Add a voice note" />
              </li>
            );
          })}
        </ol>
      )}
      {err && <div role="alert" className="sp-state sp-state-error">{err}</div>}
      <Link className="sp-btn sp-btn-sm" href={`/cases/${caseId}/summary`}>Back to the case summary</Link>
    </div>
  );
}
