"""Shared base classes and typed IDs for the canonical evidence contract (PRD §11)."""

import secrets
import time
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


class Record(BaseModel):
    """Mutable-by-replacement record; unknown fields are rejected so typos never pass silently."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ImmutableRecord(Record):
    """Source-of-truth records (originals, raw observations, audit entries) are frozen once created (PRD §7.3)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)


# Every ID carries a type prefix so an observation ID can never be passed where a zone ID is expected (PRD §11.3).
ID_PREFIXES = {
    "site": "site",
    "floor": "floor",
    "zone": "zone",
    "camera": "cam",
    "calibration": "calib",
    "sync": "sync",
    "authorization": "auth",
    "media": "media",
    "track": "trk",
    "observation": "obs",
    "object_instance": "objinst",
    "spatial_estimate": "loc",
    "multiview_estimate": "xyz",
    "correspondence": "corr",
    "sensor_event": "sens",
    "case": "case",
    "event": "evt",
    "hypothesis": "hyp",
    "finding": "finding",
    "case_revision": "rev",
    "status_change": "chg",
    "agent_request": "req",
    "coverage": "cov",
    "association": "assoc",
    "invalidation": "inv",
    "audit": "audit",
    "ledger": "cost",
    "agent_step": "step",
    "report": "report",
    "evidence_request": "evreq",
    "job": "job",
    "scan_event": "scan",
    "membership": "cmem",
    "alias": "alias",
    "clock_domain": "clkd",
    "site_plan": "plan",
    "search_task": "srch",
    "search_outcome": "sout",
    "legal_context": "lctx",
    "voice_transcript": "vtr",
    "reel": "reel",
}


def _id_type(prefix: str):
    return Annotated[str, StringConstraints(pattern=rf"^{prefix}_[A-Za-z0-9][A-Za-z0-9_-]*$", max_length=96)]


SiteId = _id_type("site")
FloorId = _id_type("floor")
ZoneId = _id_type("zone")
CameraId = _id_type("cam")
CalibrationId = _id_type("calib")
SyncId = _id_type("sync")
AuthorizationId = _id_type("auth")
MediaId = _id_type("media")
TrackId = _id_type("trk")
ObservationId = _id_type("obs")
ObjectInstanceId = _id_type("objinst")
SpatialEstimateId = _id_type("loc")
MultiViewEstimateId = _id_type("xyz")
CorrespondenceId = _id_type("corr")
SensorEventId = _id_type("sens")
CaseId = _id_type("case")
EventId = _id_type("evt")
HypothesisId = _id_type("hyp")
FindingId = _id_type("finding")
CaseRevisionId = _id_type("rev")
StatusChangeId = _id_type("chg")
AgentRequestId = _id_type("req")

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


def new_id(kind: str) -> str:
    """Server-side ID generation: time-ordered and collision-resistant. Models never mint IDs."""
    prefix = ID_PREFIXES[kind]
    return f"{prefix}_{time.time_ns():x}{secrets.token_hex(4)}"


def id_kind(value: str) -> str | None:
    """Return the entity kind for an ID string, or None if the prefix is unknown."""
    prefix = value.split("_", 1)[0]
    return next((k for k, p in ID_PREFIXES.items() if p == prefix), None)
