"use client";
/**
 * Synchronized source panel (PRD §19.2 #5): the exact original frame behind any event, with an annotated-derivative
 * toggle when a model observation exists. Context frames (what a camera showed at a scan time) are labelled as
 * context, never as observations of the parcel.
 */
import { describeScan, HUB_FLOW } from "@/lib/scans";
import { useEffect, useState } from "react";
import { api, signedUrl, useResource } from "@/lib/api";
import { camId, hubCamera, scanPoint } from "@/lib/hub";
import { fmtDuration, fmtTime, fmtUncertainty, toMs, TZ_LABEL } from "@/lib/time";
import type { CameraRow, EvidenceView, FrameAt, MediaRow, ParcelScan, ScanRow } from "@/lib/types";
import { Empty, ErrorState, Loading, ModeChip, SimulatedChip, Unavailable } from "@/components/ui";
import { useWorkspace } from "./context";

export default function SourcePanel() {
  const { selection } = useWorkspace();
  if (!selection) {
    return (
      <Empty title="Nothing selected">
        Choose a scan on the timeline or in the scene, a camera lane, or a trace segment. Its source opens here.
      </Empty>
    );
  }
  if (selection.kind === "scan") return <ScanSource scanId={selection.scanId} />;
  if (selection.kind === "observation") return <ObservationSource id={selection.observationId} />;
  if (selection.kind === "camera") return <CameraSource cameraId={selection.cameraId} time={selection.time} />;
  return (
    <div className="sp-stack">
      <div className="sp-row"><span className="sp-swatch" style={{ borderTop: "3px dotted var(--ev-unknown)" }} />
        <span className="sp-h3">Unknown interval</span></div>
      <p className="sp-body" style={{ margin: 0 }}>{fmtTime(selection.start)} to {fmtTime(selection.end)} {TZ_LABEL}
        ({fmtDuration(toMs(selection.end) - toMs(selection.start))}). The parcel was not observed, so no path is drawn.</p>
      <p className="sp-caption">Reason recorded by the backend: {selection.reason}</p>
    </div>
  );
}

function findScan(id: string, a?: ParcelScan[], b?: ScanRow[]): (ParcelScan | ScanRow) | undefined {
  return a?.find((s) => s.scan_event_id === id) ?? b?.find((s) => s.scan_event_id === id);
}

function ScanSource({ scanId }: { scanId: string }) {
  const { parcel, siteScans, cameras, media, lastSeen } = useWorkspace();
  const scan = findScan(scanId, parcel.data?.scans, siteScans.data?.scans);
  if (!scan) return <Loading label="Loading scan" />;
  const sp = scanPoint(scan.station_id ?? scan.device_id);
  const isLast = lastSeen.data?.[0]?.last_confident?.evidence_id === scanId;
  const t = toMs(scan.time);
  const viewers = (sp?.visible_by ?? []).map((h) => ({
    hub: h,
    row: cameras.data?.find((c) => c.camera.camera_id === camId.toBackend(h)),
  }));
  return (
    <div className="sp-stack">
      <div className="sp-row sp-wrap" style={{ gap: 6 }}>
        <span className="sp-swatch" style={{ borderTop: "3px double var(--ev-scan)" }} aria-hidden />
        <span className="sp-h3">{describeScan(scan).title}</span>
        {isLast && <span className="sp-chip" style={{ background: "#f3f5f7", color: "#111" }}>last confirmed</span>}
        {scan.source_type === "scan_simulated" && <SimulatedChip kind="scan_simulated" />}
      </div>
      <dl className="sp-kv">
        <dt>Time</dt><dd className="sp-num">{fmtTime(scan.time)} {TZ_LABEL}</dd>
        <dt>Clock</dt><dd>{scan.synced ? fmtUncertainty(scan.time_uncertainty_ms) : "device time; scanner clock not synchronized"}</dd>
        <dt>Read point</dt><dd>{sp ? `${sp.id} (${sp.device_kind.replace("_", " ")})` : scan.device_id}</dd>
        <dt>Zone</dt><dd>{scan.zone_id ?? "not recorded"}</dd>
        <dt>Proves</dt><dd>{describeScan(scan).proves}</dd>
        <dt>Hub flow</dt><dd className="sp-muted">{HUB_FLOW}</dd>
      </dl>
      <hr className="sp-divider" />
      <p className="sp-micro">Cameras that see this read point</p>
      {viewers.length === 0 && <p className="sp-muted">No camera in the mounting plan covers this read point.</p>}
      {viewers.map((v) => <ContextFrame key={v.hub} hubId={v.hub} row={v.row} media={media.data} t={t} />)}
    </div>
  );
}

function coverageMedia(row: CameraRow | undefined, t: number) {
  return row?.coverage.find((c) => toMs(c.start_utc) <= t && t <= toMs(c.end_utc));
}

