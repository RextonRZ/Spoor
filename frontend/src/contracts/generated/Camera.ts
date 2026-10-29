/* Generated from backend/schemas/Camera.schema.json by scripts/gen-types.mjs. Do not edit. */

export type CameraId = string
export type SiteId = string
export type FloorId = string
export type Name = string
/**
 * @minItems 2
 * @maxItems 2
 */
export type ResolutionWhPx = [unknown, unknown]
export type PositionM = ([unknown, unknown, unknown] | null)
export type PositionMeasured = boolean
export type YawDeg = (number | null)
export type HfovDeg = (number | null)
export type OrientationMeasured = boolean
export type FovPolygonM = ([unknown, unknown][] | null)
export type ValidFrom = (string | null)
export type ValidUntil = (string | null)

export interface Camera {
camera_id: CameraId
site_id: SiteId
floor_id: FloorId
name: Name
resolution_wh_px: ResolutionWhPx
position_m?: PositionM
position_measured?: PositionMeasured
yaw_deg?: YawDeg
hfov_deg?: HfovDeg
orientation_measured?: OrientationMeasured
fov_polygon_m?: FovPolygonM
zone_image_regions_px?: ZoneImageRegionsPx
valid_from?: ValidFrom
valid_until?: ValidUntil
}
export interface ZoneImageRegionsPx {
/**
 * This interface was referenced by `ZoneImageRegionsPx`'s JSON-Schema definition
 * via the `patternProperty` "^zone_[A-Za-z0-9][A-Za-z0-9_-]*$".
 */
[k: string]: [unknown, unknown][] | undefined
}
