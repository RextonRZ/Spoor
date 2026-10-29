"""Render CCTV camera frames in the FINAL look (EEVEE, the scene's lights / exposure), for review clips and the batch.

  blender -b --factory-startup assets/hub/build/hub_dressed.blend -P assets/hub/render_cctv.py -- \
      --cams CAM_01,CAM_02 --frames 1-300 --out <dir> [--res 1280x720] [--samples 4] [--step 1]

Per camera: high-bay shadows only from the pools this camera sees within 22 m (as dress_hub's previews), all
workers visible. Frames -> <out>/<CAM>/####.png; then cctv_batch.py adds lens / sensor / OSD and encodes.
Prints s/frame per camera.
"""
import argparse
import math
import sys
import time
from pathlib import Path

import bpy
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument("--cams", required=True)
ap.add_argument("--frames", default="1-300")
ap.add_argument("--out", required=True)
ap.add_argument("--res", default="1280x720")
ap.add_argument("--samples", type=int, default=4)
ap.add_argument("--step", type=int, default=1)
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
sc = bpy.context.scene
rx, ry = (int(v) for v in args.res.split("x"))
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, 100
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_depth = "8"
sc.eevee.taa_render_samples = args.samples
sc.render.use_stamp = False
F0, F1 = (int(v) for v in args.frames.split("-"))
for o in sc.objects:
    if o.name.startswith("worker_") and o.type in ("ARMATURE", "MESH"):
        o.hide_render = False
for cid in args.cams.split(","):
    cam = sc.objects[cid]
    sc.camera = cam
    inv = cam.matrix_world.inverted()
    tx = math.tan(cam.data.angle_x / 2)
    ty = tx * ry / rx
    for o in sc.objects:
        if o.type == "LIGHT" and o.name.startswith("highbay_"):
            vis = False
            if math.hypot(o.location.x - cam.location.x, o.location.y - cam.location.y) <= 22:
                for dx, dy in ((0, 0), (4, 0), (-4, 0), (0, 4), (0, -4)):
                    pc = inv @ Vector((o.location.x + dx, o.location.y + dy, 0.5))
                    if pc.z < -0.1 and abs(pc.x / -pc.z) <= tx and abs(pc.y / -pc.z) <= ty:
                        vis = True
            o.data.use_shadow = vis
    out = Path(args.out).resolve() / cid
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    n = 0
    for f in range(F0, F1 + 1, args.step):
        p = out / f"{f:04d}.png"
        if p.exists():
            continue  # resumable
        sc.frame_set(f)
        sc.render.filepath = str(p)
        bpy.ops.render.render(write_still=True)
        n += 1
    print(f"CCTV {cid} frames={n} s_per_frame={(time.time() - t0) / max(n, 1):.2f}", flush=True)
