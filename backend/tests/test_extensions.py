"""Step 11 acceptance tests: sensor CSV import, cross-camera association gates, gated multi-view triangulation.
All geometry here is synthetic with known answers (PRD scenarios C03, C07, C11-C14)."""

import cv2
import numpy as np
import pytest
from builders import World

from spoor.association import AssociationConfig, Topology, Tracklet, propose_links, to_association, tracklet
from spoor.contracts import AssociationStatus, SourceType
from spoor.sensors import SensorImportError, parse_sensor_csv
from spoor.spatial.multiview import Gates, PinholeCamera, triangulate_validated
from spoor.store import EvidenceStore

# --- 11a sensors ---------------------------------------------------------------------------------------

HEADER = "device_id,kind,value,zone_id,device_time_utc,clock_quality,source\n"


def test_sensor_csv_labels_real_and_simulated():
    events = parse_sensor_csv(HEADER + "door_b,door_contact,OPEN,zone_door_b,2026-10-27T14:00:10+00:00,ntp,real\n"
                              "shelf,weight_delta_kg,-2.4,zone_shelf_a,2026-10-27T14:00:11+00:00,unsynced,simulated\n",
                              import_batch="b1", site_id="site_test")  # fmt: skip
    assert [e.source_type for e in events] == [SourceType.SENSOR_REAL, SourceType.SENSOR_SIMULATED]
    assert events[0].value == "open" and events[1].value == -2.4


@pytest.mark.parametrize("row", [
    "door_b,door_contact,open,,2026-10-27T14:00:10+00:00,ntp,\n",          # unlabelled real/simulated
    "door_b,door_contact,ajar,,2026-10-27T14:00:10+00:00,ntp,real\n",      # invalid value
    "door_b,door_contact,open,,2026-10-27T14:00:10,ntp,real\n",            # naive timestamp
    "door_b,face_match,yes,,2026-10-27T14:00:10+00:00,ntp,real\n",         # unsupported (and forbidden) kind
])  # fmt: skip
def test_sensor_csv_rejects_bad_rows(row):
    with pytest.raises(SensorImportError):
        parse_sensor_csv(HEADER + row, import_batch="b", site_id="site_test")


# --- 11b association ------------------------------------------------------------------------------------

TOPO = Topology(min_travel_s={("cam_a", "cam_b"): 3.0})


def tl(tid, cam, start, end, s_xy=None, e_xy=None, app=None):
    return Tracklet(tid, cam, start * 1000, end * 1000, 50, s_xy, e_xy, None if app is None else np.asarray(app))


def test_feasible_unique_match_is_only_a_candidate():
    a = tl("trk_a", "cam_a", 0, 10, e_xy=(5.5, 0.2))
    b = tl("trk_b", "cam_b", 15, 20, s_xy=(5.5, -1.0))
    (p,) = propose_links([a], [b], TOPO)
    assert p.status == AssociationStatus.CANDIDATE_CROSS_CAMERA and "human confirmation" in p.reason


@pytest.mark.parametrize("b, why", [
    (tl("trk_b", "cam_b", 5, 9), "simultaneous"),                         # overlaps in time, views don't overlap
    (tl("trk_b", "cam_b", 11, 20), "needs >= 3.0s"),                       # faster than the topology allows
    (tl("trk_b", "cam_b", 15, 20, s_xy=(0.0, 30.0)), "exceeds"),           # 30 m in 5 s
    (tl("trk_b", "cam_c", 15, 20), "not connected"),
])  # fmt: skip
def test_hard_gates_reject(b, why):
    a = tl("trk_a", "cam_a", 0, 10, e_xy=(5.5, 0.2))
    (p,) = propose_links([a], [b], TOPO)
    assert p.status == AssociationStatus.REJECTED and why in p.reason


def test_lookalikes_make_the_matcher_abstain():
    """C03/C07: two equally plausible continuations -> unresolved, never a confident pick."""
    a = tl("trk_a", "cam_a", 0, 10, e_xy=(5.5, 0.2), app=[1, 0, 0])
    b1 = tl("trk_b1", "cam_b", 15, 20, s_xy=(5.5, -1.0), app=[0.99, 0.05, 0])
    b2 = tl("trk_b2", "cam_b", 15.2, 20, s_xy=(5.4, -1.0), app=[0.98, 0.06, 0])
    (p,) = propose_links([a], [b1, b2], TOPO)
    assert p.status == AssociationStatus.UNRESOLVED and "ambiguous" in p.reason


def test_appearance_mismatch_gates():
    a = tl("trk_a", "cam_a", 0, 10, app=[1, 0, 0])
    b = tl("trk_b", "cam_b", 15, 20, app=[0, 1, 0])
    assert propose_links([a], [b], TOPO)[0].status == AssociationStatus.REJECTED


