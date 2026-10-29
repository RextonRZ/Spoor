/* Generated from backend/schemas/HypothesisStatusChange.schema.json by scripts/gen-types.mjs. Do not edit. */

export type ChangeId = string
export type HypothesisId = string
export type HypothesisStatus = ("proposed" | "evaluated" | "supported" | "contradicted" | "insufficient_evidence")
export type ActorKind = ("human" | "agent" | "verifier_service" | "system")
/**
 * user id, agent role + request id, or service name
 */
export type Id = string
/**
 * Model id when kind == agent
 */
export type Model = (string | null)
export type EvidenceIds = string[]
export type Reason = string
export type At = string

/**
 * Append-only status transition with actor and evidence (PRD §11.3).
 */
export interface HypothesisStatusChange {
change_id: ChangeId
hypothesis_id: HypothesisId
from_status: HypothesisStatus
to_status: HypothesisStatus
actor: Actor
evidence_ids?: EvidenceIds
reason: Reason
at: At
}
export interface Actor {
kind: ActorKind
id: Id
model?: Model
}
