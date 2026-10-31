"""Muse Voice Transcribe (QUEUE J4), per dev.meta.ai/docs/api-reference/voice/transcribe and /schemas.

`POST {base}/asr/transcribe`, multipart: `request` (JSON: model, audioEncoding "WAV", mode, keywords) + `audio`
(RIFF/WAVE, mono integer PCM at 16 or 24 kHz, at most 10 minutes and 32 MB). The buffered JSON reply carries
`transcript`, `audioDurationMs` and `turns` (turnId, startMs, endMs, transcript, speaker in DIARIZATION mode).
Price: $0.18 per hour of audio, whole seconds rounded down (pricing page, 31 Oct 2026). The key is sent only in the
Authorization header and never logged."""

import io
import wave
from typing import Any, Protocol

MODEL = "muse-voice-transcribe-1.0"
USD_PER_HOUR = 0.18
MAX_MS = 10 * 60 * 1000
MAX_BYTES = 32 * 1024 * 1024


class VoiceError(ValueError):
    pass


def wav_info(data: bytes) -> tuple[int, int]:
    """(sample rate, duration ms) of an acceptable WAV, else VoiceError saying what is wrong."""
    if len(data) > MAX_BYTES:
        raise VoiceError("audio over 32 MB")
    try:
        with wave.open(io.BytesIO(data)) as w:
            ch, width, rate, frames = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    except (wave.Error, EOFError) as e:
        raise VoiceError(f"not a PCM WAV file: {e}") from e
    if ch != 1 or width != 2 or rate not in (16000, 24000):
        raise VoiceError(f"need mono 16-bit PCM at 16 or 24 kHz, got {ch} ch, {8 * width}-bit, {rate} Hz")
    ms = frames * 1000 // rate
    if ms > MAX_MS:
        raise VoiceError("audio over 10 minutes")
    if ms < 300:
        raise VoiceError("audio shorter than 0.3 s")
    return rate, ms


def usd_for(duration_ms: int) -> float:
    return round((duration_ms // 1000) / 3600 * USD_PER_HOUR, 6)


class Transcriber(Protocol):
    model: str

    def transcribe(self, wav: bytes, *, mode: str, keywords: list[str]) -> dict: ...


class MetaVoiceTranscriber:
    model = MODEL

    def __init__(self, api_key: str, base_url: str, client: Any = None):
        import httpx

        self._key, self._url = api_key, base_url.rstrip("/") + "/asr/transcribe"
        self._http = client or httpx.Client(timeout=180)

    def transcribe(self, wav: bytes, *, mode: str = "DIARIZATION", keywords: list[str] | None = None) -> dict:
        import json

        req = {
            "model": self.model,
            "audioEncoding": "WAV",
            "mode": mode,
            **({"keywords": keywords} if keywords else {}),
        }
        r = self._http.post(self._url, headers={"Authorization": f"Bearer {self._key}", "Accept": "application/json"},
                            files={"request": (None, json.dumps(req), "application/json"),
                                   "audio": ("audio.wav", wav, "audio/wav")})  # fmt: skip
        if r.status_code != 200:
            raise VoiceError(f"transcription failed: HTTP {r.status_code} {r.text[:200]}")
        return r.json()


def turns_of(reply: dict) -> list[dict]:
    return [{"turn_id": int(t.get("turnId", i)), "speaker": t.get("speaker"), "start_ms": int(t.get("startMs", 0)),
             "end_ms": int(t.get("endMs", 0)), "text": (t.get("transcript") or "").strip()}
            for i, t in enumerate(reply.get("turns") or []) if (t.get("transcript") or "").strip()]  # fmt: skip
