"""Authorization, media assets and frame references (PRD §7.1, §7.3, §8.3, §11.1)."""

from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from .base import AuthorizationId, CameraId, ImmutableRecord, MediaId, Sha256, SiteId, SyncId
from .enums import AssetKind


class MediaAuthorization(ImmutableRecord):
    """Required before any upload is accepted (PRD §7.1)."""

    authorization_id: AuthorizationId
    site_id: SiteId
    uploader: str
    rights_statement: str = Field(min_length=10)
    purpose: str = Field(min_length=3)
    consent_confirmed: Literal[True] = Field(
        description="Uploader confirms recording rights and that notices/consent are in place"
    )
    hosted_processing_allowed: bool = Field(
        description="May this footage be sent to hosted model providers (Meta Model API, Baseten)?"
    )
    retention_until: AwareDatetime
    recorded_at: AwareDatetime
    recording_kind: Literal["staged_event", "real_incident", "synthetic_test"] | None = Field(
        default=None, description="Declared by the uploader; drives the provenance label in reports (PRD §27.1)")


class MediaProbe(ImmutableRecord):
    """Facts read from the container by ffprobe, kept verbatim alongside derived flags."""

    container: str
    video_codec: str
    width_px: int = Field(gt=0)
    height_px: int = Field(gt=0)
    rotation_deg: int = 0
    duration_ms: float = Field(ge=0)
    avg_fps: float | None = None
    nominal_fps: float | None = None
    variable_frame_rate: bool = False
    frame_count: int | None = None
    time_base: str | None = None
    has_audio: bool = False
    creation_time_utc: AwareDatetime | None = None
    flags: list[str] = Field(default_factory=list, description="e.g. non_monotonic_pts, rotated, missing_pts")

    @property
    def display_wh_px(self) -> tuple[int, int]:
        """Pixel size after rotation metadata — the frame SAM coordinates refer to."""
        if self.rotation_deg % 180:
            return (self.height_px, self.width_px)
        return (self.width_px, self.height_px)


class MediaAsset(ImmutableRecord):
    media_id: MediaId
    site_id: SiteId
    camera_id: CameraId | None = None
    kind: AssetKind
    sha256: Sha256
    byte_size: int = Field(gt=0)
    mime_type: str
    original_filename: str = Field(description="Stored as data only; never interpolated into prompts (PRD §7.4)")
    probe: MediaProbe | None = None
    parent_media_id: MediaId | None = None
    processing_method: str | None = Field(default=None, description="e.g. ffmpeg command template id")
    software_version: str | None = None
    authorization_id: AuthorizationId
    ingested_at: AwareDatetime
    ingested_by: str

    @model_validator(mode="after")
    def _derivative_has_parent(self) -> "MediaAsset":
        if self.kind == AssetKind.ORIGINAL:
            if self.parent_media_id is not None:
                raise ValueError("an original cannot have a parent")
        elif self.parent_media_id is None or self.processing_method is None or self.software_version is None:
            raise ValueError("a derivative must record parent_media_id, processing_method and software_version")
        return self


class FrameRef(ImmutableRecord):
    """Points at one frame of one media asset; every citation resolves through this (PRD §11.1)."""

    media_id: MediaId
    pts_ms: float = Field(ge=0, description="Presentation time in the media's own timeline")
    frame_index: int = Field(ge=0)
    camera_clock_utc: AwareDatetime | None = None
    normalized_utc: AwareDatetime | None = None
    sync_id: SyncId | None = None
    time_uncertainty_ms: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _normalized_needs_sync(self) -> "FrameRef":
        if self.normalized_utc is not None and (self.sync_id is None or self.time_uncertainty_ms is None):
            raise ValueError("a normalized timestamp must cite its sync record and uncertainty (PRD §8.3)")
        return self
