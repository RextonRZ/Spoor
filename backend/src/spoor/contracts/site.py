"""Site, floor, zone, camera and calibration records (PRD §11.1, §13.1, §13.5).

Site frame: X right/east, Y forward/north, Z up, metres. Renderer axis conversion lives in `spoor.spatial`.
"""

import math
from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, Field, field_validator, model_validator

from .base import CalibrationId, CameraId, FloorId, ImmutableRecord, Record, SiteId, SyncId, ZoneId
from .enums import RigState, ZoneKind

SITE_FRAME = "site_meters_z_up_v1"

MetresXY = tuple[float, float]
MetresXYZ = tuple[float, float, float]
PixelUV = tuple[float, float]
Polygon = Annotated[list[MetresXY], Field(min_length=3)]


def _finite(*values: float) -> bool:
    return all(math.isfinite(v) for v in values)


def point_in_polygon(point: MetresXY, polygon: list[MetresXY]) -> bool:
    """Ray-casting test; points on an edge count as inside."""
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        (x1, y1), (x2, y2) = polygon[i], polygon[(i + 1) % n]
        # On-edge check (collinear and within the segment's bounding box).
        cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
        if abs(cross) < 1e-9 and min(x1, x2) - 1e-9 <= x <= max(x1, x2) + 1e-9 and min(y1, y2) - 1e-9 <= y <= max(
            y1, y2
        ) + 1e-9:
            return True
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


class Floor(Record):
    floor_id: FloorId
    name: str
    elevation_m: float = 0.0
    outline_m: Polygon

    @field_validator("outline_m")
    @classmethod
    def _finite_outline(cls, v: list[MetresXY]) -> list[MetresXY]:
        if not all(_finite(*p) for p in v):
            raise ValueError("floor outline must be finite metres")
        return v


class Zone(Record):
    zone_id: ZoneId
    floor_id: FloorId
    name: str
    kind: ZoneKind
    polygon_m: Polygon
    # Surface height above the floor, used only for `anchored_height` placement of items resting on it.
    surface_height_m: float | None = Field(default=None, ge=0)
    measured: bool = Field(description="True if surveyed in the room; False if approximate")


class Site(Record):
    site_id: SiteId
    name: str
    frame: str = SITE_FRAME
    measurement_method: str = Field(description="How dimensions were obtained, e.g. 'tape measure, ±2 cm'")
    floors: Annotated[list[Floor], Field(min_length=1)]
    zones: list[Zone] = []
    require_second_approver: bool = Field(
        default=True, description="Reports need a second person to approve them (four-eyes). Real sites keep it on; "
        "the one-user demo site turns it off, and its shared reports read 'Investigation summary'.")

    @model_validator(mode="after")
    def _zones_reference_floors(self) -> "Site":
        floor_ids = {f.floor_id for f in self.floors}
        if len(floor_ids) != len(self.floors):
            raise ValueError("duplicate floor_id")
        zone_ids = [z.zone_id for z in self.zones]
        if len(set(zone_ids)) != len(zone_ids):
            raise ValueError("duplicate zone_id")
        for z in self.zones:
            if z.floor_id not in floor_ids:
                raise ValueError(f"zone {z.zone_id} references unknown floor {z.floor_id}")
        return self

    def floor(self, floor_id: str) -> Floor:
        for f in self.floors:
            if f.floor_id == floor_id:
                return f
        raise KeyError(floor_id)

    def contains(self, floor_id: str, xy: MetresXY) -> bool:
        return point_in_polygon(xy, self.floor(floor_id).outline_m)

    def zones_at(self, floor_id: str, xy: MetresXY) -> list[Zone]:
        return [z for z in self.zones if z.floor_id == floor_id and point_in_polygon(xy, z.polygon_m)]


class Camera(Record):
    camera_id: CameraId
    site_id: SiteId
    floor_id: FloorId
    name: str
    resolution_wh_px: tuple[int, int]
    position_m: MetresXYZ | None = None
    position_measured: bool = False
    yaw_deg: float | None = None
    hfov_deg: float | None = Field(default=None, gt=0, lt=180)
    orientation_measured: bool = False
    # Floor region the camera can see; approximate unless derived from a validated calibration.
    fov_polygon_m: list[MetresXY] | None = None
    # Operator-drawn image regions for zones (e.g. a shelf top) — enables zone_only / anchored_height placement
    # for items not on the floor plane, where a floor homography is invalid (PRD §13.2 step 6).
    zone_image_regions_px: dict[ZoneId, list[PixelUV]] = {}
    valid_from: AwareDatetime | None = None
    valid_until: AwareDatetime | None = None


