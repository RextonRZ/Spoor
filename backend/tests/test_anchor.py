"""Anchored SAM prompts (perception/anchor.py): a scan point becomes pixels through the camera's calibrated pose, and a
handheld work area keeps only tracks that start inside it and leave it."""

from datetime import UTC, datetime

import numpy as np
import pytest
from test_spatial import FIT_FLOOR, HOLDOUT_FLOOR, IMG_H, IMG_W, THRESH, K, to_image

from spoor.contracts.plan import PlanReadPoint
from spoor.perception.anchor import AnchorError, anchor_for, leaves
from spoor.spatial import fit_floor_calibration

NOW = datetime(2026, 11, 1, tzinfo=UTC)
HFOV = float(np.degrees(2 * np.arctan(IMG_W / 2 / K[0, 0])))
CAL = fit_floor_calibration(calibration_id="calib_anchor", camera_id="cam_a", floor_id="floor_g", version=1,
                            image_points_px=to_image(FIT_FLOOR), floor_points_m=FIT_FLOOR,
                            holdout_image_points_px=to_image(HOLDOUT_FLOOR), holdout_floor_points_m=HOLDOUT_FLOOR,
                            thresholds=THRESH, image_wh_px=(IMG_W, IMG_H), radial_k1=0.0, lens_hfov_deg=HFOV,
                            now=NOW)  # fmt: skip


def point(**kw):
    return PlanReadPoint(**({"scan_point_id": "SP-X", "device_kind": "tunnel", "position_m": (3.0, 2.5, 0.0)} | kw))


def test_device_point_lands_on_its_pixel():
    a = anchor_for(point(device_parts_m=[(3.0, 2.5, 0.0)]), CAL)
    assert a.kind == "point" and np.allclose(a.point_px, to_image([(3.0, 2.5)])[0], atol=1)


def test_work_area_is_an_image_region_around_it():
    a = anchor_for(point(device_kind="handheld", work_area_m=[[(2.5, 2.0), (3.5, 2.0), (3.5, 3.0), (2.5, 3.0)]],
                         work_height_m=0.0), CAL)  # fmt: skip
    centre = to_image([(3.0, 2.5)])[0]
    assert a.kind == "area" and len(a.polygon_px) >= 4
    assert leaves(a.polygon_px, [(centre[0] - 2, centre[1] - 2, centre[0] + 2, centre[1] + 2), (0, 0, 4, 4)])
    assert not leaves(a.polygon_px, [(0, 0, 4, 4), (centre[0] - 2, centre[1] - 2, centre[0] + 2, centre[1] + 2)])
    assert not leaves(a.polygon_px, [(centre[0] - 2, centre[1] - 2, centre[0] + 2, centre[1] + 2)] * 3)


def test_point_out_of_view_is_refused():
    with pytest.raises(AnchorError):
        anchor_for(point(position_m=(3.0, -40.0, 0.0)), CAL)


def test_leaves_out_of_view_counts_only_when_asked():
    """A close-up whose view the work area fills: the carton is carried out of the picture, never out of the drawn
    area. That counts as leaving only when the caller asks (container watches), and only at the frame's edge."""
    area = [(0, 0), (100, 0), (100, 100), (0, 100)]
    out = [(40, 40, 60, 60), (0, 50, 20, 70)]  # last box at the left edge
    assert not leaves(area, out)
    assert leaves(area, out, out_of_view=(100, 100))
    assert not leaves(area, [(40, 40, 60, 60), (30, 50, 50, 70)], out_of_view=(100, 100))
