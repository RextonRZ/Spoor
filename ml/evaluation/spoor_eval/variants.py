"""Ablation variants (PRD §21.4). Each takes ONLY ScenarioInputs — never ground truth — and returns a Prediction.

A0  Muse Spark reads the clip(s) and answers directly.
A1  A0's question answered from SAM tracks alone: latest detection, no graph, no verification.
A2  SAM + evidence graph + deterministic verifier/orchestrator, no LLM agents.
A3  A2 + Evidence/Hypothesis agents.
"""

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from spoor.agents import ToolContext, investigate
from spoor.contracts import (
    AssociationStatus,
    Camera,
    CameraCoverage,
    Case,
    ClockSync,
    EvidenceScope,
    FloorCalibration,
    MediaAuthorization,
    ObjectInstance,
    RawObservation,
    RigState,
    Site,
    TrackAssociation,
    new_id,
)
from spoor.ingest import MediaStore, asset_path, ingest
from spoor.perception import InstancePrompt, PerceptionRequest, track_target
from spoor.reasoning import JsonBackend
from spoor.sensors import parse_sensor_csv
from spoor.spatial import ValidationThresholds, fit_floor_calibration
from spoor.store import CostEntry, EvidenceStore, estimate_for, transitions
from spoor.verification import Verifier

from .schema import Claim, Prediction, ScenarioInputs, TruthEvent

NOW = datetime(2026, 10, 27, tzinfo=UTC)  # fixed processing timestamp for reproducible records


@dataclass
class Backends:
    sam: Any = None  # SamBackend
    spark: JsonBackend | None = None
    spark_client: Any = None
    agent: JsonBackend | None = None


@dataclass
class Prepared:
    store: EvidenceStore
    media: MediaStore
    site: Site
    case: Case
    object_id: str
    clips: list[tuple[str, Any, Camera]]  # (media_id, IngestResult, camera)
    syncs: dict[str, ClockSync]


def prepare(inputs: ScenarioInputs, dataset: Path, workdir: Path) -> Prepared:
    store, media = EvidenceStore(), MediaStore(workdir / "media")
    site = store.put(Site.model_validate_json((dataset / inputs.site_file).read_text(encoding="utf-8")))
    floor_id = site.floors[0].floor_id
    syncs = {}
    cams: dict[str, Camera] = {}
    for c in inputs.cameras:
        cams[c.camera_id] = store.put(Camera(camera_id=c.camera_id, site_id=site.site_id, floor_id=floor_id,
                                             name=c.camera_id, resolution_wh_px=c.resolution_wh_px,
                                             zone_image_regions_px=c.zone_image_regions_px))  # fmt: skip
        syncs[c.camera_id] = store.put(ClockSync(sync_id=new_id("sync"), camera_id=c.camera_id,
                                                 offset_ms=c.clock_offset_ms, uncertainty_ms=c.clock_uncertainty_ms,
                                                 method=c.clock_method, created_at=NOW))  # fmt: skip
        if c.calibration:
            cal = c.calibration
            store.put(fit_floor_calibration(
                calibration_id=new_id("calibration"), camera_id=c.camera_id, floor_id=floor_id, version=1,
                image_points_px=cal["image_points_px"], floor_points_m=cal["floor_points_m"],
                holdout_image_points_px=cal.get("holdout_image_points_px", []),
                holdout_floor_points_m=cal.get("holdout_floor_points_m", []),
                thresholds=ValidationThresholds(cal["max_median_m"], cal["max_p95_m"]), now=NOW,
                image_wh_px=tuple(cal.get("image_wh_px", c.resolution_wh_px)),
            ))  # fmt: skip
    auth = store.put(MediaAuthorization(
        authorization_id=new_id("authorization"), site_id=site.site_id, uploader="evaluation",
        rights_statement="Evaluation dataset; see docs/DATA_RIGHTS.md", purpose="evaluation", consent_confirmed=True,
        hosted_processing_allowed=True, retention_until=NOW + timedelta(days=365), recorded_at=NOW,
    ))  # fmt: skip
    clips = []
    for clip in inputs.clips:
        r = ingest(dataset / clip.file, store=media, authorization=auth, site_id=site.site_id,
                   camera_id=clip.camera_id, ingested_by="evaluation", now=NOW)  # fmt: skip
        for a in (r.original, r.proxy):
            if not store.exists(a.media_id):
                store.put(a)
        sync = syncs[clip.camera_id]
        start = clip.recording_start_camera_time + timedelta(milliseconds=sync.offset_ms)
        store.put(CameraCoverage(coverage_id=new_id("coverage"), camera_id=clip.camera_id,
                                 media_id=r.original.media_id, start_utc=start,
                                 end_utc=start + timedelta(milliseconds=r.original_frames.pts_ms[-1]),
                                 sync_id=sync.sync_id, time_uncertainty_ms=sync.uncertainty_ms))  # fmt: skip
        clips.append((r.original.media_id, r, cams[clip.camera_id]))
    if inputs.sensor_csv:
        for ev in parse_sensor_csv((dataset / inputs.sensor_csv).read_text(encoding="utf-8"), import_batch="eval",
                               site_id=site.site_id):
            store.put(ev, check_refs=False)
    case = store.put(Case(case_id=new_id("case"), site_id=site.site_id, question=inputs.question,
                          target_description=inputs.target_description, created_by="evaluation", created_at=NOW))
    obj = store.put(ObjectInstance(object_instance_id=new_id("object_instance"), case_id=case.case_id,
                                   label=inputs.target_description, created_by="evaluation", created_at=NOW))
    return Prepared(store, media, site, case, obj.object_instance_id, clips, syncs)


