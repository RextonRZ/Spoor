/* Generated from backend/schemas/LegalContext.schema.json by scripts/gen-types.mjs. Do not edit. */

export type LegalContextId = string
export type SiteId = string
export type Jurisdiction = "MY"
export type Model = string
export type Provider = "meta_model_api"
export type ResponseIds = string[]
export type Question = string
export type Text = string
/**
 * @minItems 1
 */
export type Sources = [number, ...(number)[]]
export type Sentences = ContextSentence[]
/**
 * sentences the model wrote without a citation (not shown)
 */
export type DroppedUncited = number
/**
 * the model's own tool narration, e.g. 'Now I'll open…'
 */
export type DroppedNarration = number
export type Searches = number
export type Answers = ContextAnswer[]
/**
 * citation number as shown in the report, [n]
 */
export type N = number
export type Url = string
export type Title = string
export type Domain = string
/**
 * a .gov.my source (statute portal, regulator)
 */
export type Official = boolean
export type Sources1 = ContextSource[]
export type Searches1 = number
export type UsdEstimate = number
export type RetrievedAt = string
export type Label = string
export type ContentSha256 = string

export interface LegalContext {
legal_context_id: LegalContextId
site_id: SiteId
jurisdiction?: Jurisdiction
model: Model
provider?: Provider
response_ids: ResponseIds
answers: Answers
sources: Sources1
searches: Searches1
usd_estimate: UsdEstimate
retrieved_at: RetrievedAt
label?: Label
content_sha256: ContentSha256
}
export interface ContextAnswer {
question: Question
sentences: Sentences
dropped_uncited: DroppedUncited
dropped_narration?: DroppedNarration
searches: Searches
}
export interface ContextSentence {
text: Text
sources: Sources
}
export interface ContextSource {
n: N
url: Url
title: Title
domain: Domain
official: Official
}
