/**
 * Hub conveyance topology for DRAWING hypothesis links (review 005 #1) and trace height (#2).
 * A hypothesized link between two observations that both sit on known conveyance is drawn along that conveyance
 * (the sorter loop runs counter-clockwise seen from above; chutes leave the north straight). It stays an amber dashed
 * hypothesis: the route is the only physical path, not an observation. Without known conveyance it stays straight.
 * Infeed: the hub can have more than one induction line (line A: induction, tunnel, merge; line B since 30 Oct).
 * Feeder chains come from the site plan's belts (end-to-start joints, last point on the loop); none is listed here.
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

export interface ConveyorSpec {
  id: string;
  kind: string;
  path: [number, number][];
  height: number;
  /** per-point deck heights when the belt ramps (e.g. line B up through its DWS arch) */
  heights?: number[];
}

/** One infeed: belts joined end to start, ending on the loop. */
export interface FeederChain {
  id: string; // belt ids joined with "+", e.g. "induction+tunnel_line+merge"
  path: P[];
  heights: number[];
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

/** Infeed chains from the site plan: belts whose end meets another belt's start are joined; a chain counts as a
 * feeder when its last point lies on the loop. Order = site-plan order of each chain's first belt. */
export function feederChains(l: LoopSpec, conveyors: ConveyorSpec[], joinTol = 0.3, onLoopTol = 0.6): FeederChain[] {
  const belts = conveyors.filter((c) => c.kind === "belt" && c.path.length >= 2);
  const near = (a: P, b: P) => Math.hypot(a[0] - b[0], a[1] - b[1]) <= joinTol;
  const next = (c: ConveyorSpec) => belts.find((d) => d !== c && near(c.path[c.path.length - 1], d.path[0]));
  const isTarget = new Set(belts.map(next).filter(Boolean));
  const out: FeederChain[] = [];
  for (const start of belts.filter((c) => !isTarget.has(c))) {
    const ids: string[] = [];
    const path: P[] = [];
    const heights: number[] = [];
    const seen = new Set<ConveyorSpec>();
    for (let c: ConveyorSpec | undefined = start; c && !seen.has(c); c = next(c)) {
      seen.add(c);
      ids.push(c.id);
      const belt = c;
      belt.path.forEach((q, i) => {
        if (path.length && i === 0) return; // shared joint
        path.push(q);
        heights.push(belt.heights?.[i] ?? belt.height);
      });
    }
    if (loopProject(l, path[path.length - 1]).dist <= onLoopTol) out.push({ id: ids.join("+"), path, heights });
  }
  return out;
}

/** Nearest point on a polyline: arc length along it, distance, and the interpolated height. */
export function polylineProject(path: P[], heights: number[], [x, y]: P): { s: number; dist: number; z: number } {
  let best = { s: 0, dist: Infinity, z: heights[0] ?? 0 };
  let acc = 0;
  for (let i = 0; i + 1 < path.length; i++) {
    const [ax, ay] = path[i];
    const [bx, by] = path[i + 1];
    const len = Math.hypot(bx - ax, by - ay);
    const t = len ? Math.max(0, Math.min(1, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / (len * len))) : 0;
    const d = Math.hypot(ax + t * (bx - ax) - x, ay + t * (by - ay) - y);
    if (d < best.dist) best = { s: acc + t * len, dist: d, z: heights[i] + t * (heights[i + 1] - heights[i]) };
    acc += len;
  }
  return best;
}

function feederAt(chains: FeederChain[], p: P, tol: number) {
  let best: { chain: FeederChain; s: number; dist: number } | null = null;
  for (const chain of chains) {
    const r = polylineProject(chain.path, chain.heights, p);
    if (r.dist <= tol && (!best || r.dist < best.dist)) best = { chain, s: r.s, dist: r.dist };
  }
  return best;
}

/** Joint points of a chain after arc length s, up to its end (the merge onto the loop). */
function chainFrom(chain: FeederChain, s: number): P[] {
  const out: P[] = [];
  let acc = 0;
  for (let i = 0; i + 1 < chain.path.length; i++) {
    acc += Math.hypot(chain.path[i + 1][0] - chain.path[i][0], chain.path[i + 1][1] - chain.path[i][1]);
    if (acc > s) out.push(chain.path[i + 1]);
  }
  return out;
}

function chuteAt(chutes: ChuteSpec[], [x, y]: P): ChuteSpec | undefined {
  return chutes.find((c) => Math.abs(x - c.x) <= c.width / 2 + 0.3 && y >= c.mouth_y - 0.6 && y <= c.end_y + 0.3);
}

/**
 * Route for drawing a hypothesis link from a to b. Returns floor points (site metres) and how it was routed.
 * - both on the loop: forward along the direction of travel;
 * - a on the loop, b in a chute: along the loop to that chute's mouth, then down the chute;
 * - a on an infeed line (any induction line in the site plan), b on the loop or in a chute: along that line to its own
 *   merge, then as above (a line-B parcel never passes line A's merge);
 * - otherwise: straight.
 */
export function routeLink(l: LoopSpec, chutes: ChuteSpec[], a: P, b: P, onLoopTol = 1.0,
  conveyors: ConveyorSpec[] = []): { points: P[]; via: string } {
  const chute = chuteAt(chutes, b);
  const pb = chute ? loopProject(l, [chute.x, l.north_y]) : loopProject(l, b);
  if (!chute && pb.dist > onLoopTol) return { points: [a, b], via: "straight" };
  let pa = loopProject(l, a);
  const pts: P[] = [a];
  let via = "";
  if (pa.dist > onLoopTol) {
    const feed = feederAt(feederChains(l, conveyors), a, onLoopTol);
    if (!feed) return { points: [a, b], via: "straight" };
    const along = chainFrom(feed.chain, feed.s);
    pts.push(...along);
    pa = loopProject(l, along[along.length - 1] ?? a);
    via = `${feed.chain.id} → `;
  }
  const L = loopLength(l);
  const span = (((pb.s - pa.s) % L) + L) % L;
  const steps = Math.max(2, Math.ceil(span / 0.5));
  for (let i = 1; i < steps; i++) pts.push(loopPoint(l, pa.s + (span * i) / steps));
  if (chute) pts.push([chute.x, l.north_y], [chute.x, chute.mouth_y]);
  pts.push(b);
  return { points: pts, via: via + (chute ? `loop → chute ${chute.id}` : "loop") };
}

/** Surface height for drawing a floor_xy observation (the floor projection of a parcel on the deck, an infeed belt or
 * in a chute). Infeed belts use their own deck heights from the site plan, ramps included. */
export function surfaceHeight(l: LoopSpec, chutes: ChuteSpec[], p: P, conveyors: ConveyorSpec[] = []): number {
  if (chuteAt(chutes, p)) return 1.0;
  if (loopProject(l, p).dist <= 0.6) return l.deck_height + 0.05;
  for (const c of conveyors) {
    if (c.kind !== "belt" || c.path.length < 2) continue;
    const r = polylineProject(c.path, c.path.map((_, i) => c.heights?.[i] ?? c.height), p);
    if (r.dist <= 0.6) return Math.round((r.z + 0.05) * 1000) / 1000;
  }
  return 0.12;
}
