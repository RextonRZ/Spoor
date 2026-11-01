"use client";
/**
 * The hero's last beat: the case worked out on a whiteboard, in story order, the way an investigator would. A 3D
 * top-down sketch of the hub (an oblique projection of the canonical floor plan: walls with height, the sorter loop
 * raised), zoomed to where it happened, with the store that has no camera inside drawn hatched. Scene by scene the
 * route is drawn in green marker up to that moment, a numbered mark goes on it and the scene's note is written in the
 * column with the same number (no leader lines to cross). After the last scene an arrow goes in through the doorway,
 * only that last scene is circled, the records' claim is crossed out, and the verdict is written on a sticky note in
 * the Answer screen's shape (story.ts: the agent's own answer once it has one, else what the footage shows, labelled
 * so). Nothing is typed here. The sketching is an anime.js timeline the hero schedules and pauses.
 */
import { useMemo } from "react";
import { Caveat } from "next/font/google";
import { createTimeline, svg, utils, type Timeline } from "animejs";
import { ZONE_NAMES } from "@/lib/zones";
import { HUB, type Story } from "./story";

const hand = Caveat({ subsets: ["latin"], weight: ["500", "700"], display: "swap" });

// oblique projection: x east, y north, z up (metres) -> board units; looking north from above the south wall
const SHEAR = 0.32;
const DEPTH = 0.6;
const RISE = 0.85;
const pj = (x: number, y: number, z = 0): [number, number] => [x + y * SHEAR, 60 - y * DEPTH - z * RISE];
const pt = (x: number, y: number, z = 0) => pj(x, y, z).map((v) => v.toFixed(2)).join(",");
const poly = (pts: [number, number][], z = 0) => pts.map(([x, y]) => pt(x, y, z)).join(" ");

/** a hand-drawn line through points: a small seeded wobble, so the marker never looks ruled */
function rough(pts: [number, number][], seed: number, amp: number) {
  // the wobble comes from the point itself, so two strokes that share a point meet there exactly
  const rnd = (x: number, y: number, k: number) => {
    const v = Math.sin(x * 12.9898 + y * 78.233 + seed * 3.7 + k * 19.19) * 43758.5453;
    return v - Math.floor(v) - 0.5;
  };
  return pts.map(([x, y], i) => `${i ? "L" : "M"}${(x + rnd(x, y, 0) * amp).toFixed(2)},${(y + rnd(x, y, 1) * amp).toFixed(2)}`).join(" ");
}

/** a marker loop that closes a little past its start, the way a hand draws it */
function loopPath(cx: number, cy: number, rx: number, ry: number, amp: number) {
  const n = 30;
  const pts: [number, number][] = [];
  for (let i = 0; i <= n + 4; i++) {
    const a = -Math.PI * 0.6 + (i / n) * Math.PI * 2;
    const k = 1 + (i > n ? 0.07 : 0) + Math.sin(i * 1.7) * 0.03;
    pts.push([cx + Math.cos(a) * rx * k, cy + Math.sin(a) * ry * k]);
  }
  return rough(pts, 11, amp);
}

interface Note { t: number; lines: string[]; records?: boolean }

const BLIND = (HUB as unknown as { blind_corner?: { polygon: [number, number][] } }).blind_corner?.polygon ?? null;

