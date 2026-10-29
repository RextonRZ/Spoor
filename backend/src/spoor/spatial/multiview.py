"""Optional metric XYZ from synchronized, overlapping, fully calibrated views (PRD §13.4, step 11c).

Deterministic geometry with explicit quality gates. Disabled unless `ENABLE_MULTIVIEW_XYZ` and a rig in state
`validated_multiview_3d`; a failed gate returns a rejection with reasons, never a guessed point.
Convention (locked here): observations are distortion-corrected with cv2.undistortPoints into NORMALIZED coordinates
and triangulated with normalized projection matrices [R|t]; reprojection is checked in PIXELS via cv2.projectPoints.
"""

from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass(frozen=True)
class PinholeCamera:
    camera_id: str
    K: np.ndarray  # 3x3 intrinsics (pixels)
    dist: np.ndarray  # distortion coefficients (OpenCV order)
    R: np.ndarray  # 3x3 world->camera rotation (site frame, metres, Z up)
    t: np.ndarray  # 3-vector world->camera translation

    @property
    def center(self) -> np.ndarray:
        return -self.R.T @ self.t

    def project(self, xyz: np.ndarray) -> np.ndarray:
        rvec, _ = cv2.Rodrigues(self.R)
        uv, _ = cv2.projectPoints(xyz.reshape(1, 3), rvec, self.t, self.K, self.dist)
        return uv.reshape(2)

    def normalized(self, uv: np.ndarray) -> np.ndarray:
        return cv2.undistortPoints(np.asarray(uv, np.float64).reshape(1, 1, 2), self.K, self.dist).reshape(2)


@dataclass
class Gates:
    max_reprojection_px: float = 3.0
    min_ray_angle_deg: float = 5.0
    max_time_offset_motion_m: float = 0.05  # time misalignment x object speed must stay below this
    workspace_min: tuple[float, float, float] = (-1.0, -1.0, -0.2)
    workspace_max: tuple[float, float, float] = (50.0, 50.0, 4.0)


@dataclass
class TriangulationResult:
    accepted: bool
    xyz_m: tuple[float, float, float] | None
    reasons: list[str] = field(default_factory=list)
    reprojection_px: dict[str, float] = field(default_factory=dict)
    ray_angle_deg: float | None = None
    uncertainty_95_m: float | None = None


def _triangulate(a: PinholeCamera, b: PinholeCamera, uv_a, uv_b) -> np.ndarray | None:
    pa, pb = np.hstack([a.R, a.t.reshape(3, 1)]), np.hstack([b.R, b.t.reshape(3, 1)])
    na, nb = a.normalized(uv_a), b.normalized(uv_b)
    X = cv2.triangulatePoints(pa, pb, na.reshape(2, 1), nb.reshape(2, 1)).reshape(4)
    if not np.all(np.isfinite(X)) or abs(X[3]) < 1e-12:
        return None
    return X[:3] / X[3]


def triangulate_validated(a: PinholeCamera, b: PinholeCamera, uv_a, uv_b, *, time_offset_ms: float,
                          max_object_speed_mps: float, pixel_sigma: float = 1.0, gates: Gates | None = None,
                          samples: int = 200, seed: int = 0) -> TriangulationResult:  # fmt: skip
    g = gates or Gates()
    reasons: list[str] = []
    motion = abs(time_offset_ms) / 1000.0 * max_object_speed_mps
    if motion > g.max_time_offset_motion_m:
        reason = (f"time offset allows {motion:.3f} m of motion between views "
                  f"(> {g.max_time_offset_motion_m} m): not triangulatable")
        return TriangulationResult(False, None, [reason])
    X = _triangulate(a, b, uv_a, uv_b)
    if X is None:
        return TriangulationResult(False, None, ["degenerate homogeneous solution"])
    ra, rb = X - a.center, X - b.center
    angle = float(np.degrees(np.arccos(np.clip(ra @ rb / (np.linalg.norm(ra) * np.linalg.norm(rb)), -1, 1))))
    if angle < g.min_ray_angle_deg:
        reasons.append(f"near-parallel rays ({angle:.1f} deg < {g.min_ray_angle_deg})")
    for cam in (a, b):
        if (cam.R @ X + cam.t)[2] <= 0:
            reasons.append(f"point is behind camera {cam.camera_id} (cheirality)")
    reproj = {cam.camera_id: float(np.linalg.norm(cam.project(X) - np.asarray(uv, float)))
              for cam, uv in ((a, uv_a), (b, uv_b))}  # fmt: skip
    for cid, err in reproj.items():
        if err > g.max_reprojection_px:
            reasons.append(f"reprojection error {err:.1f}px in {cid} (> {g.max_reprojection_px}px): likely wrong "
                           "correspondence")  # fmt: skip
    if np.any(X < g.workspace_min) or np.any(X > g.workspace_max):
        reasons.append("point outside the measured workspace")
    if reasons:
        return TriangulationResult(False, None, reasons, reproj, angle)

    # Monte Carlo: perturb both image points by the observed pixel noise; report the 95th-percentile 3D deviation.
    rng = np.random.default_rng(seed)
    pts = []
    for _ in range(samples):
        Y = _triangulate(a, b, np.asarray(uv_a, float) + rng.normal(0, pixel_sigma, 2),
                         np.asarray(uv_b, float) + rng.normal(0, pixel_sigma, 2))  # fmt: skip
        if Y is not None:
            pts.append(Y)
    dev = np.linalg.norm(np.asarray(pts) - X, axis=1)
    return TriangulationResult(True, tuple(float(v) for v in X), [], reproj, angle,
                               float(np.percentile(dev, 95)) if len(dev) else None)  # fmt: skip
