/* Generated from backend/schemas/Track.schema.json by scripts/gen-types.mjs. Do not edit. */

export type TrackId = string
export type CameraId = string
export type MediaId = string
export type Label = string
/**
 * SAM object id within one response
 */
export type ProviderObjectId = string
export type FirstFrameIndex = number
export type LastFrameIndex = number
export type Model = string
export type ModelVersion = string
export type Provider = string
/**
 * Provider response/operation id
 */
export type RequestId = (string | null)
/**
 * Exact prompt sent (noun phrase or prompt tokens)
 */
export type Prompt = (string | null)
export type PromptTemplateVersion = (string | null)
export type CacheKey = (string | null)

/**
 * Ephemeral per-camera, per-clip track. Not a person's identity and not persistent across cameras (§7.2).
 */
export interface Track {
track_id: TrackId
camera_id: CameraId
media_id: MediaId
label: Label
provider_object_id: ProviderObjectId
first_frame_index: FirstFrameIndex
last_frame_index: LastFrameIndex
provenance: ModelProvenance
}
/**
 * Which model produced something, with what input. `confidence_raw` is only meaningful within this model.
 */
export interface ModelProvenance {
model: Model
model_version: ModelVersion
provider: Provider
request_id?: RequestId
prompt?: Prompt
prompt_template_version?: PromptTemplateVersion
cache_key?: CacheKey
}
