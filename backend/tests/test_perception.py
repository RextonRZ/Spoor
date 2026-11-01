"""Step 05 acceptance tests: SAM adapter request shape, parsing, normalization, caching and failure handling.

SAM output here is synthesized in the documented wire format (tests/sam_wire.py) — fixture data, not inference.
"""

import asyncio
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import sam_wire
from test_ingest import make_video

from spoor.contracts import Camera, ClockSync, MediaAuthorization, SpatialMode
from spoor.ingest import MediaStore, asset_path, extract_frame, ingest
from spoor.perception import (
    InstancePrompt,
    MetaSamBackend,
    PerceptionRequest,
    PromptError,
    parse_sam_stream,
    track_target,
    validate_concept,
)
from spoor.store import CostEntry, EvidenceStore

W, H = 320, 240


class FixtureSamBackend:
    """Replays a synthesized SAM stream through the real parser. Counts calls to prove caching."""

    model = "sam-3.1"

    def __init__(self, lines, delay_s: float = 0.0, fail: Exception | None = None):
        self.lines, self.delay_s, self.fail, self.calls = lines, delay_s, fail, []

    async def segment_video(self, video: Path, prompt: str, *, propagation="both"):
        self.calls.append((video, prompt, propagation))
        if self.fail:
            raise self.fail
        await asyncio.sleep(self.delay_s)
        return await parse_sam_stream(sam_wire.stream(sam_wire.events(self.lines)), model=self.model)


@pytest.fixture(scope="module")
def clip(tmp_path_factory) -> Path:
    return make_video(tmp_path_factory.mktemp("p") / "room.mp4", seconds=3)


@pytest.fixture
def setup(clip, tmp_path, now, room):
    store = EvidenceStore()
    media = MediaStore(tmp_path / "data")
    store.put(room)
    auth = store.put(MediaAuthorization(
        authorization_id="auth_p", site_id="site_test", uploader="tester", rights_statement="synthetic test clip",
        purpose="test", consent_confirmed=True, hosted_processing_allowed=True,
        retention_until=now + timedelta(days=1), recorded_at=now,
    ))  # fmt: skip
    cam = store.put(Camera(camera_id="cam_a", site_id="site_test", floor_id="floor_g", name="A",
                           resolution_wh_px=(W, H),
                           zone_image_regions_px={"zone_shelf_a": [(0, 0), (160, 0), (160, 120), (0, 120)]}))
    sync = store.put(ClockSync(sync_id="sync_a", camera_id="cam_a", offset_ms=250.0, uncertainty_ms=40.0,
                               method="fixture", created_at=now))  # fmt: skip
    r = ingest(clip, store=media, authorization=auth, site_id="site_test", camera_id="cam_a", ingested_by="t", now=now)
    store.put_many([r.original, r.proxy])

    def request(**kw):
        base = dict(original=r.original, proxy=r.proxy, proxy_path=asset_path(media, r.proxy),
                    original_frames=r.original_frames, authorization=auth, camera=cam, clip_start_camera_time=now,
                    sync=sync, concept="blue equipment case", site=room)  # fmt: skip
        return PerceptionRequest(**(base | kw))

    return SimpleNamespace(store=store, media=media, ingest=r, request=request, cache=tmp_path / "cache", now=now)


LINES = [
    sam_wire.line(0, sam_wire.record(1, (20, 30, 79, 89), (W, H), conf=0.9)),
    sam_wire.line(1, sam_wire.record(1, (22, 31, 81, 90), (W, H), conf=0.88)),
    sam_wire.line(5, sam_wire.record(1, (30, 35, 89, 94), (W, H), conf=0.4, fill=0.2),
                  sam_wire.record(2, (200, 150, 319, 239), (W, H), conf=0.7)),
]  # fmt: skip


def run(coro):
    return asyncio.run(coro)


