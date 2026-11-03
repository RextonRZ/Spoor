/**
 * The turntables behind the route in the Blender hub (assets/tour/spin_render.py): for every place on the route (and
 * the whole hub), rings of frames orbiting it, with where each step's point and each route camera fall on every frame.
 * Rings are loaded whole and decoded before they can be spun, so a drag never waits for a picture.
 */
export type UV = [number, number] | null;
export interface SpinRing { elev: number; pins: UV[][]; cams: Record<string, UV>[]; P?: number[][] }
export interface SpinPlace { steps: number[]; look: [number, number]; rings: SpinRing[] }
export interface Spin { n: number; size: [number, number]; cams: string[]; rings: Record<string, SpinPlace> }

const cache = new Map<string, Promise<HTMLImageElement[]>>();
const got = new Map<string, HTMLImageElement[]>();

export const ringUrl = (base: string, place: string, e: number, k: number) => `${base}/${place}/${e}/f${String(k).padStart(2, "0")}.webp`;

/** every frame of one ring, decoded; the same promise for every caller */
export function loadRing(base: string, place: string, e: number, n: number): Promise<HTMLImageElement[]> {
  const key = `${base}|${place}|${e}`;
  let p = cache.get(key);
  if (!p) {
    p = Promise.all(Array.from({ length: n }, (_, k) => {
      const im = new Image();
      im.decoding = "async";
      im.src = ringUrl(base, place, e, k);
      return im.decode().then(() => im);
    })).then((ims) => { got.set(key, ims); return ims; });
    p.catch(() => cache.delete(key));
    cache.set(key, p);
  }
  return p;
}
export const ringReady = (base: string, place: string, e: number) => got.get(`${base}|${place}|${e}`) ?? null;

/** the place (ring name) a step stands at: step numbers are 1-based, as the reel numbers them */
export const placeOf = (s: Spin | null, step: number) => s ? Object.keys(s.rings).find((k) => s.rings[k].steps.includes(step)) ?? null : null;

/** where a flick comes to rest (Apple's projection, in frames): small input, big output, then snap to a frame */
export const project = (v: number, rate = 0.997) => (v / 1000) * rate / (1 - rate);

/** a floor polygon (and its walls up to h metres) on a frame, from the frame's projection matrix: each face clipped at
 *  the camera's near plane, in the page's 0..1 coordinates (y down). Faces wholly behind the camera are left out. */
export function volume(P: number[], poly: number[][], h: number): { floor: string | null; walls: string[]; top: string | null } {
  const clip = (x: number, y: number, z: number) => [P[0] * x + P[1] * y + P[2] * z + P[3], P[4] * x + P[5] * y + P[6] * z + P[7], P[12] * x + P[13] * y + P[14] * z + P[15]];
  const face = (pts: number[][]) => {
    const near = 0.05, out: number[][] = [];
    pts.forEach((b, i) => {
      const a = pts[(i + pts.length - 1) % pts.length];
      const cut = () => { const t = (near - a[2]) / (b[2] - a[2]); return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, near]; };
      if (b[2] >= near) { if (a[2] < near) out.push(cut()); out.push(b); } else if (a[2] >= near) out.push(cut());
    });
    return out.length > 2 ? out.map((c) => `${((c[0] / c[2] + 1) / 2).toFixed(4)},${((1 - c[1] / c[2]) / 2).toFixed(4)}`).join(" ") : null;
  };
  const floor = face(poly.map((q) => clip(q[0], q[1], 0.03)));
  const top = face(poly.map((q) => clip(q[0], q[1], h)));
  const walls = poly.map((q, i) => { const r = poly[(i + 1) % poly.length]; return face([clip(q[0], q[1], 0), clip(r[0], r[1], 0), clip(r[0], r[1], h), clip(q[0], q[1], h)]); })
    .filter((w): w is string => !!w);
  return { floor, walls, top };
}
