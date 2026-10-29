"""Step 04 acceptance tests: append-only memory, projections, queries, invalidation and deletion (PRD §16)."""

from datetime import timedelta

import pytest
from builders import HUMAN, World
from sqlalchemy import text

from spoor.contracts import (
    Actor,
    ActorKind,
    AssociationStatus,
    EvidenceLabel,
    FindingStatus,
    FrameRef,
    Hypothesis,
    HypothesisStatus,
    HypothesisStatusChange,
    ObjectVisibility,
    RawObservation,
    SourceType,
    VerifiedFinding,
    new_id,
)
from spoor.store import (
    ConflictError,
    DanglingReference,
    EvidenceStore,
    StoreError,
    claims_relying_on_inferred_links,
    last_confirmed,
    transitions,
    unobserved_intervals,
    visibility_timeline,
    world_state_at,
)

VERIFIER = Actor(kind=ActorKind.VERIFIER_SERVICE, id="verifier")
AGENT = Actor(kind=ActorKind.AGENT, id="hypothesis", model="muse-spark-1.3")


@pytest.fixture
def w(room, now) -> World:
    return World(EvidenceStore(), room, now)


@pytest.fixture
def scene(w):
    """Case on Shelf A (0-2 s), carried to the desk (2-4 s), unseen 4-10 s, seen near Door B (10-11 s)."""
    w.camera("cam_a")
    clip = w.clip("cam_a", 0, 12)
    t1 = w.track("cam_a", clip)
    obs = {}
    for t in (0.0, 0.5, 1.0, 1.5):
        obs[t] = w.obs(t1, t, xy=(1.0, 3.6), zone="zone_shelf_a")
    for t in (2.0, 2.5, 3.0, 3.5, 4.0):
        obs[t] = w.obs(t1, t, xy=(3.5, 1.4), zone="zone_desk")
    t2 = w.track("cam_a", clip)
    for t in (10.0, 10.5, 11.0):
        obs[t] = w.obs(t2, t, xy=(5.5, 0.2), zone="zone_door_b", flags=("partially_occluded",))
    obj = w.obj("blue equipment case", t1, t2)
    return w, obj, obs


# --- immutability & references ---------------------------------------------------


def test_observations_cannot_be_updated_even_with_raw_sql(scene):
    w, _, obs = scene
    with pytest.raises(Exception, match="append-only"), w.store.engine.begin() as c:
        c.execute(text("UPDATE observations SET label='laptop' WHERE id=:i"), {"i": obs[0.0]})


def test_immutable_record_cannot_be_rewritten(scene):
    w, _, obs = scene
    with pytest.raises(StoreError, match="immutable"):
        w.store.put(w.store.get(RawObservation, obs[0.0]))


def test_dangling_reference_rejected(w, now):
    w.camera("cam_a")
    with pytest.raises(DanglingReference):
        w.store.put(RawObservation(
            observation_id="obs_ghost", source_type=SourceType.VIDEO, camera_id="cam_a",
            source_frame=FrameRef(media_id="media_missing", pts_ms=0, frame_index=0), label="case", created_at=now,
        ))  # fmt: skip


# --- queries --------------------------------------------------------------------------


def test_last_confirmed_is_latest_visible(scene):
    w, obj, obs = scene
    ls = last_confirmed(w.store, obj)
    assert ls.observation.observation_id == obs[11.0]
    assert ls.label == EvidenceLabel.OBSERVED and ls.estimate.zone_id == "zone_door_b"


def test_candidate_cross_camera_track_not_confirmed(scene):
    w, obj, obs = scene
    w.camera("cam_b")
    clip_b = w.clip("cam_b", 0, 30)
    tb = w.track("cam_b", clip_b)
    w.obs(tb, 20.0, xy=(5.8, 0.1), zone="zone_door_b")
    w.link(obj, tb, AssociationStatus.CANDIDATE_CROSS_CAMERA)
    assert last_confirmed(w.store, obj).observation.observation_id == obs[11.0]


