"use client";
/**
 * A clean vector floor plan of the hub (Rexton 3 Nov: the old sketch did not read as an industry drawing). Drawn from the
 * hub plan itself: the building, its zones with names, walkways, the cross-belt loop, conveyors, racks and cage bays as
 * plain shapes on 1 px lines and muted fills. Over it: one route (solid where a camera saw it, dashed where none did),
 * numbered stops, the cameras actually used, a "you are here", one highlighted zone. Light and print-safe (reads in
 * greyscale: the route is the darkest line, the highlight is a hatch as well as a tint), with a scale bar and north arrow.
 * Used by the worker's phone (compact, a walking route) and the case report (full, the parcel's route).
 */
import { useId, useMemo } from "react";
import { HUB } from "@/lib/hub";
import type { XY } from "@/lib/journey";
import "./floorplan.css";

export interface FPStop { n: number | string; xy: XY; tone?: "scan" | "seen" | "bad" | "none"; label?: string; on?: boolean }
export interface FPLeg { from: XY; to: XY; seen: boolean }
export interface FPCam { id: string; xy: XY; heading_deg: number }

interface Props {
  label: string;
  /** frame to these points (+ a margin); else the whole building */
  fit?: XY[];
  margin?: number;
  highlight?: string; // a zone id (Z11)
  legs?: FPLeg[];
  route?: XY[]; // one continuous walking route (the phone)
  stops?: FPStop[];
  cameras?: FPCam[];
  you?: XY;
  labels?: "all" | "major" | "none";
  /** these zones are named whatever `labels` says, at `labelSize` metres (a phone's small plan: 2-3 names it can read) */
  labelIds?: string[];
  labelSize?: number;
  /** grey every zone but the highlighted one (the route is the subject) */
  dim?: boolean;
  legend?: boolean;
  onStop?: (n: FPStop["n"]) => void;
}

const W = 60, H = 40; // the building, metres
const KIND_FILL: Record<string, string> = { dock: "var(--fp-dock)", work: "var(--fp-work)", machine: "var(--fp-machine)", staging: "var(--fp-stage)",
  store: "var(--fp-store)", office: "var(--fp-office)", yard: "transparent" };
const SHORT: Record<string, string> = { Z01: "Inbound dock", Z02: "Bag opening", Z03: "Induction", Z04: "Scan tunnel", Z05: "Sorter loop",
  Z06: "Chutes C01–C12", Z07: "Reject chute", Z08: "Exception bench", Z09: "Oversize", Z10: "Cage staging", Z11: "Exception store",
  Z12: "Outbound dock", Z13: "Office", Z14: "" };
const MAJOR = new Set(["Z01", "Z06", "Z10", "Z11", "Z12", "Z13", "Z05", "Z08"]);

export function centroid(poly: number[][]): XY {
  return [poly.reduce((a, p) => a + p[0], 0) / poly.length, poly.reduce((a, p) => a + p[1], 0) / poly.length];
}

