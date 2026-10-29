/**
 * Frame-accurate context playback (review 007 #1). Pure helpers, no React: the browser plays a clip's H.264 working
 * proxy (same frames as the original, checked at ingest), and every frame index shown or paused on is mapped back
 * through the ORIGINAL's frame table (pts in ms). Kept free of path aliases so the unit tests can import it directly.
 */

export interface Playback {
  media_id: string;
  camera_id: string;
  proxy_media_id: string;
  url: string;
  expires: number;
  pts_ms: number[];
  frame_count: number;
  start_utc: string | null;
  time_uncertainty_ms: number | null;
  sha256: string;
  proxy_sha256: string;
  label: string;
}

/** Index of the frame whose pts is nearest to `ms` (pts sorted ascending). */
export function nearestFrame(pts: number[], ms: number): number {
  if (pts.length === 0) return 0;
  let lo = 0;
  let hi = pts.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (pts[mid] < ms) lo = mid + 1;
    else hi = mid;
  }
  if (lo > 0 && Math.abs(pts[lo - 1] - ms) <= Math.abs(pts[lo] - ms)) return lo - 1;
  return lo;
}

/** Frame index shown at a video element's media time (seconds from the first frame). */
export function frameAtMediaTime(pts: number[], seconds: number): number {
  return nearestFrame(pts, (pts[0] ?? 0) + seconds * 1000);
}

/** Media time to seek to so the element shows exactly frame `idx`: the frame's own pts plus 1 ms, which lands inside
 * the frame's display interval rather than on the boundary with the previous frame. */
export function seekTimeFor(pts: number[], idx: number): number {
  const i = Math.max(0, Math.min(pts.length - 1, idx));
  return ((pts[i] ?? 0) - (pts[0] ?? 0) + 1) / 1000;
}

/** First frame at most `seconds` before frame `idx` (the pre-roll a context playback starts from). */
export function prerollStart(pts: number[], idx: number, seconds: number): number {
  if (!pts.length) return 0;
  const i = Math.max(0, Math.min(pts.length - 1, idx));
  return nearestFrame(pts, pts[i] - seconds * 1000);
}

/** Normalized time (ms since epoch) of frame `idx`, from the clip's recorded start on the case timeline. */
export function frameUtcMs(p: Pick<Playback, "pts_ms" | "start_utc">, idx: number): number | null {
  if (!p.start_utc || !p.pts_ms.length) return null;
  const i = Math.max(0, Math.min(p.pts_ms.length - 1, idx));
  return Date.parse(p.start_utc) + p.pts_ms[i] - p.pts_ms[0];
}

/** Synchronized wall: where each clip should be at wall time `t` (seconds from the earliest clip start). Returns null
 * when the clip has no footage at that time (before its start or after its last frame). */
export function wallLocalTime(t: number, offsetS: number, durationS: number): number | null {
  const local = t - offsetS;
  return local < 0 || local > durationS ? null : local;
}

/** Grid for a camera wall page: 1, 2x2 or 3x3 tiles (review 007 #1). */
export function wallColumns(n: number): 1 | 2 | 3 {
  return n <= 1 ? 1 : n <= 4 ? 2 : 3;
}
