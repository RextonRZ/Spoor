/* Generated from backend/schemas/Event.schema.json by scripts/gen-types.mjs. Do not edit. */

export type EventId = string
export type CaseId = string
/**
 * e.g. visibility_change, zone_change, contact, door_open
 */
export type Kind = string
export type ObjectInstanceId = (string | null)
/**
 * Object state machine; gaps never collapse into continuous motion (PRD §16.3).
 */
export type ObjectVisibility = ("unobserved" | "visible" | "partially_occluded" | "out_of_view" | "visible_again")
export type ZoneId = (string | null)
export type StartUtc = string
export type EndUtc = string
/**
 * User-visible evidence category for every state and path (PRD §6.2, §18.1).
 */
export type EvidenceLabel = ("observed" | "estimated" | "hypothesized" | "unknown" | "contradicted")
/**
 * @minItems 1
 */
export type ObservationIds = [string, ...(string)[]]
export type SpatialEstimateIds = string[]
export type ActorKind = ("human" | "agent" | "verifier_service" | "system")
/**
 * user id, agent role + request id, or service name
 */
export type Id = string
/**
 * Model id when kind == agent
 */
export type Model = (string | null)
export type CreatedAt = string

/**
 * A temporal state change or interaction backed by observations (PRD §11.1).
 */
export interface Event {
event_id: EventId
case_id: CaseId
kind: Kind
object_instance_id?: ObjectInstanceId
visibility?: (ObjectVisibility | null)
zone_id?: ZoneId
window: TimeWindow
label: EvidenceLabel
observation_ids: ObservationIds
spatial_estimate_ids?: SpatialEstimateIds
actor: Actor
created_at: CreatedAt
}
export interface TimeWindow {
start_utc: StartUtc
end_utc: EndUtc
}
export interface Actor {
kind: ActorKind
id: Id
model?: Model
}