def _perceive(p: Prepared, inputs: ScenarioInputs, backends: Backends, workdir: Path, *, link: bool) -> None:
    """SAM on every clip. The user-initiated clip uses the operator box; others use the concept prompt."""
    for i, (media_id, r, cam) in enumerate(p.clips):
        init = inputs.target_init
        instance = None
        if init and init.clip_index == i:
            instance = InstancePrompt(frame_index=init.frame_index, box_ltrb_px=init.box_ltrb_px)
        clip = inputs.clips[i]
        req = PerceptionRequest(
            original=r.original, proxy=r.proxy, proxy_path=asset_path(p.media, r.proxy),
            original_frames=r.original_frames, proxy_frames=r.proxy_frames, authorization=p.store.get(MediaAuthorization,
                                                                         r.original.authorization_id),
            camera=cam, clip_start_camera_time=clip.recording_start_camera_time, sync=p.syncs[cam.camera_id],
            concept=None if instance else inputs.target_description, instance=instance, case_id=p.case.case_id,
            on_floor_plane=inputs.on_floor_plane, site=p.site,
            calibration=next((c for c in p.store.find(FloorCalibration, camera_id=cam.camera_id)
                              if c.rig_state == RigState.VALIDATED_FLOOR_ONLY), None),
        )  # fmt: skip
        res = asyncio.run(track_target(req, backend=backends.sam, store=p.store, cache_dir=workdir / "cache",
                                       now=NOW))  # fmt: skip
        if not link:
            continue
        for t in res.tracks:
            # Only the operator-initiated instance is a confirmed link; anything else stays a candidate.
            status = (AssociationStatus.VERIFIED_SAME_CAMERA if instance and len(res.tracks) == 1
                      else AssociationStatus.CANDIDATE_CROSS_CAMERA)  # fmt: skip
            p.store.put(TrackAssociation(object_instance_id=p.object_id, track_id=t.track_id, status=status,
                                         reason="evaluation linking policy", version=1, created_at=NOW,
                                         created_by="evaluation"))  # fmt: skip


def _cost(p: Prepared, pred: Prediction) -> Prediction:
    entries = p.store.find(CostEntry)
    return pred.model_copy(update={"model_calls": sum(not e.cache_hit for e in entries),
                                   "input_tokens": sum(e.input_tokens for e in entries),
                                   "output_tokens": sum(e.output_tokens for e in entries)})


def _frame_ref(obs: RawObservation) -> str:
    return f"{obs.source_frame.media_id}:{obs.source_frame.frame_index}"


def variant_a1(inputs: ScenarioInputs, dataset: Path, workdir: Path, backends: Backends) -> Prediction:
    if backends.sam is None:
        return Prediction(scenario_id=inputs.scenario_id, variant="A1", status="unavailable", detail="no SAM")
    p = prepare(inputs, dataset, workdir)
    _perceive(p, inputs, backends, workdir, link=False)
    obs = [o for o in p.store.find(RawObservation) if o.source_frame.normalized_utc]
    if not obs:
        return _cost(p, Prediction(scenario_id=inputs.scenario_id, variant="A1", status="abstained"))
    last = max(obs, key=lambda o: o.source_frame.normalized_utc)
    est = estimate_for(p.store, last.observation_id)
    return _cost(p, Prediction(
        scenario_id=inputs.scenario_id, variant="A1", status="answered", last_seen_utc=last.source_frame.normalized_utc,
        last_seen_zone=est.zone_id if est else None, last_seen_xy_m=est.floor_xy_m if est else None,
        claims=[Claim(text=f"latest detection of '{last.label}'", observation_ids=[last.observation_id],
                      frame_refs=[_frame_ref(last)])],
    ))  # fmt: skip


