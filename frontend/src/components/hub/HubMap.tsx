"use client";
/**
 * The hub from straight above with every scanner as a numbered checkpoint (its step in a parcel's journey), and the
 * "Where is this?" card for one place (owner 1 Nov: judges must see which checkpoint is where).
 *
 * HubMap: pan (drag), zoom (wheel, double click, + / - / fit), a row of the same checkpoint in one zone shows as one
 * marker until you zoom in (click it to fly there), zones name themselves on hover and fly in on click, amber where
 * parcels are stalled, the chosen place in the accent. Steps and search dim what doesn't match. The view moves in the
 * DOM directly (no re-render per frame); markers are real buttons. Motion: 320 ms ease-in-out flights, 150 ms states,
 * none under reduced motion; wheel and drag follow the pointer 1:1.
 * WhereIs: the place's zone as a tilted 3D map, from straight above and at eye height, the place pinned on each and the
 * zone's other scanners as dots you can pick.
 */
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { STAGES, ZONE_LABEL, placeName, stageOf, usePlacesGeo, type PlacesGeo, type Shot } from "@/lib/places";
import { usePanZoom } from "./panzoom";
import { Turntable } from "./Turntable";
import "./hubmap.css";


const W = 1600, H = 900, GROUPED_BELOW = 1.7, MAX_ZOOM = 4;
type Box = [number, number, number, number];
interface Group { key: string; stage: number; zone: string; members: string[]; x: number; y: number; box: Box }
interface Pt { id: string; name: string; zone: string; stage: number; x: number; y: number }

/** cubic-bezier(.77,0,.175,1): on-screen movement */
function bezier(x1: number, y1: number, x2: number, y2: number) {
  const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx, cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
  const X = (t: number) => ((ax * t + bx) * t + cx) * t, Y = (t: number) => ((ay * t + by) * t + cy) * t;
  const dX = (t: number) => (3 * ax * t + 2 * bx) * t + cx;
  return (x: number) => { let t = x; for (let i = 0; i < 6; i++) { const d = dX(t); if (Math.abs(d) < 1e-6) break; t -= (X(t) - x) / d; } return Y(Math.min(1, Math.max(0, t))); };
}
const easeMove = bezier(0.77, 0, 0.175, 1);
const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const boxOf = (pts: { x: number; y: number }[]): Box =>
  [Math.min(...pts.map((p) => p.x)), Math.min(...pts.map((p) => p.y)), Math.max(...pts.map((p) => p.x)), Math.max(...pts.map((p) => p.y))];

/** One tooltip for the page: a short delay for the first, then instant while moving between markers. */
function useTip() {
  const el = useRef<HTMLDivElement>(null);
  const timer = useRef(0), hidAt = useRef(0);
  const show = useCallback((target: HTMLElement, text: string, sub?: string) => {
    window.clearTimeout(timer.current);
    const put = () => {
      const t = el.current; if (!t) return;
      t.replaceChildren(text, ...(sub ? [Object.assign(document.createElement("span"), { textContent: sub })] : []));
      const r = target.getBoundingClientRect();
      t.style.left = `${Math.round(r.left + r.width / 2 - t.offsetWidth / 2)}px`;
      t.style.top = `${Math.round(r.top - t.offsetHeight - 8)}px`;
      t.dataset.on = "";
    };
    if (performance.now() - hidAt.current < 400) { el.current?.setAttribute("data-instant", ""); put(); requestAnimationFrame(() => el.current?.removeAttribute("data-instant")); }
    else timer.current = window.setTimeout(put, 320);
  }, []);
  const hide = useCallback(() => {
    window.clearTimeout(timer.current);
    if (el.current?.hasAttribute("data-on")) hidAt.current = performance.now();
    el.current?.removeAttribute("data-on");
  }, []);
  const node = <div className="hm-tip" ref={el} role="tooltip" />;
  return { show, hide, node };
}

export function HubMap({ stalled, selected, onOpen }: {
  stalled: Record<string, number>; selected: string | null; onOpen: (id: string, el: HTMLElement) => void;
}) {
  const geo = usePlacesGeo();
  if (!geo) return <div className="hm-loading" aria-busy="true">Loading the hub map</div>;
  return <MapView geo={geo} stalled={stalled} selected={selected} onOpen={onOpen} />;
}

