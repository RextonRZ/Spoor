"""Regression tests for issues found in the 2026-10-28 logic review."""

import json
import time

import pytest
from builders import World
from test_agents import ScriptedBackend, claim, final

from spoor.agents import ToolContext, investigate
from spoor.contracts import (
    AssociationStatus,
    Camera,
    EvidenceLabel,
    EvidenceScope,
    Floor,
    ObjectVisibility,
    RawObservation,
    Site,
)
from spoor.contracts import (
    VerificationVerdict as V,
)
from spoor.store import (
    EvidenceStore,
    transitions,
    unobserved_intervals,
    visibility_timeline,
)
from spoor.verification import TransitionClaim, Verifier


@pytest.fixture
def two_cams(site, now):
    w = World(EvidenceStore(), site, now)
    w.camera("cam_a")
    w.camera("cam_b")
    ta = w.track("cam_a", w.clip("cam_a", 0, 20))
    tb = w.track("cam_b", w.clip("cam_b", 0, 20))
    a = {t: w.obs(ta, t, xy=(3.5, 1.4), zone="zone_desk") for t in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)}
    b = {t: w.obs(tb, t, xy=(3.6, 1.5), zone="zone_desk") for t in (0.1, 0.3, 0.5, 0.7, 0.9)}
    b[2.0] = w.obs(tb, 1.4, xy=(4.6, 0.6))
    b[3.0] = w.obs(tb, 1.8, xy=(5.5, 0.2), zone="zone_door_b")
    obj = w.obj("blue equipment case", ta, tb, status=AssociationStatus.HUMAN_CONFIRMED)
    return w, obj, a, b


def test_simultaneous_views_are_one_visible_span(two_cams):
    """Two cameras seeing the object at once must not fragment visibility or claim it 'reappeared'."""
    w, obj, a, b = two_cams
    spans = visibility_timeline(w.store, obj)
    assert [s.state for s in spans] == [ObjectVisibility.VISIBLE]
    assert set(spans[0].camera_ids) == {"cam_a", "cam_b"}


def test_cross_camera_handoff_is_hypothesized_not_observed(site, now):
    w = World(EvidenceStore(), site, now)
    w.camera("cam_a")
    w.camera("cam_b")
    ta = w.track("cam_a", w.clip("cam_a", 0, 20))
    tb = w.track("cam_b", w.clip("cam_b", 0, 20))
    for t in (0.0, 0.2, 0.4):
        w.obs(ta, t, xy=(3.5, 1.4), zone="zone_desk")
    for t in (0.6, 0.8):  # B picks it up with no gap, in another zone
        w.obs(tb, t, xy=(4.0, 0.3))
    last = w.obs(tb, 1.0, xy=(5.5, 0.2), zone="zone_door_b")
    obj = w.obj("blue equipment case", ta, tb, status=AssociationStatus.HUMAN_CONFIRMED)
    tr = transitions(w.store, obj)
    assert [(t.from_zone, t.to_zone, t.label) for t in tr] == [
        ("zone_desk", "zone_door_b", EvidenceLabel.HYPOTHESIZED)]
    first = w.store.find(RawObservation, track_id=ta)[0]
    r = Verifier(w.store, site).verify(TransitionClaim(
        statement="Case moved desk to door", object_instance_id=obj, from_observation_id=first.observation_id,
        to_observation_id=last, asserted_label="observed"))  # fmt: skip
    assert r.verdict == V.UNSUPPORTED and "hand-off" in r.reasons[0]


def test_within_camera_move_stays_observed(two_cams):
    w, obj, a, b = two_cams
    tr = transitions(w.store, obj)
    assert ("zone_desk", "zone_door_b", EvidenceLabel.OBSERVED) in [(t.from_zone, t.to_zone, t.label) for t in tr]