export default function FloorPlan(p: Props) {
  const uid = useId().replace(/:/g, "");
  const hub = HUB as unknown as {
    zones: { id: string; name: string; kind: string; polygons: number[][][] }[];
    walkways: { id: string; rect_m: number[] }[];
    machines: { loop: { south_y: number; north_y: number; radius: number; west_cx: number; east_cx: number };
      conveyors: { id: string; kind: string; path: number[][] }[] };
    fixtures: { racks: { rect_m: number[] }[]; cage_bays: { id: string; sw_corner_m: number[]; size_m: number }[];
      benches: { name: string; rect_m: number[] }[] };
    building: { doors: { id: string; wall: string; centre: number[]; width: number; kind: string }[] };
  };
  // the view: the building, or the points asked for with a margin (never past the walls)
  const box = useMemo(() => {
    if (!p.fit?.length) return { x0: -1.5, y0: -1.5, x1: W + 1.5, y1: H + 1.5 };
    const m = p.margin ?? 6;
    const xs = p.fit.map((q) => q[0]), ys = p.fit.map((q) => q[1]);
    return { x0: Math.max(-1.5, Math.min(...xs) - m), x1: Math.min(W + 1.5, Math.max(...xs) + m),
      y0: Math.max(-1.5, Math.min(...ys) - m), y1: Math.min(H + 1.5, Math.max(...ys) + m) };
  }, [p.fit, p.margin]);
  const vw = box.x1 - box.x0, vh = box.y1 - box.y0;
  const k = vw / 60; // stroke and text scale with the frame: the same px look at any zoom
  const X = (x: number) => x, Y = (y: number) => H - y; // north up
  const pts = (ps: number[][]) => ps.map((q) => `${X(q[0])},${Y(q[1])}`).join(" ");
  const L = hub.machines.loop;
  const loopD = `M${L.west_cx},${Y(L.south_y)} L${L.east_cx},${Y(L.south_y)} A${L.radius},${L.radius} 0 0 0 ${L.east_cx},${Y(L.north_y)} `
    + `L${L.west_cx},${Y(L.north_y)} A${L.radius},${L.radius} 0 0 0 ${L.west_cx},${Y(L.south_y)} Z`;
  const showLabel = (id: string) => p.labels === "all" || ((p.labels ?? "major") === "major" && (MAJOR.has(id) || id === p.highlight))
    || !!p.labelIds?.includes(id);
  const fs = (p.labelSize ?? 1.2) * k; // label size in metres of the drawing (1.2 ≈ 10-11 px on a desktop-width plan)

  return (
    <figure className="fp" aria-label={p.label} data-dim={p.dim ? "" : undefined}>
      <svg viewBox={`${box.x0} ${H - box.y1} ${vw} ${vh}`} role="img" aria-label={p.label} preserveAspectRatio="xMidYMid meet">
        <defs>
          <pattern id={`hatch${uid}`} width={1.2 * k} height={1.2 * k} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2={1.2 * k} className="fp-hatch" strokeWidth={0.35 * k} />
          </pattern>
          <marker id={`arr${uid}`} viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" className="fp-arrowhead" />
          </marker>
        </defs>
        {/* the building and its zones */}
        <rect x={0} y={0} width={W} height={H} className="fp-building" strokeWidth={0.18 * k} />
        {hub.zones.filter((z) => z.kind !== "yard").map((z) => z.polygons.map((poly, i) => (
          <polygon key={`${z.id}${i}`} points={pts(poly)} fill={KIND_FILL[z.kind] ?? "var(--fp-work)"} className="fp-zone" strokeWidth={0.08 * k} />
        )))}
        {p.highlight && hub.zones.filter((z) => z.id === p.highlight).map((z) => z.polygons.map((poly, i) => (
          <g key={`hl${i}`}>
            <polygon points={pts(poly)} className="fp-hl" strokeWidth={0.3 * k} />
            <polygon points={pts(poly)} fill={`url(#hatch${uid})`} className="fp-hl-hatch" />
          </g>
        )))}
        {/* walkways, racks, benches, cage bays, conveyors, the loop */}
        {hub.walkways.map((w) => (
          <rect key={w.id} x={w.rect_m[0]} y={Y(w.rect_m[3])} width={w.rect_m[2] - w.rect_m[0]} height={w.rect_m[3] - w.rect_m[1]} className="fp-walk" />
        ))}
        {hub.fixtures.racks.map((r, i) => (
          <rect key={`r${i}`} x={r.rect_m[0]} y={Y(r.rect_m[3])} width={r.rect_m[2] - r.rect_m[0]} height={r.rect_m[3] - r.rect_m[1]} className="fp-solid" />
        ))}
        {hub.fixtures.benches.map((b, i) => (
          <rect key={`b${i}`} x={b.rect_m[0]} y={Y(b.rect_m[3])} width={b.rect_m[2] - b.rect_m[0]} height={b.rect_m[3] - b.rect_m[1]} className="fp-bench" strokeWidth={0.08 * k} />
        ))}
        {hub.fixtures.cage_bays.map((c) => (
          <rect key={c.id} x={c.sw_corner_m[0]} y={Y(c.sw_corner_m[1] + c.size_m)} width={c.size_m} height={c.size_m} className="fp-bay" strokeWidth={0.07 * k} />
        ))}
        {hub.machines.conveyors.filter((c) => c.kind !== "loop").map((c) => (
          <polyline key={c.id} points={pts(c.path)} className="fp-belt" strokeWidth={0.9} />
        ))}
        <path d={loopD} className="fp-loop" strokeWidth={1.1} />
        {/* doors: a gap in the wall */}
        {hub.building.doors.map((d) => {
          const [cx, cy] = d.centre, h = d.width / 2;
          const seg = d.wall === "W" || d.wall === "E" ? [[cx, cy - h], [cx, cy + h]] : [[cx - h, cy], [cx + h, cy]];
          return <line key={d.id} x1={X(seg[0][0])} y1={Y(seg[0][1])} x2={X(seg[1][0])} y2={Y(seg[1][1])} className="fp-door" strokeWidth={0.5 * k} />;
        })}
        {/* labels */}
        {hub.zones.filter((z) => SHORT[z.id] && showLabel(z.id)).map((z) => {
          const [cx0, cy0] = centroid(z.polygons[0]);
          const half = SHORT[z.id].length * fs * 0.29; // keep the whole label inside the frame
          // on a dimmed route map the route starts and ends at zone centres: name the zone in its top-left corner instead
          const corner = p.dim && p.labelIds?.includes(z.id);
          const xs = z.polygons[0].map((q) => q[0]), ys = z.polygons[0].map((q) => q[1]);
          const left = Math.max(Math.min(...xs), box.x0) + 0.8 * k;
          const out = corner && left + half * 2 > box.x1 - 0.4 * k; // would run off the frame: sit just left of the zone instead
          const cx = !corner ? Math.min(Math.max(cx0, box.x0 + half + 0.4 * k), box.x1 - half - 0.4 * k) : out ? Math.min(...xs) - 0.8 * k : left;
          const cy = corner ? Math.min(Math.max(...ys), box.y1) - fs * 0.9 : cy0;
          return <text key={z.id} x={X(cx)} y={Y(cy)} fontSize={fs} className={`fp-label${z.id === p.highlight ? " fp-label-hl" : ""}`}
            textAnchor={!corner ? "middle" : out ? "end" : "start"} dominantBaseline="middle">{SHORT[z.id]}</text>;
        })}
        {/* the route */}
        {p.legs?.map((g, i) => (
          <line key={i} x1={X(g.from[0])} y1={Y(g.from[1])} x2={X(g.to[0])} y2={Y(g.to[1])} className={g.seen ? "fp-route" : "fp-route fp-route-gap"}
            strokeWidth={0.45 * k} strokeDasharray={g.seen ? undefined : `${1 * k} ${0.9 * k}`} />
        ))}
        {p.route && p.route.length > 1 && (
          <polyline points={pts(p.route)} className="fp-walkroute" strokeWidth={0.55 * k} markerEnd={`url(#arr${uid})`} />
        )}
        {p.cameras?.map((c) => {
          const a = (c.heading_deg * Math.PI) / 180, r = 2.2 * k;
          return (
            <g key={c.id} className="fp-cam">
              <path d={`M${X(c.xy[0])},${Y(c.xy[1])} L${X(c.xy[0] + r * Math.cos(a - 0.45))},${Y(c.xy[1] + r * Math.sin(a - 0.45))} `
                + `L${X(c.xy[0] + r * Math.cos(a + 0.45))},${Y(c.xy[1] + r * Math.sin(a + 0.45))} Z`} className="fp-cam-cone" />
              <circle cx={X(c.xy[0])} cy={Y(c.xy[1])} r={0.42 * k} className="fp-cam-dot" />
            </g>
          );
        })}
        {fanned(p.stops ?? [], 2.6 * k).map((s) => (
          <g key={String(s.n)} className="fp-stop" data-tone={s.tone ?? "none"} data-on={s.on ? "" : undefined}
            role={p.onStop ? "button" : undefined} tabIndex={p.onStop ? 0 : undefined} onClick={() => p.onStop?.(s.n)}
            onKeyDown={(e) => e.key === "Enter" && p.onStop?.(s.n)}>
            <circle cx={X(s.xy[0])} cy={Y(s.xy[1])} r={(s.on ? 1.35 : 1.1) * k} strokeWidth={0.22 * k} />
            <text x={X(s.xy[0])} y={Y(s.xy[1])} fontSize={1.25 * k} textAnchor="middle" dominantBaseline="central">{s.n}</text>
            {s.label && <title>{`${s.n}: ${s.label}`}</title>}
          </g>
        ))}
        {p.you && (
          <g className="fp-you">
            <circle cx={X(p.you[0])} cy={Y(p.you[1])} r={1.6 * k} className="fp-you-halo" />
            <circle cx={X(p.you[0])} cy={Y(p.you[1])} r={0.75 * k} className="fp-you-dot" strokeWidth={0.3 * k} />
          </g>
        )}
        {/* scale bar (10 m) and north arrow, in the frame's bottom corners */}
        <g className="fp-scale" transform={`translate(${box.x0 + 1.4 * k},${H - box.y0 - 1.6 * k})`}>
          <line x1="0" y1="0" x2="10" y2="0" strokeWidth={0.2 * k} />
          <line x1="0" y1={-0.5 * k} x2="0" y2={0.5 * k} strokeWidth={0.2 * k} />
          <line x1="10" y1={-0.5 * k} x2="10" y2={0.5 * k} strokeWidth={0.2 * k} />
          <text x="5" y={-0.9 * k} fontSize={1.1 * k} textAnchor="middle">10 m</text>
        </g>
        <g className="fp-north" transform={`translate(${box.x1 - 1.8 * k},${H - box.y1 + 2.2 * k})`}>
          <path d={`M0,${-1.4 * k} L${0.8 * k},${0.9 * k} L0,${0.45 * k} L${-0.8 * k},${0.9 * k} Z`} />
          <text x="0" y={2.3 * k} fontSize={1 * k} textAnchor="middle">N</text>
        </g>
      </svg>
      {p.legend && (
        <figcaption className="fp-legend">
          <span><i className="fp-k-route" />Route on camera</span>
          <span><i className="fp-k-gap" />No camera saw it</span>
          <span><i className="fp-k-hl" />Where to look</span>
          <span><i className="fp-k-cam" />Camera used</span>
          <span><i className="fp-k-belt" />Conveyor / sorter</span>
        </figcaption>
      )}
    </figure>
  );
}