function MapView({ geo, stalled, selected, onOpen }: {
  geo: PlacesGeo; stalled: Record<string, number>; selected: string | null; onOpen: (id: string, el: HTMLElement) => void;
}) {
  const hub = geo.hub_top;
  const pts = useMemo<Pt[]>(() => Object.entries(hub.scan_points)
    .map(([id, p]) => ({ id, name: placeName(id), zone: p.zone, stage: stageOf(id), x: p.x, y: p.y }))
    .sort((a, b) => a.stage - b.stage || a.id.localeCompare(b.id)), [hub]);
  const groups = useMemo<Group[]>(() => {
    const by = new Map<string, Pt[]>();
    for (const p of pts) by.set(`${p.stage}|${p.zone}`, [...(by.get(`${p.stage}|${p.zone}`) ?? []), p]);
    return [...by.entries()].filter(([, m]) => m.length >= 3).map(([key, m]) => ({
      key, stage: m[0].stage, zone: m[0].zone, members: m.map((p) => p.id),
      x: m.reduce((a, p) => a + p.x, 0) / m.length, y: m.reduce((a, p) => a + p.y, 0) / m.length, box: boxOf(m) }));
  }, [pts]);
  const groupOf = useMemo(() => new Map(groups.flatMap((g) => g.members.map((id) => [id, g] as const))), [groups]);

  const [q, setQ] = useState("");
  const [step, setStep] = useState<number | null>(null);
  const [hoverZone, setHoverZone] = useState<string | null>(null);
  const tip = useTip();

  const frame = useRef<HTMLDivElement>(null), content = useRef<HTMLDivElement>(null);
  const bar = useRef<HTMLDivElement>(null), barText = useRef<HTMLSpanElement>(null);
  const mk = useRef(new Map<string, HTMLButtonElement>()), gk = useRef(new Map<string, HTMLButtonElement>());
  const v = useRef({ s: 1, tx: 0, ty: 0, s0: 1 });
  const anim = useRef(0);
  const drag = useRef<{ x: number; y: number; tx: number; ty: number; zone?: string; moved: boolean } | null>(null);

  const clamp = useCallback((t: { s: number; tx: number; ty: number }) => {
    const f = frame.current!, fw = f.clientWidth, fh = f.clientHeight, cw = W * t.s, ch = H * t.s;
    t.tx = cw <= fw ? (fw - cw) / 2 : Math.min(0, Math.max(fw - cw, t.tx));
    t.ty = ch <= fh ? (fh - ch) / 2 : Math.min(0, Math.max(fh - ch, t.ty));
    return t;
  }, []);
  const apply = useCallback(() => {
    const { s, tx, ty, s0 } = v.current, grouped = s < s0 * GROUPED_BELOW;
    if (content.current) content.current.style.transform = `translate(${tx}px,${ty}px) scale(${s})`;
    // positions go in the `translate` property (CSS keeps transform: translate(-50%,-50%)), so a pressed marker's
    // `scale` shrinks it about its own centre; scaled with its position in `transform` it slid up to 11 px off the
    // pointer and the release landed on the zone (no click)
    const at = (el: HTMLElement, x: number, y: number) => el.style.setProperty("translate", `${x}px ${y}px`);
    const dots: { x: number; y: number }[] = [];
    for (const p of pts) {
      const b = mk.current.get(p.id); if (!b) continue;
      b.hidden = grouped && groupOf.has(p.id);
      const x = p.x * s + tx, y = p.y * s + ty; at(b, x, y);
      if (!b.hidden) dots.push({ x, y });
    }
    // group pills stand for a row, not a point: one that would touch another pill or a marker slides up or down just
    // clear of it (markers never move, they are exact)
    const pills = groups.map((g) => ({ b: gk.current.get(g.key), x: g.x * s + tx, y: g.y * s + ty })).filter((o) => o.b);
    for (const o of pills) o.b!.hidden = !grouped;
    if (grouped) {
      const GAP = 4, PH = 24, D = 22;
      pills.sort((a, c) => a.y - c.y);
      const placed: { x: number; y: number; hw: number; hh: number }[] = dots.map((d) => ({ ...d, hw: D / 2, hh: D / 2 }));
      for (const o of pills) {
        const hw = o.b!.offsetWidth / 2;
        const free = (y: number) => !placed.some((q) => Math.abs(q.x - o.x) < q.hw + hw + GAP && Math.abs(q.y - y) < q.hh + PH / 2 + GAP);
        // the nearest clear spot: 0, +6, -6, +12, -12 ... px (stays put when nothing is near)
        for (let k = 0; k <= 24; k++) { const dy = (k % 2 ? 1 : -1) * Math.ceil(k / 2) * 6; if (free(o.y + dy)) { o.y += dy; break; } }
        placed.push({ x: o.x, y: o.y, hw, hh: PH / 2 });
      }
    }
    for (const o of pills) at(o.b!, o.x, o.y);
    const mpp = hub.m_per_px / s, m = [2, 5, 10, 20, 50].find((x) => x / mpp >= 70) ?? 50;
    if (bar.current) bar.current.style.width = `${Math.round(m / mpp)}px`;
    if (barText.current) barText.current.textContent = `${m} m`;
  }, [pts, groups, groupOf, hub]);
  const fit = useCallback((box?: Box, pad = 40) => {
    const f = frame.current!, fw = f.clientWidth, fh = f.clientHeight;
    if (!box) { const s = Math.min(fw / W, fh / H); return { s, tx: (fw - W * s) / 2, ty: (fh - H * s) / 2 }; }
    const bw = Math.max(box[2] - box[0], 40) + pad * 2, bh = Math.max(box[3] - box[1], 40) + pad * 2;
    const s = Math.min(v.current.s0 * MAX_ZOOM, Math.max(v.current.s0, Math.min(fw / bw, fh / bh)));
    return clamp({ s, tx: fw / 2 - ((box[0] + box[2]) / 2) * s, ty: fh / 2 - ((box[1] + box[3]) / 2) * s });
  }, [clamp]);
  const flyTo = useCallback((to: { s: number; tx: number; ty: number }) => {
    cancelAnimationFrame(anim.current);
    clamp(to);
    if (reducedMotion()) { Object.assign(v.current, to); apply(); return; }
    const a = { ...v.current }, t0 = performance.now();
    const tick = (t: number) => {
      const k = easeMove(Math.min(1, (t - t0) / 320));
      v.current.s = a.s + (to.s - a.s) * k; v.current.tx = a.tx + (to.tx - a.tx) * k; v.current.ty = a.ty + (to.ty - a.ty) * k;
      apply();
      if (k < 1) anim.current = requestAnimationFrame(tick);
    };
    anim.current = requestAnimationFrame(tick);
  }, [apply, clamp]);
  const zoomAt = useCallback((f: number, cx: number, cy: number, animate: boolean) => {
    const c = v.current, s = Math.min(c.s0 * MAX_ZOOM, Math.max(c.s0, c.s * f));
    const to = { s, tx: cx - (cx - c.tx) * (s / c.s), ty: cy - (cy - c.ty) * (s / c.s) };
    if (animate) flyTo(to); else { Object.assign(c, clamp(to)); apply(); }
  }, [apply, clamp, flyTo]);

  // fit on first layout, keep fitting while untouched, clamp after a resize
  useLayoutEffect(() => {
    const f = frame.current!;
    const first = fit(); Object.assign(v.current, first, { s0: first.s }); apply();
    const ro = new ResizeObserver(() => {
      const c = v.current, wasFit = Math.abs(c.s - c.s0) < 1e-6, nf = fit();
      c.s0 = nf.s;
      if (wasFit) Object.assign(c, nf); else clamp(c);
      apply();
    });
    ro.observe(f);
    const wheel = (e: WheelEvent) => {
      e.preventDefault(); cancelAnimationFrame(anim.current);
      const r = f.getBoundingClientRect(); zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top, false);
    };
    f.addEventListener("wheel", wheel, { passive: false });
    return () => { ro.disconnect(); f.removeEventListener("wheel", wheel); cancelAnimationFrame(anim.current); };
  }, [apply, clamp, fit, zoomAt]);
  useLayoutEffect(() => { apply(); });  // markers re-rendered: put them back in place

  // a place chosen elsewhere (the list, a link): bring it into view, opening its group if needed
  useEffect(() => {
    const p = pts.find((x) => x.id === selected); const f = frame.current;
    if (!p || !f) return;
    const c = v.current, x = p.x * c.s + c.tx, y = p.y * c.s + c.ty;
    const hiddenInGroup = c.s < c.s0 * GROUPED_BELOW && groupOf.has(p.id);
    if (hiddenInGroup) { const s = Math.max(c.s, c.s0 * 2.2); flyTo({ s, tx: f.clientWidth / 2 - p.x * s, ty: f.clientHeight / 2 - p.y * s }); }
    else if (x < 40 || y < 40 || x > f.clientWidth - 40 || y > f.clientHeight - 40) flyTo({ ...c, tx: c.tx + f.clientWidth / 2 - x, ty: c.ty + f.clientHeight / 2 - y });
  }, [selected, pts, groupOf, flyTo]);

  const ql = q.trim().toLowerCase();
  const match = (p: Pt) => (!step || p.stage === step) && (!ql || `${p.name} ${p.id} ${ZONE_LABEL[p.zone] ?? ""}`.toLowerCase().includes(ql));
  const selZone = pts.find((p) => p.id === selected)?.zone;
  const nWarn = (ids: string[]) => ids.reduce((n, id) => n + (stalled[id] ?? 0), 0);

  return (
    <div className="hm">
      <div className="hm-bar">
        <label className="hm-search">
          <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="7" cy="7" r="5" /><path d="m11 11 3.5 3.5" /></svg>
          <span className="sp-sr">Find a scanner</span>
          <input type="search" placeholder="Find a scanner: C12, D07, tunnel" value={q} autoComplete="off" spellCheck={false}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") { const p = pts.find(match); const b = p && mk.current.get(p.id); if (p && b) onOpen(p.id, b); }
              if (e.key === "Escape") setQ("");
            }} />
        </label>
        <div className="hm-steps" role="group" aria-label="Show one step of a parcel's journey">
          {STAGES.map((s) => (
            <button key={s.n} type="button" className="hm-step" aria-pressed={step === s.n} title={s.how}
              onClick={() => {
                const next = step === s.n ? null : s.n; setStep(next);
                if (next) flyTo(fit(boxOf(pts.filter((p) => p.stage === next)), 90));
              }}>
              <i>{s.n}</i>{s.label}
            </button>
          ))}
        </div>
      </div>

      <div className="hm-frame" ref={frame}
        onPointerDown={(e) => {
          if (e.button !== 0 || (e.target as HTMLElement).closest(".hm-mk,.hm-chrome")) return;
          cancelAnimationFrame(anim.current);
          drag.current = { x: e.clientX, y: e.clientY, tx: v.current.tx, ty: v.current.ty, zone: (e.target as SVGElement).dataset?.zone, moved: false };
          e.currentTarget.setPointerCapture(e.pointerId);
        }}
        onPointerMove={(e) => {
          const d = drag.current; if (!d) return;
          const dx = e.clientX - d.x, dy = e.clientY - d.y;
          if (!d.moved && Math.hypot(dx, dy) > 3) { d.moved = true; e.currentTarget.dataset.dragging = ""; tip.hide(); setHoverZone(null); }
          if (d.moved) { v.current.tx = d.tx + dx; v.current.ty = d.ty + dy; clamp(v.current); apply(); }
        }}
        onPointerUp={(e) => {
          const d = drag.current; drag.current = null; delete e.currentTarget.dataset.dragging;
          if (d && !d.moved && d.zone) flyTo(fit(boxOf(hub.zones[d.zone].flat().map(([x, y]) => ({ x, y }))), 40));
        }}
        onDoubleClick={(e) => {
          if ((e.target as HTMLElement).closest(".hm-mk,.hm-chrome")) return;
          const r = e.currentTarget.getBoundingClientRect(); zoomAt(2, e.clientX - r.left, e.clientY - r.top, true);
        }}>
        <div className="hm-content" ref={content}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={hub.image} alt="The whole hub from straight above, roof removed, north up" draggable={false} />
          <svg viewBox={`0 0 ${W} ${H}`} aria-hidden="true">
            {Object.entries(hub.zones).flatMap(([z, polys]) => polys.map((poly, i) => (
              <polygon key={`${z}${i}`} data-zone={z} points={poly.map((p) => p.join(",")).join(" ")} className="hm-zone"
                data-hover={hoverZone === z || undefined} data-sel={selZone === z || undefined}
                onPointerEnter={() => !drag.current?.moved && setHoverZone(z)} onPointerLeave={() => setHoverZone(null)} />
            )))}
          </svg>
        </div>
        <div className="hm-layer">
          {groups.map((g) => {
            const s = STAGES[g.stage - 1], warn = nWarn(g.members);
            return (
              <button key={g.key} type="button" className="hm-mk hm-grp" ref={(b) => { if (b) gk.current.set(g.key, b); else gk.current.delete(g.key); }}
                data-dim={!g.members.some((id) => match(pts.find((p) => p.id === id)!)) || undefined}
                data-sel={(selected && g.members.includes(selected)) || undefined} data-tone={warn ? "warn" : undefined}
                aria-label={`${s.group}: ${g.members.length} scanners${warn ? `, ${warn} parcels stalled` : ""}. Zoom in`}
                onClick={() => { tip.hide(); flyTo(fit(g.box, 70)); }}
                onPointerEnter={(e) => tip.show(e.currentTarget, `${g.members.length} scanners`, "click to zoom in")} onPointerLeave={tip.hide}>
                <i>{g.stage}</i>{s.group}<span>{g.members.length}</span>{warn > 0 && <b>{warn}</b>}
              </button>
            );
          })}
          {pts.map((p) => {
            const warn = stalled[p.id] ?? 0;
            return (
              <button key={p.id} type="button" className="hm-mk hm-dot" ref={(b) => { if (b) mk.current.set(p.id, b); else mk.current.delete(p.id); }}
                data-dim={!match(p) || undefined} data-sel={p.id === selected || undefined} data-tone={warn ? "warn" : undefined}
                aria-label={`${p.name}, checkpoint ${p.stage}${warn ? `, ${warn} parcels stalled` : ""}`} aria-pressed={p.id === selected}
                onClick={(e) => { tip.hide(); onOpen(p.id, e.currentTarget); }}
                onPointerEnter={(e) => tip.show(e.currentTarget, p.name, warn ? `${warn} stalled` : p.id)} onPointerLeave={tip.hide}>
                {p.stage}{warn > 0 && <b>{warn}</b>}
              </button>
            );
          })}
        </div>
        {(hoverZone ?? selZone) && (
          <div className="hm-chrome hm-zname" aria-live="polite">
            <span>{hoverZone ?? selZone}</span>{ZONE_LABEL[(hoverZone ?? selZone)!] ?? ""}
          </div>
        )}
        <div className="hm-chrome hm-north" aria-hidden="true"><svg viewBox="0 0 12 12"><path d="M6 1 10 11 6 8.6 2 11Z" /></svg>N</div>
        <div className="hm-chrome hm-scale" aria-hidden="true"><span ref={barText} /><div ref={bar} /></div>
        <div className="hm-chrome hm-zoom">
          <button type="button" aria-label="Zoom in" onClick={() => { const f = frame.current!; zoomAt(1.6, f.clientWidth / 2, f.clientHeight / 2, true); }}>
            <svg viewBox="0 0 14 14"><path d="M7 2v10M2 7h10" /></svg></button>
          <button type="button" aria-label="Zoom out" onClick={() => { const f = frame.current!; zoomAt(1 / 1.6, f.clientWidth / 2, f.clientHeight / 2, true); }}>
            <svg viewBox="0 0 14 14"><path d="M2 7h10" /></svg></button>
          <button type="button" aria-label="Show the whole hub" onClick={() => flyTo(fit())}>
            <svg viewBox="0 0 14 14"><path d="M2 5V2h3M9 2h3v3M12 9v3H9M5 12H2V9" /></svg></button>
        </div>
      </div>
      {tip.node}
    </div>
  );
}

