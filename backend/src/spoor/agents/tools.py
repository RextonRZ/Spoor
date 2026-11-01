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
    CameraCoverage,
    Case,
    EvidenceScope,
    FloorCalibration,
    MediaAsset,
    ObjectInstance,
    RawObservation,
    ReadOutcome,
    Site,
    Track,
    new_id,
)
from spoor.forensics.handover import area_crossings, area_polygon, blind_areas_near, carrier_fit, floor_path
from spoor.forensics.journey import latest_plan
from spoor.store import (
    EvidenceRequest,
    EvidenceStore,
    estimate_for,
    last_confirmed,
    latest_associations,
    transitions,
    unobserved_intervals,
    visibility_timeline,
)
from spoor.store.parcels import object_keys, scans_for
from spoor.verification import CLAIM_ADAPTER, Verifier
from spoor.verification.claims import normalize_claim


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
    run_sam: Callable[..., dict] | None = None
    ask_spark: Callable[..., dict] | None = None
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    agent_actor: Actor | None = None
    # J2b: evidence pictures for models that take images: (label, data URL, source sha256). Set by the service layer.
    key_frames: list[tuple[str, str, str]] = field(default_factory=list)
    # every finished tool call, as {"role", "tool", "args", "result", "status"} (the live run screen); never fails a run
    on_step: Callable[[dict], None] | None = None

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

    def verifier_calibration(self, camera_id: str) -> FloorCalibration | None:
        cals = [c for c in self.store.find(FloorCalibration, camera_id=camera_id)
                if c.pose_rvec is not None and not self.store.is_invalid(c.calibration_id)]
        return cals[-1] if cals else None

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
    concept: str | None = Field(default=None, description="One short noun SAM looks for, e.g. 'box' (SAM finds "
                                "nothing for long phrases). Not needed with a device/sorter scan point")
    scan_point_id: str | None = Field(default=None, description="Aim SAM with a scan point id from scan_history: a device point prompts the object there at at_iso; a "
                                      "handheld point keeps only tracks that start in its work area and leave it")
    at_iso: str | None = Field(default=None, description="The scan's time (the parcel was at the point then)")
    start_iso: str | None = Field(default=None, description="Window start: only these seconds are sent to SAM")
    end_iso: str | None = Field(default=None, description="Window end")


class SparkArgs(_Args):
    media_id: str
    start_s: float = Field(ge=0)
    end_s: float = Field(gt=0)
    template: str = Field(description="presence_v1 | interaction_v1 | carrying_v1 | contradiction_v1 | next_evidence_v1")
    track_id: str | None = Field(default=None, description="Crop the clip around this track (e.g. a person far from "
                                 "the camera) so the model sees it larger; use with carrying_v1")


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
    est = estimate_for(ctx.store, ls.observation.observation_id)
    edge = blind_areas_near(ctx.store, ctx.site, est.floor_xy_m, est.uncertainty_radius_m or 0.0) \
        if est is not None and est.floor_xy_m is not None else []  # fmt: skip
    return {"status": "ok", "last": _obs_summary(ctx, ls.observation), "ambiguous_with": ls.ambiguous_with,
            "unsynced_observation_ids": ls.unsynced_observation_ids,
            "at_edge_of_unwatched_area": edge}  # fmt: skip


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
    return ctx.run_sam(a.media_id, concept=a.concept, start_iso=a.start_iso, end_iso=a.end_iso,
                       scan_point_id=a.scan_point_id, at_iso=a.at_iso)


def t_ask_spark(ctx: ToolContext, a: SparkArgs) -> dict:
    ctx.media(a.media_id)
    if a.end_s - a.start_s > 120:
        raise ScopeError("clip windows are limited to 120 s; ask about a narrower interval")
    if ctx.ask_spark is None:
        return {"status": "analysis_unavailable", "reason": "video reasoning service not configured"}
    return ctx.ask_spark(a.media_id, a.start_s, a.end_s, a.template, track_id=a.track_id)


