"""Real-footage test: the hub's scan-to-camera handshake (point rule) on a real clip, from a hand-made scan log.

For each scan (time + the scan spot), exactly what the hub does at a belt point (backend forensics/handshake.py and
services.anchored_sam): cut the clip from 0.5 s before to 5 s after the scan at its own frame rate, put ONE positive
point on the scan spot on the scan's frame (InstancePrompt), and let SAM 3.1 segment and follow it (propagation
"both", the hub's default). Nothing here knows which item is right; scoring is a separate step (score_handshake.py).

The scan spot is a fixed place on the belt. When the clip pans, the spot is moved by the camera's measured shift
(shift.json, from stab_slit.py): the stand-in for a fixed camera's calibration.

  cd backend && .venv/Scripts/python.exe ../assets/realtest/run_handshake.py ../assets/realtest/pexels_4156510 \
      --clip clip_blur.mp4 --x 864 --y 530
"""
import argparse
import asyncio
import csv
import json
import subprocess
from pathlib import Path

import cv2

from openai import AsyncOpenAI
from spoor.config import Settings
from spoor.forensics.handshake import BEFORE_S, FOLLOW_S
from spoor.perception.backend import MetaSamBackend
from spoor.perception.prompts import InstancePrompt

ap = argparse.ArgumentParser()
ap.add_argument("dir")
ap.add_argument("--clip", default="clip_blur.mp4")
ap.add_argument("--log", default="scan_log.csv")
ap.add_argument("--x", type=float, required=True, help="the scan spot at the reference frame, px")
ap.add_argument("--y", type=float, required=True)
ap.add_argument("--only", default="")
a = ap.parse_args()
d = Path(a.dir).resolve()
out = d / "sam"
out.mkdir(exist_ok=True)

cap = cv2.VideoCapture(str(d / a.clip))
fps, n = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
W, H = int(cap.get(3)), int(cap.get(4))
shift = json.loads((d / "shift.json").read_text())["shift"] if (d / "shift.json").exists() else [[0, 0]] * n
s = Settings()
sam = MetaSamBackend(AsyncOpenAI(api_key=s.model_api_key.get_secret_value(), base_url=s.meta_base_url), s.sam_model)


def cut(lo: int, hi: int, path: Path):
    """frames lo..hi exactly (the hub cuts its proxy frame-exact too), H.264 at the clip's own rate"""
    cap.set(cv2.CAP_PROP_POS_FRAMES, lo)
    raw = path.with_suffix(".raw.mp4")
    w = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    for _ in range(hi - lo + 1):
        ok, f = cap.read()
        if not ok:
            break
        w.write(f)
    w.release()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-r", f"{fps}", str(path)], check=True)
    raw.unlink()


async def main():
    rows = list(csv.DictReader((d / a.log).open(encoding="utf-8")))
    only = set(filter(None, a.only.split(",")))
    spent = 0
    for r in rows:
        if only and r["scan_id"] not in only:
            continue
        f = round(float(r["time_s"]) * fps)
        lo, hi = max(0, f - round(BEFORE_S * fps)), min(n - 1, f + round(FOLLOW_S * fps))
        px = (round(a.x + shift[f][0]), round(a.y + shift[f][1]))
        res = out / f"{r['scan_id']}.json"
        if res.exists():
            print(r["scan_id"], "cached")
            continue
        clip = out / f"{r['scan_id']}.mp4"
        cut(lo, hi, clip)
        prompt = InstancePrompt(frame_index=f - lo, positive_points_px=[px]).render((W, H))
        run = await sam.segment_video(clip, prompt, propagation="both")
        spent += hi - lo + 1
        res.write_text(json.dumps({"scan_id": r["scan_id"], "time_s": float(r["time_s"]), "frame": f, "lo": lo, "hi": hi,
                                   "point_px": px, "fps": fps, "run": run.to_json()}), encoding="utf-8")
        dets = run.detections
        print(r["scan_id"], r["time_s"], "outcome", run.outcome, "detections", len(dets),
              "objects", sorted({x.object_id for x in dets}), "frames", hi - lo + 1)
    print("frames sent", spent)


asyncio.run(main())
