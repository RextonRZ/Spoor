"""SAM's mask edge, recovered from its cached raw output and matched to a track's box (perception/contours.py)."""

import json
from pathlib import Path

from spoor.perception.contours import contours_for

TOKEN = (Path(__file__).parent / "data" / "sam_mask_token.txt").read_text(encoding="utf-8")


def test_the_mask_that_follows_a_matching_box_becomes_a_polygon_inside_it(tmp_path):
    cache = tmp_path / "sam_x.json"
    cache.write_text(json.dumps({"raw_output": f"<9f>1{TOKEN}"}), encoding="utf-8")
    box = (1246.0, 137.0, 1278.0, 149.0)  # the track's box for that frame (the cached one is within a pixel)
    out = contours_for([(9, box), (10, (0.0, 0.0, 5.0, 5.0))], [cache])
    assert list(out) == [9]  # frame 10's box matches no cached box: no contour, the box is kept
    xs, ys = [p[0] for p in out[9]], [p[1] for p in out[9]]
    assert len(out[9]) >= 4 and box[0] - 1 <= min(xs) and max(xs) <= box[2] + 1 and box[1] - 1 <= min(ys) and max(ys) <= box[3] + 1
