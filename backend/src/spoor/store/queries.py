"""Deterministic spatiotemporal queries over the evidence store (PRD §16.1, §16.3). No model calls here.

Times are milliseconds on the normalized (synchronized) timeline. Observations without a normalized time are never
silently ordered against other cameras; they are reported as `unsynced`.

Two different notions of continuity are kept apart on purpose:
- *visibility* (was the object seen by ANY confirmed camera track?) -> `visibility_timeline`
- *tracked motion* (did ONE camera follow it without a gap?) -> `track_segments`; only this can make a path "observed"
  (PRD §14.3 step 9: cross-camera transitions are dashed, gaps stay gaps).
"""

from collections import Counter
from dataclasses import dataclass, field
from itertools import pairwise

from spoor.contracts import (
    AssociationStatus,
    Camera,
    CameraCoverage,
    Case,
    EvidenceLabel,
    Hypothesis,
    MediaAsset,
    ObjectInstance,
    ObjectVisibility,
    RawObservation,
    SpatialEstimate,
    SpatialMode,
    Track,
    TrackAssociation,
    VerifiedFinding,
)

from .repository import EvidenceStore, epoch_ms

CONFIRMED = frozenset({AssociationStatus.VERIFIED_SAME_CAMERA, AssociationStatus.HUMAN_CONFIRMED,
                       AssociationStatus.SCAN_BOUND})
TENTATIVE = frozenset({AssociationStatus.CANDIDATE_CROSS_CAMERA, AssociationStatus.UNRESOLVED})
DEFAULT_MAX_GAP_MS = 500.0  # floor; the effective gap also scales with the source frame interval
GAP_FRAME_FACTOR = 2.5  # a run breaks after ~2.5 missing frame intervals
OCCLUSION_FLAGS = frozenset({"partially_occluded", "touches_frame_edge"})


@dataclass(frozen=True)
class TimedObservation:
    obs: RawObservation
    t_ms: float
    unc_ms: float
    association: AssociationStatus
    gap_ms: float = DEFAULT_MAX_GAP_MS  # largest spacing that still counts as continuous for this source


def _track_gap_ms(store: EvidenceStore, track_id: str) -> float:
    """1 fps CCTV must not look like a flickering object: the continuity gap follows the clip's frame interval."""
    try:
        media = store.get(MediaAsset, store.get(Track, track_id).media_id)
    except KeyError:
        return DEFAULT_MAX_GAP_MS
    fps = media.probe.avg_fps if media.probe else None
    return max(DEFAULT_MAX_GAP_MS, GAP_FRAME_FACTOR * 1000.0 / fps) if fps else DEFAULT_MAX_GAP_MS


@dataclass
class ObjectEvidence:
    timed: list[TimedObservation]
    unsynced: list[RawObservation]
    invalid_skipped: int


def latest_associations(store: EvidenceStore, object_instance_id: str) -> dict[str, TrackAssociation]:
    """Current association per track (highest version wins; earlier versions stay in history)."""
    latest: dict[str, TrackAssociation] = {}
    for a in store.find(TrackAssociation, object_instance_id=object_instance_id):
        if a.track_id not in latest or a.version > latest[a.track_id].version:
            latest[a.track_id] = a
    return latest


def object_evidence(store: EvidenceStore, object_instance_id: str, *, include_tentative: bool = False) -> ObjectEvidence:
    allowed = CONFIRMED | (TENTATIVE if include_tentative else frozenset())
    assoc = {t: a.status for t, a in latest_associations(store, object_instance_id).items() if a.status in allowed}
    invalid = store.invalid_ids() if assoc else set()
    timed, unsynced, skipped = [], [], 0
    for track_id, status in assoc.items():
        if track_id in invalid:
            continue
        gap = _track_gap_ms(store, track_id)
        for o in store.find(RawObservation, track_id=track_id):
            if o.observation_id in invalid:
                skipped += 1
                continue
            if not o.observed:
                continue
            f = o.source_frame
            if f is None or f.normalized_utc is None:
                unsynced.append(o)
                continue
            timed.append(TimedObservation(o, float(epoch_ms(f.normalized_utc)), f.time_uncertainty_ms or 0.0, status,
                                          gap))
    timed.sort(key=lambda t: (t.t_ms, t.obs.observation_id))
    return ObjectEvidence(timed, unsynced, skipped)


def estimate_for(store: EvidenceStore, observation_id: str) -> SpatialEstimate | None:
    """Most recent valid estimate derived from this observation."""
    return store.latest_estimates([observation_id]).get(observation_id)