function ContextFrame({ hubId, row, media, t }: { hubId: string; row?: CameraRow; media?: MediaRow[]; t: number }) {
  const cov = coverageMedia(row, t);
  const cam = hubCamera(hubId);
  if (!row || !cov?.media_id) {
    return (
      <div className="sp-card sp-card-tight">
        <span className="sp-strong">{hubId}</span> <span className="sp-muted">{cam?.osd_label}</span>
        <p className="sp-caption">No footage imported for this time. Request this camera&apos;s interval in Operator.</p>
      </div>
    );
  }
  const m = media?.find((x) => x.media.media_id === cov.media_id);
  return <FrameViewer key={`${cov.media_id}@${t}`} mediaId={cov.media_id} time={t} title={`${hubId} · ${cam?.osd_label ?? ""}`} recordingKind={m?.recording_kind}
    sha={m?.media.sha256} context />;
}

function CameraSource({ cameraId, time }: { cameraId: string; time: number }) {
  const { cameras, media } = useWorkspace();
  const row = cameras.data?.find((c) => c.camera.camera_id === cameraId);
  const cov = coverageMedia(row, time);
  const hub = camId.toHub(cameraId);
  if (!cov?.media_id) return <Empty title={`${hub}: no footage at ${fmtTime(time)}`} />;
  const m = media.data?.find((x) => x.media.media_id === cov.media_id);
  return <FrameViewer key={`${cov.media_id}@${time}`} mediaId={cov.media_id} time={time} title={`${hub} · ${hubCamera(hub)?.osd_label ?? ""}`}
    recordingKind={m?.recording_kind} sha={m?.media.sha256} context />;
}

