"""Typed agent tools (PRD §17.1-17.2). Tools are deterministic services; agents may only call them with validated
arguments inside the granted evidence scope. Results are plain data the agent reads as untrusted input."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from spoor.contracts import (
    Actor,
    ActorKind,
    Camera,
    Case,
    EvidenceScope,
    MediaAsset,
    ObjectInstance,
    RawObservation,
    Site,
    new_id,
)
from spoor.store import (
    EvidenceRequest,
    EvidenceStore,
    estimate_for,
    last_confirmed,
    transitions,
    unobserved_intervals,
    visibility_timeline,
)
from spoor.verification import CLAIM_ADAPTER, Verifier


class ScopeError(ValueError):
    pass


def iso(ms: float | None) -> str | None:
    return None if ms is None else datetime.fromtimestamp(ms / 1000, UTC).isoformat(timespec="milliseconds")


def parse_iso(value: str) -> float:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return dt.timestamp() * 1000


@dataclass
class ToolContext:
    store: EvidenceStore
    site: Site
    case: Case
    verifier: Verifier
    scope: EvidenceScope
    # Paid model calls are injected by the service layer (they need media storage and provider clients).
    run_sam: Callable[[str, str], dict] | None = None
    ask_spark: Callable[[str, float, float, str], dict] | None = None
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    agent_actor: Actor | None = None
    # J2b: evidence pictures for models that take images: (label, data URL, source sha256). Set by the service layer.
    key_frames: list[tuple[str, str, str]] = field(default_factory=list)

    # --- scope enforcement ----------------------------------------------------------------------
    def object(self, object_id: str) -> ObjectInstance:
        if not object_id.startswith("objinst_") or not self.store.exists(object_id):
            raise ScopeError(f"unknown object {object_id}")
        obj = self.store.get(ObjectInstance, object_id)
        if obj.case_id != self.case.case_id:
            raise ScopeError(f"{object_id} belongs to another case")
        if self.scope.object_instance_ids and object_id not in self.scope.object_instance_ids:
            raise ScopeError(f"{object_id} is outside the granted scope")
        return obj

    def camera_allowed(self, camera_id: str | None) -> None:
        if self.scope.camera_ids and camera_id not in self.scope.camera_ids:
            raise ScopeError(f"camera {camera_id} is outside the granted scope")

    def window_allowed(self, start_ms: float, end_ms: float) -> None:
        if end_ms < start_ms:
            raise ScopeError("window ends before it starts")
        w = self.scope.window
        if w and (start_ms < w.start_utc.timestamp() * 1000 - 1 or end_ms > w.end_utc.timestamp() * 1000 + 1):
            raise ScopeError("time window outside the granted scope")

    def observation(self, oid: str) -> RawObservation:
        if not oid.startswith("obs_") or not self.store.exists(oid):
            raise ScopeError(f"unknown observation {oid}")
        obs = self.store.get(RawObservation, oid)
        self.camera_on_site(obs.camera_id)
        self.camera_allowed(obs.camera_id)
        return obs

    def camera_on_site(self, camera_id: str | None) -> None:
        if camera_id is None or not self.store.exists(camera_id) or \
                self.store.get(Camera, camera_id).site_id != self.case.site_id:  # fmt: skip
            raise ScopeError(f"camera {camera_id} is not on this case's site")

    def media(self, media_id: str) -> MediaAsset:
        if not media_id.startswith("media_") or not self.store.exists(media_id):
            raise ScopeError(f"unknown media {media_id}")
        m = self.store.get(MediaAsset, media_id)
        if m.site_id != self.case.site_id:
            raise ScopeError(f"{media_id} is not on this case's site")
        self.camera_allowed(m.camera_id)
        return m


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoArgs(_Args):
    pass


class ObjectArgs(_Args):
    object_instance_id: str


class WindowArgs(_Args):
    object_instance_id: str
    start_iso: str
    end_iso: str


class ObservationArgs(_Args):
    observation_id: str


class SamArgs(_Args):
    media_id: str
    concept: str = Field(description="One short visual noun phrase, e.g. 'blue equipment case'")


class SparkArgs(_Args):
    media_id: str
    start_s: float = Field(ge=0)
    end_s: float = Field(gt=0)
    template: str = Field(description="presence_v1 | interaction_v1 | contradiction_v1 | next_evidence_v1")


class EvidenceRequestArgs(_Args):
    camera_id: str | None = None
    start_iso: str | None = None
    end_iso: str | None = None
    reason: str = Field(min_length=5)


class VerifyArgs(_Args):
    claim: dict[str, Any]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args: type[_Args]
    fn: Callable[[ToolContext, Any], dict]
    paid: bool = False


def _obs_summary(ctx: ToolContext, obs: RawObservation) -> dict:
    est = estimate_for(ctx.store, obs.observation_id)
    f = obs.source_frame
    return {
        "observation_id": obs.observation_id, "camera_id": obs.camera_id,
        "time": f.normalized_utc.isoformat(timespec="milliseconds") if f and f.normalized_utc else None,
        "time_uncertainty_ms": f.time_uncertainty_ms if f else None, "media_id": f.media_id if f else None,
        "frame_index": f.frame_index if f else None, "quality_flags": obs.quality_flags,
        "zone_id": est.zone_id if est else None, "spatial_mode": est.spatial_mode.value if est else "image_only",
    }  # fmt: skip


def t_list_objects(ctx: ToolContext, _: NoArgs) -> dict:
    objs = ctx.store.find(ObjectInstance, case_id=ctx.case.case_id)
    if ctx.scope.object_instance_ids:
        objs = [o for o in objs if o.object_instance_id in ctx.scope.object_instance_ids]
    return {"objects": [{"object_instance_id": o.object_instance_id, "label": o.label} for o in objs]}


def t_last_confirmed(ctx: ToolContext, a: ObjectArgs) -> dict:
    ctx.object(a.object_instance_id)
    ls = last_confirmed(ctx.store, a.object_instance_id)
    if ls.observation is None:
        return {"status": "never_confirmed", "unsynced_observation_ids": ls.unsynced_observation_ids}
    return {"status": "ok", "last": _obs_summary(ctx, ls.observation), "ambiguous_with": ls.ambiguous_with,
            "unsynced_observation_ids": ls.unsynced_observation_ids}  # fmt: skip


def t_timeline(ctx: ToolContext, a: ObjectArgs) -> dict:
    ctx.object(a.object_instance_id)
    spans = visibility_timeline(ctx.store, a.object_instance_id)
    return {"spans": [{
        "state": s.state.value, "start": iso(s.start_ms), "end": iso(s.end_ms), "camera_ids": s.camera_ids,
        "zone_id": s.zone_id, "n_observations": len(s.observation_ids),
        "first_observation_id": s.observation_ids[0] if s.observation_ids else None,
        "last_observation_id": s.observation_ids[-1] if s.observation_ids else None,
    } for s in spans]}  # fmt: skip


def t_unobserved(ctx: ToolContext, a: WindowArgs) -> dict:
    ctx.object(a.object_instance_id)
    start, end = parse_iso(a.start_iso), parse_iso(a.end_iso)
    ctx.window_allowed(start, end)
    gaps = unobserved_intervals(ctx.store, a.object_instance_id, start, end)
    return {"intervals": [{"start": iso(g.start_ms), "end": iso(g.end_ms), "reason": g.reason,
                           "covering_camera_ids": g.covering_camera_ids} for g in gaps]}  # fmt: skip


def t_transitions(ctx: ToolContext, a: ObjectArgs) -> dict:
    ctx.object(a.object_instance_id)
    return {"transitions": [{
        "from_zone": t.from_zone, "to_zone": t.to_zone, "from_observation_id": t.from_observation_id,
        "to_observation_id": t.to_observation_id, "start": iso(t.start_ms), "end": iso(t.end_ms),
        "label": t.label.value,
    } for t in transitions(ctx.store, a.object_instance_id)]}  # fmt: skip


def t_explain_spatial(ctx: ToolContext, a: ObservationArgs) -> dict:
    obs = ctx.observation(a.observation_id)
    est = estimate_for(ctx.store, obs.observation_id)
    if est is None:
        return {"spatial_mode": "image_only", "basis": "no valid spatial estimate for this observation"}
    return {"estimate_id": est.estimate_id, "spatial_mode": est.spatial_mode.value, "method": est.method,
            "floor_xy_m": est.floor_xy_m, "uncertainty_radius_m": est.uncertainty_radius_m, "zone_id": est.zone_id,
            "calibration_id": est.calibration_id, "status": est.status}  # fmt: skip


def t_run_sam(ctx: ToolContext, a: SamArgs) -> dict:
    ctx.media(a.media_id)
    if ctx.run_sam is None:
        return {"status": "analysis_unavailable", "reason": "perception service not configured"}
    return ctx.run_sam(a.media_id, a.concept)


def t_ask_spark(ctx: ToolContext, a: SparkArgs) -> dict:
    ctx.media(a.media_id)
    if a.end_s - a.start_s > 120:
        raise ScopeError("clip windows are limited to 120 s; ask about a narrower interval")
    if ctx.ask_spark is None:
        return {"status": "analysis_unavailable", "reason": "video reasoning service not configured"}
    return ctx.ask_spark(a.media_id, a.start_s, a.end_s, a.template)


def t_request_evidence(ctx: ToolContext, a: EvidenceRequestArgs) -> dict:
    if a.camera_id is not None:
        ctx.camera_on_site(a.camera_id)
    start = datetime.fromtimestamp(parse_iso(a.start_iso) / 1000, UTC) if a.start_iso else None
    end = datetime.fromtimestamp(parse_iso(a.end_iso) / 1000, UTC) if a.end_iso else None
    req = ctx.store.put(EvidenceRequest(
        evidence_request_id=new_id("evidence_request"), case_id=ctx.case.case_id, camera_id=a.camera_id,
        start_utc=start, end_utc=end, reason=a.reason,
        requested_by=ctx.agent_actor or Actor(kind=ActorKind.SYSTEM, id="orchestrator"), at=ctx.now(),
    ), check_refs=False)  # fmt: skip
    return {"status": "awaiting_authorized_import", "evidence_request_id": req.evidence_request_id,
            "note": "a human must authorize and import this footage; it is not fetched automatically"}


def t_verify(ctx: ToolContext, a: VerifyArgs) -> dict:
    claim = CLAIM_ADAPTER.validate_python(a.claim)
    r = ctx.verifier.verify(claim)
    return {"verdict": r.verdict.value, "label": r.label.value, "reasons": r.reasons, "limitations": r.limitations}


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("list_case_objects", "List the case's target objects.", NoArgs, t_list_objects),
    Tool("last_confirmed", "Latest visibly confirmed observation of an object.", ObjectArgs, t_last_confirmed),
    Tool("visibility_timeline", "Visible spans and out-of-view gaps for an object.", ObjectArgs, t_timeline),
    Tool("unobserved_intervals", "Intervals with no confirmation, and whether any camera was recording.",
         WindowArgs, t_unobserved),
    Tool("transitions", "Zone changes; 'observed' only within continuous tracking.", ObjectArgs, t_transitions),
    Tool("explain_spatial_basis", "How an observation's position was estimated.", ObservationArgs,
         t_explain_spatial),
    Tool("run_sam", "Segment/track a visual concept in one media clip (paid).", SamArgs, t_run_sam, paid=True),
    Tool("ask_spark", "Ask Muse Spark a bounded question about a clip window (paid).", SparkArgs, t_ask_spark,
         paid=True),
    Tool("request_evidence", "Ask a human to import a camera interval or sensor log.", EvidenceRequestArgs,
         t_request_evidence),
    Tool("verify_claim", "Run the deterministic verifier on a structured claim (read-only).", VerifyArgs, t_verify),
]}  # fmt: skip


def tool_catalog(names: list[str]) -> str:
    lines = []
    for n in names:
        t = TOOLS[n]
        schema = json.dumps(t.args.model_json_schema().get("properties", {}))
        lines.append(f"- {t.name}: {t.description} args={schema}")
    return "\n".join(lines)
