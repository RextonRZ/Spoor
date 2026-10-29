"use client";
/**
 * One canonical timeline (PRD §19.2 #3): normalized time, every lane carrying its own clock trust. Camera lanes show
 * coverage with their sync uncertainty as hatched ends; unverified clocks are flagged, never silently trusted.
 */
import { describeScan } from "@/lib/scans";
import { useEffect, useMemo, useRef, useState } from "react";
import { camId, scanPoint } from "@/lib/hub";
import { fmtDuration, fmtTime, toMs, TZ_LABEL } from "@/lib/time";
import { Icon, Loading } from "@/components/ui";
import { clockWarning, useWorkspace } from "./context";

export default function Timeline() {
  const ws = useWorkspace();
  const { range, playhead, setPlayhead, parcel, siteScans, cameras, replay, state, select, selection, domains, sensors } = ws;
  const span = range ? range.end - range.start : 1;
  const pct = (t: number) => `${(((t - (range?.start ?? 0)) / span) * 100).toFixed(3)}%`;
  const caseKeys = new Set((state.data?.objects[0]?.object.identifiers ?? []).map((i) => `${i.scheme}:${i.value}`));

  const axisRef = useRef<HTMLDivElement>(null);
  const [axisW, setAxisW] = useState(800);
  useEffect(() => {
    const el = axisRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setAxisW(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, [range]);
  const ticks = useMemo(() => {
    if (!range) return [];
    const maxTicks = Math.max(2, Math.floor(axisW / 78));
    const steps = [1000, 2000, 5000, 10000, 15000, 30000, 60000, 120000, 300000, 600000];
    const step = steps.find((s) => span / s <= maxTicks) ?? 600000;
    const out: number[] = [];
    for (let t = Math.ceil(range.start / step) * step; t <= range.end; t += step) out.push(t);
    return out;
  }, [range, span, axisW]);

  const camLanes = (cameras.data ?? []).filter((c) => c.coverage.length > 0);
  const scanDomain = domains.data?.find((d) => d.domain.name === "clkd_wcs");
  const gaps = replay.data?.objects[0]?.gaps ?? [];
  const spans = state.data?.objects[0]?.timeline ?? [];
  const warnings: string[] = [];
  camLanes.forEach((c) => {
    const w = clockWarning(c.clock_sync);
    if (w) warnings.push(`${camId.toHub(c.camera.camera_id)}: ${w}`);
  });
  if (scanDomain && !scanDomain.sync) warnings.push("Sorter and scanner clock (WCS): not synchronized, scan times are device times");

  if (!range) {
    return <div className="sp-panel-body">{state.loading || media(ws) ? <Loading label="Loading timeline" lines={2} />
      : <p className="sp-muted">Nothing to place on the timeline yet: no footage with a start time and no scans.</p>}</div>;
  }

  function onKey(e: React.KeyboardEvent) {
    if (!range || playhead === null) return;
    const step = e.shiftKey ? 10000 : 1000;
    if (e.key === "ArrowRight") setPlayhead(Math.min(range.end, playhead + step));
    else if (e.key === "ArrowLeft") setPlayhead(Math.max(range.start, playhead - step));
    else if (e.key === "Home") setPlayhead(range.start);
    else if (e.key === "End") setPlayhead(range.end);
    else return;
    e.preventDefault();
  }

  return (
    <div className="sp-tl">
      <div className="sp-tl-head">
        <span className="sp-micro">Timeline · {TZ_LABEL}</span>
        <span className="sp-num sp-strong" aria-live="polite">{playhead !== null ? fmtTime(playhead) : ""}</span>
        <input type="range" className="sp-tl-range" min={range.start} max={range.end} step={100}
          value={playhead ?? range.start} onChange={(e) => setPlayhead(Number(e.target.value))} onKeyDown={onKey}
          aria-label="Time scrubber. Arrow keys move one second, Shift plus arrow ten seconds."
          aria-valuetext={playhead !== null ? fmtTime(playhead) : undefined} />
        {warnings.length > 0 && (
          <details className="sp-tl-warn">
            <summary className="sp-chip sp-chip-warn"><Icon.clock /> {warnings.length} clock warning{warnings.length > 1 ? "s" : ""}</summary>
            <ul className="sp-list" style={{ padding: "8px 2px", fontSize: 12 }}>
              {warnings.map((w) => <li key={w}>{w}</li>)}
            </ul>
          </details>
        )}
      </div>
      <div className="sp-tl-grid">
        <div className="sp-tl-label" aria-hidden />
        <div className="sp-tl-axis" aria-hidden ref={axisRef}>
          {ticks.map((t) => <span key={t} style={{ left: pct(t) }}>{fmtTime(t, false)}</span>)}
        </div>

        <div className="sp-tl-label"><span className="sp-strong">Parcel</span><span className="sp-caption">scans · visibility</span></div>
        <div className="sp-tl-lane" role="group" aria-label="Parcel evidence">
          {spans.map((s, i) => (
            <span key={i} className={s.state === "visible" || s.state === "partially_occluded" ? "sp-tl-obs" : "sp-tl-unk"}
              style={{ left: pct(s.start_ms), width: `calc(${pct(s.end_ms)} - ${pct(s.start_ms)})` }}
              title={`${s.state} ${fmtTime(s.start_ms)}–${fmtTime(s.end_ms)}`} />
          ))}
          {gaps.map((g, i) => (
            <button key={`g${i}`} className="sp-tl-gap" style={{ left: pct(toMs(g.start)), width: `calc(${pct(toMs(g.end))} - ${pct(toMs(g.start))})` }}
              aria-label={`Unknown interval ${fmtTime(g.start)} to ${fmtTime(g.end)}: ${g.reason}`}
              onClick={() => select({ kind: "gap", start: g.start, end: g.end, reason: g.reason })} />
          ))}
          {(parcel.data?.scans ?? []).map((s) => {
            const sel = selection?.kind === "scan" && selection.scanId === s.scan_event_id;
            return (
              <button key={s.scan_event_id} className="sp-tl-scan" data-selected={sel || undefined}
                style={{ left: pct(toMs(s.time)) }}
                aria-label={`${describeScan(s).title} at ${fmtTime(s.time)} by ${s.device_id}${s.synced ? "" : ", clock not synchronized"}`}
                title={`${describeScan(s).title} · ${s.device_id} · ${fmtTime(s.time)}`}
                onClick={() => select({ kind: "scan", scanId: s.scan_event_id })}>
                <span aria-hidden />
              </button>
            );
          })}
          {parcel.data && parcel.data.scans.length === 0 && <span className="sp-tl-empty">No scans for this parcel in the log</span>}
        </div>

        <div className="sp-tl-label"><span className="sp-strong">Hub scans</span>
          <span className="sp-caption">{siteScans.data ? `${siteScans.data.total} in range` : "…"} · simulated</span></div>
        <div className="sp-tl-lane sp-tl-lane-thin" aria-hidden>
          {(siteScans.data?.scans ?? []).map((s) => (
            <span key={s.scan_event_id} className="sp-tl-tick" data-case={s.identity_keys.some((k) => caseKeys.has(k)) || undefined}
              data-noread={s.read_outcome !== "read" || undefined} style={{ left: pct(toMs(s.time)) }} />
          ))}
        </div>

        {(sensors.data?.length ?? 0) > 0 && (
          <>
            <div className="sp-tl-label"><span className="sp-strong">Chute photo-eyes</span>
              <span className="sp-caption">no identity · simulated</span></div>
            <div className="sp-tl-lane sp-tl-lane-thin" role="group" aria-label="Chute photo-eye pulses, simulated, no identity">
              {sensors.data!.filter((e) => range && Date.parse(e.device_time_utc) >= range.start && Date.parse(e.device_time_utc) <= range.end)
                .map((e) => (
                  <span key={e.sensor_event_id} className="sp-tl-tick sp-tl-eye" style={{ left: pct(Date.parse(e.device_time_utc)) }}
                    title={`${e.device_id} · ${fmtTime(e.device_time_utc)} · something passed the photo-eye (no identity)`} />
                ))}
            </div>
          </>
        )}
        {camLanes.map((c) => {
          const hubId = camId.toHub(c.camera.camera_id);
          const warn = clockWarning(c.clock_sync);
          const lit = ws.litCameras.includes(hubId);
          return (
            <FragmentLane key={c.camera.camera_id} label={hubId} sub={warn ? "clock unverified" : `± ${fmtDuration(c.clock_sync?.uncertainty_ms ?? 0)}`}
              warn={!!warn} lit={lit}>
              {c.coverage.map((cov) => {
                const s = toMs(cov.start_utc);
                const e = toMs(cov.end_utc);
                const u = cov.time_uncertainty_ms;
                return (
                  <span key={cov.coverage_id ?? cov.start_utc}>
                    <span className="sp-tl-unc" style={{ left: pct(s - u), width: `calc(${pct(s + u)} - ${pct(s - u)})` }} />
                    <span className="sp-tl-unc" style={{ left: pct(e - u), width: `calc(${pct(e + u)} - ${pct(e - u)})` }} />
                    <button className="sp-tl-cov" data-lit={lit || undefined}
                      style={{ left: pct(s), width: `calc(${pct(e)} - ${pct(s)})` }}
                      aria-label={`${hubId} footage ${fmtTime(s)} to ${fmtTime(e)}. Open the frame at the playhead.`}
                      onClick={(ev) => {
                        const rect = (ev.currentTarget as HTMLElement).getBoundingClientRect();
                        const t = ev.clientX && rect.width ? s + ((ev.clientX - rect.left) / rect.width) * (e - s) : (playhead ?? s);
                        select({ kind: "camera", cameraId: c.camera.camera_id, time: Math.max(s, Math.min(e, t)) });
                      }} />
                  </span>
                );
              })}
            </FragmentLane>
          );
        })}
        {playhead !== null && <div className="sp-tl-playhead" style={{ left: `calc(12px + var(--tl-label) + (100% - 24px - var(--tl-label)) * ${(playhead - range.start) / span})` }} aria-hidden />}
      </div>
    </div>
  );
}

function media(ws: ReturnType<typeof useWorkspace>) {
  return ws.media.loading;
}

function FragmentLane({ label, sub, warn, lit, children }: { label: string; sub: string; warn: boolean; lit: boolean;
  children: React.ReactNode }) {
  return (
    <>
      <div className="sp-tl-label">
        <span className="sp-strong" style={{ color: lit ? "#cfc7ff" : undefined }}>{label}</span>
        <span className="sp-caption" style={{ color: warn ? "#fcd34d" : undefined }}>{warn ? "⚠ " : ""}{sub}</span>
      </div>
      <div className="sp-tl-lane sp-tl-lane-thin">{children}</div>
    </>
  );
}

export function scanLabel(kind: string, device: string) {
  const sp = scanPoint(device);
  return `${kind.replace(/_/g, " ")} at ${sp?.id ?? device}`;
}
