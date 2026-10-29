"use client";
/**
 * Operator / showcase surface (PRD §23), separate from the investigator's workspace. It imports INPUTS (clips,
 * scan logs, simulated sensor events) and inspects what the system did (model calls, agent steps, evaluation).
 * It cannot set or edit any output: no answer, trace, provenance or metric can be entered here.
 */
import { useState } from "react";
import { API_BASE, ApiError, invalidate, useResource } from "@/lib/api";
import { camId, hubCamera } from "@/lib/hub";
import { fmtTime, fmtUncertainty, TZ_LABEL } from "@/lib/time";
import type { Capabilities, CameraRow, CaseListRow, ClockDomainRow, Me, MediaRow, OperatorTrace, Site } from "@/lib/types";
import { Empty, ErrorState, Loading, SimulatedChip, Unavailable } from "@/components/ui";
import { clockWarning } from "@/components/workspace/context";

async function postForm<T>(path: string, form: FormData): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, { method: "POST", body: form });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiError(r.status, typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body));
  return body as T;
}

export default function OperatorPage() {
  const me = useResource<Me>("/v1/me");
  const caps = useResource<Capabilities>("/v1/capabilities");
  const sites = useResource<Site[]>("/v1/sites");
  const siteId = sites.data?.[0]?.site_id;
  const cams = useResource<CameraRow[]>(siteId ? `/v1/sites/${siteId}/cameras` : null);
  const media = useResource<MediaRow[]>(siteId ? `/v1/sites/${siteId}/media` : null);
  const domains = useResource<ClockDomainRow[]>(siteId ? `/v1/sites/${siteId}/clock-domains` : null);
  const cases = useResource<CaseListRow[]>("/v1/cases");
  const admin = me.data?.role === "site_admin";

  return (
    <div className="sp-page sp-stack" style={{ gap: 22 }}>
      <header>
        <p className="sp-eyebrow">Operator · showcase controls</p>
        <h1 className="sp-h1">Inputs and inspection</h1>
        <p className="sp-muted sp-body" style={{ marginTop: 6 }}>
          Load inputs and inspect what the system did with them. Nothing here can set an answer, a trace or a metric.
        </p>
      </header>
      {me.data && !admin && (
        <div className="sp-state" role="status">Imports and evaluation need the site admin role. You are signed in as {me.data.role.replace("_", " ")}; switch in the sidebar.</div>
      )}

      <section aria-labelledby="sys-h" className="sp-tint" style={{ padding: 18 }}>
        <p className="sp-micro" id="sys-h">Model-backed steps</p>
        {caps.loading && <Loading lines={2} />}
        {caps.data && (
          <ul className="sp-row sp-wrap" style={{ listStyle: "none", padding: 0, margin: "8px 0 0", gap: 18 }}>
            <Cap on={caps.data.sam} name="SAM 3.1 segmentation and tracking" />
            <Cap on={caps.data.spark} name="Muse Spark clip reasoning" />
            <Cap on={caps.data.agents} name={`Language-model agents (${caps.data.agent_backend})`} />
            <Cap on={caps.data.multiview_xyz} name="Multi-view XYZ" off="disabled until validated" />
            <Cap on={caps.data.cross_camera_association} name="Cross-camera association" off="disabled until validated" />
          </ul>
        )}
        <p className="sp-caption" style={{ marginTop: 10 }}>Keys stay on the backend. With none configured, each step reports &quot;analysis unavailable&quot; instead of a result.</p>
      </section>

      <div className="sp-op-grid">
        <ImportClip siteId={siteId} cameras={cams.data ?? []} disabled={!admin} />
        <ImportScans siteId={siteId} disabled={!admin} />
        <ImportSensors cases={cases.data ?? []} />
      </div>

      <section className="sp-panel" aria-labelledby="cam-h">
        <div className="sp-panel-head"><h2 className="sp-h3" id="cam-h">Cameras, clocks and calibration</h2>
          <span className="sp-caption">Poses from the mounting plan; not surveyed</span></div>
        <div className="sp-panel-body sp-tablewrap">
          {cams.loading && <Loading />}
          {cams.error && <ErrorState error={cams.error} what="cameras" onRetry={cams.reload} />}
          {cams.data && (
            <table className="sp-table">
              <thead><tr><th>Camera</th><th>Zone</th><th>Clock</th><th>Calibration</th><th className="num">Clips</th></tr></thead>
              <tbody>
                {cams.data.map((c) => {
                  const hub = hubCamera(c.camera.camera_id);
                  const w = clockWarning(c.clock_sync);
                  return (
                    <tr key={c.camera.camera_id}>
                      <td><span className="sp-strong">{camId.toHub(c.camera.camera_id)}</span> <span className="sp-muted">{hub?.osd_label}</span></td>
                      <td>{hub?.zone}</td>
                      <td>{c.clock_sync ? <><span className={w ? "sp-chip sp-chip-warn" : "sp-chip sp-chip-safe"}>{w ? "unverified" : fmtUncertainty(c.clock_sync.uncertainty_ms)}</span>
                        <div className="sp-caption">{c.clock_sync.method}</div></> : <span className="sp-muted">no sync</span>}</td>
                      <td>{c.calibration ? `${c.calibration.rig_state} v${c.calibration.version}` : <span className="sp-muted">uncalibrated: positions fall back to zone or image only</span>}</td>
                      <td className="num">{c.coverage.length}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </section>

      <div className="sp-op-grid">
        <section className="sp-panel" aria-labelledby="media-h">
          <div className="sp-panel-head"><h2 className="sp-h3" id="media-h">Footage</h2></div>
          <div className="sp-panel-body sp-tablewrap">
            {media.loading && <Loading />}
            {media.data?.length === 0 && <Empty title="No footage imported" />}
            {media.data && media.data.length > 0 && (
              <table className="sp-table">
                <thead><tr><th>Camera</th><th>Kind</th><th>Start ({TZ_LABEL})</th><th>SHA-256</th></tr></thead>
                <tbody>{media.data.map((m) => (
                  <tr key={m.media.media_id}>
                    <td>{camId.toHub(m.media.camera_id)}</td>
                    <td><SimulatedChip kind={m.recording_kind.replace("_", " ")} /></td>
                    <td className="sp-num">{m.coverage[0] ? fmtTime(m.coverage[0].start_utc) : "not placed"}</td>
                    <td className="sp-mono">{m.media.sha256.slice(0, 12)}…</td>
                  </tr>
                ))}</tbody>
              </table>
            )}
          </div>
        </section>
        <section className="sp-panel" aria-labelledby="dom-h">
          <div className="sp-panel-head"><h2 className="sp-h3" id="dom-h">Clock domains</h2></div>
          <div className="sp-panel-body sp-tablewrap">
            {domains.loading && <Loading />}
            {domains.data && (
              <table className="sp-table">
                <thead><tr><th>Domain</th><th>Kind</th><th>Fit</th></tr></thead>
                <tbody>{domains.data.filter((d) => d.domain.kind !== "camera").map((d) => (
                  <tr key={d.domain.clock_domain_id}>
                    <td>{d.domain.name}</td><td>{d.domain.kind.replace("_", " ")}</td>
                    <td>{d.sync ? fmtUncertainty(d.sync.uncertainty_ms) : <span className="sp-chip sp-chip-warn">not fitted: needs matched anchor events</span>}</td>
                  </tr>
                ))}</tbody>
              </table>
            )}
            <p className="sp-caption">Per-camera domains are listed with their cameras above.</p>
          </div>
        </section>
      </div>

      <TracePanel cases={cases.data ?? []} />
      <EvaluationPanel admin={admin} />
      <style>{`.sp-op-grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr))}`}</style>
    </div>
  );
}

function Cap({ on, name, off = "unavailable: no API key" }: { on: boolean; name: string; off?: string }) {
  return (
    <li className="sp-stack" style={{ gap: 2 }}>
      <span className="sp-strong" style={{ fontWeight: 600, fontSize: 13 }}>{name}</span>
      <span className={on ? "sp-chip sp-chip-safe" : "sp-chip sp-chip-warn"} style={{ alignSelf: "flex-start" }}>{on ? "available" : off}</span>
    </li>
  );
}

function Result({ r }: { r: { tone: "ok" | "err"; text: string } | null }) {
  if (!r) return null;
  return <div role={r.tone === "err" ? "alert" : "status"} className={r.tone === "err" ? "sp-state sp-state-error" : "sp-state"} style={{ fontSize: 12.5 }}>{r.text}</div>;
}

function ImportClip({ siteId, cameras, disabled }: { siteId?: string; cameras: CameraRow[]; disabled: boolean }) {
  const [res, setRes] = useState<{ tone: "ok" | "err"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const file = f.get("file") as File;
    const start = String(f.get("start"));
    const meta = {
      site_id: siteId, camera_id: f.get("camera"), rights_statement: String(f.get("rights")), purpose: "Spoor demonstration",
      consent_confirmed: f.get("consent") === "on", hosted_processing_allowed: false, retention_days: 30,
      recording_start_camera_time: start ? new Date(start).toISOString() : null, recording_kind: f.get("kind"),
    };
    const body = new FormData();
    body.set("meta", JSON.stringify(meta));
    body.set("file", file);
    setBusy(true);
    try {
      const r = await postForm<{ media_id: string; frames: number; deduplicated: boolean }>("/v1/media/uploads", body);
      setRes({ tone: "ok", text: `Imported ${r.media_id}: ${r.frames} frames${r.deduplicated ? " (already stored, deduplicated)" : ""}.` });
      invalidate("/v1/sites/");
    } catch (err) {
      setRes({ tone: "err", text: err instanceof Error ? err.message : String(err) });
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="sp-panel" aria-labelledby="clip-h">
      <div className="sp-panel-head"><h2 className="sp-h3" id="clip-h">Import a camera clip</h2></div>
      <form className="sp-panel-body sp-stack" onSubmit={submit}>
        <label className="sp-field"><span className="sp-label">Camera</span>
          <select name="camera" className="sp-select" required>
            {cameras.map((c) => <option key={c.camera.camera_id} value={c.camera.camera_id}>{c.camera.name}</option>)}
          </select></label>
        <label className="sp-field"><span className="sp-label">Clip (MP4)</span>
          <input name="file" type="file" accept="video/mp4" className="sp-input" required /></label>
        <label className="sp-field"><span className="sp-label">Recording start, camera clock</span>
          <input name="start" type="datetime-local" step="0.001" className="sp-input" />
          <span className="sp-caption">As shown by the camera OSD. Spoor treats it as unverified until anchors are matched.</span></label>
        <label className="sp-field"><span className="sp-label">Footage kind</span>
          <select name="kind" className="sp-select" defaultValue="synthetic_test">
            <option value="synthetic_test">synthetic test</option><option value="staged_event">staged event</option>
            <option value="real_incident">real incident</option></select></label>
        <label className="sp-field"><span className="sp-label">Rights statement</span>
          <input name="rights" className="sp-input" required minLength={10} defaultValue="Synthetic footage rendered from a fictional hub model; no real people" /></label>
        <label className="sp-row" style={{ fontSize: 12.5 }}><input type="checkbox" name="consent" required /> I confirm the rights and consent above.</label>
        <div><button className="sp-btn sp-btn-primary" disabled={disabled || busy || !siteId}>{busy ? "Importing" : "Import the clip"}</button></div>
        <Result r={res} />
      </form>
    </section>
  );
}

function ImportScans({ siteId, disabled }: { siteId?: string; disabled: boolean }) {
  const [res, setRes] = useState<{ tone: "ok" | "err"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    try {
      const r = await postForm<{ imported: number; skipped_exact_duplicates: number }>(`/v1/sites/${siteId}/scans/import`, f);
      setRes({ tone: "ok", text: `Imported ${r.imported} scan events; ${r.skipped_exact_duplicates} exact duplicates skipped.` });
      invalidate("/v1/");
    } catch (err) {
      setRes({ tone: "err", text: err instanceof Error ? err.message : String(err) });
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="sp-panel" aria-labelledby="scan-h">
      <div className="sp-panel-head"><h2 className="sp-h3" id="scan-h">Import a scan log</h2></div>
      <form className="sp-panel-body sp-stack" onSubmit={submit}>
        <label className="sp-field"><span className="sp-label">Scan log (JSON Lines, Spoor ScanEvent rows)</span>
          <input name="file" type="file" accept=".jsonl,.ndjson,application/json" className="sp-input" required /></label>
        <label className="sp-field"><span className="sp-label">Batch name</span>
          <input name="batch" className="sp-input" required defaultValue="manual_import" /></label>
        <fieldset className="sp-field" style={{ border: 0, padding: 0, margin: 0 }}>
          <legend className="sp-label">Source (required)</legend>
          <label className="sp-row" style={{ fontSize: 12.5 }}><input type="radio" name="source" value="simulated" required defaultChecked /> simulated</label>
          <label className="sp-row" style={{ fontSize: 12.5 }}><input type="radio" name="source" value="real" /> real</label>
          <span className="sp-caption">Simulated logs stay labelled simulated everywhere, including reports.</span>
        </fieldset>
        <div><button className="sp-btn sp-btn-primary" disabled={disabled || busy || !siteId}>{busy ? "Importing" : "Import the log"}</button></div>
        <Result r={res} />
      </form>
    </section>
  );
}

function ImportSensors({ cases }: { cases: CaseListRow[] }) {
  const [res, setRes] = useState<{ tone: "ok" | "err"; text: string } | null>(null);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const caseId = String(f.get("case"));
    f.delete("case");
    try {
      const r = await postForm<{ imported: string[]; simulated: number }>(`/v1/cases/${caseId}/evidence/import`, f);
      setRes({ tone: "ok", text: `Imported ${r.imported.length} sensor events, ${r.simulated} marked simulated.` });
    } catch (err) {
      setRes({ tone: "err", text: err instanceof Error ? err.message : String(err) });
    }
  }
  return (
    <section className="sp-panel" aria-labelledby="sens-h">
      <div className="sp-panel-head"><h2 className="sp-h3" id="sens-h">Simulated door or weight events</h2><SimulatedChip /></div>
      <form className="sp-panel-body sp-stack" onSubmit={submit}>
        <label className="sp-field"><span className="sp-label">Case</span>
          <select name="case" className="sp-select" required>
            {cases.map((c) => <option key={c.case.case_id} value={c.case.case_id}>{c.case.target_description}</option>)}
          </select></label>
        <label className="sp-field"><span className="sp-label">Sensor CSV</span>
          <input name="file" type="file" accept=".csv,text/csv" className="sp-input" required />
          <span className="sp-caption">Header: device_id,kind,value,zone_id,device_time_utc,clock_quality,source. Every row must say real or simulated.</span></label>
        <label className="sp-field"><span className="sp-label">Batch name</span>
          <input name="batch" className="sp-input" required defaultValue="sensor_sim" /></label>
        <div><button className="sp-btn" disabled={!cases.length}>Import sensor events</button></div>
        <Result r={res} />
      </form>
    </section>
  );
}

function TracePanel({ cases }: { cases: CaseListRow[] }) {
  const [caseId, setCaseId] = useState<string | null>(null);
  const id = caseId ?? cases[0]?.case.case_id ?? null;
  const trace = useResource<OperatorTrace>(id ? `/v1/operator/cases/${id}/trace` : null);
  return (
    <section className="sp-panel" aria-labelledby="tr-h">
      <div className="sp-panel-head"><h2 className="sp-h3" id="tr-h">Model calls and agent steps</h2>
        <select className="sp-select" style={{ width: "auto" }} aria-label="Case" value={id ?? ""} onChange={(e) => setCaseId(e.target.value)}>
          {cases.map((c) => <option key={c.case.case_id} value={c.case.case_id}>{c.case.target_description}</option>)}
        </select></div>
      <div className="sp-panel-body sp-stack">
        {trace.loading && <Loading />}
        {trace.error && (trace.error.status === 403
          ? <div className="sp-state">Needs the site admin or reviewer role.</div>
          : <ErrorState error={trace.error} what="the trace" onRetry={trace.reload} />)}
        {trace.data && (
          <>
            {Object.keys(trace.data.models).length === 0
              ? <Unavailable title="No model calls recorded">No raw model responses or SAM masks exist for this case: no model key is configured, so no call was made and nothing was billed.</Unavailable>
              : (
                <table className="sp-table"><thead><tr><th>Model</th><th className="num">Calls</th><th className="num">Cache hits</th>
                  <th className="num">Tokens in / out</th><th className="num">Frames</th><th className="num">Errors</th></tr></thead>
                  <tbody>{Object.entries(trace.data.models).map(([m, v]) => (
                    <tr key={m}><td>{m}</td><td className="num">{v.calls}</td><td className="num">{v.cache_hits}</td>
                      <td className="num">{v.input_tokens} / {v.output_tokens}</td><td className="num">{v.billed_frames}</td><td className="num">{v.errors}</td></tr>
                  ))}</tbody></table>
              )}
            <p className="sp-micro">Agent steps · {trace.data.agent_steps.length}</p>
            {trace.data.agent_steps.length === 0 && <p className="sp-muted" style={{ margin: 0, fontSize: 12.5 }}>None recorded. The deterministic orchestrator runs without agent steps when the language model is off.</p>}
            <ol className="sp-list" style={{ fontSize: 12.5 }}>
              {trace.data.agent_steps.map((s) => (
                <li key={`${s.request_id}-${s.seq}`}><span className="sp-num sp-muted">{fmtTime(s.at)}</span> {s.role} · {s.kind}
                  <pre className="sp-mono" style={{ whiteSpace: "pre-wrap", margin: "4px 0 0", color: "var(--ink-muted)" }}>{JSON.stringify(s.content).slice(0, 400)}</pre></li>
              ))}
            </ol>
          </>
        )}
      </div>
    </section>
  );
}

function EvaluationPanel({ admin }: { admin: boolean }) {
  const ev = useResource<Record<string, unknown>>(admin ? "/v1/evaluations" : null);
  return (
    <section className="sp-panel" aria-labelledby="ev-h">
      <div className="sp-panel-head"><h2 className="sp-h3" id="ev-h">Evaluation results</h2></div>
      <div className="sp-panel-body">
        {!admin && <p className="sp-muted" style={{ margin: 0 }}>Needs the site admin role.</p>}
        {ev.loading && <Loading />}
        {ev.error && <ErrorState error={ev.error} what="evaluation results" onRetry={ev.reload} />}
        {ev.data && (ev.data.status === "no_results"
          ? <Empty title="No evaluation run yet">{String(ev.data.note ?? "")}</Empty>
          : <pre className="sp-mono" style={{ whiteSpace: "pre-wrap", margin: 0 }}>{JSON.stringify(ev.data, null, 2).slice(0, 4000)}</pre>)}
      </div>
    </section>
  );
}