class FootageArgs(_Args):
    camera_id: str | None = Field(default=None, description="A camera id from footage_for or scan_history")
    scan_point_id: str | None = Field(default=None, description="Or a scan point: every camera that sees it")
    start_iso: str
    end_iso: str


def t_scan_history(ctx: ToolContext, a: ObjectArgs) -> dict:
    """The object's scans on the shared clock, and where the last one leaves it: its scan point, what is there (a
    device, or a handheld work area) and which cameras see it."""
    ctx.object(a.object_instance_id)
    keys = object_keys(ctx.store, a.object_instance_id)
    timeline = scans_for(ctx.store, keys, site_id=ctx.case.site_id) if keys else None
    scans = [ts for ts in (timeline.scans if timeline else []) if ts.scan.read_outcome == ReadOutcome.READ]
    if not scans:
        return {"scans": [], "note": "no scans of this object at this site"}
    plan = latest_plan(ctx.store, ctx.case.site_id)
    rows = [{"t": ts.t.isoformat(), "event_kind": ts.scan.event_kind.value, "scan_point_id": ts.scan.station_id
             or ts.scan.device_id, "zone_id": ts.scan.read_point_zone_id, "container": ts.scan.container.value
             if ts.scan.container else None, "clock": "synchronized" if ts.synced else "not synchronized",
             "scan_event_id": ts.scan.scan_event_id} for ts in scans]  # fmt: skip
    last = rows[-1]
    rp = plan.read_point(last["scan_point_id"]) if plan else None
    where = None
    if rp is not None:
        where = {"scan_point_id": rp.scan_point_id, "device_kind": rp.device_kind, "zone_id": rp.zone_id,
                 "kind": "device" if rp.device_parts_m else "handheld work area" if rp.work_area_m else "sorter event",
                 "cameras_that_see_it": rp.visible_by}  # fmt: skip
    return {"scans": rows, "last_scan": last, "last_scan_point": where,
            "note": "after the last scan nothing records the object; cameras that see the last scan point are where "
                    "to start looking, from the earliest footage after that time"}


def t_footage_for(ctx: ToolContext, a: FootageArgs) -> dict:
    """Recorded clips covering a window, for one camera or for every camera that sees a scan point."""
    cams: list[str] = []
    if a.camera_id:
        cams = [a.camera_id]
    elif a.scan_point_id:
        plan = latest_plan(ctx.store, ctx.case.site_id)
        rp = plan.read_point(a.scan_point_id) if plan else None
        if rp is None:
            raise ScopeError(f"unknown scan point {a.scan_point_id}")
        cams = list(rp.visible_by)
    start, end = (datetime.fromtimestamp(parse_iso(x) / 1000, UTC) for x in (a.start_iso, a.end_iso))
    out = []
    for cam in cams:
        ctx.camera_on_site(cam)
        for m in ctx.store.find(MediaAsset, camera_id=cam):
            covs = ctx.store.find(CameraCoverage, media_id=m.media_id)
            if m.kind.value != "original" or not covs or covs[-1].end_utc < start or covs[-1].start_utc > end:
                continue
            out.append({"camera_id": cam, "media_id": m.media_id, "start": covs[-1].start_utc.isoformat(),
                        "end": covs[-1].end_utc.isoformat(), "clock_uncertainty_ms": covs[-1].time_uncertainty_ms})
    return {"clips": out, "note": "" if out else "no recording covers this window; request_evidence to ask for it"}


class AreaArgs(_Args):
    camera_id: str = Field(description="The camera that watches the area's doorway")
    area_id: str = Field(description="A site-plan area id (e.g. a blind room) or a zone id")


class CarrierArgs(_Args):
    object_instance_id: str
    camera_id: str = Field(description="A camera whose people may be carrying the object")


def _person_paths(ctx: ToolContext, camera_id: str):
    ctx.camera_on_site(camera_id)
    cal = ctx.verifier_calibration(camera_id)
    tracks = [t for m in ctx.store.find(MediaAsset, camera_id=camera_id) if m.kind.value == "original"
              for t in ctx.store.find(Track, media_id=m.media_id) if t.label == "person"]  # fmt: skip
    return cal, [floor_path(ctx.store, t.track_id, cal, carried=False) for t in tracks] if cal else []


