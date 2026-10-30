"""Review 014c #1: prove the SOURCE reference pose. Draws the BVH skeleton at all-zero channels (front + top) and at
its frame 0 (front, turned to face the camera), with the measured arm / leg angles, next to our Rocketbox T-pose (M1)
and the retargeted avatar at frame 0.

  py -X utf8 assets/hub/mocap/ref_pose.py <bvh> <rocketbox_tpose_front.png> <avatar_frame0.png> <out.png>
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import retarget as R  # noqa: E402

bvh, tpose_png, f0_png, out = sys.argv[1:5]
b = R.read_bvh(bvh)
J = {n: i for i, n in enumerate(b["names"])}
par = b["parents"]
# zero channels: every joint at its offset, no rotation
Z = np.zeros((len(par), 3))
for j, p in enumerate(par):
    Z[j] = b["offs"][j] + (Z[p] if p >= 0 else 0)
G0, P0 = R.fk(b, np.array([0]))
F0 = P0[0] - P0[0, J["Hips"]] * np.array([1, 0, 1])
f = G0[0, J["Hips"]] @ np.array([0, 0, 1.0])
yaw = math.atan2(f[0], f[2])
c, s = math.cos(-yaw), math.sin(-yaw)
Ry = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
F0 = F0 @ Ry.T


def ang(P, a, b_, ref):
    d = P[J[b_]] - P[J[a]]
    return math.degrees(math.acos(np.clip(np.dot(d, ref) / np.linalg.norm(d), -1, 1)))


meas = [f"zero pose: L arm {ang(Z, 'LeftShoulder', 'LeftWrist', np.array([1, 0, 0])):.2f} deg off +X (lateral, "
        f"horizontal), R arm {ang(Z, 'RightShoulder', 'RightWrist', np.array([-1, 0, 0])):.2f} deg off -X",
        f"zero pose: legs {ang(Z, 'LeftHip', 'LeftAnkle', np.array([0, -1, 0])):.2f} / "
        f"{ang(Z, 'RightHip', 'RightAnkle', np.array([0, -1, 0])):.2f} deg off vertical; spine "
        f"{ang(Z, 'Hips', 'Neck', np.array([0, 1, 0])):.2f} deg off vertical; feet point +Z (forward)",
        f"frame 0 (row 0 = Xsens' measured T): arms {ang(F0, 'LeftShoulder', 'LeftWrist', np.array([1, 0, 0])):.1f} / "
        f"{ang(F0, 'RightShoulder', 'RightWrist', np.array([-1, 0, 0])):.1f} deg off lateral; its non-zero channels: "
        f"spine/neck/hips/knees/ankles sagittal only (max {np.abs(b['data'][0, 3:]).max():.1f} deg), elbows/wrists +-2.3 "
        f"deg -> the all-zero pose is the clean T it was calibrated on; we align to the zero pose"]
W = 520
try:
    font = ImageFont.truetype("arial.ttf", 18)
    big = ImageFont.truetype("arial.ttf", 22)
except OSError:
    font = big = ImageFont.load_default()


def stick(P, view, title, scale=None):
    im = Image.new("RGB", (W, W), (40, 42, 46))
    d = ImageDraw.Draw(im)
    if view == "front":
        uv = np.stack([P[:, 0], P[:, 1]], 1)
    else:  # top: +X right, +Z (forward) down
        uv = np.stack([P[:, 0], -P[:, 2]], 1)
    cen = (uv.max(0) + uv.min(0)) / 2
    sc = scale or 0.8 * W / max(np.ptp(uv[:, 0]), np.ptp(uv[:, 1]), 1)
    xy = lambda k: (W / 2 + (uv[k, 0] - cen[0]) * sc, W / 2 - (uv[k, 1] - cen[1]) * sc)  # noqa: E731
    for j, p in enumerate(par):
        if p < 0:
            continue
        nm = b["names"][j]
        col = (80, 170, 255) if nm.startswith("Left") else (255, 120, 80) if nm.startswith("Right") else (230, 230, 230)
        d.line([xy(p), xy(j)], fill=col, width=5)
    for j, e in b["ends"].items():
        q = P[j] + np.array(e) @ (np.eye(3) if P is Z else Ry.T)
        u = np.array([q[0], q[1]]) if view == "front" else np.array([q[0], -q[2]])
        d.line([xy(j), (W / 2 + (u[0] - cen[0]) * sc, W / 2 - (u[1] - cen[1]) * sc)], fill=(170, 170, 170), width=3)
    d.text((8, 8), title, fill=(255, 255, 0), font=font)
    d.text((8, W - 28), "blue = Left, orange = Right; viewer faces the actor" if view == "front" else
           "seen from above, actor faces down the image", fill=(200, 200, 200), font=font)
    return im, sc


a1, sc = stick(Z, "front", "BVH all-zero channels (front)")
a2, _ = stick(Z, "top", "BVH all-zero channels (top)")
a3, _ = stick(F0, "front", "BVH frame 0 (front)", sc)
a4 = Image.open(tpose_png).convert("RGB").resize((W, W))
ImageDraw.Draw(a4).text((8, 8), "our Rocketbox T-pose (M1, front)", fill=(255, 255, 0), font=font)
a5 = Image.open(f0_png).convert("RGB").resize((W, W))
ImageDraw.Draw(a5).text((8, 8), "retargeted avatar at frame 0", fill=(255, 255, 0), font=font)
sheet = Image.new("RGB", (5 * W, W + 120), (25, 25, 25))
for k, im in enumerate((a1, a2, a3, a4, a5)):
    sheet.paste(im, (k * W, 120))
d = ImageDraw.Draw(sheet)
d.text((10, 6), f"Source reference pose: {Path(bvh).name}", fill=(240, 240, 240), font=big)
for k, m in enumerate(meas):
    d.text((10, 38 + 24 * k), m, fill=(200, 230, 200), font=font)
sheet.save(out)
print("\n".join(meas))
