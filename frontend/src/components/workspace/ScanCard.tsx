"use client";
/**
 * Scan card (QUEUE H13, scan_moment_0115): when the playhead reaches one of the parcel's scans, a card shows what the
 * scan record says: "✓ Label read at the scan tunnel · CTX… · 4.2 kg · 40×30×25 cm · → chute C04 · 14:32:07.9 MYT
 * (scanner clock, not synchronized)". Source = the scan log record (its id), not the video; one click opens the frame of
 * a camera watching that read point at that moment (where a stack light would flash).
 */
import { scanPoint, camId } from "@/lib/hub";
import { describeScan } from "@/lib/scans";
import { clock, type JourneyScan } from "@/lib/journey";
import { useWorkspace } from "./context";

export function activeScan(scans: JourneyScan[] | undefined, t: number | null): JourneyScan | null {
  if (!scans || t === null) return null;
  return scans.find((s) => { const d = t - Date.parse(s.t); return d >= -300 && d <= 2500; }) ?? null;
}

export default function ScanCard() {
  const { journey, playhead, select, cameras } = useWorkspace();
  const j = journey.data?.objects[0];
  const s = activeScan(j?.scans, playhead);
  if (!s) return null;
  const waybill = j?.identity_keys.find((k) => k.startsWith("carrier_waybill:"))?.split(":")[1];
  const ok = (s.read_outcome ?? "read") === "read";
  const kg = s.weight_g ? `${(s.weight_g / 1000).toFixed(1)} kg` : null;
  const size = s.dims_mm ? `${s.dims_mm.map((d) => Math.round(d / 10)).join("×")} cm` : null;
  const dest = s.sort_destination_actual ? `→ chute ${s.sort_destination_actual}` : null;
  const clk = s.clock.synchronized ? `clock synchronized ±${Math.round(s.clock.uncertainty_ms ?? 0)} ms` : "scanner clock, not synchronized";
  const viewer = scanPoint(s.station_id ?? s.device_id)?.visible_by.map(camId.toBackend)
    .find((c) => cameras.data?.find((r) => r.camera.camera_id === c)?.coverage.some((cv) => Date.parse(cv.start_utc) <= Date.parse(s.t) && Date.parse(s.t) <= Date.parse(cv.end_utc)));
  return (
    <div className="sc" data-ok={ok} role="status" aria-live="polite" data-testid="scan-card">
      <p className="sc-title"><span aria-hidden>{ok ? "✓" : "✕"}</span> {describeScan(s).title.replace(/^./, (c) => c.toUpperCase())}</p>
      <p className="sc-facts sp-num">{[waybill, kg, size, dest].filter(Boolean).join(" · ")}</p>
      <p className="sc-meta">{clock(s.t, true)} ({clk}) · source: scan record {s.scan_event_id.slice(-8)} · {s.source_type ?? "scan log"}</p>
      {viewer && <button className="sp-btn sp-btn-sm" onClick={() => select({ kind: "camera", cameraId: viewer, time: Date.parse(s.t) })}>
        See {camId.toHub(viewer)} at this moment</button>}
    </div>
  );
}