class FloorCalibration(ImmutableRecord):
    """A versioned image->floor homography. A new calibration is a new record; old ones are kept (PRD §16.4)."""

    calibration_id: CalibrationId
    camera_id: CameraId
    floor_id: FloorId
    version: int = Field(ge=1)
    rig_state: RigState
    homography_image_to_floor: tuple[
        tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]
    ]
    image_wh_px: tuple[int, int] | None = Field(default=None, description="Frame size the image points refer to")
    fit_image_points_px: list[PixelUV]
    fit_floor_points_m: list[MetresXY]
    holdout_image_points_px: list[PixelUV] = []
    holdout_floor_points_m: list[MetresXY] = []
    holdout_error_median_m: float | None = Field(default=None, ge=0)
    holdout_error_p95_m: float | None = Field(default=None, ge=0)
    undistorted: bool = False
    method: str = "cv2.findHomography RANSAC"
    software_version: str
    created_at: AwareDatetime
    notes: str = ""

    @model_validator(mode="after")
    def _consistent(self) -> "FloorCalibration":
        if len(self.fit_image_points_px) != len(self.fit_floor_points_m):
            raise ValueError("fit point lists differ in length")
        if len(self.fit_image_points_px) < 4:
            raise ValueError("a floor homography needs at least 4 correspondences")
        if len(self.holdout_image_points_px) != len(self.holdout_floor_points_m):
            raise ValueError("holdout point lists differ in length")
        if self.rig_state in (RigState.VALIDATED_FLOOR_ONLY, RigState.VALIDATED_MULTIVIEW_3D) and (
            not self.holdout_image_points_px or self.holdout_error_median_m is None
        ):
            raise ValueError("a validated calibration needs held-out points and a measured error (PRD §13.2)")
        return self


class CalibrationInvalidation(ImmutableRecord):
    calibration_id: CalibrationId
    reason: str = Field(min_length=3)
    invalidated_at: AwareDatetime
    invalidated_by: str


class ClockSync(ImmutableRecord):
    """Offset (and optional drift) from a device clock to the case's normalized timeline (PRD §8.3).

    Applies to one camera (`camera_id`) or a whole clock domain (`clock_domain_id`: sorter PLC, handheld fleet, NVR).
    normalized = device_time + offset_ms + drift_ppm * 1e-6 * (device_time - drift_reference). Never assume synchronous
    feeds; a fitted sync records its anchors and residuals so the case file can show how time was aligned."""

    sync_id: SyncId
    camera_id: CameraId | None = None
    clock_domain_id: str | None = None
    offset_ms: float = Field(description="normalized_time = device_time + offset_ms (+ drift)")
    drift_ppm: float = 0.0
    uncertainty_ms: float = Field(ge=0)
    drift_reference: AwareDatetime | None = Field(default=None, description="Device-clock instant drift is measured from")
    valid_from: AwareDatetime | None = None
    valid_to: AwareDatetime | None = None
    anchor_event_ids: list[str] = []
    residual_ms_p95: float | None = Field(default=None, ge=0)
    method: str = Field(description="e.g. 'shared clap event at camA f=120 / camB f=133', 'NTP metadata'")
    anchor_description: str = ""
    created_at: AwareDatetime

    @model_validator(mode="after")
    def _target(self) -> "ClockSync":
        if self.camera_id is None and self.clock_domain_id is None:
            raise ValueError("a clock sync applies to a camera or a clock domain")
        if self.drift_ppm and self.drift_reference is None:
            raise ValueError("drift needs drift_reference")
        if self.valid_to is not None and self.valid_from is not None and self.valid_to < self.valid_from:
            raise ValueError("sync validity ends before it starts")
        return self

    def covers(self, t: datetime) -> bool:
        return (self.valid_from is None or t >= self.valid_from) and (self.valid_to is None or t <= self.valid_to)

    def correction_ms(self, device_time: datetime) -> float:
        drift = 0.0
        if self.drift_ppm and self.drift_reference is not None:
            drift = self.drift_ppm * 1e-6 * (device_time - self.drift_reference).total_seconds() * 1000.0
        return self.offset_ms + drift
