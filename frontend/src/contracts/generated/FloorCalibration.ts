/* Generated from backend/schemas/FloorCalibration.schema.json by scripts/gen-types.mjs. Do not edit. */

export type CalibrationId = string
export type CameraId = string
export type FloorId = string
export type Version = number
/**
 * Calibration state; runtime tools check the state a method requires (PRD §13.4.2).
 */
export type RigState = ("uncalibrated" | "calibrating" | "validated_floor_only" | "validated_multiview_3d" | "invalidated")
/**
 * @minItems 3
 * @maxItems 3
 */
export type HomographyImageToFloor = [unknown, unknown, unknown]
/**
 * Frame size the image points refer to
 */
export type ImageWhPx = ([unknown, unknown] | null)
export type FitImagePointsPx = [unknown, unknown][]
export type FitFloorPointsM = [unknown, unknown][]
export type HoldoutImagePointsPx = [unknown, unknown][]
export type HoldoutFloorPointsM = [unknown, unknown][]
export type HoldoutErrorMedianM = (number | null)
export type HoldoutErrorP95M = (number | null)
export type Undistorted = boolean
export type Method = string
export type SoftwareVersion = string
export type CreatedAt = string
export type Notes = string

/**
 * A versioned image->floor homography. A new calibration is a new record; old ones are kept (PRD §16.4).
 */
export interface FloorCalibration {
calibration_id: CalibrationId
camera_id: CameraId
floor_id: FloorId
version: Version
rig_state: RigState
homography_image_to_floor: HomographyImageToFloor
image_wh_px?: ImageWhPx
fit_image_points_px: FitImagePointsPx
fit_floor_points_m: FitFloorPointsM
holdout_image_points_px?: HoldoutImagePointsPx
holdout_floor_points_m?: HoldoutFloorPointsM
holdout_error_median_m?: HoldoutErrorMedianM
holdout_error_p95_m?: HoldoutErrorP95M
undistorted?: Undistorted
method?: Method
software_version: SoftwareVersion
created_at: CreatedAt
notes?: Notes
}
