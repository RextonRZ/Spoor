"""Hand-over between a carried carton and the person carrying it, by place and time only (no identity, no appearance).

A person's floor position is the bottom-centre of their box (their feet) through the camera's calibrated pose. A
carried carton is off the floor: it is placed on the plane at hand height, once at 0.8 m and once at 1.2 m, and the
spread between the two is carried as uncertainty. Where the two cameras' views overlap, the carton and a person can
be compared at the same moments: if they stay within reach for long enough, the person is the LIKELY carrier (a
candidate link, never "the same person"); every other person in view is reported with how far away they were, so the
page can say why they do not fit.
"""

from dataclasses import dataclass

import numpy as np

from spoor.contracts import FloorCalibration, RawObservation
from spoor.spatial.homography import image_to_site
from spoor.store import EvidenceStore, epoch_ms

HAND_HEIGHTS_M = (0.8, 1.2)  # a carton carried in the hands: waist to chest
REACH_M = 1.0  # carton centre to the carrier's feet, plus calibration and height uncertainty
MIN_SHARED_S = 2.0  # seen together at least this long
PAIR_MS = 150  # samples from the two cameras count as the same moment within this


@dataclass
class FloorPath:
    track_id: str
    camera_id: str
    t_ms: np.ndarray
    xy: np.ndarray  # (n, 2) floor metres
    spread_m: np.ndarray  # (n,) position uncertainty from the unknown carry height (0 for feet)


@dataclass
class Fit:
    person_track_id: str
    shared_s: float
    median_gap_m: float | None
    verdict: str  # "likely carrier" | "not the carrier"
    reason: str


def floor_path(store: EvidenceStore, track_id: str, cal: FloorCalibration, *, carried: bool) -> FloorPath:
    obs = sorted((o for o in store.find(RawObservation, track_id=track_id)
                  if o.bbox_xyxy_px and o.source_frame.normalized_utc and not store.is_invalid(o.observation_id)),
                 key=lambda o: o.source_frame.normalized_utc)  # fmt: skip
    t = np.array([epoch_ms(o.source_frame.normalized_utc) for o in obs], float)
    b = np.array([o.bbox_xyxy_px for o in obs], float).reshape(-1, 4)
    if carried:
        uv = np.c_[(b[:, 0] + b[:, 2]) / 2, (b[:, 1] + b[:, 3]) / 2]
        lo, hi = (image_to_site(cal, uv, h)[:, :2] for h in HAND_HEIGHTS_M)
        return FloorPath(track_id, cal.camera_id, t, (lo + hi) / 2, np.linalg.norm(hi - lo, axis=1) / 2)
    uv = np.c_[(b[:, 0] + b[:, 2]) / 2, b[:, 3]]
    return FloorPath(track_id, cal.camera_id, t, image_to_site(cal, uv, 0.0)[:, :2], np.zeros(len(t)))


