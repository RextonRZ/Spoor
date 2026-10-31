"use client";
/**
 * Operator / showcase surface (PRD §23), separate from the investigator's workspace. It imports INPUTS (clips,
 * scan logs, simulated sensor events) and inspects what the system did (model calls, agent steps, evaluation).
 * It cannot set or edit any output: no answer, trace, provenance or metric can be entered here.
 */
import { useState, useSyncExternalStore } from "react";
import "./settings.css";
import { inboxClockWords, readInboxClock, writeInboxClock, type InboxClock } from "@/lib/inboxClock";
import LegalContextPanel from "@/components/LegalContextPanel";
import { API_BASE, ApiError, invalidate, useResource } from "@/lib/api";
import { camId, hubCamera } from "@/lib/hub";
import { fmtTime, fmtUncertainty, TZ_LABEL } from "@/lib/time";
import type { Capabilities, CameraRow, CaseListRow, ClockDomainRow, Me, MediaRow, OperatorTrace, Site } from "@/lib/types";
import { Empty, ErrorState, Loading, SimulatedChip, Unavailable } from "@/components/ui";
import { clockWarning } from "@/components/workspace/context";
import { postJson } from "@/components/Shell";

async function postForm<T>(path: string, form: FormData): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, { method: "POST", body: form });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiError(r.status, typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body));
  return body as T;
}

// Settings & data (owner 09:04/09:24): the old Operator page in the flow's look. Data sources, cameras and clocks,
// models (proof of spend) and evaluation. Imports stay available under "Advanced"; nothing here sets an answer.
type OpTab = "data" | "cameras" | "models" | "evaluation";
const OP_TABS: { k: OpTab; label: string }[] = [
  { k: "data", label: "Data sources" }, { k: "cameras", label: "Cameras & clocks" }, { k: "models", label: "Models" }, { k: "evaluation", label: "Evaluation" },
];

interface Spend { rows: { provider: string; model: string; job: string; calls: number; input_tokens: number; output_tokens: number;
  billed_units: number; unit: string; usd: number }[]; total_usd: number; calls: number; open_weights_share: number | null; note: string }

