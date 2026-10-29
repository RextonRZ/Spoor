/* Generated from backend/schemas/CameraCoverage.schema.json by scripts/gen-types.mjs. Do not edit. */

export type CoverageId = string
export type CameraId = string
export type MediaId = string
export type StartUtc = string
export type EndUtc = string
export type SyncId = string
export type TimeUncertaintyMs = number

/**
 * A recorded interval of one camera on the normalized timeline — what *could* have been seen (PRD §16.1).
 */
export interface CameraCoverage {
coverage_id: CoverageId
camera_id: CameraId
media_id: MediaId
start_utc: StartUtc
end_utc: EndUtc
sync_id: SyncId
time_uncertainty_ms: TimeUncertaintyMs
}
