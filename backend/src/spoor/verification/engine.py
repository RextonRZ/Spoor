"""Deterministic verification engine (PRD §17.4, §18). The only non-human path to `supported`.

It never reads another agent's prose as a source: every check resolves IDs in the store and recomputes geometry and
timing from recorded observations.
"""

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime

from pydantic import TypeAdapter

from spoor.contracts import (
    Actor,
    ActorKind,
    EvidenceLabel,
    FindingStatus,
    FloorCalibration,
    HypothesisStatus,
    HypothesisStatusChange,
    ObjectInstance,
    RawObservation,
    ReadOutcome,
    SensorEvent,
    Site,
    SourceType,
    VerificationVerdict,
    VerifiedFinding,
    ZoneKind,
    new_id,
    point_in_polygon,
)
from spoor.forensics.conveyance import ConveyorNet
from spoor.forensics.journey import ON_CONVEYANCE_DEVICES, latest_plan, scan_xy
from spoor.safety import find_forbidden
from spoor.spatial import ordering_is_determined
from spoor.spatial.homography import image_to_site
from spoor.store import (
    CONFIRMED_STATUSES,
    EvidenceStore,
    estimate_for,
    last_confirmed,
    latest_associations,
    object_evidence,
    track_segments,
)
from spoor.store.parcels import scans_for

from .claims import (
    ExitClaim,
    LastSeenClaim,
    OrderClaim,
    ParcelMatchClaim,
    PresenceClaim,
    StructuredClaim,
    TransferClaim,
    TransitionClaim,
)

VERIFIER = Actor(kind=ActorKind.VERIFIER_SERVICE, id="spoor.verification.engine/v1")
CLAIM_ADAPTER = TypeAdapter(StructuredClaim)
V = VerificationVerdict


BELT_MARGIN_M = 2.5  # a parcel between two belt scans is on the belt: further than this from every belt rules it out
STATION_WINDOW_S = 3.0  # a scan this close in time pins the parcel to the station
STATION_MARGIN_M = 6.0


@dataclass
class VerificationResult:
    verdict: VerificationVerdict
    label: EvidenceLabel
    reasons: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    checked_ids: list[str] = field(default_factory=list)
    estimate_ids: list[str] = field(default_factory=list)


def _edge_distance(p: tuple[float, float], polygon: list[tuple[float, float]]) -> float:
    """Shortest distance from a point to the polygon's edges (not just its vertices)."""
    px, py = p
    best = math.inf
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1], strict=True):
        dx, dy = x2 - x1, y2 - y1
        seg = dx * dx + dy * dy
        t = 0.0 if seg == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg))
        best = min(best, math.hypot(px - (x1 + t * dx), py - (y1 + t * dy)))
    return best


class _Stop(Exception):
    def __init__(self, result: VerificationResult):
        self.result = result


def _fail(verdict: VerificationVerdict, reason: str, label=EvidenceLabel.UNKNOWN, **kw) -> _Stop:
    return _Stop(VerificationResult(verdict, label, [reason], **kw))


