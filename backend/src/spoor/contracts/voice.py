"""Voice notes and complaint calls (QUEUE J4): Muse Voice Transcribe turns a recording into speaker turns.

The ORIGINAL audio is the evidence: it is stored as received and named by its SHA-256. The transcript is a machine
reading of it (model, mode, session id), kept with per-turn times so a reader can check any line against the audio.
A floor-search voice note is a person's statement (pseudonymous user id, place, time); a complaint call is case input.
Speaker labels are the model's ("A", "B"), never names."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, StringConstraints

from .base import CaseId, ImmutableRecord, Sha256

VoiceTranscriptId = Annotated[
    str, StringConstraints(pattern=r"^vtr_[A-Za-z0-9][A-Za-z0-9_-]*$", max_length=96)
]


class VoiceTurn(ImmutableRecord):
    turn_id: int
    speaker: str | None = Field(default=None, description="model speaker label (A, B…), DIARIZATION only")
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    text: str


class VoiceTranscript(ImmutableRecord):
    voice_transcript_id: VoiceTranscriptId
    case_id: CaseId
    kind: Literal["search_note", "complaint_call"]
    search_task_id: str | None = None
    area_id: str | None = None
    audio_sha256: Sha256
    audio_duration_ms: int = Field(ge=0)
    sample_rate_hz: Literal[16000, 24000]
    mode: Literal["PUSH_TO_TALK", "ENDPOINTING", "DIARIZATION"]
    transcript: str
    turns: list[VoiceTurn]
    model: str
    session_id: str | None = None
    usd_estimate: float
    recorded_by: str = Field(description="pseudonymous user id of the person who uploaded it")
    recorded_at: AwareDatetime
    label: str = (
        "Machine transcript of the original audio (kept with its SHA-256); check a line against the audio."
    )
    content_sha256: Sha256