def test_coverage_from_another_site_never_leaks(two_cams, now):
    w, obj, a, b = two_cams
    other = w.store.put(Site(site_id="site_other", name="Other", measurement_method="x",
                             floors=[Floor(floor_id="floor_x", name="X", outline_m=[(0, 0), (9, 0), (9, 9)])]))
    w.store.put(Camera(camera_id="cam_other", site_id=other.site_id, floor_id="floor_x", name="o",
                       resolution_wh_px=(640, 480)))  # fmt: skip
    w.syncs["cam_other"] = w.syncs["cam_a"].model_copy(update={"sync_id": "sync_cam_a"})
    w.clip("cam_other", 0, 100)
    gaps = unobserved_intervals(w.store, obj, w.ms(0), w.ms(50))
    assert all("cam_other" not in g.covering_camera_ids for g in gaps)
    assert gaps[-1].reason == "no_camera_coverage"  # this site's cameras stop at 20 s


def test_claims_about_foreign_objects_are_rejected(two_cams, now):
    w, obj, a, b = two_cams
    ctx = ToolContext(store=w.store, site=w.site, case=w.case, verifier=Verifier(w.store, w.site),
                      scope=EvidenceScope(), now=lambda: now)  # fmt: skip
    hyp = {"hypotheses": [{"claim": "Case is at the door", "missing_evidence": [], "distinguishing_request": None,
                           "claims": [claim("last_seen", "Case last seen at door", "objinst_from_other_case",
                                            observation_ids=[b[3.0]])]}]}  # fmt: skip
    res = investigate(ctx, hypothesis_backend=ScriptedBackend([final(hyp)]))
    assert any("outside this case" in r for r in res.rejected)
    assert res.hypotheses[0].status.value == "insufficient_evidence"  # no checkable claims left


def test_queries_scale_to_real_footage(site, now):
    """~5 minutes at 10 fps: timeline + transitions must stay interactive (was O(n^2) queries per observation)."""
    w = World(EvidenceStore(), site, now)
    w.camera("cam_a")
    t = w.track("cam_a", w.clip("cam_a", 0, 400))
    for i in range(3000):
        w.obs(t, i * 0.1, xy=(1.0 + (i % 40) * 0.1, 1.2), zone="zone_desk" if i % 400 < 200 else None)
    obj = w.obj("blue equipment case", t)
    start = time.perf_counter()
    visibility_timeline(w.store, obj)
    transitions(w.store, obj)
    unobserved_intervals(w.store, obj, w.ms(0), w.ms(400))
    assert time.perf_counter() - start < 5.0
    json.dumps([s.__dict__ for s in visibility_timeline(w.store, obj)])


# --- independent review, 2026-10-28 ------------------------------------------------------------------------------


@pytest.fixture
def door_scene(site, now):
    w = World(EvidenceStore(), site, now)
    w.camera("cam_a")
    w.camera("cam_hall")
    t = w.track("cam_a", w.clip("cam_a", 0, 60))
    shelf = w.obs(t, 0.0, xy=(1.0, 3.6), zone="zone_shelf_a")
    door = w.obs(t, 10.0, xy=(5.6, 0.2), zone="zone_door_b")
    th = w.track("cam_hall", w.clip("cam_hall", 0, 60))
    hall = w.obs(th, 13.0, xy=(5.0, -1.0), zone="zone_hall")
    obj = w.obj("blue equipment case", t, th, status=AssociationStatus.HUMAN_CONFIRMED)
    return w, obj, t, {"shelf": shelf, "door": door, "hall": hall}, Verifier(w.store, site)


def test_finding_text_is_generated_not_copied_from_agent(door_scene, now):
    """Review #2: a supported claim must not smuggle unverified prose into a VerifiedFinding."""
    from spoor.verification import PresenceClaim

    w, obj, t, o, v = door_scene
    c = PresenceClaim(statement="The case was carried out of the building at 14:05", object_instance_id=obj,
                      observation_ids=[o["shelf"]])  # fmt: skip
    r = v.verify(c)
    f = v.promote(c, r, case_id="case_w", now=now)
    assert "building" not in f.statement and f.statement.startswith("blue equipment case visible in 1 cited frame")