def _pipeline(inputs: ScenarioInputs, dataset: Path, workdir: Path, backends: Backends, variant: str,
              agents: bool) -> Prediction:  # fmt: skip
    if backends.sam is None or (agents and backends.agent is None):
        return Prediction(scenario_id=inputs.scenario_id, variant=variant, status="unavailable",
                          detail="missing SAM or agent backend")  # fmt: skip
    p = prepare(inputs, dataset, workdir)
    _perceive(p, inputs, backends, workdir, link=True)
    ctx = ToolContext(store=p.store, site=p.site, case=p.case, verifier=Verifier(p.store, p.site),
                      scope=EvidenceScope(), now=lambda: NOW)  # fmt: skip
    res = investigate(ctx, evidence_backend=backends.agent if agents else None,
                      hypothesis_backend=backends.agent if agents else None)  # fmt: skip
    ans = res.objects[0]
    pred = Prediction(scenario_id=inputs.scenario_id, variant=variant, status=res.status,
                      left_area={"supported": "yes", "contradicted": "no"}.get(ans.left_area, "unknown"),
                      detail=res.answer)  # fmt: skip
    if f := ans.last_seen_finding:
        obs = p.store.get(RawObservation, f.observation_ids[0])
        est = estimate_for(p.store, obs.observation_id)
        pred.last_seen_utc = obs.source_frame.normalized_utc
        pred.last_seen_zone = est.zone_id if est else None
        pred.last_seen_xy_m = est.floor_xy_m if est else None
    pred.events = [TruthEvent(kind="moved", start_utc=datetime.fromtimestamp(t.start_ms / 1000, UTC),
                              end_utc=datetime.fromtimestamp(t.end_ms / 1000, UTC), zone_from=t.from_zone,
                              zone_to=t.to_zone)
                   for t in transitions(p.store, p.object_id) if t.label.value == "observed"]  # fmt: skip
    pred.claims = [Claim(text=f.statement, observation_ids=f.observation_ids,
                         frame_refs=[_frame_ref(p.store.get(RawObservation, o)) for o in f.observation_ids])
                   for f in res.findings]  # fmt: skip
    pred.claims += [Claim(text=h.claim, label=f"hypothesis:{h.status.value}") for h in res.hypotheses]
    return _cost(p, pred)


def variant_a2(inputs, dataset, workdir, backends) -> Prediction:
    return _pipeline(inputs, dataset, workdir, backends, "A2", agents=False)


def variant_a3(inputs, dataset, workdir, backends) -> Prediction:
    return _pipeline(inputs, dataset, workdir, backends, "A3", agents=True)


class DirectAnswer(BaseModel):
    answerable: bool
    clip_index: int | None
    last_seen_time_s: float | None
    last_seen_zone_id: str | None
    left_area: Literal["yes", "no", "unknown"]
    explanation: str