@dataclass
class ObjectView:
    """One consistent snapshot of an object's confirmed evidence + estimates, loaded with batched queries."""

    evidence: ObjectEvidence
    estimates: dict[str, SpatialEstimate]

    @classmethod
    def load(cls, store: EvidenceStore, object_instance_id: str) -> "ObjectView":
        ev = object_evidence(store, object_instance_id)
        return cls(ev, store.latest_estimates(t.obs.observation_id for t in ev.timed))

    def zone(self, observation_id: str) -> str | None:
        est = self.estimates.get(observation_id)
        return est.zone_id if est else None


@dataclass
class LastSeen:
    observation: RawObservation | None
    t_ms: float | None
    uncertainty_ms: float | None
    estimate: SpatialEstimate | None
    # Observations from other cameras within timing uncertainty: "last" cannot be decided between them.
    ambiguous_with: list[str] = field(default_factory=list)
    unsynced_observation_ids: list[str] = field(default_factory=list)
    label: EvidenceLabel = EvidenceLabel.UNKNOWN


def last_confirmed(store: EvidenceStore, object_instance_id: str) -> LastSeen:
    """Latest *visibly confirmed* observation: confirmed track association, observed=True, valid, synchronized."""
    ev = object_evidence(store, object_instance_id)
    unsynced = [o.observation_id for o in ev.unsynced]
    if not ev.timed:
        return LastSeen(None, None, None, None, unsynced_observation_ids=unsynced)
    last = ev.timed[-1]
    ambiguous = []
    for t in reversed(ev.timed[:-1]):
        if last.t_ms - t.t_ms > last.unc_ms + t.unc_ms + 60_000:
            break  # sorted by time: nothing earlier can be within uncertainty
        if t.obs.camera_id != last.obs.camera_id and last.t_ms - t.t_ms <= last.unc_ms + t.unc_ms:
            ambiguous.append(t.obs.observation_id)
    return LastSeen(last.obs, last.t_ms, last.unc_ms, estimate_for(store, last.obs.observation_id), ambiguous[::-1],
                    unsynced, EvidenceLabel.OBSERVED)  # fmt: skip


@dataclass
class Span:
    """A contiguous visible run (any confirmed camera), or a gap between runs."""

    state: ObjectVisibility
    start_ms: float
    end_ms: float
    observation_ids: list[str]
    track_ids: list[str] = field(default_factory=list)
    camera_ids: list[str] = field(default_factory=list)
    zone_id: str | None = None

    @property
    def camera_id(self) -> str | None:
        return self.camera_ids[0] if len(self.camera_ids) == 1 else None


def _runs(timed: list[TimedObservation], max_gap_ms: float | None) -> list[list[TimedObservation]]:
    """Split into continuous runs. With max_gap_ms=None the threshold adapts to each source's frame interval."""
    runs: list[list[TimedObservation]] = []
    for t in timed:
        limit = max_gap_ms if max_gap_ms is not None else max(t.gap_ms, runs[-1][-1].gap_ms) if runs else 0
        if runs and t.t_ms - runs[-1][-1].t_ms <= limit:
            runs[-1].append(t)
        else:
            runs.append([t])
    return runs


def visibility_timeline(store: EvidenceStore, object_instance_id: str, *, max_gap_ms: float | None = None,
                        with_zones: bool = True, view: ObjectView | None = None) -> list[Span]:  # fmt: skip
    """Visible spans and out-of-view gaps. A gap is never bridged into continuous motion (PRD §16.3)."""
    view = view or (ObjectView.load(store, object_instance_id) if with_zones
                    else ObjectView(object_evidence(store, object_instance_id), {}))  # fmt: skip
    spans: list[Span] = []
    for i, run in enumerate(_runs(view.evidence.timed, max_gap_ms)):
        if i:
            spans.append(Span(ObjectVisibility.OUT_OF_VIEW, spans[-1].end_ms, run[0].t_ms, []))
        occluded = sum(bool(OCCLUSION_FLAGS & set(t.obs.quality_flags)) for t in run) > len(run) / 2
        state = (ObjectVisibility.PARTIALLY_OCCLUDED if occluded
                 else ObjectVisibility.VISIBLE_AGAIN if i else ObjectVisibility.VISIBLE)  # fmt: skip
        zones = Counter(z for t in run if (z := view.zone(t.obs.observation_id)))
        spans.append(Span(
            state, run[0].t_ms, run[-1].t_ms, [t.obs.observation_id for t in run],
            list(dict.fromkeys(t.obs.track_id for t in run if t.obs.track_id)),
            list(dict.fromkeys(t.obs.camera_id for t in run if t.obs.camera_id)),
            zones.most_common(1)[0][0] if zones else None,
        ))  # fmt: skip
    return spans


