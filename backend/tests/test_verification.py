"""Step 07 acceptance tests: the deterministic verifier, including PRD scenarios C02, C05, C08, C09 (§21.2)."""

from datetime import timedelta

import pytest
from builders import HUMAN, World

from spoor.contracts import (
    Actor,
    ActorKind,
    AssociationStatus,
    EvidenceLabel,
    Hypothesis,
    HypothesisStatus,
    RawObservation,
    SensorEvent,
    SensorKind,
    SourceType,
    new_id,
)
from spoor.contracts import (
    VerificationVerdict as V,
)
from spoor.store import EvidenceStore
from spoor.verification import (
    ExitClaim,
    LastSeenClaim,
    OrderClaim,
    PresenceClaim,
    TransferClaim,
    TransitionClaim,
    Verifier,
)

AGENT = Actor(kind=ActorKind.AGENT, id="hypothesis", model="muse-spark-1.3")


@pytest.fixture
def scene(site, now):
    w = World(EvidenceStore(), site, now)
    w.camera("cam_a")
    clip = w.clip("cam_a", 0, 20)
    t1 = w.track("cam_a", clip)
    o = {t: w.obs(t1, t, xy=(1.0, 3.6), zone="zone_shelf_a") for t in (0.0, 0.5, 1.0)}
    o[1.5] = w.obs(t1, 1.5, xy=(1.8, 2.9))  # carried: realistic ~2 m/s path between shelf and desk
    o[2.0] = w.obs(t1, 2.0, xy=(2.6, 2.1))
    o |= {t: w.obs(t1, t, xy=(3.5, 1.4), zone="zone_desk") for t in (2.5, 3.0)}
    t2 = w.track("cam_a", clip)
    o |= {t: w.obs(t2, t, xy=(5.5, 0.2), zone="zone_door_b") for t in (10.0, 10.5)}
    obj = w.obj("blue equipment case", t1, t2)
    return w, obj, o, Verifier(w.store, site)


def test_last_seen_supported_with_limitations(scene):
    w, obj, o, v = scene
    r = v.verify(LastSeenClaim(statement="Case last visible near Door B", object_instance_id=obj,
                               observation_id=o[10.5]))  # fmt: skip
    assert r.verdict == V.SUPPORTED and r.label == EvidenceLabel.OBSERVED
    assert any("says nothing about where" in lim for lim in r.limitations)


def test_earlier_last_seen_contradicted(scene):
    w, obj, o, v = scene
    r = v.verify(LastSeenClaim(statement="Case last seen on desk", object_instance_id=obj, observation_id=o[3.0]))
    assert r.verdict == V.CONTRADICTED


def test_unresolvable_and_invalid_citations(scene, now):
    w, obj, o, v = scene
    r = v.verify(LastSeenClaim(statement="Case at door", object_instance_id=obj, observation_id="obs_made_up"))
    assert r.verdict == V.UNSUPPORTED and "does not resolve" in r.reasons[0]
    w.store.invalidate(o[10.5], reason="track corrected", actor=HUMAN, now=now)
    r = v.verify(PresenceClaim(statement="Case at door", object_instance_id=obj, observation_ids=[o[10.5]]))
    assert r.verdict == V.UNSUPPORTED and "invalidated" in r.reasons[0]


@pytest.mark.parametrize("statement", ["The thief took the case", "A nervous man carried it",
                                       "Person identified as the culprit"])  # fmt: skip
def test_overreach_rejected(scene, statement):
    w, obj, o, v = scene
    r = v.verify(PresenceClaim(statement=statement, object_instance_id=obj, observation_ids=[o[10.0]]))
    assert r.verdict == V.UNSUPPORTED and "identity, intent" in r.reasons[0]


def test_presence_zone_checks(scene):
    w, obj, o, v = scene
    assert v.verify(PresenceClaim(statement="Case on desk", object_instance_id=obj, observation_ids=[o[3.0]],
                                  zone_id="zone_desk")).verdict == V.SUPPORTED  # fmt: skip
    r = v.verify(PresenceClaim(statement="Case on desk", object_instance_id=obj, observation_ids=[o[10.0]],
                               zone_id="zone_desk"))  # fmt: skip
    assert r.verdict == V.CONTRADICTED


