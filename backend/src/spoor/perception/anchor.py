"""Anchored SAM prompts: WHERE to look comes from the site plan and the camera's calibration, never from a guess.

A scan point says where a parcel was at the scan's second. Through the camera's calibrated pose (pose + lens, scored
against the scene at under 5 px) that place becomes pixels in that camera's frame:

- a scan device or a sorter event (tunnel exit, chute mouth, store scan-in): ONE point. SAM is prompted with it on the
  frame of the scan, so it follows the object that is there at that second, both ways in the window.
- a handheld scan (bag, cage, dock): its measured WORK AREA, as the image region it covers from the floor up to above
  the scan height. SAM looks for the concept in the window, and only tracks that START inside the area and then LEAVE
  it are kept (e.g. "the carton taken out of the west cage bays"), never every box on the camera.
"""

from dataclasses import dataclass

import numpy as np

from spoor.contracts import FloorCalibration
from spoor.contracts.plan import PlanReadPoint

from ..spatial.homography import site_to_image

AREA_TOP_ABOVE_SCAN_M = 0.9  # a parcel handled at the scan height can sit up to ~0.9 m above it (a cage shelf)


@dataclass(frozen=True)
class Anchor:
    scan_point_id: str
    kind: str  # "point" | "area"
    point_px: tuple[int, int] | None = None
    polygon_px: list[tuple[float, float]] | None = None  # convex image region (area anchors)


class AnchorError(ValueError):
    pass


def _hull(pts: np.ndarray) -> np.ndarray:
    """Convex hull (monotone chain) of image points."""
    p = sorted(map(tuple, pts))
    if len(p) < 3:
        return np.asarray(p)

    def half(seq):
        out = []
        for q in seq:
            while len(out) >= 2 and ((out[-1][0] - out[-2][0]) * (q[1] - out[-2][1])
                                     - (out[-1][1] - out[-2][1]) * (q[0] - out[-2][0])) <= 0:
                out.pop()
            out.append(q)
        return out[:-1]

    return np.asarray(half(p) + half(reversed(p)))


def anchor_for(rp: PlanReadPoint, cal: FloorCalibration) -> Anchor:
    """The scan point as pixels in this camera's delivered frame."""
    if cal.pose_rvec is None:
        raise AnchorError(f"{cal.camera_id} has no camera pose; it cannot place {rp.scan_point_id}")
    w, h = cal.image_wh_px
    if rp.work_area_m:
        z0, z1 = 0.0, (rp.work_height_m or 1.0) + AREA_TOP_ABOVE_SCAN_M
        corners = np.array([[x, y, z] for poly in rp.work_area_m for x, y in poly for z in (z0, z1)], float)
        uv, front = site_to_image(cal, corners)
        if not front.any():
            raise AnchorError(f"{rp.scan_point_id}'s work area is behind {cal.camera_id}")
        hull = _hull(np.clip(uv[front], [0, 0], [w - 1, h - 1]))
        return Anchor(rp.scan_point_id, "area", polygon_px=[(float(u), float(v)) for u, v in hull])
    xyz = (rp.device_parts_m or [rp.position_m])[0] if rp.device_kind != "rfid_portal" else rp.position_m
    uv, front = site_to_image(cal, [xyz])
    u, v = uv[0]
    if not front[0] or not (0 <= u < w and 0 <= v < h):
        raise AnchorError(f"{rp.scan_point_id} is not in {cal.camera_id}'s picture")
    return Anchor(rp.scan_point_id, "point", point_px=(int(u + 0.5), int(v + 0.5)))


def inside(poly: list[tuple[float, float]], x: float, y: float) -> bool:
    ok, n = False, len(poly)
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            ok = not ok
    return ok


def leaves(poly: list[tuple[float, float]], boxes: list[tuple[float, float, float, float]]) -> bool:
    """A track (its boxes in frame order) that starts inside the area and is later wholly outside it."""
    if not boxes:
        return False
    centre = [((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for b in boxes]
    if not inside(poly, *centre[0]):
        return False
    return any(not any(inside(poly, x, y) for x, y in ((b[0], b[1]), (b[2], b[1]), (b[0], b[3]), (b[2], b[3])))
               for b in boxes[1:])


PARCEL_MAX_M = 0.9  # the largest parcel a hub conveys or a person carries, edge length


def parcel_extent_px(rp: PlanReadPoint, cal: FloorCalibration) -> tuple[float, float]:
    """Width and height in pixels of the largest parcel (a PARCEL_MAX_M cube) standing at the scan point, through the
    camera's pose and lens. A SAM outline much bigger than this at that point is a belt, a cage or the frame, not a
    parcel."""
    x, y, z = (rp.device_parts_m or [rp.position_m])[0]
    h = PARCEL_MAX_M / 2
    corners = [(x + dx, y + dy, max(0.0, z - h) + dz) for dx in (-h, h) for dy in (-h, h) for dz in (0.0, PARCEL_MAX_M)]
    uv, front = site_to_image(cal, corners)
    uv = uv[front]
    if not len(uv):
        return float(cal.image_wh_px[0]), float(cal.image_wh_px[1])
    return float(np.ptp(uv[:, 0])), float(np.ptp(uv[:, 1]))
