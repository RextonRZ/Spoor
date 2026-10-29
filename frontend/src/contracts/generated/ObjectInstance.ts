/* Generated from backend/schemas/ObjectInstance.schema.json by scripts/gen-types.mjs. Do not edit. */

export type ObjectInstanceId = string
export type CaseId = string
export type Label = string
export type IdentifierScheme = ("s10" | "sscc" | "carrier_waybill" | "internal" | "dl_uri" | "container")
export type Value = string
export type CheckDigitValid = (boolean | null)
export type Identifiers = ParcelIdentifier[]
export type CreatedBy = string
export type CreatedAt = string

/**
 * A provisional physical object within a case, e.g. 'the blue equipment case'. Tracks link to it only through
 * TrackAssociation records; it is never a person (PRD §11.1, §7.2).
 */
export interface ObjectInstance {
object_instance_id: ObjectInstanceId
case_id: CaseId
label: Label
identifiers?: Identifiers
created_by: CreatedBy
created_at: CreatedAt
}
/**
 * One identifier on a parcel or container. A parcel can carry several at once (waybill + SSCC + S10).
 */
export interface ParcelIdentifier {
scheme: IdentifierScheme
value: Value
check_digit_valid?: CheckDigitValid
}
