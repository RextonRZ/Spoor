"""Step 01 acceptance tests: the evidence contract enforces the PRD §11.3 invariants."""

import pytest
from pydantic import ValidationError

from spoor.contracts import (
    SCHEMA_MODELS,
    Actor,
    ActorKind,
    AgentResponse,
    AssetKind,
    Claim,
    FindingStatus,
    FrameRef,
    HypothesisStatus,
    HypothesisStatusChange,
    MediaAsset,
    ModelProvenance,
    MultiView3DEstimate,
    RawObservation,
    RigState,
    SourceType,
    SpatialEstimate,
    SpatialMode,
    VerifiedFinding,
    check_estimate_in_site,
    id_kind,
    new_id,
)

VERIFIER = Actor(kind=ActorKind.VERIFIER_SERVICE, id="verifier")
AGENT = Actor(kind=ActorKind.AGENT, id="hypothesis/req_1", model="muse-spark-1.3")
SHA = "a" * 64


def video_obs(now, **overrides):
    data = dict(
        observation_id="obs_104",
        source_type=SourceType.VIDEO,
        camera_id="cam_a",
        source_frame=FrameRef(media_id="media_camA_clip03", pts_ms=9340, frame_index=280),
        track_id="trk_camA_7",
        label="blue equipment case",
        bbox_xyxy_px=(633.6, 475.2, 902.4, 723.6),
        frame_wh_px=(1920, 1080),
        quality_flags=["partially_occluded"],
        provenance=ModelProvenance(model="sam-3.1", model_version="sam-3.1", provider="meta_model_api"),
        confidence_raw=0.81,
        created_at=now,
    )
    return RawObservation(**(data | overrides))


# --- IDs -------------------------------------------------------------------


def test_new_ids_are_typed_and_unique():
    ids = {new_id("observation") for _ in range(1000)}
    assert len(ids) == 1000
    assert all(i.startswith("obs_") and id_kind(i) == "observation" for i in ids)


def test_wrong_id_type_rejected(now):
    with pytest.raises(ValidationError):
        video_obs(now, observation_id="zone_shelf_a")


# --- Observations ----------------------------------------------------------


def test_prd_example_observation_parses(now):
    obs = video_obs(now)
    assert obs.bbox_xyxy_normalized == pytest.approx((0.33, 0.44, 0.47, 0.67))
    assert obs.confidence_calibrated is None


def test_observations_are_immutable(now):
    obs = video_obs(now)
    with pytest.raises(ValidationError):
        obs.label = "laptop"


def test_video_observation_needs_source_frame(now):
    with pytest.raises(ValidationError, match="source_frame"):
        video_obs(now, source_frame=None)


def test_bbox_outside_frame_rejected(now):
    with pytest.raises(ValidationError, match="bbox"):
        video_obs(now, bbox_xyxy_px=(1800, 10, 2000, 50))


def test_calibrated_confidence_needs_calibration(now):
    with pytest.raises(ValidationError, match="calibrated confidence"):
        video_obs(now, confidence_calibrated=0.9)


def test_unknown_fields_rejected(now):
    with pytest.raises(ValidationError):
        video_obs(now, suspect_score=0.9)


# --- Spatial estimates -----------------------------------------------------


def floor_estimate(now, xy, **overrides):
    data = dict(
        estimate_id="loc_104", observation_ids=["obs_104"], spatial_mode=SpatialMode.FLOOR_XY,
        floor_id="floor_g", floor_xy_m=xy, uncertainty_radius_m=0.55, method="homography_floor_contact",
        calibration_id="calib_camA_v2", created_at=now,
    )  # fmt: skip
    return SpatialEstimate(**(data | overrides))


def test_floor_estimate_inside_site(now, room):
    check_estimate_in_site(floor_estimate(now, (3.14, 1.82)), room)


def test_pixel_values_stored_as_metres_rejected(now, room):
    with pytest.raises(ValueError, match="outside the site floor"):
        check_estimate_in_site(floor_estimate(now, (640.0, 360.0)), room)


def test_floor_xy_requires_uncertainty_and_calibration(now):
    with pytest.raises(ValidationError):
        floor_estimate(now, (1.0, 1.0), uncertainty_radius_m=None)
    with pytest.raises(ValidationError):
        floor_estimate(now, (1.0, 1.0), calibration_id=None)


def test_unknown_mode_cannot_carry_coordinates(now):
    with pytest.raises(ValidationError):
        floor_estimate(now, (1.0, 1.0), spatial_mode=SpatialMode.UNKNOWN)


def test_estimate_without_source_rejected(now):
    with pytest.raises(ValidationError):
        floor_estimate(now, (1.0, 1.0), observation_ids=[])


