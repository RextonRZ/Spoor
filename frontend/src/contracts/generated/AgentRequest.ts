/* Generated from backend/schemas/AgentRequest.schema.json by scripts/gen-types.mjs. Do not edit. */

export type CaseId = string
export type RequestId = string
export type AgentRole = ("lead" | "evidence" | "hypothesis" | "verifier")
export type Question = string
export type CameraIds = string[]
export type StartUtc = string
export type EndUtc = string
export type ObjectInstanceIds = string[]
export type AvailableTools = string[]
export type TokenBudget = number
export type MaxSteps = number
export type Deadline = string
export type OutputSchema = string

export interface AgentRequest {
case_id: CaseId
request_id: RequestId
role: AgentRole
question: Question
evidence_scope: EvidenceScope
available_tools: AvailableTools
token_budget: TokenBudget
max_steps: MaxSteps
deadline: Deadline
output_schema: OutputSchema
}
export interface EvidenceScope {
camera_ids?: CameraIds
window?: (TimeWindow | null)
object_instance_ids?: ObjectInstanceIds
}
export interface TimeWindow {
start_utc: StartUtc
end_utc: EndUtc
}
