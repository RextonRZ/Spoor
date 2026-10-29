"""Final-look brightness check: render a camera at the batch settings, classify pixels by what they see (raycast:
floor / wall / roof), report 0-255 stats per class. Targets (review 001 #1): wall mean >= 170, floor mean 85-110,
floor share > 230 = 0 %.

  blender -b --factory-startup <blend> -P assets/hub/look_stats.py -- --cams CAM_07,CAM_13 --out <dir> [--res 1344x760]
      [--exposure X] [--frame 150]
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument("--cams", default="CAM_07,CAM_13")
ap.add_argument("--out", required=True)
ap.add_argument("--res", default="1344x760")
ap.add_argument("--samples", type=int, default=4)
ap.add_argument("--exposure", type=float, default=None)
ap.add_argument("--frame", type=int, default=150)
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
sc = bpy.context.scene
OUT = Path(args.out)
OUT.mkdir(parents=True, exist_ok=True)
W, H = (int(v) for v in args.res.split("x"))
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_depth = "8"
sc.eevee.taa_render_samples = args.samples
if args.exposure is not None:
    sc.view_settings.exposure = args.exposure


def kind(ob):
    n = ob.name.lower()
    if n.startswith(("floor_slab", "floor_")):
        return "floor"
    if n.startswith(("wall", "cladding", "walls")) or "wall" in n:
        return "wall"
    if n.startswith(("roof",)) or "truss" in n or "purlin" in n:
        return "roof"
    return None


res = {}
for cid in args.cams.split(","):
    cam = sc.objects[cid]
    sc.camera = cam
    inv = cam.matrix_world.inverted()
    tx = math.tan(cam.data.angle_x / 2)
    ty = tx * H / W
    for o in sc.objects:  # shadows only from pools this camera sees within 22 m (as the batch)
        if o.type == "LIGHT" and o.name.startswith("highbay_"):
            vis = False
            if math.hypot(o.location.x - cam.location.x, o.location.y - cam.location.y) <= 22:
                for dx, dy in ((0, 0), (4, 0), (-4, 0), (0, 4), (0, -4)):
                    pc = inv @ Vector((o.location.x + dx, o.location.y + dy, 0.5))
                    if pc.z < -0.1 and abs(pc.x / -pc.z) <= tx and abs(pc.y / -pc.z) <= ty:
                        vis = True
            o.data.use_shadow = vis
    sc.frame_set(args.frame)
    path = OUT / f"{cid}_look.png"
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(str(path))
    px = np.array(img.pixels[:]).reshape(H, W, 4)[::-1, :, :3] * 255.0
    dg = bpy.context.evaluated_depsgraph_get()
    M = cam.matrix_world
    vals = {"floor": [], "wall": [], "roof": []}
    for py in range(0, H, 10):
        for pxi in range(0, W, 10):
            x = (2 * (pxi + 0.5) / W - 1) * tx
            y = (1 - 2 * (py + 0.5) / H) * ty
            d = (M.to_3x3() @ Vector((x, y, -1))).normalized()
            hit, loc, nrm, idx, ob, _ = sc.ray_cast(dg, M.translation, d, distance=200)
            k = kind(ob) if hit else None
            if k:
                vals[k].append(px[py, pxi].mean())
    r = {"frame_mean": round(float(px.mean()), 1)}
    for k, v in vals.items():
        if v:
            a = np.array(v)
            r[k] = {"n": int(a.size), "mean": round(float(a.mean()), 1), "p99": round(float(np.percentile(a, 99)), 1),
                    "over230": round(float((a > 230).mean()), 4)}
    res[cid] = r
    print("LOOK " + json.dumps({cid: r}), flush=True)
print("LOOKALL " + json.dumps({"exposure": sc.view_settings.exposure, "cams": res}), flush=True)
