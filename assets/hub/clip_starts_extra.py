"""What each recorder's export says its clip starts at (its on-screen clock at the first frame), for clips rendered
outside the scenario's own window (six checkpoints: W1 / W2 and the checkpoint cameras on the S2 window). RENDER SIDE:
it reads render_truth.json the way make_cards.py does for the S2 clips; the app gets only the JSON (a recorder export's
start time), never the offsets, and fits every clock itself.

  py -X utf8 assets/hub/clip_starts_extra.py <window t0 ISO> <CAM:first_frame,...> <out.json>
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

HUB = Path(__file__).resolve().parent
t0 = datetime.fromisoformat(sys.argv[1])
truth = json.loads((HUB / "render_truth.json").read_text(encoding="utf-8"))["cameras"]
out = {}
for item in sys.argv[2].split(","):
    cam, f0 = item.split(":")
    t = (int(f0) - 1) / 10.0
    c = truth.get(cam, {})
    off = c.get("clock_offset_s", 0.0) + c.get("clock_drift_ppm", 0.0) * 1e-6 * t
    out[cam] = (t0 + timedelta(seconds=t + off)).isoformat(timespec="milliseconds")
Path(sys.argv[3]).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
print(json.dumps(out))
