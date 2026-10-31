/* Generated from backend/schemas/SitePlan.schema.json by scripts/gen-types.mjs. Do not edit. */

export type PlanId = string
export type SiteId = string
/**
 * Where the plan came from, e.g. 'CAD export 2026-10 + machine spec'
 */
export type Source = string
/**
 * @minItems 3
 */
export type OutlineM = [[unknown, unknown], [unknown, unknown], [unknown, unknown], ...([unknown, unknown])[]]
export type EavesM = (number | null)
export type AreaId = string
export type Kind = ("zone" | "walkway" | "rack" | "bench" | "cage_bay" | "blind_spot" | "store" | "machine")
export type Name = string
/**
 * @minItems 3
 */
export type PolygonM = [[unknown, unknown], [unknown, unknown], [unknown, unknown], ...([unknown, unknown])[]]
export type HeightM = (number | null)
export type ZoneId = (string | null)
/**
 * A person can walk here (walkways, open floor of zones); racks/benches: no
 */
export type Walkable = boolean
export type Areas = PlanArea[]
export type ConveyorId = string
export type Kind1 = ("belt" | "telescopic" | "loop" | "chute")
/**
 * @minItems 2
 */
export type PathM = [[unknown, unknown], [unknown, unknown], ...([unknown, unknown])[]]
/**
 * @minItems 1
 */
export type DeckHeightsM = [number, ...(number)[]]
export type Closed = boolean
/**
 * Belt speed from the machine spec; None = unknown
 */
export type SpeedMps = (number | null)
export type Feeds = string[]
export type Conveyors = PlanConveyor[]
export type DoorId = string
/**
 * dock, personnel, fire exit, cage entrance …
 */
export type Kind2 = string
/**
 * @minItems 2
 * @maxItems 2
 */
export type CentreM = [unknown, unknown]
export type WidthM = number
export type Wall = ("N" | "S" | "E" | "W" | "inner")
/**
 * Leads out of the building
 */
export type Exit = boolean
export type Doors = PlanDoor[]
export type ScanPointId = string
export type DeviceKind = string
/**
 * @minItems 3
 * @maxItems 3
 */
export type PositionM = [unknown, unknown, unknown]
export type ZoneId1 = (string | null)
/**
 * Cameras with a clear view of it (plan check)
 */
export type VisibleBy = string[]
export type ReadPoints = PlanReadPoint[]
export type CameraId = string
/**
 * @minItems 3
 * @maxItems 3
 */
export type PositionM1 = [unknown, unknown, unknown]
export type HeadingDeg = number
export type TiltDownDeg = number
export type HfovDeg = number
export type VfovDeg = number
/**
 * @minItems 2
 * @maxItems 2
 */
export type ResolutionWhPx = [unknown, unknown]
export type Label = (string | null)
export type Cameras = PlanCamera[]
export type WalkSpeedMps = number
export type WalkSpeedMaxMps = number
export type CreatedBy = string
export type CreatedAt = string

/**
 * One version of a site's plan. A new import is a new record; answers cite the plan_id they were computed on.
 */
export interface SitePlan {
plan_id: PlanId
site_id: SiteId
source: Source
outline_m: OutlineM
eaves_m?: EavesM
areas?: Areas
conveyors?: Conveyors
doors?: Doors
read_points?: ReadPoints
cameras?: Cameras
walk_speed_mps?: WalkSpeedMps
walk_speed_max_mps?: WalkSpeedMaxMps
created_by: CreatedBy
created_at: CreatedAt
}
export interface PlanArea {
area_id: AreaId
kind: Kind
name: Name
polygon_m: PolygonM
height_m?: HeightM
zone_id?: ZoneId
walkable: Walkable
}
/**
 * A conveyor centreline in travel direction. `feeds` lists the conveyors it discharges onto: an open conveyor
 * hands over at its end; a closed one (sorter loop) hands over where the next conveyor starts (e.g. a chute mouth).
 */
export interface PlanConveyor {
conveyor_id: ConveyorId
kind: Kind1
path_m: PathM
deck_heights_m: DeckHeightsM
closed?: Closed
speed_mps?: SpeedMps
feeds?: Feeds
}
export interface PlanDoor {
door_id: DoorId
kind: Kind2
centre_m: CentreM
width_m: WidthM
wall: Wall
exit?: Exit
}
/**
 * A scan point (station id in the scan log). `event_positions` says where an event kind physically happens when
 * that is not at the device itself, e.g. the sorter PLC reports a carrier assignment at the merge onto the loop.
 */
export interface PlanReadPoint {
scan_point_id: ScanPointId
device_kind: DeviceKind
position_m: PositionM
zone_id?: ZoneId1
event_positions?: EventPositions
visible_by?: VisibleBy
}
export interface EventPositions {
/**
 * @minItems 2
 * @maxItems 2
 */
[k: string]: [unknown, unknown] | undefined
}
export interface PlanCamera {
camera_id: CameraId
position_m: PositionM1
heading_deg: HeadingDeg
tilt_down_deg: TiltDownDeg
hfov_deg: HfovDeg
vfov_deg: VfovDeg
resolution_wh_px: ResolutionWhPx
label?: Label
}
