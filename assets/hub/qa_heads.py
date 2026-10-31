"""Headwear close-ups for review (009d/009e: is every cap / hard hat seated?): for each worker wearing one, workbench
renders 0.7 m from the head at 3/4 front and side views, at a few frames.

  blender -b --factory-startup <scenario.blend> -P assets/hub/qa_heads.py -- --out <dir> [--frames 1,150,290]
"""
import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--frames", default="1,150,290")
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
OUT = Path(a.out)
OUT.mkdir(parents=True, exist_ok=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.render.image_settings.file_format = "PNG"  # (the scene may be set to a video format: stills failed silently)
sc.display.shading.light = "STUDIO"
sc.display.shading.color_type = "MATERIAL"
sc.render.resolution_x = sc.render.resolution_y = 420
cam = bpy.data.objects.new("qa_head_cam", bpy.data.cameras.new("qa_head_cam"))
cam.data.lens = 50
cam.data.clip_start = 0.05
sc.collection.objects.link(cam)
sc.camera = cam
rigs = [o for o in sc.objects if o.type == "ARMATURE" and o.name.startswith("worker_")
        and any(c.name.endswith(("_cap", "_hard")) for c in o.children_recursive)]
for f in [int(x) for x in a.frames.split(",")]:
    sc.frame_set(f)
    for rig in rigs:
        pb = rig.pose.bones["Bip01 Head"]
        mw = rig.matrix_world
        head = mw @ pb.head
        lft = (mw @ rig.pose.bones["Bip01 L Clavicle"].head) - (mw @ rig.pose.bones["Bip01 R Clavicle"].head)
        face = math.atan2(lft.y, lft.x) - math.pi / 2
        c = head + Vector((0, 0, 0.1))
        own = {rig.name} | {o.name for o in rig.children_recursive}
        dg = bpy.context.evaluated_depsgraph_get()

        def clear(d):  # line of sight from just outside the head to the lens: nothing but this worker in between
            o_ = c + d * 0.15
            hit, _l, _n, _i, ob_, _m = sc.ray_cast(dg, o_, d, distance=0.6)
            return not hit or ob_.name in own
        for tag, angs in (("front", (0.45, 0.2, 0.75, -0.3, 1.0, -0.6)), ("side", (1.57, 1.3, 1.85, -1.57, -1.3))):
            for ang in angs:  # (a fixed angle put the lens inside the carton wall / behind the mate: review 013)
                d = Vector((math.cos(face + ang), math.sin(face + ang), 0.12)).normalized()
                if clear(d):
                    break
            cam.location = c + d * 0.7
            cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
            sc.render.filepath = str(OUT / f"{rig.name}_f{f:03d}_{tag}.png")
            bpy.ops.render.render(write_still=True)
    print("HEADS frame", f, len(rigs), "workers", flush=True)
