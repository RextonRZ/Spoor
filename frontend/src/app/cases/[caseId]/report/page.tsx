"use client";
/**
 * Report review / export (PRD §19.2 #8, §22). An investigator exports a draft; a different reviewer approves it.
 * Downloads are the backend's stored content and hash manifest, byte for byte.
 */
import Link from "next/link";
import { use, useEffect, useState } from "react";
import { api, API_BASE, invalidate, useResource } from "@/lib/api";
import { fmtDate, fmtTime, TZ_LABEL } from "@/lib/time";
import type { CaseState, Me, ReportRow } from "@/lib/types";
import { Empty, ErrorState, Loading } from "@/components/ui";

interface ReportFull {
  report_id: string;
  status: "draft" | "approved";
  approved_by: string | null;
  sha256: string;
  manifest: { report_sha256: string; sources: { media_id: string; sha256: string }[]; algorithm: string; note: string };
  content: Record<string, unknown>;
}

function download(name: string, data: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function ReportPage({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = use(params);
  const state = useResource<CaseState>(`/v1/cases/${caseId}/state`);
  const reports = useResource<ReportRow[]>(`/v1/cases/${caseId}/reports`);
  const me = useResource<Me>("/v1/me");
  const [sel, setSel] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ tone: "ok" | "err"; text: string } | null>(null);
  const list = reports.data ?? [];
  const current = sel ?? list[list.length - 1]?.report_id ?? null;
  const full = useResource<ReportFull>(current ? `/v1/reports/${current}` : null);
  const [htmlFor, setHtmlFor] = useState<{ id: string; html: string } | null>(null);
  const html = htmlFor && htmlFor.id === current ? htmlFor.html : null;

  useEffect(() => {
    if (!current) return;
    let live = true;
    fetch(`${API_BASE}/v1/reports/${current}?format=html`, { cache: "no-store" }).then((r) => r.text())
      .then((t) => live && setHtmlFor({ id: current, html: t })).catch(() => {});
    return () => { live = false; };
  }, [current]);

  async function act(kind: "export" | "approve") {
    setBusy(kind);
    setMsg(null);
    try {
      if (kind === "export") {
        const r = await api<{ report_id: string }>(`/v1/cases/${caseId}/export`, { method: "POST" });
        setSel(r.report_id);
        setMsg({ tone: "ok", text: "Draft exported. A reviewer other than you must approve it." });
      } else if (current) {
        const r = await api<{ report_id: string; sha256: string }>(`/v1/reports/${current}/approve`, { method: "POST" });
        setSel(r.report_id);
        setMsg({ tone: "ok", text: `Approved. Report hash ${r.sha256.slice(0, 16)}…` });
      }
      invalidate(`/v1/cases/${caseId}/reports`);
      invalidate("/v1/cases");
    } catch (e) {
      setMsg({ tone: "err", text: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(null);
    }
  }

  const role = me.data?.role;
  const sel_ = list.find((r) => r.report_id === current);
  return (
    <div className="sp-page sp-stack" style={{ gap: 20 }}>
      <header className="sp-row sp-wrap" style={{ justifyContent: "space-between", gap: 12 }}>
        <div>
          <p className="sp-eyebrow">Report review</p>
          <h1 className="sp-h1" style={{ fontSize: 26 }}>{state.data?.case.question ?? "Loading case"}</h1>
          <p className="sp-caption">Investigation support, not a forensic certification. Every claim links to a source frame or scan.</p>
        </div>
        <Link className="sp-btn sp-btn-sm" href={`/cases/${caseId}`}>Open workspace</Link>
      </header>

      <div className="sp-report-grid">
        <section className="sp-panel" aria-labelledby="rl-h">
          <div className="sp-panel-head"><h2 className="sp-h3" id="rl-h">Versions</h2></div>
          <div className="sp-panel-body sp-stack">
            {reports.loading && <Loading lines={2} />}
            {reports.error && <ErrorState error={reports.error} what="reports" onRetry={reports.reload} />}
            {reports.data && list.length === 0 && <Empty title="No report yet">Export a draft from the current case revision.</Empty>}
            <ul className="sp-list">
              {[...list].reverse().map((r) => (
                <li key={r.report_id}>
                  <button className="sp-btn sp-btn-sm" style={{ width: "100%", justifyContent: "space-between" }}
                    aria-pressed={r.report_id === current} onClick={() => setSel(r.report_id)}>
                    <span>{fmtDate(r.at)} {fmtTime(r.at, false)}</span>
                    <span className={r.status === "approved" ? "sp-chip sp-chip-safe" : "sp-chip"}>{r.status}</span>
                  </button>
                </li>
              ))}
            </ul>
            <hr className="sp-divider" />
            <button className="sp-btn" onClick={() => act("export")} disabled={!!busy || role === "site_admin"}>
              {busy === "export" ? "Exporting" : "Export a new draft"}</button>
            <button className="sp-btn sp-btn-primary" onClick={() => act("approve")}
              disabled={!!busy || role !== "reviewer" || sel_?.status !== "draft"}>
              {busy === "approve" ? "Approving" : "Approve this draft"}</button>
            <p className="sp-caption">{role === "reviewer" ? "You can approve drafts you did not export."
              : "Approval needs the reviewer role. Switch role in the sidebar."}</p>
            {msg && <div role={msg.tone === "err" ? "alert" : "status"} className={msg.tone === "err" ? "sp-state sp-state-error" : "sp-state"}>{msg.text}</div>}
          </div>
        </section>

        <section className="sp-panel" aria-labelledby="rv-h" style={{ minHeight: 560 }}>
          <div className="sp-panel-head">
            <h2 className="sp-h3" id="rv-h">{sel_ ? `Report ${sel_.status}` : "Preview"}</h2>
            {full.data && (
              <div className="sp-row sp-wrap" style={{ gap: 6 }}>
                <button className="sp-btn sp-btn-sm" onClick={() => download(`${full.data!.report_id}.json`, full.data!.content)}>Download report JSON</button>
                <button className="sp-btn sp-btn-sm" onClick={() => download(`${full.data!.report_id}.manifest.json`, full.data!.manifest)}>Download hash manifest</button>
              </div>
            )}
          </div>
          <div className="sp-panel-body sp-stack">
            {!current && <p className="sp-muted">No report selected.</p>}
            {full.error && <ErrorState error={full.error} what="the report" onRetry={full.reload} />}
            {full.data && (
              <dl className="sp-kv">
                <dt>Report hash</dt><dd className="sp-mono">{full.data.manifest.report_sha256}</dd>
                <dt>Algorithm</dt><dd>{full.data.manifest.algorithm}</dd>
                <dt>Sources</dt><dd>{full.data.manifest.sources.length === 0 ? "none cited (no verified observation yet)"
                  : full.data.manifest.sources.map((s) => `${s.media_id} ${s.sha256.slice(0, 12)}…`).join(", ")}</dd>
                <dt>Approved by</dt><dd>{full.data.approved_by ?? "not approved"}</dd>
                <dt>Custody</dt><dd>{full.data.manifest.note}</dd>
              </dl>
            )}
            {current && (html === null ? <Loading label="Loading preview" lines={4} /> : (
              <iframe title="Report preview" sandbox="" srcDoc={html} className="sp-report-frame" />
            ))}
            <p className="sp-caption">Times in the report are UTC; the workspace shows {TZ_LABEL}.</p>
          </div>
        </section>
      </div>
      <style>{`.sp-report-grid{display:grid;grid-template-columns:300px minmax(0,1fr);gap:16px}
        .sp-report-frame{width:100%;min-height:520px;border:1px solid var(--hairline);border-radius:10px;background:#fff}
        @media (max-width: 900px){.sp-report-grid{grid-template-columns:1fr}}`}</style>
    </div>
  );
}
