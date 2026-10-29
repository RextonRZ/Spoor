"""SAM 3.1 transport. `MetaSamBackend` calls the Meta Model API; parsing always goes through Meta's parser."""

import time
from collections.abc import AsyncIterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from meta_sam_parser import (
    CompletedOutcome,
    SegmentationBoxRecord,
    SegmentationMaskRecord,
    decode_mask_to_raster,
    parse_responses_stream,
    video_segmentation_format,
)

Propagation = Literal["both", "forward", "backward"]


@dataclass(frozen=True)
class SamDetection:
    frame_index: int
    object_id: str
    box_ltrb_px: tuple[float, float, float, float]  # half-open, displayed-frame pixels
    confidence: float | None
    mask_fill: float | None  # fraction of the box covered by the mask; low values can indicate occlusion


@dataclass(frozen=True)
class SamRun:
    model: str
    response_id: str | None
    completed: bool
    outcome: str
    detections: tuple[SamDetection, ...]
    diagnostics: tuple[str, ...]
    raw_output: str
    latency_s: float | None = None
    request_metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict) -> "SamRun":
        dets = tuple(SamDetection(**{**d, "box_ltrb_px": tuple(d["box_ltrb_px"])}) for d in data["detections"])
        return cls(**{**data, "detections": dets, "diagnostics": tuple(data["diagnostics"])})


class SamBackend(Protocol):
    model: str

    async def segment_video(self, video: Path, prompt: str, *, propagation: Propagation = "both") -> SamRun: ...


def _event_type(event: Any) -> str | None:
    return event.get("type") if isinstance(event, dict) else getattr(event, "type", None)


def _response_id(event: Any) -> str | None:
    resp = event.get("response") if isinstance(event, dict) else getattr(event, "response", None)
    if resp is None:
        return None
    return resp.get("id") if isinstance(resp, dict) else getattr(resp, "id", None)


async def parse_sam_stream(events: AsyncIterable[Any], *, model: str, metadata: dict | None = None) -> SamRun:
    """Parse a Responses event stream with meta-sam-parser into normalized detections."""
    seen: dict[str, str | None] = {"id": None}

    async def tap():
        async for e in events:
            if _event_type(e) == "response.created":
                seen["id"] = _response_id(e)
            yield e

    start = time.perf_counter()
    result = await parse_responses_stream(tap(), video_segmentation_format()).final_result()
    masks = {(m.object_id, m.frame.frame_index if m.frame else 0): m
             for m in result.records if isinstance(m, SegmentationMaskRecord)}  # fmt: skip
    detections = []
    for r in result.records:
        if not isinstance(r, SegmentationBoxRecord):
            continue
        frame = r.frame.frame_index if r.frame else 0
        fill = None
        if (m := masks.get((r.object_id, frame))) is not None:
            raster = decode_mask_to_raster(m.mask)
            fill = sum(raster) / len(raster) if raster else None
        detections.append(SamDetection(frame, r.object_id, (r.left, r.top, r.right, r.bottom), r.confidence, fill))
    return SamRun(
        model=model, response_id=seen["id"], completed=isinstance(result.outcome, CompletedOutcome),
        outcome=str(result.outcome), detections=tuple(detections),
        diagnostics=tuple(f"{d.severity}:{d.code}:{d.message}" for d in result.diagnostics),
        raw_output=result.raw_output, latency_s=round(time.perf_counter() - start, 3),
        request_metadata=metadata or {},
    )  # fmt: skip


class MetaSamBackend:
    """SAM 3.1 over the Meta Model API: Files API upload -> streamed /v1/responses -> parser.

    Uploaded clips expire after one hour and are deleted after use (PRD §7.1, §12).
    """

    def __init__(self, client: Any, model: str = "sam-3.1", upload_ttl_s: int = 3600):
        self.client, self.model, self.upload_ttl_s = client, model, upload_ttl_s

    async def segment_video(self, video: Path, prompt: str, *, propagation: Propagation = "both") -> SamRun:
        with video.open("rb") as f:
            uploaded = await self.client.files.create(
                purpose="user_data", file=f, expires_after={"anchor": "created_at", "seconds": self.upload_ttl_s}
            )
        metadata = {"include_confidence": "true", "propagation_direction": propagation}
        try:
            stream = await self.client.responses.create(
                model=self.model,
                stream=True,
                metadata=metadata,
                input=[{"role": "user", "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_video", "file_id": uploaded.id},
                ]}],
            )  # fmt: skip
            return await parse_sam_stream(stream, model=self.model, metadata=metadata)
        finally:
            await self.client.files.delete(uploaded.id)
