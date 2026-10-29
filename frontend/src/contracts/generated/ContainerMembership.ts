/* Generated from backend/schemas/ContainerMembership.schema.json by scripts/gen-types.mjs. Do not edit. */

export type MembershipId = string
export type Version = number
/**
 * '<scheme>:<value>' of the parcel or container inside
 */
export type ChildKey = string
/**
 * 'container:<value>' of the enclosing container
 */
export type ParentKey = string
export type ValidFrom = string
export type ValidTo = (string | null)
export type OpenedByEventId = (string | null)
export type ClosedByEventId = (string | null)
export type Basis = ("scan" | "video_observed" | "inferred")
export type LinkStatus = ("active" | "closed" | "contradicted" | "retracted")
export type Reason = string
export type CreatedAt = string

/**
 * 'child was inside parent from valid_from to valid_to'. Versioned: a change is a new version, history kept.
 * Location inherited through membership is a presumption 'until contradicted' (EPCIS AggregationEvent), shown as
 * estimated, never observed.
 */
export interface ContainerMembership {
membership_id: MembershipId
version: Version
child_key: ChildKey
parent_key: ParentKey
valid_from: ValidFrom
valid_to?: ValidTo
opened_by_event_id?: OpenedByEventId
closed_by_event_id?: ClosedByEventId
basis: Basis
status: LinkStatus
reason?: Reason
created_at: CreatedAt
}
