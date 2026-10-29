/* Generated from backend/schemas/IdentifierAlias.schema.json by scripts/gen-types.mjs. Do not edit. */

export type AliasId = string
export type FromKey = string
export type ToKey = string
export type LinkedByEventId = (string | null)
export type Basis = ("relabel_scan" | "manual_encode" | "human_confirmed" | "video_candidate")
export type Status = ("active" | "retracted")
export type CreatedAt = string

/**
 * Two identifiers denote the same physical parcel (relabel, manual encode). Without this a relabelled parcel
 * appears to vanish while a new one appears from nowhere: exactly the false 'lost parcel' Spoor must not produce.
 */
export interface IdentifierAlias {
alias_id: AliasId
from_key: FromKey
to_key: ToKey
linked_by_event_id?: LinkedByEventId
basis: Basis
status?: Status
created_at: CreatedAt
}
