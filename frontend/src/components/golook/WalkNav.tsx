"use client";
/**
 * Spoor Floor's Map tab: walking directions to the search place (reviewer 09:35, Rexton's plan). Indoors there is no
 * GPS: the start is where the worker last scanned (the supervisor's office, where tasks are handed out) and, while
 * walking, the nearest pillar marker (QR or BLE on the hub's columns). In the demo the walk is simulated along the route
 * (said in LIMITATIONS, not here).
 *
 * 3D: a Blender follow camera along the route over the hub model only (assets/tour/walk_render.py), with the route
 * ribbon, the place and the landmark names drawn here in true perspective from each frame's projection matrix.
 * 2D: the hub plan turned so the walk runs up the screen, only walls, walkways and the landmarks the directions name.
 * The directions (banner) come from the route's own geometry: its legs, turns and what each leg passes.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import type { XY } from "@/lib/journey";
import { HUB } from "@/lib/hub";
import "./walknav.css";

interface Walk { fps: number; frames: number; size: [number, number]; route: [number, number][]; length_m: number; s: number[]; P: number[][] }
type Zone = { id: string; kind: string; polygons: number[][][] };
const ZONES = (HUB as unknown as { zones: Zone[] }).zones;
const COLUMNS = (HUB as unknown as { building: { columns: number[][]; footprint_m: [number, number] } }).building;
const WALKWAYS = (HUB as unknown as { walkways: { rect_m: number[] }[] }).walkways.map((w) => w.rect_m);
// the landmarks a worker would name (the plan's own names are longer than a direction needs)
const LANDMARK: Record<string, string> = { Z05: "sorter loop", Z06: "chute row", Z10: "cage bays", Z12: "outbound dock", Z08: "exception bench",
  Z04: "scan tunnel", Z02: "bag-opening benches", Z03: "induction belts", Z01: "inbound dock", Z09: "oversize area", Z13: "office" };
const WALK_MS = 1.2;   // a brisk walk, m/s (for "about n min")
const SIM_MS = 4;      // the simulated walk without a 3D render plays at this many metres per second

const sub = (a: XY, b: XY): XY => [a[0] - b[0], a[1] - b[1]];
const len = (a: XY) => Math.hypot(a[0], a[1]);
const rectOf = (poly: number[][]) => [Math.min(...poly.map((p) => p[0])), Math.min(...poly.map((p) => p[1])), Math.max(...poly.map((p) => p[0])), Math.max(...poly.map((p) => p[1]))];
const rectGap = (r: number[], p: XY) => Math.hypot(Math.max(r[0] - p[0], 0, p[0] - r[2]), Math.max(r[1] - p[1], 0, p[1] - r[3]));
const metres = (m: number) => m >= 20 ? Math.round(m / 5) * 5 : Math.max(1, Math.round(m));

/** the route as legs: segments joined where the way bends less than 35 degrees */
function legsOf(route: XY[]) {
  const legs: { a: XY; b: XY; len: number; s0: number }[] = [];
  for (let i = 1; i < route.length; i++) {
    const a = route[i - 1], b = route[i], d = len(sub(b, a));
    if (d < 0.05) continue;
    const last = legs.at(-1);
    if (last) {
      const u = sub(last.b, last.a), v = sub(b, a);
      const ang = Math.acos(Math.max(-1, Math.min(1, (u[0] * v[0] + u[1] * v[1]) / (len(u) * len(v)))));
      if (ang < (35 * Math.PI) / 180) { last.b = b; last.len = len(sub(b, last.a)); continue; }
    }
    legs.push({ a, b, len: d, s0: 0 });
  }
  // lengths along the route (the merged legs are measured straight; the walk is measured along the route)
  let s = 0; for (const l of legs) { l.s0 = s; s += l.len; }
  return legs;
}
/** left or right, as the walker turns from leg u to leg v (x east, y north) */
const side = (u: XY, v: XY) => u[0] * v[1] - u[1] * v[0] > 0 ? "left" : "right";
/** the landmark a leg runs past, and on which side */
function past(a: XY, b: XY, skip: string | undefined) {
  let best: { name: string; score: number; side: string } | null = null;
  const dir = sub(b, a), L = len(dir);
  for (const z of ZONES) {
    if (!LANDMARK[z.id] || z.id === skip) continue;
    const r = rectOf(z.polygons[0]);
    // what the leg runs alongside, the closer the better (a walkway through the chute row beats the loop 4 m away)
    let hits = 0, score = 0;
    for (let t = 0.1; t < 1; t += 0.1) { const g = rectGap(r, [a[0] + dir[0] * t, a[1] + dir[1] * t]); if (g < 5) { hits++; score += 5 - g; } }
    if (hits >= 3 && (!best || score > best.score)) {
      const c: XY = [(r[0] + r[2]) / 2 - a[0], (r[1] + r[3]) / 2 - a[1]];
      best = { name: LANDMARK[z.id], score, side: side(dir, c) };
    }
  }
  return L > 6 ? best : null;
}