def test_c02_gap_cannot_be_shown_as_observed(scene):
    """C02 occlusion/gap: a path across the unobserved 2-10 s interval is only a hypothesis."""
    w, obj, o, v = scene
    r = v.verify(TransitionClaim(statement="Case moved desk to door", object_instance_id=obj,
                                 from_observation_id=o[3.0], to_observation_id=o[10.0], asserted_label="observed"))
    assert r.verdict == V.UNSUPPORTED and r.label == EvidenceLabel.HYPOTHESIZED
    r = v.verify(TransitionClaim(statement="Case may have moved desk to door", object_instance_id=obj,
                                 from_observation_id=o[3.0], to_observation_id=o[10.0],
                                 asserted_label="hypothesized"))  # fmt: skip
    assert r.verdict == V.INSUFFICIENT_EVIDENCE and r.label == EvidenceLabel.HYPOTHESIZED


def test_observed_transition_within_track(scene):
    w, obj, o, v = scene
    r = v.verify(TransitionClaim(statement="Case moved shelf to desk", object_instance_id=obj,
                                 from_observation_id=o[1.0], to_observation_id=o[2.5], asserted_label="observed"))
    assert r.verdict == V.SUPPORTED and r.label == EvidenceLabel.OBSERVED


def test_impossible_speed_contradicted(scene):
    w, obj, o, v = scene
    t = w.track("cam_a", w.store.get(RawObservation, o[0.0]).source_frame.media_id)
    fast = w.obs(t, 1.1, xy=(5.8, 0.1), zone="zone_door_b")  # 5 m in 0.1 s
    w.link(obj, t, AssociationStatus.VERIFIED_SAME_CAMERA)
    r = v.verify(TransitionClaim(statement="Case moved", object_instance_id=obj, from_observation_id=o[1.0],
                                 to_observation_id=fast, asserted_label="hypothesized"))  # fmt: skip
    assert r.verdict == V.CONTRADICTED and "implausible" in r.reasons[0]


def test_c09_exit_without_footage_beyond_door(scene):
    """C09 blind spot: last seen at the door is not 'left the room'."""
    w, obj, o, v = scene
    r = v.verify(ExitClaim(statement="Case left through Door B", object_instance_id=obj, door_zone_id="zone_door_b",
                           observation_ids=[o[10.0], o[10.5]]))  # fmt: skip
    assert r.verdict == V.INSUFFICIENT_EVIDENCE and "no footage beyond" in r.reasons[0]


def test_exit_supported_with_hallway_footage(scene):
    w, obj, o, v = scene
    w.camera("cam_hall")
    th = w.track("cam_hall", w.clip("cam_hall", 0, 30))
    out = w.obs(th, 13.0, xy=(5.0, -1.0), zone="zone_hall")
    w.link(obj, th, AssociationStatus.HUMAN_CONFIRMED)
    r = v.verify(ExitClaim(statement="Case moved through Door B into the hallway", object_instance_id=obj,
                           door_zone_id="zone_door_b", observation_ids=[o[10.5], out]))  # fmt: skip
    assert r.verdict == V.SUPPORTED and any("not who carried it" in lim for lim in r.limitations)


def test_c08_simulated_sensor_cannot_establish_exit(scene, now):
    """C08: a (simulated) door log alone never proves the object left."""
    w, obj, o, v = scene
    sens = w.store.put(SensorEvent(sensor_event_id=new_id("sensor_event"), site_id=w.site.site_id,
                                   source_type=SourceType.SENSOR_SIMULATED,
                                   device_id="door_b", kind=SensorKind.DOOR_CONTACT, value="open",
                                   zone_id="zone_door_b", device_time_utc=now + timedelta(seconds=11),
                                   clock_quality="unsynced", import_batch="test"))  # fmt: skip
    r = v.verify(ExitClaim(statement="Case left through Door B", object_instance_id=obj, door_zone_id="zone_door_b",
                           observation_ids=[o[10.5]], sensor_event_ids=[sens.sensor_event_id]))  # fmt: skip
    assert r.verdict == V.INSUFFICIENT_EVIDENCE
    assert any("SIMULATED" in lim for lim in r.limitations)


