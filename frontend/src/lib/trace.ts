/**
 * Movement-trace rendering contract (PRD §18.1, §19.3, §29):
 *   green solid  = observed, only inside one camera's continuous track and only between placed points;
 *   amber dashed = hypothesized link between two observed segments;
 *   grey         = unknown interval, drawn as a gap (no path).
 * The backend's /replay already obeys this. These functions re-check it defensively so a malformed payload can
 * never make the UI draw more certainty than the evidence has: solid runs are split at any unplaced point and at
 * any unknown interval that falls inside them.
 */
import type { ReplayGap, ReplayLink, ReplayObject, ReplayPoint } from "./types";

export interface SolidRun {
  key: string;
  cameraId: string;
  trackId: string;
  points: ReplayPoint[]; // >= 2 placed points, chronological
}

export interface DashedLink {
  key: string;
  from: ReplayPoint;
  to: ReplayPoint;
  link: ReplayLink;
}

export interface TraceModel {
  solid: SolidRun[];
  singles: ReplayPoint[]; // a placed observation that forms no run: a marker, never a line
  unplaced: ReplayPoint[]; // image_only / zone_only points: timeline and source only
  dashed: DashedLink[];
  gaps: ReplayGap[];
}

const ms = (iso: string) => Date.parse(iso);

function crossesGap(a: ReplayPoint, b: ReplayPoint, gaps: ReplayGap[]): boolean {
  const t0 = ms(a.t);
  const t1 = ms(b.t);
  return gaps.some((g) => ms(g.start) < t1 && ms(g.end) > t0);
}

export function buildTrace(obj: ReplayObject): TraceModel {
  const solid: SolidRun[] = [];
  const singles: ReplayPoint[] = [];
  const unplaced: ReplayPoint[] = [];
  const byObs = new Map<string, ReplayPoint>();
  for (const seg of obj.segments) {
    if (seg.kind !== "observed") continue;
    let run: ReplayPoint[] = [];
    let n = 0;
    const flush = () => {
      if (run.length >= 2) {
        solid.push({ key: `${seg.track_id}:${n++}`, cameraId: seg.camera_id, trackId: seg.track_id, points: run });
      } else if (run.length === 1) {
        singles.push(run[0]);
      }
      run = [];
    };
    const pts = [...seg.points].sort((a, b) => ms(a.t) - ms(b.t));
    for (const p of pts) {
      byObs.set(p.observation_id, p);
      if (!p.floor_xy_m) {
        unplaced.push(p);
        flush();
        continue;
      }
      const prev = run[run.length - 1];
      if (prev && crossesGap(prev, p, obj.gaps)) flush();
      run.push(p);
    }
    flush();
  }
  const dashed: DashedLink[] = [];
  for (const l of obj.links) {
    const from = byObs.get(l.from);
    const to = byObs.get(l.to);
    if (l.kind === "hypothesized" && from?.floor_xy_m && to?.floor_xy_m) {
      dashed.push({ key: `${l.from}->${l.to}`, from, to, link: l });
    }
  }
  return { solid, singles, unplaced, dashed, gaps: obj.gaps };
}

/** True when no solid run spans any part of an unknown interval. */
export function solidNeverBridgesGaps(t: TraceModel): boolean {
  return t.solid.every((r) => r.points.every((p, i) => i === 0 || !crossesGap(r.points[i - 1], p, t.gaps)));
}

export const EVIDENCE_STYLE = {
  observed: { label: "Observed", pattern: "solid line", color: "var(--ev-observed)" },
  estimated: { label: "Estimated", pattern: "ring", color: "var(--ev-estimated)" },
  hypothesized: { label: "Hypothesis", pattern: "dashed line", color: "var(--ev-hypothesis)" },
  unknown: { label: "Unknown", pattern: "gap, no path", color: "var(--ev-unknown)" },
  contradicted: { label: "Contradicted", pattern: "crossed", color: "var(--ev-contradicted)" },
} as const;
