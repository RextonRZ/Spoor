"""Smoke 10 (J4): Muse Voice Transcribe on a WAV, DIARIZATION mode.

Usage: uv run python scripts/smoke/voice_transcribe.py <file.wav>
The smoke input is SYNTHETIC speech (Windows speech synthesis), never case evidence; nothing is stored on a case.
Price: $0.18 per audio hour (a 10 s clip ≈ $0.0005).
"""

import sys
from pathlib import Path

from _common import record, timed

from spoor.config import get_settings
from spoor.voice import MODEL, MetaVoiceTranscriber, turns_of, usd_for, wav_info

s = get_settings()
if s.model_api_key is None:
    sys.exit("MODEL_API_KEY is not set")
data = Path(sys.argv[1]).read_bytes()
rate, ms = wav_info(data)
print(f"estimate: {MODEL} · {ms / 1000:.1f} s of audio at {rate} Hz ≈ ${usd_for(ms):.5f}")
with timed() as t:
    reply = MetaVoiceTranscriber(s.model_api_key.get_secret_value(), s.meta_base_url).transcribe(
        data, mode="DIARIZATION", keywords=["exception store", "cage"]
    )
turns = turns_of(reply)
print(
    f"actual: ${usd_for(int(reply.get('audioDurationMs') or ms)):.5f} · {t['latency_s']} s · {len(turns)} turns"
)
print("transcript:", reply.get("transcript"))
for x in turns:
    print(f"  [{x['start_ms']}-{x['end_ms']} ms] {x['speaker']}: {x['text']}")
record("voice_transcribe", {"model": MODEL, "input": "synthetic TTS speech", "audio_ms": ms, "latency_s": t["latency_s"],
                            "session_id": reply.get("sessionId"), "transcript": reply.get("transcript"), "turns": turns})  # fmt: skip
