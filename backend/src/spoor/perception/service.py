"""Perception service (PRD §14.1): SAM detections -> tracks, observations and spatial estimates with provenance.

Inference runs on the frame-aligned working proxy (verified at ingest: proxy frame i == original frame i), but every
observation cites the ORIGINAL media and its frame timestamps, so citations resolve to unmodified evidence.
"""

import asyncio
import dataclasses
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from spoor.contracts import (
    Camera,
    ClockSync,
    FloorCalibration,
    FrameRef,
    MediaAsset,
    MediaAuthorization,
    ModelProvenance,
    RawObservation,
    Site,
    SourceType,
    SpatialEstimate,
    Track,
    new_id,
)
from spoor.ingest import FrameTable, inference_cache_key
from spoor.ingest.clips import ClipCutError, cut_frames, frame_chunks
from spoor.ingest.ffmpeg import MediaToolError
from spoor.spatial import ProjectionInput, normalize, project_observation
from spoor.store import CostEntry, EvidenceStore

from .backend import Propagation, SamBackend, SamRun
from .prompts import InstancePrompt, validate_concept

PROMPT_VERSION = "sam_prompt_v1"
SAM_MIN_BILLED_FRAMES = 50  # dev.meta.ai/docs/sam/segmenting: video billed per frame, 50-frame minimum
SAM_MAX_FRAMES = 15_000  # dev.meta.ai/docs/sam/segmenting: clips can be up to 15,000 frames
LOW_CONFIDENCE = 0.5
SMALL_OBJECT_FRACTION = 0.001
LOW_MASK_FILL = 0.3
# SAM docs: object ids are not reliable once the object leaves view or is occluded. A run of missing frames longer than
# this ends the track; detections after it under the same id become their own track (never assumed the same object).
MAX_GAP_FRAMES = 5

Status = Literal["ok", "no_detections", "not_authorized_for_hosted_processing", "unknown_completion",
                 "analysis_unavailable", "incomplete"]  # fmt: skip


@dataclass
class PerceptionRequest:
    original: MediaAsset
    proxy: MediaAsset
    proxy_path: Path
    original_frames: FrameTable
    authorization: MediaAuthorization
    camera: Camera
    clip_start_camera_time: datetime
    sync: ClockSync
    concept: str | None = None
    instance: InstancePrompt | None = None
    propagation: Propagation = "both"
    case_id: str | None = None
    # Spatial projection (optional): the target's contact point lies on the floor plane?
    on_floor_plane: bool = False
    site: Site | None = None
    calibration: FloorCalibration | None = None
    # The proxy's own frame table (same frame count; its timestamps may start at 0 when the original's do not).
    proxy_frames: FrameTable | None = None
    # Only these frames (inclusive) are sent: the window a scan or a gap points to, not the whole clip.
    frame_range: tuple[int, int] | None = None


@dataclass
class PerceptionResult:
    status: Status
    message: str = ""
    tracks: list[Track] = field(default_factory=list)
    observations: list[RawObservation] = field(default_factory=list)
    estimates: list[SpatialEstimate] = field(default_factory=list)
    cache_hit: bool = False
    cache_key: str | None = None
    run: SamRun | None = None


def _quality_flags(box, frame_wh, confidence, mask_fill) -> list[str]:
    left, top, right, bottom = box
    w, h = frame_wh
    flags = []
    if left <= 2 or top <= 2 or right >= w - 2 or bottom >= h - 2:
        flags.append("touches_frame_edge")
    if (right - left) * (bottom - top) < SMALL_OBJECT_FRACTION * w * h:
        flags.append("small_object")
    if confidence is not None and confidence < LOW_CONFIDENCE:
        flags.append("low_raw_confidence")
    if mask_fill is not None and mask_fill < LOW_MASK_FILL:
        flags.append("partially_occluded")
    return flags


def _clamp_box(box, frame_wh):
    w, h = frame_wh
    left, top, right, bottom = box
    clamped = (max(0.0, left), max(0.0, top), min(float(w), right), min(float(h), bottom))
    return clamped, clamped != tuple(float(v) for v in box)


def _ledger(store, req, run, *, outcome, cache_hit, frames, now, latency=None):
    if store is None:
        return
    store.record_cost(CostEntry(
        cost_id=new_id("ledger"), provider="meta_model_api", model=run.model if run else "sam-3.1",
        request_kind="sam_video_segmentation", case_id=req.case_id, response_id=run.response_id if run else None,
        billed_units=0 if cache_hit else max(SAM_MIN_BILLED_FRAMES, frames), unit="frames", usd_estimate=None,
        cache_hit=cache_hit, outcome=outcome, latency_s=latency, at=now,
    ))  # fmt: skip


@dataclass
class _ChunkRun:
    start_frame: int
    run: SamRun | None
    cache_hit: bool
    cache_key: str
    failure: tuple[Status, str] | None = None


