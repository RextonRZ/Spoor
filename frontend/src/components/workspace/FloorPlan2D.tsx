"use client";
/** 2D floor-plan fallback (PRD §19.4): same site-plan data and trace contract as the 3D scene, as accessible SVG. */
import { describeScan } from "@/lib/scans";
import { useMemo } from "react";
import { floorFootprint } from "@/lib/frames";
import { HUB, centroid, hubZone, scanPoint } from "@/lib/hub";
import { buildTrace } from "@/lib/trace";
import { routeLink } from "@/lib/topology";
import { fmtTime } from "@/lib/time";
import { clock, markerAt, type JourneyObject } from "@/lib/journey";
import { useWorkspace } from "./context";

// Framed on the building (docks to the outbound wall): the journey happens inside; yards are context only.
const MIN_X = -6;
const MAX_X = 62;
const MIN_Y = -2;
const MAX_Y = 45;
const sx = (x: number) => x - MIN_X;
const sy = (y: number) => MAX_Y - y;
const pts = (poly: [number, number][]) => poly.map(([x, y]) => `${sx(x).toFixed(2)},${sy(y).toFixed(2)}`).join(" ");

export default function FloorPlan2D() {
  const { parcel, replay, litCameras, select, selection, lastSeen, mode, journey, playhead } = useWorkspace();
  const jo = journey.data?.objects[0];
  const traces = useMemo(() => (replay.data?.objects ?? []).map(buildTrace), [replay.data]);
  const [W, H] = HUB.building.footprint_m;
  const loop = HUB.machines.loop;
  const lcId = lastSeen.data?.[0]?.last_confident?.evidence_id;
  const showObject = mode !== "people";
  return (
    <figure className="sp-plan" style={{ margin: 0 }}>
      <svg viewBox={`0 0 ${MAX_X - MIN_X} ${MAX_Y - MIN_Y}`} role="group"
        aria-label="Floor plan of the hub with zones, cameras, scan points and the parcel's evidence"
        style={{ width: "100%", height: "100%", display: "block" }}>
        <rect x={sx(0)} y={sy(H)} width={W} height={H} fill="#15181b" stroke="#9aa4ad" strokeWidth={0.25} />
        {HUB.zones.map((z) => z.polygons.map((p, i) => (
          <polygon key={`${z.id}${i}`} points={pts(p)} fill="rgba(226,232,238,0.04)" stroke="#59616a" strokeWidth={0.12}>
            <title>{`${z.id} ${z.name}`}</title>
          </polygon>
        )))}
        {HUB.zones.map((z) => {
          const [cx, cy] = centroid(z.polygons[0]);
          return <text key={`t${z.id}`} x={sx(cx)} y={sy(cy)} fontSize={1.3} fill="#9aa4ad" textAnchor="middle">{z.id}</text>;
        })}
        <polygon points={pts(HUB.blind_corner.polygon)} fill="rgba(248,113,113,0.08)" stroke="#f87171"
          strokeWidth={0.15} strokeDasharray="0.6 0.4"><title>{`Blind corner: ${HUB.blind_corner.why}`}</title></polygon>
        <rect x={sx(loop.west_cx - loop.radius)} y={sy(loop.north_y)} width={loop.east_cx - loop.west_cx + 2 * loop.radius}
          height={loop.north_y - loop.south_y} rx={loop.radius} fill="none" stroke="#c6ccd2" strokeWidth={0.5} />
        {HUB.machines.conveyors.map((c) => (
          <polyline key={c.id} points={pts(c.path)} fill="none" stroke="#c6ccd2" strokeWidth={0.4} opacity={0.6} />
        ))}
        {HUB.machines.chutes.map((c) => (
          <rect key={c.id} x={sx(c.x - c.width / 2)} y={sy(c.end_y)} width={c.width} height={c.end_y - c.mouth_y}
            fill="#2a2f35" stroke="#59616a" strokeWidth={0.08} />
        ))}
        {HUB.cameras.map((c) => {
          const lit = litCameras.includes(c.id);
          return (
            <g key={c.id}>
              {lit && <polygon points={pts(floorFootprint(c, 40))} fill="rgba(169,155,255,0.12)" stroke="#a99bff" strokeWidth={0.2} />}
              <circle cx={sx(c.position_m[0])} cy={sy(c.position_m[1])} r={0.55} fill={lit ? "#a99bff" : "#9aa4ad"}>
                <title>{`${c.id} ${c.osd_label} (approximate FOV from mounting plan)`}</title>
              </circle>
              {lit && <text x={sx(c.position_m[0]) + 0.9} y={sy(c.position_m[1]) - 0.6} fontSize={1.4} fill="#cfc7ff">{c.id}</text>}
            </g>
          );
        })}
        {HUB.scan_points.map((s) => (
          <rect key={s.id} x={sx(s.position_m[0]) - 0.25} y={sy(s.position_m[1]) - 0.25} width={0.5} height={0.5}
            fill="#59616a"><title>{s.id}</title></rect>
        ))}
        {showObject && jo && <JourneyLayer j={jo} t={playhead} selection={selection} select={select} />}
        {showObject && !jo && traces.map((t, i) => (
          <g key={i}>
            {t.solid.map((r) => (
              <polyline key={r.key} data-ev="observed" data-from={r.points[0].t} data-to={r.points[r.points.length - 1].t}
                points={pts(r.points.map((p) => p.floor_xy_m!))} fill="none" stroke="#4ade80"
                strokeWidth={0.45} role="button" tabIndex={0} style={{ cursor: "pointer" }}
                aria-label={`Observed segment from ${r.cameraId}, open its source frame`}
                onClick={() => select({ kind: "observation", observationId: r.points[0].observation_id })}
                onKeyDown={(e) => e.key === "Enter" && select({ kind: "observation", observationId: r.points[0].observation_id })} />
            ))}
            {t.dashed.map((d) => (
              <polyline key={d.key} data-ev="hypothesis" fill="none" stroke="#fbbf24" strokeWidth={0.35} strokeDasharray="0.8 0.5"
                points={pts(routeLink(HUB.machines.loop, HUB.machines.chutes, d.from.floor_xy_m!, d.to.floor_xy_m!, 1.0, HUB.machines.conveyors).points)}>
                <title>Hypothesis: a possible link, drawn along the conveyance; not observed</title>
              </polyline>
            ))}
          </g>
        ))}
        {showObject && !jo && parcel.data?.scans.map((s) => {
          const sp = scanPoint(s.station_id ?? s.device_id);
          const z = hubZone(s.zone_id);
          const xy = sp ? [sp.position_m[0], sp.position_m[1]] : z ? centroid(z.polygons[0]) : null;
          if (!xy) return null;
          const sel = selection?.kind === "scan" && selection.scanId === s.scan_event_id;
          const label = `${describeScan(s).title} at ${fmtTime(s.time)}`;
          return (
            <g key={s.scan_event_id} role="button" tabIndex={0} aria-label={`Scan: ${label}. Open source.`}
              onClick={() => select({ kind: "scan", scanId: s.scan_event_id })} style={{ cursor: "pointer" }}
              onKeyDown={(e) => e.key === "Enter" && select({ kind: "scan", scanId: s.scan_event_id })}>
              {s.scan_event_id === lcId && <circle cx={sx(xy[0])} cy={sy(xy[1])} r={1.6} fill="none" stroke="#fff" strokeWidth={0.25} />}
              <rect x={sx(xy[0]) - 0.7} y={sy(xy[1]) - 0.7} width={1.4} height={1.4} transform={`rotate(45 ${sx(xy[0])} ${sy(xy[1])})`}
                fill={sel ? "#fff" : "#e2e8f0"} stroke="#0e1012" strokeWidth={0.15} />
              <title>{label}</title>
            </g>
          );
        })}
      </svg>
      <figcaption className="sp-sr">Floor plan in site metres, north up. Camera fields of view are approximate.</figcaption>
    </figure>
  );
}

