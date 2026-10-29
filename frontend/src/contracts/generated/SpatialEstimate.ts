/* Generated from backend/schemas/SpatialEstimate.schema.json by scripts/gen-types.mjs. Do not edit. */

export type EstimateId = string
/**
 * @minItems 1
 */
export type ObservationIds = [string, ...(string)[]]
/**
 * How a position was obtained; every rendered marker carries one (PRD §13.5).
 */
export type SpatialMode = ("multiview_xyz" | "floor_xy" | "anchored_height" | "zone_only" | "image_only" | "unknown")
export type FloorId = (string | null)
export type FloorXyM = ([unknown, unknown] | null)
/**
 * Only for anchored_height, from a measured surface
 */
export type HeightM = (number | null)
export type ZoneId = (string | null)
export type UncertaintyRadiusM = (number | null)
export type Method = string
export type CalibrationId = (string | null)
export type Status = string
export type CreatedAt = string

/**
 * A position derived from observations, separate from them and always carrying its basis (PRD §11.2).
 */
export interface SpatialEstimate {
estimate_id: EstimateId
observation_ids: ObservationIds
spatial_mode: SpatialMode
floor_id?: FloorId
floor_xy_m?: FloorXyM
height_m?: HeightM
zone_id?: ZoneId
uncertainty_radius_m?: UncertaintyRadiusM
method: Method
calibration_id?: CalibrationId
status?: Status
created_at: CreatedAt
}
