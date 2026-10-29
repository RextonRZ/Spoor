/* Generated from backend/schemas/MediaAuthorization.schema.json by scripts/gen-types.mjs. Do not edit. */

export type AuthorizationId = string
export type SiteId = string
export type Uploader = string
export type RightsStatement = string
export type Purpose = string
/**
 * Uploader confirms recording rights and that notices/consent are in place
 */
export type ConsentConfirmed = true
/**
 * May this footage be sent to hosted model providers (Meta Model API, Baseten)?
 */
export type HostedProcessingAllowed = boolean
export type RetentionUntil = string
export type RecordedAt = string
/**
 * Declared by the uploader; drives the provenance label in reports (PRD §27.1)
 */
export type RecordingKind = (("staged_event" | "real_incident" | "synthetic_test") | null)

/**
 * Required before any upload is accepted (PRD §7.1).
 */
export interface MediaAuthorization {
authorization_id: AuthorizationId
site_id: SiteId
uploader: Uploader
rights_statement: RightsStatement
purpose: Purpose
consent_confirmed: ConsentConfirmed
hosted_processing_allowed: HostedProcessingAllowed
retention_until: RetentionUntil
recorded_at: RecordedAt
recording_kind?: RecordingKind
}
