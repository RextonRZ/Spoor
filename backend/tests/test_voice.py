"""J4 Muse Voice Transcribe: the original WAV is kept by hash, the transcript carries speaker turns and a case
revision, the price follows audio seconds, a bad file is refused with the reason, and no-key mode stores nothing."""

import io
import math
import struct
import wave
from datetime import UTC, datetime

import pytest
from builders import World
from fastapi.testclient import TestClient

from spoor.api.app import create_app
from spoor.api.auth import Principal, Role, TokenRegistry
from spoor.api.services import Services
from spoor.config import Settings
from spoor.contracts import ObjectInstance, ParcelIdentifier, VoiceTranscript
from spoor.voice import MetaVoiceTranscriber, VoiceError, turns_of, usd_for, wav_info


def tone(seconds: float, rate: int = 16000, channels: int = 1) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        n = int(seconds * rate)
        w.writeframes(b"".join(struct.pack("<h", int(3000 * math.sin(i / 8))) * channels for i in range(n)))
    return buf.getvalue()


def test_wav_rules_and_price():
    assert wav_info(tone(2.0)) == (16000, 2000)
    assert wav_info(tone(1.0, rate=24000))[0] == 24000
    with pytest.raises(VoiceError, match="mono 16-bit"):
        wav_info(tone(1.0, channels=2))
    with pytest.raises(VoiceError, match="8000 Hz"):
        wav_info(tone(1.0, rate=8000))
    with pytest.raises(VoiceError, match="not a PCM WAV"):
        wav_info(b"RIFF....not audio")
    assert usd_for(3_599_999) == round(3599 / 3600 * 0.18, 6) and usd_for(999) == 0.0


def test_turns_skip_empty_and_keep_speakers():
    reply = {"turns": [{"turnId": 0, "startMs": 0, "endMs": 900, "transcript": " Found it on shelf three. ", "speaker": "A"},
                       {"turnId": 1, "startMs": 950, "endMs": 990, "transcript": "  "}]}  # fmt: skip
    assert turns_of(reply) == [
        {"turn_id": 0, "speaker": "A", "start_ms": 0, "end_ms": 900, "text": "Found it on shelf three."}
    ]


def test_meta_transcriber_sends_multipart_with_the_documented_fields():
    seen = {}

    class Http:
        def post(self, url, headers, files):
            seen.update(url=url, headers=headers, files=files)
            return type(
                "R",
                (),
                {"status_code": 200, "json": lambda self: {"transcript": "ok", "turns": []}, "text": ""},
            )()

    t = MetaVoiceTranscriber("k-test", "https://api.meta.ai/v1", client=Http())
    assert t.transcribe(tone(1.0), mode="DIARIZATION", keywords=["CTX1"]) == {"transcript": "ok", "turns": []}
    assert seen["url"] == "https://api.meta.ai/v1/asr/transcribe"
    assert (
        '"audioEncoding": "WAV"' in seen["files"]["request"][1]
        and '"mode": "DIARIZATION"' in seen["files"]["request"][1]
    )
    assert seen["files"]["audio"][2] == "audio/wav" and seen["headers"]["Accept"] == "application/json"


class FakeVoice:
    model = "muse-voice-transcribe-1.0"

    def __init__(self):
        self.keywords = None

    def transcribe(self, wav, *, mode, keywords):
        self.keywords = keywords
        return {"sessionId": "sess_1", "audioDurationMs": 2000, "transcript": "Found it. Shelf three.",
                "turns": [{"turnId": 0, "startMs": 100, "endMs": 1900, "transcript": "Found it. Shelf three.", "speaker": "A"}]}  # fmt: skip


NOW = datetime(2026, 10, 28, 6, 40, tzinfo=UTC)
WAYBILL = ParcelIdentifier(scheme="carrier_waybill", value="CTX100200300400")


def _client(tmp_path, voice, site):
    svc = Services.from_settings(Settings(data_dir=tmp_path, model_api_key=None, agent_backend="none"))
    svc.tokens = TokenRegistry({"t-inv": Principal("inv", Role.INVESTIGATOR, frozenset({site.site_id}))})
    svc.voice = voice
    w = World(svc.store, site, NOW)
    svc.store.put(ObjectInstance(object_instance_id="objinst_v1", case_id=w.case.case_id, label="parcel CTX1",
                                 identifiers=[WAYBILL], created_by="inv", created_at=NOW))  # fmt: skip
    return TestClient(create_app(services=svc)), svc, w.case.case_id


def test_complaint_call_is_kept_by_hash_with_turns_cost_and_revision(tmp_path, site):
    voice = FakeVoice()
    c, svc, cid = _client(tmp_path, voice, site)
    wav = tone(2.0)
    r = c.post(f"/v1/cases/{cid}/voice", headers={"Authorization": "Bearer t-inv"},
               files={"file": ("call.wav", wav, "audio/wav")}, data={"kind": "complaint_call"})  # fmt: skip
    assert r.status_code == 201, r.text
    out = r.json()
    import hashlib

    assert out["audio_sha256"] == hashlib.sha256(wav).hexdigest() and out["turns"][0]["speaker"] == "A"
    assert out["sample_rate_hz"] == 16000 and out["usd_estimate"] == usd_for(2000)
    assert "CTX100200300400" in voice.keywords
    assert (tmp_path / "audio" / f"{out['audio_sha256']}.wav").read_bytes() == wav
    assert c.get(out["audio_url"]).content == wav
    assert svc.store.head_revision(cid).changed_ids == [out["voice_transcript_id"]]
    listed = c.get(f"/v1/cases/{cid}/voice", headers={"Authorization": "Bearer t-inv"}).json()
    assert listed["available"] and [i["voice_transcript_id"] for i in listed["items"]] == [
        out["voice_transcript_id"]
    ]
    bad = c.post(f"/v1/cases/{cid}/voice", headers={"Authorization": "Bearer t-inv"},
                 files={"file": ("x.wav", tone(1.0, channels=2), "audio/wav")}, data={"kind": "complaint_call"})  # fmt: skip
    assert bad.status_code == 422 and "mono" in bad.json()["detail"]
    note = c.post(f"/v1/cases/{cid}/voice", headers={"Authorization": "Bearer t-inv"},
                  files={"file": ("n.wav", wav, "audio/wav")}, data={"kind": "search_note", "area_id": "Z11"})  # fmt: skip
    assert note.status_code == 404  # a floor note must name a place of a real search task


def test_no_key_stores_nothing(tmp_path, site):
    c, svc, cid = _client(tmp_path, None, site)
    r = c.post(f"/v1/cases/{cid}/voice", headers={"Authorization": "Bearer t-inv"},
               files={"file": ("call.wav", tone(1.0), "audio/wav")}, data={"kind": "complaint_call"})  # fmt: skip
    assert r.status_code == 503 and "no API key" in r.json()["detail"]
    assert svc.store.find(VoiceTranscript, case_id=cid) == [] and not (tmp_path / "audio").exists()
