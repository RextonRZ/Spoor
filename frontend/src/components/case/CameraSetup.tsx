"use client";
/**
 * The hub's camera setup on the Blender turntable (Rexton 3 Nov: "a toggle to view the CCTV and camera setup; click a
 * camera to see what it sees, cinematic, easy to navigate"; 4 Nov: "why cannot 3D rotate, zoom in"). The whole hub turns
 * under a drag, with inertia, and zooms toward the pointer. The turntable is a Blender render (spin_render.py, ring "ov",
 * a frame every 2 degrees at two heights) played as a video with a key frame on every frame, so a drag lands on any
 * frame at once. Every camera sits where it is mounted on every frame, and hovering one lights the floor it covers (its
 * frustum met with the floor), both projected with the frame's own camera matrix from Blender (cameras3d.py). Clicking
 * one flies into it: its own view opens over the hub. Esc, or "Back to the hub", flies out. The view is the camera's own
 * recording (or its still, for the close-up cameras); nothing is generated.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { PointerEvent as RPointerEvent } from "react";
import { HUB } from "@/lib/hub";
import { floorOn, onFrame, project } from "./spin";
import "./hubtour.css";

interface Hub3D { n: number; fps: number; size: [number, number]; cameras: { id: string; at: [number, number, number]; floor: [number, number][] }[]; rings: { elev: number; P: number[][] }[] }
type Cam = { id: string; osd_label: string; question: string; mount: string; height_m: number };
const CAMS = HUB.cameras as unknown as Cam[];
const BASE = "/tour/hub";
const CLOSE: Record<string, string> = { UNLOAD: "Unload close-up", TUNNEL: "Tunnel close-up", CHUTE: "Chute close-up", CAGE_W: "Cage close-up",
  STORE: "Store door close-up", DOCK: "Dock close-up" };
// "CHUTES C07-C12" reads "Chutes C07-C12": lower case, but a code with a digit in it, or a lone side letter ("W"),
// stays as painted
const place = (s: string) => s.toLowerCase().replace(/\b(\w*\d\w*|\w)\b/g, (w) => w.toUpperCase()).replace(/^\w/, (x) => x.toUpperCase());
const label = (id: string) => place(CAMS.find((c) => c.id === id)?.osd_label ?? "");
const nameOf = (id: string) => id.startsWith("CHK_") ? CLOSE[id.slice(4)] ?? id : `${id.replace("_", " ")} · ${label(id)}`;
// the plan's internal zone ids ("BLIND_NW") mean nothing on screen
const ask = (q: string) => q.replace(/\s*\([^)]*BLIND_[^)]*\)/g, "").replace(/\bBLIND_\w+\b/g, "a blind spot");
const REDUCED = () => typeof window !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;
const HINT_KEY = "spoor.cams.turned";
const DEG_PER_PX = 0.3;      // a drag across the stage turns the hub about a third of the way round
const TILT_PX = 46;          // a drag this far down looks from higher up, this far up from lower
const ZOOM_MAX = 2.5;        // past this the full-HD frame goes soft on a laptop screen
const mod = (a: number, n: number) => ((a % n) + n) % n;
type View = { s: number; tx: number; ty: number };   // a picture point u shows at u * s + t (stage fractions)
const FIT: View = { s: 1, tx: 0, ty: 0 };
const clampView = (v: View): View => ({ s: v.s, tx: Math.min(0, Math.max(1 - v.s, v.tx)), ty: Math.min(0, Math.max(1 - v.s, v.ty)) });

/** used: camera id -> the step numbers it shows on this case's route (empty on the Cameras page) */
export function CameraSetup({ used = {} }: { used?: Record<string, number[]> }) {
  const [hub, setHub] = useState<Hub3D | null | "none">(null);
  const [hover, setHover] = useState<string | null>(null);   // from the map: the card shows the camera
  const [peek, setPeek] = useState<string | null>(null);     // from the list: the map lights it, the list stays
  const [open, setOpen] = useState<string | null>(null);
  const [phase, setPhase] = useState<"idle" | "in" | "view" | "out">("idle");
  const [ring, setRing] = useState(0);                       // the height asked for
  const [shown, setShown] = useState<[number, number]>([0, 0]);  // [ring, frame] on screen now
  const [ready, setReady] = useState<[boolean, boolean]>([false, false]);
  const [view, setView] = useState<View>(FIT);
  const [turned, setTurned] = useState(() => { try { return typeof window !== "undefined" && localStorage.getItem(HINT_KEY) === "1"; } catch { return false; } });
  const stage = useRef<HTMLDivElement>(null);
  const vids = useRef<(HTMLVideoElement | null)[]>([null, null]);
  const pos = useRef(0);                 // the turn, in frames (fractional while moving)
  const ringRef = useRef(0);
  const want = useRef([-1, -1]);         // the frame each video was last asked for
  const spinRaf = useRef(0);
  const zoomRaf = useRef(0);
  const viewRef = useRef<View>(FIT);     // what is drawn
  const goal = useRef<View>(FIT);        // where the zoom is heading
  const drag = useRef<{ x: number; y: number; p0: number; hist: [number, number][] } | null>(null);

  useEffect(() => {
    let live = true;
    fetch(`${BASE}/cameras3d.json`).then((r) => r.ok ? r.json() : "none").then((j) => { if (live) setHub(j); }).catch(() => live && setHub("none"));
    return () => { live = false; };
  }, []);
  const h = hub && hub !== "none" ? hub : null;
  const n = h?.n ?? 1;

  // each height's video, fetched whole before it can be turned, so a drag never waits on the network
  useEffect(() => {
    if (!h) return;
    let live = true;
    const urls: string[] = [];
    h.rings.reduce((p, _r, e) => p.then(() => fetch(`${BASE}/ov${e}.mp4`).then((r) => r.blob()).then((b) => {
      const v = vids.current[e];
      if (!live || !v) return;
      const u = URL.createObjectURL(b); urls.push(u);
      return new Promise<void>((ok) => { v.addEventListener("loadeddata", () => ok(), { once: true }); v.src = u; v.load(); })
        .then(() => { if (live) setReady((x) => (e ? [x[0], true] : [true, x[1]])); });
    })), Promise.resolve()).catch(() => {});
    return () => { live = false; urls.forEach((u) => URL.revokeObjectURL(u)); };
  }, [h]);

  /** ask the current height's video for the frame the turn is at; one seek in flight at a time, the newest wins */
  const seek = useCallback(() => {
    const e = ringRef.current, v = vids.current[e];
    if (!h || !v || v.readyState < 1 || v.seeking) return;
    const k = mod(Math.round(pos.current), h.n);
    if (want.current[e] === k) return;
    want.current[e] = k;
    v.currentTime = (k + 0.5) / h.fps;
  }, [h]);
  const seeked = (e: number) => {
    if (e === ringRef.current) setShown([e, want.current[e]]);
    seek();
  };
  useEffect(() => { if (ready[0]) { want.current[0] = -1; seek(); } }, [ready, seek]);

  /** the turn comes to rest on `to` from velocity v (frames/s): a critically damped spring, so a flick carries on */
  const settle = useCallback((to: number, v: number) => {
    cancelAnimationFrame(spinRaf.current);
    if (REDUCED()) { pos.current = to; seek(); return; }
    const k = (2 * Math.PI / 0.5) ** 2, c = 2 * Math.sqrt(k);
    let x = pos.current, vel = v, last = performance.now();
    const step = (t: number) => {
      const dt = Math.min(0.032, (t - last) / 1000); last = t;
      vel += (-k * (x - to) - c * vel) * dt; x += vel * dt;
      pos.current = x; seek();
      if (Math.abs(x - to) < 0.02 && Math.abs(vel) < 0.1) { pos.current = to; seek(); return; }
      spinRaf.current = requestAnimationFrame(step);
    };
    spinRaf.current = requestAnimationFrame(step);
  }, [seek]);

  /** the zoom eases toward its goal; the picture under the pointer stays under it */
  const zoomTo = useCallback((g: View) => {
    goal.current = clampView(g);
    cancelAnimationFrame(zoomRaf.current);
    if (REDUCED()) { viewRef.current = goal.current; setView(goal.current); return; }
    let last = performance.now();
    const step = (t: number) => {
      const a = 1 - Math.exp(-((t - last) / 1000) * 16); last = t;
      const c = viewRef.current, gg = goal.current;
      const nv = { s: c.s + (gg.s - c.s) * a, tx: c.tx + (gg.tx - c.tx) * a, ty: c.ty + (gg.ty - c.ty) * a };
      const done = Math.abs(nv.s - gg.s) < 0.002 && Math.abs(nv.tx - gg.tx) < 0.0005 && Math.abs(nv.ty - gg.ty) < 0.0005;
      viewRef.current = done ? gg : nv; setView(viewRef.current);
      if (!done) zoomRaf.current = requestAnimationFrame(step);
    };
    zoomRaf.current = requestAnimationFrame(step);
  }, []);
  const zoomAt = useCallback((factor: number, cx: number, cy: number) => {
    const g = goal.current, s = Math.min(ZOOM_MAX, Math.max(1, g.s * factor));
    zoomTo({ s, tx: cx - (cx - g.tx) * (s / g.s), ty: cy - (cy - g.ty) * (s / g.s) });
  }, [zoomTo]);
  useEffect(() => {
    const el = stage.current;
    if (!el) return;
    const wheel = (ev: WheelEvent) => {
      if (open) return;
      ev.preventDefault();
      const r = el.getBoundingClientRect(), dy = ev.deltaY * (ev.deltaMode === 1 ? 16 : 1);
      zoomAt(Math.exp(-dy * (ev.ctrlKey ? 0.01 : 0.0016)), (ev.clientX - r.left) / r.width, (ev.clientY - r.top) / r.height);
    };
    el.addEventListener("wheel", wheel, { passive: false });
    return () => el.removeEventListener("wheel", wheel);
  }, [zoomAt, open]);
  useEffect(() => () => { cancelAnimationFrame(spinRaf.current); cancelAnimationFrame(zoomRaf.current); }, []);

  const tilt = useCallback((e: number) => {
    if (e === ringRef.current || !ready[e]) return;
    ringRef.current = e; setRing(e);
    want.current[e] = -1; seek();
  }, [ready, seek]);
  const markTurned = () => { if (turned) return; setTurned(true); try { localStorage.setItem(HINT_KEY, "1"); } catch { /* private window */ } };
  const canTurn = ready[0] && !open;
  const reset = () => { const home = Math.round(pos.current / n) * n; settle(home, 0); zoomTo(FIT); };

  const down = (ev: RPointerEvent<HTMLDivElement>) => {
    if (!canTurn || ev.button !== 0 || (ev.target as Element).closest(".hc-cam, .ht-ctl, .hc-view")) return;
    cancelAnimationFrame(spinRaf.current);
    ev.currentTarget.setPointerCapture(ev.pointerId);
    drag.current = { x: ev.clientX, y: ev.clientY, p0: pos.current, hist: [[ev.timeStamp, ev.clientX]] };
  };
  const move = (ev: RPointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (!d || !h) return;
    pos.current = d.p0 - (ev.clientX - d.x) * DEG_PER_PX / (360 / h.n);
    d.hist.push([ev.timeStamp, ev.clientX]); if (d.hist.length > 6) d.hist.shift();
    const dy = ev.clientY - d.y;
    if (Math.abs(dy) > TILT_PX && ev.pointerType === "mouse") { tilt(dy > 0 ? 1 : 0); d.y = ev.clientY; }
    if (Math.abs(ev.clientX - d.x) > 6) markTurned();
    seek();
  };
  const up = (ev: RPointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    drag.current = null;
    if (!d || !h) return;
    const [t0, x0] = d.hist[0], dt = (ev.timeStamp - t0) / 1000;
    const vpx = dt > 0 && ev.timeStamp - d.hist[d.hist.length - 1][0] < 80 ? (ev.clientX - x0) / dt : 0;
    const v = -vpx * DEG_PER_PX / (360 / h.n);
    settle(Math.round(pos.current + project(v)), v);
  };
  const key = (ev: React.KeyboardEvent) => {
    if (open || !canTurn) return;
    const step = h ? Math.round(10 / (360 / h.n)) || 1 : 1;
    if (ev.key === "ArrowLeft" || ev.key === "ArrowRight") { ev.preventDefault(); cancelAnimationFrame(spinRaf.current); pos.current = Math.round(pos.current) + (ev.key === "ArrowLeft" ? step : -step); seek(); markTurned(); }
    if (ev.key === "ArrowUp" || ev.key === "ArrowDown") { ev.preventDefault(); tilt(ev.key === "ArrowDown" ? 1 : 0); }
    if (ev.key === "+" || ev.key === "=") zoomAt(1.4, 0.5, 0.5);
    if (ev.key === "-") zoomAt(1 / 1.4, 0.5, 0.5);
    if (ev.key === "0") reset();
  };

  // the cameras on this route first, then the rest in their numbering (the order the view's arrows step through)
  const list = useMemo(() => (h?.cameras ?? []).filter((c) => CAMS.some((x) => x.id === c.id))
    .sort((a, b) => Number(!used[a.id]) - Number(!used[b.id]) || a.id.localeCompare(b.id)), [h, used]);
  const groups = useMemo(() => {
    const ids = (h?.cameras ?? []).map((c) => c.id).filter((id) => CAMS.some((x) => x.id === id)).sort();
    return [["Wide cameras", ids.filter((id) => id.startsWith("CAM_"))], ["Close-up cameras", ids.filter((id) => id.startsWith("CHK_"))]] as const;
  }, [h]);

  const fly = useCallback((id: string) => {
    if (open && open !== id) { setOpen(id); return; }        // already inside: switch cameras in place
    setOpen(id); setHover(null); setPeek(null);
    if (REDUCED()) { setPhase("view"); return; }
    setPhase("in"); window.setTimeout(() => setPhase("view"), 380);
  }, [open]);
  const out = useCallback(() => {
    if (REDUCED()) { setOpen(null); setPhase("idle"); return; }
    setPhase("out"); window.setTimeout(() => { setOpen(null); setPhase("idle"); }, 360);
  }, []);
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => {
      if (e.key === "Escape") out();
      const i = list.findIndex((c) => c.id === open);
      if (e.key === "ArrowRight") fly(list[(i + 1) % list.length].id);
      if (e.key === "ArrowLeft") fly(list[(i - 1 + list.length) % list.length].id);
    };
    window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k);
  }, [open, list, out, fly]);

  if (hub === "none") return <p className="ht-none">The camera setup has not been exported yet.</p>;
  const sel = open ?? hover ?? peek;
  const info = (open ?? hover) ? CAMS.find((c) => c.id === (open ?? hover)) : null;
  const idx = open ? list.findIndex((c) => c.id === open) : -1;
  const P = h?.rings[shown[0]]?.P[shown[1]];
  const onScreen = (u: [number, number] | null): [number, number] | null => u && [u[0] * view.s + view.tx, u[1] * view.s + view.ty];
  const pins = P ? list.map((c) => ({ c, at: onScreen(onFrame(P, ...c.at)) })) : [];
  const selCam = sel ? h?.cameras.find((c) => c.id === sel) : null;
  const cover = P && selCam ? floorOn(P, selCam.floor) : null;
  const openAt = open ? pins.find((p) => p.c.id === open)?.at : null;
  const moved = view.s > 1.01 || shown[1] !== 0 || ring !== 0;

  return (
    <>
      <div className="ht-main">
        <div ref={stage} className="hc-stage" data-phase={phase} data-turn={canTurn ? "" : undefined} tabIndex={0} onKeyDown={key}
          aria-label="The hub in 3D. Drag or use the arrow keys to turn it; scroll or use plus and minus to zoom."
          onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up} onDoubleClick={(ev) => { if (!(ev.target as Element).closest(".hc-cam, .ht-ctl, .hc-view")) reset(); }}
          style={h ? { aspectRatio: `${h.size[0]} / ${h.size[1]}` } : undefined}>
          <div className="hc-world" style={openAt ? { transformOrigin: `${openAt[0] * 100}% ${openAt[1] * 100}%` } : undefined}>
            <div className="hc-zoom" style={{ transform: `translate(${view.tx * 100}%, ${view.ty * 100}%) scale(${view.s})` }}>
              {/* eslint-disable-next-line @next/next/no-img-element -- the turntable's first frame while its video loads */}
              {h && <img className="hc-img" src={`${BASE}/ov0.jpg`} alt="The hub model, rendered in Blender" draggable={false} />}
              {h?.rings.map((_r, e) => (
                <video key={e} ref={(el) => { vids.current[e] = el; }} className="hc-img hc-turn" data-on={ready[e] && (e === 0 || shown[0] === 1) ? "" : undefined} muted playsInline preload="auto"
                  onSeeked={() => seeked(e)} aria-hidden />
              ))}
              {cover && (
                <svg className="hc-floor" viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden><polygon points={cover} data-on="" /></svg>
              )}
            </div>
            {pins.map(({ c, at }) => at && at[0] > -0.01 && at[0] < 1.01 && at[1] > -0.01 && at[1] < 1.01 && (
              <button key={c.id} type="button" className="hc-cam" data-close={c.id.startsWith("CHK_") ? "" : undefined} data-used={used[c.id] ? "" : undefined}
                data-on={sel === c.id ? "" : undefined} style={{ left: `${at[0] * 100}%`, top: `${at[1] * 100}%` }} tabIndex={open ? -1 : 0}
                onMouseEnter={() => setHover(c.id)} onMouseLeave={() => setHover((x) => x === c.id ? null : x)} onFocus={() => setHover(c.id)} onBlur={() => setHover(null)}
                onClick={() => fly(c.id)} aria-label={`Look through ${nameOf(c.id)}`}>
                <svg viewBox="0 0 24 24" aria-hidden><path d="M4 8h11a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1zM16 11l5-3v8l-5-3" /></svg>
              </button>
            ))}
          </div>
          {!h && <span className="ht-wait" />}

          {canTurn && !turned && (
            <span className="ht-hint" aria-hidden>
              <svg viewBox="0 0 24 24"><path d="M20 12a8 8 0 1 1-2.34-5.66" /><path d="M20 4v4.5h-4.5" /></svg>Drag to turn · scroll to zoom
            </span>
          )}
          {!open && h && (
            <>
              <div className="ht-ctl">
                <button type="button" className="ht-play ht-ghost" aria-pressed={ring === 1} onClick={() => tilt(ring ? 0 : 1)} disabled={!ready[ring ? 0 : 1]}>
                  <svg viewBox="0 0 24 24" aria-hidden className="ht-stroke">{ring ? <path d="M6 9l6 6 6-6" /> : <path d="M6 15l6-6 6 6" />}</svg>
                  {ring ? "Lower view" : "Higher view"}
                </button>
              </div>
              <div className="ht-ctl ht-ctl-r hc-zoomctl">
                {moved && (
                  <button type="button" className="ht-play ht-ghost" onClick={reset}>
                    <svg viewBox="0 0 24 24" aria-hidden className="ht-stroke"><path d="M4 12a8 8 0 1 0 2.34-5.66" /><path d="M4 4v4.5h4.5" /></svg>Reset view
                  </button>
                )}
                <button type="button" className="ht-play hc-zbtn" onClick={() => zoomAt(1 / 1.5, 0.5, 0.5)} disabled={view.s <= 1.001} aria-label="Zoom out">
                  <svg viewBox="0 0 24 24" aria-hidden className="ht-stroke"><path d="M6 12h12" /></svg></button>
                <button type="button" className="ht-play hc-zbtn" onClick={() => zoomAt(1.5, 0.5, 0.5)} disabled={view.s >= ZOOM_MAX - 0.001} aria-label="Zoom in">
                  <svg viewBox="0 0 24 24" aria-hidden className="ht-stroke"><path d="M6 12h12M12 6v12" /></svg></button>
              </div>
            </>
          )}

          {open && (
            <div className="hc-view" role="dialog" aria-label={`The view from ${nameOf(open)}`}>
              {open.startsWith("CHK_")
                // eslint-disable-next-line @next/next/no-img-element -- the close-up camera's own frame
                ? <img key={open} className="hc-feed" src={`/cameras/${open}.jpg`} alt={`What ${nameOf(open)} sees`} />
                : <video key={open} className="hc-feed" src={`/cameras/${open}.mp4`} poster={`/cameras/${open}.jpg`} autoPlay muted loop playsInline aria-label={`What ${nameOf(open)} sees`} />}
              {/* only the way back sits on the picture: the camera's own time and name (its corners) stay readable */}
              <div className="hc-view-top">
                <button type="button" className="hc-x" onClick={out}><svg viewBox="0 0 24 24" aria-hidden><path d="M15 5l-7 7 7 7" /></svg>Back to the hub</button>
              </div>
              <div className="hc-view-nav">
                <button type="button" className="hc-nav" onClick={() => fly(list[(idx - 1 + list.length) % list.length].id)} aria-label="Previous camera">
                  <svg viewBox="0 0 24 24" aria-hidden><path d="M15 5l-7 7 7 7" /></svg></button>
                <span className="hc-count">{idx + 1} / {list.length}</span>
                <button type="button" className="hc-nav" onClick={() => fly(list[(idx + 1) % list.length].id)} aria-label="Next camera">
                  <svg viewBox="0 0 24 24" aria-hidden><path d="M9 5l7 7-7 7" /></svg></button>
              </div>
            </div>
          )}
        </div>
        <div className="hc-legend" aria-hidden>
          <span><i className="hc-k-wide" />Wide camera</span><span><i className="hc-k-close" />Close-up camera</span>
          {Object.keys(used).length > 0 && <span><i className="hc-k-used" />On this parcel&apos;s route</span>}
          <span className="hc-hint">Hover a camera to see what it covers. Click to look through it.</span>
        </div>
      </div>

      <aside className="ht-card hc-card" aria-live="polite">
        {info ? (
          <>
            <div className="ht-card-top"><span className="ht-n">{info.id.startsWith("CHK_") ? "Close-up camera" : "Wide camera"}</span>
              {used[info.id] && <span className="ht-chip" data-tone="seen">Step {used[info.id].join(", ")}</span>}</div>
            <h3 className="ht-title">{nameOf(info.id)}</h3>
            <p className="ht-sub">{ask(info.question)}</p>
            <p className="ht-meta">{info.mount} · {info.height_m} m up</p>
            {!open && <button type="button" className="ht-btn ht-btn-main hc-look" onClick={() => fly(info.id)}>Look through it</button>}
          </>
        ) : (
          <>
            <h3 className="ht-title">{list.length} cameras</h3>
            <div className="hc-groups">
              {groups.map(([title, ids]) => ids.length > 0 && (
                <section key={title} className="hc-group">
                  <h4 className="hc-gh">{title}<span>{ids.length}</span></h4>
                  <ul className="hc-rows">
                    {ids.map((id) => {
                      const cam = CAMS.find((c) => c.id === id)!;
                      return (
                        <li key={id}>
                          <button type="button" className="hc-row" data-used={used[id] ? "" : undefined} data-on={peek === id ? "" : undefined}
                            onMouseEnter={() => setPeek(id)} onMouseLeave={() => setPeek((x) => x === id ? null : x)} onFocus={() => setPeek(id)} onBlur={() => setPeek(null)}
                            onClick={() => fly(id)} aria-label={`Look through ${nameOf(id)}`}>
                            <span className="hc-row-n">{id.startsWith("CAM_") ? id.slice(4) : <i className="hc-k-close" />}</span>
                            <span className="hc-row-name">{label(id)}</span>
                            <span className="hc-row-m">{used[id] ? `Step ${used[id].join(", ")}` : `${cam.height_m} m`}</span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ))}
            </div>
          </>
        )}
      </aside>
    </>
  );
}
