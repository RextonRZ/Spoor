/**
 * Hub conveyance topology for DRAWING hypothesis links (review 005 #1) and trace height (#2).
 * A hypothesized link between two observations that both sit on known conveyance is drawn along that conveyance
 * (the sorter loop runs counter-clockwise seen from above; chutes leave the north straight). It stays an amber dashed
 * hypothesis: the route is the only physical path, not an observation. Without known conveyance it stays straight.
 */
export interface LoopSpec {
  south_y: number;
  north_y: number;
  radius: number;
  west_cx: number;
  east_cx: number;
  cy: number;
  deck_height: number;
}

export interface ChuteSpec {
  id: string;
  x: number;
  mouth_y: number;
  end_y: number;
  width: number;
}

type P = [number, number];

export function loopLength(l: LoopSpec): number {
  return 2 * (l.east_cx - l.west_cx) + 2 * Math.PI * l.radius;
}

/** Point at arc length s (0 = west end of the south straight, increasing counter-clockwise = direction of travel). */
export function loopPoint(l: LoopSpec, s: number): P {
  const straight = l.east_cx - l.west_cx;
  const arc = Math.PI * l.radius;
  const L = loopLength(l);
  s = ((s % L) + L) % L;
  if (s < straight) return [l.west_cx + s, l.south_y];
  s -= straight;
  if (s < arc) {
    const a = -Math.PI / 2 + s / l.radius;
    return [l.east_cx + l.radius * Math.cos(a), l.cy + l.radius * Math.sin(a)];
  }
  s -= arc;
  if (s < straight) return [l.east_cx - s, l.north_y];
  s -= straight;
  const a = Math.PI / 2 + s / l.radius;
  return [l.west_cx + l.radius * Math.cos(a), l.cy + l.radius * Math.sin(a)];
}

/** Nearest loop arc length and distance for a floor point. */
export function loopProject(l: LoopSpec, [x, y]: P): { s: number; dist: number } {
  const L = loopLength(l);
  let best = { s: 0, dist: Infinity };
  for (let i = 0; i < 720; i++) {
    const s = (i / 720) * L;
    const [px, py] = loopPoint(l, s);
    const d = Math.hypot(px - x, py - y);
    if (d < best.dist) best = { s, dist: d };
  }
  return best;
}

function chuteAt(chutes: ChuteSpec[], [x, y]: P): ChuteSpec | undefined {
  return chutes.find((c) => Math.abs(x - c.x) <= c.width / 2 + 0.3 && y >= c.mouth_y - 0.6 && y <= c.end_y + 0.3);
}

/**
 * Route for drawing a hypothesis link from a to b. Returns floor points (site metres) and how it was routed.
 * - both on the loop: forward along the direction of travel;
 * - a on the loop, b in a chute: along the loop to that chute's mouth, then down the chute;
 * - otherwise: straight.
 */
export function routeLink(l: LoopSpec, chutes: ChuteSpec[], a: P, b: P, onLoopTol = 1.0): { points: P[]; via: string } {
  const pa = loopProject(l, a);
  const chute = chuteAt(chutes, b);
  const pb = chute ? loopProject(l, [chute.x, l.north_y]) : loopProject(l, b);
  if (pa.dist > onLoopTol || (!chute && pb.dist > onLoopTol)) return { points: [a, b], via: "straight" };
  const L = loopLength(l);
  const span = (((pb.s - pa.s) % L) + L) % L;
  const steps = Math.max(2, Math.ceil(span / 0.5));
  const pts: P[] = [a];
  for (let i = 1; i < steps; i++) pts.push(loopPoint(l, pa.s + (span * i) / steps));
  if (chute) pts.push([chute.x, l.north_y], [chute.x, chute.mouth_y]);
  pts.push(b);
  return { points: pts, via: chute ? `loop → chute ${chute.id}` : "loop" };
}

/** Surface height for drawing a floor_xy observation (the floor projection of a parcel on the deck or in a chute). */
export function surfaceHeight(l: LoopSpec, chutes: ChuteSpec[], p: P): number {
  if (chuteAt(chutes, p)) return 1.0;
  return loopProject(l, p).dist <= 0.6 ? l.deck_height + 0.05 : 0.12;
}