def variant_a0(inputs: ScenarioInputs, dataset: Path, workdir: Path, backends: Backends) -> Prediction:
    """Plain video-LLM baseline: all clips + the question, one structured answer, no tools or verification."""
    if backends.spark is None or backends.spark_client is None:
        return Prediction(scenario_id=inputs.scenario_id, variant="A0", status="unavailable", detail="no Spark")
    site = Site.model_validate_json((dataset / inputs.site_file).read_text(encoding="utf-8"))
    zones = [{"zone_id": z.zone_id, "name": z.name} for z in site.zones]
    content = [{"type": "input_text", "text": json.dumps({
        "question": inputs.question, "target": inputs.target_description, "zones": zones,
        "clips": [{"clip_index": i, "camera_id": c.camera_id} for i, c in enumerate(inputs.clips)],
        "instructions": "Answer from the videos. Times are seconds from the start of the given clip.",
    })}]  # fmt: skip
    file_ids, start = [], time.perf_counter()
    try:
        for c in inputs.clips:
            with (dataset / c.file).open("rb") as f:
                file_ids.append(backends.spark_client.files.create(
                    purpose="user_data", file=f, expires_after={"anchor": "created_at", "seconds": 3600}).id)
        content += [{"type": "input_video", "file_id": fid} for fid in file_ids]
        reply = backends.spark.complete(system="You answer questions about CCTV clips.", content=content,
                                        output=DirectAnswer, name="direct_answer")  # fmt: skip
    except Exception as e:  # noqa: BLE001 — a failed baseline is recorded, not retried silently
        return Prediction(scenario_id=inputs.scenario_id, variant="A0", status="error", detail=str(e)[:300])
    finally:
        for fid in file_ids:
            backends.spark_client.files.delete(fid)
    a: DirectAnswer = reply.data
    pred = Prediction(scenario_id=inputs.scenario_id, variant="A0", model_calls=1, input_tokens=reply.input_tokens,
                      output_tokens=reply.output_tokens, latency_s=round(time.perf_counter() - start, 3),
                      status="answered" if a.answerable else "abstained", left_area=a.left_area,
                      last_seen_zone=a.last_seen_zone_id, claims=[Claim(text=a.explanation)])  # fmt: skip
    if a.answerable and a.clip_index is not None and a.last_seen_time_s is not None \
            and 0 <= a.clip_index < len(inputs.clips):  # fmt: skip
        clip = inputs.clips[a.clip_index]
        cam = next(c for c in inputs.cameras if c.camera_id == clip.camera_id)
        pred.last_seen_utc = clip.recording_start_camera_time + timedelta(seconds=a.last_seen_time_s,
                                                                          milliseconds=cam.clock_offset_ms)
    return pred


VARIANTS = {"A0": variant_a0, "A1": variant_a1, "A2": variant_a2, "A3": variant_a3}


def variant_cd(inputs: ScenarioInputs, dataset: Path, workdir: Path, backends: Backends) -> Prediction:
    """Deterministic change-detection baseline (PRD §1.3, §21.3): no model at all. Watches the operator-selected
    region of the target and reports the last frame before it changes persistently."""
    import cv2
    import numpy as np

    init = inputs.target_init
    if init is None:
        return Prediction(scenario_id=inputs.scenario_id, variant="CD", status="unavailable",
                          detail="needs an operator-selected target region")  # fmt: skip
    p = prepare(inputs, dataset, workdir)
    _, r, cam = p.clips[init.clip_index]
    cap = cv2.VideoCapture(str(asset_path(p.media, r.proxy)))
    x1, y1, x2, y2 = init.box_ltrb_px

    def patch(frame) -> np.ndarray:
        g = cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
        return cv2.resize(g, (32, 32)).astype(np.float32)

    diffs, ref, i = [], None, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i == init.frame_index:
            ref = patch(frame)
        if ref is not None:
            diffs.append((i, float(np.mean(np.abs(patch(frame) - ref)))))
        i += 1
    cap.release()
    if ref is None or not diffs:
        return Prediction(scenario_id=inputs.scenario_id, variant="CD", status="error", detail="could not read clip")
    noise = float(np.median([d for _, d in diffs[1:6]])) if len(diffs) > 1 else 0.0
    threshold, persist = max(12.0, 4.0 * noise), 5
    last_present = diffs[0][0]
    absent_run = 0
    for idx, d in diffs:
        if d <= threshold:
            last_present, absent_run = idx, 0
        else:
            absent_run += 1
            if absent_run >= persist:
                break
    clip = inputs.clips[init.clip_index]
    offset = next(c.clock_offset_ms for c in inputs.cameras if c.camera_id == cam.camera_id)
    t = clip.recording_start_camera_time + timedelta(milliseconds=r.original_frames.pts_ms[last_present] + offset)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    from spoor.contracts import point_in_polygon

    zone = next((z for z, poly in cam.zone_image_regions_px.items() if point_in_polygon((cx, cy), poly)), None)
    return Prediction(scenario_id=inputs.scenario_id, variant="CD", status="answered", last_seen_utc=t,
                      last_seen_zone=zone, detail=f"threshold {threshold:.1f}, region changed after frame "
                      f"{last_present}", claims=[Claim(text="target region unchanged until this frame",
                                                       frame_refs=[f"{r.original.media_id}:{last_present}"])])


VARIANTS["CD"] = variant_cd
