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


def event_xyz(rp: PlanReadPoint, event_kind: str | None, conveyors=()) -> list[float]:
    """Where this event physically happens, in 3-D: the read point's own spot, or (when the plan says the event happens
    elsewhere, e.g. a sorter PLC's induct reported where the parcel boards the loop) that spot at the deck height of
    the conveyor under it (the plan stores only x, y for it; the read point's own height there was 0.4 m off)."""
    if not event_kind or event_kind not in rp.event_positions:
        return list((rp.device_parts_m or [rp.position_m])[0] if rp.device_kind != "rfid_portal" else rp.position_m)
    x, y = rp.event_positions[event_kind]
    best = None
    for cv in conveyors:
        hs = cv.deck_heights_m if len(cv.deck_heights_m) == len(cv.path_m) else cv.deck_heights_m * len(cv.path_m)
        for (px, py), h in zip(cv.path_m, hs, strict=False):
            d = ((px - x) ** 2 + (py - y) ** 2) ** 0.5
            if d <= 0.6 and (best is None or d < best[0]):
                best = (d, h)
    return [x, y, best[1] if best else rp.position_m[2]]


def anchor_for(rp: PlanReadPoint, cal: FloorCalibration, event_kind: str | None = None, conveyors=()) -> Anchor:
    """The scan point as pixels in this camera's delivered frame (at the event's own spot when the plan has one)."""
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
    xyz = event_xyz(rp, event_kind, conveyors)
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


def leaves(poly: list[tuple[float, float]], boxes: list[tuple[float, float, float, float]],
           out_of_view: tuple[int, int] | None = None) -> bool:
    """A track (its boxes in frame order) that starts inside the area and is later wholly outside it. With
    out_of_view=(width, height): also one carried out of the picture, its last box at the frame's edge (a close-up
    whose view the area fills: the carton leaves the view, not the drawn area). The caller drops tracks that only ran
    out of footage."""
    if not boxes:
        return False
    centre = [((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for b in boxes]
    if not inside(poly, *centre[0]):
        return False
    if out_of_view and len(boxes) > 1:
        w, h = out_of_view
        x1, y1, x2, y2 = boxes[-1]
        if x1 <= EDGE_PX or y1 <= EDGE_PX or x2 >= w - 1 - EDGE_PX or y2 >= h - 1 - EDGE_PX:
            return True
    return any(not any(inside(poly, x, y) for x, y in ((b[0], b[1]), (b[2], b[1]), (b[0], b[3]), (b[2], b[3])))
               for b in boxes[1:])


EDGE_PX = 3  # a box this close to the frame's edge is at the edge


def handled(poly: list[tuple[float, float]], boxes: list[tuple[float, float, float, float]]) -> bool:
    """A track handled in the area: its centre is inside it at some frame and it travels more than twice its own size
    (a carton in someone's hands, put in or taken out, went 6-8x; stock standing in a trailer wall or on a shelf jitters
    under 1x as SAM re-fits it when an arm passes in front of it)."""
    if len(boxes) < 2:
        return False
    centre = [((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for b in boxes]
    if not any(inside(poly, x, y) for x, y in centre):
        return False
    size = max(max(b[2] - b[0], b[3] - b[1]) for b in boxes)
    return max(abs(x - centre[0][0]) + abs(y - centre[0][1]) for x, y in centre) > 2 * size


def expected_carton_px(rp: PlanReadPoint, cal: FloorCalibration, dims_m: tuple[float, float, float],
                       ) -> tuple[float, float, float, float] | None:  # fmt: skip
    """Where THIS parcel (its own measured size, from the tunnel's dimensioner) would sit in the picture at the scan
    point: the projected box of that cuboid (both orientations, since its yaw is unknown), in frame pixels. Used to
    prompt SAM with a box of the parcel's size when a point alone outlined something bigger (the sorter's tray)."""
    x, y, z = (rp.device_parts_m or [rp.position_m])[0]
    L, W, H = sorted(dims_m, reverse=True)
    pts = [(x + dx, y + dy, max(0.0, z - H / 2) + dz) for lx, wy in ((L, W), (W, L))
           for dx in (-lx / 2, lx / 2) for dy in (-wy / 2, wy / 2) for dz in (0.0, H)]  # fmt: skip
    uv, front = site_to_image(cal, pts)
    if not front.all():
        return None
    return float(uv[:, 0].min()), float(uv[:, 1].min()), float(uv[:, 0].max()), float(uv[:, 1].max())


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
