"""EvidenceStore: the only write path to case memory (PRD §16).

- Original/derived evidence is append-only (DB triggers abort UPDATE).
- Every write checks that referenced IDs exist, so dangling citations cannot enter memory (PRD §11.3).
- Hypothesis status is a projection of append-only status changes; the base hypothesis never mutates.
- Invalidation propagates along dependency edges instead of rewriting history (PRD §16.4).
"""

import json
import time
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel
from sqlalchemy import Engine, create_engine, delete, event, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from spoor.contracts import (
    Actor,
    ActorKind,
    CalibrationInvalidation,
    Camera,
    CameraCoverage,
    Case,
    CaseRevision,
    ClockDomain,
    ClockSync,
    ContainerMembership,
    Event,
    FloorCalibration,
    Hypothesis,
    HypothesisStatus,
    HypothesisStatusChange,
    IdentifierAlias,
    LegalContext,
    MediaAsset,
    MediaAuthorization,
    MultiView3DEstimate,
    ObjectInstance,
    RawObservation,
    ScanEvent,
    SearchOutcome,
    SearchTask,
    SensorEvent,
    Site,
    SitePlan,
    SpatialEstimate,
    Track,
    TrackAssociation,
    VerifiedFinding,
    VoiceTranscript,
    id_kind,
    new_id,
)

from . import db
from .records import (
    AgentStep,
    AuditEntry,
    CostEntry,
    EvidenceRequest,
    Invalidation,
    LiveAlert,
    ReportRecord,
    ScanHandshake,
)

M = TypeVar("M", bound=BaseModel)
SYSTEM = Actor(kind=ActorKind.SYSTEM, id="store")


class StoreError(ValueError):
    pass


class DanglingReference(StoreError):
    pass


class ConflictError(StoreError):
    """Optimistic-concurrency conflict: someone else changed the record first."""


def epoch_ms(dt: datetime | None) -> int | None:
    return None if dt is None else round(dt.timestamp() * 1000)


@dataclass(frozen=True)
class Spec:
    table: Any
    id_of: Callable[[Any], str]
    index: Callable[[Any], dict]
    refs: Callable[[Any], list[tuple[str, str]]] = lambda r: []


def _obs_refs(o: RawObservation) -> list[tuple[str, str]]:
    out = []
    if o.source_frame:
        out.append((o.source_frame.media_id, "source_media"))
    if o.track_id:
        out.append((o.track_id, "track"))
    if o.sensor_event_id:
        out.append((o.sensor_event_id, "sensor_event"))
    return out


