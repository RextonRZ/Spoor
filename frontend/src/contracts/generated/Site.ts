/* Generated from backend/schemas/Site.schema.json by scripts/gen-types.mjs. Do not edit. */

export type SiteId = string
export type Name = string
export type Frame = string
/**
 * How dimensions were obtained, e.g. 'tape measure, ±2 cm'
 */
export type MeasurementMethod = string
/**
 * @minItems 1
 */
export type Floors = [Floor, ...(Floor)[]]
export type FloorId = string
export type Name1 = string
export type ElevationM = number
/**
 * @minItems 3
 */
export type OutlineM = [[unknown, unknown], [unknown, unknown], [unknown, unknown], ...([unknown, unknown])[]]
export type ZoneId = string
export type FloorId1 = string
export type Name2 = string
export type ZoneKind = ("shelf" | "desk" | "door" | "hallway" | "walkway" | "other")
/**
 * @minItems 3
 */
export type PolygonM = [[unknown, unknown], [unknown, unknown], [unknown, unknown], ...([unknown, unknown])[]]
export type SurfaceHeightM = (number | null)
/**
 * True if surveyed in the room; False if approximate
 */
export type Measured = boolean
export type Zones = Zone[]

export interface Site {
site_id: SiteId
name: Name
frame?: Frame
measurement_method: MeasurementMethod
floors: Floors
zones?: Zones
}
export interface Floor {
floor_id: FloorId
name: Name1
elevation_m?: ElevationM
outline_m: OutlineM
}
export interface Zone {
zone_id: ZoneId
floor_id: FloorId1
name: Name2
kind: ZoneKind
polygon_m: PolygonM
surface_height_m?: SurfaceHeightM
measured: Measured
}
