/* Generated from backend/schemas/Hypothesis.schema.json by scripts/gen-types.mjs. Do not edit. */

export type HypothesisId = string
export type CaseId = string
export type Claim = string
export type SupportObservationIds = string[]
export type AgainstObservationIds = string[]
export type MissingEvidence = string[]
export type HypothesisStatus = ("proposed" | "evaluated" | "supported" | "contradicted" | "insufficient_evidence")
export type NextAction = (string | null)
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
 * An explanation under investigation. Its status only changes through HypothesisStatusChange.
 */
export interface Hypothesis {
hypothesis_id: HypothesisId
case_id: CaseId
claim: Claim
support_observation_ids?: SupportObservationIds
against_observation_ids?: AgainstObservationIds
missing_evidence?: MissingEvidence
status?: HypothesisStatus
next_action?: NextAction
proposed_by: Actor
created_at: CreatedAt
}
export interface Actor {
kind: ActorKind
id: Id
model?: Model
}
