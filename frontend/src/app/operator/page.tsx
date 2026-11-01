"use client";
/**
 * Operator / showcase surface (PRD §23), separate from the investigator's workspace. It imports INPUTS (clips,
 * scan logs, simulated sensor events) and inspects what the system did (model calls, agent steps, evaluation).
 * It cannot set or edit any output: no answer, trace, provenance or metric can be entered here.
 */
import { useState } from "react";
import { Tabs } from "@/components/hub/parts";
import "./settings.css";
import { API_BASE, ApiError, invalidate, useResource } from "@/lib/api";
import { camId, hubCamera } from "@/lib/hub";
import { fmtUncertainty } from "@/lib/time";
import type { Capabilities, CameraRow, Me, MediaRow, Site } from "@/lib/types";
import { ErrorState, Loading } from "@/components/ui";
import { clockWarning } from "@/components/workspace/context";
import { postJson } from "@/components/Shell";

async function postForm<T>(path: string, form: FormData): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, { method: "POST", body: form });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiError(r.status, typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body));
  return body as T;
}

// Settings & data (owner 31 Oct: lean). Three tabs: Data (what the hub has imported, and the importers under Advanced),
// Cameras (each camera, its zone, its clock check and clips) and Models (which are on, and the proof of spend).
// Nothing here sets an answer; the evaluation, model-call trace, legal panel and simulated-sensor import were removed.
type OpTab = "data" | "cameras" | "models";

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
  const scans = useResource<{ total: number }>(siteId ? `/v1/sites/${siteId}/scans?limit=1` : null);
  const plan = useResource<{ plan_id: string; created_at: string }>(siteId ? `/v1/sites/${siteId}/plan` : null);
  const admin = me.data?.role === "site_admin";
  const [tab, setTab] = useState<OpTab>("data");
  const camsWithFootage = new Set((media.data ?? []).map((m) => m.media.camera_id)).size;
  const tabs: { id: OpTab; label: string; n: number }[] = [
    { id: "data", label: "Data", n: 3 },
    { id: "cameras", label: "Cameras", n: cams.data?.length ?? 0 },
    { id: "models", label: "Models", n: 3 },
  ];

  return (
    <div className="hb st">
      <header className="hb-head">
        <div>
          <h1 className="hb-title">Settings</h1>
          <p className="hb-sub">The data, cameras and models behind this hub</p>
        </div>
      </header>

      <section className="hb-panel" aria-label="Settings">
        <div className="hb-tabbar"><Tabs tabs={tabs} tab={tab} onTab={setTab} /></div>

        {tab === "data" && (
          <div className="st-body">
            <dl className="st-stats">
              <div><dt>Camera clips</dt><dd>{media.data?.length ?? 0}</dd><small>from {camsWithFootage} of {cams.data?.length ?? 19} cameras</small></div>
              <div><dt>Scans in the scan log</dt><dd>{scans.data?.total ?? 0}</dd><small>simulated</small></div>
              <div><dt>Site plan</dt><dd>{plan.data ? "Loaded" : "None"}</dd><small>{plan.data ? `version ${plan.data.plan_id.slice(-6)}` : "no site plan yet"}</small></div>
            </dl>
            <details className="st-adv">
              <summary>Import footage or a scan log</summary>
              <div className="sp-op-grid">
                <ImportClip siteId={siteId} cameras={cams.data ?? []} disabled={!admin} />
                <ImportScans siteId={siteId} disabled={!admin} />
              </div>
            </details>
          </div>
        )}

        {tab === "cameras" && (
          <div className="sp-tablewrap">
            {cams.loading && <Loading />}
            {cams.error && <ErrorState error={cams.error} what="cameras" onRetry={cams.reload} />}
            {cams.data && (
              <table className="sp-table">
                <thead><tr><th>Camera</th><th>Zone</th><th>Clock check</th><th className="num">Clips</th></tr></thead>
                <tbody>
                  {cams.data.map((c) => {
                    const hub = hubCamera(c.camera.camera_id);
                    const w = clockWarning(c.clock_sync);
                    return (
                      <tr key={c.camera.camera_id}>
                        <td><span className="sp-strong">{camId.toHub(c.camera.camera_id).replace("_", " ")}</span> <span className="sp-muted">{hub?.osd_label}</span></td>
                        <td>{hub?.zone}</td>
                        <td>{c.clock_sync ? <span className={w ? "sp-chip sp-chip-warn" : "sp-chip sp-chip-safe"}>{w ? "not verified" : fmtUncertainty(c.clock_sync.uncertainty_ms)}</span> : <span className="sp-muted">not checked</span>}</td>
                        <td className="num">{c.coverage.length}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        )}

        {tab === "models" && (
          <div className="st-body">
            {caps.data && (
              <ul className="st-caps">
                <Cap on={caps.data.sam} name="SAM 3.1 tracking" off="off in this demo" />
                <Cap on={caps.data.spark} name="Muse Spark camera analysts" off="off in this demo" />
                <Cap on={caps.data.agents} name="Agents" off="off in this demo" />
              </ul>
            )}
            <SpendPanel />
          </div>
        )}
      </section>
      <style>{`.sp-op-grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr))}`}</style>
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