export default function OperatorPage() {
  const me = useResource<Me>("/v1/me");
  const caps = useResource<Capabilities>("/v1/capabilities");
  const sites = useResource<Site[]>("/v1/sites");
  const site = sites.data?.[0];
  const siteId = site?.site_id;
  const cams = useResource<CameraRow[]>(siteId ? `/v1/sites/${siteId}/cameras` : null);
  const media = useResource<MediaRow[]>(siteId ? `/v1/sites/${siteId}/media` : null);
  const domains = useResource<ClockDomainRow[]>(siteId ? `/v1/sites/${siteId}/clock-domains` : null);
  const scans = useResource<{ total: number }>(siteId ? `/v1/sites/${siteId}/scans?limit=1` : null);
  const plan = useResource<{ plan_id: string; created_at: string }>(siteId ? `/v1/sites/${siteId}/plan` : null);
  const cases = useResource<CaseListRow[]>("/v1/cases");
  const admin = me.data?.role === "site_admin";
  const [tab, setTab] = useState<OpTab>("data");
  const camsWithFootage = new Set((media.data ?? []).map((m) => m.media.camera_id)).size;
  const fourEyes = (site as (Site & { require_second_approver?: boolean }) | undefined)?.require_second_approver;

  return (
    <div className="st">
      <div className="st-main">
        <div className="st-head">
          <div>
            <p className="st-site">Settings &amp; data</p>
            <h1 className="st-h1">Settings</h1>
          </div>
          <div className="st-seg" role="tablist" aria-label="Settings sections">
            {OP_TABS.map((t) => <button key={t.k} role="tab" aria-selected={tab === t.k} onClick={() => setTab(t.k)}>{t.label}</button>)}
          </div>
        </div>

        {tab === "data" && <>
          <div className="st-cards">
            <div className="st-card"><p className="st-card-n">{media.data?.length ?? 0}</p><p className="st-card-l">clips from {camsWithFootage} of {cams.data?.length ?? 19} cameras</p></div>
            <div className="st-card"><p className="st-card-n">{scans.data?.total ?? 0}</p><p className="st-card-l">scans in the scan log (simulated)</p></div>
            <div className="st-card"><p className="st-card-n">{plan.data ? "1" : "0"}</p><p className="st-card-l">{plan.data ? `site plan · ${plan.data.plan_id.slice(-6)}` : "no site plan yet"}</p></div>
          </div>
          <p className="st-line">Require a second person to approve reports: <strong>{fourEyes === false ? "Off" : "On"}</strong>{fourEyes === false ? " (one-user demo site: a shared report is an investigation summary)." : "."}</p>
          <details className="st-adv">
            <summary>Advanced: import footage, a scan log or sensor events</summary>
            <InboxClockControl />
            <div className="sp-op-grid">
              <ImportClip siteId={siteId} cameras={cams.data ?? []} disabled={!admin} />
              <ImportScans siteId={siteId} disabled={!admin} />
              <ImportSensors cases={cases.data ?? []} />
            </div>
          </details>
        </>}

        {tab === "cameras" && <>
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
                          <td>{c.calibration ? `${c.calibration.rig_state} v${c.calibration.version}` : <span className="sp-muted">uncalibrated</span>}</td>
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
                {media.data?.length === 0 && <Empty title="No footage imported yet" />}
                {media.data && media.data.length > 0 && (
                  <table className="sp-table">
                    <thead><tr><th>Camera</th><th>Start ({TZ_LABEL})</th><th>SHA-256</th></tr></thead>
                    <tbody>{media.data.map((m) => (
                      <tr key={m.media.media_id}>
                        <td>{camId.toHub(m.media.camera_id)}</td>
                        <td className="sp-num">{m.coverage[0] ? fmtTime(m.coverage[0].start_utc) : "not placed"}</td>
                        <td className="sp-mono">{m.media.sha256.slice(0, 12)}…</td>
                      </tr>
                    ))}</tbody>
                  </table>
                )}
              </div>
            </section>
            <section className="sp-panel" aria-labelledby="dom-h">
              <div className="sp-panel-head"><h2 className="sp-h3" id="dom-h">Scanner clocks</h2></div>
              <div className="sp-panel-body sp-tablewrap">
                {domains.data && (
                  <table className="sp-table">
                    <thead><tr><th>Clock</th><th>Kind</th><th>Check</th></tr></thead>
                    <tbody>{domains.data.filter((d) => d.domain.kind !== "camera").map((d) => (
                      <tr key={d.domain.clock_domain_id}>
                        <td>{d.domain.name}</td><td>{d.domain.kind.replace("_", " ")}</td>
                        <td>{d.sync ? fmtUncertainty(d.sync.uncertainty_ms) : <span className="sp-muted">not checked yet</span>}</td>
                      </tr>
                    ))}</tbody>
                  </table>
                )}
              </div>
            </section>
          </div>
        </>}

        {tab === "models" && <>
          <SpendPanel />
          {caps.data && (
            <section className="st-card st-models" aria-labelledby="mods-h">
              <h2 id="mods-h">Models in this run</h2>
              <ul>
                <Cap on={caps.data.sam} name="SAM 3.1 tracking" off="off in this demo" />
                <Cap on={caps.data.spark} name="Muse Spark camera analysts" off="off in this demo" />
                <Cap on={caps.data.agents} name="Agents" off="off in this demo" />
              </ul>
            </section>
          )}
          <LegalContextPanel siteId={siteId} admin={admin} />
          <TracePanel cases={cases.data ?? []} />
        </>}
        {tab === "evaluation" && <EvaluationPanel admin={admin} />}
        <style>{`.sp-op-grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr))}`}</style>
      </div>
    </div>
  );
}

