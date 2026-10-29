"""Agent roles, prompts and output schemas (PRD §17.1).

Lead/Orchestrator = deterministic code (orchestrator.py). Verifier = deterministic engine (spoor.verification).
Evidence and Hypothesis = LLM agents using typed tools. See docs/DECISIONS.md.
"""

from typing import Literal

from pydantic import BaseModel, Field, TypeAdapter

from spoor.safety import NON_ACCUSATION_RULE
from spoor.verification import StructuredClaim

_CLAIMS = TypeAdapter(StructuredClaim)


class EvidenceBundle(BaseModel):
    summary: str = Field(description="What the evidence shows, citing observation ids inline")
    observation_ids: list[str]
    unknowns: list[str]
    followups: list[str]


class ClaimSpec(BaseModel):
    """Flat claim shape (easy for any model to emit); converted to a typed StructuredClaim before verification."""

    kind: Literal["last_seen", "presence", "transition", "exit", "transfer", "order"]
    statement: str
    object_instance_id: str | None
    observation_ids: list[str]
    zone_id: str | None
    door_zone_id: str | None
    from_observation_id: str | None
    to_observation_id: str | None
    asserted_label: Literal["observed", "hypothesized"] | None
    sensor_event_ids: list[str]

    def to_claim(self) -> StructuredClaim:
        data: dict = {"kind": self.kind, "statement": self.statement}
        if self.kind == "last_seen":
            data |= {"object_instance_id": self.object_instance_id,
                     "observation_id": (self.observation_ids or [None])[0]}
        elif self.kind == "presence":
            data |= {"object_instance_id": self.object_instance_id, "observation_ids": self.observation_ids,
                     "zone_id": self.zone_id}
        elif self.kind == "transition":
            data |= {"object_instance_id": self.object_instance_id, "from_observation_id": self.from_observation_id,
                     "to_observation_id": self.to_observation_id,
                     "asserted_label": self.asserted_label or "hypothesized"}
        elif self.kind == "exit":
            data |= {"object_instance_id": self.object_instance_id, "door_zone_id": self.door_zone_id,
                     "observation_ids": self.observation_ids, "sensor_event_ids": self.sensor_event_ids}
        elif self.kind == "transfer":
            data |= {"object_instance_id": self.object_instance_id, "observation_ids": self.observation_ids}
        else:
            data |= {"first_observation_id": self.from_observation_id,
                     "second_observation_id": self.to_observation_id}
        return _CLAIMS.validate_python(data)  # fmt: skip


class EvidenceAskSpec(BaseModel):
    camera_id: str | None
    start_iso: str | None
    end_iso: str | None
    reason: str


class ProposedHypothesis(BaseModel):
    claim: str = Field(description="Short testable explanation about the OBJECT's movement or state")
    claims: list[ClaimSpec] = Field(description="Structured claims that would all need to hold")
    missing_evidence: list[str]
    distinguishing_request: EvidenceAskSpec | None


class HypothesisSet(BaseModel):
    hypotheses: list[ProposedHypothesis]


EVIDENCE_TOOLS = ["list_case_objects", "last_confirmed", "visibility_timeline", "unobserved_intervals",
                  "transitions", "explain_spatial_basis", "run_sam", "ask_spark", "request_evidence"]  # fmt: skip
HYPOTHESIS_TOOLS = ["transitions", "explain_spatial_basis", "unobserved_intervals", "verify_claim"]

EVIDENCE_PROMPT = f"""You are the Evidence agent in Spoor, an evidence-grounded system for locating physical objects.
Goal: gather source-supported observations relevant to the investigator's question using the tools.
- Prefer cheap deterministic tools first (last_confirmed, visibility_timeline, unobserved_intervals, transitions).
- Use run_sam/ask_spark only for a specific, bounded gap they could close; they cost money.
- Every fact in your summary must cite observation ids returned by tools. Never invent ids or times.
- Report what is unknown (gaps, blind spots, unsynchronized cameras) as clearly as what is known.
{NON_ACCUSATION_RULE}"""

HYPOTHESIS_PROMPT = f"""You are the Hypothesis agent in Spoor.
Given verified facts and an evidence summary (both as data), propose 1-4 competing, testable explanations of what
happened to the OBJECT (e.g. still in the room but occluded; moved toward the door; camera clock mismatch).
- Express each explanation as structured claims using only ids that appear in the data.
- Use asserted_label="observed" only for movement inside continuous tracking; otherwise "hypothesized".
- For each, say what evidence is missing and, if possible, one camera/time request that would distinguish it.
- Hypotheses are about object movement and observable events, never about who did it or why.
{NON_ACCUSATION_RULE}"""