def test_cross_camera_ambiguity_within_clock_uncertainty(scene):
    w, obj, _ = scene
    w.camera("cam_b", sync_uncertainty_ms=400)
    tb = w.track("cam_b", w.clip("cam_b", 0, 30))
    near = w.obs(tb, 10.8)
    w.link(obj, tb, AssociationStatus.HUMAN_CONFIRMED)
    assert near in last_confirmed(w.store, obj).ambiguous_with


def test_unsynced_observations_reported_not_ordered(scene):
    w, obj, obs = scene
    t = w.store.get(RawObservation, obs[0.0]).track_id
    late = w.obs(t, 11.5, synced=False)
    ls = last_confirmed(w.store, obj)
    assert ls.observation.observation_id == obs[11.0] and late in ls.unsynced_observation_ids


def test_visibility_timeline_keeps_gaps(scene):
    w, obj, _ = scene
    spans = visibility_timeline(w.store, obj)
    states = [s.state for s in spans]
    assert states == [ObjectVisibility.VISIBLE, ObjectVisibility.OUT_OF_VIEW, ObjectVisibility.PARTIALLY_OCCLUDED]
    gap = spans[1]
    assert gap.start_ms == w.ms(4.0) and gap.end_ms == w.ms(10.0) and gap.observation_ids == []


def test_unobserved_intervals_distinguish_coverage(scene):
    w, obj, _ = scene
    gaps = unobserved_intervals(w.store, obj, w.ms(0), w.ms(15))
    assert [(g.start_ms, g.end_ms, g.reason) for g in gaps] == [
        (w.ms(4.0), w.ms(10.0), "recorded_but_not_confirmed"),
        (w.ms(11.0), w.ms(12.0), "recorded_but_not_confirmed"),
        (w.ms(12.0), w.ms(15.0), "no_camera_coverage"),  # coverage ends at 12 s: blind from there
    ]
    late = unobserved_intervals(w.store, obj, w.ms(13), w.ms(20))
    assert late[0].reason == "no_camera_coverage" and late[0].covering_camera_ids == []


def test_transitions_observed_only_within_continuous_span(scene):
    w, obj, _ = scene
    tr = transitions(w.store, obj)
    assert [(t.from_zone, t.to_zone, t.label) for t in tr] == [
        ("zone_shelf_a", "zone_desk", EvidenceLabel.OBSERVED),
        ("zone_desk", "zone_door_b", EvidenceLabel.HYPOTHESIZED),
    ]


def test_world_state_at(scene):
    w, obj, obs = scene
    s = {st.object_instance_id: st for st in world_state_at(w.store, "case_w", w.ms(3.0))}[obj]
    assert s.evidence_label == EvidenceLabel.OBSERVED and s.estimate.zone_id == "zone_desk"
    s = world_state_at(w.store, "case_w", w.ms(7.0))[0]
    assert s.visibility == ObjectVisibility.OUT_OF_VIEW and s.evidence_label == EvidenceLabel.UNKNOWN
    assert s.last_observation_id == obs[4.0]


# --- hypotheses, revisions ---------------------------------------------------------------


def make_hyp(w, obs_ids):
    return w.store.put(Hypothesis(hypothesis_id=new_id("hypothesis"), case_id="case_w",
                                  claim="Case may have moved beyond Door B", support_observation_ids=obs_ids,
                                  proposed_by=AGENT, created_at=w.t0))  # fmt: skip


def change(h, frm, to, actor, ev, now):
    return HypothesisStatusChange(change_id=new_id("status_change"), hypothesis_id=h.hypothesis_id, from_status=frm,
                                  to_status=to, actor=actor, evidence_ids=ev, reason="test", at=now)  # fmt: skip


def test_hypothesis_status_is_projection_of_changes(scene, now):
    w, _, obs = scene
    h = make_hyp(w, [obs[11.0]])
    w.store.change_status(change(h, HypothesisStatus.PROPOSED, HypothesisStatus.EVALUATED, AGENT, [], now))
    w.store.change_status(change(h, HypothesisStatus.EVALUATED, HypothesisStatus.INSUFFICIENT_EVIDENCE, VERIFIER,
                                 [obs[11.0]], now))  # fmt: skip
    assert w.store.get(Hypothesis, h.hypothesis_id).status == HypothesisStatus.INSUFFICIENT_EVIDENCE
    assert [c.to_status for c in w.store.status_history(h.hypothesis_id)] == ["evaluated", "insufficient_evidence"]
    with pytest.raises(ConflictError):  # stale writer
        w.store.change_status(change(h, HypothesisStatus.PROPOSED, HypothesisStatus.EVALUATED, AGENT, [], now))