/** Proof of spend (agent_showcase_0925): every recorded model call by provider, model and job, from the cost ledger. */
function SpendPanel() {
  const sp = useResource<Spend>("/v1/spend");
  if (!sp.data) return sp.error ? <ErrorState error={sp.error} what="the spend" onRetry={sp.reload} /> : <Loading lines={2} />;
  const d = sp.data;
  return (
    <section className="st-card st-spend" aria-labelledby="spend-h">
      <div className="st-spend-head">
        <h2 id="spend-h">Proof of spend</h2>
        <span>US${d.total_usd.toFixed(2)} · {d.calls} model call{d.calls === 1 ? "" : "s"}{d.open_weights_share !== null ? ` · ${Math.round(d.open_weights_share * 100)} % on open weights` : ""}</span>
      </div>
      {d.rows.length === 0 ? <p className="st-muted">No model calls recorded on this store yet.</p> : (
        <div className="sp-tablewrap">
          <table className="sp-table">
            <thead><tr><th>Model</th><th>Job</th><th className="num">Calls</th><th className="num">Tokens in · out</th><th className="num">Units</th><th className="num">US$</th></tr></thead>
            <tbody>{d.rows.map((r) => (
              <tr key={`${r.provider}${r.model}${r.job}`}>
                <td>{r.model} <span className="sp-muted">· {r.provider === "baseten" ? "Baseten (open weights)" : "Meta Model API"}</span></td>
                <td>{r.job.replace(/_/g, " ")}</td>
                <td className="num">{r.calls}</td>
                <td className="num">{r.input_tokens.toLocaleString()} · {r.output_tokens.toLocaleString()}</td>
                <td className="num">{r.unit === "tokens" ? "" : `${Math.round(r.billed_units)} ${r.unit.replace("tokens + ", "")}`}</td>
                <td className="num">{r.usd.toFixed(3)}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
      <p className="st-muted">{d.note}. On-site triage (Muse Glimmer on Modal) runs outside this store; its run is in docs/open_weights_proof.</p>
    </section>
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
    const check = String(f.get("clockcheck") ?? "").trim();
    const ref = String(f.get("ref") ?? "").trim();
    const meta = {
      site_id: siteId, camera_id: f.get("camera"), rights_statement: String(f.get("rights")),
      purpose: ref ? `CCTV retrieval for ${ref}` : "CCTV retrieval (no case or claim reference given)",
      consent_confirmed: f.get("consent") === "on", hosted_processing_allowed: false, retention_days: 30,
      recording_start_camera_time: start ? new Date(start).toISOString() : null, recording_kind: f.get("kind"),
    };
    const body = new FormData();
    body.set("meta", JSON.stringify(meta));
    body.set("file", file);
    setBusy(true);
    try {
      if (check) {
        // Clock check at retrieval: recorder display minus a reference clock, recorded before the clip is placed on
        // the timeline (Home Office v3.0 3.3(a): "Any discrepancy between the system time and real time should be
        // recorded in the audit trail"). A recorder running ahead by d seconds needs -d to reach reference time.
        const d = Number(check);
        if (!Number.isFinite(d)) throw new Error("Clock check must be a number of seconds, e.g. 4.2 or -1.5");
        await postJson(`/v1/cameras/${f.get("camera")}/clock-syncs`, {
          offset_ms: -d * 1000, uncertainty_ms: 1000,
          method: "clock check at retrieval: recorder display vs reference clock, read by the operator (±1 s)",
          anchor_description: `recorder ${d >= 0 ? "ahead of" : "behind"} reference by ${Math.abs(d)} s at retrieval` });
      }
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
      <div className="sp-panel-head"><h2 className="sp-h3" id="clip-h">CCTV retrieval: import a recorder clip</h2></div>
      <form className="sp-panel-body sp-stack" onSubmit={submit}>
        <p className="sp-caption" style={{ margin: 0 }}>Import the recorder&apos;s native file. It is kept unchanged as the
          master, with its SHA-256; the app plays an H.264 working copy (converted format). Record the clock check and the
          period so the clip can be placed on the case timeline.</p>
        <label className="sp-field"><span className="sp-label">Case or claim reference</span>
          <input name="ref" className="sp-input" placeholder="e.g. the case ID or the customer&apos;s complaint reference" /></label>
        <label className="sp-field"><span className="sp-label">Camera</span>
          <select name="camera" className="sp-select" required>
            {cameras.map((c) => <option key={c.camera.camera_id} value={c.camera.camera_id}>{c.camera.name}</option>)}
          </select></label>
        <label className="sp-field"><span className="sp-label">Clip (MP4)</span>
          <input name="file" type="file" accept="video/mp4" className="sp-input" required /></label>
        <label className="sp-field"><span className="sp-label">Recording start, camera clock</span>
          <input name="start" type="datetime-local" step="0.001" className="sp-input" />
          <span className="sp-caption">As shown by the camera OSD. Spoor treats it as unverified until anchors are matched.</span></label>
        <label className="sp-field"><span className="sp-label">Clock check at retrieval (seconds, recorder minus reference)</span>
          <input name="clockcheck" inputMode="decimal" className="sp-input sp-num" placeholder="e.g. 4.2 if the recorder shows 14:32:11.2 at 14:32:07.0" />
          <span className="sp-caption">Read the recorder&apos;s displayed time against a reference clock when you export. Leave empty if not checked: the clip stays &quot;clock unverified&quot;.</span></label>
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
          : ev.data.kind === "hub_no_key" ? <HubEvaluation r={ev.data as unknown as HubEval} />
          : <pre className="sp-mono" style={{ whiteSpace: "pre-wrap", margin: 0 }}>{JSON.stringify(ev.data, null, 2).slice(0, 4000)}</pre>)}
      </div>
    </section>
  );
}

type HubAggregate = { n_cases: number; last_seen_accuracy: number | null; median_last_seen_time_error_s: number | null;
  abstained_after_last_scan: number; abstention_correct: number; abstention_missed_visible: number; false_left_hub: number };
type HubCase = { parcel: string; scenario?: string; title?: string; last_seen_correct: boolean; last_seen_time_error_s: number | null;
  pred_last_event: string | null; truth_last_event: string | null; abstention: string; false_left_hub: boolean };
interface HubSuite {
  name: "scenarios" | "control_flow";
  scenario: string;
  inputs: { scan_log: string; clips: string[]; clips_note?: string };
  aggregate: HubAggregate;
  cases: HubCase[];
}

interface HubEval {
  run_at: string;
  scenario: string;
  variant: string;
  inputs: { scan_log: string; clips: string[]; clips_note?: string };
  aggregate: HubAggregate;
  cases: HubCase[];
  /** review 007 #4: which suite the headline comes from; absent in results written before it */
  headline?: { source: "scenarios" | "control_flow"; label: string; caveat: string | null; scenarios: string[];
    waiting: { scenario: string; reason: string }[] };
  suites?: HubSuite[];
  truth_read_by: string;
  note: string;
}

const pct = (v: number | null) => (v === null ? "not measured" : `${Math.round(v * 100)} %`);

function HubStats({ a, size = 18 }: { a: HubAggregate; size?: number }) {
  return (
    <dl className="sp-row sp-wrap" style={{ gap: 28, margin: 0 }}>
      {[["Cases", String(a.n_cases)], ["Last seen correct", pct(a.last_seen_accuracy)],
        ["Median time error", a.median_last_seen_time_error_s === null ? "not measured" : `${a.median_last_seen_time_error_s.toFixed(1)} s`],
        ["Abstained after last scan", `${a.abstained_after_last_scan} / ${a.n_cases}`],
        ["Abstention correct", String(a.abstention_correct)], ["Visible but unanalysed", String(a.abstention_missed_visible)],
        ["False left the hub", String(a.false_left_hub)]].map(([k, v]) => (
        <div key={k}><dt className="sp-micro">{k}</dt><dd className="sp-num sp-strong" style={{ margin: "2px 0 0", fontSize: size }}>{v}</dd></div>
      ))}
    </dl>
  );
}

/** Parcel-hub evaluation of the no-key answers (ml/evaluation/spoor_eval/hub.py). Truth was read by the evaluator only.
 * Headline = the D scenarios (S1-S5) when they have renders and reference data; otherwise the control flow, with its
 * caveat on screen (review 007 #4). */
function HubEvaluation({ r }: { r: HubEval }) {
  const a = r.aggregate;
  const [all, setAll] = useState(false);
  const rows = all ? r.cases : r.cases.slice(0, 8);
  const fromScenarios = r.headline?.source === "scenarios";
  const others = (r.suites ?? []).slice(1);
  const caveat = r.headline ? r.headline.caveat
    : "Control flow: the scan log is the sorter's own (the WCS is the reference clock), so last seen 100 % and a 0.0 s median error are expected and prove little.";
  const showScenario = r.cases.some((c) => c.scenario);
  return (
    <div className="sp-stack">
      <div className="sp-row sp-wrap" style={{ gap: 8 }}>
        <span className={fromScenarios ? "sp-chip sp-chip-safe" : "sp-chip sp-chip-warn"} data-testid="eval-headline-source">
          headline: {fromScenarios ? `D scenarios ${r.headline!.scenarios.join(", ")}` : "control flow (fallback)"}</span>
        <span className="sp-caption">{r.scenario} · {r.variant} · run {fmtTime(r.run_at, false)} · scan log {r.inputs.scan_log} ·
          clips {r.inputs.clips.join(", ") || "none"}</span>
      </div>
      {caveat && <div className="sp-state sp-state-warn" role="note" style={{ fontSize: 12.5 }}>{caveat}</div>}
      <HubStats a={a} />
      <div className="sp-tablewrap">
        <table className="sp-table">
          <thead><tr>{showScenario && <th>Scenario</th>}<th>Subject</th><th>Last seen</th><th>Spoor vs truth event</th><th className="num">Time error</th><th>After the last scan</th><th>Left hub claim</th></tr></thead>
          <tbody>{rows.map((c) => (
            <tr key={`${c.scenario ?? ""}${c.parcel}`}>
              {showScenario && <td title={c.title}>{c.scenario}{c.title ? ` · ${c.title}` : ""}</td>}
              <td className="sp-mono">{c.parcel}</td>
              <td><span className={c.last_seen_correct ? "sp-chip sp-chip-safe" : "sp-chip sp-chip-alert"}>{c.last_seen_correct ? "correct" : "wrong"}</span></td>
              <td>{c.pred_last_event ?? "none"} / {c.truth_last_event ?? "none"}</td>
              <td className="num">{c.last_seen_time_error_s === null ? "n/a" : `${c.last_seen_time_error_s.toFixed(1)} s`}</td>
              <td>{c.abstention}</td>
              <td>{c.false_left_hub ? <span className="sp-chip sp-chip-alert">false claim</span> : "none"}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      {r.cases.length > 8 && <button className="sp-btn sp-btn-sm" style={{ alignSelf: "stretch" }} onClick={() => setAll(!all)}>
        {all ? "Show fewer" : `Show all ${r.cases.length}`}</button>}
      {others.map((s) => (
        <details key={s.name} className="sp-stack" style={{ gap: 8 }}>
          <summary className="sp-strong" style={{ cursor: "pointer" }}>
            {s.name === "control_flow" ? "Control flow (sanity check)" : s.scenario}: {s.aggregate.n_cases} cases, last seen {pct(s.aggregate.last_seen_accuracy)}
          </summary>
          <HubStats a={s.aggregate} size={15} />
          {s.name === "control_flow" && <p className="sp-caption" style={{ margin: 0 }}>Expected to be near perfect: the sorter&apos;s clock is the reference clock. Proves the plumbing, not the method.</p>}
        </details>
      ))}
      {!fromScenarios && r.headline?.waiting.length ? (
        <p className="sp-caption" style={{ margin: 0 }}>Waiting for: {Object.entries(r.headline.waiting.reduce<Record<string, string[]>>((acc, w) => {
          (acc[w.reason] ??= []).push(w.scenario);
          return acc;
        }, {})).map(([reason, ids]) => `${ids.join(", ")} (${reason})`).join(" · ")}</p>
      ) : null}
      <p className="sp-caption" style={{ margin: 0 }}>{r.note} {r.inputs.clips_note ? `Clips: ${r.inputs.clips_note}.` : ""} Ground truth was read by the {r.truth_read_by}; the app and backend never read it.</p>
    </div>
  );
}

/** Exceptions inbox clock (review F-style-b #4): replays what the Hub inbox shows N minutes after the log ended. */
function InboxClockControl() {
  const [, bump] = useState(0); // re-render after a write; the snapshot below re-reads storage
  const snap = useSyncExternalStore(() => () => {}, () => JSON.stringify(readInboxClock()), () => "null");
  const c: InboxClock = snap === "null" ? { kind: "log", minutes: 0 } : JSON.parse(snap);
  const setC = (v: InboxClock) => { void v; bump((n) => n + 1); };
  const opts: { label: string; v: InboxClock }[] = [
    { label: "End of the imported log", v: { kind: "log", minutes: 0 } },
    { label: "+30 min", v: { kind: "log", minutes: 30 } },
    { label: "+2 h", v: { kind: "log", minutes: 120 } },
    { label: "Now (live)", v: { kind: "now" } },
  ];
  const same = (a: InboxClock, b: InboxClock) => JSON.stringify(a) === JSON.stringify(b);
  return (
    <section className="sp-panel" aria-labelledby="inbox-clock" id="inbox-clock">
      <div className="sp-panel-head"><h2 className="sp-h3" id="inbox-clock-h">Exceptions inbox clock</h2></div>
      <div className="sp-panel-body sp-stack">
        <div className="sp-seg" role="group" aria-labelledby="inbox-clock-h" style={{ flexWrap: "wrap", alignSelf: "flex-start" }}>
          {opts.map((o) => <button key={o.label} aria-pressed={same(c, o.v)} onClick={() => { writeInboxClock(o.v); setC(o.v); }}>{o.label}</button>)}
        </div>
        <p className="sp-caption">The Hub inbox judges overdue scans as of {inboxClockWords(c)}. A synthetic log is short, so its parcels only
          become overdue when you replay a later moment. Stored in this browser only; it changes no evidence.</p>
      </div>
    </section>
  );
}
