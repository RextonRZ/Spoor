"""Site plan (QUEUE I9): the geometry a real hub already has — floor plan (CAD/PDF), conveyor layout with deck heights
and belt speeds from the machine spec, read points, doors, racks and the camera mounting plan. Spoor's forensic
journey stands on this plan, not on a 3D model: belt-routed inferred segments (I2), predicted hand-off windows (I3),
the reachable "where it could be" area (I4) and the plan-built 2.5D view (H6) are all computed from it.

Every value is declared with where it came from (`source`); nothing here is an observation."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, StringConstraints, model_validator

from .base import CameraId, ImmutableRecord, Record, SiteId, ZoneId
from .site import MetresXY, MetresXYZ

PlanId = Annotated[str, StringConstraints(pattern=r"^plan_[A-Za-z0-9][A-Za-z0-9_-]*$", max_length=96)]

# Average unhurried indoor walking speed used for reachability bounds. Source: Fruin, "Pedestrian Planning and Design"
# (1971), free-flow walking ~1.3-1.4 m/s; a person carrying a parcel is not faster. Upper bound = brisk 1.8 m/s.
WALK_SPEED_MPS = 1.4
WALK_SPEED_MAX_MPS = 1.8


class PlanConveyor(Record):
    """A conveyor centreline in travel direction. `feeds` lists the conveyors it discharges onto: an open conveyor
    hands over at its end; a closed one (sorter loop) hands over where the next conveyor starts (e.g. a chute mouth)."""

    conveyor_id: str = Field(min_length=1, max_length=64)
    kind: Literal["belt", "telescopic", "loop", "chute"]
    path_m: Annotated[list[MetresXY], Field(min_length=2)]
    deck_heights_m: Annotated[list[float], Field(min_length=1)]
    closed: bool = False
    speed_mps: float | None = Field(default=None, gt=0, description="Belt speed from the machine spec; None = unknown")
    feeds: list[str] = []

    @model_validator(mode="after")
    def _heights(self) -> "PlanConveyor":
        if len(self.deck_heights_m) not in (1, len(self.path_m)):
            raise ValueError("deck_heights_m must have one value or one per path point")
        return self


class PlanReadPoint(Record):
    """A scan point (station id in the scan log). `event_positions` says where an event kind physically happens when
    that is not at the device itself, e.g. the sorter PLC reports a carrier assignment at the merge onto the loop."""

    scan_point_id: str = Field(min_length=1, max_length=64)
    device_kind: str
    position_m: MetresXYZ
    zone_id: ZoneId | None = None
    event_positions: dict[str, MetresXY] = {}
    visible_by: list[CameraId] = Field(default=[], description="Cameras with a clear view of it (plan check)")
    device_parts_m: list[MetresXYZ] = Field(
        default=[], description="Where the scan hardware physically stands (e.g. an RFID portal's two antennas). Empty: "
                                "no fixed device; a handheld scan in a work area, or a sorter event at a chute mouth")
    work_area_m: list[list[MetresXY]] = Field(
        default=[], description="Handheld scans: the floor area(s) where the scan is made, measured from what stands "
                                "there (a chute's bag frame, a bench, the bay rows, the dock door mouths)")
    work_height_m: float | None = Field(default=None, ge=0, le=3, description="Height the handheld scan is made at "
                                        "(the bag rim, the bench top, measured scanner height)")

    def position_for(self, event_kind: str) -> MetresXY:
        return self.event_positions.get(event_kind, (self.position_m[0], self.position_m[1]))


class PlanArea(Record):
    area_id: str = Field(min_length=1, max_length=64)
    kind: Literal["zone", "walkway", "rack", "bench", "cage_bay", "blind_spot", "store", "machine"]
    name: str
    polygon_m: Annotated[list[MetresXY], Field(min_length=3)]
    height_m: float | None = Field(default=None, ge=0)
    zone_id: ZoneId | None = None
    walkable: bool = Field(description="A person can walk here (walkways, open floor of zones); racks/benches: no")


class PlanDoor(Record):
    door_id: str
    kind: str = Field(description="dock, personnel, fire exit, cage entrance …")
    centre_m: MetresXY
    width_m: float = Field(gt=0)
    wall: Literal["N", "S", "E", "W", "inner"]
    exit: bool = Field(default=False, description="Leads out of the building")


class PlanCamera(Record):
    camera_id: CameraId
    position_m: MetresXYZ
    heading_deg: float
    tilt_down_deg: float
    hfov_deg: float = Field(gt=0, lt=180)
    vfov_deg: float = Field(gt=0, lt=180)
    resolution_wh_px: tuple[int, int]
    label: str | None = None


class SitePlan(ImmutableRecord):
    """One version of a site's plan. A new import is a new record; answers cite the plan_id they were computed on."""

    plan_id: PlanId
    site_id: SiteId
    source: str = Field(min_length=3, description="Where the plan came from, e.g. 'CAD export 2026-10 + machine spec'")
    outline_m: Annotated[list[MetresXY], Field(min_length=3)]
    eaves_m: float | None = None
    areas: list[PlanArea] = []
    conveyors: list[PlanConveyor] = []
    doors: list[PlanDoor] = []
    read_points: list[PlanReadPoint] = []
    cameras: list[PlanCamera] = []
    walk_speed_mps: float = Field(default=WALK_SPEED_MPS, gt=0)
    walk_speed_max_mps: float = Field(default=WALK_SPEED_MAX_MPS, gt=0)
    created_by: str
    created_at: AwareDatetime

    @model_validator(mode="after")
    def _references(self) -> "SitePlan":
        ids = [c.conveyor_id for c in self.conveyors]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate conveyor_id")
        for c in self.conveyors:
            unknown = set(c.feeds) - set(ids)
            if unknown:
                raise ValueError(f"conveyor {c.conveyor_id} feeds unknown conveyors {sorted(unknown)}")
        return self

    def read_point(self, scan_point_id: str | None) -> PlanReadPoint | None:
        return next((r for r in self.read_points if r.scan_point_id == scan_point_id), None)

    def conveyor(self, conveyor_id: str) -> PlanConveyor:
        return next(c for c in self.conveyors if c.conveyor_id == conveyor_id)
