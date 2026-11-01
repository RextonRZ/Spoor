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


def carrier_fit(carton: FloorPath, person: FloorPath) -> Fit:
    gaps, times = [], []
    for i, t in enumerate(carton.t_ms):
        j = int(np.argmin(np.abs(person.t_ms - t))) if len(person.t_ms) else -1
        if j < 0 or abs(person.t_ms[j] - t) > PAIR_MS or not np.isfinite(carton.xy[i]).all() \
                or not np.isfinite(person.xy[j]).all():  # fmt: skip
            continue
        gaps.append(max(0.0, float(np.linalg.norm(carton.xy[i] - person.xy[j])) - carton.spread_m[i]))
        times.append(t)
    if not gaps:
        ok = np.isfinite(person.xy).all(axis=1)
        if not ok.any():
            return Fit(person.track_id, 0.0, None, "not the carrier", "no floor position")
        last = int(np.flatnonzero(ok)[-1])
        x, y = person.xy[last]
        when = "before" if person.t_ms[last] < carton.t_ms.min() else "after"
        move = heading(person)
        return Fit(person.track_id, 0.0, None, "not the carrier", f"out of view {when} the carton appeared; last seen at "
                   f"({x:.1f}, {y:.1f}) m, {move if move == 'standing still' else 'heading ' + move}")
    shared = (max(times) - min(times)) / 1000
    med = float(np.median(gaps))
    if med <= REACH_M and shared >= MIN_SHARED_S:
        return Fit(person.track_id, shared, med, "likely carrier",
                   f"within {med:.1f} m of the carton for {shared:.1f} s, at the same moments")
    where = f"{med:.0f} m from the carton" if med > REACH_M else f"with it for only {shared:.1f} s"
    move = heading(person)
    return Fit(person.track_id, shared, med, "not the carrier", f"{where}, {move if move == 'standing still' else 'heading ' + move}")
