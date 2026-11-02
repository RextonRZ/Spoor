import json
import shutil
from datetime import UTC, datetime, timedelta

import pytest

from spoor.forensics.journey_reel import Segment, build_journey_reel

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")


def test_chapters_in_time_order_with_their_place_in_the_video(tmp_path):
    t0 = datetime(2026, 10, 28, 6, 21, 33, tzinfo=UTC)
    segs = [Segment(title="Most likely in the store", tone="card", t=t0 + timedelta(minutes=12), seconds=1.0),
            Segment(title="In RC-1, no scan for 11 min", tone="wait", t=t0 + timedelta(seconds=1), seconds=1.5)]
    man = build_journey_reel(segs, tmp_path, "reel_test", "CTX1")
    assert [c["title"] for c in man["chapters"]] == ["In RC-1, no scan for 11 min", "Most likely in the store"]
    first, second = man["chapters"]
    assert first["start_s"] == 2.0 and first["end_s"] == pytest.approx(3.5)  # after the 2.0 s intro card
    assert second["start_s"] == first["end_s"] and man["seconds"] == pytest.approx(6.5)  # the answer card holds 3.0 s
    assert (tmp_path / "reel_test.mp4").stat().st_size > 0
    assert json.loads((tmp_path / "reel_test.json").read_text(encoding="utf-8"))["chapters"] == man["chapters"]
