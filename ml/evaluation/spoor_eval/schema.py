"""Evaluation data model (PRD §21). Inputs and ground truth are SEPARATE files and types: variants only ever receive
`ScenarioInputs`; `GroundTruth` is loaded by the scorer after predictions exist (PRD §8.1)."""

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClipInput(_M):
    camera_id: str
    file: str = Field(description="Path relative to the dataset directory")
    recording_start_camera_time: AwareDatetime


class CameraInput(_M):
    camera_id: str
    resolution_wh_px: tuple[int, int]
    clock_offset_ms: float = 0.0
    clock_uncertainty_ms: float
    clock_method: str
    zone_image_regions_px: dict[str, list[tuple[float, float]]] = {}
    calibration: dict | None = Field(default=None, description="fit/holdout points + thresholds, as in the API")


class TargetInit(_M):
    """User-verified target initiation (a legitimate investigator input, PRD §10.3), not an answer."""

    camera_id: str
    clip_index: int
    frame_index: int
    box_ltrb_px: tuple[int, int, int, int]


class ScenarioInputs(_M):
    scenario_id: str
    category: str = Field(description="C01..C14 from PRD §21.2")
    question: str
    target_description: str
    site_file: str = "site.json"
    cameras: list[CameraInput]
    clips: list[ClipInput]
    target_init: TargetInit | None = None
    on_floor_plane: bool = False
    sensor_csv: str | None = None
    split: Literal["dev", "holdout"]


class TruthEvent(_M):
    kind: Literal["moved", "occluded", "left_view", "returned", "contact", "no_change"]
    start_utc: AwareDatetime
    end_utc: AwareDatetime
    zone_from: str | None = None
    zone_to: str | None = None


class GroundTruth(_M):
    scenario_id: str
    answerable: bool = Field(description="False if the footage cannot establish the last-seen position")
    last_seen_utc: AwareDatetime | None = None
    last_seen_zone: str | None = None
    last_seen_xy_m: tuple[float, float] | None = None
    left_area: Literal["yes", "no", "unknown"] = "unknown"
    events: list[TruthEvent] = []
    time_tolerance_s: float = 1.0
    annotator: str
    annotated_at: AwareDatetime
    annotation_confidence: Literal["high", "medium", "low"]
    notes: str = ""


class Claim(_M):
    text: str
    observation_ids: list[str] = []
    frame_refs: list[str] = Field(default=[], description="media_id:frame_index strings for blind review")
    label: str = "observed"


class Prediction(_M):
    scenario_id: str
    variant: str
    status: Literal["answered", "abstained", "unavailable", "error"]
    last_seen_utc: datetime | None = None
    last_seen_zone: str | None = None
    last_seen_xy_m: tuple[float, float] | None = None
    left_area: Literal["yes", "no", "unknown"] = "unknown"
    events: list[TruthEvent] = []
    claims: list[Claim] = []
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    detail: str = ""
