/* Generated from backend/schemas/VoiceTranscript.schema.json by scripts/gen-types.mjs. Do not edit. */

export type VoiceTranscriptId = string
export type CaseId = string
export type Kind = ("search_note" | "complaint_call")
export type SearchTaskId = (string | null)
export type AreaId = (string | null)
export type AudioSha256 = string
export type AudioDurationMs = number
export type SampleRateHz = (16000 | 24000)
export type Mode = ("PUSH_TO_TALK" | "ENDPOINTING" | "DIARIZATION")
export type Transcript = string
export type TurnId = number
/**
 * model speaker label (A, B…), DIARIZATION only
 */
export type Speaker = (string | null)
export type StartMs = number
export type EndMs = number
export type Text = string
export type Turns = VoiceTurn[]
export type Model = string
export type SessionId = (string | null)
export type UsdEstimate = number
/**
 * pseudonymous user id of the person who uploaded it
 */
export type RecordedBy = string
export type RecordedAt = string
export type Label = string
export type ContentSha256 = string

export interface VoiceTranscript {
voice_transcript_id: VoiceTranscriptId
case_id: CaseId
kind: Kind
search_task_id?: SearchTaskId
area_id?: AreaId
audio_sha256: AudioSha256
audio_duration_ms: AudioDurationMs
sample_rate_hz: SampleRateHz
mode: Mode
transcript: Transcript
turns: Turns
model: Model
session_id?: SessionId
usd_estimate: UsdEstimate
recorded_by: RecordedBy
recorded_at: RecordedAt
label?: Label
content_sha256: ContentSha256
}
export interface VoiceTurn {
turn_id: TurnId
speaker?: Speaker
start_ms: StartMs
end_ms: EndMs
text: Text
}
