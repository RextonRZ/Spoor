"""Raw observations, tracks, spatial estimates and sensor events (PRD §11.2, §13, §20)."""

import math
from typing import Annotated

from pydantic import AwareDatetime, Field, field_validator, model_validator

from .base import (
    CalibrationId,
    CameraId,
    CorrespondenceId,
    FloorId,
    ImmutableRecord,
    MediaId,
    MultiViewEstimateId,
    ObjectInstanceId,
    ObservationId,
    SensorEventId,
    SiteId,
    SpatialEstimateId,
    SyncId,
    TrackId,
    ZoneId,
)
from .enums import AssociationStatus, RigState, SensorKind, SourceType, SpatialMode
from .media import FrameRef
from .parcels import ParcelIdentifier
from .site import SITE_FRAME, MetresXY, MetresXYZ, Site

BoxXYXY = tuple[float, float, float, float]


class ModelProvenance(ImmutableRecord):
    """Which model produced something, with what input. `confidence_raw` is only meaningful within this model."""

    model: str
    model_version: str
    provider: str
    request_id: str | None = Field(default=None, description="Provider response/operation id")
    prompt: str | None = Field(default=None, description="Exact prompt sent (noun phrase or prompt tokens)")
    prompt_template_version: str | None = None
    cache_key: str | None = None


class RawObservation(ImmutableRecord):
    """A video- or sensor-derived observation. Never produced from user-facing narrative (PRD §11.2)."""

    observation_id: ObservationId
    source_type: SourceType
    camera_id: CameraId | None = None
    source_frame: FrameRef | None = None
    sensor_event_id: SensorEventId | None = None
    track_id: TrackId | None = None
    label: str = Field(min_length=1, max_length=120)
    # Pixel box in the media's displayed frame (after rotation), and that frame's size.
    bbox_xyxy_px: BoxXYXY | None = None
    frame_wh_px: tuple[int, int] | None = None
    mask_asset_id: MediaId | None = None
    # Image point used for floor projection (e.g. bottom-centre of box for an object on the floor).
    floor_contact_uv_px: tuple[float, float] | None = None
    observed: bool = True
    quality_flags: list[str] = []
    provenance: ModelProvenance | None = None
    confidence_raw: float | None = Field(default=None, ge=0, le=1)
    # Stays null until calibrated on holdout data (PRD §11.3, §18.3).
    confidence_calibrated: float | None = Field(default=None, ge=0, le=1)
    confidence_calibration_id: str | None = None
    created_at: AwareDatetime

    @model_validator(mode="after")
    def _source_consistency(self) -> "RawObservation":
        if self.source_type == SourceType.VIDEO:
            if self.source_frame is None or self.camera_id is None:
                raise ValueError("a video observation needs camera_id and source_frame")
        elif (
            self.source_type in (SourceType.SENSOR_REAL, SourceType.SENSOR_SIMULATED) and self.sensor_event_id is None
        ):
            raise ValueError("a sensor observation needs sensor_event_id")
        if self.bbox_xyxy_px is not None:
            if self.frame_wh_px is None:
                raise ValueError("bbox_xyxy_px requires frame_wh_px")
            x1, y1, x2, y2 = self.bbox_xyxy_px
            w, h = self.frame_wh_px
            if not (0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h):
                raise ValueError("bbox outside frame or degenerate")
        if self.confidence_calibrated is not None and self.confidence_calibration_id is None:
            raise ValueError("calibrated confidence must cite its calibration")
        return self

    @property
    def bbox_xyxy_normalized(self) -> BoxXYXY | None:
        if self.bbox_xyxy_px is None or self.frame_wh_px is None:
            return None
        x1, y1, x2, y2 = self.bbox_xyxy_px
        w, h = self.frame_wh_px
        return (x1 / w, y1 / h, x2 / w, y2 / h)


class Track(ImmutableRecord):
    """Ephemeral per-camera, per-clip track. Not a person's identity and not persistent across cameras (§7.2)."""

    track_id: TrackId
    camera_id: CameraId
    media_id: MediaId
    label: str
    provider_object_id: str = Field(description="SAM object id within one response")
    first_frame_index: int = Field(ge=0)
    last_frame_index: int = Field(ge=0)
    provenance: ModelProvenance


class ObjectInstance(ImmutableRecord):
    """A provisional physical object within a case, e.g. 'the blue equipment case'. Tracks link to it only through
    TrackAssociation records; it is never a person (PRD §11.1, §7.2)."""

    object_instance_id: ObjectInstanceId
    case_id: str
    label: str = Field(min_length=1, max_length=120)
    # Scan identifiers of the target (e.g. its waybill). Relabels are linked with IdentifierAlias, not edits here.
    identifiers: list[ParcelIdentifier] = []
    created_by: str
    created_at: AwareDatetime


class CameraCoverage(ImmutableRecord):
    """A recorded interval of one camera on the normalized timeline — what *could* have been seen (PRD §16.1)."""

    coverage_id: str
    camera_id: CameraId
    media_id: MediaId
    start_utc: AwareDatetime
    end_utc: AwareDatetime
    sync_id: SyncId
    time_uncertainty_ms: float = Field(ge=0)


