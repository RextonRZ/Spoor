"""M3 proof video: CCTV (the hub's CAM_01, crop around the inductor) | front | side, with frame, time, phase and the
QA headline burned in; plus a 1 fps sheet.

  py -X utf8 assets/hub/mocap/m3_compose.py qa/review/m3_hub
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

D = Path(sys.argv[1])
qa = json.load(open(D / "m3_qa.json"))
ev = qa["events"]
fps = qa["fps"]
F = qa["frames"]
try:
    font = ImageFont.truetype("arial.ttf", 20)
    small = ImageFont.truetype("arial.ttf", 15)
except OSError:
    font = small = ImageFont.load_default()


def phase(f):
    for n, e in ev.items():
        g, r = e["grasp"], e["release"]
        if g - 8 <= f < g:
            return f"reach to carton {n}"
        if g <= f <= r:
            return f"carton {n} in the hands"
        if r < f <= r + 9:
            return f"carton {n} released (belt waits {e.get('belt_wait_s')} s)"
    return ""


def cctv_crop(im):
    # inductor I2 sits at about (0.62, 0.67) of CAM_01's frame (probe): a 3:4 crop around it, scaled to 480 x 640
    W, H = im.size
    cx, cy = 0.62 * W, (1 - 0.67) * H
    w, h = 0.30 * W, 0.40 * W
    box = (int(cx - w / 2), int(cy - h * 0.55), int(cx + w / 2), int(cy + h * 0.45))
    return im.crop(box).resize((480, 640))


out = D / "composite"
out.mkdir(exist_ok=True)
tw = max(qa["twist_max_deg"].values()) if "twist_max_deg" in qa else None
for f in range(1, F + 1):
    cc = Image.open(D / "frames" / f"cctv_{f:04d}.png").convert("RGB")
    fr = Image.open(D / "frames" / f"front_{f:04d}.png").convert("RGB")
    sd = Image.open(D / "frames" / f"side_{f:04d}.png").convert("RGB")
    sheet = Image.new("RGB", (480 + 640 + 640, 640 + 76), (22, 22, 22))
    sheet.paste(cctv_crop(cc), (0, 76))
    sheet.paste(fr, (480, 76))
    sheet.paste(sd, (1120, 76))
    d = ImageDraw.Draw(sheet)
    d.text((10, 6), f"M3 inductor I2 (mocap: AndyData, CC BY 4.0) - frame {f}/{F}  t = {(f - 1) / fps:5.1f} s   "
                    f"{phase(f)}", fill=(240, 240, 240), font=font)
    d.text((10, 34), f"QA (evaluated pose): cycles {qa['cycles']} at {qa['cycle_s']['min']}-{qa['cycle_s']['max']} s | "
                     f"hand skin to carton on holds {qa['hand_skin_to_carton_mm']['min']}..{qa['hand_skin_to_carton_mm']['max']} mm | "
                     f"foot skate max {qa['foot_skate_mm_max']} mm | ground pen {qa['ground_pen_frames']} frames",
           fill=(200, 230, 200), font=small)
    d.text((10, 54), "CCTV = hub CAM_01 (crop)        front (across belt A)        side", fill=(255, 255, 0), font=small)
    sheet.save(out / f"c_{f:04d}.png")
mp4 = D / "m3_inductor_cctv_front_side.mp4"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(out / "c_%04d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", str(mp4)], check=True)
idx = list(range(1, F + 1, int(fps)))
th = [Image.open(out / f"c_{i:04d}.png").resize((880, 358)) for i in idx]
cols = 3
sh = Image.new("RGB", (cols * 880, ((len(th) + cols - 1) // cols) * 358))
for i, im in enumerate(th):
    sh.paste(im, ((i % cols) * 880, (i // cols) * 358))
sh.save(D / "m3_sheet_1fps.jpg", quality=82)
print("wrote", mp4, mp4.stat().st_size // 1024, "KB")
