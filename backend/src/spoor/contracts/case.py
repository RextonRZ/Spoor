"""Cases, events, hypotheses, findings, status changes and revisions (PRD §11, §16, §17.4)."""

from typing import Annotated

from pydantic import AwareDatetime, Field, model_validator

from .base import (
    CameraId,
    CaseId,
    CaseRevisionId,
    EventId,
    FindingId,
    HypothesisId,
    ImmutableRecord,
    ObjectInstanceId,
    ObservationId,
    Record,
    SiteId,
    SpatialEstimateId,
    StatusChangeId,
    ZoneId,
)
from .enums import (
    DECIDED_STATUSES,
    HYPOTHESIS_TRANSITIONS,
    ActorKind,
    EvidenceLabel,
    FindingStatus,
    HypothesisStatus,
    ObjectVisibility,
)


class Actor(ImmutableRecord):
    kind: ActorKind
    id: str = Field(description="user id, agent role + request id, or service name")
    model: str | None = Field(default=None, description="Model id when kind == agent")

    @model_validator(mode="after")
    def _agent_names_model(self) -> "Actor":
        if self.kind == ActorKind.AGENT and not self.model:
            raise ValueError("agent actors must record the model that produced the output")
        return self


class TimeWindow(Record):
    start_utc: AwareDatetime
    end_utc: AwareDatetime

    @model_validator(mode="after")
    def _ordered(self) -> "TimeWindow":
        if self.end_utc < self.start_utc:
            raise ValueError("time window ends before it starts")
        return self


class Case(Record):
    case_id: CaseId
    site_id: SiteId
    question: str = Field(min_length=3, description="Investigator's question; data, not instructions to agents")
    target_description: str = Field(min_length=1, description="Concrete visual noun phrase, e.g. 'blue case'")
    camera_ids: list[CameraId] = []
    window: TimeWindow | None = None
    created_by: str
    created_at: AwareDatetime


class Event(ImmutableRecord):
    """A temporal state change or interaction backed by observations (PRD §11.1)."""

    event_id: EventId
    case_id: CaseId
    kind: str = Field(description="e.g. visibility_change, zone_change, contact, door_open")
    object_instance_id: ObjectInstanceId | None = None
    visibility: ObjectVisibility | None = None
    zone_id: ZoneId | None = None
    window: TimeWindow
    label: EvidenceLabel
    observation_ids: Annotated[list[ObservationId], Field(min_length=1)]
    spatial_estimate_ids: list[SpatialEstimateId] = []
    actor: Actor
    created_at: AwareDatetime


class Hypothesis(Record):
    """An explanation under investigation. Its status only changes through HypothesisStatusChange."""

    hypothesis_id: HypothesisId
    case_id: CaseId
    claim: str = Field(min_length=3)
    support_observation_ids: list[ObservationId] = []
    against_observation_ids: list[ObservationId] = []
    missing_evidence: list[str] = []
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    next_action: str | None = None
    proposed_by: Actor
    created_at: AwareDatetime


class HypothesisStatusChange(ImmutableRecord):
    """Append-only status transition with actor and evidence (PRD §11.3)."""

    change_id: StatusChangeId
    hypothesis_id: HypothesisId
    from_status: HypothesisStatus
    to_status: HypothesisStatus
    actor: Actor
    evidence_ids: list[ObservationId] = []
    reason: str = Field(min_length=3)
    at: AwareDatetime

    @model_validator(mode="after")
    def _legal(self) -> "HypothesisStatusChange":
        if self.to_status not in HYPOTHESIS_TRANSITIONS[self.from_status]:
            raise ValueError(f"illegal transition {self.from_status} -> {self.to_status}")
        if self.to_status in DECIDED_STATUSES and self.actor.kind not in (
            ActorKind.VERIFIER_SERVICE,
            ActorKind.HUMAN,
        ):
            raise ValueError("only the verifier service or a human may decide a hypothesis (PRD §11.3)")
        if self.to_status in (HypothesisStatus.SUPPORTED, HypothesisStatus.CONTRADICTED) and not self.evidence_ids:
            raise ValueError(f"{self.to_status} requires evidence")
        return self


class VerifiedFinding(ImmutableRecord):
    """A verified summary assertion — investigation support, not a legal finding (PRD §11.2, §22.3)."""

    finding_id: FindingId
    case_id: CaseId
    statement: str = Field(min_length=3)
    observation_ids: Annotated[list[ObservationId], Field(min_length=1)]
    spatial_estimate_ids: list[SpatialEstimateId] = []
    verification_status: FindingStatus
    limitations: list[str] = []
    verified_by: Actor
    at: AwareDatetime

    @model_validator(mode="after")
    def _not_agent_verified(self) -> "VerifiedFinding":
        if self.verified_by.kind not in (ActorKind.VERIFIER_SERVICE, ActorKind.HUMAN):
            raise ValueError("findings are set by the verifier service or a human, never an agent")
        return self


class CaseRevision(ImmutableRecord):
    """Immutable snapshot pointer: every change to case state produces a new revision (PRD §11.1)."""

    case_revision_id: CaseRevisionId
    case_id: CaseId
    parent_revision_id: CaseRevisionId | None
    actor: Actor
    reason: str
    changed_ids: list[str]
    at: AwareDatetime
