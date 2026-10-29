"""Agent request/response envelopes (PRD §17.2). Agents propose; they never set verification status."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, model_validator

from .base import AgentRequestId, CameraId, CaseId, ObjectInstanceId, Record
from .case import TimeWindow
from .enums import AgentRole


class EvidenceScope(Record):
    camera_ids: list[CameraId] = []
    window: TimeWindow | None = None
    object_instance_ids: list[ObjectInstanceId] = []


class AgentRequest(Record):
    case_id: CaseId
    request_id: AgentRequestId
    role: AgentRole
    question: str
    evidence_scope: EvidenceScope
    available_tools: list[str]
    token_budget: int = Field(gt=0)
    max_steps: int = Field(gt=0, le=50)
    deadline: AwareDatetime
    output_schema: str


class Claim(Record):
    """`observation` claims must cite evidence; `hypothesis` claims are explicitly unverified."""

    kind: Literal["observation", "hypothesis"]
    text: str = Field(min_length=1)
    evidence_ids: list[str] = []

    @model_validator(mode="after")
    def _observations_cite(self) -> "Claim":
        if self.kind == "observation" and not self.evidence_ids:
            raise ValueError("an observation claim must cite evidence ids")
        return self


class AgentCost(Record):
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
    usd_estimate: float | None = None


class AgentResponse(Record):
    request_id: AgentRequestId
    status: Literal["ok", "abstained", "budget_exhausted", "error"]
    claims: list[Claim] = []
    evidence_ids: list[str] = []
    unknowns: list[str] = []
    conflicts: list[str] = []
    recommended_next_tool: str | None = None
    abstain_reason: str | None = None
    cost: AgentCost
    model_version: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def _abstain_has_reason(self) -> "AgentResponse":
        if self.status == "abstained" and not self.abstain_reason:
            raise ValueError("an abstention must say why")
        return self
