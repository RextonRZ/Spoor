/* Generated from backend/schemas/AgentResponse.schema.json by scripts/gen-types.mjs. Do not edit. */

export type RequestId = string
export type Status = ("ok" | "abstained" | "budget_exhausted" | "error")
export type Kind = ("observation" | "hypothesis")
export type Text = string
export type EvidenceIds = string[]
export type Claims = Claim[]
export type EvidenceIds1 = string[]
export type Unknowns = string[]
export type Conflicts = string[]
export type RecommendedNextTool = (string | null)
export type AbstainReason = (string | null)
export type InputTokens = number
export type OutputTokens = number
export type ToolCalls = number
export type UsdEstimate = (number | null)
export type ModelVersion = string

export interface AgentResponse {
request_id: RequestId
status: Status
claims?: Claims
evidence_ids?: EvidenceIds1
unknowns?: Unknowns
conflicts?: Conflicts
recommended_next_tool?: RecommendedNextTool
abstain_reason?: AbstainReason
cost: AgentCost
model_version: ModelVersion
}
/**
 * `observation` claims must cite evidence; `hypothesis` claims are explicitly unverified.
 */
export interface Claim {
kind: Kind
text: Text
evidence_ids?: EvidenceIds
}
export interface AgentCost {
input_tokens?: InputTokens
output_tokens?: OutputTokens
tool_calls?: ToolCalls
usd_estimate?: UsdEstimate
}
