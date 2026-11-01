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


def undistort_px(uv, k1: float, hfov_deg: float, wh_px: tuple[int, int]) -> np.ndarray:
    """Delivered (barrel) pixel -> undistorted pixel for a one-term radial lens normalised at the edge midpoints."""
    w, h = wh_px
    f = w / (2 * np.tan(np.radians(hfov_deg / 2)))
    uv = np.asarray(uv, np.float64).reshape(-1, 2)
    x, y = (uv[:, 0] - w / 2) / f, (uv[:, 1] - h / 2) / f
    s = (1 - k1 * (x * x + y * y)) / (1 - k1 * (w / 2 / f) ** 2)
    return np.c_[x * s * f + w / 2, y * s * f + h / 2]


def distort_px(uv, k1: float, hfov_deg: float, wh_px: tuple[int, int]) -> np.ndarray:
    """Inverse of undistort_px: an undistorted pixel -> where the lens puts it in the delivered frame."""
    w, h = wh_px
    f = w / (2 * np.tan(np.radians(hfov_deg / 2)))
    uv = np.asarray(uv, np.float64).reshape(-1, 2)
    xs, ys = (uv[:, 0] - w / 2) / f, (uv[:, 1] - h / 2) / f
    x, y = xs.copy(), ys.copy()
    for _ in range(30):  # fixed point: s(r_out) * out = undistorted (converges fast for |k1| < 0.5)
        s = (1 - k1 * (x * x + y * y)) / (1 - k1 * (w / 2 / f) ** 2)
        x, y = xs / s, ys / s
    return np.c_[x * f + w / 2, y * f + h / 2]


def lens_matrix(hfov_deg: float, wh_px: tuple[int, int]) -> np.ndarray:
    w, h = wh_px
    f = w / (2 * np.tan(np.radians(hfov_deg / 2)))
    return np.array([[f, 0, w / 2], [0, f, h / 2], [0, 0, 1.0]])


def site_to_image(cal: FloorCalibration, xyz) -> tuple[np.ndarray, np.ndarray]:
    """3D site points (m, Z up; a scanner at its height) -> pixels in the delivered frame, through the camera pose
    solved at calibration. Returns (uv, in_front). Needs a calibration with a lens and a pose."""
    if cal.pose_rvec is None or cal.radial_k1 is None:
        raise CalibrationError("this calibration has no camera pose; only floor points can be placed")
    xyz = np.asarray(xyz, np.float64).reshape(-1, 3)
    rot = cv2.Rodrigues(np.asarray(cal.pose_rvec))[0]
    cam = xyz @ rot.T + np.asarray(cal.pose_tvec)
    k = lens_matrix(cal.lens_hfov_deg, cal.image_wh_px)
    with np.errstate(divide="ignore", invalid="ignore"):
        uv = (cam @ k.T)[:, :2] / cam[:, 2:3]
    return distort_px(uv, cal.radial_k1, cal.lens_hfov_deg, cal.image_wh_px), cam[:, 2] > 0.05


def image_to_site(cal: FloorCalibration, uv, height_m: float = 0.0) -> np.ndarray:
    """Pixels in the delivered frame -> site points on the horizontal plane at height_m (0 = the floor: a person's
    feet; ~1 m: a carton carried in the hands). Needs the solved pose; NaN where the ray never meets that plane."""
    if cal.pose_rvec is None or cal.radial_k1 is None:
        raise CalibrationError("this calibration has no camera pose")
    uv = undistort_px(uv, cal.radial_k1, cal.lens_hfov_deg, cal.image_wh_px)
    k = lens_matrix(cal.lens_hfov_deg, cal.image_wh_px)
    rot = cv2.Rodrigues(np.asarray(cal.pose_rvec))[0]
    centre = -rot.T @ np.asarray(cal.pose_tvec)
    rays = (rot.T @ np.linalg.inv(k) @ np.c_[uv, np.ones(len(uv))].T).T
    with np.errstate(divide="ignore", invalid="ignore"):
        t = (height_m - centre[2]) / rays[:, 2]
    pts = centre + rays * t[:, None]
    pts[~(t > 0)] = np.nan
    return pts


