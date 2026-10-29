/* Generated from backend/schemas/ScanEvent.schema.json by scripts/gen-types.mjs. Do not edit. */

export type ScanEventId = string
export type SiteId = string
export type SourceType = ("video" | "sensor_real" | "sensor_simulated" | "scan_real" | "scan_simulated" | "human_annotation")
export type ImportBatch = string
export type IdentifierScheme = ("s10" | "sscc" | "carrier_waybill" | "internal" | "dl_uri" | "container")
export type Value = string
export type CheckDigitValid = (boolean | null)
export type Identifiers = ParcelIdentifier[]
export type ReadOutcome = ("read" | "no_read" | "no_solve" | "multi_read")
export type ScanEventKind = ("arrived_facility" | "inducted" | "tunnel_read" | "return_inducted" | "tunnel_no_read" | "sort_assigned" | "divert_confirmed" | "recirculated" | "exception_diverted" | "manual_encoded" | "relabeled" | "damage_hold" | "missort_detected" | "container_add" | "container_closed" | "container_remove" | "container_loaded" | "departed_facility" | "case_opened" | "case_closed")
export type RawCode = (string | null)
/**
 * Stored as data, never prompts
 */
export type RawDescription = (string | null)
export type ReasonCode = (string | null)
export type ActionCode = (string | null)
export type EpcisAction = (("ADD" | "OBSERVE" | "DELETE") | null)
export type BizStep = (string | null)
export type Disposition = (string | null)
export type DeviceTimeUtc = string
export type RecordTimeUtc = (string | null)
export type ClockDomainId = (string | null)
export type DeviceId = string
export type DeviceKind = ("tunnel" | "dws_static" | "sorter_plc" | "ship_sorter" | "handheld" | "rfid_portal")
export type StationId = (string | null)
/**
 * Zone of the read point (camera FOV lookup)
 */
export type ReadPointZoneId = (string | null)
export type BizLocationId = (string | null)
export type SortDestinationAssigned = (string | null)
export type SortDestinationActual = (string | null)
export type DivertConfirmed = (boolean | null)
export type ContainerType = ("bag" | "cage" | "pallet" | "gaylord" | "trailer")
export type WeightG = (number | null)
export type DimsMm = ([unknown, unknown, unknown] | null)
export type ImageRefs = string[]
export type OperatorRef = (string | null)
export type CorrectsScanEventId = (string | null)
export type CorrectionReason = (("did_not_occur" | "incorrect_data") | null)

/**
 * One barcode/RFID read or machine event about a parcel or container. Append-only; corrections are new events
 * that point at the event they correct (EPCIS errorDeclaration), never edits.
 */
export interface ScanEvent {
scan_event_id: ScanEventId
site_id: SiteId
source_type: SourceType
import_batch: ImportBatch
identifiers?: Identifiers
read_outcome?: ReadOutcome
event_kind: ScanEventKind
raw_code?: RawCode
raw_description?: RawDescription
reason_code?: ReasonCode
action_code?: ActionCode
epcis_action?: EpcisAction
biz_step?: BizStep
disposition?: Disposition
device_time_utc: DeviceTimeUtc
record_time_utc?: RecordTimeUtc
clock_domain_id?: ClockDomainId
device_id: DeviceId
device_kind: DeviceKind
station_id?: StationId
read_point_zone_id?: ReadPointZoneId
biz_location_id?: BizLocationId
sort_destination_assigned?: SortDestinationAssigned
sort_destination_actual?: SortDestinationActual
divert_confirmed?: DivertConfirmed
container?: (ParcelIdentifier | null)
container_type?: (ContainerType | null)
parent_container?: (ParcelIdentifier | null)
weight_g?: WeightG
dims_mm?: DimsMm
image_refs?: ImageRefs
operator_ref?: OperatorRef
corrects_scan_event_id?: CorrectsScanEventId
correction_reason?: CorrectionReason
}
/**
 * One identifier on a parcel or container. A parcel can carry several at once (waybill + SSCC + S10).
 */
export interface ParcelIdentifier {
scheme: IdentifierScheme
value: Value
check_digit_valid?: CheckDigitValid
}