@dataclass
class TrackSegment:
    """A run of ONE track with no gap longer than max_gap: the only basis for an 'observed' path."""

    track_id: str
    camera_id: str | None
    observations: list[TimedObservation]

    @property
    def start_ms(self) -> float:
        return self.observations[0].t_ms

    @property
    def end_ms(self) -> float:
        return self.observations[-1].t_ms

    @property
    def observation_ids(self) -> list[str]:
        return [t.obs.observation_id for t in self.observations]


def track_segments(store: EvidenceStore, object_instance_id: str, *, max_gap_ms: float | None = None,
                   view: ObjectView | None = None) -> list[TrackSegment]:  # fmt: skip
    ev = view.evidence if view else object_evidence(store, object_instance_id)
    by_track: dict[str, list[TimedObservation]] = {}
    for t in ev.timed:
        by_track.setdefault(t.obs.track_id or "", []).append(t)
    segs = [TrackSegment(track, run[0].obs.camera_id, run)
            for track, obs in by_track.items() for run in _runs(obs, max_gap_ms)]  # fmt: skip
    return sorted(segs, key=lambda s: (s.start_ms, s.track_id))


@dataclass
class UnobservedInterval:
    start_ms: float
    end_ms: float
    # Cameras that were recording during the interval yet did not confirm the object. Empty => blind spot.
    covering_camera_ids: list[str]
    reason: str


def site_camera_ids(store: EvidenceStore, object_instance_id: str) -> set[str]:
    """Cameras on the object's site. Coverage from other sites must never leak into this site's answers."""
    case = store.get(Case, store.get(ObjectInstance, object_instance_id).case_id)
    return {c.camera_id for c in store.find(Camera, site_id=case.site_id)}


def _split_by_coverage(covs: list[tuple[float, float, str]], start_ms: float,
                       end_ms: float) -> list[UnobservedInterval]:  # fmt: skip
    """Split a gap at camera-coverage boundaries so blind spots are reported exactly, not blurred into coverage."""
    cuts = sorted({start_ms, end_ms, *(t for a, b, _ in covs for t in (a, b) if start_ms < t < end_ms)})
    pieces: list[UnobservedInterval] = []
    for a, b in pairwise(cuts):
        cams = sorted({cam for ca, cb, cam in covs if ca < b and cb > a})
        reason = "recorded_but_not_confirmed" if cams else "no_camera_coverage"
        if pieces and pieces[-1].covering_camera_ids == cams:
            pieces[-1] = UnobservedInterval(pieces[-1].start_ms, b, cams, reason)
        else:
            pieces.append(UnobservedInterval(a, b, cams, reason))
    return pieces


def coverage_intervals(store: EvidenceStore, camera_ids: set[str]) -> list[tuple[float, float, str]]:
    if not camera_ids:
        return []
    return [(float(epoch_ms(c.start_utc)), float(epoch_ms(c.end_utc)), c.camera_id)
            for c in store.find(CameraCoverage, camera_id=sorted(camera_ids))
            if not store.is_invalid(c.coverage_id)]  # fmt: skip


def unobserved_intervals(store: EvidenceStore, object_instance_id: str, start_ms: float, end_ms: float, *,
                         max_gap_ms: float | None = None) -> list[UnobservedInterval]:  # fmt: skip
    seen = [(s.start_ms, s.end_ms) for s in visibility_timeline(store, object_instance_id, max_gap_ms=max_gap_ms,
                                                                with_zones=False)
            if s.state != ObjectVisibility.OUT_OF_VIEW]  # fmt: skip
    edge = max_gap_ms if max_gap_ms is not None else DEFAULT_MAX_GAP_MS
    gaps, cursor = [], start_ms
    for i, (a, b) in enumerate(seen):
        if b < start_ms or a > end_ms:
            continue
        # Between two visible spans the timeline already decided it was a gap; at the window edge use the floor.
        if a - cursor > (0 if i and cursor > start_ms else edge):
            gaps.append((cursor, a))
        cursor = max(cursor, b)
    if end_ms - cursor > edge:
        gaps.append((cursor, end_ms))
    covs = coverage_intervals(store, site_camera_ids(store, object_instance_id)) if gaps else []
    return [piece for a, b in gaps for piece in _split_by_coverage(covs, a, b)]


@dataclass
class Transition:
    from_zone: str | None
    to_zone: str | None
    from_observation_id: str
    to_observation_id: str
    start_ms: float
    end_ms: float
    label: EvidenceLabel  # observed only inside one camera's continuous track; hypothesized otherwise


