"""Step 03 acceptance tests: floor calibration, projection fallback chain, frames and clock sync (PRD §13).

A synthetic pinhole camera with known pose generates exact image<->floor correspondences, so expected answers come
from geometry, not hand-picked numbers.
"""

from datetime import timedelta

import cv2
import numpy as np
import pytest

from spoor.contracts import Camera, FrameRef, RigState, SpatialMode
from spoor.spatial import (
    CalibrationError,
    ProjectionInput,
    ValidationThresholds,
    fit_floor_calibration,
    normalize,
    ordering_is_determined,
    project_observation,
    renderer_to_site,
    site_to_renderer,
    sync_from_shared_event,
)
from spoor.spatial.frames import SITE_TO_RENDERER
from spoor.spatial.homography import floor_to_image, site_to_image

IMG_W, IMG_H = 1280, 720
K = np.array([[900.0, 0, IMG_W / 2], [0, 900.0, IMG_H / 2], [0, 0, 1]])
CAM_POS = np.array([3.0, 0.1, 2.5])  # mounted high on the south wall
TARGET = np.array([3.0, 3.0, 0.0])
THRESH = ValidationThresholds(max_median_m=0.10, max_p95_m=0.20)


def _pose():
    f = (TARGET - CAM_POS) / np.linalg.norm(TARGET - CAM_POS)
    r = np.cross(f, [0, 0, 1.0])
    r /= np.linalg.norm(r)
    d = np.cross(f, r)
    rot = np.vstack([r, d, f])
    return cv2.Rodrigues(rot)[0], -rot @ CAM_POS


RVEC, TVEC = _pose()


def to_image(floor_xy) -> np.ndarray:
    pts = np.array([[x, y, 0.0] for x, y in floor_xy])
    uv, _ = cv2.projectPoints(pts, RVEC, TVEC, K, None)
    return uv.reshape(-1, 2)


FIT_FLOOR = [(1.5, 1.7), (4.5, 1.7), (5.5, 3.8), (0.5, 3.8), (3.0, 2.5), (2.0, 3.2)]
HOLDOUT_FLOOR = [(2.0, 2.0), (4.2, 2.2), (2.2, 3.3), (4.0, 3.0), (3.3, 1.8)]


def in_view(uv: np.ndarray) -> bool:
    return bool(np.all((uv >= 0) & (uv <= [IMG_W, IMG_H])))


def test_fixture_points_are_visible():
    """Real landmarks must be visible in the image; keep the synthetic setup honest."""
    assert in_view(to_image(FIT_FLOOR)) and in_view(to_image(HOLDOUT_FLOOR))


@pytest.fixture
def camera() -> Camera:
    return Camera(
        camera_id="cam_a", site_id="site_test", floor_id="floor_g", name="Cam A", resolution_wh_px=(IMG_W, IMG_H),
        zone_image_regions_px={
            "zone_shelf_a": [(0, 0), (300, 0), (300, 200), (0, 200)],
            "zone_desk": [(900, 400), (1100, 400), (1100, 500), (900, 500)],
        },
    )  # fmt: skip


def calibrate(now, noise_px=0.0, holdout=True, thresholds=THRESH, seed=0):
    rng = np.random.default_rng(seed)
    img = to_image(FIT_FLOOR) + rng.normal(0, noise_px, (len(FIT_FLOOR), 2))
    hold_img = to_image(HOLDOUT_FLOOR) + rng.normal(0, noise_px, (len(HOLDOUT_FLOOR), 2))
    return fit_floor_calibration(
        calibration_id="calib_a_v1", camera_id="cam_a", floor_id="floor_g", version=1,
        image_points_px=img, floor_points_m=FIT_FLOOR,
        holdout_image_points_px=hold_img if holdout else (), holdout_floor_points_m=HOLDOUT_FLOOR if holdout else (),
        thresholds=thresholds, now=now,
    )  # fmt: skip


# --- Calibration -------------------------------------------------------------


def test_exact_correspondences_recover_geometry(now):
    cal = calibrate(now)
    assert cal.rig_state == RigState.VALIDATED_FLOOR_ONLY
    assert cal.holdout_error_p95_m < 1e-6


def test_noisy_calibration_validated_with_measured_error(now):
    cal = calibrate(now, noise_px=1.0)
    assert cal.rig_state == RigState.VALIDATED_FLOOR_ONLY
    assert 0 < cal.holdout_error_median_m < THRESH.max_median_m
    assert "validated" in cal.notes


def test_no_holdout_means_not_validated(now):
    cal = calibrate(now, holdout=False)
    assert cal.rig_state == RigState.CALIBRATING and cal.holdout_error_median_m is None


def test_errors_above_threshold_not_validated(now):
    cal = calibrate(now, noise_px=1.0, thresholds=ValidationThresholds(max_median_m=1e-4, max_p95_m=1e-4))
    assert cal.rig_state == RigState.CALIBRATING and "exceeds thresholds" in cal.notes