SPECS: dict[type, Spec] = {
    Site: Spec(db.sites, lambda r: r.site_id, lambda r: {}),
    Camera: Spec(db.cameras, lambda r: r.camera_id, lambda r: {"site_id": r.site_id}, lambda r: [(r.site_id, "site")]),
    FloorCalibration: Spec(db.calibrations, lambda r: r.calibration_id, lambda r: {"camera_id": r.camera_id},
                           lambda r: [(r.camera_id, "camera")]),
    ClockSync: Spec(db.clock_syncs, lambda r: r.sync_id,
                    lambda r: {"camera_id": r.camera_id, "clock_domain_id": r.clock_domain_id},
                    lambda r: ([(r.camera_id, "camera")] if r.camera_id else [])
                    + ([(r.clock_domain_id, "clock_domain")] if r.clock_domain_id else [])),
    ClockDomain: Spec(db.clock_domains, lambda r: r.clock_domain_id, lambda r: {"site_id": r.site_id},
                      lambda r: [(r.site_id, "site")]),
    SitePlan: Spec(db.site_plans, lambda r: r.plan_id, lambda r: {"site_id": r.site_id},
                   lambda r: [(r.site_id, "site")]),
    LegalContext: Spec(db.legal_contexts, lambda r: r.legal_context_id, lambda r: {"site_id": r.site_id},
                       lambda r: [(r.site_id, "site")]),
    VoiceTranscript: Spec(db.voice_transcripts, lambda r: r.voice_transcript_id, lambda r: {"case_id": r.case_id},
                          lambda r: [(r.case_id, "case")]),
    SearchTask: Spec(db.search_tasks, lambda r: r.search_task_id, lambda r: {"case_id": r.case_id},
                     lambda r: [(r.case_id, "case")]),
    SearchOutcome: Spec(db.search_outcomes, lambda r: r.search_outcome_id,
                        lambda r: {"case_id": r.case_id, "search_task_id": r.search_task_id},
                        lambda r: [(r.case_id, "case"), (r.search_task_id, "search_task")]),
    ScanEvent: Spec(
        db.scan_events, lambda r: r.scan_event_id,
        lambda r: {"site_id": r.site_id, "event_kind": r.event_kind.value, "device_id": r.device_id,
                   "clock_domain_id": r.clock_domain_id, "container_key": r.container.key if r.container else None,
                   "t_device_ms": epoch_ms(r.device_time_utc), "corrects_id": r.corrects_scan_event_id},
        lambda r: [(r.site_id, "site")] + ([(r.clock_domain_id, "clock_domain")] if r.clock_domain_id else [])
        + [(m, "image") for m in r.image_refs]
        + ([(r.corrects_scan_event_id, "corrects")] if r.corrects_scan_event_id else []),
    ),
    ContainerMembership: Spec(
        db.memberships, lambda r: f"{r.membership_id}_v{r.version}",
        lambda r: {"membership_id": r.membership_id, "child_key": r.child_key, "parent_key": r.parent_key,
                   "version": r.version},
        lambda r: [(e, "scan") for e in (r.opened_by_event_id, r.closed_by_event_id) if e],
    ),
    IdentifierAlias: Spec(db.aliases, lambda r: r.alias_id, lambda r: {"from_key": r.from_key, "to_key": r.to_key},
                          lambda r: [(r.linked_by_event_id, "scan")] if r.linked_by_event_id else []),
    MediaAuthorization: Spec(db.authorizations, lambda r: r.authorization_id, lambda r: {"site_id": r.site_id}),
    MediaAsset: Spec(
        db.media, lambda r: r.media_id,
        lambda r: {"site_id": r.site_id, "camera_id": r.camera_id, "kind": r.kind.value,
                   "parent_id": r.parent_media_id, "sha256": r.sha256},
        lambda r: [(r.authorization_id, "authorization")]
        + ([(r.parent_media_id, "derived_from")] if r.parent_media_id else []),
    ),
    CameraCoverage: Spec(
        db.coverage, lambda r: r.coverage_id,
        lambda r: {"camera_id": r.camera_id, "media_id": r.media_id, "start_ms": epoch_ms(r.start_utc),
                   "end_ms": epoch_ms(r.end_utc)},
        lambda r: [(r.media_id, "media"), (r.sync_id, "sync")],
    ),
    Track: Spec(db.tracks, lambda r: r.track_id, lambda r: {"camera_id": r.camera_id, "media_id": r.media_id},
                lambda r: [(r.media_id, "media")]),
    RawObservation: Spec(
        db.observations, lambda r: r.observation_id,
        lambda r: {
            "camera_id": r.camera_id, "media_id": r.source_frame.media_id if r.source_frame else None,
            "track_id": r.track_id, "label": r.label, "source_type": r.source_type.value,
            "frame_index": r.source_frame.frame_index if r.source_frame else None,
            "pts_ms": r.source_frame.pts_ms if r.source_frame else None,
            "t_norm_ms": epoch_ms(r.source_frame.normalized_utc) if r.source_frame else None,
            "t_unc_ms": r.source_frame.time_uncertainty_ms if r.source_frame else None, "observed": r.observed,
        },
        _obs_refs,
    ),
    SpatialEstimate: Spec(
        db.estimates, lambda r: r.estimate_id,
        lambda r: {"spatial_mode": r.spatial_mode.value, "zone_id": r.zone_id, "calibration_id": r.calibration_id},
        lambda r: [(o, "observation") for o in r.observation_ids]
        + ([(r.calibration_id, "calibration")] if r.calibration_id else []),
    ),
    MultiView3DEstimate: Spec(
        db.estimates_xyz, lambda r: r.estimate_id, lambda r: {"correspondence_id": r.correspondence_id},
        lambda r: [(o, "observation") for o in r.source_observation_ids]
        + [(c, "calibration") for c in r.calibration_ids],
    ),
    SensorEvent: Spec(
        db.sensor_events, lambda r: r.sensor_event_id,
        lambda r: {"site_id": r.site_id, "kind": r.kind.value, "zone_id": r.zone_id,
                   "t_ms": epoch_ms(r.device_time_utc), "source_type": r.source_type.value},
        lambda r: [(r.site_id, "site")],
    ),
    ObjectInstance: Spec(db.object_instances, lambda r: r.object_instance_id, lambda r: {"case_id": r.case_id},
                         lambda r: [(r.case_id, "case")]),
    TrackAssociation: Spec(
        db.associations, lambda r: f"assoc_{r.object_instance_id}_{r.track_id}_v{r.version}",
        lambda r: {"object_instance_id": r.object_instance_id, "track_id": r.track_id, "status": r.status.value,
                   "version": r.version},
        lambda r: [(r.object_instance_id, "object"), (r.track_id, "track")],
    ),
    Case: Spec(db.cases, lambda r: r.case_id, lambda r: {"site_id": r.site_id}, lambda r: [(r.site_id, "site")]),
    CaseRevision: Spec(db.case_revisions, lambda r: r.case_revision_id,
                       lambda r: {"case_id": r.case_id, "parent_id": r.parent_revision_id},
                       lambda r: [(r.case_id, "case")]),
    Event: Spec(
        db.events, lambda r: r.event_id,
        lambda r: {"case_id": r.case_id, "object_instance_id": r.object_instance_id,
                   "start_ms": epoch_ms(r.window.start_utc), "end_ms": epoch_ms(r.window.end_utc),
                   "label": r.label.value},
        lambda r: [(r.case_id, "case")] + [(o, "observation") for o in r.observation_ids]
        + [(e, "estimate") for e in r.spatial_estimate_ids],
    ),
    Hypothesis: Spec(
        db.hypotheses, lambda r: r.hypothesis_id, lambda r: {"case_id": r.case_id},
        lambda r: [(r.case_id, "case")] + [(o, "supports") for o in r.support_observation_ids]
        + [(o, "against") for o in r.against_observation_ids],
    ),
    HypothesisStatusChange: Spec(
        db.status_changes, lambda r: r.change_id, lambda r: {"hypothesis_id": r.hypothesis_id},
        lambda r: [(r.hypothesis_id, "hypothesis")] + [(o, "evidence") for o in r.evidence_ids],
    ),
    VerifiedFinding: Spec(
        db.findings, lambda r: r.finding_id, lambda r: {"case_id": r.case_id},
        lambda r: [(r.case_id, "case")] + [(o, "observation") for o in r.observation_ids]
        + [(e, "estimate") for e in r.spatial_estimate_ids],
    ),
    EvidenceRequest: Spec(db.evidence_requests, lambda r: r.evidence_request_id, lambda r: {"case_id": r.case_id},
                          lambda r: [(r.case_id, "case")]),
    ReportRecord: Spec(db.reports, lambda r: r.report_id, lambda r: {"case_id": r.case_id},
                       lambda r: [(r.case_id, "case")]),
    Invalidation: Spec(db.invalidations, lambda r: r.invalidation_id, lambda r: {"target_id": r.target_id}),
    AuditEntry: Spec(db.audit, lambda r: r.audit_id, lambda r: {"target_id": r.target_id, "action": r.action}),
    CostEntry: Spec(db.cost_ledger, lambda r: r.cost_id, lambda r: {"case_id": r.case_id, "provider": r.provider}),
    LiveAlert: Spec(db.live_alerts, lambda r: r.alert_id, lambda r: {"site_id": r.site_id}),
    ScanHandshake: Spec(db.handshakes, lambda r: r.handshake_id,
                        lambda r: {"site_id": r.site_id, "waybill": r.waybill, "scan_event_id": r.scan_event_id}),
    AgentStep: Spec(db.agent_steps, lambda r: r.step_id,
                    lambda r: {"case_id": r.case_id, "request_id": r.request_id,
                               "idempotency_key": r.idempotency_key}),
}  # fmt: skip

