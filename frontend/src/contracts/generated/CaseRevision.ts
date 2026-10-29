/* Generated from backend/schemas/CaseRevision.schema.json by scripts/gen-types.mjs. Do not edit. */

export type CaseRevisionId = string
export type CaseId = string
export type ParentRevisionId = (string | null)
export type ActorKind = ("human" | "agent" | "verifier_service" | "system")
/**
 * user id, agent role + request id, or service name
 */
export type Id = string
/**
 * Model id when kind == agent
 */
export type Model = (string | null)
export type Reason = string
export type ChangedIds = string[]
export type At = string

/**
 * Immutable snapshot pointer: every change to case state produces a new revision (PRD §11.1).
 */
export interface CaseRevision {
case_revision_id: CaseRevisionId
case_id: CaseId
parent_revision_id: ParentRevisionId
actor: Actor
reason: Reason
changed_ids: ChangedIds
at: At
}
export interface Actor {
kind: ActorKind
id: Id
model?: Model
}
