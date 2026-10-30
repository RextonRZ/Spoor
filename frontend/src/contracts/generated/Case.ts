/* Generated from backend/schemas/Case.schema.json by scripts/gen-types.mjs. Do not edit. */

export type CaseId = string
export type SiteId = string
/**
 * Investigator's question; data, not instructions to agents
 */
export type Question = string
/**
 * Concrete visual noun phrase, e.g. 'blue case'
 */
export type TargetDescription = string
export type CameraIds = string[]
export type StartUtc = string
export type EndUtc = string
export type CreatedBy = string
export type CreatedAt = string
/**
 * Courier claim / complaint ref.
 */
export type ClaimReference = (string | null)
/**
 * The customer's complaint, as reported
 */
export type Complaint = (string | null)
/**
 * When the customer reported it
 */
export type ReportedAt = (string | null)

export interface Case {
case_id: CaseId
site_id: SiteId
question: Question
target_description: TargetDescription
camera_ids?: CameraIds
window?: (TimeWindow | null)
created_by: CreatedBy
created_at: CreatedAt
claim_reference?: ClaimReference
complaint?: Complaint
reported_at?: ReportedAt
}
export interface TimeWindow {
start_utc: StartUtc
end_utc: EndUtc
}