def test_c05_proximity_is_not_transfer(scene):
    w, obj, o, v = scene
    r = v.verify(TransferClaim(statement="Case moved from shelf to desk", object_instance_id=obj,
                               observation_ids=[o[0.0], o[3.0]]))  # fmt: skip
    assert r.verdict == V.INSUFFICIENT_EVIDENCE and "proximity is not transfer" in r.reasons[0]


def test_order_within_clock_uncertainty_is_undetermined(scene):
    w, obj, o, v = scene
    w.camera("cam_b", sync_uncertainty_ms=800)
    tb = w.track("cam_b", w.clip("cam_b", 0, 30))
    b = w.obs(tb, 10.2)
    r = v.verify(OrderClaim(statement="Seen on A before B", first_observation_id=o[10.0], second_observation_id=b))
    assert r.verdict == V.INSUFFICIENT_EVIDENCE


def test_cross_camera_conflict_detected(scene):
    w, obj, o, v = scene
    w.camera("cam_b")
    tb = w.track("cam_b", w.clip("cam_b", 0, 30))
    w.obs(tb, 10.1, xy=(0.5, 3.8), zone="zone_shelf_a")  # same instant, other side of the room
    w.link(obj, tb, AssociationStatus.HUMAN_CONFIRMED)
    assert v.consistency_conflicts(obj)


def test_decide_writes_status_changes_and_promote(scene, now):
    w, obj, o, v = scene
    h = w.store.put(Hypothesis(hypothesis_id=new_id("hypothesis"), case_id="case_w", claim="Case left via Door B",
                               support_observation_ids=[o[10.5]], proposed_by=AGENT, created_at=now))  # fmt: skip
    status, results = v.decide(h.hypothesis_id, [ExitClaim(statement="Case left via Door B",
                                                            object_instance_id=obj, door_zone_id="zone_door_b",
                                                            observation_ids=[o[10.5]])], now=now)  # fmt: skip
    assert status == HypothesisStatus.INSUFFICIENT_EVIDENCE
    history = w.store.status_history(h.hypothesis_id)
    assert [c.actor.kind for c in history] == ["verifier_service", "verifier_service"]
    claim = LastSeenClaim(statement="Case last visible near Door B", object_instance_id=obj, observation_id=o[10.5])
    finding = v.promote(claim, v.verify(claim), case_id="case_w", now=now)
    assert finding is not None and finding.observation_ids == [o[10.5]]
    assert v.promote(claim, results[0], case_id="case_w") is None  # not supported -> no finding


def test_hypothesis_that_only_restates_last_seen_is_not_supported(scene, now):
    # "it left through the far door" cited only with the (true) last-seen fact: nothing tested what happened next
    w, obj, o, v = scene
    h = w.store.put(Hypothesis(hypothesis_id=new_id("hypothesis"), case_id="case_w", claim="it left afterwards",
                               support_observation_ids=[o[10.5]], proposed_by=AGENT, created_at=now))  # fmt: skip
    last = max(o, key=float)
    status, results = v.decide(h.hypothesis_id, [LastSeenClaim(statement="last seen", object_instance_id=obj,
                                                               observation_id=o[last])], now=now)  # fmt: skip
    assert results[0].verdict.value == "supported" and status == HypothesisStatus.INSUFFICIENT_EVIDENCE
    assert "nothing tests what it says happened next" in w.store.status_history(h.hypothesis_id)[-1].reason


def test_describe_never_crashes_on_an_unknown_door_zone(scene):
    """Rejected claims are described too (the answer shows what each idea was tested on): an agent may name an area id
    where a zone id belongs; the sentence keeps the id instead of failing the whole investigation."""
    from spoor.verification import ExitClaim

    _, obj, o, v = scene
    text = v.describe(ExitClaim(statement="left", object_instance_id=obj, door_zone_id="AREA_NOT_A_ZONE",
                                observation_ids=[o[10.0]]))
    assert "AREA_NOT_A_ZONE" in text