/**
 * Journey layer (H2): the backend-typed segments only. Green solid = seen on a camera, amber dotted = inferred along
 * the plan's belt route between two scans (not seen), grey hatched halo = where the trail ends (unknown after it).
 * Blue diamonds are scans. The replay marker follows the playhead and says what it rests on.
 */
function JourneyLayer({ j, t, selection, select }: {
  j: JourneyObject; t: number | null;
  selection: ReturnType<typeof useWorkspace>["selection"]; select: ReturnType<typeof useWorkspace>["select"];
}) {
  const m = t !== null ? markerAt(j, t) : null;
  const last = j.last_confirmed?.xy;
  return (
    <g className="jl">
      <defs>
        <pattern id="jl-hatch" width="0.8" height="0.8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="0.8" stroke="#8b909b" strokeWidth="0.22" />
        </pattern>
        <filter id="jl-glow" x="-1" y="-1" width="3" height="3"><feGaussianBlur stdDeviation="0.5" /></filter>
      </defs>
      {last && <g data-ev="unknown">
        <circle cx={sx(last[0])} cy={sy(last[1])} r={2.4} fill="url(#jl-hatch)" stroke="#8b909b" strokeWidth={0.18}
          strokeDasharray="0.5 0.35"><title>Trail ends here. After this point nothing confirms where it went.</title></circle>
      </g>}
      {j.segments.map((sg, i) => sg.kind === "inferred_along_conveyor" ? (
        <polyline key={i} data-ev="inferred" points={pts(sg.path_m)} fill="none" stroke="#fbbf24" strokeWidth={0.5}
          strokeDasharray="0.05 0.85" strokeLinecap="round" strokeLinejoin="round">
          <title>{`Inferred along ${sg.route.join(" → ")}: ${sg.belt_time_s} s at belt speed, recorded ${sg.recorded_gap_s} s (${sg.timing.replace(/_/g, " ")}). Not seen.`}</title>
        </polyline>
      ) : sg.kind === "observed" ? (
        <polyline key={i} data-ev="observed" data-from={sg.start} data-to={sg.end}
          points={pts(sg.points.filter((q) => q.xy).map((q) => q.xy!))} fill="none"
          stroke="#4ade80" strokeWidth={0.55} strokeLinecap="round" role="button" tabIndex={0} style={{ cursor: "pointer" }}
          aria-label={`Seen on ${sg.camera_id}: open its source frame`}
          onClick={() => select({ kind: "observation", observationId: sg.points[0].observation_id })}
          onKeyDown={(e) => e.key === "Enter" && select({ kind: "observation", observationId: sg.points[0].observation_id })} />
      ) : null)}
      {j.scans.filter((s) => s.xy).map((s) => {
        const [x, y] = [sx(s.xy![0]), sy(s.xy![1])];
        const sel = selection?.kind === "scan" && selection.scanId === s.scan_event_id;
        const label = `${describeScan(s).title} at ${clock(s.t, true)}`;
        return (
          <g key={s.scan_event_id} role="button" tabIndex={0} aria-label={`Scan: ${label}. Open source.`} style={{ cursor: "pointer" }}
            onClick={() => select({ kind: "scan", scanId: s.scan_event_id })}
            onKeyDown={(e) => e.key === "Enter" && select({ kind: "scan", scanId: s.scan_event_id })}>
            <rect x={x - 0.75} y={y - 0.75} width={1.5} height={1.5} transform={`rotate(45 ${x} ${y})`}
              fill={sel ? "#bfdbfe" : "#60a5fa"} stroke="#0b0c10" strokeWidth={0.2} />
            <text x={x + 1.3} y={y - 1} fontSize={1.15} fill="#c9ccd3" className="jl-time">{fmtTime(s.t, false)}</text>
            <title>{label}</title>
          </g>
        );
      })}
      {m?.xy && (
        <g data-testid="replay-marker" data-kind={m.kind} pointerEvents="none">
          <circle cx={sx(m.xy[0])} cy={sy(m.xy[1])} r={1.4} fill={m.kind === "observed" ? "#4ade80" : "#fbbf24"}
            opacity={0.45} filter="url(#jl-glow)" />
          <circle cx={sx(m.xy[0])} cy={sy(m.xy[1])} r={0.7} fill="#f4f5f7"
            stroke={m.kind === "observed" ? "#4ade80" : m.kind === "scan" ? "#60a5fa" : "#fbbf24"} strokeWidth={0.3} />
          <title>{m.label}</title>
        </g>
      )}
    </g>
  );
}
