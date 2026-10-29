"""Close review crops in the FINAL look (EEVEE, the scene's own lights / exposure), from a free review camera.

  blender -b --factory-startup assets/hub/build/hub_dressed.blend -P assets/hub/qa_crops.py -- \
      --job dockD05:-3.6,23.0,1.85:-6.0,23.0,1.0:28 --frames 1,40,80 --out <dir> [--res 1280x720] [--samples 8]
      [--visible -5.97,23.64,1.5]   (also print which CCTV cameras see these points: raycast, in frame)

job = name:camera_xyz:target_xyz:lens_mm. Frames are written as <out>/<name>_####.png. Review cameras are never
CCTV views: they only exist to check contact up close; the SYNTHETIC mark is not needed on them (QA only).
"""
import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument("--job", action="append", default=[])
ap.add_argument("--frames", default="1")
ap.add_argument("--out", required=True)
ap.add_argument("--res", default="1280x720")
ap.add_argument("--samples", type=int, default=8)
ap.add_argument("--visible", action="append", default=[])
ap.add_argument("--range", default="")  # a-b: every frame of a range (for clips)
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
sc = bpy.context.scene
OUT = Path(args.out).resolve()
OUT.mkdir(parents=True, exist_ok=True)
rx, ry = (int(v) for v in args.res.split("x"))
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, 100
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_depth = "8"
sc.eevee.taa_render_samples = args.samples
for o in sc.objects:  # every worker visible (dress may have culled people per camera)
    if o.name.startswith("worker_") or (o.parent and o.parent.name.startswith("worker_")):
        if not o.name.endswith(("__look",)):
            o.hide_render = False


def vec(s):
    return Vector(tuple(float(v) for v in s.split(",")))


if args.visible:
    dg = bpy.context.evaluated_depsgraph_get()
    sc.frame_set(1)
    for spt in args.visible:
        p = vec(spt)
        seen = []
        for cam in sorted([o for o in sc.objects if o.type == "CAMERA" and o.name.startswith("CAM_")],
                          key=lambda o: o.name):
            loc = cam.matrix_world.translation
            pc = cam.matrix_world.inverted() @ p
            if pc.z >= -0.1:
                continue
            tx = math.tan(cam.data.angle_x / 2)
            ty = tx * sc.render.resolution_y / sc.render.resolution_x
            if abs(pc.x / -pc.z) > tx or abs(pc.y / -pc.z) > ty:
                continue
            d = p - loc
            hit, hl, *_ = sc.ray_cast(dg, loc, d.normalized(), distance=d.length - 0.3)
            seen.append((cam.name, "blocked" if hit else "VISIBLE", round(d.length, 1)))
        print("VIS", spt, seen, flush=True)

frames = [int(f) for f in args.frames.split(",") if f]
if args.range:
    a, b = (int(v) for v in args.range.split("-"))
    frames = list(range(a, b + 1))
for job in args.job:
    name, cpos, tpos, lens = job.split(":")
    cd = bpy.data.cameras.new(f"review_{name}")
    cd.lens = float(lens)
    cd.clip_start = 0.05
    cam = bpy.data.objects.new(f"review_{name}", cd)
    sc.collection.objects.link(cam)
    cam.location = vec(cpos)
    d = vec(tpos) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    for f in frames:
        sc.frame_set(f)
        sc.render.filepath = str(OUT / f"{name}_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
    print("CROPS", name, len(frames), flush=True)
