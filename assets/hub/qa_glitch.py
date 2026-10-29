"""Glitch scan of rendered camera clips + contact sheets for the vision self-review.

  py -X utf8 assets/hub/qa_glitch.py [--videos assets/hub/build/qa/cctv] [--sheets]

Per clip, every frame (decoded with ffmpeg), the burned-in label box masked out:
  glitch_brightness   mean brightness jumps > 4 levels AND > 5x the clip's typical frame-to-frame change
  glitch_magenta      > 0.05 % of pixels pure magenta (Blender's missing-texture colour)
  glitch_black        black area grows by > 1 % of the frame in one frame (a surface turned black / a hole)
  glitch_pop          changed area spikes > 4x its neighbourhood (something appeared / vanished);
                      'one-frame' if the frame before and after match (a flash), else 'stays' (popped in/out)
Rows go to qa/glitch_flags.csv and replace earlier glitch_* rows in qa/auto_flags.csv.
--sheets: qa/review_sheets/<clip>.jpg, every 10th frame (30 tiles, frame numbers) of every clip in qa/workers and
qa/cctv, for the self-review.
"""

import argparse
import csv
import statistics
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HUB = Path(__file__).resolve().parent
QA = HUB / "build" / "qa"
ap = argparse.ArgumentParser()
ap.add_argument("--videos", default=str(QA / "cctv"))
ap.add_argument("--sheets", action="store_true")
args = ap.parse_args()


def frames(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    w, h = (int(x) for x in r.stdout.strip().split(","))
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         stdout=subprocess.PIPE)
    n = w * h * 3
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        yield np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 3)
    p.wait()


def scan(path):
    rows, means, mag, blk, chg, prev2, prev = [], [], [], [], [], None, None
    one_frame = []
    for k, fr in enumerate(frames(path)):
        a = fr.astype(np.int16)
        a[:40, :760] = 0  # burned-in label
        means.append(float(a.mean()))
        mag.append(float(((a[..., 0] > 200) & (a[..., 1] < 70) & (a[..., 2] > 200)).mean()))
        blk.append(float((a.sum(axis=2) < 15).mean()))
        if prev is None:
            chg.append(0.0)
            one_frame.append(False)
        else:
            chg.append(float((np.abs(a - prev).max(axis=2) > 40).mean()))
            one_frame.append(prev2 is not None and float((np.abs(a - prev2).max(axis=2) > 40).mean()) < 0.3 * chg[-1])
        prev2, prev = prev, a
    n = len(means)
    dm = [abs(means[i] - means[i - 1]) for i in range(1, n)]
    typ = statistics.median(dm) if dm else 0
    for i in range(1, n):
        f = i + 1
        if dm[i - 1] > 4 and dm[i - 1] > 5 * max(typ, 0.2):
            rows.append((f, "glitch_brightness", "high", f"brightness jumps {dm[i - 1]:.1f} levels (typical {typ:.2f})"))
        if blk[i] - blk[i - 1] > 0.01:
            rows.append((f, "glitch_black", "high", f"black area +{(blk[i] - blk[i - 1]) * 100:.1f} % of the frame"))
        win = chg[max(1, i - 6):i - 1] + chg[i + 2:i + 7]
        base = statistics.median(win) if win else 0
        if chg[i] > 0.003 and chg[i] > 4 * max(base, 1e-4):
            kind = "one-frame flash" if (i + 1 < n and one_frame[i + 1]) else "stays (popped in/out)"
            rows.append((f, "glitch_pop", "high" if chg[i] > 0.02 else "medium",
                         f"{chg[i] * 100:.2f} % of the frame changes at once (typical {base * 100:.2f} %): {kind}"))
    for i in range(n):
        if mag[i] > 0.0005:
            rows.append((i + 1, "glitch_magenta", "high", f"{mag[i] * 100:.2f} % magenta (missing texture?)"))
    return rows, n


def contact_sheet(path, out):
    font = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 18)
    tiles = []
    for k, fr in enumerate(frames(path)):
        f = k + 1
        if f == 1 or f % 10 == 0:
            im = Image.fromarray(fr).resize((320, 180))
            d = ImageDraw.Draw(im)
            d.rectangle([0, 160, 58, 180], fill=(0, 0, 0))
            d.text((3, 160), f"{f:03d}", font=font, fill=(255, 255, 0))
            tiles.append(im)
    tiles = tiles[:31]
    cols = 6
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (320 * cols, 180 * rows), (20, 20, 20))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * 320, (i // cols) * 180))
    sheet.save(out, quality=82)


if __name__ == "__main__":
    vids = sorted(Path(args.videos).glob("*.mp4"))
    allrows = []
    for v in vids:
        rows, n = scan(v)
        print(f"GLITCH {v.stem}: {n} frames, {len(rows)} flags", flush=True)
        allrows += [[v.stem, "camera", "-", f, f, chk, sev, det] for f, chk, sev, det in rows]
    hdr = ["worker_name", "role", "clip_name", "frame_start", "frame_end", "check", "severity", "detail"]
    with open(QA / "glitch_flags.csv", "w", newline="", encoding="utf-8") as fh:
        cw = csv.writer(fh)
        cw.writerow(hdr)
        cw.writerows(allrows)
    af = QA / "auto_flags.csv"
    if af.exists():
        old = [r for r in csv.reader(open(af, encoding="utf-8"))][1:]
        old = [r for r in old if not r[5].startswith("glitch_")]
        with open(af, "w", newline="", encoding="utf-8") as fh:
            cw = csv.writer(fh)
            cw.writerow(hdr)
            cw.writerows(old + allrows)
    print(f"GLITCH total {len(allrows)} flags", flush=True)
    if args.sheets:
        sd = QA / "review_sheets"
        sd.mkdir(exist_ok=True)
        for v in sorted((QA / "workers").glob("*.mp4")) + sorted((QA / "cctv").glob("*.mp4")):
            contact_sheet(v, sd / f"{v.stem}.jpg")
        print("SHEETS", len(list(sd.glob("*.jpg"))), flush=True)
