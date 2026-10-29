/* Generated from backend/schemas/MultiView3DEstimate.schema.json by scripts/gen-types.mjs. Do not edit. */

export type EstimateId = string
export type TargetKind = string
/**
 * @minItems 3
 * @maxItems 3
 */
export type SiteXyzM = [unknown, unknown, unknown]
export type SiteFrame = string
export type Method = string
/**
 * @minItems 2
 */
export type SourceObservationIds = [string, string, ...(string)[]]
export type CorrespondenceId = string
/**
 * @minItems 2
 */
export type CalibrationIds = [string, string, ...(string)[]]
/**
 * Calibration state; runtime tools check the state a method requires (PRD §13.4.2).
 */
export type RigState = ("uncalibrated" | "calibrating" | "validated_floor_only" | "validated_multiview_3d" | "invalidated")
export type SynchronizationId = string
export type Uncertainty3DM = number
export type QualityGatesPassed = string[]
export type SoftwareVersion = string
export type CreatedAt = string

/**
 * Optional, feature-gated (PRD §13.4). Only valid from a validated multi-view rig.
 */
export interface MultiView3DEstimate {
estimate_id: EstimateId
target_kind?: TargetKind
site_xyz_m: SiteXyzM
site_frame?: SiteFrame
method?: Method
source_observation_ids: SourceObservationIds
correspondence_id: CorrespondenceId
calibration_ids: CalibrationIds
rig_state: RigState
synchronization_id: SynchronizationId
reprojection_error_px_by_camera: ReprojectionErrorPxByCamera
uncertainty_3d_m: Uncertainty3DM
quality_gates_passed: QualityGatesPassed
software_version: SoftwareVersion
created_at: CreatedAt
}
export interface ReprojectionErrorPxByCamera {
[k: string]: number | undefined
}