export interface Direction { icon: "straight" | "left" | "right" | "here"; text: string; dist: string | null; then: string | null }
export function directions(route: XY[], s: number, dest: string, destZone?: string): Direction {
  const legs = legsOf(route);
  const total = legs.reduce((a, l) => a + l.len, 0);
  if (!legs.length || s >= total - 0.5) return { icon: "here", text: `You're at the ${dest}`, dist: null, then: null };
  const i = Math.max(0, legs.findIndex((l) => s < l.s0 + l.len));
  const leg = legs[i], left = leg.s0 + leg.len - s, next = legs[i + 1];
  const turnWords = (k: number) => {
    const u = sub(legs[k].b, legs[k].a), v = sub(legs[k + 1].b, legs[k + 1].a), dir = side(u, v);
    if (k + 1 === legs.length - 1) return { dir, text: `${dest[0].toUpperCase()}${dest.slice(1)} on your ${dir}` };
    if (k + 2 === legs.length - 1 && legs[k + 1].len < 14) return { dir, text: `Turn ${dir} towards the ${dest}` };
    const lm = past(legs[k + 1].a, legs[k + 1].b, destZone);
    return { dir, text: lm ? `Turn ${dir} at the ${lm.name}` : `Turn ${dir}` };
  };
  if (!next) return { icon: "straight", text: `The ${dest} is ahead`, dist: `${metres(left)} m`, then: null };
  const turn = turnWords(i);
  if (left > 15) {
    const lm = past(leg.a, leg.b, destZone);
    return { icon: "straight", text: lm ? `Walk past the ${lm.name}` : "Keep walking", dist: `${metres(left)} m`, then: turn.text };
  }
  return { icon: turn.dir as "left" | "right", text: turn.text, dist: `In ${metres(left)} m`, then: null };
}

/** the point s metres along the route, and the way it faces there */
function along(route: XY[], s: number): { p: XY; d: XY } {
  let rest = Math.max(0, s);
  for (let i = 1; i < route.length; i++) {
    const a = route[i - 1], b = route[i], d = sub(b, a), L = len(d);
    if (rest <= L || i === route.length - 1) {
      const u = L ? Math.min(1, rest / L) : 0;
      return { p: [a[0] + d[0] * u, a[1] + d[1] * u], d: L ? [d[0] / L, d[1] / L] : [0, 1] };
    }
    rest -= L;
  }
  return { p: route[0], d: [0, 1] };
}
const routeLen = (r: XY[]) => r.reduce((a, p, i) => i ? a + len(sub(p, r[i - 1])) : 0, 0);
/** the pillar marker nearest the walker (the hub's columns, numbered P1 to Pn in the plan's order) */
function marker(p: XY) {
  let best = -1, bd = 7;
  COLUMNS.columns.forEach((c, i) => { const d = Math.hypot(c[0] - p[0], c[1] - p[1]); if (d < bd) { bd = d; best = i; } });
  return best >= 0 ? `P${best + 1}` : null;
}

