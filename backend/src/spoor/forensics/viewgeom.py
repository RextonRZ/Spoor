"""Where a floor point lands in a camera image, from the camera MOUNTING PLAN pose (pinhole, no lens model).

Used only to place an "expected here" region (I3 / H10) and to centre crops; the region is approximate and is labelled
so. Same pose convention as the plan footprint: heading from +X towards +Y, tilt down from horizontal."""

import math

from spoor.contracts import PlanCamera

PARCEL_M = 0.45  # typical parcel edge used to size an expected-region box


def _basis(cam: PlanCamera):
    yaw, tilt = math.radians(cam.heading_deg), math.radians(cam.tilt_down_deg)
    fwd = (math.cos(yaw) * math.cos(tilt), math.sin(yaw) * math.cos(tilt), -math.sin(tilt))
    right = (math.sin(yaw), -math.cos(yaw), 0.0)
    up = (right[1] * fwd[2] - right[2] * fwd[1], right[2] * fwd[0] - right[0] * fwd[2],
          right[0] * fwd[1] - right[1] * fwd[0])  # fmt: skip
    return fwd, right, up


def project(cam: PlanCamera, xyz: tuple[float, float, float]) -> tuple[float, float, float] | None:
    """(u, v, range_m) in pixels, or None when the point is behind the camera or outside the frame."""
    fwd, right, up = _basis(cam)
    d = [xyz[k] - cam.position_m[k] for k in range(3)]
    z = sum(d[k] * fwd[k] for k in range(3))
    if z <= 0.1:
        return None
    w, h = cam.resolution_wh_px
    th, tv = math.tan(math.radians(cam.hfov_deg) / 2), math.tan(math.radians(cam.vfov_deg) / 2)
    u = w / 2 + (sum(d[k] * right[k] for k in range(3)) / z) / th * w / 2
    v = h / 2 - (sum(d[k] * up[k] for k in range(3)) / z) / tv * h / 2
    if not (0 <= u < w and 0 <= v < h):
        return None
    return u, v, math.sqrt(sum(c * c for c in d))


def expected_region(cam: PlanCamera, xyz: tuple[float, float, float]) -> list[float] | None:
    """[x1, y1, x2, y2] px box a parcel-sized object at xyz would occupy (padded for pose error), or None."""
    p = project(cam, xyz)
    if p is None:
        return None
    u, v, rng = p
    w, h = cam.resolution_wh_px
    f = (w / 2) / math.tan(math.radians(cam.hfov_deg) / 2)
    half = max(28.0, 1.8 * PARCEL_M * f / rng / 2)  # 1.8x: mounting-plan pose, no lens model
    return [round(max(0, u - half)), round(max(0, v - half)), round(min(w, u + half)), round(min(h, v + half))]