def test_detections_become_cited_observations(setup):
    backend = FixtureSamBackend(LINES)
    res = run(track_target(setup.request(), backend=backend, store=setup.store, cache_dir=setup.cache,
                           now=setup.now))  # fmt: skip
    assert res.status == "ok" and len(res.tracks) == 2 and len(res.observations) == 4
    t1 = next(t for t in res.tracks if t.provider_object_id == "1")
    assert (t1.first_frame_index, t1.last_frame_index) == (0, 5)
    o = next(o for o in res.observations if o.source_frame.frame_index == 5 and o.track_id == t1.track_id)
    # Inclusive wire box (30,35)-(89,94) -> half-open (30,35,90,95), in the ORIGINAL media's frame timeline.
    assert o.bbox_xyxy_px == (30, 35, 90, 95)
    assert o.source_frame.media_id == setup.ingest.original.media_id
    assert o.source_frame.pts_ms == pytest.approx(500)
    assert o.source_frame.normalized_utc == setup.now + timedelta(milliseconds=750)  # pts 500 + offset 250
    assert {"low_raw_confidence", "partially_occluded"} <= set(o.quality_flags)
    assert o.provenance.model == "sam-3.1" and o.provenance.request_id == "resp_fixture"
    edge = next(o for o in res.observations if o.track_id != t1.track_id)
    assert "touches_frame_edge" in edge.quality_flags
    # Every observation resolves to a frame of the original.
    path = asset_path(setup.media, setup.ingest.original)
    assert extract_frame(path, setup.ingest.original_frames, o.source_frame.frame_index)


def test_spatial_fallback_without_calibration(setup):
    res = run(track_target(setup.request(), backend=FixtureSamBackend(LINES), store=setup.store,
                           cache_dir=setup.cache, now=setup.now))  # fmt: skip
    modes = {e.spatial_mode for e in res.estimates}
    assert SpatialMode.FLOOR_XY not in modes  # no calibration: never a floor coordinate
    assert modes <= {SpatialMode.ANCHORED_HEIGHT, SpatialMode.ZONE_ONLY, SpatialMode.IMAGE_ONLY}


def test_cache_prevents_second_paid_call(setup):
    backend = FixtureSamBackend(LINES)
    first = run(track_target(setup.request(), backend=backend, store=setup.store, cache_dir=setup.cache,
                             now=setup.now))  # fmt: skip
    second = run(track_target(setup.request(), backend=backend, store=None, cache_dir=setup.cache, now=setup.now))
    assert len(backend.calls) == 1 and second.cache_hit and second.cache_key == first.cache_key
    assert len(second.observations) == len(first.observations)
    ledger = setup.store.find(CostEntry)
    assert ledger[0].billed_units == 50 and ledger[0].unit == "frames"  # 30-frame clip, 50-frame minimum


def test_hosted_processing_requires_authorization(setup):
    auth = setup.request().authorization.model_copy(update={"hosted_processing_allowed": False})
    backend = FixtureSamBackend(LINES)
    res = run(track_target(setup.request(authorization=auth), backend=backend, store=setup.store,
                           cache_dir=setup.cache))  # fmt: skip
    assert res.status == "not_authorized_for_hosted_processing" and backend.calls == []


def test_timeout_is_unknown_completion_not_retried(setup):
    backend = FixtureSamBackend(LINES, delay_s=1.0)
    res = run(track_target(setup.request(), backend=backend, store=setup.store, cache_dir=setup.cache,
                           timeout_s=0.05, now=setup.now))  # fmt: skip
    assert res.status == "unknown_completion" and len(backend.calls) == 1
    assert setup.store.find(CostEntry)[-1].outcome == "timeout_unknown_completion"


def test_provider_failure_is_analysis_unavailable(setup):
    res = run(track_target(setup.request(), backend=FixtureSamBackend(LINES, fail=ConnectionError("down")),
                           store=setup.store, cache_dir=setup.cache))  # fmt: skip
    assert res.status == "analysis_unavailable" and res.observations == []


def test_no_detections_suggests_operator_prompt(setup):
    res = run(track_target(setup.request(), backend=FixtureSamBackend([]), store=setup.store, cache_dir=setup.cache))
    assert res.status == "no_detections" and "box/point" in res.message


