"""The worst remaining contacts AS THE CCTV CAMERA SEES THEM (Rexton 1 Nov: judge them in the real view, not a close-up):
for the deepest row of each of the N worst visible collision pairs, the camera that sees it renders that frame at its
own resolution in the scene's look; a 480 x 300 px window round the contact (1:1 pixels) is saved, with the point marked.

  blender -b <final.blend> -P assets/hub/cctv_crops.py -- --gates <gates dir> --out <dir> [--n 10]
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument("--gates", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--n", type=int, default=10)
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
sc = bpy.context.scene
out = Path(a.out).resolve()
out.mkdir(parents=True, exist_ok=True)
rows = json.loads((Path(a.gates) / "rows_in_view.json").read_text(encoding="utf-8"))["seen_rows"]
by = defaultdict(list)
for r in rows:
    by[(r["a"].split("_body")[0], r["b"].split("_body")[0])].append(r)
worst = sorted(by.items(), key=lambda kv: -max(float(r["depth_cm"]) for r in kv[1]))[:a.n]
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 2688, 1520, 100
sc.render.image_settings.file_format = "PNG"
lines = []
for i, ((pa, pb), rs) in enumerate(worst):
    r = max(rs, key=lambda x: float(x["depth_cm"]))
    f, p = int(r["frame"]), Vector((float(r["x"]), float(r["y"]), float(r["z"])))
    sc.frame_set(f)
    cams = [sc.objects[c] for c in r["cams"]]
    cam = min(cams, key=lambda c: (c.matrix_world.translation - p).length)  # the one nearest it: the most pixels
    sc.camera = cam
    uv = world_to_camera_view(sc, cam, p)
    fn = out / f"{i + 1:02d}_{cam.name}_f{f:03d}"
    sc.render.filepath = str(fn) + "_full.png"
    bpy.ops.render.render(write_still=True)
    px, py = int(uv.x * 2688), int((1 - uv.y) * 1520)
    lines.append(dict(n=i + 1, pair=f"{pa} | {pb}", rows=len(rs), frame=f, depth_cm=r["depth_cm"], camera=cam.name,
                      px=[px, py], dist_m=round((cam.matrix_world.translation - p).length, 1), full=str(fn) + "_full.png"))
    print("CROP", json.dumps(lines[-1]), flush=True)
(out / "crops.json").write_text(json.dumps(lines, indent=1), encoding="utf-8")