def test_hypothesis_with_unchecked_claims_is_never_supported(door_scene, now):
    w, obj, t, o, v = door_scene
    ctx = ToolContext(store=w.store, site=w.site, case=w.case, verifier=v, scope=EvidenceScope(), now=lambda: now)
    hyp = {"hypotheses": [{"claim": "Case carried out and taken off site", "missing_evidence": [],
                           "distinguishing_request": None,
                           "claims": [claim("presence", "case seen", obj, observation_ids=[o["shelf"]]),
                                      claim("presence", "broken", None)]}]}  # fmt: skip
    res = investigate(ctx, hypothesis_backend=ScriptedBackend([final(hyp)]))
    assert res.hypotheses[0].status.value == "insufficient_evidence"
    assert "agent's wording" in res.answer and "verified: blue equipment case visible" in res.answer


def test_exit_contradicted_by_cited_later_inroom_sighting(door_scene):
    """Review #3: citing the back-in-room sighting must not exempt it from the contradiction check."""
    from spoor.verification import ExitClaim

    w, obj, t, o, v = door_scene
    back = w.obs(t, 30.0, xy=(1.0, 3.6), zone="zone_shelf_a")
    r = v.verify(ExitClaim(statement="left", object_instance_id=obj, door_zone_id="zone_door_b",
                           observation_ids=[o["door"], o["hall"], back]))  # fmt: skip
    assert r.verdict == V.CONTRADICTED


def test_exit_contradicted_by_unzoned_inroom_sighting(door_scene):
    from spoor.verification import ExitClaim

    w, obj, t, o, v = door_scene
    w.obs(t, 30.0, xy=(2.5, 2.5))  # back in the room, outside any named zone
    r = v.verify(ExitClaim(statement="left", object_instance_id=obj, door_zone_id="zone_door_b",
                           observation_ids=[o["hall"], o["door"]]))  # fmt: skip
    assert r.verdict == V.CONTRADICTED


def test_exit_needs_beyond_sighting_after_door_in_time(door_scene):
    from spoor.verification import ExitClaim

    w, obj, t, o, v = door_scene
    early_hall = w.obs(w.track("cam_hall", w.clip("cam_hall", 0, 60)), 2.0, xy=(5.0, -1.0), zone="zone_hall")
    w.link(obj, w.store.get(RawObservation, early_hall).track_id, AssociationStatus.HUMAN_CONFIRMED)
    r = v.verify(ExitClaim(statement="left", object_instance_id=obj, door_zone_id="zone_door_b",
                           observation_ids=[early_hall, o["door"]]))  # fmt: skip
    assert r.verdict == V.INSUFFICIENT_EVIDENCE


def test_zone_membership_respects_uncertainty_on_both_sides(site, now):
    """Review #9: near an edge (not just a vertex) the answer is undetermined, inside or outside."""
    from spoor.verification import PresenceClaim

    w = World(EvidenceStore(), site, now)
    w.camera("cam_a")
    t = w.track("cam_a", w.clip("cam_a", 0, 10))
    inside_edge = w.obs(t, 1.0, xy=(3.75, 1.05))  # desk spans y 1.0-1.8; 5 cm inside, radius 0.2
    outside_edge = w.obs(t, 5.0, xy=(3.75, 0.9))  # 10 cm outside the middle of the edge
    obj = w.obj("blue equipment case", t)
    v = Verifier(w.store, site)
    for oid in (inside_edge, outside_edge):
        r = v.verify(PresenceClaim(statement="on desk", object_instance_id=obj, observation_ids=[oid],
                                   zone_id="zone_desk"))  # fmt: skip
        assert r.verdict == V.INSUFFICIENT_EVIDENCE, oid


def test_low_frame_rate_cctv_is_not_a_flickering_object(site, now):
    """Review #10: 1 fps footage of a continuously visible object is one span, not 9 gaps."""
    w = World(EvidenceStore(), site, now)
    w.camera("cam_a")
    t = w.track("cam_a", w.clip("cam_a", 0, 20, fps=1.0))
    for s in range(10):
        w.obs(t, float(s), xy=(1.0 + 0.3 * s, 2.5))
    obj = w.obj("blue equipment case", t)
    spans = visibility_timeline(w.store, obj)
    assert [s.state for s in spans] == [ObjectVisibility.VISIBLE]
    assert unobserved_intervals(w.store, obj, w.ms(0), w.ms(9)) == []