async def _run_chunk(req, backend, store, cache_dir, chunk_dir, prompt, start, end, n_frames, timeout_s, now):
    whole = (start, end) == (0, n_frames - 1)
    key = inference_cache_key(source_sha256=req.proxy.sha256, model_id=backend.model, prompt_version=PROMPT_VERSION,
                              prompt=prompt, settings={"propagation": req.propagation},
                              clip_window_ms=None if whole else (float(start), float(end)))  # fmt: skip
    cache_file = cache_dir / f"sam_{req.proxy.sha256[:16]}_{key}.json"
    frames = end - start + 1
    if cache_file.exists():
        run = SamRun.from_json(json.loads(cache_file.read_text(encoding="utf-8")))
        _ledger(store, req, run, outcome="ok", cache_hit=True, frames=frames, now=now)
        return _ChunkRun(start, run, True, key)
    video = req.proxy_path
    if not whole:
        try:
            video = cut_frames(req.proxy_path, req.proxy_frames or req.original_frames,
                               source_media_id=req.proxy.media_id,
                               start_frame=start, end_frame=end, out_dir=chunk_dir).path  # fmt: skip
        except (ClipCutError, MediaToolError) as e:
            return _ChunkRun(start, None, False, key, ("analysis_unavailable", f"chunk {start}-{end}: {e}"))
    try:
        run = await asyncio.wait_for(backend.segment_video(video, prompt, propagation=req.propagation), timeout_s)
    except TimeoutError:
        # The provider may still finish and bill: record as unknown completion, never blindly retry (PRD §12).
        _ledger(store, req, None, outcome="timeout_unknown_completion", cache_hit=False, frames=frames, now=now)
        msg = f"frames {start}-{end}: no response within {timeout_s}s"
        return _ChunkRun(start, None, False, key, ("unknown_completion", msg))
    except Exception as e:  # noqa: BLE001 — provider/network failure: evidence stays, analysis does not
        _ledger(store, req, None, outcome="error", cache_hit=False, frames=frames, now=now)
        return _ChunkRun(start, None, False, key, ("analysis_unavailable", f"{type(e).__name__}: {e}"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(run.to_json()), encoding="utf-8")
    _ledger(store, req, run, outcome="ok", cache_hit=False, frames=frames, now=now, latency=run.latency_s)
    return _ChunkRun(start, run, False, key)


async def track_target(
    req: PerceptionRequest,
    *,
    backend: SamBackend,
    store: EvidenceStore | None,
    cache_dir: Path,
    timeout_s: float = 600.0,
    max_frames_per_request: int = SAM_MAX_FRAMES,
    now: datetime | None = None,
) -> PerceptionResult:
    """Segment/track the target. Clips longer than SAM's per-request frame limit are processed in contiguous chunks;
    SAM object IDs restart in every chunk, so each chunk yields its own tracks (never silently stitched)."""
    now = now or datetime.now(UTC)
    if not req.authorization.hosted_processing_allowed:
        return PerceptionResult("not_authorized_for_hosted_processing",
                                "the uploader has not authorized hosted model processing for this footage")
    if (req.concept is None) == (req.instance is None):
        raise ValueError("give exactly one of concept or instance prompt")
    display_wh = req.proxy.probe.display_wh_px
    n_frames = len(req.original_frames.pts_ms)
    if req.frame_range is not None:
        lo, hi = max(0, req.frame_range[0]), min(n_frames - 1, req.frame_range[1])
        if lo > hi:
            raise ValueError(f"frame range {req.frame_range} is outside the clip")
        if hi - lo + 1 < SAM_MIN_BILLED_FRAMES:  # billed as 50 frames anyway: use them (still inside the clip)
            grow = SAM_MIN_BILLED_FRAMES - (hi - lo + 1)
            lo = max(0, lo - grow // 2)
            hi = min(n_frames - 1, lo + SAM_MIN_BILLED_FRAMES - 1)
        chunks = [(a + lo, b + lo) for a, b in frame_chunks(hi - lo + 1, max_frames_per_request)]
    else:
        chunks = frame_chunks(n_frames, max_frames_per_request)
    notes: list[str] = []
    if req.instance is not None:
        chunks = [c for c in chunks if c[0] <= req.instance.frame_index <= c[1]]
        if not chunks:
            raise ValueError(f"instance prompt frame {req.instance.frame_index} is outside the clip")
        if n_frames > max_frames_per_request:
            notes.append(f"operator prompt covers frames {chunks[0][0]}-{chunks[0][1]} only; other frames were not "
                         "inspected")  # fmt: skip

    result = PerceptionResult("ok")
    reused: set[str] = set()
    label = req.concept or "operator-selected instance"
    for start, end in chunks:
        if req.concept:
            prompt = validate_concept(req.concept)
        else:
            rebased = dataclasses.replace(req.instance, frame_index=req.instance.frame_index - start)
            prompt = rebased.render(display_wh)
        chunk = await _run_chunk(req, backend, store, cache_dir, cache_dir / "chunks", prompt, start, end, n_frames,
                                 timeout_s, now)  # fmt: skip
        result.cache_key = result.cache_key or chunk.cache_key
        result.cache_hit = chunk.cache_hit if result.run is None else result.cache_hit and chunk.cache_hit
        if chunk.failure:
            result.status, msg = chunk.failure
            done = f"{len([c for c in chunks if c[0] < start])}/{len(chunks)} chunk(s) completed before failure"
            result.message = "; ".join([msg, done, *notes])
            break
        result.run = chunk.run
        if not chunk.run.completed:
            result.status, result.message = "incomplete", f"frames {start}-{end}: {chunk.run.outcome}"
            break
        if chunk.cache_hit and store is not None and (prior := _stored_tracks(store, req, chunk.cache_key)):
            # Same footage, model and prompt were already normalized and stored: reuse, never duplicate.
            result.tracks += prior
            result.observations += [o for t in prior for o in store.find(RawObservation, track_id=t.track_id)]
            reused.update(t.track_id for t in prior)
            continue
        _normalize(req, chunk.run, start, end, prompt, chunk.cache_key, label, display_wh, now, result)

    if result.status == "ok" and not result.observations:
        result.status = "no_detections"
        notes.insert(0, "try an operator box/point prompt on a clear frame" if req.concept
                     else "no match for the prompt")  # fmt: skip
    if result.status in ("ok", "no_detections"):
        result.message = "; ".join([m for m in [result.message.strip("; "), *notes] if m])
    if store is not None:
        fresh_obs = [o for o in result.observations if o.track_id not in reused]
        fresh_ids = {o.observation_id for o in fresh_obs}
        store.put_many([*(t for t in result.tracks if t.track_id not in reused), *fresh_obs,
                        *(e for e in result.estimates if e.observation_ids[0] in fresh_ids)])
    return result


def _stored_tracks(store: EvidenceStore, req: PerceptionRequest, cache_key: str) -> list[Track]:
    return [t for t in store.find(Track, media_id=req.original.media_id) if t.provenance.cache_key == cache_key]


def _normalize(req, run, start, end, prompt, key, label, display_wh, now, result) -> None:
    provenance = ModelProvenance(model=run.model, model_version=run.model, provider="meta_model_api",
                                 request_id=run.response_id, prompt=prompt, prompt_template_version=PROMPT_VERSION,
                                 cache_key=key)  # fmt: skip
    by_object: dict[str, list] = defaultdict(list)
    for det in run.detections:
        frame_index = det.frame_index + start
        if 0 <= det.frame_index and frame_index <= end:
            by_object[det.object_id].append((frame_index, det))
        else:  # out-of-range frame indices are reported, never mapped to a guessed time
            result.message += f"dropped detection at out-of-range frame {det.frame_index} (chunk start {start}); "

    segments = []
    for object_id, dets in sorted(by_object.items()):
        dets.sort(key=lambda d: d[0])
        seg = [dets[0]]
        for d in dets[1:]:
            if d[0] - seg[-1][0] > MAX_GAP_FRAMES:
                segments.append((object_id, seg))
                seg = []
            seg.append(d)
        segments.append((object_id, seg))
    for object_id, dets in segments:
        track = Track(track_id=new_id("track"), camera_id=req.camera.camera_id, media_id=req.original.media_id,
                      label=label, provider_object_id=object_id, first_frame_index=dets[0][0],
                      last_frame_index=dets[-1][0], provenance=provenance)  # fmt: skip
        result.tracks.append(track)
        for frame_index, det in dets:
            box, clamped = _clamp_box(det.box_ltrb_px, display_wh)
            flags = _quality_flags(box, display_wh, det.confidence, det.mask_fill) + (["box_clamped"] if clamped
                                                                                     else [])  # fmt: skip
            frame = normalize(
                FrameRef(media_id=req.original.media_id, pts_ms=req.original_frames.pts_ms[frame_index],
                         frame_index=frame_index),
                clip_start_camera_time=req.clip_start_camera_time, sync=req.sync,
            )  # fmt: skip
            contact = ((box[0] + box[2]) / 2, box[3])
            obs = RawObservation(
                observation_id=new_id("observation"), source_type=SourceType.VIDEO, camera_id=req.camera.camera_id,
                source_frame=frame, track_id=track.track_id, label=label, bbox_xyxy_px=box, frame_wh_px=display_wh,
                floor_contact_uv_px=contact, observed=True, quality_flags=flags, provenance=provenance,
                confidence_raw=det.confidence, created_at=now,
            )  # fmt: skip
            result.observations.append(obs)
            if req.site is not None:
                result.estimates.append(project_observation(
                    ProjectionInput([obs.observation_id], contact, on_floor_plane=req.on_floor_plane,
                                    frame_wh_px=display_wh),
                    camera=req.camera, site=req.site, calibration=req.calibration, now=now,
                ))  # fmt: skip
