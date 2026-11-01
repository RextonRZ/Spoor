"""CCTV pass over a rendered image sequence, then one video encode (RENDER SIDE: reads render_truth.json).

  uv run python assets/hub/cctv_batch.py <frames_dir> <out.mp4> --cam CAM_07 [--codec h264|h265] [--width 1280]
      [--first 1] [--fps 10] [--keep]

Per frame: lens (this camera's k1 from render_truth, vignette, softness, chromatic aberration) -> sensor grain ->
ISP -> OSD with THIS camera's own clock (scenario t0 + frame time, + its offset and drift from render_truth), the
camera label from hub_spec, and the SYNTHETIC mark. The whole sequence is then encoded once (H.265 for the batch,
H.264 for review clips), so the codec's blocking / smearing comes from real inter-frame compression.
Spoor's runtime never reads render_truth: only this render-side script does.
"""
import argparse
import json
import os
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import numpy as np

import cctv_look as L

HUB = Path(__file__).resolve().parent
T0 = datetime(2026, 10, 28, 14, 32, 7, tzinfo=timezone(timedelta(hours=8)))  # frame 1 on the hub's true clock


def osd_time(cam_truth, t_s):
    off = cam_truth.get("clock_offset_s", 0.0)
    drift = cam_truth.get("clock_drift_ppm", 0.0) * 1e-6
    t = T0 + timedelta(seconds=t_s + off + drift * t_s)
    return t.strftime("%Y-%m-%d %H:%M:%S")


def _frame(job):
    """One frame through lens / sensor / ISP / OSD. The noise is seeded per frame (same result in any process)."""
    fp, f, t_s, seed, k1, hfov, cam, label, when, width = job
    raw = cv2.imread(fp)
    rng = np.random.default_rng([seed, f])
    img = L.isp(L.sensor(L.lens(raw, k1, hfov), rng))
    img = L.osd(img, cam, label, when, mark=True)
    if width and img.shape[1] > width:
        h = int(round(img.shape[0] * width / img.shape[1] / 2) * 2)
        img = cv2.resize(img, (width, h), interpolation=cv2.INTER_AREA)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames")
    ap.add_argument("out")
    ap.add_argument("--cam", required=True)
    ap.add_argument("--codec", default="h264")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--first", type=int, default=1)
    ap.add_argument("--fps", type=int, default=10)
    ap.add_argument("--seed", type=int, default=9)
    ap.add_argument("--t0-offset", type=float, default=0.0, help="scenario start relative to T0 (s)")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 4))
    a = ap.parse_args()
    truth = json.loads((HUB / "render_truth.json").read_text(encoding="utf-8"))["cameras"].get(a.cam, {})
    spec = json.loads((HUB / "hub_spec.json").read_text(encoding="utf-8"))
    cam = next(c for c in spec["cameras"] if c["id"] == a.cam)
    label = cam.get("osd_label", "")
    files = sorted(Path(a.frames).glob("*.png"))
    if not files:
        raise SystemExit(f"no frames in {a.frames}")
    k1, hfov = truth.get("lens_k1", -0.06), cam.get("hfov_deg", 103.0)
    jobs = [(str(fp), a.first + i, a.t0_offset + (a.first + i - 1) / a.fps, a.seed + (int(a.cam[-2:]) if a.cam[-2:].isdigit() else sum(map(ord, a.cam)) % 97), k1, hfov,
             a.cam, label, osd_time(truth, a.t0_offset + (a.first + i - 1) / a.fps), a.width) for i, fp in enumerate(files)]
    probe = _frame(jobs[0])
    h, w = probe.shape[:2]
    enc = ["-c:v", "libx265", "-preset", "fast", "-crf", "30", "-x265-params", "keyint=30:log-level=error"]         if a.codec == "h265" else ["-c:v", "libx264", "-crf", "24", "-g", "30"]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    # frames go straight into the encoder (raw BGR on stdin: no temp PNGs), processed in parallel, written in order
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
                           "-s", f"{w}x{h}", "-framerate", str(a.fps), "-i", "-", *enc, "-pix_fmt", "yuv420p",
                           "-movflags", "+faststart", a.out], stdin=subprocess.PIPE)
    ff.stdin.write(probe.tobytes())
    with ProcessPoolExecutor(max_workers=max(1, min(a.workers, len(jobs) - 1))) as ex:
        for img in ex.map(_frame, jobs[1:], chunksize=4):
            ff.stdin.write(img.tobytes())
    ff.stdin.close()
    if ff.wait() != 0:
        raise SystemExit(f"ffmpeg failed for {a.out}")
    print(json.dumps({"out": a.out, "frames": len(files), "cam": a.cam,
                      "osd_first": osd_time(truth, a.t0_offset), "codec": a.codec}))


if __name__ == "__main__":
    main()
