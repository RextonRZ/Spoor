/* Generated from backend/schemas/SensorEvent.schema.json by scripts/gen-types.mjs. Do not edit. */

export type SensorEventId = string
export type SiteId = string
export type SourceType = ("video" | "sensor_real" | "sensor_simulated" | "scan_real" | "scan_simulated" | "human_annotation")
export type DeviceId = string
export type SensorKind = ("door_contact" | "weight_delta_kg" | "rfid_tag_seen" | "motion_trigger")
export type Value = (string | number | boolean)
export type ZoneId = (string | null)
export type DeviceTimeUtc = string
/**
 * e.g. 'ntp', 'unsynced', 'manual offset ±2s'
 */
export type ClockQuality = string
export type ImportBatch = string

/**
 * Vendor-neutral sensor event (PRD §20). Corroborates; never identifies who or what.
 */
export interface SensorEvent {
sensor_event_id: SensorEventId
site_id: SiteId
source_type: SourceType
device_id: DeviceId
kind: SensorKind
value: Value
zone_id?: ZoneId
device_time_utc: DeviceTimeUtc
clock_quality: ClockQuality
import_batch: ImportBatch
}
