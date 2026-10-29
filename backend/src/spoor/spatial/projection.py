"""Turn an image observation into the best honest SpatialEstimate (PRD §13.2, §13.4.4 fallback chain).

    floor_xy (validated homography, floor-contact point inside the site)
      -> anchored_height (item on a measured surface zone, via operator-drawn image region)
      -> zone_only (image point inside an operator-drawn zone region)
      -> image_only (visible in the image, no trustworthy position)

`unknown` is reserved for intervals with no observation at all; it is never produced from an observation.
"""

from dataclasses import dataclass
from datetime import datetime

import numpy as np

from spoor.contracts import (
    Camera,
    FloorCalibration,
    RigState,
    Site,
    SpatialEstimate,
    SpatialMode,
    Zone,
    new_id,
    point_in_polygon,
)

from .homography import apply_homography


@dataclass(frozen=True)
class ProjectionInput:
    observation_ids: list[str]
    uv_px: tuple[float, float]
    # Is uv the object's contact point with the FLOOR (e.g. a case standing on the floor, a person's feet)?
    # False for items on shelves/desks or carried — homography is invalid for them (PRD §13.2 step 6).
    on_floor_plane: bool
    # Pixel uncertainty of the contact point (detector box jitter, occlusion of the base).
    sigma_px: float = 3.0
    # Size of the frame uv refers to. If it differs from the calibration's, uv is rescaled (same aspect) or refused.
    frame_wh_px: tuple[int, int] | None = None


def _jacobian_px_to_m(h: np.ndarray, uv: np.ndarray, eps: float = 0.5) -> np.ndarray:
    pts = np.array([uv + [eps, 0], uv - [eps, 0], uv + [0, eps], uv - [0, eps]])
    xy, _ = apply_homography(h, pts)
    return np.column_stack([(xy[0] - xy[1]) / (2 * eps), (xy[2] - xy[3]) / (2 * eps)])


def _zone_by_image_region(camera: Camera, site: Site, uv: tuple[float, float]) -> Zone | None:
    zones = {z.zone_id: z for z in site.zones}
    hits = [zones[zid] for zid, poly in camera.zone_image_regions_px.items()
            if zid in zones and point_in_polygon(uv, poly)]  # fmt: skip
    # Ambiguous (overlapping regions) -> no zone rather than a guess.
    return hits[0] if len(hits) == 1 else None


def _zone_radius(zone: Zone) -> tuple[tuple[float, float], float]:
    pts = np.asarray(zone.polygon_m)
    centre = pts.mean(axis=0)
    return (float(centre[0]), float(centre[1])), float(np.max(np.linalg.norm(pts - centre, axis=1)))


def project_observation(
    obs: ProjectionInput,
    *,
    camera: Camera,
    site: Site,
    calibration: FloorCalibration | None,
    invalidated_calibration_ids: frozenset[str] = frozenset(),
    now: datetime,
) -> SpatialEstimate:
    base = {"estimate_id": new_id("spatial_estimate"), "observation_ids": obs.observation_ids, "created_at": now}
    w, h = obs.frame_wh_px or camera.resolution_wh_px
    u, v = obs.uv_px
    scale_ok = True
    if calibration is not None and calibration.image_wh_px and obs.frame_wh_px \
            and tuple(calibration.image_wh_px) != tuple(obs.frame_wh_px):  # fmt: skip
        cw, ch = calibration.image_wh_px
        sx, sy = cw / obs.frame_wh_px[0], ch / obs.frame_wh_px[1]
        scale_ok = abs(sx - sy) <= 0.01 * max(sx, sy)  # same aspect ratio: a pure rescale is valid
        u, v, w, h = u * sx, v * sy, cw, ch
    in_frame = 0 <= u <= w and 0 <= v <= h

    usable_calibration = (
        calibration is not None
        and calibration.camera_id == camera.camera_id
        and calibration.rig_state in (RigState.VALIDATED_FLOOR_ONLY, RigState.VALIDATED_MULTIVIEW_3D)
        and calibration.calibration_id not in invalidated_calibration_ids
        and calibration.holdout_error_p95_m is not None
        and scale_ok
    )

    if obs.on_floor_plane and usable_calibration and in_frame:
        hm = np.asarray(calibration.homography_image_to_floor)
        uv = np.array([u, v], dtype=np.float64)
        xy, wh = apply_homography(hm, uv[None, :])
        x, y = (float(c) for c in xy[0])
        if wh[0] > 0 and np.isfinite([x, y]).all() and site.contains(calibration.floor_id, (x, y)):
            # Calibration error (held-out p95) combined with the local pixel->metre stretch of this image point.
            stretch = float(np.linalg.svd(_jacobian_px_to_m(hm, uv), compute_uv=False)[0])
            radius = float(np.hypot(calibration.holdout_error_p95_m, stretch * obs.sigma_px))
            zones = site.zones_at(calibration.floor_id, (x, y))
            return SpatialEstimate(
                **base, spatial_mode=SpatialMode.FLOOR_XY, floor_id=calibration.floor_id, floor_xy_m=(x, y),
                zone_id=zones[0].zone_id if len(zones) == 1 else None, uncertainty_radius_m=max(radius, 1e-3),
                method="homography_floor_contact", calibration_id=calibration.calibration_id,
            )  # fmt: skip

    zone = _zone_by_image_region(camera, site, obs.uv_px) if in_frame else None
    if zone is not None:
        centre, radius = _zone_radius(zone)
        if not obs.on_floor_plane and zone.surface_height_m is not None and zone.measured:
            return SpatialEstimate(
                **base, spatial_mode=SpatialMode.ANCHORED_HEIGHT, floor_id=zone.floor_id, floor_xy_m=centre,
                height_m=zone.surface_height_m, zone_id=zone.zone_id, uncertainty_radius_m=max(radius, 1e-3),
                method="operator_image_region_on_measured_surface",
            )  # fmt: skip
        return SpatialEstimate(**base, spatial_mode=SpatialMode.ZONE_ONLY, zone_id=zone.zone_id,
                               method="operator_image_region")  # fmt: skip

    return SpatialEstimate(**base, spatial_mode=SpatialMode.IMAGE_ONLY, method="no_valid_spatial_mapping")