type View = "tilt" | "top" | "eye";
const VIEWS: [View, string][] = [["tilt", "3D"], ["top", "From above"], ["eye", "Eye level"]];

/** Where one place is (owner 1 Nov): three Blender pictures aimed at this exact scanner (a tilted 3D view, straight
 *  down, eye height; zoomable; the scanner pinned, the zone's other scanners as dots to pick), all three loading as
 *  soon as the place opens; one still loading shows the last picture blurred under a progress line. "Explore in 3D"
 *  opens the live hub model full screen (turn, move, zoom). Zones without per-scanner pictures fall back to the
 *  zone's pictures. */
export function WhereIs({ point, onPick }: { point: string; onPick?: (id: string, el: HTMLElement) => void }) {
  const geo = usePlacesGeo();
  const [view, setView] = useState<View>("tilt");
  const [instant, setInstant] = useState(false);
  const [bigOpen, setBigOpen] = useState(false);
  const [spun, setSpun] = useState(false);  // the turntable was opened (it then stays mounted)
  const big = useRef<HTMLDialogElement>(null);
  const [pzFrame, pzInner, zoomed, pzReset, pzStep, pzHandlers] = usePanZoom();
  const zone = geo?.hub_top.scan_points[point]?.zone;
  const z = zone ? geo?.zones[zone] : undefined;
  // the picture for a view: this scanner's own (aimed at it), else the zone's
  const shotFor = (v: View): Shot | null => {
    const own = geo?.pt?.[point]?.[v];
    if (own) return own;
    const zp = v === "tilt" ? z?.map : v === "top" ? z?.top : z?.eye;
    const h = zp?.scan_points[point];
    if (!zp || !h || h.seen === false) return zp ? { image: zp.image, x: -1, y: -1, mates: {} } : null;
    return { image: zp.image, x: h.x, y: h.y, mates: Object.fromEntries(Object.entries(zp.scan_points)
      .filter(([id, q]) => id !== point && q.zone === zone && q.seen !== false).map(([id, q]) => [id, { x: q.x, y: q.y }])) };
  };
  const shot = shotFor(view);
  // all three pictures stay mounted once the place opens (each loads once, switching only changes which is shown: the
  // dev server sends no-cache, so a swapped src was fetched again on every switch); a picture still loading shows
  // the last one under a progress line
  const src = shot?.image ?? null;
  const all = VIEWS.map(([k]) => shotFor(k)?.image).filter((u): u is string => !!u);
  const [loaded, setLoaded] = useState<Record<string, true>>({});
  const [shown, setShown] = useState<string | null>(null);
  if (src && loaded[src] && shown !== src) setShown(src);  // adjusting state while rendering (no effect)
  const tip = useTip();
  if (!geo || !z || !zone || !shot) return null;
  const name = placeName(point);
  const loading = !!src && shown !== src;
  const first = !shown;
  const vi = VIEWS.findIndex(([k]) => k === view);
  const pinned = shot.x >= 0;
  const caption = !pinned ? "This scanner is not in this picture; try another view."
    : view === "tilt" ? `${name} in ${ZONE_LABEL[zone]}, tilted view. Scroll to zoom.`
      : view === "top" ? `${name} from straight above, north up. Scroll to zoom.`
        : `${name} at eye height. Scroll to zoom.`;
  const pick = (k: View, kb: boolean) => { setInstant(kb); setView(k); pzReset(); };
  const open3d = () => { setBigOpen(true); big.current?.showModal(); };
  // "3D" is the scanner's Blender turntable when it has one; it stays mounted (hidden) once opened, like the pictures
  const turnN = geo.turn?.[point]?.n;
  const spin = !!turnN && view === "tilt";
  if (spin && !spun) setSpun(true);
  return (
    <figure className="hm-where">
      <div className="hm-seg" role="tablist" aria-label="View" data-instant={instant || undefined}>
        <span className="hm-thumb" style={{ width: `calc((100% - 6px) / ${VIEWS.length})`, transform: `translateX(${vi * 100}%)` }} aria-hidden="true" />
        {VIEWS.map(([k, label]) => (
          <button key={k} type="button" role="tab" aria-selected={k === view} disabled={!shotFor(k)}
            onClick={(e) => pick(k, e.detail === 0)}
            onKeyDown={(e) => {
              if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
              e.preventDefault();
              const on = VIEWS.filter(([x]) => shotFor(x)), j = on.findIndex(([x]) => x === view);
              const n = on[(j + (e.key === "ArrowRight" ? 1 : -1) + on.length) % on.length][0];
              pick(n, true);
              ((e.currentTarget.parentElement?.querySelectorAll("[role=tab]")[VIEWS.findIndex(([x]) => x === n)]) as HTMLElement | undefined)?.focus();
            }}>{label}</button>
        ))}
      </div>
      {spun && turnN && <div hidden={!spin}><Turntable point={point} n={turnN} onPick={onPick} onExpand={open3d} /></div>}
      <div className="hm-shot" ref={pzFrame} data-instant={instant || undefined} data-loading={loading || undefined} hidden={spin}
        data-zoomed={zoomed || undefined} aria-busy={loading || first} {...pzHandlers}>
        <div className="hm-zoomable" ref={pzInner}>
          {all.map((u) => (
            // eslint-disable-next-line @next/next/no-img-element
            <img key={u} src={u} alt={u === shown ? `${VIEWS[vi][1]} view of ${name}` : ""} draggable={false}
              data-front={u === shown || undefined} fetchPriority={u === src ? "high" : "low"}
              onLoad={() => setLoaded((l) => (l[u] ? l : { ...l, [u]: true }))} />
          ))}
          {!loading && Object.entries(shot.mates).map(([id, q]) => (
            <button key={id} type="button" className="hm-mate" style={{ left: `${q.x / 16}%`, top: `${q.y / 9}%` }} aria-label={placeName(id)}
              onClick={(e) => { tip.hide(); onPick?.(id, e.currentTarget); }}
              onPointerEnter={(e) => tip.show(e.currentTarget, placeName(id), id)} onPointerLeave={tip.hide} />
          ))}
          {!loading && pinned && <>
            <span className="hm-pin" style={{ left: `${shot.x / 16}%`, top: `${shot.y / 9}%` }} aria-hidden="true" />
            <span className="hm-pinlabel" data-left={shot.x > 1150 || undefined} style={{ left: `${shot.x / 16}%`, top: `${shot.y / 9}%` }}>{name}</span>
          </>}
        </div>
        {first && <div className="hm-shot-wait">Loading picture</div>}
        <div className="hm-3dbar">
          <button type="button" onClick={open3d}>
            <svg viewBox="0 0 14 14" aria-hidden="true"><path d="M7 1.5 12.5 4.5v5L7 12.5 1.5 9.5v-5zM1.5 4.5 7 7.5l5.5-3M7 7.5v5" /></svg>Explore in 3D
          </button>
        </div>
        <div className="hm-chrome hm-pz">
          <button type="button" aria-label="Zoom in" onClick={() => pzStep(1.6)}><svg viewBox="0 0 14 14"><path d="M7 2v10M2 7h10" /></svg></button>
          <button type="button" aria-label="Zoom out" disabled={!zoomed} onClick={() => pzStep(1 / 1.6)}><svg viewBox="0 0 14 14"><path d="M2 7h10" /></svg></button>
          {zoomed && <button type="button" aria-label="Show the whole picture" onClick={() => pzReset(true)}>
            <svg viewBox="0 0 14 14"><path d="M2 5V2h3M9 2h3v3M12 9v3H9M5 12H2V9" /></svg></button>}
        </div>
      </div>
      <figcaption>{caption}</figcaption>
      {tip.node}
      <dialog ref={big} className="hm-dlg" aria-label={`${name} in 3D`} onClose={() => setBigOpen(false)}
        onClick={(e) => { if (e.target === e.currentTarget) big.current?.close(); }}>
        <div className="hm-dlg-head">
          <span className="hm-dlg-zone">{zone} · {ZONE_LABEL[zone]}</span><b>{name}</b>
          <span className="hm-dlg-hint">Drag to turn · drag up or down for height · scroll to zoom</span>
          <button type="button" className="hb-x" aria-label="Close 3D" onClick={() => big.current?.close()}>
            <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8" /></svg>
          </button>
        </div>
        <div className="hm-dlg-body">{bigOpen && (turnN
          ? <Turntable point={point} n={turnN} big onPick={(id, el) => { big.current?.close(); onPick?.(id, el); }} />
          : <p className="hm-3dwait">No 3D view for this scanner yet.</p>)}</div>
      </dialog>
    </figure>
  );
}