def _clock_ms(ctx: ToolContext, camera_id: str) -> float:
    covs = [c for m in ctx.store.find(MediaAsset, camera_id=camera_id)
            for c in ctx.store.find(CameraCoverage, media_id=m.media_id)]
    return covs[-1].time_uncertainty_ms if covs else 0.0


def t_door_crossings(ctx: ToolContext, a: AreaArgs) -> dict:
    """Who went into / came out of an area at its edge, from the people SAM tracked on the camera watching it."""
    area = area_polygon(ctx.store, ctx.site, a.area_id)
    if area is None:
        raise ScopeError(f"unknown area {a.area_id}")
    cal, paths = _person_paths(ctx, a.camera_id)
    if cal is None:
        return {"status": "unavailable", "reason": f"{a.camera_id} has no calibrated pose"}
    if not paths:
        return {"status": "no_people_tracked", "note": "run run_sam with concept 'person' on this camera's clip first"}
    seen: list = []
    for x in area_crossings(paths, area[1]):  # two tracks of one person (overlapping SAM runs) cross once
        if not any(y.kind == x.kind and abs(y.t_ms - x.t_ms) <= 1000 for y in seen):
            seen.append(x)
    return {"area": area[0], "crossings": [{"kind": x.kind, "t": datetime.fromtimestamp(x.t_ms / 1000, UTC).isoformat(),
                                             "person_track_id": x.track_id} for x in seen],
            "note": "people are anonymous tracks; a crossing says nothing about who they are"}


def t_carrier_check(ctx: ToolContext, a: CarrierArgs) -> dict:
    """Which tracked person on a camera was with the object (its linked track) at the same moments, by place and time,
    within the two cameras' clock uncertainty."""
    ctx.object(a.object_instance_id)
    cal, paths = _person_paths(ctx, a.camera_id)
    if cal is None or not paths:
        return {"status": "no_people_tracked", "note": "run run_sam with concept 'person' on this camera's clip first"}
    out = []
    for assoc in latest_associations(ctx.store, a.object_instance_id).values():
        if assoc.status.value not in ("verified_same_camera", "human_confirmed", "scan_bound"):
            continue
        t = ctx.store.get(Track, assoc.track_id)
        tcal = ctx.verifier_calibration(t.camera_id)
        if tcal is None:
            continue
        carton = floor_path(ctx.store, t.track_id, tcal, carried=True)
        tol = 0.0 if t.camera_id == a.camera_id else _clock_ms(ctx, t.camera_id) + _clock_ms(ctx, a.camera_id)
        for person in paths:
            f = carrier_fit(carton, person, clock_tolerance_ms=tol)
            out.append({"object_track_id": t.track_id, "person_track_id": person.track_id, "verdict": f.verdict,
                        "reason": f.reason})
    return {"results": out, "note": "a likely carrier is a candidate link by place and time, never an identity"}


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
    # models filling a strict schema send every field of every claim kind, unused ones as null: drop the nulls, keep
    # everything else strict (an unknown field with a value is still refused)
    claim = CLAIM_ADAPTER.validate_python(normalize_claim(a.claim))
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
    Tool("scan_history", "The object's scans and where the last one leaves it (scan point, cameras that see it).",
         ObjectArgs, t_scan_history),
    Tool("footage_for", "Recorded clips (media_id, time span) for a camera or a scan point in a window.",
         FootageArgs, t_footage_for),
    Tool("door_crossings", "Who went into / came out of an area no camera sees inside (people tracked by SAM).",
         AreaArgs, t_door_crossings),
    Tool("carrier_check", "Which tracked person was with the object at the same moments (place and time only).",
         CarrierArgs, t_carrier_check),
    Tool("run_sam", "Follow a parcel with SAM in one clip (paid, per frame): aim it with a scan point and a time "
                    "window, not the whole clip.", SamArgs, t_run_sam, paid=True),
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