/** One original frame at a normalized time, with frame stepping. */
function FrameViewer({ mediaId, time, title, recordingKind, sha, context }: { mediaId: string; time: number; title: string;
  recordingKind?: string; sha?: string; context?: boolean }) {
  const iso = new Date(time).toISOString();
  const at = useResource<FrameAt>(`/v1/media/${mediaId}/frame-at?time=${encodeURIComponent(iso)}`);
  const [offset, setOffset] = useState(0);
  const [stepped, setStepped] = useState<{ idx: number; url: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const idx = at.data ? Math.max(0, Math.min(at.data.frame_count - 1, at.data.frame_index + offset)) : null;
  const fresh = at.data && idx === at.data.frame_index ? at.data.frame_url : stepped && stepped.idx === idx ? stepped.url : null;
  const [lastUrl, setLastUrl] = useState<string | null>(null);
  if (fresh && fresh !== lastUrl) setLastUrl(fresh);
  const url = fresh ?? lastUrl;
  useEffect(() => {
    if (!at.data || idx === null || idx === at.data.frame_index) return;
    let live = true;
    api<{ url: string }>(`/v1/media/${mediaId}/frames/${idx}/link`).then((r) => live && setStepped({ idx, url: r.url }))
      .catch((e) => live && setErr(String(e.message ?? e)));
    return () => { live = false; };
  }, [at.data, idx, mediaId]);
  return (
    <div className="sp-frame">
      <div className="sp-row" style={{ justifyContent: "space-between" }}>
        <span className="sp-strong" style={{ fontWeight: 600 }}>{title}</span>
        <span className="sp-chip">original</span>
      </div>
      {at.loading && <div className="sp-skel" style={{ aspectRatio: "16 / 9" }} />}
      {at.error && <ErrorState error={at.error} what="the frame" onRetry={at.reload} />}
      {url && <FrameImage src={signedUrl(url)} alt={`${title}, frame ${idx}`} onExpired={() => at.reload()} />}
      {err && <p className="sp-caption" role="alert">{err}</p>}
      {at.data && idx !== null && (
        <>
          <div className="sp-row sp-wrap" style={{ gap: 6 }}>
            <button className="sp-btn sp-btn-sm" onClick={() => setOffset((o) => o - 1)} disabled={idx <= 0} aria-label="Previous frame">◀ frame</button>
            <span className="sp-num" style={{ fontSize: 12 }}>frame {idx} / {at.data.frame_count - 1}</span>
            <button className="sp-btn sp-btn-sm" onClick={() => setOffset((o) => o + 1)} disabled={idx >= at.data.frame_count - 1} aria-label="Next frame">frame ▶</button>
          </div>
          <dl className="sp-kv">
            <dt>Media</dt><dd className="sp-mono">{mediaId}</dd>
            {sha && <><dt>SHA-256</dt><dd className="sp-mono">{sha.slice(0, 16)}…</dd></>}
            <dt>Footage</dt><dd>{recordingKind === "synthetic_test" ? "synthetic test footage (SYNTHETIC mark burned in)" : recordingKind ?? "unknown"}</dd>
            <dt>Clock</dt><dd>{fmtUncertainty(at.data.time_uncertainty_ms)} on this clip&apos;s start time</dd>
          </dl>
          {context && (
            <p className="sp-caption">Context frame at the selected time. Not an observation: nothing has been detected in it.
              Annotated derivative: none.</p>
          )}
        </>
      )}
    </div>
  );
}

function FrameImage({ src, alt, onExpired }: { src: string; alt: string; onExpired: () => void }) {
  const [st, setSt] = useState<{ src: string; s: "ok" | "error" } | null>(null);
  const state = st && st.src === src ? st.s : "loading";
  const setState = (s: "ok" | "error") => setSt({ src, s });
  const [lastOk, setLastOk] = useState<string | null>(null);
  const [retried, setRetried] = useState(false);
  // While the next frame loads, the previous frame stays visible (dimmed) instead of a black box (review 004 #7).
  const showPrev = state === "loading" && lastOk && lastOk !== src;
  return (
    <div className="sp-frame-img" data-state={state}>
      {showPrev && (
        // eslint-disable-next-line @next/next/no-img-element -- previous evidence frame kept while the next loads
        <img src={lastOk!} alt="" aria-hidden style={{ position: "absolute", inset: 0, opacity: 0.45 }} />
      )}
      {/* eslint-disable-next-line @next/next/no-img-element -- signed, short-lived evidence frames: no optimizer cache */}
      <img src={src} alt={alt} decoding="async" style={{ position: "relative", opacity: state === "ok" ? 1 : 0 }}
        onLoad={() => { setState("ok"); setLastOk(src); }}
        onError={() => { if (!retried) { setRetried(true); onExpired(); } else setState("error"); }} />
      {state === "loading" && !showPrev && <div className="sp-skel" style={{ position: "absolute", inset: 0 }} aria-hidden />}
      {state === "loading" && <span className="sp-frame-loading" role="status">Loading frame</span>}
      {state === "error" && <div className="sp-state sp-state-error" role="alert" style={{ position: "absolute", inset: 8 }}>
        Frame could not be loaded. The link may have expired.</div>}
    </div>
  );
}

function ObservationSource({ id }: { id: string }) {
  const { caseId, caps } = useWorkspace();
  const ev = useResource<EvidenceView>(`/v1/cases/${caseId}/evidence/${id}`);
  const [annotated, setAnnotated] = useState(false);
  if (ev.loading) return <Loading label="Loading evidence" />;
  if (ev.error) return <ErrorState error={ev.error} what="this evidence" onRetry={ev.reload} />;
  const e = ev.data!;
  const o = e.observation;
  return (
    <div className="sp-stack">
      <div className="sp-row sp-wrap" style={{ gap: 6 }}>
        <span className="sp-swatch" style={{ borderTop: "3px solid var(--ev-observed)" }} aria-hidden />
        <span className="sp-h3">Observed · {o.label}</span>
        {e.invalidated && <span className="sp-chip sp-chip-alert">invalidated</span>}
        {e.estimate && <ModeChip mode={e.estimate.spatial_mode} />}
      </div>
      <div className="sp-seg" role="tablist" aria-label="Frame version">
        <button role="tab" aria-selected={!annotated} onClick={() => setAnnotated(false)}>Original</button>
        <button role="tab" aria-selected={annotated} onClick={() => setAnnotated(true)}>Annotated derivative</button>
      </div>
      <FrameImage key={annotated ? "a" : "o"} src={signedUrl(annotated ? e.annotated_frame_url : e.frame_url)}
        alt={annotated ? "Annotated derivative of the source frame" : "Original source frame"} onExpired={() => ev.reload()} />
      <dl className="sp-kv">
        <dt>Camera</dt><dd>{camId.toHub(o.camera_id)}</dd>
        <dt>Frame</dt><dd className="sp-num">{o.source_frame?.frame_index} · pts {o.source_frame?.pts_ms} ms</dd>
        <dt>Time</dt><dd className="sp-num">{fmtTime(o.source_frame?.normalized_utc ?? null)} {TZ_LABEL} ({fmtUncertainty(o.source_frame?.time_uncertainty_ms)})</dd>
        <dt>Media</dt><dd className="sp-mono">{e.media.media_id} · {e.media.sha256.slice(0, 12)}…</dd>
        <dt>Source</dt><dd>{o.provenance ? `${o.provenance.provider} ${o.provenance.model} ${o.provenance.model_version}` : o.source_type}</dd>
        {e.estimate && <><dt>Position</dt><dd>{e.estimate.floor_xy_m ? `${e.estimate.floor_xy_m.map((v) => v.toFixed(2)).join(", ")} m ± ${e.estimate.uncertainty_radius_m?.toFixed(2)} m` : e.estimate.zone_id ?? "unknown"}</dd></>}
        <dt>Confidence</dt><dd>{o.confidence_calibrated !== null ? o.confidence_calibrated : "not calibrated: shown as unverified"}</dd>
      </dl>
      {!caps.data?.spark && <Unavailable title="Evidence agent: analysis unavailable">No language-model key, so no agent
        message accompanies this frame. The frame and its provenance above are the evidence.</Unavailable>}
    </div>
  );
}