export function WalkNav({ walkKey, route: fallback, dest, destZone, destPoly, onSearch, onNavigating }: {
  walkKey: string | null; route: XY[]; dest: string; destZone?: string; destPoly?: number[][]; onSearch: () => void; onNavigating?: (on: boolean) => void;
}) {
  const [walk, setWalk] = useState<Walk | null>(null);
  const [view, setView] = useState<"3d" | "2d">("3d");
  const [phase, setPhase] = useState<"idle" | "walk" | "here">("idle");
  const [s, setS] = useState(0);
  const [f, setF] = useState(0);
  const video = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (!walkKey) return;
    let live = true;
    fetch(`/tour/walk/${walkKey}/walk.json`).then((r) => r.ok ? r.json() : null).then((j) => { if (live && j && !j.test) setWalk(j); }).catch(() => {});
    return () => { live = false; };
  }, [walkKey]);
  const route: XY[] = useMemo(() => walk ? walk.route.map((p) => [p[0], p[1]] as XY) : fallback, [walk, fallback]);
  const L = useMemo(() => routeLen(route), [route]);
  const has3d = !!walk;
  const v3 = has3d && view === "3d";

  // one clock for both views: the 3D video's frame when there is one (it plays hidden under the 2D plan), else a timer
  useEffect(() => {
    if (phase !== "walk") return;
    let id = 0, t0 = -1;
    const tick = (now: number) => {
      const v = video.current;
      if (walk && v) {
        const k = Math.min(walk.frames - 1, Math.floor(v.currentTime * walk.fps));
        setF(k); setS(walk.s[Math.min(k, walk.s.length - 1)]);
        if (v.ended) { setPhase("here"); onNavigating?.(false); return; }
      } else {
        if (t0 < 0) t0 = now;
        const ns = Math.min(L, ((now - t0) / 1000) * SIM_MS);
        setS(ns);
        if (ns >= L) { setPhase("here"); onNavigating?.(false); return; }
      }
      id = requestAnimationFrame(tick);
    };
    id = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(id);
  }, [phase, walk, L, onNavigating]);

  const start = () => {
    setS(0); setF(0); setPhase("walk"); onNavigating?.(true);
    const v = video.current; if (v) { v.currentTime = 0; void v.play(); }
  };
  const end = () => {
    video.current?.pause();
    if (video.current) video.current.currentTime = 0;
    setPhase("idle"); setS(0); setF(0); onNavigating?.(false);
  };
  useEffect(() => () => onNavigating?.(false), [onNavigating]);

  const dir = phase === "here" ? directions(route, L, dest, destZone) : directions(route, s, dest, destZone);
  const leftM = Math.max(0, L - s), mins = Math.max(1, Math.round(leftM / WALK_MS / 60));
  const at = along(route, s);
  const where = phase === "idle" ? "Position: last scan at the office" : marker(at.p) ? `Position: marker ${marker(at.p)}` : "Position: last scan at the office";

  return (
    <div className="wn" data-phase={phase}>
      <div className="wn-map">
        {has3d && <video ref={video} className="wn-video" data-shown={v3 ? "" : undefined} src={`/tour/walk/${walkKey}/walk.mp4`} muted playsInline preload="auto"
          aria-label={`A 3D view of the walk to the ${dest}`} />}
        {v3 && walk && <Overlay3D walk={walk} f={phase === "here" ? walk.frames - 1 : f} route={route} s={phase === "here" ? L : s} dest={dest} destPoly={destPoly} destZone={destZone} />}
        {!v3 && <Plan2D route={route} s={phase === "idle" ? 0 : phase === "here" ? L : s} walking={phase !== "idle"} dest={dest} destPoly={destPoly} destZone={destZone} />}
      </div>

      <div className="wn-banner" data-icon={dir.icon} role="status" aria-live="polite">
        <span className="wn-arrow" aria-hidden key={dir.icon}><Arrow icon={dir.icon} /></span>
        <span className="wn-say" key={`${dir.icon}|${dir.text}`}>
          {phase === "idle" ? <><b>{dir.dist ? `${dir.text}, ${dir.dist.replace(/^In /, "")}` : dir.text}</b><small>Then {dir.then ? dir.then.toLowerCase() : "follow the line"}</small></>
            : <>{dir.dist && <em>{dir.dist}</em>}<b>{dir.text}</b>{dir.then && <small>Then {dir.then[0].toLowerCase()}{dir.then.slice(1)}</small>}</>}
        </span>
      </div>
      {has3d && phase !== "here" && (
        <div className="wn-seg" role="group" aria-label="Map view">
          <button type="button" aria-pressed={view === "3d"} onClick={() => setView("3d")}>3D</button>
          <button type="button" aria-pressed={view === "2d"} onClick={() => setView("2d")}>2D</button>
        </div>
      )}

      <div className="wn-sheet">
        {phase === "here" ? (
          <>
            <div className="wn-sum"><b>Search the {dest}</b><small>{where}</small></div>
            <button type="button" className="wn-go" onClick={onSearch}>Start search</button>
          </>
        ) : (
          <>
            <div className="wn-sum">
              <b>{phase === "idle" ? `${dest[0].toUpperCase()}${dest.slice(1)}` : `${metres(leftM)} m · about ${mins} min`}</b>
              <small>{phase === "idle" ? `${metres(L)} m · about ${mins} min walk` : where}</small>
              {phase === "idle" && <small className="wn-fine">{where}</small>}
            </div>
            {phase === "idle"
              ? <button type="button" className="wn-go" onClick={start}>Start</button>
              : <button type="button" className="wn-end" onClick={end}>End</button>}
          </>
        )}
      </div>
    </div>
  );
}

