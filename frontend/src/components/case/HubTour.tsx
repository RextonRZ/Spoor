"use client";
/**
 * The route in the Blender hub (Rexton 3 Nov: "the 3D should be from Blender", "click a point and see what the box was
 * doing"). A drone fly-through rendered in Blender from the hub model only (people, moving cartons and roof hidden:
 * assets/tour/tour_render.py), with a table of where every step's point falls on each frame. The pins and the carton
 * marker are drawn here from that table, so every mark is the case's evidence (camera and scan positions) and the
 * picture underneath is just the building.
 *
 * Navigation is one row of numbered steps (no free orbit to get lost in): the next step flies there, any other step
 * cross-fades to it; Play flies the whole route and ends on the answer. The card beside it is the step's own camera frame
 * and words.
 *
 * Story mode, cinematic (reviewer 01:05, Rexton: no grey, light and motion instead). The hub keeps its colour. The
 * carton is a real object in the render (assets/tour/carton.py) moving along the belts and walkways; here the route
 * draws itself on the surface it travels (travelled part solid indigo, the rest faint, dashed where no camera saw the
 * move: the journey's own observed spans), pins spring in as the parcel reaches them, the cameras at a place shine
 * soft beams onto it (indigo for the step's own camera), a story clock runs, and the ending eases into the store, whose
 * outline glows once. All of it is placed with each frame's own projection matrix, so it stays on the building while
 * the place turns.
 *
 * At rest on a step the place can be turned around (Rexton 3 Nov, approved: "spin around at every step"): a Blender
 * turntable of the same place (assets/tour/spin_render.py) whose first frame is the fly-through's landing frame, so
 * the first drag swaps the video for the turntable without a jump, and Next turns back to that frame before it flies.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { signedUrl, useResource } from "@/lib/api";
import { SEEK_JOURNEY, type Chapter, type Reel } from "./JourneyReel";
import { CameraSetup } from "./CameraSetup";
import { TruthCompare, type Truth } from "./TruthCompare";
import { loadRing, onFrame, placeOf, project, ringReady, volume, type Spin, type UV } from "./spin";
import { HUB } from "@/lib/hub";
import "./hubtour.css";

interface Tour { fps: number; frames: number; size: [number, number]; steps: { n: number; arrive: number; title: string; tone: string }[];
  pins: [number, number][][]; marker: [number, number][]; P?: number[][]; ending?: { arrive: number } }
interface SearchTasks { tasks: { places: { name: string; zone_id: string | null }[] }[] }
/** the carton's way between two steps (assets/tour/route_path.py: belts, walkways, or held where it was last seen) */
interface Way { from: number; to: number; kind: "belt" | "walk" | "held"; path: [number, number, number?][] }
interface JourneyLite { objects: { segments: { kind: string; start: string; end: string }[] }[] }
interface StateLite { answer?: { objects: { inside?: { place: string; carried_in_at?: string; came_out_empty?: string[]; until?: string } | null }[] } | null }
type XY = [number, number];
const MARK_Z = 0.8;   // the pins' and the carton's height in the render (tour_render.py PIN_Z)
const isCam = (c: string) => /^(CAM|CHK)_/.test(c);
/** the first share u (0..1) of a polyline, by its length on screen: how the route unrolls like a pen stroke */
function prefix(q: XY[], u: number): XY[] {
  const seg = q.slice(1).map((b, i) => Math.hypot(b[0] - q[i][0], (b[1] - q[i][1]) * 0.5625));
  let left = u * seg.reduce((x, y) => x + y, 0);
  const out: XY[] = [q[0]];
  for (let i = 0; i < seg.length; i++) {
    if (left >= seg[i]) { out.push(q[i + 1]); left -= seg[i]; continue; }
    const f = seg[i] ? left / seg[i] : 0;
    out.push([q[i][0] + (q[i + 1][0] - q[i][0]) * f, q[i][1] + (q[i + 1][1] - q[i][1]) * f]);
    break;
  }
  return out;
}
/** the end of a polyline that lies inside the frame (with a margin), cut where it crosses in: on the ending no line
 *  leaves the picture (reviewer 01:35) */
function tailInside(q: XY[], m = 0.05): XY[] {
  const ok = (p: XY) => p[0] > m && p[0] < 1 - m && p[1] > m && p[1] < 1 - m;
  let i = q.length - 1;
  if (i < 0 || !ok(q[i])) return [];
  while (i > 0 && ok(q[i - 1])) i -= 1;
  if (i === 0) return q;
  // where the segment q[i-1] -> q[i] enters the frame: halve towards it
  let a = q[i - 1], b = q[i];
  for (let k = 0; k < 20; k++) { const c: XY = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]; if (ok(c)) b = c; else a = c; }
  return [b, ...q.slice(i)];
}
/** where a screen point falls on a polyline (page fractions; y counted at the stage's 16:9) */
function splitAt(pts: XY[], q: XY): [XY[], XY[]] {
  let best = { d: Infinity, i: 0, p: pts[0] as XY };
  for (let i = 0; i < pts.length - 1; i++) {
    const [ax, ay] = pts[i], [bx, by] = pts[i + 1], dx = bx - ax, dy = (by - ay) * 0.5625, ll = dx * dx + dy * dy;
    const u = ll ? Math.max(0, Math.min(1, ((q[0] - ax) * dx + (q[1] - ay) * 0.5625 * dy) / ll)) : 0;
    const p: XY = [ax + (bx - ax) * u, ay + (by - ay) * u], d = Math.hypot(p[0] - q[0], (p[1] - q[1]) * 0.5625);
    if (d < best.d) best = { d, i, p };
  }
  return [[...pts.slice(0, best.i + 1), best.p], [best.p, ...pts.slice(best.i + 1)]];
}
const pts = (q: XY[]) => q.map(([x, y]) => `${x.toFixed(4)},${y.toFixed(4)}`).join(" ");
const ZONES = (HUB as unknown as { zones: { id: string; polygons: number[][][] }[] }).zones;

const hms = (iso: string) => new Date(iso).toLocaleTimeString("en-GB", { timeZone: "Asia/Kuala_Lumpur", hour12: false });
const CHIP: Record<string, string> = { scan: "Scanned", seen: "On camera", noscan: "Not scanned in", record: "Records disagree", wait: "No camera" };
const camWords = (c: string) => !c ? "No camera" : c === "Tunnel reader" ? "The tunnel reader's photo"
  : c.startsWith("CHK_") ? `${c.slice(4).toLowerCase().replace("_w", "").replace("_e", "").replace("_", " ")} close-up camera`.replace(/^\w/, (x) => x.toUpperCase()) : c.replace("_", " ");
