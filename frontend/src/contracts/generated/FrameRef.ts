/* Generated from backend/schemas/FrameRef.schema.json by scripts/gen-types.mjs. Do not edit. */

export type MediaId = string
/**
 * Presentation time in the media's own timeline
 */
export type PtsMs = number
export type FrameIndex = number
export type CameraClockUtc = (string | null)
export type NormalizedUtc = (string | null)
export type SyncId = (string | null)
export type TimeUncertaintyMs = (number | null)

/**
 * Points at one frame of one media asset; every citation resolves through this (PRD §11.1).
 */
export interface FrameRef {
media_id: MediaId
pts_ms: PtsMs
frame_index: FrameIndex
camera_clock_utc?: CameraClockUtc
normalized_utc?: NormalizedUtc
sync_id?: SyncId
time_uncertainty_ms?: TimeUncertaintyMs
}