function Arrow({ icon }: { icon: Direction["icon"] }) {
  if (icon === "here") return <svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>;
  if (icon === "left") return <svg viewBox="0 0 24 24"><path d="M15 21v-7a4 4 0 0 0-4-4H5M9 6l-4 4 4 4" /></svg>;
  if (icon === "right") return <svg viewBox="0 0 24 24"><path d="M9 21v-7a4 4 0 0 1 4-4h6M15 6l4 4-4 4" /></svg>;
  return <svg viewBox="0 0 24 24"><path d="M12 21V4M6 10l6-6 6 6" /></svg>;
}

/** the measured size of an element (for drawing over a cover-fitted picture) */
function useSize() {
  const ref = useRef<HTMLDivElement>(null);
  const [sz, setSz] = useState<[number, number]>([0, 0]);
  useEffect(() => {
    const el = ref.current; if (!el) return;
    const ro = new ResizeObserver(([e]) => setSz([e.contentRect.width, e.contentRect.height]));
    ro.observe(el); return () => ro.disconnect();
  }, []);
  return [ref, sz] as const;
}

function Overlay3D({ walk, f, route, s, dest, destPoly, destZone }: { walk: Walk; f: number; route: XY[]; s: number; dest: string; destPoly?: number[][]; destZone?: string }) {
  const [ref, [W, H]] = useSize();
  const P = walk.P[Math.min(f, walk.P.length - 1)];
  // the picture is cover-fitted: where a point of the image lands in this box
  const k = Math.max(W / walk.size[0], H / walk.size[1]), dw = walk.size[0] * k, dh = walk.size[1] * k, ox = (W - dw) / 2, oy = (H - dh) / 2;
  const proj = (x: number, y: number, z = 0): [number, number] | null => {
    const cx = P[0] * x + P[1] * y + P[2] * z + P[3], cy = P[4] * x + P[5] * y + P[6] * z + P[7], cw = P[12] * x + P[13] * y + P[14] * z + P[15];
    if (cw < 0.6) return null;
    return [ox + ((cx / cw + 1) / 2) * dw, oy + ((1 - cy / cw) / 2) * dh];
  };
  const pts = (xs: ([number, number] | null)[]) => xs.every(Boolean) ? xs.map((p) => p!.join(",")).join(" ") : null;

  // the ribbon: the route still to walk, 1.1 m wide on the floor, its edges offset along the smoothed direction
  const L = routeLen(route), lefts: [number, number][] = [], rights: [number, number][] = [];
  for (let d = s; d <= L + 0.01; d += 0.5) {
    const { p } = along(route, d), a = along(route, d - 0.8).p, b = along(route, d + 0.8).p;
    const t = sub(b, a), tl = len(t) || 1, n: XY = [-t[1] / tl * 0.55, t[0] / tl * 0.55];
    const l = proj(p[0] + n[0], p[1] + n[1], 0.03), r = proj(p[0] - n[0], p[1] - n[1], 0.03);
    if (l && r) { lefts.push(l); rights.push(r); }
  }
  const ribbon = lefts.length > 1 ? [...lefts, ...rights.reverse()].map((p) => p.join(",")).join(" ") : null;
  const me = along(route, s), mp = proj(me.p[0], me.p[1], 0.03), ahead = proj(me.p[0] + me.d[0] * 2.2, me.p[1] + me.d[1] * 2.2, 0.03);

  // the place: its floor and walls to 2.4 m, drawn as a soft volume
  const poly = destPoly ?? [];
  const floor = pts(poly.map((q) => proj(q[0], q[1], 0.02)));
  const walls = poly.map((q, i) => { const r = poly[(i + 1) % poly.length]; return pts([proj(q[0], q[1], 0), proj(r[0], r[1], 0), proj(r[0], r[1], 2.4), proj(q[0], q[1], 2.4)]); });
  const top = pts(poly.map((q) => proj(q[0], q[1], 2.4)));
  const c = poly.length ? [poly.reduce((a, q) => a + q[0], 0) / poly.length, poly.reduce((a, q) => a + q[1], 0) / poly.length] : null;
  // the place's name only where it reads whole: clear of the edges, the banner and the 3D/2D switch
  const tagAt = c ? proj(c[0], c[1], 3.2) : null;
  const destTag = tagAt && tagAt[0] > 80 && tagAt[0] < W - 80 && tagAt[1] > 180 && tagAt[1] < H - 120 ? tagAt : null;

  const placed: number[][] = [];   // names already placed: [x, y, width]
  // landmark names, big: the nearest three in view, never the place itself
  const marks = ZONES.filter((z) => LANDMARK[z.id] && z.id !== destZone).map((z) => {
    const r = rectOf(z.polygons[0]), m: XY = [(r[0] + r[2]) / 2, (r[1] + r[3]) / 2];
    return { id: z.id, name: LANDMARK[z.id], d: Math.hypot(m[0] - me.p[0], m[1] - me.p[1]), at: proj(m[0], m[1], 2.6) };
  }).filter((m) => m.at && m.d < 40 && m.at[0] > 30 && m.at[0] < W - 30 && m.at[1] > 150 && m.at[1] < H - 150).sort((a, b) => a.d - b.d).slice(0, 3)
    // a name never covers the route: lifted clear of the ribbon if it can be, else left out
    .map((m) => {
      const w = m.name.length * 8.5 + 22, hits = (y: number) => placed.some((b) => Math.abs(b[0] - m.at![0]) < (b[2] + w) / 2 + 6 && Math.abs(b[1] - y) < 36), onRoute = (y: number) => lefts.some((l, i) => { const r = rights[rights.length - 1 - i] ?? l, x = (l[0] + r[0]) / 2, yy = (l[1] + r[1]) / 2;
        return x > m.at![0] - w / 2 - 6 && x < m.at![0] + w / 2 + 6 && yy > y - 21 && yy < y + 21; });
      for (const dy of [0, -36, 36, -72]) {
        const y = m.at![1] + dy;
        if (!onRoute(y) && !hits(y) && y > 150) { placed.push([m.at![0], y, w]); return { ...m, at: [m.at![0], y] as [number, number] }; }
      }
      return null;
    }).filter((m): m is NonNullable<typeof m> => !!m);

  return (
    <div ref={ref} className="wn-over" aria-hidden>
      {W > 0 && (
        <svg width={W} height={H}>
          {walls.map((w, i) => w && <polygon key={i} className="wn-vol-wall" points={w} />)}
          {floor && <polygon className="wn-vol-floor" points={floor} />}
          {top && <polygon className="wn-vol-top" points={top} />}
          {ribbon && <polygon className="wn-ribbon" points={ribbon} />}
          {mp && ahead && <line className="wn-me-dir" x1={mp[0]} y1={mp[1]} x2={ahead[0]} y2={ahead[1]} />}
          {mp && <><circle className="wn-me-halo" cx={mp[0]} cy={mp[1]} r={16} /><circle className="wn-me" cx={mp[0]} cy={mp[1]} r={8} /></>}
        </svg>
      )}
      {marks.map((m) => <span key={m.id} className="wn-lm" style={{ left: m.at![0], top: m.at![1] }}>{m.name[0].toUpperCase() + m.name.slice(1)}</span>)}
      {destTag && <span className="wn-dest" style={{ left: destTag[0], top: destTag[1] }}>{dest[0].toUpperCase() + dest.slice(1)}</span>}
    </div>
  );
}

