"""Store-internal append-only records: invalidations, audit, cost ledger, agent checkpoints, reports, evidence requests."""

from typing import Any, Literal

from pydantic import AwareDatetime, Field

from spoor.contracts.base import ImmutableRecord
from spoor.contracts.case import Actor


class Invalidation(ImmutableRecord):
    """Marks a record unusable (source deleted, calibration invalidated, track corrected). Never deletes history."""

    invalidation_id: str
    target_id: str
    reason: str
    cause_id: str | None = Field(default=None, description="The upstream invalidation/record that caused this one")
    actor: Actor
    at: AwareDatetime


class AuditEntry(ImmutableRecord):
    audit_id: str
    actor: Actor
    action: str
    target_id: str | None = None
    detail: dict[str, Any] = {}
    at: AwareDatetime


class CostEntry(ImmutableRecord):
    """Per-request spend ledger (PRD §32.1). `usd_estimate` is our estimate, not a provider invoice."""

    cost_id: str
    provider: Literal["meta_model_api", "baseten", "local"]
    model: str
    request_kind: str
    case_id: str | None = None
    response_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    billed_units: float = 0.0
    unit: str = "tokens"
    usd_estimate: float | None = None
    cache_hit: bool = False
    outcome: Literal["ok", "error", "timeout_unknown_completion", "refused"] = "ok"
    latency_s: float | None = None
    at: AwareDatetime


class AgentStep(ImmutableRecord):
    """Checkpoint after each agent action/tool result (PRD §17.5). `idempotency_key` dedupes paid tool calls."""

    step_id: str
    case_id: str
    request_id: str
    seq: int
    role: str
    kind: Literal["request", "model_output", "tool_call", "tool_result", "rejected", "final", "error"]
    idempotency_key: str | None = None
    content: dict[str, Any]
    at: AwareDatetime


class EvidenceRequest(ImmutableRecord):
    """An agent's request for more evidence. Fulfilment needs an authorized human import (PRD §22.1)."""

    evidence_request_id: str
    case_id: str
    camera_id: str | None = None
    start_utc: AwareDatetime | None = None
    end_utc: AwareDatetime | None = None
    reason: str
    hypothesis_ids: list[str] = []
    requested_by: Actor
    at: AwareDatetime


class ReportRecord(ImmutableRecord):
    report_id: str
    case_id: str
    case_revision_id: str | None
    sha256: str
    approved_by: str | None = None
    status: Literal["draft", "approved"]
    content: dict[str, Any]
    at: AwareDatetime