def heading(p: FloorPath) -> str:
    """Compass direction of a path's overall movement, in the site frame (X east, Y north)."""
    ok = np.isfinite(p.xy).all(axis=1)
    if ok.sum() < 2:
        return "unknown"
    d = p.xy[ok][-1] - p.xy[ok][0]
    if np.hypot(*d) < 1.0:
        return "standing still"
    ang = np.degrees(np.arctan2(d[1], d[0])) % 360
    return ["east", "north-east", "north", "north-west", "west", "south-west", "south", "south-east"][int((ang + 22.5) // 45) % 8]


def _gaps(carton: FloorPath, person: FloorPath, shift_ms: float) -> tuple[list[float], list[float], list[float]]:
    """Carton-to-person distances at the same moments, with the person's clock moved by shift_ms: (net of the carton's
    height uncertainty, raw, times)."""
    gaps, raw, times = [], [], []
    pt = person.t_ms + shift_ms
    for i, t in enumerate(carton.t_ms):
        j = int(np.argmin(np.abs(pt - t))) if len(pt) else -1
        if j < 0 or abs(pt[j] - t) > PAIR_MS or not np.isfinite(carton.xy[i]).all()                 or not np.isfinite(person.xy[j]).all():  # fmt: skip
            continue
        d = float(np.linalg.norm(carton.xy[i] - person.xy[j]))
        gaps.append(max(0.0, d - carton.spread_m[i]))
        raw.append(d)
        times.append(t)
    return gaps, raw, times


def carrier_fit(carton: FloorPath, person: FloorPath, clock_tolerance_ms: float = 0.0) -> Fit:
    """The person is the likely carrier if, at SOME alignment of the two cameras' clocks within their combined
    uncertainty, they stay within reach of the carton long enough; ruled out only if no such alignment exists."""
    best = None  # (median gap, shared s, shift ms, median raw distance)
    for shift in np.arange(-clock_tolerance_ms, clock_tolerance_ms + 1, 100.0) if clock_tolerance_ms else [0.0]:
        gaps, raw, times = _gaps(carton, person, float(shift))
        if gaps:
            cand = (float(np.median(gaps)), (max(times) - min(times)) / 1000, float(shift), float(np.median(raw)))
            ok_c = cand[0] <= REACH_M and cand[1] >= MIN_SHARED_S
            ok_b = best is not None and best[0] <= REACH_M and best[1] >= MIN_SHARED_S
            if best is None or (ok_c and not ok_b) or (ok_c == ok_b and cand[3] < best[3]):
                best = cand
    within = f" at any clock alignment within ±{clock_tolerance_ms / 1000:.1f} s" if clock_tolerance_ms else ""
    if best is None:
        ok = np.isfinite(person.xy).all(axis=1)
        if not ok.any():
            return Fit(person.track_id, 0.0, None, "not the carrier", "no floor position")
        last = int(np.flatnonzero(ok)[-1])
        x, y = person.xy[last]
        when = "before" if person.t_ms[last] < carton.t_ms.min() else "after"
        move = heading(person)
        return Fit(person.track_id, 0.0, None, "not the carrier", f"out of view {when} the carton appeared{within}; last "
                   f"seen at ({x:.1f}, {y:.1f}) m, {move if move == 'standing still' else 'heading ' + move}")
    med, shared, shift, _raw = best
    if med <= REACH_M and shared >= MIN_SHARED_S:
        at = f" (best clock alignment {shift / 1000:+.1f} s, within ±{clock_tolerance_ms / 1000:.1f} s)" if clock_tolerance_ms             else ", at the same moments"  # fmt: skip
        return Fit(person.track_id, shared, med, "likely carrier", f"within {med:.1f} m of the carton for {shared:.1f} s{at}")
    where = f"{med:.0f} m from the carton" if med > REACH_M else f"with it for only {shared:.1f} s"
    move = heading(person)
    return Fit(person.track_id, shared, med, "not the carrier",
               f"{where}{within}, {move if move == 'standing still' else 'heading ' + move}")


DOOR_NEAR_M = 1.2  # a person lost from view this close to an area's edge went through its doorway


def _dist_to_poly(poly: np.ndarray, p: np.ndarray) -> float:
    """0 inside the polygon, else the distance to its nearest edge."""
    n, ok = len(poly), False
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
        if (y0 > p[1]) != (y1 > p[1]) and p[0] < (x1 - x0) * (p[1] - y0) / (y1 - y0) + x0:
            ok = not ok
    if ok:
        return 0.0
    best = np.inf
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        t = np.clip(np.dot(p - a, b - a) / max(np.dot(b - a, b - a), 1e-9), 0, 1)
        best = min(best, float(np.linalg.norm(p - (a + t * (b - a)))))
    return best


@dataclass
class AreaCrossing:
    track_id: str
    kind: str  # "went in" | "came out"
    t_ms: float


def area_crossings(paths: list[FloorPath], polygon_m) -> list[AreaCrossing]:
    """People who went into an area (last seen at its edge, walking towards it) or came out of it (first seen at its
    edge, walking away). An area no camera sees inside (e.g. the exception store) is judged at its doorway only."""
    poly = np.asarray(polygon_m, float)
    out = []
    for p in paths:
        ok = np.flatnonzero(np.isfinite(p.xy).all(axis=1))
        if len(ok) < 2:
            continue
        first, last = p.xy[ok[0]], p.xy[ok[-1]]
        d_first, d_last = _dist_to_poly(poly, first), _dist_to_poly(poly, last)
        if d_last <= DOOR_NEAR_M and d_last < d_first:
            out.append(AreaCrossing(p.track_id, "went in", float(p.t_ms[ok[-1]])))
        if d_first <= DOOR_NEAR_M and d_first < d_last:
            out.append(AreaCrossing(p.track_id, "came out", float(p.t_ms[ok[0]])))
    return sorted(out, key=lambda c: c.t_ms)


def area_polygon(store, site, area_id: str) -> tuple[str, list] | None:
    """(name, polygon) of a site-plan area (e.g. a blind room) or a site zone, by id."""
    from .journey import latest_plan

    plan = latest_plan(store, site.site_id)
    for a in (plan.areas if plan else []):
        if a.area_id == area_id:
            return a.name, list(a.polygon_m)
    for z in site.zones:
        if z.zone_id == area_id:
            return z.name, list(z.polygon_m)
    return None


def dist_to_area(polygon_m, xy) -> float:
    return _dist_to_poly(np.asarray(polygon_m, float), np.asarray(xy, float))


def blind_areas_near(store, site, xy, radius_m: float) -> list[dict]:
    """Plan areas no camera sees inside (kind blind_spot) whose edge is within reach of a position, and the cameras
    whose view covers that edge (they watch who goes in and out). General: any blind room or corner on any site."""
    from spoor.contracts import Camera, point_in_polygon

    from .journey import latest_plan

    plan = latest_plan(store, site.site_id)
    out = []
    for a in (plan.areas if plan else []):
        if a.kind != "blind_spot":
            continue
        poly = np.asarray(a.polygon_m, float)
        d = _dist_to_poly(poly, np.asarray(xy, float))
        if d > radius_m + DOOR_NEAR_M:
            continue
        best, edge = np.inf, None
        for i in range(len(poly)):  # the nearest point on the area's edge
            p0, p1 = poly[i], poly[(i + 1) % len(poly)]
            t = np.clip(np.dot(np.asarray(xy) - p0, p1 - p0) / max(np.dot(p1 - p0, p1 - p0), 1e-9), 0, 1)
            q = p0 + t * (p1 - p0)
            if (dq := float(np.linalg.norm(q - np.asarray(xy)))) < best:
                best, edge = dq, q
        watched = [c.camera_id for c in store.find(Camera, site_id=site.site_id)
                   if c.fov_polygon_m and point_in_polygon((float(edge[0]), float(edge[1])), c.fov_polygon_m)]
        out.append({"area_id": a.area_id, "name": a.name, "distance_m": round(d, 2), "doorway_watched_by": watched,
                    "note": "no camera sees inside; who went in and out is visible only at its edge"})
    return out