def floor_to_image(cal: FloorCalibration, floor_xy) -> tuple[np.ndarray, np.ndarray]:
    """Floor points (m) -> pixels in the calibration's frame, lens included. Returns (uv, on_floor_side): a point
    behind the camera or beyond its horizon has on_floor_side False (it is not in this camera's picture)."""
    hinv = np.linalg.inv(np.asarray(cal.homography_image_to_floor))
    uv = apply_homography(hinv, np.asarray(floor_xy, np.float64).reshape(-1, 2))[0]
    # the forward map sends picture points to w > 0 (fit orients it so); the inverse keeps that sign on the floor side
    back_w = apply_homography(np.asarray(cal.homography_image_to_floor), uv)[1]
    ok = np.isfinite(uv).all(axis=1) & (back_w > 0)
    if cal.radial_k1 is not None:
        uv = distort_px(uv, cal.radial_k1, cal.lens_hfov_deg, cal.image_wh_px)
    return uv, ok


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
    radial_k1: float | None = None,
    lens_hfov_deg: float | None = None,
    now: datetime,
    notes: str = "",
) -> FloorCalibration:
    if (radial_k1 is None) != (lens_hfov_deg is None) or (radial_k1 is not None and image_wh_px is None):
        raise CalibrationError("a lens needs radial_k1, lens_hfov_deg and image_wh_px together")
    lens = (lambda p: undistort_px(p, radial_k1, lens_hfov_deg, image_wh_px)) if radial_k1 is not None else (lambda p: p)
    raw_img = _as_array(image_points_px, "image_points_px")
    img = lens(raw_img)
    flr = _as_array(floor_points_m, "floor_points_m")
    if len(img) != len(flr):
        raise CalibrationError("image and floor point counts differ")
    _check_spread(img, "image points")
    _check_spread(flr, "floor points")

    h, inliers = cv2.findHomography(img, flr, cv2.RANSAC, ransac_reproj_threshold_m)
    if h is None or not np.all(np.isfinite(h)) or abs(np.linalg.det(h)) < 1e-12:
        raise CalibrationError("homography estimation failed (degenerate configuration)")
    h = h / h[2, 2]
    # w > 0 must mean "on the floor side of the horizon". Scaling by h[2, 2] puts the picture's corner (0, 0) on that
    # side, which is wrong for a low camera whose top corner sees wall: orient by the floor points themselves.
    if np.median(apply_homography(h, img)[1]) < 0:
        h = -h
    n_inliers = int(inliers.sum()) if inliers is not None else len(img)
    if n_inliers < 4:
        raise CalibrationError("fewer than 4 RANSAC inliers; check the correspondences")

    raw_hold = _as_array(holdout_image_points_px, "holdout") if len(holdout_image_points_px) else np.empty((0, 2))
    hold_img = lens(raw_hold) if len(raw_hold) else raw_hold
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

    pose = {}
    if radial_k1 is not None:  # the lens is known, so the marks also fix the camera's pose (for raised points)
        k = lens_matrix(lens_hfov_deg, image_wh_px)
        ok, rvec, tvec = cv2.solvePnP(np.c_[flr, np.zeros(len(flr))], img, k, None, flags=cv2.SOLVEPNP_ITERATIVE)
        if ok:
            back = cv2.projectPoints(np.c_[flr, np.zeros(len(flr))], rvec, tvec, k, None)[0].reshape(-1, 2)
            pose = {"pose_rvec": tuple(float(v) for v in rvec.ravel()), "pose_tvec": tuple(float(v) for v in tvec.ravel()),
                    "pose_reprojection_px": float(np.sqrt(np.mean(np.sum((back - img) ** 2, axis=1))))}
    return FloorCalibration(
        **pose,
        calibration_id=calibration_id, camera_id=camera_id, floor_id=floor_id, version=version, rig_state=state,
        homography_image_to_floor=tuple(tuple(float(v) for v in row) for row in h), image_wh_px=image_wh_px,
        fit_image_points_px=[tuple(p) for p in raw_img.tolist()], fit_floor_points_m=[tuple(p) for p in flr.tolist()],
        holdout_image_points_px=[tuple(p) for p in raw_hold.tolist()],
        holdout_floor_points_m=[tuple(p) for p in hold_flr.tolist()],
        holdout_error_median_m=median, holdout_error_p95_m=p95, undistorted=undistorted, radial_k1=radial_k1,
        lens_hfov_deg=lens_hfov_deg,
        method=f"cv2.findHomography RANSAC (thr {ransac_reproj_threshold_m} m, {n_inliers}/{len(img)} inliers)",
        software_version=SOFTWARE, created_at=now, notes="; ".join(filter(None, [verdict, notes])),
    )  # fmt: skip


def invalidate(calibration: FloorCalibration, *, reason: str, by: str, now: datetime) -> CalibrationInvalidation:
    """Camera moved / zoomed / re-mounted: record invalidation. Dependent estimates are marked stale by the store."""
    return CalibrationInvalidation(
        calibration_id=calibration.calibration_id, reason=reason, invalidated_at=now, invalidated_by=by
    )