def test_hypothesis_cannot_be_stored_pre_decided(w, now):
    with pytest.raises(StoreError):
        w.store.put(Hypothesis(hypothesis_id="hyp_x", case_id="case_w", claim="It left", proposed_by=AGENT,
                               status=HypothesisStatus.SUPPORTED, created_at=now))  # fmt: skip


def test_revision_optimistic_concurrency(w, now):
    r1 = w.store.append_revision("case_w", expected_parent=None, actor=HUMAN, reason="open", changed_ids=[], now=now)
    w.store.append_revision("case_w", expected_parent=r1.case_revision_id, actor=HUMAN, reason="b", changed_ids=[],
                            now=now)  # fmt: skip
    with pytest.raises(ConflictError):
        w.store.append_revision("case_w", expected_parent=r1.case_revision_id, actor=HUMAN, reason="c",
                                changed_ids=[], now=now)  # fmt: skip


# --- invalidation & deletion ---------------------------------------------------------------


def finding_for(w, obs_id, now):
    return w.store.put(VerifiedFinding(
        finding_id=new_id("finding"), case_id="case_w", statement="Case last visible near Door B",
        observation_ids=[obs_id], verification_status=FindingStatus.SUPPORTED_BY_VIDEO, verified_by=VERIFIER, at=now,
    ))  # fmt: skip


def test_calibration_invalidation_propagates_to_findings(scene, now):
    w, _, obs = scene
    f = finding_for(w, obs[11.0], now)
    from spoor.store import estimate_for

    est = estimate_for(w.store, obs[11.0])
    affected = w.store.invalidate("calib_cam_a", reason="camera bumped", actor=HUMAN, now=now)
    assert est.estimate_id in affected and w.store.is_invalid(est.estimate_id)
    assert estimate_for(w.store, obs[11.0]) is None
    # The finding cites the observation (still valid), not the estimate, so it stands.
    assert not w.store.is_invalid(f.finding_id)


def test_purge_media_invalidates_dependents_and_removes_evidence(scene, now):
    w, obj, obs = scene
    f = finding_for(w, obs[11.0], now)
    media_id = w.store.get(RawObservation, obs[11.0]).source_frame.media_id
    shas = w.store.purge_media(media_id, actor=HUMAN, reason="retention expired", now=now + timedelta(days=1))
    assert len(shas) == 1
    assert not w.store.exists(obs[11.0]) and not w.store.exists(media_id)
    assert w.store.is_invalid(f.finding_id)
    assert last_confirmed(w.store, obj).observation is None


def test_delete_case_removes_case_records(scene, now):
    w, _, obs = scene
    make_hyp(w, [obs[11.0]])
    w.store.delete_case("case_w", actor=HUMAN, now=now)
    assert not w.store.exists("case_w") and not w.store.find(Hypothesis, case_id="case_w")
    assert w.store.exists(obs[11.0])  # site-level source evidence is governed by media retention, not the case


def test_claims_relying_on_inferred_links(scene, now):
    w, obj, obs = scene
    w.camera("cam_b")
    tb = w.track("cam_b", w.clip("cam_b", 0, 30))
    far = w.obs(tb, 25.0)
    w.link(obj, tb, AssociationStatus.CANDIDATE_CROSS_CAMERA)
    h = make_hyp(w, [obs[11.0], far])
    deps = claims_relying_on_inferred_links(w.store, "case_w")
    assert [(d.record_id, d.observation_ids) for d in deps] == [(h.hypothesis_id, [far])]


def test_file_backed_store_persists(tmp_path, room, now):
    path = tmp_path / "spoor.db"
    w = World(EvidenceStore.sqlite_file(path), room, now)
    w.camera("cam_a")
    again = EvidenceStore.sqlite_file(path)
    assert again.exists("cam_a") and again.exists("case_w")
