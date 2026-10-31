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

bpy.context.preferences.system.anisotropic_filter = "FILTER_16"  # (factory 2x: the shutter slats and wall
# ribs alias into bands at grazing angles - review mesh_hygiene, CAM_01 at D01)
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument("--cams", required=True)
ap.add_argument("--frames", default="1-300")
ap.add_argument("--out", required=True)
ap.add_argument("--res", default="1280x720")
ap.add_argument("--raytrace", type=int, default=-1)  # -1: as saved
ap.add_argument("--exposure", type=float, default=None)
ap.add_argument("--shadow-scale", type=float, default=-1.0)
ap.add_argument("--samples", type=int, default=4)
ap.add_argument("--step", type=int, default=1)
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
sc = bpy.context.scene
if args.raytrace >= 0:
    sc.eevee.use_raytracing = bool(args.raytrace)
if args.exposure is not None:
    sc.view_settings.exposure = args.exposure
if args.shadow_scale > 0:
    sc.eevee.shadow_resolution_scale = args.shadow_scale
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
for o in sc.objects:  # the LED rows are shadowless fill; shadows come from the high-bay spots near each camera
    if o.type == "LIGHT" and o.name.startswith("ledrow_"):
        o.data.use_shadow = False
# each camera runs its own auto-exposure: the yard camera looks at overcast daylight, the hall's exposure blew it out
# (B2 stills: CAM_17 mean 153 vs 105-119 indoors, 2.4 % clipped; -1.1 EV -> see log)
AE_OFFSET = {"CAM_17": -1.1}
base_exposure = sc.view_settings.exposure
for cid in args.cams.split(","):
    cam = sc.objects[cid]
    sc.camera = cam
    sc.view_settings.exposure = base_exposure + AE_OFFSET.get(cid, 0.0)
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