# Which table an ID lives in, by its prefix kind (used for reference checks).
KIND_TABLE = {
    "site": db.sites, "camera": db.cameras, "calibration": db.calibrations, "sync": db.clock_syncs,
    "authorization": db.authorizations, "media": db.media, "coverage": db.coverage, "track": db.tracks,
    "observation": db.observations, "spatial_estimate": db.estimates, "multiview_estimate": db.estimates_xyz,
    "sensor_event": db.sensor_events, "object_instance": db.object_instances, "case": db.cases,
    "case_revision": db.case_revisions, "event": db.events, "hypothesis": db.hypotheses,
    "status_change": db.status_changes, "finding": db.findings, "evidence_request": db.evidence_requests,
    "report": db.reports, "scan_event": db.scan_events, "alias": db.aliases, "clock_domain": db.clock_domains,
    "site_plan": db.site_plans, "search_task": db.search_tasks, "search_outcome": db.search_outcomes,
    "legal_context": db.legal_contexts,
    "voice_transcript": db.voice_transcripts,
}  # fmt: skip
MODEL_BY_TABLE = {spec.table.name: model for model, spec in SPECS.items()}


class EvidenceStore:
    def __init__(self, url: str = "sqlite:///:memory:", *, engine: Engine | None = None):
        if engine is None:
            # In-memory SQLite: one shared connection so every thread sees the same database.
            kw = (
                {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
                if ":memory:" in url
                else {}
            )
            engine = create_engine(url, **kw)
        self.engine = engine
        self.writes = 0  # evidence writes in this process: read models cached against it are fresh while it is unchanged
        if self.engine.dialect.name == "sqlite":
            event.listen(self.engine, "connect", lambda conn, _: conn.execute("PRAGMA journal_mode=WAL"))
        db.metadata.create_all(self.engine)

    def _insert_ignore(self, table):
        """INSERT that skips rows whose primary key already exists (dependency edges are idempotent)."""
        if self.engine.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            return pg_insert(table).on_conflict_do_nothing()
        return insert(table).prefix_with("OR IGNORE", dialect="sqlite")

    @classmethod
    def sqlite_file(cls, path: Path) -> "EvidenceStore":
        path.parent.mkdir(parents=True, exist_ok=True)
        return cls(f"sqlite:///{path.as_posix()}")

    # --- generic write/read ------------------------------------------------------

    def put(self, record: M, *, check_refs: bool = True) -> M:
        with self.engine.begin() as c:
            self._write(c, record, check_refs=check_refs, known=set())
        return record

    def put_many(self, records: Iterable[BaseModel]) -> None:
        """Write a batch atomically (all or nothing). Each referenced ID is checked once, and records earlier in the
        batch count as existing — so a perception run's tracks, observations and estimates go in one transaction."""
        known: set[str] = set()
        with self.engine.begin() as c:
            for r in records:
                self._write(c, r, check_refs=True, known=known)

    def _exists_in(self, c, any_id: str) -> bool:
        table = KIND_TABLE.get(id_kind(any_id) or "")
        return (
            table is not None
            and c.execute(select(table.c.id).where(table.c.id == any_id)).first() is not None
        )

    def _write(self, c, record: BaseModel, *, check_refs: bool, known: set[str]) -> None:
        if not isinstance(record, AuditEntry):  # (reading a case writes an audit entry: that is not new evidence)
            self.writes += 1
        if isinstance(record, CalibrationInvalidation):
            raise StoreError("use invalidate_calibration()")
        spec = SPECS[type(record)]
        rid = spec.id_of(record)
        if isinstance(record, Hypothesis) and record.status != HypothesisStatus.PROPOSED:
            raise StoreError("hypotheses are stored as proposed; status changes go through change_status()")
        refs = spec.refs(record)
        if check_refs:
            missing = []
            for dst, _ in refs:
                if dst in known:
                    continue
                if self._exists_in(c, dst):
                    known.add(dst)
                else:
                    missing.append(dst)
            if missing:
                raise DanglingReference(f"{rid} references unknown ids: {missing}")
        row = {"id": rid, "seq": time.time_ns(), "payload": record.model_dump_json(), **spec.index(record)}
        if spec.table.info["immutable"]:
            try:
                with c.begin_nested():
                    c.execute(insert(spec.table).values(**row))
            except IntegrityError as e:
                raise StoreError(f"{rid} already exists and is immutable") from e
        elif c.execute(select(spec.table.c.id).where(spec.table.c.id == rid)).first():
            c.execute(update(spec.table).where(spec.table.c.id == rid).values(**row))
        else:
            c.execute(insert(spec.table).values(**row))
        for dst, rel in refs:
            c.execute(self._insert_ignore(db.refs).values(src_id=rid, dst_id=dst, rel=rel))
        if isinstance(record, ScanEvent):
            for key in dict.fromkeys(i.key for i in record.identifiers):
                c.execute(self._insert_ignore(db.scan_identifiers).values(scan_event_id=rid, key=key))
        known.add(rid)

    def exists(self, any_id: str) -> bool:
        table = KIND_TABLE.get(id_kind(any_id) or "")
        if table is None:
            return False
        with self.engine.connect() as c:
            return c.execute(select(table.c.id).where(table.c.id == any_id)).first() is not None

    def get(self, model: type[M], rid: str) -> M:
        table = SPECS[model].table
        with self.engine.connect() as c:
            row = c.execute(select(table.c.payload).where(table.c.id == rid)).first()
        if row is None:
            raise KeyError(rid)
        obj = model.model_validate_json(row[0])
        if isinstance(obj, Hypothesis):
            obj = obj.model_copy(update={"status": self.hypothesis_status(rid)})
        return obj

    def find(self, model: type[M], *, order: str = "seq", **where: Any) -> list[M]:
        table = SPECS[model].table
        q = select(table.c.payload)
        for col, val in where.items():
            q = q.where(table.c[col].in_(val) if isinstance(val, (list, tuple, set)) else table.c[col] == val)
        q = q.order_by(table.c[order], table.c.seq)
        with self.engine.connect() as c:
            out = [model.model_validate_json(p) for (p,) in c.execute(q)]
        if model is Hypothesis:
            out = [h.model_copy(update={"status": self.hypothesis_status(h.hypothesis_id)}) for h in out]
        return out

    def referrers(self, dst_id: str, rel: str | None = None) -> list[str]:
        q = select(db.refs.c.src_id).where(db.refs.c.dst_id == dst_id)
        if rel:
            q = q.where(db.refs.c.rel == rel)
        with self.engine.connect() as c:
            return [r for (r,) in c.execute(q)]

    def scan_ids_for_keys(self, keys: Iterable[str]) -> list[str]:
        """IDs of scan events carrying any of these identifier keys ('<scheme>:<value>')."""
        keys = list(dict.fromkeys(keys))
        if not keys:
            return []
        with self.engine.connect() as c:
            rows = c.execute(
                select(db.scan_identifiers.c.scan_event_id).where(db.scan_identifiers.c.key.in_(keys))
            )
            return list(dict.fromkeys(r for (r,) in rows))

    def get_many(self, model: type[M], ids: Iterable[str]) -> list[M]:
        table = SPECS[model].table
        ids = list(dict.fromkeys(ids))
        out: list[M] = []
        with self.engine.connect() as c:
            for i in range(0, len(ids), 500):
                rows = c.execute(select(table.c.payload).where(table.c.id.in_(ids[i : i + 500])))
                out += [model.model_validate_json(p) for (p,) in rows]
        return out

    def latest_estimates(self, observation_ids: Iterable[str]) -> dict[str, SpatialEstimate]:
        """Most recent valid floor/zone estimate per observation, in a few batched queries (not one per observation)."""
        ids = list(dict.fromkeys(observation_ids))
        if not ids:
            return {}
        invalid = self.invalid_ids()
        pairs: list[tuple[str, str]] = []
        with self.engine.connect() as c:
            for i in range(0, len(ids), 500):
                q = select(db.refs.c.src_id, db.refs.c.dst_id).where(
                    db.refs.c.dst_id.in_(ids[i:i + 500]), db.refs.c.rel == "observation",
                    db.refs.c.src_id.like("loc\\_%", escape="\\"))  # fmt: skip
                pairs += [(s, d) for s, d in c.execute(q) if s not in invalid]
            est_ids = list({s for s, _ in pairs})
            payloads: dict[str, SpatialEstimate] = {}
            for i in range(0, len(est_ids), 500):
                q = select(db.estimates.c.id, db.estimates.c.payload).where(
                    db.estimates.c.id.in_(est_ids[i : i + 500])
                )
                payloads |= {rid: SpatialEstimate.model_validate_json(p) for rid, p in c.execute(q)}
        out: dict[str, SpatialEstimate] = {}
        for est_id, obs_id in pairs:
            est = payloads.get(est_id)
            if est and (obs_id not in out or est.created_at > out[obs_id].created_at):
                out[obs_id] = est
        return out

    # --- hypotheses ------------------------------------------------------------------

    def hypothesis_status(self, hypothesis_id: str) -> HypothesisStatus:
        changes = self.find(HypothesisStatusChange, hypothesis_id=hypothesis_id)
        return changes[-1].to_status if changes else HypothesisStatus.PROPOSED

    def status_history(self, hypothesis_id: str) -> list[HypothesisStatusChange]:
        return self.find(HypothesisStatusChange, hypothesis_id=hypothesis_id)

    def change_status(self, change: HypothesisStatusChange) -> HypothesisStatusChange:
        self.writes += 1
        current = self.hypothesis_status(change.hypothesis_id)
        if change.from_status != current:
            raise ConflictError(f"{change.hypothesis_id} is {current}, not {change.from_status}")
        invalid = [e for e in change.evidence_ids if self.is_invalid(e)]
        if invalid:
            raise StoreError(f"cannot decide on invalidated evidence: {invalid}")
        return self.put(change)

    def change_status_chain(self, changes: list[HypothesisStatusChange]) -> None:
        """Several consecutive status changes, all or nothing."""
        self.writes += 1
        if not changes:
            return
        current = self.hypothesis_status(changes[0].hypothesis_id)
        for ch in changes:
            if ch.from_status != current:
                raise ConflictError(f"{ch.hypothesis_id} is {current}, not {ch.from_status}")
            if invalid := [e for e in ch.evidence_ids if self.is_invalid(e)]:
                raise StoreError(f"cannot decide on invalidated evidence: {invalid}")
            current = ch.to_status
        self.put_many(changes)

    # --- revisions (optimistic concurrency) ------------------------------------------

    def head_revision(self, case_id: str) -> CaseRevision | None:
        revs = self.find(CaseRevision, case_id=case_id)
        return revs[-1] if revs else None

    def append_revision(self, case_id: str, *, expected_parent: str | None, actor: Actor, reason: str,
                        changed_ids: list[str], now: datetime) -> CaseRevision:  # fmt: skip
        self.writes += 1
        head = self.head_revision(case_id)
        head_id = head.case_revision_id if head else None
        if head_id != expected_parent:
            raise ConflictError(f"case {case_id} head is {head_id}, expected {expected_parent}")
        rev = CaseRevision(case_revision_id=new_id("case_revision"), case_id=case_id, parent_revision_id=head_id,
                           actor=actor, reason=reason, changed_ids=changed_ids, at=now)  # fmt: skip
        return self.put(rev)

    # --- invalidation ------------------------------------------------------------------

    def invalid_ids(self) -> set[str]:
        with self.engine.connect() as c:
            return {t for (t,) in c.execute(select(db.invalidations.c.target_id))}

    def is_invalid(self, rid: str) -> bool:
        with self.engine.connect() as c:
            return c.execute(select(db.invalidations.c.id).where(db.invalidations.c.target_id == rid)).first() \
                is not None  # fmt: skip

    def invalidate(self, target_id: str, *, reason: str, actor: Actor, now: datetime) -> list[str]:
        """Invalidate `target_id` and everything derived from or citing it. Returns all invalidated ids."""
        self.writes += 1
        already = self.invalid_ids()
        root = Invalidation(invalidation_id=new_id("invalidation"), target_id=target_id, reason=reason, actor=actor,
                            at=now)  # fmt: skip
        done: list[str] = []
        if target_id not in already:
            self.put(root, check_refs=False)
            done.append(target_id)
            already.add(target_id)
        queue = deque([target_id])
        while queue:
            current = queue.popleft()
            for src in self.referrers(current):
                if src in already or id_kind(src) in ("case", "site", "camera"):
                    continue
                self.put(Invalidation(invalidation_id=new_id("invalidation"), target_id=src,
                                      reason=f"depends on invalidated {current}", cause_id=root.invalidation_id,
                                      actor=actor, at=now), check_refs=False)  # fmt: skip
                already.add(src)
                done.append(src)
                queue.append(src)
        self.audit(actor, "invalidate", target_id, {"reason": reason, "affected": done}, now)
        return done

    def invalidate_calibration(self, inv: CalibrationInvalidation, now: datetime) -> list[str]:
        self.writes += 1
        actor = Actor(kind=ActorKind.HUMAN, id=inv.invalidated_by)
        return self.invalidate(inv.calibration_id, reason=inv.reason, actor=actor, now=now)

    # --- deletion (retention / right to delete) -----------------------------------------

    def purge_media(self, media_id: str, *, actor: Actor, reason: str, now: datetime) -> list[str]:
        """Delete a source and everything derived from it; case records citing it are invalidated, not deleted.

        Returns the sha256 of every media asset whose bytes the caller must now delete from object storage.
        """
        self.writes += 1
        media_ids = [media_id]
        i = 0
        while i < len(media_ids):
            media_ids += [s for s in self.referrers(media_ids[i], "derived_from") if s not in media_ids]
            i += 1
        assets = [self.get(MediaAsset, m) for m in media_ids]
        obs_ids = [s for m in media_ids for s in self.referrers(m, "source_media")]
        track_ids = [s for m in media_ids for s in self.referrers(m, "media") if id_kind(s) == "track"]
        cov_ids = [s for m in media_ids for s in self.referrers(m, "media") if id_kind(s) == "coverage"]
        est_ids = sorted({s for o in obs_ids for s in self.referrers(o, "observation")
                          if id_kind(s) in ("spatial_estimate", "multiview_estimate")})  # fmt: skip
        for m in media_ids:
            self.invalidate(m, reason=f"source deleted: {reason}", actor=actor, now=now)
        doomed = [*est_ids, *obs_ids, *track_ids, *cov_ids, *media_ids]
        with self.engine.begin() as c:
            for table in (db.estimates, db.estimates_xyz, db.observations, db.tracks, db.coverage, db.media):
                c.execute(delete(table).where(table.c.id.in_(doomed)))
            c.execute(delete(db.refs).where(db.refs.c.src_id.in_(doomed)))
        self.audit(actor, "purge_media", media_id, {"reason": reason, "deleted": doomed}, now)
        return [a.sha256 for a in assets]

    def delete_case(self, case_id: str, *, actor: Actor, now: datetime) -> None:
        """Delete case-scoped records. Audit entries are kept (IDs only) as the documented exception (§7.1)."""
        self.writes += 1
        objects = [o.object_instance_id for o in self.find(ObjectInstance, case_id=case_id)]
        hyps = [h.hypothesis_id for h in self.find(Hypothesis, case_id=case_id)]
        with self.engine.begin() as c:
            c.execute(delete(db.associations).where(db.associations.c.object_instance_id.in_(objects)))
            c.execute(delete(db.status_changes).where(db.status_changes.c.hypothesis_id.in_(hyps)))
            for t in (db.object_instances, db.case_revisions, db.events, db.hypotheses, db.findings,
                      db.evidence_requests, db.reports, db.agent_steps):  # fmt: skip
                c.execute(delete(t).where(t.c.case_id == case_id))
            c.execute(delete(db.cases).where(db.cases.c.id == case_id))
        self.audit(actor, "delete_case", case_id, {}, now)

    # --- operations ---------------------------------------------------------------------

    def audit(self, actor: Actor, action: str, target_id: str | None, detail: dict, now: datetime) -> None:
        self.put(AuditEntry(audit_id=new_id("audit"), actor=actor, action=action, target_id=target_id,
                            detail=json.loads(json.dumps(detail, default=str)), at=now), check_refs=False)  # fmt: skip

    def record_cost(self, entry: CostEntry) -> CostEntry:
        return self.put(entry, check_refs=False)

    def checkpoint(self, step: AgentStep) -> AgentStep:
        return self.put(step, check_refs=False)

    def step_by_key(self, idempotency_key: str) -> AgentStep | None:
        steps = self.find(AgentStep, idempotency_key=idempotency_key)
        results = [s for s in steps if s.kind == "tool_result"]
        return results[-1] if results else None


def utcnow() -> datetime:
    return datetime.now(UTC)
