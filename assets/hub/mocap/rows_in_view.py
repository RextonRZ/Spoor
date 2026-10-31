"""Which collision rows can a scenario's cameras see? (S2 gate scoping: a contact nobody films is not in the footage,
but every one a rendered camera sees must be 0.) For each row of collision_check.py's CSV: in the frame (1 % in from
its edge), kept by the lens crop (cctv_look barrel remap, render_truth k1), and not hidden behind the static hub
(ray from the camera to the contact point; the two objects in contact are ignored, people / parcels never block).

  blender -b <scenario.blend> -P assets/hub/mocap/rows_in_view.py -- --csv <collisions.csv> --cams CAM_01,CAM_06
          --out <json>
"""
import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import bpy
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument("--csv", required=True)
ap.add_argument("--cams", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
sc = bpy.context.scene
RX, RY = 2688, 1520
TRUTH = json.loads((Path(__file__).resolve().parents[1] / "render_truth.json").read_text())["cameras"]
MOVING = ("worker_", "flow_parcel", "parcel_", "bag_", "cage_rolling", "sack_")


def lens_keeps(cam, x, y):
    k1 = TRUTH.get(cam.name, {}).get("lens_k1", -0.06)
    f = RX / (2 * math.tan(cam.data.angle_x / 2))
    dx, dy = x - RX / 2, y - RY / 2
    r_in = math.hypot(dx, dy)
    if r_in < 1:
        return True
    t_edge = min((RX / 2) / abs(dx) if abs(dx) > 1e-9 else 1e9, (RY / 2) / abs(dy) if abs(dy) > 1e-9 else 1e9)
    ex, ey = dx * t_edge / f, dy * t_edge / f
    s_ = (1 - k1 * (ex * ex + ey * ey)) / (1 - k1 * (RX / 2 / f) ** 2)
    return r_in <= math.hypot(ex, ey) * f * s_ - 2


def sees(cam, p, ignore, dg):
    pc = cam.matrix_world.inverted() @ p
    if pc.z > -0.1:
        return False
    tx = math.tan(cam.data.angle_x / 2)
    ty = tx * RY / RX
    if abs(pc.x / -pc.z) > tx * 0.98 or abs(pc.y / -pc.z) > ty * 0.98:
        return False
    if not lens_keeps(cam, RX / 2 + pc.x / -pc.z / tx * RX / 2, RY / 2 - pc.y / -pc.z / ty * RY / 2):
        return False
    o = cam.matrix_world.translation
    d = p - o
    L = d.length
    org = o.copy()
    for _ in range(12):
        hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, org, d.normalized(), distance=max(0.0, L - (org - o).length - 0.03))
        if not hit:
            return True
        if ob.name in ignore or ob.name.startswith(MOVING):
            org = loc + d.normalized() * 0.005
            continue
        return False
    return True


cams = [sc.objects[c] for c in a.cams.split(",") if c in sc.objects]
rows = list(csv.DictReader(open(a.csv)))
by_frame = defaultdict(list)
for r in rows:
    by_frame[int(r["frame"])].append(r)
seen_rows = []
for f in sorted(by_frame):
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    for r in by_frame[f]:
        p = Vector((float(r["x"]), float(r["y"]), float(r["z"])))
        vis = [c.name for c in cams if sees(c, p, {r["a"], r["b"]}, dg)]
        if vis:
            seen_rows.append(dict(r, cams=vis))
pair = Counter((r["a"].split("_body")[0], r["b"].split("_body")[0]) for r in seen_rows)
by_cam = Counter(c for r in seen_rows for c in r["cams"])
out = dict(rows=len(rows), seen=len(seen_rows), by_cam=dict(by_cam), by_pair=[(f"{k[0]} | {k[1]}", v) for k, v in
                                                                             pair.most_common(60)],
           seen_rows=seen_rows)
Path(a.out).write_text(json.dumps(out, indent=1))
print("INVIEW", json.dumps({k: v for k, v in out.items() if k != "seen_rows"})[:3000])