class TrackAssociation(ImmutableRecord):
    """Hypothesized link of a track to a provisional physical object. Versioned, never silently merged (§14.3)."""

    object_instance_id: ObjectInstanceId
    track_id: TrackId
    status: AssociationStatus
    signals: dict[str, float] = Field(default_factory=dict, description="appearance/temporal/topology scores")
    reason: str
    version: int = Field(ge=1)
    created_at: AwareDatetime
    created_by: str


class SpatialEstimate(ImmutableRecord):
    """A position derived from observations, separate from them and always carrying its basis (PRD §11.2)."""

    estimate_id: SpatialEstimateId
    observation_ids: Annotated[list[ObservationId], Field(min_length=1)]
    spatial_mode: SpatialMode
    floor_id: FloorId | None = None
    floor_xy_m: MetresXY | None = None
    height_m: float | None = Field(default=None, description="Only for anchored_height, from a measured surface")
    zone_id: ZoneId | None = None
    uncertainty_radius_m: float | None = Field(default=None, gt=0)
    method: str
    calibration_id: CalibrationId | None = None
    status: str = "estimated_not_measured"
    created_at: AwareDatetime

    @model_validator(mode="after")
    def _mode_fields(self) -> "SpatialEstimate":
        m = self.spatial_mode
        has_xy = self.floor_xy_m is not None
        if m in (SpatialMode.FLOOR_XY, SpatialMode.ANCHORED_HEIGHT):
            if not has_xy or self.floor_id is None or self.uncertainty_radius_m is None:
                raise ValueError(f"{m} needs floor_id, floor_xy_m and uncertainty_radius_m")
            if m == SpatialMode.FLOOR_XY and self.calibration_id is None:
                raise ValueError("floor_xy needs the calibration it was projected with")
            if m == SpatialMode.ANCHORED_HEIGHT and (self.zone_id is None or self.height_m is None):
                raise ValueError("anchored_height needs the anchoring zone and its measured height")
            if not all(math.isfinite(v) for v in self.floor_xy_m):
                raise ValueError("non-finite floor position")
        elif m == SpatialMode.ZONE_ONLY:
            if self.zone_id is None or has_xy:
                raise ValueError("zone_only carries a zone_id and no coordinates")
        elif m in (SpatialMode.IMAGE_ONLY, SpatialMode.UNKNOWN):
            if has_xy or self.height_m is not None:
                raise ValueError(f"{m} must not carry coordinates")
        elif m == SpatialMode.MULTIVIEW_XYZ:
            raise ValueError("multiview XYZ uses MultiView3DEstimate")
        return self


def check_estimate_in_site(estimate: SpatialEstimate, site: Site) -> None:
    """Reject positions outside the measured floor — this also catches pixel values stored as metres."""
    if estimate.floor_xy_m is None:
        return
    if estimate.floor_id is None or not site.contains(estimate.floor_id, estimate.floor_xy_m):
        raise ValueError(f"{estimate.estimate_id}: floor position {estimate.floor_xy_m} is outside the site floor")
    if estimate.zone_id is not None and estimate.zone_id not in {z.zone_id for z in site.zones}:
        raise ValueError(f"{estimate.estimate_id}: unknown zone {estimate.zone_id}")


class MultiView3DEstimate(ImmutableRecord):
    """Optional, feature-gated (PRD §13.4). Only valid from a validated multi-view rig."""

    estimate_id: MultiViewEstimateId
    target_kind: str = "non_identifying_object_landmark"
    site_xyz_m: MetresXYZ
    site_frame: str = SITE_FRAME
    method: str = "calibrated_multiview_triangulation"
    source_observation_ids: Annotated[list[ObservationId], Field(min_length=2)]
    correspondence_id: CorrespondenceId
    calibration_ids: Annotated[list[CalibrationId], Field(min_length=2)]
    rig_state: RigState
    synchronization_id: SyncId
    reprojection_error_px_by_camera: dict[str, float]
    uncertainty_3d_m: float = Field(gt=0)
    quality_gates_passed: list[str]
    software_version: str
    created_at: AwareDatetime

    @field_validator("rig_state")
    @classmethod
    def _validated_rig(cls, v: RigState) -> RigState:
        if v != RigState.VALIDATED_MULTIVIEW_3D:
            raise ValueError("multi-view XYZ requires a validated_multiview_3d rig (PRD §13.4.1)")
        return v


class SensorEvent(ImmutableRecord):
    """Vendor-neutral sensor event (PRD §20). Corroborates; never identifies who or what."""

    sensor_event_id: SensorEventId
    site_id: SiteId
    source_type: SourceType
    device_id: str
    kind: SensorKind
    value: str | float | bool
    zone_id: ZoneId | None = None
    device_time_utc: AwareDatetime
    clock_quality: str = Field(description="e.g. 'ntp', 'unsynced', 'manual offset ±2s'")
    import_batch: str

    @field_validator("source_type")
    @classmethod
    def _sensor_source(cls, v: SourceType) -> SourceType:
        if v not in (SourceType.SENSOR_REAL, SourceType.SENSOR_SIMULATED):
            raise ValueError("sensor events must be sensor_real or sensor_simulated")
        return v
