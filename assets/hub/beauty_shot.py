"""Beauty shots of the S2 hub for the landing page's closing section (a working-environment backdrop, not a CCTV view).
Adds free cameras to a saved S2 blend, renders one frame each with the batch look (EEVEE), and writes PNGs.

  blender -b <blend> -P assets/hub/beauty_shot.py -- --cams A:58,2,7:36,20,1:30 B:... --frame 400 --out DIR [--res 1920x1080 --samples 16]

A camera is NAME:x,y,z:tx,ty,tz:lens_mm (look-at target). The page's backdrop is a render of the hub's own model
(people are the Rocketbox/Mixamo rigs already animated in the blend); nothing here is generated imagery.
"""
import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument("--cams", nargs="+", required=True)
ap.add_argument("--frame", type=int, default=400)
ap.add_argument("--out", required=True)
ap.add_argument("--res", default="960x540")
ap.add_argument("--samples", type=int, default=4)
ap.add_argument("--exposure", type=float, default=0.2)
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])

sc = bpy.context.scene
rx, ry = (int(v) for v in args.res.split("x"))
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, 100
sc.render.image_settings.file_format = "PNG"
sc.render.use_stamp = False
sc.eevee.taa_render_samples = args.samples
sc.eevee.use_raytracing = False
sc.eevee.shadow_resolution_scale = 0.5
sc.view_settings.exposure = args.exposure
for o in sc.objects:
    if o.name.startswith("worker_") and o.type in ("ARMATURE", "MESH"):
        o.hide_render = False
    if o.type == "LIGHT" and o.name.startswith("ledrow_"):
        o.data.use_shadow = False
out = Path(args.out).resolve()
out.mkdir(parents=True, exist_ok=True)
sc.frame_set(args.frame)
for spec in args.cams:
    name, loc, tgt, lens = spec.split(":")
    cd = bpy.data.cameras.new(f"BEAUTY_{name}")
    cd.lens = float(lens)
    cd.sensor_width = 36
    cam = bpy.data.objects.new(f"BEAUTY_{name}", cd)
    sc.collection.objects.link(cam)
    cam.location = Vector([float(v) for v in loc.split(",")])
    d = Vector([float(v) for v in tgt.split(",")]) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    cam_xy = cam.location
    for o in sc.objects:  # shadowed high-bays only near the view, as the CCTV renders do
        if o.type == "LIGHT" and o.name.startswith("highbay_"):
            o.data.use_shadow = math.hypot(o.location.x - cam_xy.x, o.location.y - cam_xy.y) <= 26
    sc.render.filepath = str(out / f"{name}_{args.frame:04d}.png")
    bpy.ops.render.render(write_still=True)
    print("BEAUTY", name, sc.render.filepath, flush=True)