/** The plan, turned a quarter (north to the right) so the long side of the hall runs up the phone: walls, walkways,
 *  the landmarks the directions name, the place filled, the route 4 px with a start dot and an end pin. */
function Plan2D({ route, s, walking, dest, destPoly, destZone }: { route: XY[]; s: number; walking: boolean; dest: string; destPoly?: number[][]; destZone?: string }) {
  const [ref, [W, H]] = useSize();
  const [bw, bh] = COLUMNS.footprint_m;   // 60 x 40: x east, y north
  // screen: right = north (y), down = east (x)
  const padX = 28, padTop = 150, padBot = 150;
  const k = W && H ? Math.min((W - padX * 2) / bh, (H - padTop - padBot) / bw) : 1;
  const ox = (W - bh * k) / 2, oy = padTop + Math.max(0, (H - padTop - padBot - bw * k) / 2);
  const tp = (x: number, y: number): [number, number] => [ox + y * k, oy + x * k];
  const rect = (r: number[]) => { const a = tp(r[0], r[1]), b = tp(r[2], r[3]); return { x: Math.min(a[0], b[0]), y: Math.min(a[1], b[1]), width: Math.abs(b[0] - a[0]), height: Math.abs(b[1] - a[1]) }; };
  const line = (r: XY[]) => r.map((p) => tp(p[0], p[1]).join(",")).join(" ");
  const L = routeLen(route);
  const walked: XY[] = [], ahead: XY[] = [];
  let acc = 0;
  route.forEach((p, i) => {
    const seg = i ? len(sub(p, route[i - 1])) : 0;
    if (acc + seg <= s) walked.push(p); else { if (!ahead.length) { const m = along(route, s).p; walked.push(m); ahead.push(m); } ahead.push(p); }
    acc += seg;
  });
  const me = along(route, Math.min(s, L));
  const shown = ["Z06", "Z05", "Z10", "Z12", "Z13"].map((id) => ZONES.find((z) => z.id === id)!).filter((z) => z && z.id !== destZone);
  const end = tp(route.at(-1)![0], route.at(-1)![1]), st = tp(route[0][0], route[0][1]), mp = tp(me.p[0], me.p[1]);
  const dp = destPoly ? destPoly.map((q) => tp(q[0], q[1]).join(",")).join(" ") : null;
  const ten = 10 * k;
  // labels never sit on the route: try spots across the zone (or beside the place) and keep the first one clear of it
  const rpts: [number, number][] = [];
  route.forEach((p, i) => { if (!i) return; const a = tp(route[i - 1][0], route[i - 1][1]), b2 = tp(p[0], p[1]), n = Math.ceil(Math.hypot(b2[0] - a[0], b2[1] - a[1]) / 4);
    for (let j = 0; j <= n; j++) rpts.push([a[0] + (b2[0] - a[0]) * j / n, a[1] + (b2[1] - a[1]) * j / n]); });
  const taken: number[][] = [];
  const clear = (x: number, y: number, w: number, h: number) => !rpts.some(([px, py]) => px > x - 8 && px < x + w + 8 && py > y - 8 && py < y + h + 8)
    && !taken.some((t) => x < t[2] + 6 && t[0] < x + w + 6 && y < t[3] + 4 && t[1] < y + h + 4);
  const fit = (text: string, spots: [number, number][], big = false) => {
    const w = text.length * (big ? 8.2 : 7.2) + 18, h = big ? 28 : 24;
    const at = spots.find(([cx, cy]) => clear(cx - w / 2, cy - h / 2, w, h) && cx - w / 2 > 4 && cx + w / 2 < W - 4) ?? null;
    if (at) taken.push([at[0] - w / 2, at[1] - h / 2, at[0] + w / 2, at[1] + h / 2]);
    return at;
  };
  const destName = dest[0].toUpperCase() + dest.slice(1);
  const db = destPoly ? rect(rectOf(destPoly)) : null;
  const destAt = db ? fit(destName, [[db.x - destName.length * 4.1 - 18, db.y + 22], [db.x + db.width / 2, db.y + db.height + 22], [db.x - destName.length * 4.1 - 18, db.y + db.height / 2], [db.x + db.width / 2, db.y - 20]], true) : null;
  const labs = shown.map((z) => {
    const r = rect(rectOf(z.polygons[0])), name = LANDMARK[z.id][0].toUpperCase() + LANDMARK[z.id].slice(1);
    const cx = r.x + r.width / 2, cy = r.y + r.height / 2, dx = r.width * 0.3, dy = r.height * 0.3;
    // inside its own zone or not at all (beside it, a name reads as the neighbour's)
    return { id: z.id, name, at: fit(name, [[cx, cy], [cx, cy - dy], [cx, cy + dy], [cx - dx, cy], [cx + dx, cy], [cx - dx, cy - dy], [cx + dx, cy + dy], [cx - dx, cy + dy], [cx + dx, cy - dy]]) };
  });
  return (
    <div ref={ref} className="wn-plan" role="img" aria-label={`Plan of the hub, the walk to the ${dest}`}>
      {W > 0 && (
        <svg width={W} height={H}>
          <rect className="wn-p-hall" {...rect([0, 0, bw, bh])} rx={4} />
          {WALKWAYS.map((w, i) => <rect key={i} className="wn-p-walk" {...rect(w)} />)}
          {shown.map((z) => <rect key={z.id} className="wn-p-zone" {...rect(rectOf(z.polygons[0]))} rx={3} />)}
          {dp && <polygon className="wn-p-dest" points={dp} />}
          {walking && walked.length > 1 && <polyline className="wn-p-done" points={line(walked)} />}
          <polyline className="wn-p-route" points={line(walking ? ahead : route)} />
          <circle className="wn-p-start" cx={st[0]} cy={st[1]} r={6} />
          <g transform={`translate(${end[0]} ${end[1]})`} className="wn-p-pin"><path d="M0 0c-5-7-9-11-9-16a9 9 0 0 1 18 0c0 5-4 9-9 16z" /><circle cx="0" cy="-16" r="3.4" /></g>
          {walking && <><circle className="wn-me-halo" cx={mp[0]} cy={mp[1]} r={15} /><circle className="wn-me" cx={mp[0]} cy={mp[1]} r={7.5} /></>}
          {/* scale and north, big enough to read */}
          <g transform={`translate(${ox} ${oy + bw * k + 22})`} className="wn-p-scale"><path d={`M0 0v6h${ten}v-6`} /><text x={ten + 8} y={8}>10 m</text></g>
          <g transform={`translate(${ox + bh * k - 14} ${oy - 26})`} className="wn-p-north"><path d="M-10 0h16M0 -6l7 6-7 6" /><text x={-34} y={5}>N</text></g>
        </svg>
      )}
      {labs.map((l) => l.at && <span key={l.id} className="wn-p-lab" style={{ left: l.at[0], top: l.at[1] }}>{l.name}</span>)}
      {destAt && <span className="wn-p-lab wn-p-lab-dest" style={{ left: destAt[0], top: destAt[1] }}>{destName}</span>}
    </div>
  );
}
