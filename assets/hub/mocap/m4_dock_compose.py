"""M4 dock proof video: CAM_02 (crop on the D05 door) | inside the trailer by the door | behind the unloader; frame,
time and carton phase burned in; plus a 1 fps sheet.

  py -X utf8 assets/hub/mocap/m4_dock_compose.py qa/review/m4_dock
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

D = Path(sys.argv[1])
qa = json.load(open(D / "m4_dock_qa.json"))
F, fps = qa["frames"], 10.0
try:
    font = ImageFont.truetype("arial.ttf", 20)
    small = ImageFont.truetype("arial.ttf", 15)
except OSError:
    font = small = ImageFont.load_default()


def phase(f):
    for n, (g, r) in qa["cartons"].items():
        if g - 8 <= f < g:
            return f"reach to wall carton {n} (top {qa['pick_heights_m'][n]} m)"
        if g <= f <= r:
            return f"carton {n} in the hands"
        if r < f <= r + 8:
            return f"carton {n} on the boom nose"
    return ""


out = D / "composite"
out.mkdir(exist_ok=True)
for f in range(1, F + 1):
    cc = Image.open(D / "frames" / f"cctv_{f:04d}.png").convert("RGB")
    W, H = cc.size
    cx, cy = 0.40 * W, (1 - 0.90) * H  # the worker in CAM_02 (probe: 0.39, 0.84)
    box = (int(max(0, cx - 0.2 * W)), int(max(0, cy - 0.02 * H)), int(min(W, cx + 0.2 * W)), int(min(H, cy + 0.5 * H)))
    cc = cc.crop(box).resize((640, 640))
    dr = Image.open(D / "frames" / f"door_{f:04d}.png").convert("RGB")
    bh = Image.open(D / "frames" / f"behind_{f:04d}.png").convert("RGB")
    sheet = Image.new("RGB", (1920, 640 + 60), (22, 22, 22))
    for i, im in enumerate((cc, dr, bh)):
        sheet.paste(im, (640 * i, 60))
    d = ImageDraw.Draw(sheet)
    d.text((10, 6), f"M4 dock unloader D05 (mocap AndyData, CC BY 4.0): frame {f}/{F}  t = {(f - 1) / fps:5.1f} s   "
                    f"{phase(f)}", fill=(240, 240, 240), font=font)
    d.text((10, 34), "CAM_02 (crop) | inside the trailer, by the door | behind him", fill=(255, 255, 0), font=small)
    sheet.save(out / f"c_{f:04d}.png")
mp4 = D / "m4_dock_cctv_door_behind.mp4"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(out / "c_%04d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "21", str(mp4)], check=True)
idx = list(range(1, F + 1, int(fps)))
th = [Image.open(out / f"c_{i:04d}.png").resize((960, 350)) for i in idx]
sh = Image.new("RGB", (2 * 960, ((len(th) + 1) // 2) * 350))
for i, im in enumerate(th):
    sh.paste(im, ((i % 2) * 960, (i // 2) * 350))
sh.save(D / "m4_dock_sheet_1fps.jpg", quality=80)
print("wrote", mp4)
