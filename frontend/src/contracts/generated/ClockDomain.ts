/* Generated from backend/schemas/ClockDomain.schema.json by scripts/gen-types.mjs. Do not edit. */

export type ClockDomainId = string
export type SiteId = string
export type Kind = ("wcs_plc" | "handheld_fleet" | "nvr" | "camera" | "rfid" | "other")
export type Name = string
export type DeviceIds = string[]
export type CameraIds = string[]

/**
 * A set of devices that share one clock: the sorter WCS/PLC, the handheld fleet, an NVR, a single camera.
 */
export interface ClockDomain {
clock_domain_id: ClockDomainId
site_id: SiteId
kind: Kind
name: Name
device_ids?: DeviceIds
camera_ids?: CameraIds
}