def test_instance_prompt_rendered_in_pixels(setup):
    backend = FixtureSamBackend(LINES)
    req = setup.request(concept=None, instance=InstancePrompt(frame_index=3, box_ltrb_px=(20, 30, 80, 90)))
    run(track_target(req, backend=backend, store=None, cache_dir=setup.cache))
    prompt = backend.calls[0][1]
    assert prompt.startswith("<3f>1<|box;") and f"w={W};h={H}" in prompt


@pytest.mark.parametrize("bad", ["the thief", "suspicious person", "who took the case", "laptop and parcel",
                                 "case?", "a very long description of a blue equipment case here"])  # fmt: skip
def test_concept_validation_rejects_roles_and_questions(bad):
    with pytest.raises(PromptError):
        validate_concept(bad)


def test_concept_validation_accepts_objects():
    assert validate_concept("  Blue Equipment  Case ") == "blue equipment case"
    assert validate_concept("person") == "person"


def test_meta_backend_request_shape(tmp_path):
    """The real adapter: uploads with expiry, streams /v1/responses with Meta's documented fields, deletes upload."""
    calls = {}

    class Files:
        async def create(self, **kw):
            calls["upload"] = kw
            return SimpleNamespace(id="file-fixture")

        async def delete(self, file_id):
            calls["deleted"] = file_id

    class Responses:
        async def create(self, **kw):
            calls["request"] = kw
            return sam_wire.stream(sam_wire.events(LINES[:1]))

    video = tmp_path / "v.mp4"
    video.write_bytes(b"\x00")
    backend = MetaSamBackend(SimpleNamespace(files=Files(), responses=Responses()))
    result = run(backend.segment_video(video, "blue equipment case", propagation="forward"))
    req = calls["request"]
    assert req["model"] == "sam-3.1" and req["stream"] is True
    assert req["metadata"] == {"include_confidence": "true", "propagation_direction": "forward"}
    content = req["input"][0]["content"]
    assert content[0] == {"type": "input_text", "text": "blue equipment case"}
    assert content[1] == {"type": "input_video", "file_id": "file-fixture"}
    assert calls["upload"]["purpose"] == "user_data" and calls["upload"]["expires_after"]["seconds"] == 3600
    assert calls["deleted"] == "file-fixture"
    assert result.completed and len(result.detections) == 1


def test_cache_hit_reuses_stored_records_instead_of_duplicating(setup):
    """Review (minor): repeating the same SAM request must not insert a second copy of every observation."""
    from spoor.contracts import RawObservation, Track

    backend = FixtureSamBackend(LINES)
    first = run(track_target(setup.request(), backend=backend, store=setup.store, cache_dir=setup.cache,
                             now=setup.now))  # fmt: skip
    again = run(track_target(setup.request(), backend=backend, store=setup.store, cache_dir=setup.cache,
                             now=setup.now))  # fmt: skip
    assert again.cache_hit and len(backend.calls) == 1
    assert {t.track_id for t in again.tracks} == {t.track_id for t in first.tracks}
    assert len(setup.store.find(Track)) == 2 and len(setup.store.find(RawObservation)) == 4


def test_track_ends_where_sam_loses_the_object(setup):
    # SAM ids are not reliable after the object leaves view: a long run of missing frames splits the track.
    lines = [sam_wire.line(0, sam_wire.record(1, (20, 30, 79, 89), (W, H), conf=0.9)),
             sam_wire.line(1, sam_wire.record(1, (22, 31, 81, 90), (W, H), conf=0.88)),
             sam_wire.line(20, sam_wire.record(1, (200, 150, 230, 180), (W, H), conf=0.3))]  # fmt: skip
    res = run(track_target(setup.request(), backend=FixtureSamBackend(lines), store=setup.store, cache_dir=setup.cache,
                           now=setup.now))  # fmt: skip
    spans = sorted((t.first_frame_index, t.last_frame_index) for t in res.tracks)
    assert spans == [(0, 1), (20, 20)] and {t.provider_object_id for t in res.tracks} == {"1"}