class Verifier:
    def __init__(self, store: EvidenceStore, site: Site, *, max_speed_mps: float = 3.0,
                 max_gap_ms: float | None = None):  # fmt: skip
        self.store, self.site = store, site
        self.max_speed_mps, self.max_gap_ms = max_speed_mps, max_gap_ms
        self.zones = {z.zone_id: z for z in site.zones}

    # --- shared checks ------------------------------------------------------------------------

    def _observation(self, oid: str) -> RawObservation:
        if not oid.startswith("obs_") or not self.store.exists(oid):
            raise _fail(V.UNSUPPORTED, f"citation {oid} does not resolve to a stored observation")
        if self.store.is_invalid(oid):
            raise _fail(V.UNSUPPORTED, f"citation {oid} is invalidated (source deleted or corrected)")
        return self.store.get(RawObservation, oid)

    def _linked(self, object_id: str, obs: RawObservation, limitations: list[str]) -> None:
        if not self.store.exists(object_id):
            raise _fail(V.UNSUPPORTED, f"unknown object {object_id}")
        assoc = latest_associations(self.store, object_id).get(obs.track_id or "")
        if assoc is None:
            raise _fail(V.UNSUPPORTED, f"{obs.observation_id} is not linked to {object_id}")
        if assoc.status not in CONFIRMED_STATUSES:
            limitations.append(f"{obs.observation_id} is linked to the object only as {assoc.status.value}")

    def _overreach(self, statement: str) -> None:
        if hits := find_forbidden(statement):
            terms = sorted({t for _, t in hits})
            raise _fail(V.UNSUPPORTED, f"statement asserts identity, intent or personal attributes: {terms}")

    def _order(self, a: RawObservation, b: RawObservation) -> bool | None:
        return ordering_is_determined(a.source_frame, b.source_frame)

    def _gap_s(self, a: RawObservation, b: RawObservation) -> float:
        return (b.source_frame.normalized_utc - a.source_frame.normalized_utc).total_seconds()

    def _in_zone(self, oid: str, zone_id: str) -> bool | None:
        """True/False if the observation's estimate places it in/out of the zone; None if position is unknown."""
        est = estimate_for(self.store, oid)
        if est is None or (est.zone_id is None and est.floor_xy_m is None):
            return None
        zone = self.zones.get(zone_id)
        if est.floor_xy_m is None or zone is None:
            # Zone-only / anchored placement: membership comes from the operator region, not geometry.
            return est.zone_id == zone_id
        inside = point_in_polygon(est.floor_xy_m, zone.polygon_m)
        # Within the uncertainty radius of the boundary (either side) the answer is undetermined.
        if _edge_distance(est.floor_xy_m, zone.polygon_m) <= (est.uncertainty_radius_m or 0.0):
            return None
        return inside

    def _near_zone(self, oid: str, zone_id: str) -> bool:
        """Inside the zone or within the position uncertainty of its boundary ("at the door")."""
        est = estimate_for(self.store, oid)
        zone = self.zones.get(zone_id)
        if est is None or zone is None:
            return False
        if est.floor_xy_m is None:
            return est.zone_id == zone_id
        return point_in_polygon(est.floor_xy_m, zone.polygon_m) or             _edge_distance(est.floor_xy_m, zone.polygon_m) <= (est.uncertainty_radius_m or 0.0)  # fmt: skip

    # --- entry point ------------------------------------------------------------------------------

    def verify(self, claim: StructuredClaim | dict) -> VerificationResult:
        if isinstance(claim, dict):
            claim = CLAIM_ADAPTER.validate_python(claim)
        try:
            self._overreach(claim.statement)
            handler = {LastSeenClaim: self._last_seen, PresenceClaim: self._presence,
                       TransitionClaim: self._transition, ExitClaim: self._exit, TransferClaim: self._transfer,
                       OrderClaim: self._order_claim, ParcelMatchClaim: self._parcel_match}[type(claim)]  # fmt: skip
            return handler(claim)
        except _Stop as stop:
            return stop.result

    # --- claim handlers ---------------------------------------------------------------------------

    def _last_seen(self, c: LastSeenClaim) -> VerificationResult:
        lim: list[str] = []
        obs = self._observation(c.observation_id)
        self._linked(c.object_instance_id, obs, lim)
        if not obs.observed:
            raise _fail(V.UNSUPPORTED, "the cited observation is not a direct observation")
        ls = last_confirmed(self.store, c.object_instance_id)
        if ls.observation is None:
            raise _fail(V.INSUFFICIENT_EVIDENCE, "no synchronized, confirmed observation of the object exists")
        if ls.observation.observation_id != c.observation_id and c.observation_id not in ls.ambiguous_with:
            raise _fail(V.CONTRADICTED, f"a later confirmed observation exists: {ls.observation.observation_id}",
                        checked_ids=[c.observation_id, ls.observation.observation_id])  # fmt: skip
        if ls.ambiguous_with:
            lim.append(f"cannot order against {len(ls.ambiguous_with)} observation(s) from other cameras within "
                       "clock uncertainty")  # fmt: skip
        if ls.unsynced_observation_ids:
            lim.append(f"{len(ls.unsynced_observation_ids)} unsynchronized observation(s) not considered")
        lim.append("last *visible* confirmation; says nothing about where the object went afterwards")
        est = estimate_for(self.store, c.observation_id)
        return VerificationResult(V.SUPPORTED, EvidenceLabel.OBSERVED, ["latest confirmed observation"], lim,
                                  [c.observation_id], [est.estimate_id] if est else [])  # fmt: skip

    def _presence(self, c: PresenceClaim) -> VerificationResult:
        lim: list[str] = []
        obs = [self._observation(o) for o in c.observation_ids]
        for o in obs:
            self._linked(c.object_instance_id, o, lim)
        if c.zone_id is None:
            return VerificationResult(V.SUPPORTED, EvidenceLabel.OBSERVED, ["object visible in cited frames"], lim,
                                      c.observation_ids)  # fmt: skip
        if c.zone_id not in self.zones:
            raise _fail(V.UNSUPPORTED, f"unknown zone {c.zone_id}")
        verdicts = [self._in_zone(o.observation_id, c.zone_id) for o in obs]
        ests = [e.estimate_id for o in obs if (e := estimate_for(self.store, o.observation_id))]
        if any(v is False for v in verdicts):
            raise _fail(V.CONTRADICTED, f"spatial estimates place the object outside {c.zone_id}",
                        checked_ids=c.observation_ids, estimate_ids=ests)  # fmt: skip
        if any(v is None for v in verdicts):
            raise _fail(V.INSUFFICIENT_EVIDENCE, "position not established (no estimate, or within uncertainty of "
                        "the zone boundary)", checked_ids=c.observation_ids, estimate_ids=ests)  # fmt: skip
        return VerificationResult(V.SUPPORTED, EvidenceLabel.ESTIMATED, [f"estimated inside {c.zone_id}"],
                                  lim + ["zone placement is a calibrated estimate, not a measurement"],
                                  c.observation_ids, ests)  # fmt: skip

    def _physical(self, a: RawObservation, b: RawObservation) -> str | None:
        """Return a contradiction reason if moving from a to b is physically implausible."""
        ea, eb = estimate_for(self.store, a.observation_id), estimate_for(self.store, b.observation_id)
        if not (ea and eb and ea.floor_xy_m and eb.floor_xy_m):
            return None
        dist = max(0.0, math.dist(ea.floor_xy_m, eb.floor_xy_m) - (ea.uncertainty_radius_m or 0)
                   - (eb.uncertainty_radius_m or 0))  # fmt: skip
        dt = abs(self._gap_s(a, b)) + ((a.source_frame.time_uncertainty_ms or 0)
                                       + (b.source_frame.time_uncertainty_ms or 0)) / 1000.0  # fmt: skip
        if dist > 0 and (dt == 0 or dist / dt > self.max_speed_mps):
            return (f"implies moving at least {dist:.2f} m in {dt:.2f} s (> {self.max_speed_mps} m/s): physically "
                    "implausible, or two different objects")  # fmt: skip
        return None

    def _same_segment(self, object_id: str, a: str, b: str) -> bool:
        """Both observations inside one camera's continuous track (no gap, no camera hand-off)."""
        for seg in track_segments(self.store, object_id, max_gap_ms=self.max_gap_ms):
            ids = seg.observation_ids
            if a in ids and b in ids:
                return True
        return False

    def _transition(self, c: TransitionClaim) -> VerificationResult:
        lim: list[str] = []
        a, b = self._observation(c.from_observation_id), self._observation(c.to_observation_id)
        self._linked(c.object_instance_id, a, lim)
        self._linked(c.object_instance_id, b, lim)
        ids = [a.observation_id, b.observation_id]
        order = self._order(a, b)
        if order is None:
            raise _fail(V.INSUFFICIENT_EVIDENCE, "the two observations cannot be ordered within clock uncertainty",
                        checked_ids=ids)  # fmt: skip
        if order is False:
            raise _fail(V.CONTRADICTED, "the 'to' observation precedes the 'from' observation", checked_ids=ids)
        if reason := self._physical(a, b):
            raise _fail(V.CONTRADICTED, reason, checked_ids=ids)
        continuous = self._same_segment(c.object_instance_id, a.observation_id, b.observation_id)
        if c.asserted_label == "observed":
            if not continuous:
                raise _fail(V.UNSUPPORTED, "the path crosses an unobserved interval or a camera hand-off; it "
                            "may only be shown as hypothesized", EvidenceLabel.HYPOTHESIZED, checked_ids=ids)
            return VerificationResult(V.SUPPORTED, EvidenceLabel.OBSERVED, ["continuously tracked"], lim, ids)
        return VerificationResult(V.INSUFFICIENT_EVIDENCE, EvidenceLabel.HYPOTHESIZED,
                                  ["physically possible but not observed"], lim, ids)  # fmt: skip

    def _exit(self, c: ExitClaim) -> VerificationResult:
        lim: list[str] = []
        door = self.zones.get(c.door_zone_id)
        if door is None or door.kind != ZoneKind.DOOR:
            raise _fail(V.UNSUPPORTED, f"{c.door_zone_id} is not a known door zone")
        obs = [self._observation(o) for o in c.observation_ids]
        for o in obs:
            self._linked(c.object_instance_id, o, lim)
        at_door = [o for o in obs if self._near_zone(o.observation_id, c.door_zone_id)]
        beyond = [o for o in obs if (e := estimate_for(self.store, o.observation_id)) and e.zone_id
                  and self.zones.get(e.zone_id) and self.zones[e.zone_id].kind == ZoneKind.HALLWAY]  # fmt: skip
        for sid in c.sensor_event_ids:
            if not self.store.exists(sid):
                raise _fail(V.UNSUPPORTED, f"sensor event {sid} does not resolve")
            ev = self.store.get(SensorEvent, sid)
            if ev.site_id != self.site.site_id:
                raise _fail(V.UNSUPPORTED, f"sensor event {sid} belongs to another site")
            if ev.source_type == SourceType.SENSOR_SIMULATED:
                lim.append(f"{sid} is a SIMULATED sensor event")
            lim.append(f"{sid} ({ev.kind.value}) shows the door state only, not what passed through")
        if not at_door:
            raise _fail(V.INSUFFICIENT_EVIDENCE, f"no cited observation places the object at {c.door_zone_id}",
                        checked_ids=c.observation_ids, limitations=lim)  # fmt: skip
        if any(o.source_frame.normalized_utc is None for o in obs):
            raise _fail(V.INSUFFICIENT_EVIDENCE, "a cited observation is not on the synchronized timeline",
                        checked_ids=c.observation_ids, limitations=lim)  # fmt: skip
        last_door = max(at_door, key=lambda o: o.source_frame.normalized_utc)
        beyond = sorted((o for o in beyond if self._order(last_door, o) is True),
                        key=lambda o: o.source_frame.normalized_utc)  # fmt: skip
        if not beyond:
            raise _fail(V.INSUFFICIENT_EVIDENCE, "last seen at the door; no footage beyond it (after the door "
                        "sighting) confirms the object left", EvidenceLabel.HYPOTHESIZED,
                        checked_ids=c.observation_ids, limitations=lim)  # fmt: skip
        # Every confirmed sighting after the door must be beyond it. Being cited does not exempt an observation.
        for t in object_evidence(self.store, c.object_instance_id).timed:
            if self._order(last_door, t.obs) is not True:
                continue
            e = estimate_for(self.store, t.obs.observation_id)
            zone = self.zones.get(e.zone_id) if e and e.zone_id else None
            if zone is not None and zone.kind == ZoneKind.HALLWAY:
                continue
            if zone is not None or (e is not None and e.floor_xy_m is not None):
                raise _fail(V.CONTRADICTED, f"a later confirmed observation ({t.obs.observation_id}) places the "
                            "object back inside", checked_ids=[*c.observation_ids, t.obs.observation_id])
            raise _fail(V.INSUFFICIENT_EVIDENCE, f"the object is seen again after the door ({t.obs.observation_id}) "
                        "at an unmapped position", checked_ids=[*c.observation_ids, t.obs.observation_id],
                        limitations=lim)  # fmt: skip
        return VerificationResult(V.SUPPORTED, EvidenceLabel.OBSERVED, ["seen at the door, then beyond it"],
                                  lim + ["shows the object's movement only; not who carried it or why"],
                                  c.observation_ids)  # fmt: skip

    def _transfer(self, c: TransferClaim) -> VerificationResult:
        lim: list[str] = []
        obs = sorted((self._observation(o) for o in c.observation_ids), key=lambda o: o.source_frame.normalized_utc
                     or datetime.max.replace(tzinfo=UTC))  # fmt: skip
        for o in obs:
            self._linked(c.object_instance_id, o, lim)
        contact = [o for o in obs if "contact_observed" in o.quality_flags]
        zones = [(e.zone_id if (e := estimate_for(self.store, o.observation_id)) else None) for o in obs]
        if not contact:
            raise _fail(V.INSUFFICIENT_EVIDENCE, "no visible contact: proximity is not transfer",
                        EvidenceLabel.HYPOTHESIZED, checked_ids=c.observation_ids)  # fmt: skip
        if zones[0] is None or zones[-1] is None or zones[0] == zones[-1]:
            raise _fail(V.INSUFFICIENT_EVIDENCE, "no before/after change of position is established",
                        EvidenceLabel.HYPOTHESIZED, checked_ids=c.observation_ids)  # fmt: skip
        if self._order(obs[0], obs[-1]) is not True:
            raise _fail(V.INSUFFICIENT_EVIDENCE, "before/after order not established", checked_ids=c.observation_ids)
        return VerificationResult(V.SUPPORTED, EvidenceLabel.OBSERVED, ["contact with before/after positions"],
                                  lim + ["describes object movement only"], c.observation_ids)  # fmt: skip

    def _order_claim(self, c: OrderClaim) -> VerificationResult:
        a, b = self._observation(c.first_observation_id), self._observation(c.second_observation_id)
        ids = [a.observation_id, b.observation_id]
        order = self._order(a, b)
        if order is None:
            return VerificationResult(V.INSUFFICIENT_EVIDENCE, EvidenceLabel.UNKNOWN,
                                      ["order undetermined within clock uncertainty"], [], ids)  # fmt: skip
        if order is False:
            return VerificationResult(V.CONTRADICTED, EvidenceLabel.CONTRADICTED, ["order is reversed"], [], ids)
        return VerificationResult(V.SUPPORTED, EvidenceLabel.OBSERVED, ["order established"], [], ids)

    def _sighting_xy(self, obs: RawObservation) -> list[tuple[float, float]]:
        """Where a sighting could be on the floor: its spatial estimate, else the camera's calibrated pose at every
        plausible height (on the floor, or carried up to chest height); empty if neither is available."""
        est = estimate_for(self.store, obs.observation_id)
        if est is not None and est.floor_xy_m is not None:
            return [tuple(est.floor_xy_m)]
        cals = [c for c in self.store.find(FloorCalibration, camera_id=obs.camera_id)
                if c.pose_rvec is not None and not self.store.is_invalid(c.calibration_id)]
        if not cals or obs.bbox_xyxy_px is None:
            return []
        b = obs.bbox_xyxy_px
        out = []
        for h, (u, v) in ((0.0, ((b[0] + b[2]) / 2, b[3])), *((h, ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2))
                                                                for h in (0.8, 1.2))):  # fmt: skip
            xyz = image_to_site(cals[-1], [[u, v]], h)[0]
            if math.isfinite(xyz[0]):
                out.append((float(xyz[0]), float(xyz[1])))
        return out

    def _parcel_match(self, c: ParcelMatchClaim) -> VerificationResult:
        """Rule a sighting out as parcel X when X's own scans put it somewhere else at that moment."""
        obs = [self._observation(o) for o in c.observation_ids]
        plan = latest_plan(self.store, self.site.site_id)
        net = ConveyorNet(plan) if plan else None
        timeline = scans_for(self.store, {f"carrier_waybill:{c.waybill}"}, site_id=self.site.site_id)
        scans = [ts for ts in (timeline.scans if timeline else []) if ts.scan.read_outcome == ReadOutcome.READ]
        if not scans:
            raise _fail(V.INSUFFICIENT_EVIDENCE, f"no scans of {c.waybill} at this site", checked_ids=c.observation_ids)
        def hhmm(ts) -> str:
            return ts.t.astimezone(obs[0].source_frame.normalized_utc.tzinfo).strftime("%H:%M:%S.%f")[:-5]

        for o in obs:
            t = o.source_frame.normalized_utc
            if t is None:
                continue
            t_ms = t.timestamp() * 1000
            where = self._sighting_xy(o)
            if not where:
                continue
            before = [ts for ts in scans if ts.t_ms <= t_ms]
            after = [ts for ts in scans if ts.t_ms >= t_ms]
            prev, nxt = (before[-1] if before else None), (after[0] if after else None)
            if prev and nxt and net and prev.synced and nxt.synced and                     {prev.scan.device_kind, nxt.scan.device_kind} <= ON_CONVEYANCE_DEVICES:  # fmt: skip
                gap = min(min((net.snap(p, max_dist=1e6) or (None, 0, math.inf))[2] for p in where), math.inf)
                if gap > BELT_MARGIN_M:
                    return VerificationResult(
                        V.CONTRADICTED, EvidenceLabel.CONTRADICTED,
                        [(f"the scans place {c.waybill} on the belt between {prev.scan.station_id or prev.scan.device_id} "
                          f"({hhmm(prev)}) and {nxt.scan.station_id or nxt.scan.device_id} ({hhmm(nxt)}); this sighting "
                          f"is {gap:.0f} m from any belt at that moment")],
                        ["rules out this parcel only; says nothing about which parcel it is"], c.observation_ids)  # fmt: skip
            for ts in scans:
                xy = scan_xy(plan, ts)
                if xy and ts.synced and abs(ts.t_ms - t_ms) <= STATION_WINDOW_S * 1000:
                    d = min(math.dist(xy, p) for p in where)
                    if d > STATION_MARGIN_M:
                        return VerificationResult(
                            V.CONTRADICTED, EvidenceLabel.CONTRADICTED,
                            [(f"{c.waybill} was scanned at {ts.scan.station_id or ts.scan.device_id} at {hhmm(ts)}, "
                              f"{d:.0f} m from this sighting")],
                            ["rules out this parcel only"], c.observation_ids)  # fmt: skip
        return VerificationResult(V.INSUFFICIENT_EVIDENCE, EvidenceLabel.HYPOTHESIZED,
                                  [f"the scans of {c.waybill} do not rule this sighting out"],
                                  ["not ruling out is not identification: that needs a scan or an unbroken track"],
                                  c.observation_ids)  # fmt: skip

    # --- consistency scan ---------------------------------------------------------------------------

    def consistency_conflicts(self, object_id: str) -> list[str]:
        """Pairs of confirmed observations of one object that cannot both be true (PRD §18.2)."""
        timed = object_evidence(self.store, object_id).timed
        out = []
        for i, a in enumerate(timed):
            for b in timed[i + 1:]:
                if b.t_ms - a.t_ms > 60_000:
                    break
                if a.obs.camera_id != b.obs.camera_id and (reason := self._physical(a.obs, b.obs)):
                    out.append(f"{a.obs.observation_id} vs {b.obs.observation_id}: {reason}")
        return out

    # --- writing decisions ---------------------------------------------------------------------------

    def decide(self, hypothesis_id: str, claims: list[StructuredClaim], *, now: datetime | None = None,
               unchecked_claims: int = 0) -> tuple[HypothesisStatus, list[VerificationResult]]:  # fmt: skip
        """Verify the claims that make up a hypothesis and record the decision as append-only status changes.

        `unchecked_claims` counts proposed claims that could not be verified at all (malformed, out of scope):
        a hypothesis is only SUPPORTED when every one of its claims was checked and supported."""
        now = now or datetime.now(UTC)
        results = [self.verify(c) for c in claims]
        if not claims:
            status = HypothesisStatus.INSUFFICIENT_EVIDENCE
        elif any(r.verdict == V.CONTRADICTED for r in results):
            status = HypothesisStatus.CONTRADICTED
        elif all(r.verdict == V.SUPPORTED for r in results) and not unchecked_claims:
            status = HypothesisStatus.SUPPORTED
        else:
            status = HypothesisStatus.INSUFFICIENT_EVIDENCE
        evidence = sorted({i for r in results for i in r.checked_ids if self.store.exists(i)
                           and not self.store.is_invalid(i)})  # fmt: skip
        if status in (HypothesisStatus.SUPPORTED, HypothesisStatus.CONTRADICTED) and not evidence:
            status = HypothesisStatus.INSUFFICIENT_EVIDENCE
        reason = "; ".join(f"{r.verdict.value}: {', '.join(r.reasons)}" for r in results) or "no checkable claims"
        if unchecked_claims:
            reason += f"; {unchecked_claims} proposed claim(s) could not be checked"
        current = self.store.hypothesis_status(hypothesis_id)
        if current != HypothesisStatus.EVALUATED:
            self.store.change_status(HypothesisStatusChange(
                change_id=new_id("status_change"), hypothesis_id=hypothesis_id, from_status=current,
                to_status=HypothesisStatus.EVALUATED, actor=VERIFIER, reason="verification started", at=now))
        self.store.change_status(HypothesisStatusChange(
            change_id=new_id("status_change"), hypothesis_id=hypothesis_id, from_status=HypothesisStatus.EVALUATED,
            to_status=status, actor=VERIFIER, evidence_ids=evidence, reason=reason[:2000], at=now))  # fmt: skip
        return status, results

    # --- deterministic wording ------------------------------------------------------------------------

    def _when(self, oid: str) -> str:
        o = self.store.get(RawObservation, oid)
        t = o.source_frame.normalized_utc
        return f"{t.isoformat(timespec='seconds') if t else 'unsynchronized time'} (camera {o.camera_id})"

    def _where(self, oid: str) -> str:
        e = estimate_for(self.store, oid)
        if e is None or (e.zone_id is None and e.floor_xy_m is None):
            return "an unmapped image position"
        if e.zone_id:
            return f"{self.zones[e.zone_id].name if e.zone_id in self.zones else e.zone_id} (estimated position)"
        return f"floor position ({e.floor_xy_m[0]:.1f} m, {e.floor_xy_m[1]:.1f} m) ±{e.uncertainty_radius_m:.1f} m"

    def describe(self, claim: StructuredClaim) -> str:
        """The finding statement, built only from verified fields: object, frames, times, mapped positions."""
        label = (self.store.get(ObjectInstance, claim.object_instance_id).label
                 if getattr(claim, "object_instance_id", None) and self.store.exists(claim.object_instance_id)
                 else "object")  # fmt: skip
        if isinstance(claim, LastSeenClaim):
            o = claim.observation_id
            return f"{label} last visibly confirmed at {self._when(o)}, at {self._where(o)}"
        if isinstance(claim, PresenceClaim):
            ids = sorted(claim.observation_ids, key=lambda i: self.store.get(RawObservation, i).source_frame.pts_ms)
            where = f", estimated in {self.zones[claim.zone_id].name}" if claim.zone_id in self.zones else ""
            return f"{label} visible in {len(ids)} cited frame(s) from {self._when(ids[0])} to {self._when(ids[-1])}" \
                + where  # fmt: skip
        if isinstance(claim, TransitionClaim):
            a, b = claim.from_observation_id, claim.to_observation_id
            return (f"{label} continuously tracked from {self._where(a)} at {self._when(a)} to {self._where(b)} at "
                    f"{self._when(b)}")
        if isinstance(claim, ExitClaim):
            door = self.zones[claim.door_zone_id].name
            ids = sorted(claim.observation_ids, key=lambda i: self.store.get(RawObservation, i).source_frame.pts_ms)
            return f"{label} seen at {door} and then beyond it, at {self._where(ids[-1])} at {self._when(ids[-1])}"
        if isinstance(claim, TransferClaim):
            ids = claim.observation_ids
            return (f"{label} moved with visible contact from {self._where(ids[0])} to {self._where(ids[-1])} "
                    f"between {self._when(ids[0])} and {self._when(ids[-1])}")
        return (f"observation at {self._when(claim.first_observation_id)} precedes observation at "
                f"{self._when(claim.second_observation_id)}")

    def promote(self, claim: StructuredClaim, result: VerificationResult, *, case_id: str,
                now: datetime | None = None) -> VerifiedFinding | None:  # fmt: skip
        """Store a VerifiedFinding only for a SUPPORTED claim with resolvable observations."""
        if result.verdict != V.SUPPORTED:
            return None
        obs_ids = [i for i in result.checked_ids if i.startswith("obs_")]
        if not obs_ids:
            return None
        sources = {self.store.get(RawObservation, o).source_type for o in obs_ids}
        status = FindingStatus.SUPPORTED_BY_VIDEO
        if sources & {SourceType.SENSOR_REAL} and SourceType.VIDEO in sources:
            status = FindingStatus.SUPPORTED_BY_VIDEO_AND_SENSOR
        elif SourceType.VIDEO not in sources:
            status = FindingStatus.SUPPORTED_BY_SENSOR
        return self.store.put(VerifiedFinding(
            finding_id=new_id("finding"), case_id=case_id, statement=self.describe(claim), observation_ids=obs_ids,
            spatial_estimate_ids=result.estimate_ids, verification_status=status, limitations=result.limitations,
            verified_by=VERIFIER, at=now or datetime.now(UTC),
        ))  # fmt: skip

