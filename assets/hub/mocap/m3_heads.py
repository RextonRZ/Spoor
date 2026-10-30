"""Bare-head sheet (014b): the mocap worker's head front + side at the given frames, from the saved M3 scene.

  blender -b qa/review/m3_hub/m3_test.blend -P assets/hub/mocap/m3_heads.py -- <out_dir> 1,150,300
"""
import math
import sys

import bpy
from mathutils import Vector

out, frs = sys.argv[sys.argv.index("--") + 1:][:2]
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 360, 360, 100
sc.render.image_settings.file_format = "PNG"
arm = next(o for o in sc.objects if o.type == "ARMATURE" and o.animation_data and o.animation_data.action
           and o.animation_data.action.name.startswith("inductor"))
cd = bpy.data.cameras.new("head_cam")
cd.lens = 70
cd.clip_start = 0.05
cam = bpy.data.objects.new("head_cam", cd)
sc.collection.objects.link(cam)
sc.camera = cam
for f in [int(x) for x in frs.split(",")]:
    sc.frame_set(f)
    pb = arm.pose.bones
    h = arm.matrix_world @ pb["Bip01 Head"].head + Vector((0, 0, 0.08))
    lv = (arm.matrix_world @ pb["Bip01 L Thigh"].head) - (arm.matrix_world @ pb["Bip01 R Thigh"].head)
    lv.z = 0
    lv.normalize()
    fwd = Vector((lv.y, -lv.x, 0))  # facing: the hip line turned -90 deg
    for tag, d in (("front", fwd), ("side", lv)):
        cam.location = h + d * 1.1 + Vector((0, 0, 0.05))
        cam.rotation_euler = (h - cam.location).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = f"{out}/head_{f:03d}_{tag}.png"
        bpy.ops.render.render(write_still=True)
print("heads done", flush=True)
