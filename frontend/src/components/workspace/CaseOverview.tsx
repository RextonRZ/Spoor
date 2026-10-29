"use client";
/** Case overview (PRD §19.2 #1): question, last confirmed observation, unknowns, next evidence, report state. */
import { describeScan } from "@/lib/scans";
import Link from "next/link";
import { camId, hubCamera, scanPoint } from "@/lib/hub";
import { fmtTime, fmtUncertainty, toMs, TZ_LABEL } from "@/lib/time";
import { EvidenceLegend, Loading, ErrorState } from "@/components/ui";
import { clockWarning, useWorkspace, type TraceMode } from "./context";

const CLASS_LABEL: Record<string, string> = {
  fixed_scan: "fixed scanner read", handheld_scan: "handheld scan", video: "video, confirmed track",
  candidate_video: "candidate video", inherited_container: "inside a container",
};

export function useLastConfirmed() {
  const { lastSeen, parcel } = useWorkspace();
  const lc = lastSeen.data?.[0]?.last_confident ?? null;
  const scan = lc ? parcel.data?.scans.find((s) => s.scan_event_id === lc.evidence_id) : undefined;
  const sp = scan ? scanPoint(scan.station_id ?? scan.device_id) : undefined;
  return { lc, scan, sp };
}

export function CaseOverview() {
  const ws = useWorkspace();
  const { state, lastSeen, parcel, cameras, reports, caps, select, focusOn, setLitCameras } = ws;
  const { lc, scan, sp } = useLastConfirmed();
  if (state.loading) return <Loading label="Loading case" lines={5} />;
  if (state.error) return <ErrorState error={state.error} what="the case" onRetry={state.reload} />;
  const c = state.data!.case;
  const leads = lastSeen.data?.[0]?.leads ?? [];
  const report = reports.data?.[reports.data.length - 1];

  function whereDidItGo() {
    if (!lc || !scan) return;
    select({ kind: "scan", scanId: scan.scan_event_id });
    if (sp) {
      focusOn([sp.position_m[0], sp.position_m[1]], 13);
      setLitCameras(sp.visible_by);
    }
    document.getElementById("source-panel")?.scrollIntoView({ block: "nearest" });
  }

  const after = lc ? toMs(lc.time) : null;
  const viewers = sp?.visible_by ?? [];
  const covered = (hub: string) => cameras.data?.find((r) => r.camera.camera_id === camId.toBackend(hub))
    ?.coverage.some((cv) => after !== null && toMs(cv.end_utc) > after);
  const unknowns: string[] = [];
  if (!lc) unknowns.push("No scan or confirmed observation places this parcel yet.");
  else unknowns.push(`Where the parcel went after ${fmtTime(lc.time)} ${TZ_LABEL}: no later scan, no observation.`);
  if (!caps.data?.sam) unknowns.push("Footage has not been analysed: object tracking needs SAM (no API key).");
  if (parcel.data?.scans.some((s) => !s.synced)) unknowns.push("Scanner clock is not synchronized to the cameras; scan times are device times.");
  const badClocks = (cameras.data ?? []).filter((r) => r.coverage.length && clockWarning(r.clock_sync)).length;
  if (badClocks) unknowns.push(`${badClocks} camera clock${badClocks > 1 ? "s are" : " is"} unverified.`);

  return (
    <div className="sp-stack" style={{ gap: 16 }}>
      <div>
        <p className="sp-micro">Question</p>
        <h1 className="sp-h2" style={{ marginTop: 4, fontSize: 18, lineHeight: 1.3 }}>{c.question}</h1>
        <p className="sp-caption">{c.target_description} · case {c.case_id.slice(-8)}</p>
      </div>
      <button className="sp-btn sp-btn-primary" onClick={whereDidItGo} disabled={!lc || !scan} data-testid="where-did-it-go">
        Show where it was last confirmed
      </button>

      <section aria-labelledby="lc-h" className="sp-tint" style={{ padding: 14 }}>
        <p className="sp-micro" id="lc-h">Last confirmed</p>
        {lastSeen.loading ? <Loading lines={2} /> : lc ? (
          <div style={{ marginTop: 6 }}>
            <div className="sp-strong" style={{ fontWeight: 600 }}>{lc.label === "observed" ? "Observed" : "Estimated"}: {scan ? describeScan(scan).card : CLASS_LABEL[lc.class]}</div>
            <div className="sp-num" style={{ fontSize: 13 }}>{fmtTime(lc.time)} {TZ_LABEL}</div>
            <div className="sp-caption">{scan ? describeScan(scan).title : lc.where} · {sp?.id ?? lc.where} · {fmtUncertainty(lc.time_uncertainty_ms)}</div>
          </div>
        ) : <p className="sp-muted" style={{ margin: "6px 0 0" }}>Not confirmed by any scan or observation.</p>}
        {leads.length > 0 && (
          <div style={{ marginTop: 10 }}>
            <p className="sp-micro">Leads, not last seen</p>
            <ul className="sp-list" style={{ fontSize: 12.5, marginTop: 4 }}>
              {leads.map((l) => <li key={l.evidence_id}>{CLASS_LABEL[l.class]} · {l.where} · {fmtTime(l.time)}</li>)}
            </ul>
          </div>
        )}
      </section>

      <section aria-labelledby="unk-h">
        <p className="sp-micro" id="unk-h">Unknown</p>
        <ul className="sp-list" style={{ fontSize: 12.5, marginTop: 6 }}>
          {unknowns.map((u) => <li key={u} className="sp-row" style={{ alignItems: "flex-start" }}>
            <span className="sp-swatch" style={{ borderTop: "3px dotted var(--ev-unknown)", marginTop: 8, width: 12 }} aria-hidden />
            <span>{u}</span></li>)}
        </ul>
      </section>

      <section aria-labelledby="next-h">
        <p className="sp-micro" id="next-h">Next evidence</p>
        <ul className="sp-list" style={{ fontSize: 12.5, marginTop: 6 }}>
          {state.data!.evidence_requests.map((r) => (
            <li key={r.evidence_request_id}>{r.camera_id ? camId.toHub(r.camera_id) + ": " : ""}{r.reason}
              <span className="sp-caption"> · requested by the investigation</span></li>
          ))}
          {state.data!.evidence_requests.length === 0 && viewers.map((h) => (
            <li key={h}>
              <span className="sp-strong">{h}</span> {hubCamera(h)?.osd_label.toLowerCase()} from {lc ? fmtTime(lc.time, false) : "the last scan"}
              <span className="sp-caption"> · {covered(h) ? "footage imported, not yet analysed" : "footage not imported"}</span>
            </li>
          ))}
          {state.data!.evidence_requests.length === 0 && viewers.length === 0 && <li className="sp-muted">No suggestion: no last read point.</li>}
        </ul>
        {state.data!.evidence_requests.length === 0 && viewers.length > 0 && (
          <p className="sp-caption">Suggested from the camera mounting plan: these cameras see the last read point.</p>
        )}
      </section>

      <section aria-labelledby="rep-h" className="sp-row" style={{ justifyContent: "space-between" }}>
        <div><p className="sp-micro" id="rep-h">Report</p>
          <span style={{ fontSize: 12.5 }}>{report ? `${report.status} · ${fmtTime(report.at, false)}` : "not drafted"}</span></div>
        <Link className="sp-btn sp-btn-sm" href={`/cases/${c.case_id}/report`}>Review report</Link>
      </section>
    </div>
  );
}

export function TraceControls() {
  const { mode, setMode } = useWorkspace();
  const opts: { k: TraceMode; label: string }[] = [
    { k: "object", label: "Object" }, { k: "people", label: "People (anonymous)" }, { k: "all", label: "All" },
  ];
  return (
    <div className="sp-stack sp-gap-s">
      <p className="sp-micro" id="trace-h">Movement trace</p>
      <div className="sp-seg" role="group" aria-labelledby="trace-h" style={{ flexWrap: "wrap" }}>
        {opts.map((o) => (
          <button key={o.k} aria-pressed={mode === o.k} onClick={() => setMode(o.k)}>{o.label}</button>
        ))}
      </div>
      <EvidenceLegend compact />
    </div>
  );
}
