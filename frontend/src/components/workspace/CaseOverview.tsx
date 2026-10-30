"use client";
/** Case overview (PRD §19.2 #1): question, last confirmed observation, unknowns, next evidence, report state. */
import { describeScan } from "@/lib/scans";
import Link from "next/link";
import { useState } from "react";
import { camId, scanPoint } from "@/lib/hub";
import { fmtTime, toMs } from "@/lib/time";
import { answerParts, nextAction, unknownSentences } from "@/lib/journey";
import { Loading, ErrorState } from "@/components/ui";
import { useWorkspace, type TraceMode } from "./context";

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
  const { state, lastSeen, reports, caps, select, focusOn, setLitCameras, journey, missing } = ws;
  const jo = journey.data?.objects[0];
  const mmo = missing.data?.objects[0];
  const parts = answerParts(jo, mmo);
  const action = nextAction(mmo);
  const lastBead = jo?.last_confirmed?.kind === "scan" ? jo.scans.find((x) => x.scan_event_id === jo.last_confirmed!.evidence_id) : undefined;
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
        {!journey.data ? <Loading lines={2} /> : jo?.last_confirmed ? (
          <div style={{ marginTop: 6 }} data-testid="ws-last-confirmed">
            <div className="sp-strong" style={{ fontWeight: 620, fontSize: 15 }}>{parts.head}</div>
            <div className="sp-caption">{lastBead ? `${describeScan(lastBead).card} · ${lastBead.clock.synchronized ? "clock synchronized" : "scanner clock, not synchronized"}` : "camera sighting"}</div>
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

      <ScanHistory />

      <section aria-labelledby="unk-h">
        <p className="sp-micro" id="unk-h">Unknown</p>
        <div className="sp-stack" style={{ gap: 4, marginTop: 6, fontSize: 13 }}>
          {unknownSentences(jo, mmo, !!caps.data?.sam).map((u) => <p key={u} style={{ margin: 0 }}>{u}</p>)}
        </div>
      </section>

      <section aria-labelledby="next-h">
        <p className="sp-micro" id="next-h">Next action</p>
        {action ? <>
          <p style={{ margin: "6px 0 2px", fontSize: 13.5, fontWeight: 600 }} className="sp-strong" data-testid="ws-next-action">{action.text}</p>
          <p className="sp-caption">{action.detail}</p>
        </> : <p className="sp-muted" style={{ margin: "6px 0 0", fontSize: 13 }}>{missing.data ? "No action can be derived from the evidence yet." : "Working it out from the plan."}</p>}
        {state.data!.evidence_requests.map((r) => (
          <p key={r.evidence_request_id} className="sp-caption">{r.camera_id ? camId.toHub(r.camera_id) + ": " : ""}{r.reason} · requested by the investigation</p>
        ))}
      </section>

      <section aria-labelledby="rep-h" className="sp-row" style={{ justifyContent: "space-between" }}>
        <div><p className="sp-micro" id="rep-h">Report</p>
          <span style={{ fontSize: 12.5 }}>{report ? `${report.status} · ${fmtTime(report.at, false)}` : "not drafted"}</span></div>
        <div className="sp-row" style={{ gap: 6 }}>
          <Link className="sp-btn sp-btn-sm" href={`/cases/${c.case_id}/summary`} data-testid="open-summary">Case summary</Link>
          <Link className="sp-btn sp-btn-sm" href={`/cases/${c.case_id}/report`}>Review report</Link>
        </div>
      </section>
    </div>
  );
}

/** The consignment's scan history, as a hub ops / claims team reads it first (QUEUE G): every scan of the waybill in
 * time order, with the gap since the previous scan. Each row opens its source. It says where the consignment was
 * SCANNED; where it went in between is what the footage is for. */
function ScanHistory() {
  const { parcel, select } = useWorkspace();
  const [all, setAll] = useState(false);
  const scans = [...(parcel.data?.scans ?? [])].sort((a, b) => toMs(a.time) - toMs(b.time));
  if (parcel.loading) return <Loading lines={2} />;
  if (!scans.length) return null;
  const shown = all ? scans : scans.slice(-6);
  return (
    <section aria-labelledby="sh-h">
      <p className="sp-micro" id="sh-h">Scan history · {scans.length} scan{scans.length === 1 ? "" : "s"}</p>
      <p className="sp-caption" style={{ margin: "2px 0 6px" }}>Where it was scanned, not where it went.</p>
      <ol className="sp-list sp-scanhist" style={{ fontSize: 12.5 }}>
        {shown.map((s) => {
          const i = scans.indexOf(s);
          const gap = i > 0 ? (toMs(s.time) - toMs(scans[i - 1].time)) / 1000 : null;
          return (
            <li key={s.scan_event_id}>
              {gap !== null && gap >= 60 && <span className="sp-caption sp-scanhist-gap">no scan for {fmtGap(gap)}</span>}
              <button className="sp-linkbtn" onClick={() => select({ kind: "scan", scanId: s.scan_event_id })}>
                <span className="sp-num">{fmtTime(s.time, false)}</span> {describeScan(s).title}
                <span className="sp-caption"> · {s.station_id ?? s.device_id}{s.synced ? "" : " · device time"}{s.late_upload ? " · uploaded late" : ""}</span>
              </button>
            </li>
          );
        })}
      </ol>
      {scans.length > 6 && <button className="sp-btn sp-btn-sm sp-btn-ghost" onClick={() => setAll(!all)}>
        {all ? "Show the last 6" : `Show all ${scans.length}`}</button>}
    </section>
  );
}

function fmtGap(s: number): string {
  if (s < 3600) return `${Math.round(s / 60)} min`;
  const h = Math.floor(s / 3600);
  return `${h} h ${Math.round((s - h * 3600) / 60)} min`;
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

    </div>
  );
}