const camShort = (c: string) => c.startsWith("CHK_") ? camWords(c).replace(" camera", "") : c.replace("_", " ");
const REDUCED = () => typeof window !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;
const mod = (x: number, n: number) => ((x % n) + n) % n;
const inView = (p: UV | undefined): p is [number, number] => !!p && p[0] > 0.02 && p[0] < 0.98 && p[1] > 0.03 && p[1] < 0.97;
const HINT_KEY = "spoor.spin.turned";

export function HubTour({ caseId }: { caseId: string }) {
  const [tour, setTour] = useState<Tour | null | "none">(null);
  const [spin, setSpin] = useState<Spin | null>(null);
  const [mode, setMode] = useState<"route" | "cameras">("route");
  const reel = useResource<Reel>(`/v1/cases/${caseId}/journey-reel`);
  // where Spoor says to search first (the search task's first place): drawn as a soft volume on the hub
  const search = useResource<SearchTasks>(`/v1/cases/${caseId}/search-tasks`);
  const jr = useResource<JourneyLite>(`/v1/cases/${caseId}/journey`);
  const state = useResource<StateLite>(`/v1/cases/${caseId}/state`);
  const first = search.data?.tasks.at(-1)?.places[0];
  const answer = first?.zone_id ? ZONES.find((z) => z.id === first.zone_id!.replace(/^zone_/, "")) : undefined;
  const steps: Chapter[] = useMemo(() => (reel.data?.chapters ?? []).filter((c) => c.tone !== "card"), [reel.data]);
  const video = useRef<HTMLVideoElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [frame, setFrame] = useState(0);
  const [on, setOn] = useState(0);
  const [playing, setPlaying] = useState<"all" | "to" | null>(null);
  const [fading, setFading] = useState(false);
  const [ov, setOv] = useState(false);
  const [evAt, setEvAt] = useState<number | null>(null);   // the step whose own clip is open (another step closes it)
  const [endOv, setEnding] = useState(false);              // older tours without an ending: the answer on the whole hub
  const [hoverCam, setHoverCam] = useState<string | null>(null);
  // the simulation's ground truth: fetched only when asked for, shown only behind its own button
  const [truth, setTruth] = useState<Truth | null | "none">(null);
  const [cmp, setCmp] = useState(false);
  const compare = () => {
    if (truth && truth !== "none") { setCmp(true); return; }
    fetch(`/tour/${caseId}/truth.json`).then((r) => (r.ok ? r.json() : "none")).then((j) => { setTruth(j); if (j !== "none") setCmp(true); }).catch(() => setTruth("none"));
  };
  // legs a jump has just travelled, unrolling like a pen stroke (u 0..1, ease-in-out over 700 ms)
  const [pen, setPen] = useState<{ upTo: number; from: number; u: number } | null>(null);
  const penRaf = useRef(0);
  const unroll = (from: number, upTo: number) => {
    cancelAnimationFrame(penRaf.current);
    if (upTo <= from || REDUCED()) { setPen(null); return; }
    let t0 = -1;
    const ease = (x: number) => (x < 0.5 ? 4 * x ** 3 : 1 - (-2 * x + 2) ** 3 / 2);
    const tick = (now: number) => {
      if (t0 < 0) t0 = now;
      const x = Math.min(1, (now - t0) / 700);
      setPen(x < 1 ? { from, upTo, u: ease(x) } : null);
      if (x < 1) penRaf.current = requestAnimationFrame(tick);
    };
    setPen({ from, upTo, u: 0 });
    penRaf.current = requestAnimationFrame(tick);
  };
  const [ways, setWays] = useState<Way[]>([]);
  const [camAt, setCamAt] = useState<Record<string, [number, number, number]>>({});
  const stopAt = useRef<number | null>(null);
  const base = `/tour/${caseId}/spin`;

  // the turn: a (frames, unrounded while it glides) and the ring (0 = the fly-through's height, 1 = higher)
  const [a, setAState] = useState(0);
  const [e, setEState] = useState(0);
  const aRef = useRef(0), eRef = useRef(0), anim = useRef(0);
  const setA = (v: number) => { aRef.current = v; setAState(v); };
  const [cut, setCut] = useState(0);
  // the rings are different heights: a cut between them is softened by a short blur, so it reads as a move, not a jump
  const setE = (v: number) => { if (v !== eRef.current) setCut((c) => c + 1); eRef.current = v; setEState(v); };
  const [, setLoaded] = useState(0);
  const [turned, setTurned] = useState(() => { try { return typeof window !== "undefined" && localStorage.getItem(HINT_KEY) === "1"; } catch { return false; } });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    fetch(`/tour/${caseId}/tour.json`).then((r) => r.ok ? r.json() : "none").then((j) => { if (live) setTour(j); }).catch(() => live && setTour("none"));
    fetch(`/tour/${caseId}/spin/spin.json`).then((r) => r.ok ? r.json() : null).then((j) => { if (live && j && !j.test) setSpin(j); }).catch(() => {});
    fetch(`/tour/${caseId}/ways.json`).then((r) => r.ok ? r.json() : null).then((j) => { if (live && j) setWays(j.legs); }).catch(() => {});
    fetch("/tour/hub/cameras3d.json").then((r) => r.ok ? r.json() : null)
      .then((j: { cameras: { id: string; at: [number, number, number] }[] } | null) => { if (live && j) setCamAt(Object.fromEntries(j.cameras.map((c) => [c.id, c.at]))); }).catch(() => {});
    return () => { live = false; };
  }, [caseId]);
  const t = tour && tour !== "none" ? tour : null;
  const n = spin?.n ?? 36;
  // the answer: the render's ending (the drone eases back into the store and holds), reached by playing on or by the
  // rail's Answer stop
  const endAt = t?.ending?.arrive;
  const ending = endAt != null ? !ov && frame >= endAt - 1 : endOv;

  // steps that share a place share one pin ("8-10"); the pin shows the step you are on when it is one of them
  const groups = useMemo(() => {
    const g: number[][] = [];
    steps.forEach((c, i) => {
      const prev = g.at(-1);
      const same = prev && steps[prev[0]].xy && c.xy && Math.hypot(steps[prev[0]].xy![0] - c.xy[0], steps[prev[0]].xy![1] - c.xy[1]) < 0.5;
      if (same || (prev && !c.xy)) prev!.push(i); else g.push([i]);
    });
    return g;
  }, [steps]);

  // follow the video frame by frame: the marks move with the picture, and the step is whichever was last arrived at
  useEffect(() => {
    const v = video.current; if (!v || !t) return;
    let id = 0;
    const tick = () => {
      const f = Math.min(t.frames - 1, Math.round(v.currentTime * t.fps));
      setFrame(f);
      const k = t.steps.reduce((best, s, i) => s.arrive <= f ? i : best, 0);
      if (playing === "all") setOn(k);
      if (stopAt.current !== null && f >= stopAt.current) { v.pause(); stopAt.current = null; setPlaying(null); }
      if (v.ended) setPlaying(null);
      id = "requestVideoFrameCallback" in v ? (v as HTMLVideoElement & { requestVideoFrameCallback: (cb: () => void) => number }).requestVideoFrameCallback(tick) : requestAnimationFrame(tick);
    };
    tick();
    return () => { if ("cancelVideoFrameCallback" in v) (v as HTMLVideoElement & { cancelVideoFrameCallback: (n: number) => void }).cancelVideoFrameCallback(id); else cancelAnimationFrame(id); };
  }, [t, playing]);

  const place = ov ? "ov" : placeOf(spin, on + 1);
  const resting = !!t && !playing && !fading;
  const k = mod(Math.round(a), n);
  const frames = place ? ringReady(base, place, e) : null;
  const spun = ov || k !== 0 || e !== 0;
  const showTurn = resting && spun && !!frames;
  const ring = resting && !ending && spin && place ? spin.rings[place]?.rings[e] : null;

  // load this place's rings (low first), the next place's low ring and the Overview, so a turn never waits
  useEffect(() => {
    if (!spin || !t) return;
    const want: [string, number][] = [];
    if (place) want.push([place, 0], [place, 1]);
    const next = placeOf(spin, on + 2); if (next && next !== place) want.push([next, 0]);
    want.push(["ov", 0]);
    let live = true;
    want.reduce((p, [pl, ee]) => p.then(() => loadRing(base, pl, ee, spin.n).then(() => { if (live) setLoaded((x) => x + 1); }).catch(() => {})), Promise.resolve());
    return () => { live = false; };
  }, [spin, t, place, on, base]);
  useEffect(() => {
    if (evAt === null) return;
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") setEvAt(null); };
    window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k);
  }, [evAt]);

  // the turntable is a canvas: a decoded frame is drawn in one call, so spinning never flashes an empty picture
  useEffect(() => {
    const c = canvas.current; if (!c || !showTurn || !frames) return;
    const im = frames[k]; if (!im) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = Math.round(c.clientWidth * dpr), h = Math.round(c.clientHeight * dpr);
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
    c.getContext("2d")?.drawImage(im, 0, 0, w, h);
  }, [showTurn, frames, k, cut]);

  const stopAnim = () => cancelAnimationFrame(anim.current);
  const tweenTo = (target: number, ms: number) => new Promise<void>((res) => {
    stopAnim();
    const a0 = aRef.current;
    let t0 = -1;
    const ease = (u: number) => u < 0.5 ? 4 * u ** 3 : 1 - (-2 * u + 2) ** 3 / 2;
    const tick = (now: number) => {
      if (t0 < 0) t0 = now;
      const u = Math.min(1, (now - t0) / ms);
      setA(a0 + (target - a0) * ease(u));
      if (u < 1) anim.current = requestAnimationFrame(tick); else res();
    };
    anim.current = requestAnimationFrame(tick);
  });
  // a flick keeps going at the finger's speed and slows to the frame it projects to (exponential, like a scroll)
  const glide = (v: number) => {
    const a0 = aRef.current;
    if (REDUCED() || Math.abs(v) < 0.6) { setA(Math.round(a0)); return; }
    const target = Math.round(a0 + Math.max(-n, Math.min(n, project(v))));
    const tau = Math.max(0.12, Math.abs((target - a0) / v));
    let t0 = -1;
    stopAnim();
    const tick = (now: number) => {
      if (t0 < 0) t0 = now;
      const x = target - (target - a0) * Math.exp(-(now - t0) / 1000 / tau);
      if (Math.abs(target - x) < 0.02) { setA(target); return; }
      setA(x); anim.current = requestAnimationFrame(tick);
    };
    anim.current = requestAnimationFrame(tick);
  };
  // back to the fly-through's frame (the way it came, the short way round) before anything flies
  const rewind = () => {
    stopAnim();
    if (eRef.current) setE(0);
    const a0 = aRef.current, home = Math.round(a0 / n) * n;
    if (REDUCED() || Math.abs(home - a0) < 0.01) { setA(0); return Promise.resolve(); }
    return tweenTo(home, Math.min(520, 140 + 16 * Math.abs(home - a0))).then(() => setA(0));
  };
  const resetTurn = () => { stopAnim(); setA(0); setE(0); };
  const markTurned = () => { if (turned) return; setTurned(true); try { localStorage.setItem(HINT_KEY, "1"); } catch { /* private window */ } };

  const crossTo = (k2: number, then?: () => void) => {
    const v = video.current; if (!v || !t) return;
    v.pause(); stopAt.current = null; setPlaying(null);
    const target = t.steps[k2].arrive / t.fps + 0.01;
    if (REDUCED()) { setOv(false); setEnding(false); resetTurn(); setOn(k2); v.currentTime = target; then?.(); return; }
    setFading(true);
    window.setTimeout(() => { setOv(false); setEnding(false); resetTurn(); setOn(k2); v.currentTime = target; then?.(); }, 120);
    window.setTimeout(() => unroll(on, k2), 600);   // once the picture is back: the legs this jump passed over draw in
    window.setTimeout(() => setFading(false), 600);   // a seek to the frame it is on may not fire "seeked"
  };
  const goTo = async (k2: number) => {
    const v = video.current; if (!v || !t || k2 < 0 || k2 >= t.steps.length || busy) return;
    if (k2 === on + 1 && !ov && !ending && !REDUCED()) {  // the next step: turn back to the landing frame, then fly there
      setBusy(true); await rewind(); setBusy(false);
      setOn(k2); stopAt.current = t.steps[k2].arrive; setPlaying("to"); void v.play();
      return;
    }
    crossTo(k2);                               // any other step: a short blurred cross-fade, no long rewind
  };
  const playAll = async () => {
    const v = video.current; if (!v || !t || busy) return;
    if (playing) { v.pause(); setPlaying(null); stopAt.current = null; return; }
    if (ov || ending) { crossTo(0, () => { v.currentTime = 0; stopAt.current = null; setPlaying("all"); void v.play(); }); return; }
    setBusy(true); await rewind(); setBusy(false);
    if (v.ended || frame >= t.frames - 2) v.currentTime = 0;
    stopAt.current = null; setPlaying("all"); void v.play();
  };
  const toggleOv = () => {
    if (ov) { crossTo(on); return; }
    setEnding(false);
    const v = video.current; v?.pause(); stopAt.current = null; setPlaying(null); stopAnim();
    if (REDUCED()) { setOv(true); setA(0); setE(0); return; }
    setFading(true);
    window.setTimeout(() => { setOv(true); setA(0); setE(0); setFading(false); }, 140);
  };
  const higher = () => { markTurned(); setE(e ? 0 : 1); };
  // the answer: the whole hub, everything grey but the store Spoor names and the carton in it
  const goAnswer = async () => {
    const v = video.current; if (!v || !t || busy) return;
    if (endAt != null) {
      const last = steps.length - 1;
      if (on === last && !ov && !ending && !REDUCED()) {   // from the last step: fly on into the ending
        setBusy(true); await rewind(); setBusy(false);
        stopAt.current = null; setPlaying("to"); void v.play();
        return;
      }
      v.pause(); stopAt.current = null; setPlaying(null);
      const go = () => { setOv(false); resetTurn(); setOn(last); v.currentTime = endAt / t.fps + 0.01; };
      if (REDUCED()) { go(); return; }
      setFading(true); window.setTimeout(go, 120); window.setTimeout(() => setFading(false), 600);
      return;
    }
    v.pause(); stopAt.current = null; setPlaying(null); stopAnim();
    const show = () => { setOv(true); setEnding(true); setOn(steps.length - 1); setA(0); setE(0); };
    if (REDUCED()) { show(); return; }
    setFading(true);
    window.setTimeout(() => { show(); setFading(false); }, 140);
  };

  // drag to turn: 1:1 with the pointer (half a turn across the picture), a flick carries on; up/down changes height
  const drag = useRef<{ x: number; y: number; a0: number; e0: number; id: number; moved: boolean; hist: { t: number; a: number }[] } | null>(null);
  const canTurn = resting && !ending && !!spin && !!place && !!ringReady(base, place, 0) && !busy;
  const onDown = (ev: React.PointerEvent) => {
    // a drag may start anywhere on the picture, pins included (the step's pin sits in the middle); only the controls are out
    if (ev.button !== 0 || (ev.target as Element).closest(".ht-ctl, .ht-ev")) return;
    ev.preventDefault();   // a drag on the picture never selects the page's text (also before it can turn)
    if (!canTurn) return;
    stopAnim();
    drag.current = { x: ev.clientX, y: ev.clientY, a0: aRef.current, e0: eRef.current, id: ev.pointerId, moved: false, hist: [{ t: ev.timeStamp, a: aRef.current }] };
  };
  const onMove = (ev: React.PointerEvent) => {
    const d = drag.current; if (!d || ev.pointerId !== d.id) return;
    const dx = ev.clientX - d.x, dy = ev.clientY - d.y;
    if (!d.moved && Math.hypot(dx, dy) < 5) return;
    // captured only once it is a drag, so a plain click on a pin still picks that step
    if (!d.moved) { d.moved = true; markTurned(); ev.currentTarget.setPointerCapture(ev.pointerId); }
    const w = stage.current?.clientWidth ?? 900;
    const na = d.a0 - dx / (w / (n / 2));
    setA(na);
    if (ringReady(base, place!, 1)) { if (d.e0 === 0 && dy > 40) setE(1); else if (d.e0 === 1 && dy < -40) setE(0); else if (Math.abs(dy) < 20) setE(d.e0); }
    d.hist.push({ t: ev.timeStamp, a: na });
    if (d.hist.length > 8) d.hist.shift();
  };
  const onUp = (ev: React.PointerEvent) => {
    const d = drag.current; drag.current = null; if (!d || !d.moved) return;
    const h = d.hist.filter((p) => ev.timeStamp - p.t < 100);
    const f = h[0], l = h.at(-1);
    glide(f && l && l.t > f.t ? (l.a - f.a) / ((l.t - f.t) / 1000) : 0);
  };
  const onKey = (ev: React.KeyboardEvent) => {
    if (!canTurn) return;
    const keys: Record<string, () => void> = {
      ArrowLeft: () => setA(Math.round(aRef.current) + 1), ArrowRight: () => setA(Math.round(aRef.current) - 1),
      ArrowUp: () => ringReady(base, place!, 1) && setE(1), ArrowDown: () => setE(0), Home: () => resetTurn(),
    };
    const f = keys[ev.key]; if (!f) return;
    ev.preventDefault(); ev.stopPropagation(); stopAnim(); markTurned(); f();
  };

  const cur = steps[on];
  const ev = evAt === on;
  // the cameras this route was seen on, with their step numbers (for the camera setup's highlight)
  const used: Record<string, number[]> = {};
  steps.forEach((c, i) => { if (/^(CAM|CHK)_/.test(c.camera)) (used[c.camera] ??= []).push(i + 1); });
  const modes = (
    <div className="ht-modes" role="tablist" aria-label="3D hub view">
      <button type="button" role="tab" aria-selected={mode === "route"} onClick={() => setMode("route")}>The parcel&apos;s route</button>
      <button type="button" role="tab" aria-selected={mode === "cameras"} onClick={() => { video.current?.pause(); setPlaying(null); setMode("cameras"); }}>Camera setup</button>
    </div>
  );
  if (mode === "cameras") return <div className="ht">{modes}<CameraSetup used={used} /></div>;
  if (tour === "none") return <div className="ht">{modes}<p className="ht-none">The 3D route has not been exported for this case yet.</p></div>;
  // at rest the marks come from the turntable's table (its first frame is the video's), while flying from the video's
  const pins: UV[] = ring ? ring.pins[k] : t?.pins[Math.min(frame, t.pins.length - 1)] ?? [];
  // the carton stays where it was last seen: a step that is only a record (the truck's manifest) does not move it
  let held = ending ? steps.length - 1 : on; while (held > 0 && steps[held]?.tone === "record") held -= 1;
  const mk: UV | undefined = ring ? ring.pins[k][held] : t?.marker[Math.min(frame, t.marker.length - 1)];
  const camUV = ring && !ov && cur ? ring.cams[k]?.[cur.camera] : null;
  const pinUV = pins[on];
  // the camera's name gives way to the step's tag (which hangs right of its pin) when the two would touch
  const camNearTag = inView(camUV) && inView(pinUV) && camUV[0] - pinUV[0] > -0.06 && camUV[0] - pinUV[0] < 0.26 && Math.abs(camUV[1] - pinUV[1]) < 0.12;
  const ovWait = ov && !frames;
  const Pm = ring ? ring.P?.[k] : t?.P?.[Math.min(frame, (t?.P?.length ?? 1) - 1)];
  const vol = answer && Pm ? volume(Pm, answer.polygons[0], 2.4) : null;
  // the step is inside the answer zone: the zone pulses once when you arrive (keyed by the step, no loop)
  const inAnswer = (i: number) => { const xy = steps[i]?.xy, r = answer?.polygons[0]; if (!xy || !r) return false;
    const xs = r.map((q) => q[0]), ys = r.map((q) => q[1]); return xy[0] >= Math.min(...xs) && xy[0] <= Math.max(...xs) && xy[1] >= Math.min(...ys) && xy[1] <= Math.max(...ys); };

  // story mode. The table's points are y-up (Blender's camera view); the page draws y-down
  const flat = (q: UV | undefined | null): XY | null => q ? [q[0], 1 - q[1]] : null;
  const proj = (x: number, y: number, z = MARK_Z): XY | null => Pm ? onFrame(Pm, x, y, z) : null;
  const tms = steps.map((c) => Date.parse(c.t));
  const arrive = t?.steps.map((x) => x.arrive) ?? [];
  // a move was seen only where the journey has an observed span over most of it (being carried to the store, here)
  const observed = (jr.data?.objects[0]?.segments ?? []).filter((x) => x.kind === "observed").map((x) => [Date.parse(x.start), Date.parse(x.end)]);
  const seenMove = (i: number, j: number) => { const a0 = tms[i], a1 = tms[j]; if (!(a1 > a0)) return false;
    return observed.reduce((sum, [b0, b1]) => sum + Math.max(0, Math.min(a1, b1) - Math.max(a0, b0)), 0) / (a1 - a0) >= 0.5; };
  const flying = playing ? ways.find((w) => w.kind !== "held" && frame >= arrive[w.from] && frame < arrive[w.to]) : undefined;
  const mkTop = flat(mk);
  // on the ending only the last carry is drawn, and only its part inside the picture
  const lastWay = ways.filter((w) => w.kind !== "held").at(-1);
  const route = t && !fading ? ways.filter((w) => w.kind !== "held" && (!ending || endAt == null || w === lastWay)).map((w) => {
    const line = w.path.map(([x, y, z]) => proj(x, y, z ?? 0)).filter((q): q is XY => !!q);
    const unrolling = pen && w.from >= pen.from && w.to <= pen.upTo && line.length > 1;
    const [done, rest]: [XY[], XY[]] = unrolling ? [prefix(line, pen.u), line]
      : ending && endAt != null ? [tailInside(line), []]
      : ending || (w !== flying && w.to <= on) ? [line, []]
      : w === flying && mkTop && line.length > 1 ? splitAt(line, mkTop) : [[], line];
    const gap = !seenMove(w.from, w.to), mins = Math.round((tms[w.to] - tms[w.from]) / 60000);
    return { w, done, rest, gap, tag: gap && mins >= 1 && line.length > 1 ? { at: line[Math.floor(line.length / 2)], text: `No camera · ${mins} min` } : null };
  }) : [];
  // the cameras that recorded a step at this place, as soft beams onto it: the step's own camera indigo, the others
  // faint (a camera is only drawn for a step it recorded: nothing is claimed for the rest)
  const group = groups.find((g) => g.includes(on)) ?? [on];
  const placeCams = [...new Set(group.map((i) => steps[i]?.camera).filter((c): c is string => !!c && isCam(c)))];
  const beam = (cid: string) => {
    const cA = camAt[cid], xy = steps[group.find((i) => steps[i].camera === cid) ?? on]?.xy;
    if (!cA || !xy) return null;
    const [sx, sy] = xy; let dx = sx - cA[0], dy = sy - cA[1]; const l = Math.hypot(dx, dy) || 1; dx /= l; dy /= l;
    const c = proj(cA[0], cA[1], cA[2]), p1 = proj(sx - dy * 1.1, sy + dx * 1.1, 0.4), p2 = proj(sx + dy * 1.1, sy - dx * 1.1, 0.4);
    return c && p1 && p2 && inView(c) ? { cid, c, p1, p2, best: hoverCam ? cid === hoverCam : cid === cur?.camera } : null;
  };
  const beams = !ov && !ending && cur ? placeCams.map(beam).filter((b): b is NonNullable<ReturnType<typeof beam>> => !!b) : [];
  // the step the parcel has reached: its pin springs in as it gets there
  const reached = ending ? steps.length - 1 : playing ? arrive.reduce((b, f, j) => (f <= frame ? j : b), 0) : on;
  const carton3d = !!t?.ending;   // a tour rendered with the carton in the scene: no drawn carton on top
  const trail = playing && t && mkTop ? [4, 8, 12, 16, 20].map((d) => flat(t.marker[Math.max(0, frame - d)]))
    .filter((q): q is XY => !!q && Math.hypot(q[0] - mkTop[0], q[1] - mkTop[1]) > 0.006) : [];
  // the story clock: the step's time at rest; while flying it runs from one step's time to the next's (a wait in place
  // runs it too), so eleven minutes in a cage pass as a fast count
  const near = (i: number) => { const p = steps[i - 1]?.xy, q = steps[i]?.xy; return !!p && !!q && Math.hypot(p[0] - q[0], p[1] - q[1]) < 0.5; };
  let clock = tms[on];
  if (playing && t && arrive.length) {
    const i = arrive.reduce((b, f, j) => (f <= frame ? j : b), 0);
    clock = tms[i];
    if (i < steps.length - 1) {
      const f0 = near(i + 1) ? arrive[i] : arrive[i] + Math.round(t.fps * (i === 0 || !near(i) ? 1.0 : 0.7));
      clock = tms[i] + (tms[i + 1] - tms[i]) * Math.min(1, Math.max(0, (frame - f0) / Math.max(1, arrive[i + 1] - f0)));
    }
  }
  const inside = state.data?.answer?.objects.find((o) => o.inside)?.inside ?? null;
  const placeName = (inside?.place ?? first?.name ?? "").replace(/^Z\d+ /, "").replace(/\s*\(Z\d+\)$/, "");

  return (
    <div className="ht" onKeyDown={(ev) => { if (ev.key === "ArrowRight") void goTo(on + 1); if (ev.key === "ArrowLeft") void goTo(on - 1); }}>
      {modes}
      <div className="ht-main">
        <div ref={stage} className="ht-stage" data-fading={fading ? "" : undefined} data-turn={canTurn ? "" : undefined}
          style={t ? { aspectRatio: `${t.size[0]} / ${t.size[1]}` } : undefined} tabIndex={canTurn ? 0 : -1} onKeyDown={onKey}
          onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp} onDoubleClick={(ev) => { if (!(ev.target as Element).closest("button, .ht-ev") && canTurn) void rewind(); }}
          aria-label={canTurn ? "The hub around this step. Drag, or use the arrow keys, to turn it; up and down to look from higher or lower." : undefined}>
          {t && <video ref={video} className="ht-video" src={`/tour/${caseId}/tour.mp4`} muted playsInline preload="auto"
            onSeeked={() => setFading(false)} onEnded={() => { if (playing === "all" && endAt == null) window.setTimeout(() => void goAnswer(), 700); }}
            aria-label="Fly-through of the hub model along the parcel's route" />}
          <canvas ref={canvas} key={`cut${cut}`} className="ht-turn" data-on={showTurn ? "" : undefined} data-cut={cut ? "" : undefined} aria-hidden />
          {ovWait && <span className="ht-wait" />}
          <span className="ht-vignette" aria-hidden />
          {t && !ovWait && (
            <div className="ht-marks" data-ending={ending ? "" : undefined} aria-hidden>
              {vol && (
                <svg className="ht-zone" viewBox="0 0 1 1" preserveAspectRatio="none" key={ending ? "zend" : inAnswer(on) && resting ? `z${on}` : "z"}
                  data-pulse={(inAnswer(on) && resting) || ending ? "" : undefined} data-glow={ending ? "" : undefined}>
                  {vol.walls.map((w, i) => <polygon key={i} className="ht-zone-wall" points={w} />)}
                  {vol.floor && <polygon className="ht-zone-floor" points={vol.floor} />}
                  {vol.top && <polygon className="ht-zone-top" points={vol.top} />}
                </svg>
              )}
              {route.length > 0 && (
                <svg className="ht-route" viewBox="0 0 1 1" preserveAspectRatio="none">
                  {route.map(({ w, rest, gap }) => rest.length > 1 && <polyline key={`r${w.to}`} className="ht-r-next" data-gap={gap ? "" : undefined} points={pts(rest)} />)}
                  {route.map(({ w, done }) => done.length > 1 && <polyline key={`h${w.to}`} className="ht-r-halo" points={pts(done)} />)}
                  {route.map(({ w, done, gap }) => done.length > 1 && <polyline key={`d${w.to}`} className="ht-r-done" data-gap={gap ? "" : undefined} points={pts(done)} />)}
                </svg>
              )}
              {route.map(({ w, tag }) => tag && inView(tag.at) && !ending && (
                <span key={`g${w.to}`} className="ht-gap-tag" style={{ left: `${tag.at[0] * 100}%`, top: `${tag.at[1] * 100}%` }}>{tag.text}</span>
              ))}
              {beams.length > 0 && (
                <svg className="ht-beams" viewBox="0 0 1 1" preserveAspectRatio="none" key={`b${group[0]}`} data-out={!resting ? "" : undefined}>
                  <defs>
                    {beams.map((b) => (
                      <linearGradient key={b.cid} id={`ht-beam-${b.cid}`} gradientUnits="userSpaceOnUse" x1={b.c[0]} y1={b.c[1]} x2={(b.p1[0] + b.p2[0]) / 2} y2={(b.p1[1] + b.p2[1]) / 2}>
                        <stop offset="0" stopColor={b.best ? "#a5b4fc" : "#ffffff"} stopOpacity={b.best ? 0.5 : 0.25} />
                        <stop offset="1" stopColor={b.best ? "#818cf8" : "#ffffff"} stopOpacity={b.best ? 0.32 : 0.12} />
                      </linearGradient>
                    ))}
                  </defs>
                  {beams.map((b) => <polygon key={b.cid} className="ht-beam" data-best={b.best ? "" : undefined} points={pts([b.c, b.p1, b.p2])} fill={`url(#ht-beam-${b.cid})`} />)}
                </svg>
              )}
              {inView(camUV) && (
                <button type="button" className="ht-cam" style={{ left: `${camUV[0] * 100}%`, top: `${(1 - camUV[1]) * 100}%` }}
                  tabIndex={-1} onClick={() => setEvAt(on)} aria-label={`See what the ${camShort(cur.camera)} camera recorded at step ${on + 1}`}>
                  <svg viewBox="0 0 24 24" aria-hidden><path d="M4 8h11a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1zM16 11l5-3v8l-5-3" /></svg>
                  {!camNearTag && <small>{camShort(cur.camera)}</small>}
                </button>
              )}
              {groups.map((g) => {
                const p = pins[g[0]]; if (!inView(p)) return null;
                const here = g.includes(on) && !ending, c = steps[here ? on : g[0]];
                // the tag hangs right of its pin, unless another pin or the step's camera is there: then it hangs left
                const under = (q: UV | undefined) => inView(q) && q[0] - p[0] > 0 && q[0] - p[0] < 0.27 && Math.abs(q[1] - p[1]) < 0.07;
                const flip = here && (groups.some((o) => o !== g && under(pins[o[0]])) || under(camUV));
                const label = g.length > 1 ? `${g[0] + 1}–${g.at(-1)! + 1}` : `${g[0] + 1}`;
                return (
                  <button key={g[0]} type="button" tabIndex={-1} className="ht-pin" data-tone={c.tone} data-on={here ? "" : undefined} data-flip={flip ? "" : undefined}
                    data-reached={g[0] <= reached ? "" : undefined}
                    style={{ left: `${p[0] * 100}%`, top: `${(1 - p[1]) * 100}%` }} onClick={() => void goTo(here ? on : g[0])}>
                    <span className="ht-pin-n">{here ? on + 1 : label}</span>
                    {here && <span className="ht-pin-tag"><b>{c.title}</b><small>{hms(c.t)}</small></span>}
                  </button>
                );
              })}
              {trail.map((q, i) => (
                <span key={i} className="ht-trail" style={{ left: `${q[0] * 100}%`, top: `${q[1] * 100}%`, opacity: 0.55 - i * 0.1, scale: `${1 - i * 0.12}` }} />
              ))}
              {inView(mk) && !carton3d && (
                <span className="ht-carton" style={{ left: `${mk[0] * 100}%`, top: `${(1 - mk[1]) * 100}%` }}>
                  <svg viewBox="0 0 32 32"><path className="ht-c-top" d="M16 4 28 10 16 16 4 10z" /><path className="ht-c-l" d="M4 10 16 16v13L4 23z" /><path className="ht-c-r" d="M28 10 16 16v13l12-6z" /><path className="ht-c-tape" d="M10 7 22 13v3" /></svg>
                </span>
              )}
            </div>
          )}
          {t && !ending && Number.isFinite(clock) && (
            <span className="ht-clock" aria-hidden>
              <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></svg>
              {new Date(clock).toLocaleTimeString("en-GB", { timeZone: "Asia/Kuala_Lumpur", hour12: false })}
            </span>
          )}
          {ending && !fading && (
            <div className="ht-end" role="status" data-foot={endAt != null ? "" : undefined}>
              {/* "here" only while the carton is in the picture: the words never point at empty floor */}
              <b>{inView(mk) || endAt == null ? "Most likely here" : `Most likely in the ${placeName}`}</b>
              {inside && <small>{placeName}{inside.carried_in_at ? ` · carried in at ${inside.carried_in_at}, not seen coming out` : ""}</small>}
            </div>
          )}
          {!t && <span className="ht-wait" />}
          {ev && cur && reel.data && (
            <div className="ht-ev" role="dialog" aria-label={`What ${camWords(cur.camera).replace(/^The /, "the ")} recorded at step ${on + 1}`}>
              {/* the step's own stretch of the journey reel: the camera's recording, the outline and the clock as filmed, and the
                  reel's own title for the step (so nothing here repeats it; the way back sits on the floor, bottom centre) */}
              <video key={on} className="ht-ev-v" src={`${signedUrl(reel.data.url)}#t=${cur.start_s},${cur.end_s}`} poster={cur.thumb_url ? signedUrl(cur.thumb_url) : undefined}
                autoPlay muted playsInline onTimeUpdate={(e) => { const v = e.currentTarget; if (v.currentTime >= cur.end_s - 0.05) { v.currentTime = cur.start_s; void v.play(); } }} />
              <button type="button" className="hc-x ht-ev-x" onClick={() => setEvAt(null)}>
                <svg viewBox="0 0 24 24" aria-hidden><path d="M15 5l-7 7 7 7" /></svg>Back to the route</button>
            </div>
          )}
          {cmp && truth && truth !== "none" && (
            <TruthCompare src={`/tour/${caseId}/truth.mp4`} truth={truth} legs={ways.filter((w) => w.kind !== "held").map((w) => w.path)}
              zone={answer?.polygons[0]} answerZone={first?.zone_id?.replace(/^zone_/, "") ?? null} answerName={placeName} onClose={() => setCmp(false)} />
          )}
          {canTurn && !turned && (
            <span className="ht-hint" aria-hidden>
              <svg viewBox="0 0 24 24"><path d="M20 12a8 8 0 1 1-2.34-5.66" /><path d="M20 4v4.5h-4.5" /></svg>Drag to look around
            </span>
          )}
          <div className="ht-ctl">
            <button type="button" className="ht-play" data-primary={!playing ? "" : undefined} onClick={() => void playAll()} disabled={!t}>
              {playing === "all" ? <svg viewBox="0 0 24 24" aria-hidden><rect x="6.5" y="5" width="4" height="14" rx="1.3" /><rect x="13.5" y="5" width="4" height="14" rx="1.3" /></svg>
                : <svg viewBox="0 0 24 24" aria-hidden><path d="M8 5.6v12.8a1 1 0 0 0 1.5.86l10.4-6.4a1 1 0 0 0 0-1.72L9.5 4.74A1 1 0 0 0 8 5.6Z" /></svg>}
              {playing === "all" ? "Pause" : "Fly the route"}
            </button>
            {spin?.rings.ov && (
              <button type="button" className="ht-play ht-ghost" aria-pressed={ov} onClick={toggleOv} disabled={!t}>
                <svg viewBox="0 0 24 24" aria-hidden className="ht-stroke"><path d="M4 9V5a1 1 0 0 1 1-1h4M15 4h4a1 1 0 0 1 1 1v4M20 15v4a1 1 0 0 1-1 1h-4M9 20H5a1 1 0 0 1-1-1v-4" /></svg>
                {ov ? "Back to the step" : "Whole hub"}
              </button>
            )}
          </div>
          {canTurn && spin && place && spin.rings[place].rings.length > 1 && (
            <div className="ht-ctl ht-ctl-r">
              <button type="button" className="ht-play ht-ghost" aria-pressed={e === 1} onClick={higher}>
                <svg viewBox="0 0 24 24" aria-hidden className="ht-stroke">{e ? <path d="M6 9l6 6 6-6" /> : <path d="M6 15l6-6 6 6" />}</svg>
                {e ? "Lower view" : "Higher view"}
              </button>
            </div>
          )}
        </div>
        <ol className="ht-rail" aria-label="Steps">
          {steps.map((c, i) => (
            <li key={i} data-done={i <= on || ending ? "" : undefined}>
              <button type="button" className="ht-step" data-tone={c.tone} aria-current={on === i && !ending ? "step" : undefined} onClick={() => void goTo(i)}>
                <span className="ht-step-n">{i + 1}</span><span className="ht-step-t">{hms(c.t).slice(0, 5)}</span>
              </button>
            </li>
          ))}
          {answer && (
            <li data-done={ending ? "" : undefined}>
              <button type="button" className="ht-step ht-step-end" aria-current={ending ? "step" : undefined} onClick={() => void goAnswer()}>
                <span className="ht-step-n"><svg viewBox="0 0 24 24" aria-hidden><path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11z" /><circle cx="12" cy="10" r="2.3" /></svg></span>
                <span className="ht-step-t">Answer</span>
              </button>
            </li>
          )}
        </ol>
      </div>

      {ending && (
        <aside className="ht-card" aria-live="polite">
          <figure className="ht-frame">
            {/* eslint-disable-next-line @next/next/no-img-element -- the last step at the store, cut from its camera by the API */}
            {steps[held]?.thumb_url ? <img src={signedUrl(steps[held].thumb_url!)} alt={`${steps[held].title}, ${camWords(steps[held].camera)}`} /> : <span className="ht-frame-none">No camera saw this step</span>}
          </figure>
          <div className="ht-card-top"><span className="ht-n">The answer</span><span className="ht-chip" data-tone="seen">Most likely</span></div>
          <h3 className="ht-title">In the {placeName || "place Spoor names"}</h3>
          {inside && (
            <p className="ht-sub">
              {inside.carried_in_at && `Carried in at ${inside.carried_in_at}. `}
              {inside.came_out_empty?.[0] && `Came out without it at ${inside.came_out_empty[0]}. `}
              {inside.until && `Not seen coming out until the recording ends at ${inside.until}.`}
            </p>
          )}
          <p className="ht-meta">No camera sees inside; the door is the only way in (site plan)</p>
          <div className="ht-acts">
            <button type="button" className="ht-btn" onClick={() => void goTo(steps.length - 1)} aria-label="Back to the last step">
              <svg viewBox="0 0 24 24" aria-hidden><path d="M15 5l-7 7 7 7" /></svg></button>
            <a className="ht-btn ht-btn-main" href={`/cases/${caseId}/search`}>Go look</a>
            <span />
          </div>
          {truth !== "none" && (
            <button type="button" className="ht-truth-btn" onClick={compare} aria-pressed={cmp}>
              <svg viewBox="0 0 24 24" aria-hidden><path d="M8 5.6v12.8a1 1 0 0 0 1.5.86l10.4-6.4a1 1 0 0 0 0-1.72L9.5 4.74A1 1 0 0 0 8 5.6Z" /></svg>
              Compare with what really happened
            </button>
          )}
        </aside>
      )}
      {cur && !ending && (
        <aside className="ht-card" aria-live="polite">
          <figure className="ht-frame">
            {cur.thumb_url
              ? <button type="button" className="ht-frame-open" onClick={() => setEvAt(on)} aria-label={`Play step ${on + 1} as ${camWords(cur.camera).toLowerCase()} recorded it`}>
                  {/* eslint-disable-next-line @next/next/no-img-element -- the step's own frame, cut from its camera by the API */}
                  <img key={on} src={signedUrl(cur.thumb_url)} alt={`${cur.title}, ${camWords(cur.camera)}`} /></button>
              : <span className="ht-frame-none">No camera saw this step</span>}
          </figure>
          <div className="ht-card-top"><span className="ht-n">Step {on + 1} of {steps.length}</span><span className="ht-chip" data-tone={cur.tone}>{cur.last_scan ? "Last scan" : CHIP[cur.tone]}</span></div>
          <h3 className="ht-title">{cur.title}</h3>
          {cur.sub && <p className="ht-sub">{cur.sub}</p>}
          {placeCams.length > 1 && (
            <div className="ht-seen" onMouseLeave={() => setHoverCam(null)}>
              <span className="ht-seen-h">Seen here by {placeCams.length} cameras</span>
              <div className="ht-seen-row">
                {[...placeCams].sort((x, y) => Number(y === cur.camera) - Number(x === cur.camera)).map((cid) => {
                  const i = group.find((j) => steps[j].camera === cid) ?? on, own = cid === cur.camera;
                  return (
                    <button key={cid} type="button" className="ht-seen-cam" data-best={own ? "" : undefined} onMouseEnter={() => setHoverCam(cid)} onFocus={() => setHoverCam(cid)}
                      onBlur={() => setHoverCam(null)} onClick={() => (own ? setEvAt(on) : void goTo(i))} aria-label={`${camWords(cid)}, step ${i + 1}`}>
                      {/* eslint-disable-next-line @next/next/no-img-element -- the step's own frame from that camera */}
                      {steps[i].thumb_url ? <img src={signedUrl(steps[i].thumb_url!)} alt="" /> : <span />}
                      <small>{camShort(cid)}</small>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
          <p className="ht-meta">{hms(cur.t)} · {camWords(cur.camera)}</p>
          <div className="ht-acts">
            <button type="button" className="ht-btn" onClick={() => void goTo(on - 1)} disabled={on === 0} aria-label="Previous step">
              <svg viewBox="0 0 24 24" aria-hidden><path d="M15 5l-7 7 7 7" /></svg></button>
            <button type="button" className="ht-btn ht-btn-main" onClick={() => {
              window.dispatchEvent(new CustomEvent(SEEK_JOURNEY, { detail: on }));
              document.querySelector(".pf-reel")?.scrollIntoView({ behavior: REDUCED() ? "auto" : "smooth", block: "center" });
            }}>Watch it on camera</button>
            <button type="button" className="ht-btn" onClick={() => void goTo(on + 1)} disabled={on >= steps.length - 1} aria-label="Next step">
              <svg viewBox="0 0 24 24" aria-hidden><path d="M9 5l7 7-7 7" /></svg></button>
          </div>
        </aside>
      )}
      <p className="ht-note">
        {answer && <span className="ht-key"><i aria-hidden />Where Spoor says to search first{first ? `: the ${first.name.replace(/^Z\d+ /, "").replace(/\s*\(Z\d+\)$/, "")}` : ""}.</span>}
        The hub model, rendered in Blender. The pins and the carton are placed from the cameras and scans; the moves between steps are drawn, not filmed.
      </p>
    </div>
  );
}
