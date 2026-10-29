/* Generated from backend/schemas/MediaAsset.schema.json by scripts/gen-types.mjs. Do not edit. */

export type MediaId = string
export type SiteId = string
export type CameraId = (string | null)
/**
 * Distinguished on every UI surface and export (PRD §7.3).
 */
export type AssetKind = ("original" | "annotated_derivative" | "working_derivative" | "estimated_geometry" | "illustrative")
export type Sha256 = string
export type ByteSize = number
export type MimeType = string
/**
 * Stored as data only; never interpolated into prompts (PRD §7.4)
 */
export type OriginalFilename = string
export type Container = string
export type VideoCodec = string
export type WidthPx = number
export type HeightPx = number
export type RotationDeg = number
export type DurationMs = number
export type AvgFps = (number | null)
export type NominalFps = (number | null)
export type VariableFrameRate = boolean
export type FrameCount = (number | null)
export type TimeBase = (string | null)
export type HasAudio = boolean
export type CreationTimeUtc = (string | null)
/**
 * e.g. non_monotonic_pts, rotated, missing_pts
 */
export type Flags = string[]
export type ParentMediaId = (string | null)
/**
 * e.g. ffmpeg command template id
 */
export type ProcessingMethod = (string | null)
export type SoftwareVersion = (string | null)
export type AuthorizationId = string
export type IngestedAt = string
export type IngestedBy = string

export interface MediaAsset {
media_id: MediaId
site_id: SiteId
camera_id?: CameraId
kind: AssetKind
sha256: Sha256
byte_size: ByteSize
mime_type: MimeType
original_filename: OriginalFilename
probe?: (MediaProbe | null)
parent_media_id?: ParentMediaId
processing_method?: ProcessingMethod
software_version?: SoftwareVersion
authorization_id: AuthorizationId
ingested_at: IngestedAt
ingested_by: IngestedBy
}
/**
 * Facts read from the container by ffprobe, kept verbatim alongside derived flags.
 */
export interface MediaProbe {
container: Container
video_codec: VideoCodec
width_px: WidthPx
height_px: HeightPx
rotation_deg?: RotationDeg
duration_ms: DurationMs
avg_fps?: AvgFps
nominal_fps?: NominalFps
variable_frame_rate?: VariableFrameRate
frame_count?: FrameCount
time_base?: TimeBase
has_audio?: HasAudio
creation_time_utc?: CreationTimeUtc
flags?: Flags
}