def test_collinear_points_rejected(now):
    line = [(0.5, 1.0), (1.5, 1.5), (2.5, 2.0), (3.5, 2.5), (4.5, 3.0)]
    with pytest.raises(CalibrationError, match="collinear"):
        fit_floor_calibration(
            calibration_id="calib_x", camera_id="cam_a", floor_id="floor_g", version=1,
            image_points_px=to_image(line), floor_points_m=line, now=now,
        )  # fmt: skip


def test_too_few_points_rejected(now):
    with pytest.raises(CalibrationError, match="at least 4"):
        fit_floor_calibration(
            calibration_id="calib_x", camera_id="cam_a", floor_id="floor_g", version=1,
            image_points_px=to_image(FIT_FLOOR[:3]), floor_points_m=FIT_FLOOR[:3], now=now,
        )  # fmt: skip


# --- Projection fallback chain -----------------------------------------------


def project(now, camera, room, uv, on_floor=True, cal="default", **kw):
    cal = calibrate(now, noise_px=1.0) if cal == "default" else cal
    obs = ProjectionInput(observation_ids=["obs_1"], uv_px=tuple(uv), on_floor_plane=on_floor)
    return project_observation(obs, camera=camera, site=room, calibration=cal, now=now, **kw)


def test_floor_point_projects_within_uncertainty(now, camera, room):
    truth = (2.5, 2.2)
    est = project(now, camera, room, to_image([truth])[0])
    assert est.spatial_mode == SpatialMode.FLOOR_XY
    assert np.hypot(est.floor_xy_m[0] - truth[0], est.floor_xy_m[1] - truth[1]) <= est.uncertainty_radius_m
    assert est.calibration_id == "calib_a_v1"


def test_uncertainty_grows_with_distance(now, camera, room):
    near = project(now, camera, room, to_image([(3.0, 1.6)])[0])
    far = project(now, camera, room, to_image([(3.0, 3.8)])[0])
    assert far.uncertainty_radius_m > near.uncertainty_radius_m


def test_floor_point_inside_zone_gets_zone(now, camera, room):
    est = project(now, camera, room, to_image([(3.8, 1.7)])[0])  # inside the desk footprint
    assert est.spatial_mode == SpatialMode.FLOOR_XY and est.zone_id == "zone_desk"


def test_point_outside_room_is_image_only(now, camera, room):
    est = project(now, camera, room, to_image([(3.0, 6.0)])[0])  # floor beyond the north wall
    assert est.spatial_mode == SpatialMode.IMAGE_ONLY and est.floor_xy_m is None


def test_point_above_horizon_is_image_only(now, camera, room):
    est = project(now, camera, room, (640, 5))  # sky/wall region: ray never meets the floor in the room
    assert est.spatial_mode == SpatialMode.IMAGE_ONLY


def test_unvalidated_or_invalidated_calibration_not_used(now, camera, room):
    uv = to_image([(2.5, 2.2)])[0]
    assert project(now, camera, room, uv, cal=calibrate(now, holdout=False)).spatial_mode == SpatialMode.IMAGE_ONLY
    est = project(now, camera, room, uv, invalidated_calibration_ids=frozenset({"calib_a_v1"}))
    assert est.spatial_mode == SpatialMode.IMAGE_ONLY
    assert project(now, camera, room, uv, cal=None).spatial_mode == SpatialMode.IMAGE_ONLY


def test_item_on_shelf_is_anchored_not_floor_projected(now, camera, room):
    est = project(now, camera, room, (150, 100), on_floor=False)
    assert est.spatial_mode == SpatialMode.ANCHORED_HEIGHT
    assert est.zone_id == "zone_shelf_a" and est.height_m == 1.2


def test_off_floor_item_without_region_is_image_only(now, camera, room):
    est = project(now, camera, room, to_image([(2.5, 2.2)])[0], on_floor=False)
    assert est.spatial_mode == SpatialMode.IMAGE_ONLY


def test_overlapping_regions_do_not_guess(now, camera, room):
    camera.zone_image_regions_px["zone_door_b"] = [(0, 0), (300, 0), (300, 200), (0, 200)]
    est = project(now, camera, room, (150, 100), on_floor=False)
    assert est.spatial_mode == SpatialMode.IMAGE_ONLY


# --- Frames and clocks -------------------------------------------------------


def test_site_renderer_transform():
    assert np.linalg.det(SITE_TO_RENDERER) == pytest.approx(1.0)  # rotation, not a mirror
    assert site_to_renderer((0, 0, 1)) == pytest.approx((0, 1, 0))  # site up -> renderer up
    p = (2.14, 3.61, 1.06)
    assert renderer_to_site(site_to_renderer(p)) == pytest.approx(p)


