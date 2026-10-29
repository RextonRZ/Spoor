"use client";
/**
 * Evidence graph (PRD §19.2 #6): sources -> evidence -> hypotheses -> findings, with counter-evidence. Built only
 * from stored records; an empty column says why it is empty instead of being filled with placeholders.
 */
import { describeScan } from "@/lib/scans";
import Link from "next/link";
import { Fragment, use, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useResource } from "@/lib/api";
import { camId } from "@/lib/hub";
import { fmtTime, TZ_LABEL } from "@/lib/time";
import type { CaseState, MediaRow, ParcelLookup, Replay, ScanRow } from "@/lib/types";
import { ErrorState, Loading, SimulatedChip } from "@/components/ui";

type Col = "source" | "evidence" | "hypothesis" | "finding";
interface GNode {
  id: string;
  col: Col;
  title: string;
  sub: string;
  tone: "scan" | "observed" | "hypothesis" | "finding" | "source" | "contradicted";
  detail: [string, string][];
}
interface GEdge { from: string; to: string; kind: "supports" | "against" | "derived" }

const COLS: { k: Col; label: string; empty: string }[] = [
  { k: "source", label: "Sources", empty: "No source recorded." },
  { k: "evidence", label: "Evidence", empty: "No scan or observation for this parcel." },
  { k: "hypothesis", label: "Hypotheses", empty: "None proposed. Hypotheses come from the agents (language model off) or a reviewer." },
  { k: "finding", label: "Findings", empty: "None verified. A finding needs at least one verified observation of the parcel in footage." },
];

