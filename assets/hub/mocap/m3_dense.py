"""014d #2: dense hand crops around a grasp and a release (every frame = 0.1 s, 1.5 s windows), two views per frame
(from the left hand's side and from the right hand's side, aimed at the carton), from the saved M3 scene.

  blender -b qa/review/m3_hub/m3_test.blend -P assets/hub/mocap/m3_dense.py -- <out_dir> <grasp> <release> <n>
"""
import sys

import bpy
from mathutils import Vector

out, g, r, n = sys.argv[sys.argv.index("--") + 1:][:4]
g, r = int(g), int(r)
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
if hasattr(sc.eevee, "taa_render_samples"):
    sc.eevee.taa_render_samples = 8
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 360, 360, 100
sc.render.image_settings.file_format = "PNG"
arm = next(o for o in sc.objects if o.type == "ARMATURE" and o.animation_data and o.animation_data.action
           and o.animation_data.action.name.startswith("inductor"))
pc = sc.objects[f"parcel_{n}"]
cams = {}
for tag in ("L", "R"):
    cd = bpy.data.cameras.new(f"dense_{tag}")
    cd.lens = 45
    cd.clip_start = 0.05
    cams[tag] = bpy.data.objects.new(f"dense_{tag}", cd)
    sc.collection.objects.link(cams[tag])
frames = [("grasp", f) for f in range(g - 7, g + 8)] + [("release", f) for f in range(r - 7, r + 8)]
for kind, f in frames:
    sc.frame_set(f)
    c = pc.matrix_world.translation.copy()
    hl = arm.matrix_world @ arm.pose.bones["Bip01 L Hand"].head
    hr = arm.matrix_world @ arm.pose.bones["Bip01 R Hand"].head
    mid = (hl + hr) / 2
    for tag, h in (("L", hl), ("R", hr)):
        d = (h - mid)
        d.z = 0
        d = d.normalized() if d.length > 1e-4 else Vector((1, 0, 0))
        cam = cams[tag]
        cam.location = mid + d * 0.75 + Vector((0, 0, 0.35))
        cam.rotation_euler = (mid - cam.location).to_track_quat("-Z", "Y").to_euler()
        sc.camera = cam
        sc.render.filepath = f"{out}/d_{kind}_{f:04d}_{tag}.png"
        bpy.ops.render.render(write_still=True)
print("dense done", flush=True)
