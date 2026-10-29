/* Generated from backend/schemas/VerifiedFinding.schema.json by scripts/gen-types.mjs. Do not edit. */

export type FindingId = string
export type CaseId = string
export type Statement = string
/**
 * @minItems 1
 */
export type ObservationIds = [string, ...(string)[]]
export type SpatialEstimateIds = string[]
export type FindingStatus = ("supported_by_video" | "supported_by_sensor" | "supported_by_video_and_sensor")
export type Limitations = string[]
export type ActorKind = ("human" | "agent" | "verifier_service" | "system")
/**
 * user id, agent role + request id, or service name
 */
export type Id = string
/**
 * Model id when kind == agent
 */
export type Model = (string | null)
export type At = string

/**
 * A verified summary assertion — investigation support, not a legal finding (PRD §11.2, §22.3).
 */
export interface VerifiedFinding {
finding_id: FindingId
case_id: CaseId
statement: Statement
observation_ids: ObservationIds
spatial_estimate_ids?: SpatialEstimateIds
verification_status: FindingStatus
limitations?: Limitations
verified_by: Actor
at: At
}
export interface Actor {
kind: ActorKind
id: Id
model?: Model
}
