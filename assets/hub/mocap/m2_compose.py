"""M2 proof video: retargeted avatar (EEVEE front + side) next to the source BVH stick figure, drawn with the SAME
orthographic projection (scaled by the leg ratio, placed like the root), with the AndyData action label of that moment.

  py -X utf8 assets/hub/mocap/m2_compose.py qa/review/m2 <labels.csv> <t0> <fps>
"""
import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

D = Path(sys.argv[1])
labels, t0, fps = sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
z = np.load(D / "m2_src.npz")
src, names, parents = z["src"], list(z["names"]), list(z["parents"])
cam = json.load(open(D / "m2_cams.json"))
qa = json.load(open(D / "m2_qa.json"))
W = cam["res"]
ACT = {"Re": "reach", "Pi": "pick", "Ca": "carry", "Pl": "place", "Rl": "release", "Id": "idle", "Fm": "fine manip.",
       "Sc": "screw"}
rows = list(csv.DictReader(open(labels, encoding="utf-8")))
lt = np.array([float(r["t_video"]) for r in rows])


def label(t):
    r = rows[int(np.clip(np.searchsorted(lt, t), 0, len(rows) - 1))]
    v = [r[f"current_action_Annotator{k}"] for k in (1, 2, 3)]
    a = max(set(v), key=v.count)
    return ACT.get(a, a), r["detailed_posture_Annotator1"]


def proj(p, view):
    u = (p[0] - cam["cx"]) if view == "front" else (p[1] - cam["cy"])
    return W / 2 + u / cam["ortho"] * W, W / 2 - (p[2] - cam["cz"]) / cam["ortho"] * W


try:
    font = ImageFont.truetype("arial.ttf", 20)
    small = ImageFont.truetype("arial.ttf", 16)
except OSError:
    font = small = ImageFont.load_default()
out = D / "composite"
out.mkdir(exist_ok=True)
F = src.shape[0]
for f in range(F):
    sheet = Image.new("RGB", (4 * W, W + 70), (25, 25, 25))
    d = ImageDraw.Draw(sheet)
    for k, view in enumerate(("front", "side")):
        im = Image.open(D / "frames" / f"{view}_{f + 1:04d}.png").convert("RGB")
        sheet.paste(im, (2 * k * W, 70))
        st = Image.new("RGB", (W, W), (40, 42, 46))
        sd = ImageDraw.Draw(st)
        fy = proj((cam["cx"], cam["cy"], 0.0), view)[1]
        sd.line([(0, fy), (W, fy)], fill=(90, 90, 90), width=1)
        for j, pj in enumerate(parents):
            if pj < 0:
                continue
            nm = names[j]
            col = (80, 170, 255) if nm.startswith("Left") else (255, 120, 80) if nm.startswith("Right") else (230, 230, 230)
            sd.line([proj(src[f, pj], view), proj(src[f, j], view)], fill=col, width=4)
        for j in range(len(names)):
            x, y = proj(src[f, j], view)
            sd.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(255, 255, 255))
        sheet.paste(st, ((2 * k + 1) * W, 70))
        d.text((2 * k * W + 8, 74), f"retargeted ({view})", fill=(255, 255, 0), font=small)
        d.text(((2 * k + 1) * W + 8, 74), f"source BVH ({view}), x leg ratio", fill=(255, 255, 0), font=small)
    t = t0 + f / fps
    act, post = label(t)
    d.text((10, 8), f"M2 retarget: AndyData {qa['bvh'].split('.')[0]} -> Rocketbox {qa['avatar']}   "
                    f"t = {t:6.2f} s   frame {f + 1}/{F}", fill=(240, 240, 240), font=font)
    tw = max(qa["twist_max_deg"].values())
    d.text((10, 38), f"label: {act.upper()}  ({post})     QA (evaluated pose): foot skate max {qa['foot_skate_max_mm']} mm "
                     f"over {len(qa['contacts'])} contacts, ground-pen frames {qa['ground_pen_frames']}, limb-dir err max "
                     f"{qa['limb_dir_err_max_deg']} deg, twist max {tw} deg, leg ratio {qa['leg_scale']}",
           fill=(200, 230, 200), font=small)
    sheet.save(out / f"c_{f + 1:04d}.png")
mp4 = D / "m2_retarget_front_side.mp4"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(out / "c_%04d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", str(mp4)], check=True)
# 1 fps sheet
idx = list(range(0, F, int(fps)))
th = [Image.open(out / f"c_{i + 1:04d}.png").resize((4 * W // 3, (W + 70) // 3)) for i in idx]
cols = 2
sh = Image.new("RGB", (cols * th[0].width, ((len(th) + cols - 1) // cols) * th[0].height))
for i, im in enumerate(th):
    sh.paste(im, ((i % cols) * im.width, (i // cols) * im.height))
sh.save(D / "m2_sheet_1fps.jpg", quality=85)
print("wrote", mp4, mp4.stat().st_size // 1024, "KB")
