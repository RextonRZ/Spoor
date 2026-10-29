"""Long clips exceed SAM's 15,000-frame request limit: they are processed in verified, contiguous chunks."""

import asyncio

import pytest
import sam_wire
from test_perception import H, W
from test_perception import clip as clip
from test_perception import setup as setup

from spoor.ingest import asset_path
from spoor.ingest.clips import ClipCutError, cut_frames, frame_chunks
from spoor.perception import InstancePrompt, parse_sam_stream, track_target


class ChunkRecordingSam:
    """Fixture backend: one detection on local frames 0 and 3 of every chunk; records the clip lengths it got."""

    model = "sam-3.1"

    def __init__(self):
        self.calls = []

    async def segment_video(self, video, prompt, *, propagation="both"):
        from spoor.ingest import probe

        self.calls.append((len(probe(video)[1].pts_ms), prompt))
        lines = [sam_wire.line(f, sam_wire.record(1, (20, 30, 79, 89), (W, H), conf=0.9)) for f in (0, 3)]
        return await parse_sam_stream(sam_wire.stream(sam_wire.events(lines)), model=self.model)


def test_frame_chunks_are_contiguous_and_bounded():
    assert frame_chunks(30, 12) == [(0, 11), (12, 23), (24, 29)]
    assert frame_chunks(10, 15000) == [(0, 9)]


def test_long_clip_is_chunked_and_frames_offset(setup):
    backend = ChunkRecordingSam()
    res = asyncio.run(track_target(setup.request(), backend=backend, store=setup.store, cache_dir=setup.cache,
                                   max_frames_per_request=12, now=setup.now))  # fmt: skip
    assert [n for n, _ in backend.calls] == [12, 12, 6]  # 30-frame clip, verified cuts
    assert res.status == "ok" and len(res.tracks) == 3  # SAM ids restart per chunk: never silently stitched
    frames = sorted(o.source_frame.frame_index for o in res.observations)
    assert frames == [0, 3, 12, 15, 24, 27]
    assert all(o.source_frame.media_id == setup.ingest.original.media_id for o in res.observations)


def test_instance_prompt_runs_only_on_its_chunk_and_says_so(setup):
    backend = ChunkRecordingSam()
    req = setup.request(concept=None, instance=InstancePrompt(frame_index=14, box_ltrb_px=(20, 30, 80, 90)))
    res = asyncio.run(track_target(req, backend=backend, store=None, cache_dir=setup.cache,
                                   max_frames_per_request=12))  # fmt: skip
    assert len(backend.calls) == 1 and backend.calls[0][1].startswith("<2f>")  # frame 14 rebased to chunk start 12
    assert "not inspected" in res.message
    assert sorted(o.source_frame.frame_index for o in res.observations) == [12, 15]


def test_misaligned_cut_is_refused(setup, tmp_path):
    table = setup.ingest.original_frames
    broken = type(table)(stream_start_s=table.stream_start_s, pts_ms=table.pts_ms + [table.pts_ms[-1] + 100] * 5)
    with pytest.raises(ClipCutError):
        cut_frames(asset_path(setup.media, setup.ingest.proxy), broken, source_media_id="media_x", start_frame=20,
                   end_frame=34, out_dir=tmp_path)  # fmt: skip