def test_multiview_requires_validated_rig(now):
    with pytest.raises(ValidationError, match="validated_multiview_3d"):
        MultiView3DEstimate(
            estimate_id="xyz_021", site_xyz_m=(2.14, 3.61, 1.06), source_observation_ids=["obs_a", "obs_b"],
            correspondence_id="corr_021", calibration_ids=["calib_a", "calib_b"],
            rig_state=RigState.VALIDATED_FLOOR_ONLY, synchronization_id="sync_04",
            reprojection_error_px_by_camera={"cam_a": 1.2}, uncertainty_3d_m=0.05, quality_gates_passed=[],
            software_version="test", created_at=now,
        )  # fmt: skip


# --- Hypotheses and findings ----------------------------------------------


def change(now, frm, to, actor, evidence=("obs_135",)):
    return HypothesisStatusChange(
        change_id="chg_1", hypothesis_id="hyp_12", from_status=frm, to_status=to, actor=actor,
        evidence_ids=list(evidence), reason="test", at=now,
    )  # fmt: skip


def test_legal_status_path(now):
    change(now, HypothesisStatus.PROPOSED, HypothesisStatus.EVALUATED, AGENT)
    change(now, HypothesisStatus.EVALUATED, HypothesisStatus.SUPPORTED, VERIFIER)
    change(now, HypothesisStatus.SUPPORTED, HypothesisStatus.EVALUATED, VERIFIER)  # re-opened by new evidence


def test_cannot_skip_evaluation(now):
    with pytest.raises(ValidationError, match="illegal transition"):
        change(now, HypothesisStatus.PROPOSED, HypothesisStatus.SUPPORTED, VERIFIER)


def test_agent_cannot_decide_hypothesis(now):
    with pytest.raises(ValidationError, match="only the verifier"):
        change(now, HypothesisStatus.EVALUATED, HypothesisStatus.SUPPORTED, AGENT)


def test_supported_requires_evidence(now):
    with pytest.raises(ValidationError, match="requires evidence"):
        change(now, HypothesisStatus.EVALUATED, HypothesisStatus.SUPPORTED, VERIFIER, evidence=())


def finding(now, **overrides):
    data = dict(
        finding_id="finding_21", case_id="case_1", statement="Case last visible near Door B",
        observation_ids=["obs_135"], spatial_estimate_ids=["loc_135"],
        verification_status=FindingStatus.SUPPORTED_BY_VIDEO,
        limitations=["camera_clipped_exit", "clock_offset_uncertain"], verified_by=VERIFIER, at=now,
    )  # fmt: skip
    return VerifiedFinding(**(data | overrides))


def test_prd_example_finding_parses(now):
    assert finding(now).observation_ids == ["obs_135"]


def test_source_free_finding_rejected(now):
    with pytest.raises(ValidationError):
        finding(now, observation_ids=[])


def test_agent_cannot_verify_finding(now):
    with pytest.raises(ValidationError, match="never an agent"):
        finding(now, verified_by=AGENT)


def test_agent_actor_must_name_model():
    with pytest.raises(ValidationError):
        Actor(kind=ActorKind.AGENT, id="lead")


# --- Media -----------------------------------------------------------------


def test_derivative_must_name_parent(now):
    base = dict(
        media_id="media_proxy1", site_id="site_test", kind=AssetKind.WORKING_DERIVATIVE, sha256=SHA,
        byte_size=10, mime_type="video/mp4", original_filename="x.mp4", authorization_id="auth_1",
        ingested_at=now, ingested_by="tester",
    )  # fmt: skip
    with pytest.raises(ValidationError, match="parent_media_id"):
        MediaAsset(**base)
    MediaAsset(**base, parent_media_id="media_orig1", processing_method="proxy_h264_v1", software_version="ff 8.1")


def test_normalized_time_needs_sync():
    with pytest.raises(ValidationError, match="sync"):
        FrameRef(media_id="media_a", pts_ms=0, frame_index=0, normalized_utc="2026-10-27T14:00:00Z")


# --- Agents ----------------------------------------------------------------


def test_observation_claim_must_cite():
    with pytest.raises(ValidationError):
        Claim(kind="observation", text="The case was on the desk")
    Claim(kind="hypothesis", text="The case may have left via Door B")


def test_abstention_needs_reason():
    with pytest.raises(ValidationError):
        AgentResponse(request_id="req_1", status="abstained", cost={}, model_version="muse-spark-1.3")


# --- Schema export ---------------------------------------------------------


def test_all_schemas_export():
    for model in SCHEMA_MODELS:
        assert model.model_json_schema()["title"] == model.__name__
