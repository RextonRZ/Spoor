"""M4 proof video: line A from the hub's CAM_01 (crop over the induction tables) above a front view along the line,
frame / time / per-worker phase burned in; plus a 1 fps sheet.

  py -X utf8 assets/hub/mocap/m4_compose.py qa/review/m4_line_a
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

D = Path(sys.argv[1])
qa = json.load(open(D / "m4_qa.json"))
fps, F = qa["fps"], qa["frames"]
try:
    font = ImageFont.truetype("arial.ttf", 20)
    small = ImageFont.truetype("arial.ttf", 15)
except OSError:
    font = small = ImageFont.load_default()
out = D / "composite"
out.mkdir(exist_ok=True)
grasps = qa["grasp_frames_per_worker"]
for f in range(1, F + 1):
    cc = Image.open(D / "frames" / f"cctv_{f:04d}.png").convert("RGB")
    W, H = cc.size
    cc = cc.crop((int(0.42 * W), int(0.05 * H), int(0.98 * W), int(0.53 * H))).resize((1280, 640))  # line A in CAM_01
    fr = Image.open(D / "frames" / f"front_{f:04d}.png").convert("RGB").resize((1280, 640))
    sheet = Image.new("RGB", (1280, 1280 + 70), (22, 22, 22))
    sheet.paste(cc, (0, 70))
    sheet.paste(fr, (0, 710))
    d = ImageDraw.Draw(sheet)
    d.text((10, 6), f"M4 line A (mocap AndyData, CC BY 4.0): frame {f}/{F}  t = {(f - 1) / fps:5.1f} s",
           fill=(240, 240, 240), font=font)
    line = []
    for w, gl in zip(qa["workers"], grasps):
        nxt = [g for g in gl if g + 1 >= f]
        line.append(f"I{w['k']} {w['avatar']}: next grasp f{nxt[0] + 1}" if nxt else f"I{w['k']} {w['avatar']}")
    d.text((10, 36), " | ".join(line) + f" | min spacing {qa['spacing_min_m']} m", fill=(200, 230, 200), font=small)
    d.text((10, 76), "CCTV: hub CAM_01 (crop)", fill=(255, 255, 0), font=small)
    d.text((10, 716), "front, along line A", fill=(255, 255, 0), font=small)
    sheet.save(out / f"c_{f:04d}.png")
mp4 = D / "m4_line_a_cctv_front.mp4"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(out / "c_%04d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "21", str(mp4)], check=True)
idx = list(range(1, F + 1, int(fps)))
th = [Image.open(out / f"c_{i:04d}.png").resize((427, 450)) for i in idx]
cols = 6
sh = Image.new("RGB", (cols * 427, ((len(th) + cols - 1) // cols) * 450))
for i, im in enumerate(th):
    sh.paste(im, ((i % cols) * 427, (i // cols) * 450))
sh.save(D / "m4_sheet_1fps.jpg", quality=80)
print("wrote", mp4, mp4.stat().st_size // 1024, "KB")