def test_tracklets_from_store_and_association_record(room, now):
    w = World(EvidenceStore(), room, now)
    w.camera("cam_a")
    t = w.track("cam_a", w.clip("cam_a", 0, 20))
    for s in (1.0, 2.0, 3.0):
        w.obs(t, s, xy=(1.0 + s, 1.0))
    tr = tracklet(w.store, t)
    assert tr.start_xy == (2.0, 1.0) and tr.end_xy == (4.0, 1.0) and tr.end_ms - tr.start_ms == 2000
    earlier = Tracklet("trk_0", "cam_a", tr.start_ms - 6000, tr.start_ms - 3000, 20, None, (1.5, 1.0), None)
    rec = to_association("objinst_x", propose_links([earlier], [tr], TOPO)[0], version=1,
                         created_by="association", now=now)  # fmt: skip
    assert rec.status == AssociationStatus.CANDIDATE_CROSS_CAMERA and rec.track_id == t


# --- 11c multi-view --------------------------------------------------------------------------------------

K = np.array([[900.0, 0, 640], [0, 900.0, 360], [0, 0, 1]])
DIST = np.array([-0.05, 0.01, 0, 0, 0])


def look_at(cid, pos, target=(3.0, 2.0, 0.8)):
    pos, target = np.asarray(pos, float), np.asarray(target, float)
    f = (target - pos) / np.linalg.norm(target - pos)
    r = np.cross(f, [0, 0, 1.0])
    r /= np.linalg.norm(r)
    R = np.vstack([r, np.cross(f, r), f])
    return PinholeCamera(cid, K, DIST, R, -R @ pos)


CAM_A = look_at("cam_a", (0.2, 0.2, 2.5))
CAM_B = look_at("cam_b", (5.8, 0.3, 2.5))
POINT = np.array([3.1, 2.4, 1.06])  # e.g. a corner of the case on the shelf


def test_accurate_triangulation_with_uncertainty():
    r = triangulate_validated(CAM_A, CAM_B, CAM_A.project(POINT), CAM_B.project(POINT), time_offset_ms=10,
                              max_object_speed_mps=0.5)  # fmt: skip
    assert r.accepted and np.linalg.norm(np.array(r.xyz_m) - POINT) < 1e-3
    assert 0 < r.uncertainty_95_m < 0.1 and r.ray_angle_deg > 30


def test_wrong_correspondence_rejected_by_reprojection():
    """C12: a lookalike landmark in view B does not satisfy both projections."""
    other = POINT + np.array([0.4, -0.3, 0.0])
    r = triangulate_validated(CAM_A, CAM_B, CAM_A.project(POINT), CAM_B.project(other), time_offset_ms=0,
                              max_object_speed_mps=0.5)  # fmt: skip
    assert not r.accepted and r.xyz_m is None and any("reprojection" in x for x in r.reasons)


def test_near_parallel_rays_rejected():
    """C13: two cameras almost on the same line of sight."""
    b_close = look_at("cam_b", (0.35, 0.25, 2.5))
    r = triangulate_validated(CAM_A, b_close, CAM_A.project(POINT), b_close.project(POINT), time_offset_ms=0,
                              max_object_speed_mps=0.5)  # fmt: skip
    assert not r.accepted and any("near-parallel" in x for x in r.reasons)


def test_time_offset_with_moving_object_rejected():
    """C13: clocks too far apart for a moving object."""
    r = triangulate_validated(CAM_A, CAM_B, CAM_A.project(POINT), CAM_B.project(POINT), time_offset_ms=200,
                              max_object_speed_mps=1.0)  # fmt: skip
    assert not r.accepted and "not triangulatable" in r.reasons[0]


def test_point_outside_workspace_rejected():
    r = triangulate_validated(CAM_A, CAM_B, CAM_A.project(POINT), CAM_B.project(POINT), time_offset_ms=0,
                              max_object_speed_mps=0.5, gates=Gates(workspace_max=(10, 2.0, 3)))  # fmt: skip
    assert not r.accepted and any("workspace" in x for x in r.reasons)


def test_undistortion_convention_matters():
    """Feeding pixels as if undistorted would bias the point; the locked convention recovers it."""
    uv_a, uv_b = CAM_A.project(POINT), CAM_B.project(POINT)
    pa = K @ np.hstack([CAM_A.R, CAM_A.t.reshape(3, 1)])
    pb = K @ np.hstack([CAM_B.R, CAM_B.t.reshape(3, 1)])
    naive = cv2.triangulatePoints(pa, pb, uv_a.reshape(2, 1), uv_b.reshape(2, 1)).reshape(4)
    naive = naive[:3] / naive[3]
    good = triangulate_validated(CAM_A, CAM_B, uv_a, uv_b, time_offset_ms=0, max_object_speed_mps=0.5)
    assert np.linalg.norm(naive - POINT) > 10 * np.linalg.norm(np.array(good.xyz_m) - POINT)


def test_config_defaults_keep_extensions_off():
    from spoor.config import Settings

    s = Settings(_env_file=None)
    assert s.enable_multiview_xyz is False and s.enable_cross_camera_association is False
    assert AssociationConfig().accept_cost > 0
