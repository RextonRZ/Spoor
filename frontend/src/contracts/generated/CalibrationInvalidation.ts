/* Generated from backend/schemas/CalibrationInvalidation.schema.json by scripts/gen-types.mjs. Do not edit. */

export type CalibrationId = string
export type Reason = string
export type InvalidatedAt = string
export type InvalidatedBy = string

export interface CalibrationInvalidation {
calibration_id: CalibrationId
reason: Reason
invalidated_at: InvalidatedAt
invalidated_by: InvalidatedBy
}