/** stops closer than d (metres) spread around their spot so each number reads */
function fanned(stops: FPStop[], d: number): FPStop[] {
  const placed: XY[] = [];
  return stops.map((s) => {
    let q: XY = s.xy;
    for (let k = 0; placed.some((p) => Math.hypot(p[0] - q[0], p[1] - q[1]) < d) && k < 10; k++)
      q = [s.xy[0] + d * Math.cos(k * 1.9), s.xy[1] + d * Math.sin(k * 1.9)];
    placed.push(q);
    return { ...s, xy: q };
  });
}

/** A walking route between two points along the hub's walkways (rect graph: walkways that touch are joined), ending at the
 *  target. General: no hand-drawn paths. */
export function walkRoute(from: XY, to: XY): XY[] {
  const ws = (HUB as unknown as { walkways: { id: string; rect_m: number[] }[] }).walkways.map((w) => w.rect_m);
  const gap = (r: number[], p: XY) => Math.hypot(Math.max(r[0] - p[0], 0, p[0] - r[2]), Math.max(r[1] - p[1], 0, p[1] - r[3]));
  // every walkway a few metres from the point is a way on (the nearest one may not join the rest)
  const around = (p: XY) => { const d = ws.map((r) => gap(r, p)); const m = Math.min(...d); return ws.map((_, i) => i).filter((i) => d[i] <= m + 4); };
  const touch = (a: number[], b: number[]) => a[0] <= b[2] + 0.3 && b[0] <= a[2] + 0.3 && a[1] <= b[3] + 0.3 && b[1] <= a[3] + 0.3;
  const starts = around(from), ends = new Set(around(to));
  const prev = new Map<number, number>(starts.map((i) => [i, -1]));
  const q = [...starts];
  let t = -1;
  while (q.length) {
    const c = q.shift()!;
    if (ends.has(c)) { t = c; break; }
    ws.forEach((r, i) => { if (!prev.has(i) && touch(ws[c], r)) { prev.set(i, c); q.push(i); } });
  }
  if (t < 0) return [from, to];
  const chain: number[] = [];
  for (let c = t; c !== -1; c = prev.get(c)!) chain.unshift(c);
  const mid = (r: number[]): XY => [(r[0] + r[2]) / 2, (r[1] + r[3]) / 2];
  const clampTo = (r: number[], p: XY): XY => [Math.min(Math.max(p[0], r[0]), r[2]), Math.min(Math.max(p[1], r[1]), r[3])];
  const out: XY[] = [from, clampTo(ws[chain[0]], from)];
  for (let i = 1; i < chain.length; i++) {
    const a = ws[chain[i - 1]], b = ws[chain[i]];
    // the joint: the overlap's centre, entered along the first walkway's axis
    const j: XY = [(Math.max(a[0], b[0]) + Math.min(a[2], b[2])) / 2, (Math.max(a[1], b[1]) + Math.min(a[3], b[3])) / 2];
    const last = out[out.length - 1];
    const horizontal = a[2] - a[0] > a[3] - a[1];
    out.push(horizontal ? [j[0], last[1]] : [last[0], j[1]], j);
    void mid;
  }
  out.push(clampTo(ws[chain[chain.length - 1]], to), to);
  return out.filter((p, i) => i === 0 || Math.hypot(p[0] - out[i - 1][0], p[1] - out[i - 1][1]) > 0.2);
}
