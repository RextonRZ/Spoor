"use client";
/**
 * Hub floor plan in the architectural language of floorplan_design_0300 (reference: review/refs/floorplan_reference.png,
 * ported from its generator): thick walls with real openings and dock numbers, belts as strips with flow chevrons, the
 * sorter as a stadium track with carrier ticks, numbered chutes, human zone names with faint codes, a monochrome base,
 * quiet cameras (indigo only when in play), the blind spot hatched, time chips that never sit on the route, legend,
 * scale bar and north arrow.
 *
 * The SVG is drawn at the panel's real pixel size (px per metre from the measured box), so text stays at true pixel
 * sizes on every screen. Evidence styles: green solid = seen; amber dotted = inferred along a belt; blue diamond = scan;
 * last confirmed = ring (green for a sighting, blue for a scan: no-key mode never draws green); dashed box = where it
 * was expected (red only for a typed negative observation, grey when not analysed); grey hatch = no coverage.
 */
import { useLayoutEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from "react";
import { HUB, centroid } from "@/lib/hub";
import { describeScan } from "@/lib/scans";
import { cam, clock, type JourneyObject, type MarkerAt, type MissingObject } from "@/lib/journey";
import "./hubplan.css";

type XY = [number, number];
// metres: building + yards + a strip for the scale bar; narrow plans zoom to the journey instead (see `frame`)
interface Ext { x0: number; x1: number; y0: number; y1: number }
const FULL: Ext = { x0: -5.5, x1: 61.5, y0: -4.6, y1: 45.6 };

/** On a narrow plan (phone), frame the journey (scans, routes, last point, expected spots) + a margin, not the site. */
function frame(props: PlanProps, w: number): Ext {
  if (props.heat) return { x0: -1.5, x1: 61.5, y0: -1.5, y1: 41.5 }; // the trail-ends map: the building only, readable
  if (props.focus) {
    // a thumbnail around one point (Hub rows: where the parcel stopped)
    const [x, y] = props.focus.xy;
    const r = props.focus.radius_m ?? 9;
    return { x0: x - r * 1.5, x1: x + r * 1.5, y0: y - r, y1: y + r };
  }
  if (w >= 640 || !props.journey) return FULL;
  const pts: XY[] = [];
  props.journey.scans.forEach((s) => s.xy && pts.push(s.xy));
  props.journey.segments.forEach((s) => s.kind === "inferred_along_conveyor" && pts.push(...s.path_m));
  if (props.journey.last_confirmed?.xy) pts.push(props.journey.last_confirmed.xy);
  (props.missing?.expected_next ?? []).forEach((r) => r.result !== "no_footage" && pts.push(r.expected_xy));
  // cameras in play stay in frame, with room for their label
  HUB.cameras.forEach((c) => props.litCameras?.includes(c.id) && pts.push([c.position_m[0], c.position_m[1]]));
  if (pts.length < 2) return FULL;
  const pad = 7;
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  return { x0: Math.max(FULL.x0, Math.min(...xs) - pad), x1: Math.min(FULL.x1, Math.max(...xs) + pad),
    y0: Math.max(FULL.y0, Math.min(...ys) - pad), y1: Math.min(FULL.y1, Math.max(...ys) + pad) };
}
const C = {
  floor: "#16171d", mach: "#23252d", machE: "#363944", wall: "#4b4f5a", inkS: "#f4f5f7", ink: "#c9ccd3",
  inkM: "#8b909b", inkF: "#5a5f69", surf: "#121318", surf2: "#1b1d24", obs: "#4ade80", hyp: "#fbbf24", unk: "#8b909b",
  con: "#f87171", scan: "#60a5fa", acc: "#818cf8",
};
import { ZONE_NAMES } from "@/lib/zones"; // (the short zone names: one list for the app and the landing page)
export { ZONE_NAMES };
// small zones lose their label on small plans (unless they carry a count), so names never collide
const SMALL_ZONES = new Set(["Z02", "Z04", "Z08", "Z09", "Z13", "Z11"]);
export const LABEL_AT: Record<string, XY> = {
  Z01: [0.8, 29.2], Z02: [8.6, 28.2], Z03: [6.2, 6.0], Z04: [17.9, 7.0], Z06: [30.4, 24.0], Z08: [23.4, 24.0],
  Z09: [9.0, 4.4], Z10: [25.6, 31.8], Z11: [15.9, 31.2], Z12: [24.6, 39.2], Z13: [55.0, 5.2],
};

export interface PlanProps {
  journey?: JourneyObject;
  missing?: MissingObject;
  marker?: MarkerAt | null;
  litCameras?: string[]; // hub ids ("CAM_07")
  heat?: Record<string, number>; // hub zone id -> count (dashboard)
  cloud?: { polygons: XY[][]; seconds: number; removed: string[] } | null; // where it could be (computed, H4)
  selectedScanId?: string | null;
  activeScanId?: string | null; // the scan the playhead is on (H13): ringed, and its chip always shown
  onScan?: (scanId: string) => void;
  onObservation?: (observationId: string) => void;
  legend?: boolean;
  /** route only, no time chips (the Hub's trails card) */
  quiet?: boolean;
  /** frame a small box around one point and pin it (Hub row thumbnails); hides the scale bar */
  focus?: { xy: XY; radius_m?: number; tone?: "warn" | "bad" };
  label: string;
  minHeight?: number;
  /** "width": the plan takes the card's full width and its own height (summary, hub); default fits the box. */
  fit?: "width" | "contain";
}

function useBox() {
  const ref = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState({ w: 0, h: 0 });
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setBox({ w: e.contentRect.width, h: e.contentRect.height }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, box] as const;
}

/** A zone label a time chip covers is hidden whole, never left peeking out from under it (review F-039 P2 #1). */
function useChipKnockout(svg: RefObject<SVGSVGElement | null>) {
  useLayoutEffect(() => {
    const el = svg.current;
    if (!el) return;
    const chips = [...el.querySelectorAll<SVGRectElement>(".hp-chip rect")].map((r) => r.getBBox());
    el.querySelectorAll<SVGGraphicsElement>(".hp-zl").forEach((z) => {
      const b = z.getBBox();
      const hit = chips.some((c) => b.x < c.x + c.width + 2 && c.x < b.x + b.width + 2 && b.y < c.y + c.height + 2 && c.y < b.y + b.height + 2);
      z.style.visibility = hit ? "hidden" : "";
    });
  });
}

export default function HubPlan(props: PlanProps) {
  const [ref, box] = useBox();
  const svgRef = useRef<SVGSVGElement>(null);
  useChipKnockout(svgRef);
  const narrow = box.w > 0 && box.w < 640;
  const litKey = props.litCameras?.join() ?? "";
  const fx = props.focus ? props.focus.xy.join() : "";
  const hk = props.heat ? "heat" : "";
  // eslint-disable-next-line react-hooks/exhaustive-deps -- recompute only when the evidence or the width class changes
  const ext = useMemo(() => frame(props, box.w), [props.journey, props.missing, litKey, narrow, fx, hk]);
  const byW = box.w / (ext.x1 - ext.x0);
  const fitW = props.fit === "width" || ext !== FULL; // a zoomed phone plan takes the width; the box shrinks to it
  const S = box.w ? Math.max(4, fitW ? byW : Math.min(byW, (box.h || 1e9) / (ext.y1 - ext.y0))) : 0;
  const W = (ext.x1 - ext.x0) * S, H = (ext.y1 - ext.y0) * S;
  return (
    <div className="hp">
      <div className="hp-box" ref={ref} style={fitW ? { minHeight: S ? (ext.y1 - ext.y0) * S : 200, flex: "none" }
        : { minHeight: props.minHeight ?? 260 }}>
        {S > 0 && (
          <svg ref={svgRef} className="hp-svg" width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="group" aria-label={props.label}>
            <Base S={S} heat={props.heat} ext={ext} />
            <Overlay S={S} ext={ext} {...props} />
            {!props.focus && <ScaleNorth S={S} W={W} H={H} zoomed={ext !== FULL && !props.heat} />}
            {props.focus && (() => {
              const [px, py] = [(props.focus.xy[0] - ext.x0) * S, (ext.y1 - props.focus.xy[1]) * S];
              const col = props.focus.tone === "bad" ? "#f87171" : "#fbbf24";
              return <g aria-hidden><circle cx={px} cy={py} r={16} fill={col} opacity={0.18} />
                <circle cx={px} cy={py} r={6} fill={col} stroke="#0b0c10" strokeWidth={2} /></g>;
            })()}
          </svg>
        )}
      </div>
      {props.legend !== false && <Legend heat={!!props.heat} />}
    </div>
  );
}

const mk = (S: number, e: Ext = FULL) => {
  const P = ([x, y]: XY): XY => [(x - e.x0) * S, (e.y1 - y) * S];
  const pts = (poly: XY[]) => poly.map((p) => P(p).map((v) => v.toFixed(1)).join(",")).join(" ");
  const rect = (x1: number, y1: number, x2: number, y2: number) => {
    const [a, b] = P([Math.min(x1, x2), Math.max(y1, y2)]);
    return { x: a, y: b, width: Math.abs(x2 - x1) * S, height: Math.abs(y2 - y1) * S };
  };
  return { P, pts, rect };
};

function Base({ S, heat, ext }: { S: number; heat?: Record<string, number>; ext: Ext }) {
  return useMemo(() => {
    const { P, pts, rect } = mk(S, ext);
    const L = HUB.machines.loop as typeof HUB.machines.loop & { speed_mps?: number; carriers?: number };
    const stadium = (rr: number) => {
      const a = P([L.west_cx, L.cy - rr]), b = P([L.east_cx, L.cy - rr]), c = P([L.east_cx, L.cy + rr]), d = P([L.west_cx, L.cy + rr]);
      const R = rr * S;
      return `M${a} L${b} A${R},${R} 0 0 0 ${c} L${d} A${R},${R} 0 0 0 ${a} Z`;
    };
    const fs = (px: number) => Math.max(8, Math.min(px, px * S / 15)); // labels shrink a little on small plans, never below 8 px
    const showCodes = S >= 11;
    const chevrons: ReactNode[] = [];
    HUB.machines.conveyors.forEach((cv) => cv.path.forEach((a, i) => {
      const b = cv.path[i + 1];
      if (!b) return;
      const len = Math.hypot(b[0] - a[0], b[1] - a[1]);
      for (let k = 1; k * 2.2 < len - 0.4; k++) {
        const t = (k * 2.2 - 0.5) / len;
        const p = P([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]);
        const q = P([a[0] + (b[0] - a[0]) * (t + 0.3 / len), a[1] + (b[1] - a[1]) * (t + 0.3 / len)]);
        chevrons.push(<line key={`${cv.id}${i}${k}`} x1={p[0]} y1={p[1]} x2={q[0]} y2={q[1]} stroke="none" markerEnd="url(#hp-chev)" />);
      }
    }));
    const W_ = HUB.building.footprint_m[0], H_ = HUB.building.footprint_m[1];
    const walls: ReactNode[] = [];
    ([["W", 0, H_, 1], ["E", W_, H_, 1], ["S", 0, W_, 0], ["N", H_, W_, 0]] as const).forEach(([wall, fixed, len, coord]) => {
      const gaps = HUB.building.doors.filter((d) => d.wall === wall)
        .map((d) => [d.centre[coord] - d.width / 2, d.centre[coord] + d.width / 2, d] as const).sort((a, b) => a[0] - b[0]);
      let cur = 0;
      const segs: [number, number][] = [];
      gaps.forEach(([g0, g1]) => { segs.push([cur, g0]); cur = g1; });
      segs.push([cur, len]);
      const at = (v: number): XY => (coord === 1 ? [fixed, v] : [v, fixed]);
      segs.forEach(([s0, s1], i) => {
        const [a, b] = [P(at(s0)), P(at(s1))];
        walls.push(<line key={`${wall}s${i}`} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke={C.wall} strokeWidth={Math.max(2.5, 0.32 * S)} strokeLinecap="square" />);
      });
      gaps.forEach(([g0, g1, d]) => {
        const [a, b] = [P(at(g0)), P(at(g1))];
        if (d.kind === "dock") {
          const lab = coord === 1 ? P([fixed - 1.4, d.centre[1]]) : P([d.centre[0], fixed + 1.1]);
          walls.push(<g key={d.id}><line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke={C.inkF} strokeWidth={1.5} strokeDasharray="2 3" />
            <text x={lab[0]} y={lab[1] + 4} className="hp-t" fontSize={fs(10)} fill={C.inkM} fontWeight={640} textAnchor="middle">{d.board ?? d.id}</text></g>);
        } else {
          const h = coord === 1 ? P([fixed, g0]) : P([g0, fixed]);
          const r = S;
          const dpath = coord === 1 ? `M${h} a${r},${r} 0 0 0 ${fixed > 0 ? -r : r},${-r}` : `M${h} a${r},${r} 0 0 ${fixed > 0 ? 0 : 1} ${r},${fixed > 0 ? r : -r}`;
          walls.push(<path key={d.id} d={dpath} fill="none" stroke={C.inkF} strokeWidth={1} />);
        }
      });
    });
    const maxHeat = heat ? Math.max(1, ...Object.values(heat)) : 1;
    return (
      <g className="hp-base">
        <defs>
          <pattern id="hp-hatch" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="7" stroke={C.unk} strokeOpacity={0.4} strokeWidth={1.4} /></pattern>
          <pattern id="hp-hatch-cloud" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="6" height="6" fill="#8b909b" fillOpacity={0.12} />
            <line x1="0" y1="0" x2="0" y2="6" stroke="#c9ccd3" strokeOpacity={0.5} strokeWidth={1.3} /></pattern>
          <pattern id="hp-yard" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="10" stroke="#fff" strokeOpacity={0.035} /></pattern>
          <pattern id="hp-zebra" width="5" height="5" patternUnits="userSpaceOnUse"><rect width="2.5" height="5" fill="#fff" fillOpacity={0.07} /></pattern>
          <radialGradient id="hp-glow"><stop offset="0" stopColor={C.obs} stopOpacity={0.35} /><stop offset="1" stopColor={C.obs} stopOpacity={0} /></radialGradient>
          <radialGradient id="hp-glow-scan"><stop offset="0" stopColor={C.scan} stopOpacity={0.32} /><stop offset="1" stopColor={C.scan} stopOpacity={0} /></radialGradient>
          <marker id="hp-chev" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto">
            <path d="M2,1 L7,5 L2,9" fill="none" stroke={C.inkF} strokeWidth={1.6} strokeLinecap="round" /></marker>
        </defs>
        <rect {...rect(-4.6, 0, 0, 34)} fill="url(#hp-yard)" />
        <rect {...rect(20, 40, 60, 44.6)} fill="url(#hp-yard)" />
        <text className="hp-t" x={P([51.5, 43.3])[0]} y={P([51.5, 43.3])[1]} fontSize={fs(9)} fill={C.inkF} fontWeight={600} letterSpacing="0.12em">TRUCK YARD</text>
        <rect {...rect(0, 0, W_, H_)} fill={C.floor} />
        {HUB.walkways.map((w) => <rect key={w.id} {...rect(...w.rect_m)} fill="#fff" fillOpacity={0.018} />)}
        <polyline points={pts(HUB.circulation.forklift_lane.centreline_m)} fill="none" stroke="#fff" strokeOpacity={0.025}
          strokeWidth={HUB.circulation.forklift_lane.width_m * S} strokeLinejoin="round" />
        <polyline points={pts(HUB.circulation.forklift_lane.centreline_m)} fill="none" stroke="#fff" strokeOpacity={0.07} strokeDasharray="6 7" />
        {HUB.circulation.zebra_crossings.map((z) => <rect key={z.id} {...rect(...z.rect_m)} fill="url(#hp-zebra)" />)}
        {HUB.zones.filter((z) => z.id !== "Z14" && z.id !== "Z05").flatMap((z) => z.polygons.map((p, i) => {
          const n = heat?.[z.id] ?? 0;
          return <polygon key={`${z.id}${i}`} points={pts(p)} fill={n ? C.inkS : "#fff"}
            fillOpacity={n ? 0.06 + 0.22 * (n / maxHeat) : 0.022} stroke="rgba(255,255,255,0.07)" />;
        }))}
        {HUB.building.columns.map(([x, y], i) => <rect key={i} {...rect(x - 0.25, y - 0.25, x + 0.25, y + 0.25)} fill="#2c2f38" />)}
        {HUB.fixtures.racks.map((r, i) => <rect key={i} {...rect(...r.rect_m)} fill="#2a2d35" stroke={C.machE} />)}
        <polygon points={pts(HUB.blind_corner.polygon)} fill="url(#hp-hatch)" stroke={C.unk} strokeOpacity={0.5} strokeDasharray="4 4" />
        <text className="hp-t" x={P([1.0, 37.6])[0]} y={P([1.0, 37.6])[1]} fontSize={fs(11)} fill={C.ink} fontWeight={600}>No camera coverage</text>
        {S >= 9 && <text className="hp-t" x={P([1.0, 37.6])[0]} y={P([1.0, 37.6])[1] + fs(11) + 3} fontSize={fs(10)} fill={C.inkM} fontWeight={500}>behind the sack racks</text>}
        {HUB.fixtures.benches.map((b, i) => <rect key={i} {...rect(...b.rect_m)} rx={2} fill={C.mach} stroke={C.machE} />)}
        {HUB.fixtures.cage_bays.map((c) => <rect key={c.id} {...rect(c.sw_corner_m[0] + 0.15, c.sw_corner_m[1] + 0.15,
          c.sw_corner_m[0] + c.size_m - 0.15, c.sw_corner_m[1] + c.size_m - 0.15)} rx={2} fill="none" stroke="#fff" strokeOpacity={0.08} />)}
        {HUB.machines.conveyors.map((cv) => (
          <g key={cv.id}>
            <polyline points={pts(cv.path)} fill="none" stroke={C.machE} strokeWidth={(cv.kind === "telescopic" ? 0.7 : 0.8) * S + 2} strokeLinejoin="round" />
            <polyline points={pts(cv.path)} fill="none" stroke={C.mach} strokeWidth={(cv.kind === "telescopic" ? 0.7 : 0.8) * S} strokeLinejoin="round" />
          </g>
        ))}
        {chevrons}
        <rect {...rect(19.5, 8.6, 22.0, 10.4)} rx={3} fill="#2a2d36" stroke="#4a4e59" />
        <path d={stadium(L.radius)} fill="none" stroke={C.machE} strokeWidth={S + 2} />
        <path d={stadium(L.radius)} fill="none" stroke={C.mach} strokeWidth={S} />
        <path d={stadium(L.radius)} fill="none" stroke="#3a3d47" strokeWidth={0.8 * S} strokeDasharray={`1.2 ${Math.max(1, 0.7 * S - 1.2)}`} />
        <path d={stadium(L.radius - 0.5)} fill="#fff" fillOpacity={0.012} />
        <text className="hp-t hp-zl" x={P([(L.west_cx + L.east_cx) / 2, L.cy + 0.2])[0]} y={P([(L.west_cx + L.east_cx) / 2, L.cy + 0.2])[1]}
          fontSize={fs(12)} fill={C.inkM} fontWeight={600} textAnchor="middle">Cross-belt sorter</text>
        {S >= 10 && <text className="hp-t hp-zl" x={P([(L.west_cx + L.east_cx) / 2, L.cy + 0.2])[0]} y={P([(L.west_cx + L.east_cx) / 2, L.cy + 0.2])[1] + 15}
          fontSize={fs(10)} fill={C.inkF} fontWeight={500} textAnchor="middle">{`${L.carriers ?? 99} carriers · ${L.speed_mps ?? 2} m/s · counter-clockwise`}</text>}
        {HUB.circulation.crossovers.map((x) => <rect key={x.id} {...rect(x.x - x.width / 2, x.south_stair_y[0], x.x + x.width / 2, x.north_stair_y[1])}
          rx={2} fill="none" stroke="#fff" strokeOpacity={0.16} strokeDasharray="3 3" />)}
        {HUB.machines.chutes.map((ch) => {
          const poly: XY[] = [[ch.x - 0.42, ch.mouth_y - 0.25], [ch.x + 0.42, ch.mouth_y - 0.25], [ch.x + ch.width / 2 - 0.05, ch.end_y], [ch.x - ch.width / 2 + 0.05, ch.end_y]];
          const t = P([ch.x, ch.end_y + 0.75]);
          return <g key={ch.id}><polygon points={pts(poly)} fill="#2a2d36" stroke="#474b56" strokeLinejoin="round" />
            {S >= 8 && <text className="hp-t" x={t[0]} y={t[1] + 3} fontSize={fs(9)} fill={C.inkF} fontWeight={600} textAnchor="middle">{ch.id === "REJECT" ? "R" : ch.id.slice(1)}</text>}</g>;
        })}
        {walls}
        {HUB.zones.filter((z) => LABEL_AT[z.id] && (heat ? !!heat[z.id] : S >= 8.5 || !SMALL_ZONES.has(z.id))).map((z) => {
          const [x, y] = P(LABEL_AT[z.id]);
          const n = heat?.[z.id];
          return <g key={z.id} className="hp-zl">
            <text className="hp-t" x={x} y={y} fontSize={fs(11)} fill={n ? C.inkS : C.inkM} fontWeight={600}>{ZONE_NAMES[z.id] ?? z.name}</text>
            {(showCodes || n) && <text className="hp-t" x={x} y={y + fs(11) + 2} fontSize={fs(9)} fill={n ? C.ink : C.inkF} fontWeight={600} letterSpacing="0.04em">
              {n ? `${n} case${n === 1 ? "" : "s"} end here · ${z.id}` : z.id}</text>}
          </g>;
        })}
      </g>
    );
  }, [S, heat, ext]);
}

function ScaleNorth({ S, W, H, zoomed }: { S: number; W: number; H: number; zoomed: boolean }) {
  const [sx, sy] = [10, H - 14];
  const [nx, ny] = [W - 14, H - 18];
  return (
    <g aria-hidden>
      <rect x={sx - 6} y={sy - 10} width={10 * S + (zoomed ? 150 : 40)} height={20} rx={6} fill={C.surf} fillOpacity={0.85} />
      <rect x={nx - 11} y={ny - 19} width={22} height={36} rx={6} fill={C.surf} fillOpacity={0.85} />
      <line x1={sx} y1={sy} x2={sx + 10 * S} y2={sy} stroke={C.inkM} strokeWidth={1.5} />
      {[0, 5, 10].map((i) => <line key={i} x1={sx + i * S} y1={sy - 4} x2={sx + i * S} y2={sy + 4} stroke={C.inkM} strokeWidth={1.5} />)}
      <text className="hp-t" x={sx + 10 * S + 6} y={sy + 4} fontSize={9.5} fill={C.inkM}>10 m{zoomed ? " · zoomed to the journey" : ""}</text>
      <path d={`M${nx},${ny - 14} L${nx + 5},${ny} L${nx},${ny - 4} L${nx - 5},${ny} Z`} fill={C.inkM} />
      <text className="hp-t" x={nx} y={ny + 12} fontSize={9} fill={C.inkM} fontWeight={640} textAnchor="middle">N</text>
    </g>
  );
}

interface Chip { x: number; y: number; w: number; h: number; ax: number; ay: number; t: string; sub: string; dot: string }

/** Chip placement (review F-032 #1): chips never overlap each other and never leave the plan. Story chips go first
 * (`rank` 0); each takes the first preferred offset that is free, else the nearest free spot anywhere on the plan
 * (first off the route, then anywhere chip-free); a chip with no free spot is dropped, its facts stay in the bead tooltip. */
function placeChips(want: { at: XY; t: string; sub: string; dot: string; rank: number }[], route: XY[], W: number, H: number): Chip[] {
  const out: Chip[] = [];
  const outside = (x: number, y: number, w: number, h: number) => x < 4 || y < 4 || x + w > W - 4 || y + h > H - 4;
  const onChip = (x: number, y: number, w: number, h: number) =>
    out.some((c) => x < c.x + c.w + 6 && x + w + 6 > c.x && y < c.y + c.h + 6 && y + h + 6 > c.y);
  const onRoute = (x: number, y: number, w: number, h: number) =>
    route.some(([px, py]) => px > x - 8 && px < x + w + 8 && py > y - 8 && py < y + h + 8);
  for (const c of [...want].sort((a, b) => a.rank - b.rank)) {
    const w = 34 + 7.1 * Math.max(c.t.length * 0.95, c.sub.length * 0.86);
    const h = 36;
    const [ax, ay] = c.at;
    const pref: XY[] = [[34, -62], [34, 26], [-34 - w, -62], [-34 - w, 26], [60, -104], [-60 - w, -104], [60, 70], [-60 - w, 70],
      [90, -20], [-90 - w, -20]].map(([dx, dy]) => [ax + dx, ay + dy]);
    const free = ([x, y]: XY) => !outside(x, y, w, h) && !onChip(x, y, w, h);
    const clear = (p: XY) => free(p) && !onRoute(p[0], p[1], w, h);
    let grid: XY[] | null = null;
    const near = () => {
      if (!grid) {
        const d = ([x, y]: XY) => Math.hypot(x + w / 2 - ax, y + h / 2 - ay);
        grid = [];
        for (let y = 4; y + h <= H - 4; y += 8) for (let x = 4; x + w <= W - 4; x += 8) grid.push([x, y]);
        grid.sort((p, q) => d(p) - d(q));
      }
      return grid;
    };
    const pick = pref.find(clear) ?? near().find(clear) ?? pref.find(free) ?? near().find(free);
    if (pick) out.push({ x: pick[0], y: pick[1], w, h, ax, ay, t: c.t, sub: c.sub, dot: c.dot });
  }
  return out;
}

function Overlay({ S, ext, journey: j, missing, marker, cloud, litCameras = [], selectedScanId, activeScanId, onScan, onObservation, quiet }: PlanProps & { S: number; ext: Ext }) {
  const { P, pts } = mk(S, ext);
  const W = (ext.x1 - ext.x0) * S, H = (ext.y1 - ext.y0) * S;
  const lit = new Set(litCameras);
  const last = j?.last_confirmed ?? null;
  const expected = (missing?.expected_next ?? []).filter((r) => r.role !== "watching_last_point" && r.result !== "no_footage").slice(0, 2);
  const routePx: XY[] = [];
  j?.segments.forEach((s) => {
    if (s.kind === "inferred_along_conveyor") s.path_m.forEach((p) => routePx.push(P(p)));
    if (s.kind === "observed") s.points.forEach((p) => p.xy && routePx.push(P(p.xy)));
  });
  // small plans keep only the chips that carry the story (last confirmed + expected); others stay in bead tooltips
  const compact = S < 12;
  const chips = j && !quiet ? placeChips([
    ...j.scans.filter((s) => s.xy && (!compact || last?.evidence_id === s.scan_event_id || s.scan_event_id === activeScanId)).map((s) => {
      const isLast = last?.evidence_id === s.scan_event_id;
      return { at: P(s.xy!), t: clock(s.t, true).replace(" MYT", ""), sub: `${isLast ? "Last confirmed · " : ""}${short(describeScan(s).title)}`, dot: C.scan,
        rank: isLast ? 0 : 2 };
    }),
    ...(last?.kind === "observation" && last.xy ? [{ at: P(last.xy), t: clock(last.t, true).replace(" MYT", ""), sub: `Last confirmed · seen on ${cam(last.camera_id)}`, dot: C.obs, rank: 0 }] : []),
    ...expected.map((r) => ({ at: P(r.expected_xy), t: `${clock(r.window.start, true).replace(" MYT", "")}–${clock(r.window.end).replace(" MYT", "").slice(-2)}`,
      sub: `Expected on ${cam(r.camera_id).replace("_", " ")} · ${r.result === "not_seen" ? "not seen" : r.result === "seen" ? "seen" : "not analysed"}`,
      dot: r.result === "not_seen" ? C.con : C.unk, rank: 1 })),
  ], routePx, W, H) : [];
  return (
    <g className="hp-over">
      {HUB.cameras.map((c) => {
        const hi = lit.has(c.id);
        const [cx, cy] = P([c.position_m[0], c.position_m[1]]);
        const h = (c.heading_deg * Math.PI) / 180;
        const half = (c.hfov_deg * Math.PI) / 360;
        const rng = 8;
        const p1 = P([c.position_m[0] + rng * Math.cos(h - half), c.position_m[1] + rng * Math.sin(h - half)]);
        const p2 = P([c.position_m[0] + rng * Math.cos(h + half), c.position_m[1] + rng * Math.sin(h + half)]);
        const [dx, dy] = [Math.cos(h), -Math.sin(h)];
        const col = hi ? C.acc : C.inkF;
        return (
          <g key={c.id}>
            {hi && <path d={`M${cx},${cy} L${p1} A${rng * S},${rng * S} 0 0 0 ${p2} Z`} fill={C.acc} fillOpacity={0.07} stroke={C.acc} strokeOpacity={0.35} />}
            <circle cx={cx} cy={cy} r={hi ? 6 : 3.5} fill={C.surf} stroke={col} strokeWidth={1.6}><title>{`${c.id} ${c.osd_label}`}</title></circle>
            <line x1={cx} y1={cy} x2={cx + dx * (hi ? 11 : 6.5)} y2={cy + dy * (hi ? 11 : 6.5)} stroke={col} strokeWidth={1.8} strokeLinecap="round" />
            {hi && <text className="hp-t" x={cx - dx * 15} y={cy - dy * 15 + 4} fontSize={10} fill={C.acc} fontWeight={640} textAnchor="middle">{c.id.replace("_", " ")}</text>}
          </g>
        );
      })}
      {cloud && cloud.polygons.map((poly, i) => (
        <polygon key={`cloud${i}`} data-ev="possible" points={pts(poly)} fill="url(#hp-hatch-cloud)"
          stroke="#c9ccd3" strokeOpacity={0.75} strokeWidth={1.2} strokeDasharray="4 3">
          <title>{`Could be here (computed): reachable within ${cloud.seconds} s on foot${cloud.removed.length ? `, minus what ${cloud.removed.join(", ")} watched without seeing it` : ""}. Not an observation.`}</title>
        </polygon>
      ))}
      {j?.segments.map((s, i) => s.kind === "observed" ? (
        <g key={i} data-ev="observed" data-from={s.start} data-to={s.end}>
          <polyline points={pts(s.points.filter((p) => p.xy).map((p) => p.xy!))} fill="none" stroke={C.obs} strokeWidth={10} strokeOpacity={0.18} strokeLinecap="round" strokeLinejoin="round" />
          <polyline points={pts(s.points.filter((p) => p.xy).map((p) => p.xy!))} fill="none" stroke={C.obs} strokeWidth={3} strokeLinecap="round" strokeLinejoin="round"
            role="button" tabIndex={0} aria-label={`Seen on ${cam(s.camera_id)}: open its frame`} style={{ cursor: "pointer" }}
            onClick={() => onObservation?.(s.points[0].observation_id)} onKeyDown={(e) => e.key === "Enter" && onObservation?.(s.points[0].observation_id)} />
        </g>
      ) : s.kind === "inferred_along_conveyor" ? (
        <polyline key={i} data-ev="inferred" points={pts(s.path_m)} fill="none" stroke={C.hyp} strokeWidth={3} strokeDasharray="0.1 7" strokeLinecap="round" strokeLinejoin="round">
          <title>{`Inferred along ${s.route.join(" → ")}: ${s.belt_time_s} s at belt speed, recorded ${s.recorded_gap_s} s. Not seen.`}</title>
        </polyline>
      ) : null)}
      {expected.map((r) => {
        const [x, y] = P(r.expected_xy);
        return <rect key={r.camera_id} data-ev={r.result === "not_seen" ? "expected-not-seen" : "expected"} x={x - 11} y={y - 9} width={22} height={18} rx={4}
          fill="none" stroke={r.result === "not_seen" ? C.con : C.unk} strokeWidth={1.6} strokeDasharray="4 3">
          <title>{`Expected on ${cam(r.camera_id)} ${clock(r.predicted_t, true)} (${r.how}): ${r.result.replace(/_/g, " ")}`}</title></rect>;
      })}
      {last?.xy && (() => {
        const [x, y] = P(last.xy);
        const seen = last.kind === "observation";
        return <g data-ev="last-confirmed" aria-hidden>
          <circle cx={x} cy={y} r={22} fill={`url(#${seen ? "hp-glow" : "hp-glow-scan"})`} />
          <circle cx={x} cy={y} r={10} fill="none" stroke={seen ? C.obs : C.scan} strokeWidth={1.5} strokeOpacity={0.85} />
        </g>;
      })()}
      {j?.scans.filter((s) => s.xy).map((s) => {
        const [x, y] = P(s.xy!);
        const sel = selectedScanId === s.scan_event_id;
        const label = `${describeScan(s).title} at ${clock(s.t, true)}`;
        return (
          <g key={s.scan_event_id} role="button" tabIndex={0} aria-label={`Scan: ${label}. Open source.`} style={{ cursor: "pointer" }}
            onClick={() => onScan?.(s.scan_event_id)} onKeyDown={(e) => e.key === "Enter" && onScan?.(s.scan_event_id)}>
            {s.scan_event_id === activeScanId && <circle cx={x} cy={y} r={13} fill="none" stroke={C.scan} strokeWidth={2} strokeOpacity={0.8} data-ev="scan-active" />}
            <rect x={x - 5.5} y={y - 5.5} width={11} height={11} rx={2} transform={`rotate(45 ${x} ${y})`} fill={sel ? "#bfdbfe" : C.scan} stroke={C.surf} strokeWidth={2} />
            <title>{label}</title>
          </g>
        );
      })}
      {chips.map((c, i) => (
        <g key={i} className="hp-chip" aria-hidden>
          <line x1={c.ax} y1={c.ay} x2={c.x < c.ax ? c.x + c.w : c.x} y2={c.y + c.h / 2} stroke={C.inkF} />
          <rect x={c.x} y={c.y} width={c.w} height={c.h} rx={9} fill={C.surf2} stroke="rgba(255,255,255,0.13)" />
          <circle cx={c.x + 11} cy={c.y + 12} r={3.2} fill={c.dot} />
          <text className="hp-t" x={c.x + 20} y={c.y + 16} fontSize={11.5} fill={C.inkS} fontWeight={640}>{c.t}</text>
          <text className="hp-t" x={c.x + 11} y={c.y + 30} fontSize={9.5} fill={C.inkM} fontWeight={520}>{c.sub}</text>
        </g>
      ))}
      {marker?.xy && (() => {
        const [x, y] = P(marker.xy);
        const col = marker.kind === "observed" ? C.obs : marker.kind === "scan" ? C.scan : C.hyp;
        return <g data-testid="replay-marker" data-kind={marker.kind} pointerEvents="none">
          <circle cx={x} cy={y} r={12} fill={col} opacity={0.22} />
          <circle cx={x} cy={y} r={5.5} fill={C.inkS} stroke={col} strokeWidth={2.5} /><title>{marker.label}</title></g>;
      })()}
    </g>
  );
}

const short = (title: string) => title.replace("label read at the scan tunnel", "Label read · tunnel").replace(/^loaded onto carrier (\d+)/, "On carrier $1")
  .replace(/^sorter divert to (\w+)/, "Divert $1").replace(/ \(line [AB]\)/, "");

function Legend({ heat }: { heat: boolean }) {
  const items: [string, ReactNode][] = heat ? [
    ["Cases whose evidence ends in this zone", <rect key="h" x="1" y="3" width="18" height="12" rx="3" fill="#f4f5f7" fillOpacity={0.24} />],
    ["No camera coverage", <rect key="n" x="1" y="3" width="18" height="12" rx="3" fill="url(#hp-hatch-l)" stroke="#8b909b" strokeOpacity={0.6} />],
  ] : [
    ["Seen on camera", <line key="s" x1="1" y1="9" x2="19" y2="9" stroke={C.obs} strokeWidth="3" strokeLinecap="round" />],
    ["Inferred along belt (not seen)", <line key="i" x1="1" y1="9" x2="19" y2="9" stroke={C.hyp} strokeWidth="3" strokeDasharray="0.1 6" strokeLinecap="round" />],
    ["Scan", <rect key="b" x="5" y="4" width="10" height="10" rx="2" transform="rotate(45 10 9)" fill={C.scan} />],
    ["Last confirmed", <circle key="l" cx="10" cy="9" r="6.5" fill="none" stroke={C.scan} strokeWidth="1.5" />],
    ["Expected here (red: not seen)", <rect key="e" x="1" y="3" width="18" height="12" rx="3" fill="none" stroke={C.con} strokeWidth="1.5" strokeDasharray="4 3" />],
    ["No coverage / could be here", <rect key="n" x="1" y="3" width="18" height="12" rx="3" fill="url(#hp-hatch-l)" stroke="#8b909b" strokeOpacity={0.6} />],
    ["Camera in play", <circle key="c" cx="10" cy="9" r="5" fill={C.surf} stroke={C.acc} strokeWidth="1.6" />],
  ];
  return (
    <ul className="hp-legend" aria-label="Legend">
      <svg width="0" height="0" aria-hidden style={{ position: "absolute" }}><defs>
        <pattern id="hp-hatch-l" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="5" stroke="#8b909b" strokeOpacity={0.6} strokeWidth={1.3} /></pattern></defs></svg>
      {items.map(([label, sw]) => <li key={label}><svg width="20" height="18" aria-hidden>{sw}</svg>{label}</li>)}
    </ul>
  );
}

export { centroid };
