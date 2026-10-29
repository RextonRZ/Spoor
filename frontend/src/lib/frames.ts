/**
 * Site frame <-> renderer frame, and camera view geometry from the mounting plan (PRD §13.5).
 *
 * Site frame (backend storage): X east, Y north, Z up, metres. Renderer (three.js / glTF): Y up.
 * The backend owns the transform (spoor.spatial.frames.SITE_TO_RENDERER, served by /v1/capabilities); this module
 * applies whatever matrix the backend sends and falls back to the same constant, which a unit test pins to the
 * backend source. site (x, y, z) -> renderer (x, z, -y).
 */
export type Vec3 = [number, number, number];
export type Mat3 = [Vec3, Vec3, Vec3];

export const DEFAULT_SITE_TO_RENDERER: Mat3 = [
  [1, 0, 0],
  [0, 0, 1],
  [0, -1, 0],
];

let active: Mat3 = DEFAULT_SITE_TO_RENDERER;

/** Install the backend's matrix. Rejects anything that is not a proper rotation (det +1, orthonormal). */
export function setSiteToRenderer(m: number[][] | undefined | null): boolean {
  if (!m || m.length !== 3 || m.some((r) => r.length !== 3)) return false;
  const M = m as Mat3;
  const det =
    M[0][0] * (M[1][1] * M[2][2] - M[1][2] * M[2][1]) -
    M[0][1] * (M[1][0] * M[2][2] - M[1][2] * M[2][0]) +
    M[0][2] * (M[1][0] * M[2][1] - M[1][1] * M[2][0]);
  if (Math.abs(det - 1) > 1e-9) return false;
  active = M.map((r) => [...r]) as Mat3;
  return true;
}

export function siteToRenderer([x, y, z]: Vec3, m: Mat3 = active): Vec3 {
  return [
    m[0][0] * x + m[0][1] * y + m[0][2] * z,
    m[1][0] * x + m[1][1] * y + m[1][2] * z,
    m[2][0] * x + m[2][1] * y + m[2][2] * z,
  ];
}

export function rendererToSite([x, y, z]: Vec3, m: Mat3 = active): Vec3 {
  // Inverse of a rotation is its transpose.
  return [
    m[0][0] * x + m[1][0] * y + m[2][0] * z,
    m[0][1] * x + m[1][1] * y + m[2][1] * z,
    m[0][2] * x + m[1][2] * y + m[2][2] * z,
  ];
}

export interface MountedCamera {
  position_m: [number, number];
  height_m: number;
  /** Degrees counter-clockwise from +X (east), as in hub_spec and the Blender build. */
  heading_deg: number;
  tilt_down_deg: number;
  hfov_deg: number;
  vfov_deg: number;
}

const rad = (d: number) => (d * Math.PI) / 180;

/** Unit view basis in site coordinates: forward, right, up. */
export function cameraBasis(c: MountedCamera): { fwd: Vec3; right: Vec3; up: Vec3 } {
  const yaw = rad(c.heading_deg);
  const tilt = rad(c.tilt_down_deg);
  const fwd: Vec3 = [Math.cos(yaw) * Math.cos(tilt), Math.sin(yaw) * Math.cos(tilt), -Math.sin(tilt)];
  const right: Vec3 = [Math.sin(yaw), -Math.cos(yaw), 0];
  const up: Vec3 = [
    right[1] * fwd[2] - right[2] * fwd[1],
    right[2] * fwd[0] - right[0] * fwd[2],
    right[0] * fwd[1] - right[1] * fwd[0],
  ];
  return { fwd, right, up };
}

/** Ray direction (site frame, unit) through normalized image coords u,v in [-1,1] (u right, v up). */
export function viewRay(c: MountedCamera, u: number, v: number): Vec3 {
  const { fwd, right, up } = cameraBasis(c);
  const th = Math.tan(rad(c.hfov_deg) / 2);
  const tv = Math.tan(rad(c.vfov_deg) / 2);
  const d: Vec3 = [0, 1, 2].map((k) => fwd[k] + u * th * right[k] + v * tv * up[k]) as Vec3;
  const n = Math.hypot(...d);
  return d.map((x) => x / n) as Vec3;
}

/**
 * Approximate floor footprint (site XY polygon) of what a camera can see, from its mounting plan. No occlusion,
 * no lens distortion: the UI must label it "approximate FOV" (PRD §13.5). Rays above the horizon stop at maxRange.
 */
export function floorFootprint(c: MountedCamera, maxRange = 45, steps = 6): [number, number][] {
  const border: [number, number][] = [];
  for (let i = 0; i < steps; i++) border.push([-1 + (2 * i) / steps, -1]);
  for (let i = 0; i < steps; i++) border.push([1, -1 + (2 * i) / steps]);
  for (let i = 0; i < steps; i++) border.push([1 - (2 * i) / steps, 1]);
  for (let i = 0; i < steps; i++) border.push([-1, 1 - (2 * i) / steps]);
  const [x, y] = c.position_m;
  return border.map(([u, v]) => {
    const d = viewRay(c, u, v);
    let t: number;
    if (d[2] < -1e-6) {
      t = c.height_m / -d[2];
      const horiz = Math.hypot(d[0], d[1]) * t;
      if (horiz > maxRange) t *= maxRange / horiz;
    } else {
      t = maxRange / Math.max(Math.hypot(d[0], d[1]), 1e-6);
    }
    return [round2(x + d[0] * t), round2(y + d[1] * t)];
  });
}

/** Frustum edge end points (site frame) for drawing: 4 corner rays to the floor (or to maxRange). */
export function frustumCorners(c: MountedCamera, maxRange = 45): Vec3[] {
  const [x, y] = c.position_m;
  return ([[-1, -1], [1, -1], [1, 1], [-1, 1]] as const).map(([u, v]) => {
    const d = viewRay(c, u, v);
    let t = d[2] < -1e-6 ? c.height_m / -d[2] : maxRange;
    const horiz = Math.hypot(d[0], d[1]) * t;
    if (horiz > maxRange) t *= maxRange / horiz;
    return [x + d[0] * t, y + d[1] * t, Math.max(0, c.height_m + d[2] * t)] as Vec3;
  });
}

export function pointInPolygon([x, y]: [number, number], poly: [number, number][]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [x1, y1] = poly[i];
    const [x2, y2] = poly[j];
    if (y1 > y !== y2 > y && x < ((x2 - x1) * (y - y1)) / (y2 - y1) + x1) inside = !inside;
  }
  return inside;
}

function round2(v: number) {
  return Math.round(v * 100) / 100;
}
