"""Close-ups of the worst collision groups (review: "where the biggest remaining groups are, with crops"): for each of
the N largest (object pair) groups in collisions.csv, a workbench render 0.9 m from its deepest hit, looking at it.

  blender -b --factory-startup <scenario.blend> -P assets/hub/collision_crops.py -- --csv <collisions.csv> --out <dir>
      [--n 12]
"""
import argparse
import collections
import csv
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument("--csv", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--n", type=int, default=12)
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
OUT = Path(a.out)
OUT.mkdir(parents=True, exist_ok=True)
rows = list(csv.DictReader(open(a.csv, encoding="utf-8")))
groups = collections.defaultdict(list)
for r in rows:
    groups[(r["a"], r["b"])].append(r)
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.render.image_settings.file_format = "PNG"  # (the scene may be set to a video format: stills failed silently)
sc.display.shading.light = "STUDIO"
sc.display.shading.color_type = "MATERIAL"
sc.render.resolution_x, sc.render.resolution_y = 520, 400
cam = bpy.data.objects.new("crop_cam", bpy.data.cameras.new("crop_cam"))
cam.data.lens = 35
cam.data.clip_start = 0.05
sc.collection.objects.link(cam)
sc.camera = cam
lines = []
for k, ((oa, ob), rs) in enumerate(sorted(groups.items(), key=lambda kv: -len(kv[1]))[:a.n]):
    r = max(rs, key=lambda x: float(x["depth_cm"]))
    f = int(r["frame"])
    sc.frame_set(f)
    at = Vector((float(r["x"]), float(r["y"]), float(r["z"])))
    for ang in (0.7, 2.4):  # two views round the point
        d = Vector((math.cos(ang), math.sin(ang), 0.45)).normalized()
        cam.location = at + d * 0.9
        cam.rotation_euler = (at - cam.location).to_track_quat("-Z", "Y").to_euler()
        fn = f"{k + 1:02d}_{oa[:24]}__{ob[:24]}_f{f:03d}_{'a' if ang < 1 else 'b'}.png"
        sc.render.filepath = str(OUT / fn)
        bpy.ops.render.render(write_still=True)
    lines.append(f"{k + 1:02d}  {len(rs):4d} frame-hits  {oa} | {ob}  deepest {r['depth_cm']} cm at f{f} "
                 f"({r['x']}, {r['y']}, {r['z']}) {r.get('bone', '')}")
    print("CROP", lines[-1], flush=True)
(OUT / "groups.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
