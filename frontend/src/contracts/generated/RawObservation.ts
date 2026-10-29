/* Generated from backend/schemas/RawObservation.schema.json by scripts/gen-types.mjs. Do not edit. */

export type ObservationId = string
export type SourceType = ("video" | "sensor_real" | "sensor_simulated" | "scan_real" | "scan_simulated" | "human_annotation")
export type CameraId = (string | null)
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
export type SensorEventId = (string | null)
export type TrackId = (string | null)
export type Label = string
export type BboxXyxyPx = ([unknown, unknown, unknown, unknown] | null)
export type FrameWhPx = ([unknown, unknown] | null)
export type MaskAssetId = (string | null)
export type FloorContactUvPx = ([unknown, unknown] | null)
export type Observed = boolean
export type QualityFlags = string[]
export type Model = string
export type ModelVersion = string
export type Provider = string
/**
 * Provider response/operation id
 */
export type RequestId = (string | null)
/**
 * Exact prompt sent (noun phrase or prompt tokens)
 */
export type Prompt = (string | null)
export type PromptTemplateVersion = (string | null)
export type CacheKey = (string | null)
export type ConfidenceRaw = (number | null)
export type ConfidenceCalibrated = (number | null)
export type ConfidenceCalibrationId = (string | null)
export type CreatedAt = string

/**
 * A video- or sensor-derived observation. Never produced from user-facing narrative (PRD §11.2).
 */
export interface RawObservation {
observation_id: ObservationId
source_type: SourceType
camera_id?: CameraId
source_frame?: (FrameRef | null)
sensor_event_id?: SensorEventId
track_id?: TrackId
label: Label
bbox_xyxy_px?: BboxXyxyPx
frame_wh_px?: FrameWhPx
mask_asset_id?: MaskAssetId
floor_contact_uv_px?: FloorContactUvPx
observed?: Observed
quality_flags?: QualityFlags
provenance?: (ModelProvenance | null)
confidence_raw?: ConfidenceRaw
confidence_calibrated?: ConfidenceCalibrated
confidence_calibration_id?: ConfidenceCalibrationId
created_at: CreatedAt
}
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
/**
 * Which model produced something, with what input. `confidence_raw` is only meaningful within this model.
 */
export interface ModelProvenance {
model: Model
model_version: ModelVersion
provider: Provider
request_id?: RequestId
prompt?: Prompt
prompt_template_version?: PromptTemplateVersion
cache_key?: CacheKey
}
