/* Generated from backend/schemas/TrackAssociation.schema.json by scripts/gen-types.mjs. Do not edit. */

export type ObjectInstanceId = string
export type TrackId = string
/**
 * Cross-track link status (PRD §14.3 step 8).
 */
export type AssociationStatus = ("verified_same_camera" | "scan_bound" | "candidate_cross_camera" | "human_confirmed" | "rejected" | "unresolved")
export type Reason = string
export type Version = number
export type CreatedAt = string
export type CreatedBy = string

/**
 * Hypothesized link of a track to a provisional physical object. Versioned, never silently merged (§14.3).
 */
export interface TrackAssociation {
object_instance_id: ObjectInstanceId
track_id: TrackId
status: AssociationStatus
signals?: Signals
reason: Reason
version: Version
created_at: CreatedAt
created_by: CreatedBy
}
/**
 * appearance/temporal/topology scores
 */
export interface Signals {
[k: string]: number | undefined
}