function useBoard(story: Story) {
  return useMemo(() => {
    const d = story.data;
    const sc = d.scenario;
    const steps = story.steps;
    const picked = steps.find((s) => s.event === "picked");
    const carried = steps.filter((s) => s.event === "carried");
    const blind = steps.find((s) => s.event === "into_blind");
    const out = story.moments.find((m) => m.event === "out_empty");
    const cam = (c: string) => c.replace("_", " ");
    const two = (cams: string, caption: string) => {
      const [time, ...words] = caption.split(" · ");
      return words.length ? [`${cams} · ${time}`, words.join(" · ")] : [`${cams} · ${time}`];
    };
    // the scenes, in story order, each at its moment
    const notes: Note[] = [];
    if (story.opener) notes.push({ t: 0, lines: [story.opener.replace(/^Scan records: /, "Records: ").replace(/\.$/, "")], records: true });
    if (picked) notes.push({ t: sc.picked_t_s ?? 0, lines: two(cam(picked.camera), picked.caption) });
    if (carried.length) {
      const mid = carried[Math.floor(carried.length / 2)];
      notes.push({ t: ((mid.clip_f[0] + mid.clip_f[1]) / 2 - d.frames[0]) / d.fps, lines: two(carried.map((c) => cam(c.camera)).join(", "), carried[0].caption) });
    }
    if (blind) notes.push({ t: sc.enters_blind_t_s ?? 0, lines: [...two(cam(blind.camera), blind.caption), ...(out ? [out.caption] : [])] });
    const at = (t: number) => {
      let best = d.path[0];
      for (const p of d.path) if (Math.abs(p[0] - t) < Math.abs(best[0] - t)) best = p;
      return pj(best[1], best[2], 0.2);
    };
    // the route cut at each scene's moment: scene i draws the stretch since the scene before
    // (each stretch starts on the last point of the one before, so the marker line never breaks)
    const segs: [number, number][][] = [];
    let k0 = 0;
    notes.forEach((n) => {
      let k1 = k0;
      while (k1 + 1 < d.path.length && d.path[k1 + 1][0] <= n.t + 0.05) k1++;
      segs.push(d.path.slice(k0, k1 + 1).map(([, x, y]) => pj(x, y, 0.2)));
      k0 = k1;
    });
    const route = d.path.map(([, x, y]) => pj(x, y, 0.2));
    const pts = [...route, ...(BLIND ? BLIND.map(([x, y]) => pj(x, y)) : [])];
    const xs = pts.map((p) => p[0]);
    const ys = pts.map((p) => p[1]);
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const vbW = Math.max((x1 - x0) / 0.5, ((y1 - y0) / 0.5) * (16 / 9), 24);
    const vbH = (vbW * 9) / 16;
    const vb = { x: x0 - vbW * 0.05, y: (y0 + y1) / 2 - vbH * 0.45, w: vbW, h: vbH };
    return { notes: notes.map((n) => ({ ...n, p: at(n.t) })), segs, vb };
  }, [story]);
}