def transitions(store: EvidenceStore, object_instance_id: str, start_ms: float | None = None,
                end_ms: float | None = None, *, max_gap_ms: float | None = None) -> list[Transition]:  # fmt: skip
    """Zone changes. `observed` only inside one track segment. A change between segments (a gap, or a hand-off between
    cameras) is `hypothesized`. Overlapping segments from different cameras imply no movement and are not linked."""
    view = ObjectView.load(store, object_instance_id)

    def in_window(t: TimedObservation) -> bool:
        return (start_ms is None or t.t_ms >= start_ms) and (end_ms is None or t.t_ms <= end_ms)

    out: list[Transition] = []
    zoned_segments = []
    for seg in track_segments(store, object_instance_id, max_gap_ms=max_gap_ms, view=view):
        zoned = [(t, z) for t in seg.observations if in_window(t) and (z := view.zone(t.obs.observation_id))]
        for (a, za), (b, zb) in pairwise(zoned):
            if za != zb:
                out.append(Transition(za, zb, a.obs.observation_id, b.obs.observation_id, a.t_ms, b.t_ms,
                                      EvidenceLabel.OBSERVED))  # fmt: skip
        if zoned:
            zoned_segments.append(zoned)
    for prev, nxt in pairwise(zoned_segments):
        (a, za), (b, zb) = prev[-1], nxt[0]
        if za != zb and b.t_ms > a.t_ms:
            out.append(Transition(za, zb, a.obs.observation_id, b.obs.observation_id, a.t_ms, b.t_ms,
                                  EvidenceLabel.HYPOTHESIZED))  # fmt: skip
    return sorted(out, key=lambda t: (t.start_ms, t.end_ms))


@dataclass
class ObjectState:
    object_instance_id: str
    label: str
    visibility: ObjectVisibility
    evidence_label: EvidenceLabel
    last_observation_id: str | None
    last_seen_ms: float | None
    estimate: SpatialEstimate | None
    spatial_mode: SpatialMode


def world_state_at(store: EvidenceStore, case_id: str, t_ms: float, *,
                   max_gap_ms: float | None = None) -> list[ObjectState]:  # fmt: skip
    """Per-object state at time t, computed only from recorded events (PRD §13.3)."""
    states = []
    for obj in store.find(ObjectInstance, case_id=case_id):
        view = ObjectView.load(store, obj.object_instance_id)
        times = {t.obs.observation_id: t.t_ms for t in view.evidence.timed}
        spans = [s for s in visibility_timeline(store, obj.object_instance_id, max_gap_ms=max_gap_ms, view=view)
                 if s.state != ObjectVisibility.OUT_OF_VIEW]  # fmt: skip
        inside = next((s for s in spans if s.start_ms <= t_ms <= s.end_ms), None)
        before = [s for s in spans if s.end_ms < t_ms]
        if inside:
            oid = max((o for o in inside.observation_ids if times[o] <= t_ms), key=lambda o: times[o])
            est = view.estimates.get(oid)
            states.append(ObjectState(obj.object_instance_id, obj.label, inside.state, EvidenceLabel.OBSERVED, oid,
                                      times[oid], est, est.spatial_mode if est else SpatialMode.IMAGE_ONLY))
        elif before:
            oid = before[-1].observation_ids[-1]
            states.append(ObjectState(obj.object_instance_id, obj.label, ObjectVisibility.OUT_OF_VIEW,
                                      EvidenceLabel.UNKNOWN, oid, before[-1].end_ms, view.estimates.get(oid),
                                      SpatialMode.UNKNOWN))  # fmt: skip
        else:
            states.append(ObjectState(obj.object_instance_id, obj.label, ObjectVisibility.UNOBSERVED,
                                      EvidenceLabel.UNKNOWN, None, None, None, SpatialMode.UNKNOWN))  # fmt: skip
    return states


@dataclass
class InferredDependency:
    record_id: str
    observation_ids: list[str]
    association_statuses: list[str]


def claims_relying_on_inferred_links(store: EvidenceStore, case_id: str) -> list[InferredDependency]:
    """Hypotheses/findings whose cited observations belong to tracks linked only tentatively (PRD §16.1)."""
    tentative_tracks: dict[str, str] = {}
    for obj in store.find(ObjectInstance, case_id=case_id):
        for track_id, a in latest_associations(store, obj.object_instance_id).items():
            if a.status in TENTATIVE:
                tentative_tracks[track_id] = a.status.value
    out = []
    records = [(h.hypothesis_id, h.support_observation_ids) for h in store.find(Hypothesis, case_id=case_id)]
    records += [(f.finding_id, f.observation_ids) for f in store.find(VerifiedFinding, case_id=case_id)]
    for rid, obs_ids in records:
        hits = [(o, tentative_tracks[t]) for o in obs_ids
                if store.exists(o) and (t := store.get(RawObservation, o).track_id) in tentative_tracks]  # fmt: skip
        if hits:
            out.append(InferredDependency(rid, [h[0] for h in hits], sorted({h[1] for h in hits})))
    return out
