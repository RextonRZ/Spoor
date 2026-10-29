"""Inspect the CC BY 'Construction Worker in Safety Vest' (.glb) and export an FBX for Mixamo's auto-rigger.

  blender -b --factory-startup -P assets/hub/prep_vest_worker.py

Mixamo rigs a single unrigged mesh in a T/A-pose most reliably, so if the glb carries its own armature, the mesh is
exported in its rest pose without that armature. Textures are embedded in the FBX.
"""

import json
import math
from pathlib import Path

import bpy

WORKERS = Path(bpy.path.abspath("//")) if bpy.data.filepath else Path(__file__).parent / "build" / "third_party" / "workers"
SRC = WORKERS / "construction_worker_in_safety_vest.glb"
OUT = WORKERS / "vest_worker_for_mixamo.fbx"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(SRC))
objs = list(bpy.context.scene.objects)
meshes = [o for o in objs if o.type == "MESH"]
arms = [o for o in objs if o.type == "ARMATURE"]
report = {"objects": [(o.name, o.type) for o in objs], "meshes": len(meshes),
          "triangles": sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in meshes),
          "armatures": [{"name": a.name, "bones": len(a.data.bones), "sample_bones": [b.name for b in a.data.bones][:12]}
                        for a in arms],
          "animations": [a.name for a in bpy.data.actions],
          "materials": sorted({m.name for o in meshes for m in o.data.materials if m}),
          "images": [(i.name, i.size[:]) for i in bpy.data.images]}
dg = bpy.context.evaluated_depsgraph_get()
zs, xs = [], []
for o in meshes:
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    for v in me.vertices:
        w = ev.matrix_world @ v.co
        zs.append(w.z)
        xs.append(w.x)
    ev.to_mesh_clear()
report["height_m"] = round(max(zs) - min(zs), 3)
report["arm_span_m"] = round(max(xs) - min(xs), 3)
report["pose_guess"] = ("T-pose" if report["arm_span_m"] > 0.9 * report["height_m"] else
                        "A-pose" if report["arm_span_m"] > 0.6 * report["height_m"] else "arms down / other")
for a in arms:  # show the rest pose, not an animated frame
    a.data.pose_position = "REST"
for o in meshes:  # bake the rest-pose mesh, drop the armature so Mixamo's auto-rigger starts clean
    for m in list(o.modifiers):
        if m.type == "ARMATURE":
            bpy.context.view_layer.objects.active = o
            bpy.ops.object.modifier_apply(modifier=m.name)
    o.parent = None
for a in arms:
    bpy.data.objects.remove(a, do_unlink=True)
for o in list(bpy.context.scene.objects):
    if o.type not in ("MESH",):
        bpy.data.objects.remove(o, do_unlink=True)
for o in bpy.context.scene.objects:
    o.select_set(True)
bpy.ops.export_scene.fbx(filepath=str(OUT), use_selection=True, path_mode="COPY", embed_textures=True,
                         apply_scale_options="FBX_SCALE_ALL", add_leaf_bones=False, bake_anim=False)
report["exported"] = str(OUT)
report["exported_mb"] = round(OUT.stat().st_size / 1e6, 1)
print("REPORT " + json.dumps(report), flush=True)