export function DetectiveBoard({ story, boardRef }: { story: Story; boardRef: React.Ref<SVGSVGElement> }) {
  const { notes, segs, vb } = useBoard(story);
  const [bw, bh] = HUB.building.footprint_m;
  const hub = HUB as unknown as { machines: { loop: { south_y: number; north_y: number; radius: number; west_cx: number; east_cx: number } } };
  const L = hub.machines.loop;
  const loop: [number, number][] = [];
  for (let i = 0; i <= 36; i++) {
    const a = (i / 36) * Math.PI * 2;
    const cx = Math.cos(a) >= 0 ? L.east_cx : L.west_cx;
    loop.push([cx + Math.cos(a) * L.radius, (L.south_y + L.north_y) / 2 + Math.sin(a) * L.radius]);
  }
  const u = vb.w / 100; // a hundredth of the board's width
  const fs = vb.h * 0.042;
  const colX = vb.x + vb.w * 0.62;
  const inView = (x: number, y: number) => x > vb.x && x < colX - u * 3 && y > vb.y && y < vb.y + vb.h;

  // the column: the notes in story order, numbered like their marks on the route
  const tops = notes.reduce<number[]>((acc, n) => [...acc, acc[acc.length - 1] + fs * 1.22 * n.lines.length + fs * 0.75], [vb.y + vb.h * 0.08]);
  const column = notes.map((n, i) => ({ n, i, y: tops[i] }));
  const yy = tops[tops.length - 1];
  // the marks: a numbered ring per scene on the route; scenes at the same spot sit side by side
  const RX = u * 4;
  const RY = u * 2.4;
  const marks = notes.reduce<[number, number][]>((acc, n, i) => {
    if (i === notes.length - 1) return [...acc, [n.p[0] + RX * 0.95, n.p[1] - RY - u * 2.2]]; // outside the circle
    // above its scene; slid left (away from the notes column) until it clears the marks already placed
    const m: [number, number] = [n.p[0], n.p[1] - u * 4.2];
    while (acc.some((a) => Math.hypot(a[0] - m[0], a[1] - m[1]) < u * 4.6)) m[0] -= u * 0.5;
    return [...acc, m];
  }, []);

  const lastScene = notes[notes.length - 1]?.p;
  // the circle's own note, under it in the same red: where the parcel was last seen, at the footage's clock
  const blindStep = story.steps.find((x) => x.event === "into_blind");
  const lastSeen = blindStep ? `last seen here · ${blindStep.caption.split(" · ")[0]}` : "last seen here";
  const blindPts = BLIND ? poly(BLIND) : null;
  const blindC = BLIND ? pj(BLIND.reduce((s, q) => s + q[0], 0) / BLIND.length, BLIND.reduce((s, q) => s + q[1], 0) / BLIND.length) : null;
  // the store's label at its far (west) end, left-aligned: clear of the doorway and its circle
  const blindLabel = BLIND
    ? pj(Math.min(...BLIND.map((q) => q[0])) + 1.2, (Math.min(...BLIND.map((q) => q[1])) + Math.max(...BLIND.map((q) => q[1]))) / 2)
    : null;
  // the arrow: from the doorway (the last scene) a short shaft into the store, then its head
  let arrow: string | null = null;
  if (lastScene && blindC) {
    const ang = Math.atan2(blindC[1] - lastScene[1], blindC[0] - lastScene[0]);
    const tip: [number, number] = [lastScene[0] + Math.cos(ang) * u * 5.5, lastScene[1] + Math.sin(ang) * u * 5.5];
    const wing = (d: number): [number, number] => [tip[0] + Math.cos(ang + Math.PI + d) * u * 1.8, tip[1] + Math.sin(ang + Math.PI + d) * u * 1.8];
    arrow = `${rough([[lastScene[0] + Math.cos(ang) * u * 1.4, lastScene[1] + Math.sin(ang) * u * 1.4], tip], 9, u * 0.1)} ${rough([wing(0.5), tip, wing(-0.5)], 4, u * 0.08)}`;
  }
  const zoneLabels = HUB.zones
    .map((z) => {
      const p = z.polygons[0];
      const [x, y] = pj(p.reduce((s, q) => s + q[0], 0) / p.length, p.reduce((s, q) => s + q[1], 0) / p.length);
      return { id: z.id, name: ZONE_NAMES[z.id] ?? z.name.replace(/\s*\(.*\)\s*$/, ""), x, y };
    })
    .filter((z) => inView(z.x, z.y) && !(BLIND && z.id === "Z11"));

  const v = story.verdict;
  const nx = colX - u * 2.5; // the sticky note
  const ny = Math.max(yy + fs * 0.6, vb.y + vb.h * 0.56);
  const nw = vb.x + vb.w - nx - u * 3;
  const nh = vb.y + vb.h - ny - u * 2.5;
  return (
    <svg ref={boardRef} className={`lp-board-svg ${hand.className}`} viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`} aria-hidden="true">
      <defs>
        <pattern id="lp-bd-hatch" width={u * 1.6} height={u * 1.6} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2={u * 1.6} className="lp-bd-hatch-line" />
        </pattern>
      </defs>
      <g className="lp-bd-plan">
        <polygon points={poly([[0, 0], [bw, 0], [bw, bh], [0, bh]])} className="lp-bd-floor" />
        <polygon points={`${pt(0, bh)} ${pt(bw, bh)} ${pt(bw, bh, 3)} ${pt(0, bh, 3)}`} className="lp-bd-wall" />
        <polygon points={`${pt(0, 0)} ${pt(0, bh)} ${pt(0, bh, 3)} ${pt(0, 0, 3)}`} className="lp-bd-wall lp-bd-wall-side" />
        {HUB.zones.flatMap((z) => z.polygons.map((p, k) => <polygon key={`${z.id}${k}`} points={poly(p)} className="lp-bd-zone" />))}
        {blindPts && <polygon points={blindPts} className="lp-bd-blind" />}
        <polyline points={poly(loop, 1.5)} className="lp-bd-loop" />
        <polyline points={poly(loop, 0)} className="lp-bd-loop lp-bd-loop-foot" />
        {HUB.cameras.map((c) => {
          const [x, y] = pj(c.position_m[0], c.position_m[1], 2.2);
          return <circle key={c.id} cx={x} cy={y} r={u * 0.55} className={story.seen.has(c.id) ? "lp-bd-cam is-seen" : "lp-bd-cam"} />;
        })}
        {zoneLabels.map((z) => (
          <text key={z.id} x={z.x} y={z.y} className="lp-bd-zone-label" style={{ fontSize: fs * 0.55 }}>{z.name}</text>
        ))}
        {blindLabel && (
          <text x={blindLabel[0]} y={blindLabel[1]} className="lp-bd-zone-label lp-bd-blind-label" style={{ fontSize: fs * 0.56 }}>
            {ZONE_NAMES.Z11 ?? "Store"} · no camera inside
          </text>
        )}
      </g>
      {segs.map((sg, i) =>
        sg.length > 1 ? (
          <g key={i} className="lp-bd-seg" data-seg={i}>
            <path d={rough(sg, 3, u * 0.25)} className="lp-bd-trail-bleed" />
            <path d={rough(sg, 3, u * 0.25)} className="lp-bd-trail" />
          </g>
        ) : null,
      )}
      {arrow && <path d={arrow} className="lp-bd-arrow" />}
      {column.map(({ n, i, y }) => (
        <g key={i} className="lp-bd-note" data-note={i}>
          <g className="lp-bd-dot">
            <path d={`M${n.p[0]},${n.p[1]} L${marks[i][0]},${marks[i][1]}`} className="lp-bd-pin-tick" />
            <circle cx={marks[i][0]} cy={marks[i][1]} r={u * 2} className="lp-bd-badge" />
            <text x={marks[i][0]} y={marks[i][1]} className="lp-bd-badge-n" textAnchor="middle" dominantBaseline="central" style={{ fontSize: fs * 1.05 }}>{i + 1}</text>
            <circle cx={colX - u * 2} cy={y - fs * 0.32} r={u * 1.3} className="lp-bd-badge" />
            <text x={colX - u * 2} y={y - fs * 0.32} className="lp-bd-badge-n" textAnchor="middle" dominantBaseline="central" style={{ fontSize: fs * 0.78 }}>{i + 1}</text>
          </g>
          <clipPath id={`lp-bd-c${i}`}>
            <rect x={colX - u * 0.2} y={y - fs * 1.1} width={0} height={fs * 1.25 * n.lines.length + fs} className="lp-bd-reveal" data-w={vb.w * 0.36} />
          </clipPath>
          <text x={colX} y={y} clipPath={`url(#lp-bd-c${i})`} style={{ fontSize: fs, strokeWidth: fs * 0.32 }}>
            {n.lines.map((line, k) => (
              <tspan key={k} x={colX} dy={k ? fs * 1.22 : 0}>{line}</tspan>
            ))}
          </text>
          {n.records && <path d={rough([[colX - u * 0.4, y - fs * 0.3], [colX + n.lines[0].length * fs * 0.14, y - fs * 0.38], [colX + n.lines[0].length * fs * 0.29, y - fs * 0.28]], 5, u * 0.15)} className="lp-bd-strike" />}
        </g>
      ))}
      {lastScene && <path d={loopPath(lastScene[0], lastScene[1], RX, RY, u * 0.12)} className="lp-bd-circle" />}
      {lastScene && (
        <g className="lp-bd-circle-note">
          <clipPath id="lp-bd-cc">
            <rect x={lastScene[0] + RX * 0.3 - vb.w * 0.34} y={lastScene[1] + RY} width={0} height={fs * 1.9} className="lp-bd-reveal" data-w={vb.w * 0.34 + u * 2} />
          </clipPath>
          <text x={lastScene[0] + RX * 0.3} y={lastScene[1] + RY + fs * 1.15} textAnchor="end" clipPath="url(#lp-bd-cc)" className="lp-bd-circle-label" style={{ fontSize: fs * 1.2, strokeWidth: fs * 0.3 }}>
            {lastSeen}
          </text>
        </g>
      )}
      {v && (
        <g className="lp-bd-verdict" data-source={v.source}>
          <g className="lp-bd-sticky" transform={`rotate(-1.6 ${nx + nw / 2} ${ny + nh / 2})`}>
            <rect x={nx + u * 0.5} y={ny + u * 0.7} width={nw} height={nh} rx={u * 0.4} className="lp-bd-sticky-shadow" />
            <rect x={nx} y={ny} width={nw} height={nh} rx={u * 0.4} className="lp-bd-sticky-paper" />
          </g>
          <clipPath id="lp-bd-cv">
            <rect x={nx} y={ny} width={0} height={nh} className="lp-bd-reveal" data-w={nw} />
          </clipPath>
          <g clipPath="url(#lp-bd-cv)" transform={`rotate(-1.6 ${nx + nw / 2} ${ny + nh / 2})`}>
            <text x={nx + u * 2} y={ny + fs * 1.15} className="lp-bd-pill" style={{ fontSize: fs * 0.72 }}>
              {v.source === "agent" ? `Spoor's answer · ${v.pill[0]}` : v.pill[0]}
            </text>
            <text x={nx + u * 2} y={ny + fs * 2.45} className="lp-bd-head" style={{ fontSize: fs * 1.2 }}>{v.head}</text>
            {v.reasons.map((r, k) => (
              <g key={k}>
                <circle cx={nx + u * 2.6} cy={ny + fs * (3.65 + k * 1.05) - fs * 0.27} r={u * 0.45} className={`lp-bd-why lp-bd-why-${r.tone}`} />
                <text x={nx + u * 3.9} y={ny + fs * (3.65 + k * 1.05)} className="lp-bd-reason" style={{ fontSize: fs * 0.86 }}>{r.text}</text>
              </g>
            ))}
          </g>
        </g>
      )}
    </svg>
  );
}