def test_clock_sync_and_ordering(now):
    sync_b = sync_from_shared_event(
        camera_id="cam_b", camera_event_time=now, reference_event_time=now + timedelta(milliseconds=1500),
        camera_frame_interval_ms=100, reference_frame_interval_ms=100, anchor_description="hand clap", now=now,
    )  # fmt: skip
    assert sync_b.offset_ms == 1500 and sync_b.uncertainty_ms == 200
    a = normalize(FrameRef(media_id="media_a", pts_ms=0, frame_index=0), clip_start_camera_time=now, sync=sync_b)
    b_close = normalize(FrameRef(media_id="media_b", pts_ms=300, frame_index=3), clip_start_camera_time=now,
                        sync=sync_b)  # fmt: skip
    b_far = normalize(FrameRef(media_id="media_b", pts_ms=900, frame_index=9), clip_start_camera_time=now,
                      sync=sync_b)  # fmt: skip
    assert a.normalized_utc == now + timedelta(milliseconds=1500)
    assert ordering_is_determined(a, b_close) is None  # 300 ms apart < 400 ms combined uncertainty
    assert ordering_is_determined(a, b_far) is True


def test_barrel_lens_is_corrected_before_the_homography(now):
    # The delivered CCTV frame bends straight floor lines (one radial term); a plain homography cannot fit that.
    k1, hfov = -0.15, float(np.degrees(2 * np.arctan(IMG_W / 2 / K[0, 0])))
    edge = (IMG_W / 2 / K[0, 0]) ** 2

    def barrel(uv):
        xs, ys = (uv[:, 0] - IMG_W / 2) / K[0, 0], (uv[:, 1] - IMG_H / 2) / K[0, 0]
        x, y = xs, ys
        for _ in range(40):  # invert undistort_px: s(r_out) * out = undistorted
            s = (1 - k1 * (x * x + y * y)) / (1 - k1 * edge)
            x, y = xs / s, ys / s
        return np.c_[x * K[0, 0] + IMG_W / 2, y * K[0, 0] + IMG_H / 2]

    args = dict(calibration_id="calib_lens", camera_id="cam_a", floor_id="floor_g", version=1,
                image_points_px=barrel(to_image(FIT_FLOOR)), floor_points_m=FIT_FLOOR,
                holdout_image_points_px=barrel(to_image(HOLDOUT_FLOOR)), holdout_floor_points_m=HOLDOUT_FLOOR,
                thresholds=THRESH, image_wh_px=(IMG_W, IMG_H), now=now)  # fmt: skip
    plain = fit_floor_calibration(**args)
    lens = fit_floor_calibration(**args, radial_k1=k1, lens_hfov_deg=hfov)
    assert lens.rig_state == RigState.VALIDATED_FLOOR_ONLY and lens.holdout_error_p95_m < 1e-6
    assert plain.holdout_error_p95_m > 100 * lens.holdout_error_p95_m
    assert np.allclose(lens.fit_image_points_px, barrel(to_image(FIT_FLOOR)))  # stored as clicked
    with pytest.raises(CalibrationError):
        fit_floor_calibration(**args, radial_k1=k1)
    # and back: a floor point lands on the delivered (bent) pixel it was clicked at
    uv, ok = floor_to_image(lens, HOLDOUT_FLOOR)
    assert ok.all() and np.allclose(uv, barrel(to_image(HOLDOUT_FLOOR)), atol=1e-3)
    # a scanner 1.7 m up: the floor map cannot place it, the pose solved from the same marks can
    raised = np.array([[2.5, 2.6, 1.7], [4.0, 3.1, 1.1]])
    true = barrel(cv2.projectPoints(raised, RVEC, TVEC, K, None)[0].reshape(-1, 2))
    uv, front = site_to_image(lens, raised)
    assert front.all() and np.allclose(uv, true, atol=0.05) and lens.pose_reprojection_px < 1e-3
    assert np.linalg.norm(floor_to_image(lens, raised[:, :2])[0] - true, axis=1).min() > 20


def test_low_camera_whose_top_corner_sees_wall_still_validates(now):
    # A homography is defined up to sign; the floor side of the horizon is where the floor marks are, not wherever
    # pixel (0, 0) falls. Shift the picture so its top corner lies above the horizon (a low wall camera seeing wall).
    hm, _ = cv2.findHomography(to_image(FIT_FLOOR), np.array(FIT_FLOOR))
    hm = hm / hm[2, 2]
    drop = 1.5 * hm[2, 2] / hm[2, 1]  # rows from the corner down to past the horizon line (w = 0 at u = 0)
    shift = lambda uv: np.c_[uv[:, 0], uv[:, 1] + drop]
    assert drop > 0 and (hm[2] @ [0, -drop, 1]) < 0  # the shifted corner is beyond the horizon
    cal = fit_floor_calibration(calibration_id="calib_low", camera_id="cam_a", floor_id="floor_g", version=1,
                                image_points_px=shift(to_image(FIT_FLOOR)), floor_points_m=FIT_FLOOR,
                                holdout_image_points_px=shift(to_image(HOLDOUT_FLOOR)),
                                holdout_floor_points_m=HOLDOUT_FLOOR, thresholds=THRESH, now=now)  # fmt: skip
    assert cal.rig_state == RigState.VALIDATED_FLOOR_ONLY
