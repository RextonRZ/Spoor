"""Agent roles, prompts and output schemas (PRD §17.1).

Lead/Orchestrator = deterministic code (orchestrator.py). Verifier = deterministic engine (spoor.verification).
Evidence and Hypothesis = LLM agents using typed tools. See docs/DECISIONS.md.
"""

from typing import Literal

from pydantic import BaseModel, Field, TypeAdapter

from spoor.safety import NON_ACCUSATION_RULE
from spoor.verification import StructuredClaim
from spoor.verification.claims import normalize_claim

_CLAIMS = TypeAdapter(StructuredClaim)


class EvidenceBundle(BaseModel):
    summary: str = Field(description="What the evidence shows, citing observation ids inline")
    observation_ids: list[str]
    unknowns: list[str]
    followups: list[str]


class ClaimSpec(BaseModel):
    """Flat claim shape (easy for any model to emit); converted to a typed StructuredClaim before verification."""

    kind: Literal["last_seen", "presence", "transition", "exit", "transfer", "order", "parcel_match", "stayed_in_area"]
    statement: str
    object_instance_id: str | None
    observation_ids: list[str]
    zone_id: str | None
    door_zone_id: str | None
    from_observation_id: str | None
    to_observation_id: str | None
    asserted_label: Literal["observed", "hypothesized"] | None
    sensor_event_ids: list[str]
    observation_id: str | None = Field(default=None, description="last_seen / stayed_in_area: the ONE observation id "
                                       "(the object's last confirmed observation)")
    area_id: str | None = Field(default=None, description="stayed_in_area: a site-plan area or zone id")
    waybill: str | None = Field(default=None, description="parcel_match: the parcel the sighting would be")

    def _one_observation(self) -> str | None:
        """The single id a last_seen / stayed_in_area claim cites, wherever the model put it."""
        return self.observation_id or (self.observation_ids[0] if len(self.observation_ids) == 1 else None) \
            or self.to_observation_id  # fmt: skip

    def to_claim(self) -> StructuredClaim:
        data: dict = {"kind": self.kind, "statement": self.statement}
        if self.kind == "last_seen":
            data |= {"object_instance_id": self.object_instance_id, "observation_id": self._one_observation()}
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
        elif self.kind == "parcel_match":
            data |= {"observation_ids": self.observation_ids, "waybill": self.waybill}
        elif self.kind == "stayed_in_area":
            data |= {"object_instance_id": self.object_instance_id, "area_id": self.area_id,
                     "observation_id": self._one_observation()}
        else:
            data |= {"first_observation_id": self.from_observation_id,
                     "second_observation_id": self.to_observation_id}
        return _CLAIMS.validate_python(normalize_claim(data))  # fmt: skip


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


EVIDENCE_TOOLS = ["list_case_objects", "scan_history", "footage_for", "last_confirmed", "visibility_timeline",
                  "unobserved_intervals", "transitions", "explain_spatial_basis", "run_sam", "ask_spark",
                  "door_crossings", "carrier_check", "request_evidence"]  # fmt: skip
HYPOTHESIS_TOOLS = ["transitions", "explain_spatial_basis", "unobserved_intervals", "door_crossings", "carrier_check",
                    "verify_claim"]

EVIDENCE_PROMPT = f"""You are the Evidence agent in Spoor, an evidence-grounded system for locating physical objects.
Goal: gather source-supported observations relevant to the investigator's question using the tools.
- Prefer cheap deterministic tools first (last_confirmed, visibility_timeline, unobserved_intervals, transitions).
- Use run_sam/ask_spark only for a specific, bounded gap they could close; they cost money.
- Start from scan_history: the last scan says where the object was left. footage_for gives the clips of the cameras
  that see that scan point. Aim run_sam with the scan record: scan_point_id + the camera that sees it + a short window. The last scan before a
  gap is the anchor (e.g. a cage scan: keep the carton that leaves the cage bays); never ask for "box" on a whole clip.
- If the question comes with a lead_plan (the lead investigator's plan), follow its steps in order unless a tool shows
  a step is impossible; say which steps you did.
- If the object was last seen at the edge of an area no camera sees inside (a store room, a blind corner): run_sam
  with concept 'person' on the camera watching its doorway, then door_crossings and carrier_check.
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
- Claim kinds for verify_claim: last_seen {{object_instance_id, observation_id}}; presence {{object_instance_id,
  observation_ids, zone_id}}; transition; exit {{object_instance_id, door_zone_id, observation_ids}}; transfer; order;
  parcel_match {{observation_ids, waybill}} (rules a sighting out as another parcel); stayed_in_area
  {{object_instance_id, area_id, observation_id}} (inside an area no camera sees: last seen at its edge, carried in,
  never seen again until the recording ends). Send only the fields of the kind you use.
{NON_ACCUSATION_RULE}"""
