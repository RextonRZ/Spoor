"""Image -> floor homography calibration with held-out validation (PRD §13.2 steps 3-5).

A calibration is only `validated_floor_only` when held-out points (not used in the fit) meet thresholds the caller
chose from validation data. Thresholds are inputs, never tuned here to make a demo pass.
"""

from dataclasses import dataclass
from datetime import datetime

import cv2
import numpy as np

from spoor.contracts import CalibrationInvalidation, FloorCalibration, RigState

SOFTWARE = f"spoor.spatial.homography/opencv-{cv2.__version__}"


class CalibrationError(ValueError):
    pass


@dataclass(frozen=True)
class ValidationThresholds:
    max_median_m: float
    max_p95_m: float
    min_holdout_points: int = 3


def _as_array(points, name: str) -> np.ndarray:
    arr = np.asarray(points, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[1] != 2 or not np.all(np.isfinite(arr)):
        raise CalibrationError(f"{name} must be a list of finite (x, y) pairs")
    return arr


def _check_spread(points: np.ndarray, name: str, min_area_fraction: float = 0.02) -> None:
    """Reject collinear / clustered correspondences: their convex hull must cover a reasonable area."""
    if len(points) < 4:
        raise CalibrationError(f"{name}: at least 4 correspondences are required")
    hull = cv2.convexHull(points.astype(np.float32))
    area = cv2.contourArea(hull)
    span = np.ptp(points, axis=0)
    bbox_area = float(span[0] * span[1])
    if bbox_area <= 0 or area < min_area_fraction * bbox_area or area <= 1e-9:
        raise CalibrationError(f"{name}: points are collinear or too clustered for a stable homography")


def apply_homography(h: np.ndarray, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Map points through H. Returns (mapped xy, homogeneous w). w <= 0 means the ray never meets the floor."""
    homog = np.hstack([points, np.ones((len(points), 1))]) @ h.T
    w = homog[:, 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        xy = homog[:, :2] / w[:, None]
    return xy, w


def holdout_errors_m(h: np.ndarray, image_pts: np.ndarray, floor_pts: np.ndarray) -> np.ndarray:
    xy, w = apply_homography(h, image_pts)
    err = np.linalg.norm(xy - floor_pts, axis=1)
    err[w <= 0] = np.inf
    return err


def fit_floor_calibration(
    *,
    calibration_id: str,
    camera_id: str,
    floor_id: str,
    version: int,
    image_points_px,
    floor_points_m,
    holdout_image_points_px=(),
    holdout_floor_points_m=(),
    thresholds: ValidationThresholds | None = None,
    undistorted: bool = False,
    ransac_reproj_threshold_m: float = 0.05,
    image_wh_px: tuple[int, int] | None = None,
    now: datetime,
    notes: str = "",
) -> FloorCalibration:
    img = _as_array(image_points_px, "image_points_px")
    flr = _as_array(floor_points_m, "floor_points_m")
    if len(img) != len(flr):
        raise CalibrationError("image and floor point counts differ")
    _check_spread(img, "image points")
    _check_spread(flr, "floor points")

    h, inliers = cv2.findHomography(img, flr, cv2.RANSAC, ransac_reproj_threshold_m)
    if h is None or not np.all(np.isfinite(h)) or abs(np.linalg.det(h)) < 1e-12:
        raise CalibrationError("homography estimation failed (degenerate configuration)")
    h = h / h[2, 2]
    n_inliers = int(inliers.sum()) if inliers is not None else len(img)
    if n_inliers < 4:
        raise CalibrationError("fewer than 4 RANSAC inliers; check the correspondences")

    hold_img = _as_array(holdout_image_points_px, "holdout") if len(holdout_image_points_px) else np.empty((0, 2))
    hold_flr = _as_array(holdout_floor_points_m, "holdout") if len(holdout_floor_points_m) else np.empty((0, 2))
    if len(hold_img) != len(hold_flr):
        raise CalibrationError("holdout image and floor point counts differ")

    median = p95 = None
    state = RigState.CALIBRATING
    verdict = "no held-out points; calibration not validated"
    if len(hold_img):
        err = holdout_errors_m(h, hold_img, hold_flr)
        median, p95 = float(np.median(err)), float(np.percentile(err, 95))
        if not (np.isfinite(median) and np.isfinite(p95)):
            verdict = "a held-out point projects beyond the horizon; calibration not validated"
            median = p95 = None
        elif thresholds is None:
            verdict = "no validation thresholds supplied; calibration not validated"
        elif len(hold_img) < thresholds.min_holdout_points:
            verdict = f"only {len(hold_img)} held-out points (< {thresholds.min_holdout_points}); not validated"
        elif median <= thresholds.max_median_m and p95 <= thresholds.max_p95_m:
            state = RigState.VALIDATED_FLOOR_ONLY
            verdict = f"validated: holdout median {median:.3f} m, p95 {p95:.3f} m"
        else:
            verdict = (f"holdout median {median:.3f} m / p95 {p95:.3f} m exceeds thresholds "
                       f"{thresholds.max_median_m} / {thresholds.max_p95_m} m; not validated")  # fmt: skip

    return FloorCalibration(
        calibration_id=calibration_id, camera_id=camera_id, floor_id=floor_id, version=version, rig_state=state,
        homography_image_to_floor=tuple(tuple(float(v) for v in row) for row in h), image_wh_px=image_wh_px,
        fit_image_points_px=[tuple(p) for p in img.tolist()], fit_floor_points_m=[tuple(p) for p in flr.tolist()],
        holdout_image_points_px=[tuple(p) for p in hold_img.tolist()],
        holdout_floor_points_m=[tuple(p) for p in hold_flr.tolist()],
        holdout_error_median_m=median, holdout_error_p95_m=p95, undistorted=undistorted,
        method=f"cv2.findHomography RANSAC (thr {ransac_reproj_threshold_m} m, {n_inliers}/{len(img)} inliers)",
        software_version=SOFTWARE, created_at=now, notes="; ".join(filter(None, [verdict, notes])),
    )  # fmt: skip


def invalidate(calibration: FloorCalibration, *, reason: str, by: str, now: datetime) -> CalibrationInvalidation:
    """Camera moved / zoomed / re-mounted: record invalidation. Dependent estimates are marked stale by the store."""
    return CalibrationInvalidation(
        calibration_id=calibration.calibration_id, reason=reason, invalidated_at=now, invalidated_by=by
    )