def test_stream_start_offset_frames_and_cuts_are_exact(tmp_path, now):
    """Review #5: exports whose timestamps start at 20 s must still cite and cut the right frames."""
    from datetime import timedelta

    from test_ingest import H, W, make_video

    from spoor.contracts import MediaAuthorization
    from spoor.ingest import MediaStore, asset_path, extract_frame, ingest
    from spoor.ingest.clips import cut_frames
    from spoor.ingest.ffmpeg import run_ffmpeg

    src = make_video(tmp_path / "offset.mp4", "-output_ts_offset", "20")
    auth = MediaAuthorization(authorization_id="auth_o", site_id="site_test", uploader="t",
                              rights_statement="synthetic test clip", purpose="test", consent_confirmed=True,
                              hosted_processing_allowed=False, retention_until=now + timedelta(days=1),
                              recorded_at=now)  # fmt: skip
    r = ingest(src, store=MediaStore(tmp_path / "d"), authorization=auth, site_id="site_test", camera_id=None,
               ingested_by="t", now=now)  # fmt: skip
    assert r.original_frames.stream_start_s >= 19.9
    path = asset_path(MediaStore(tmp_path / "d"), r.original)
    full = run_ffmpeg("-i", str(path), "-fps_mode", "passthrough", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1",
                      capture_stdout=True)  # fmt: skip
    size = W * H * 3
    for i in (0, 5, 30, 59):
        assert extract_frame(path, r.original_frames, i, fmt="rgb") == full[i * size:(i + 1) * size], i
    proxy = asset_path(MediaStore(tmp_path / "d"), r.proxy)
    win = cut_frames(proxy, r.proxy_frames, source_media_id=r.original.media_id, start_frame=20, end_frame=39,
                     out_dir=tmp_path / "cuts")  # fmt: skip
    assert win.n_frames == 20 and win.to_original(0.0) == 20 and win.to_original(1.0) == 30


def test_projection_rescales_or_refuses_on_resolution_change(room, now):
    """Review #13: a 1920x1080 calibration applied to a 640x360 substream must rescale; other aspects refuse."""
    import numpy as np

    from spoor.contracts import RigState, SpatialMode
    from spoor.spatial import ProjectionInput, fit_floor_calibration, project_observation

    s = 1 / 400  # synthetic top-down camera: 400 px per metre on the 1920x1080 frame
    img = [(200, 200), (1800, 200), (1800, 1000), (200, 1000), (1000, 600), (600, 400)]
    hold = [(400, 800), (1400, 300), (1000, 900)]
    cal = fit_floor_calibration(
        calibration_id="calib_x", camera_id="cam_a", floor_id="floor_g", version=1, image_points_px=img,
        floor_points_m=[(u * s, v * s) for u, v in img], holdout_image_points_px=hold,
        holdout_floor_points_m=[(u * s, v * s) for u, v in hold], image_wh_px=(1920, 1080), now=now,
        thresholds=__import__("spoor.spatial", fromlist=["ValidationThresholds"]).ValidationThresholds(0.1, 0.2),
    )  # fmt: skip
    assert cal.rig_state == RigState.VALIDATED_FLOOR_ONLY
    cam = Camera(camera_id="cam_a", site_id="site_test", floor_id="floor_g", name="a", resolution_wh_px=(1920, 1080))

    def proj(uv, wh):
        return project_observation(ProjectionInput(["obs_1"], uv, on_floor_plane=True, frame_wh_px=wh),
                                   camera=cam, site=room, calibration=cal, now=now)  # fmt: skip

    full = proj((1000, 600), (1920, 1080))
    sub = proj((1000 / 3, 200), (640, 360))
    assert full.spatial_mode == sub.spatial_mode == SpatialMode.FLOOR_XY
    assert np.allclose(full.floor_xy_m, sub.floor_xy_m, atol=1e-6)
    assert proj((300, 200), (640, 480)).spatial_mode == SpatialMode.IMAGE_ONLY  # different aspect: refuse