/** The board's sketching in story order, as one timeline the hero schedules and pauses. */
export function boardTimeline(root: SVGSVGElement): Timeline {
  const tl = createTimeline({ autoplay: false });
  const notes = Array.from(root.querySelectorAll<SVGGElement>(".lp-bd-note")).sort((a, b) => Number(a.dataset.note) - Number(b.dataset.note));
  const segs = new Map(Array.from(root.querySelectorAll<SVGGElement>(".lp-bd-seg")).map((g) => [Number(g.dataset.seg), g]));
  const arrow = root.querySelector<SVGPathElement>(".lp-bd-arrow");
  const circle = root.querySelector<SVGPathElement>(".lp-bd-circle");
  const strike = root.querySelector<SVGPathElement>(".lp-bd-strike");
  const verdict = root.querySelector<SVGGElement>(".lp-bd-verdict");
  const sticky = root.querySelector<SVGGElement>(".lp-bd-sticky");
  root.querySelectorAll<SVGRectElement>(".lp-bd-reveal").forEach((r) => r.setAttribute("width", "0"));
  notes.forEach((n) => utils.set(Array.from(n.querySelectorAll(".lp-bd-dot")), { opacity: 0 }));
  const segD = new Map([...segs].map(([k, g]) => [k, svg.createDrawable(Array.from(g.querySelectorAll<SVGPathElement>("path")))]));
  segD.forEach((d) => utils.set(d, { draw: "0 0" }));
  const arrowD = arrow ? svg.createDrawable(arrow) : null;
  const circleD = circle ? svg.createDrawable(circle) : null;
  const strikeD = strike ? svg.createDrawable(strike) : null;
  [arrowD, circleD, strikeD].forEach((d) => d && utils.set(d, { draw: "0 0" }));
  if (sticky) utils.set(sticky, { opacity: 0 });

  tl.add(root.querySelector(".lp-bd-plan")!, { opacity: [0, 1], duration: 500, ease: "out(3)" }, 0);
  let t = 500;
  notes.forEach((n) => {
    const d = segD.get(Number(n.dataset.note));
    if (d) {
      tl.add(d, { draw: ["0 0", "0 1"], duration: 750, ease: "inOut(2)" }, t); // the marker reaches this scene
      t += 700;
    }
    const r = n.querySelector<SVGRectElement>(".lp-bd-reveal")!;
    tl.add(Array.from(n.querySelectorAll(".lp-bd-dot")), { opacity: [0, 1], duration: 220, ease: "out(3)" }, t);
    tl.add(r, { width: [0, Number(r.dataset.w)], duration: 900, ease: "linear" }, t + 120); // writing: a constant pace
    t += 1100;
  });
  if (arrowD) {
    tl.add(arrowD, { draw: ["0 0", "0 1"], duration: 420, ease: "out(3)" }, t);
    t += 420;
  }
  if (circleD) {
    tl.add(circleD, { draw: ["0 0", "0 1"], duration: 700, ease: "inOut(2)" }, t); // only the last scene is circled
    t += 700;
    const cr = root.querySelector<SVGRectElement>(".lp-bd-circle-note .lp-bd-reveal");
    if (cr) {
      tl.add(cr, { width: [0, Number(cr.dataset.w)], duration: 650, ease: "linear" }, t - 100); // then labelled
      t += 600;
    }
  }
  if (strikeD) {
    tl.add(strikeD, { draw: ["0 0", "0 1"], duration: 420, ease: "inOut(2)" }, t);
    t += 520;
  }
  if (verdict && sticky) {
    tl.add(sticky, { opacity: [0, 1], translateY: [-6, 0], duration: 320, ease: "out(3)" }, t);
    const r = verdict.querySelector<SVGRectElement>(".lp-bd-reveal")!;
    tl.add(r, { width: [0, Number(r.dataset.w)], duration: 2200, ease: "linear" }, t + 260);
  }
  return tl;
}

/** How long the board's sketching takes (ms), so the hero can hold it after the last stroke. */
export const BOARD_MS = 13400;
