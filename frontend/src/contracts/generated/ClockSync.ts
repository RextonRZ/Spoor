/* Generated from backend/schemas/ClockSync.schema.json by scripts/gen-types.mjs. Do not edit. */

export type SyncId = string
export type CameraId = (string | null)
export type ClockDomainId = (string | null)
/**
 * normalized_time = device_time + offset_ms (+ drift)
 */
export type OffsetMs = number
export type DriftPpm = number
export type UncertaintyMs = number
/**
 * Device-clock instant drift is measured from
 */
export type DriftReference = (string | null)
export type ValidFrom = (string | null)
export type ValidTo = (string | null)
export type AnchorEventIds = string[]
export type ResidualMsP95 = (number | null)
/**
 * e.g. 'shared clap event at camA f=120 / camB f=133', 'NTP metadata'
 */
export type Method = string
export type AnchorDescription = string
export type CreatedAt = string

/**
 * Offset (and optional drift) from a device clock to the case's normalized timeline (PRD §8.3).
 * 
 * Applies to one camera (`camera_id`) or a whole clock domain (`clock_domain_id`: sorter PLC, handheld fleet, NVR).
 * normalized = device_time + offset_ms + drift_ppm * 1e-6 * (device_time - drift_reference). Never assume synchronous
 * feeds; a fitted sync records its anchors and residuals so the case file can show how time was aligned.
 */
export interface ClockSync {
sync_id: SyncId
camera_id?: CameraId
clock_domain_id?: ClockDomainId
offset_ms: OffsetMs
drift_ppm?: DriftPpm
uncertainty_ms: UncertaintyMs
drift_reference?: DriftReference
valid_from?: ValidFrom
valid_to?: ValidTo
anchor_event_ids?: AnchorEventIds
residual_ms_p95?: ResidualMsP95
method: Method
anchor_description?: AnchorDescription
created_at: CreatedAt
}