export default function GraphPage({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = use(params);
  const state = useResource<CaseState>(`/v1/cases/${caseId}/state`);
  const siteId = state.data?.case.site_id;
  const ident = state.data?.objects[0]?.object.identifiers?.[0];
  const parcel = useResource<ParcelLookup>(siteId && ident ? `/v1/sites/${siteId}/parcels/${ident.scheme}/${ident.value}` : null);
  const replay = useResource<Replay>(`/v1/cases/${caseId}/replay`);
  const media = useResource<MediaRow[]>(siteId ? `/v1/sites/${siteId}/media` : null);
  const scans = useResource<{ scans: ScanRow[] }>(siteId ? `/v1/sites/${siteId}/scans?limit=20000` : null);
  const [sel, setSel] = useState<string | null>(null);

  const { nodes, edges } = useMemo(() => {
    const nodes: GNode[] = [];
    const edges: GEdge[] = [];
    if (!state.data) return { nodes, edges };
    const batchOf = new Map((scans.data?.scans ?? []).map((s) => [s.scan_event_id, s.import_batch]));
    const batches = new Set<string>();
    for (const s of parcel.data?.scans ?? []) {
      const b = batchOf.get(s.scan_event_id) ?? "scan log";
      batches.add(b);
      nodes.push({ id: s.scan_event_id, col: "evidence", tone: "scan", title: describeScan(s).title,
        sub: `${s.device_id} · ${fmtTime(s.time)}`, detail: [["Kind", describeScan(s).card], ["Proves", describeScan(s).proves], ["Device", s.device_id],
          ["Time", `${fmtTime(s.time)} ${TZ_LABEL}`], ["Clock", s.synced ? "synchronized" : "device time, not synchronized"],
          ["Source", s.source_type], ["ID", s.scan_event_id]] });
      edges.push({ from: `batch:${b}`, to: s.scan_event_id, kind: "derived" });
    }
    batches.forEach((b) => nodes.push({ id: `batch:${b}`, col: "source", tone: "source", title: "Scan log import",
      sub: `${b} · simulated`, detail: [["Batch", b], ["Label", "scan_simulated, end to end"]] }));
    const obsToTrack = new Map<string, string>();
    const usedMedia = new Set<string>();
    for (const o of replay.data?.objects ?? []) {
      for (const seg of o.segments) {
        seg.points.forEach((p) => obsToTrack.set(p.observation_id, seg.track_id));
        nodes.push({ id: seg.track_id, col: "evidence", tone: "observed", title: `Track on ${camId.toHub(seg.camera_id)}`,
          sub: `${seg.points.length} observations · ${fmtTime(seg.start)}`, detail: [["Kind", "observed, one camera track"],
            ["Camera", camId.toHub(seg.camera_id)], ["From", fmtTime(seg.start)], ["To", fmtTime(seg.end)]] });
        edges.push({ from: `cam:${seg.camera_id}`, to: seg.track_id, kind: "derived" });
        usedMedia.add(seg.camera_id);
      }
    }
    for (const m of media.data ?? []) {
      if (!m.media.camera_id) continue;
      nodes.push({ id: `cam:${m.media.camera_id}`, col: "source", tone: "source", title: `Footage ${camId.toHub(m.media.camera_id)}`,
        sub: `${m.recording_kind.replace("_", " ")} · ${m.media.sha256.slice(0, 10)}…`, detail: [["Media", m.media.media_id],
          ["SHA-256", m.media.sha256], ["Kind", m.recording_kind], ["Analysed", usedMedia.has(m.media.camera_id) ? "yes" : "not yet"]] });
    }
    const target = (oid: string) => obsToTrack.get(oid) ?? oid;
    for (const h of state.data.hypotheses) {
      nodes.push({ id: h.hypothesis_id, col: "hypothesis", tone: h.status === "contradicted" ? "contradicted" : "hypothesis",
        title: h.claim, sub: `status: ${h.status}`, detail: [["Status", h.status ?? "proposed"], ["Missing", (h.missing_evidence ?? []).join("; ") || "none listed"],
          ["History", h.history.map((x) => `${x.from_status}→${x.to_status} by ${x.actor.kind}`).join(", ") || "none"]] });
      (h.support_observation_ids ?? []).forEach((o) => edges.push({ from: target(o), to: h.hypothesis_id, kind: "supports" }));
      (h.against_observation_ids ?? []).forEach((o) => edges.push({ from: target(o), to: h.hypothesis_id, kind: "against" }));
    }
    for (const f of state.data.findings) {
      nodes.push({ id: f.finding_id, col: "finding", tone: f.invalidated ? "contradicted" : "finding", title: f.statement,
        sub: `${f.verification_status}${f.invalidated ? " · invalidated" : ""}`, detail: [["Status", f.verification_status],
          ["Verified by", f.verified_by.kind], ["Limitations", (f.limitations ?? []).join("; ") || "none listed"]] });
      f.observation_ids.forEach((o) => edges.push({ from: target(o), to: f.finding_id, kind: "supports" }));
    }
    const ids = new Set(nodes.map((n) => n.id));
    return { nodes, edges: edges.filter((e) => ids.has(e.from) && ids.has(e.to)) };
  }, [state.data, parcel.data, replay.data, media.data, scans.data]);

  const wrap = useRef<HTMLDivElement>(null);
  const [paths, setPaths] = useState<{ d: string; kind: GEdge["kind"]; key: string }[]>([]);
  useLayoutEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const draw = () => {
      const box = el.getBoundingClientRect();
      const pos = (id: string) => el.querySelector<HTMLElement>(`[data-node="${CSS.escape(id)}"]`)?.getBoundingClientRect();
      setPaths(edges.flatMap((e) => {
        const a = pos(e.from);
        const b = pos(e.to);
        if (!a || !b || a.width === 0 || b.width === 0 || Math.abs(a.left - b.left) < 20) return [];
        const x1 = a.right - box.left; const y1 = a.top + a.height / 2 - box.top;
        const x2 = b.left - box.left; const y2 = b.top + b.height / 2 - box.top;
        const mx = (x1 + x2) / 2;
        return [{ d: `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`, kind: e.kind, key: `${e.from}>${e.to}` }];
      }));
    };
    draw();
    const ro = new ResizeObserver(draw);
    ro.observe(el);
    return () => ro.disconnect();
  }, [edges, nodes]);

  const selected = nodes.find((n) => n.id === sel);
  const linked = (id: string) => edges.filter((e) => e.from === id || e.to === id);

  return (
    <div className="sp-page sp-stack" style={{ gap: 18, maxWidth: "100rem" }}>
      <header className="sp-row sp-wrap" style={{ justifyContent: "space-between", gap: 12 }}>
        <div>
          <p className="sp-eyebrow">Evidence graph</p>
          <h1 className="sp-h1" style={{ fontSize: 26 }}>{state.data?.case.question ?? "Loading case"}</h1>
          <p className="sp-caption">Observations and scans on the left support or contradict hypotheses and findings on the right.</p>
        </div>
        <div className="sp-row sp-wrap" style={{ gap: 14, fontSize: 12 }}>
          <span className="sp-row"><span className="sp-swatch" style={{ borderTopColor: "#c6ccd2" }} /> derived from</span>
          <span className="sp-row"><span className="sp-swatch" style={{ borderTopColor: "var(--ev-observed)" }} /> supports</span>
          <span className="sp-row"><span className="sp-swatch" style={{ borderTop: "3px dashed var(--ev-contradicted)" }} /> counter-evidence</span>
          <Link className="sp-btn sp-btn-sm" href={`/cases/${caseId}`}>Open workspace</Link>
        </div>
      </header>
      {state.loading && <Loading label="Loading graph" lines={6} />}
      {state.error && <ErrorState error={state.error} what="the case" onRetry={state.reload} />}
      {state.data && (
        <div className="sp-graph-layout">
          <div ref={wrap} className="sp-graph" role="list" aria-label="Evidence chain">
            <svg className="sp-graph-edges" aria-hidden>
              {paths.map((p) => (
                <path key={p.key} d={p.d} fill="none" strokeWidth={1.5}
                  stroke={p.kind === "against" ? "var(--ev-contradicted)" : p.kind === "supports" ? "var(--ev-observed)" : "#6b737b"}
                  strokeDasharray={p.kind === "against" ? "5 4" : undefined} opacity={sel && !p.key.includes(sel) ? 0.25 : 0.9} />
              ))}
            </svg>
            {COLS.map((c) => {
              const col = nodes.filter((n) => n.col === c.k);
              return (
                <section key={c.k} className="sp-graph-col" role="listitem" aria-label={c.label}>
                  <p className="sp-micro">{c.label} · {col.length}</p>
                  {col.length === 0 && <div className="sp-state" style={{ fontSize: 12.5 }}>{c.empty}</div>}
                  {col.map((n) => (
                    <button key={n.id} data-node={n.id} data-tone={n.tone} className="sp-gnode" aria-pressed={sel === n.id}
                      onClick={() => setSel(sel === n.id ? null : n.id)}>
                      <span className="sp-gnode-title">{n.title}</span>
                      <span className="sp-gnode-sub">{n.sub}</span>
                    </button>
                  ))}
                </section>
              );
            })}
          </div>
          <aside className="sp-panel" aria-label="Selected node" style={{ alignSelf: "start" }}>
            <div className="sp-panel-head"><span className="sp-h3">Details</span>
              {selected?.tone === "scan" && <SimulatedChip kind="scan_simulated" />}</div>
            <div className="sp-panel-body sp-stack">
              {!selected && <p className="sp-muted" style={{ margin: 0 }}>Select a node to see its record and links.</p>}
              {selected && (
                <>
                  <span className="sp-strong" style={{ fontWeight: 600 }}>{selected.title}</span>
                  <dl className="sp-kv">{selected.detail.map(([k, v]) => <Fragment key={k}><dt>{k}</dt><dd>{v}</dd></Fragment>)}</dl>
                  <p className="sp-micro">Links</p>
                  <ul className="sp-list" style={{ fontSize: 12.5 }}>
                    {linked(selected.id).map((e) => {
                      const other = nodes.find((n) => n.id === (e.from === selected.id ? e.to : e.from));
                      return <li key={`${e.from}${e.to}`}>{e.kind === "derived" ? "derived" : e.kind}: {other?.title}</li>;
                    })}
                    {linked(selected.id).length === 0 && <li className="sp-muted">No links.</li>}
                  </ul>
                </>
              )}
              {state.data.evidence_requests.length > 0 && (
                <>
                  <hr className="sp-divider" />
                  <p className="sp-micro">Open evidence requests</p>
                  <ul className="sp-list" style={{ fontSize: 12.5 }}>
                    {state.data.evidence_requests.map((r) => <li key={r.evidence_request_id}>{r.reason}</li>)}
                  </ul>
                </>
              )}
            </div>
          </aside>
        </div>
      )}
      <style>{`
        .sp-graph-layout{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:16px}
        .sp-graph{position:relative;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:56px;padding:4px}
        .sp-graph-edges{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;overflow:visible}
        .sp-graph-col{display:flex;flex-direction:column;gap:10px;position:relative}
        .sp-gnode{position:relative;text-align:left;display:flex;flex-direction:column;gap:2px;padding:10px 12px;border-radius:10px;
          border:1px solid var(--hairline-strong);background:var(--surface);cursor:pointer;border-left-width:3px}
        .sp-gnode[data-tone=scan]{border-left-color:var(--ev-scan);border-left-style:double}
        .sp-gnode[data-tone=observed]{border-left-color:var(--ev-observed)}
        .sp-gnode[data-tone=hypothesis]{border-left-color:var(--ev-hypothesis);border-left-style:dashed}
        .sp-gnode[data-tone=contradicted]{border-left-color:var(--ev-contradicted)}
        .sp-gnode[data-tone=finding]{border-left-color:var(--ev-observed);background:var(--surface-2)}
        .sp-gnode[data-tone=source]{border-left-color:#6b737b}
        .sp-gnode[aria-pressed=true]{outline:2px solid var(--accent);outline-offset:1px}
        .sp-gnode-title{font-weight:600;color:var(--ink-strong);font-size:13px}
        .sp-gnode-sub{font-size:11.5px;color:var(--ink-muted)}
        @media (max-width: 1000px){.sp-graph-layout{grid-template-columns:1fr}.sp-graph{grid-template-columns:1fr;gap:18px}.sp-graph-edges{display:none}}
      `}</style>
    </div>
  );
}
