"""Put the checkpoint cameras (hub_spec kind "checkpoint", checkpoint_cams.py) into an open blend: camera objects posed
as build_hub poses the wide ones, and their housings + brackets, so other cameras see them mounted. The blend's own
cameras are not touched. Chain it before a render script, or save:

  blender -b <blend> -P assets/hub/add_checkpoint_cams.py -P assets/hub/render_cctv.py -- --cams CHK_STORE ...
  blender -b <blend> -P assets/hub/add_checkpoint_cams.py -- --save <out.blend>
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy

HUB = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--spec", default="hub_spec_lineAb.json")
ap.add_argument("--save", default="")
args, _ = ap.parse_known_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
spec = json.loads((HUB / args.spec).read_text(encoding="utf-8"))
coll = bpy.data.collections.get("CCTV") or bpy.context.scene.collection

added = []
bm = bmesh.new()
for cs in (c for c in spec["cameras"] if c.get("kind") == "checkpoint"):
    if cs["id"] in bpy.data.objects:
        continue
    x, y = cs["position_m"]
    hgt, yaw, tilt = cs["height_m"], cs["heading_deg"], cs["tilt_down_deg"]
    cd = bpy.data.cameras.new(cs["id"])
    cd.sensor_fit = "HORIZONTAL"
    cd.angle_x = math.radians(cs["hfov_deg"])
    cd.clip_start, cd.clip_end = 0.05, 150.0
    co = bpy.data.objects.new(cs["id"], cd)
    co.location = (x, y, hgt)
    co.rotation_euler = (math.radians(90 - tilt), 0, math.radians(yaw - 90))
    co["question"], co["detail_target"] = cs["question"], cs["detail_target"]
    coll.objects.link(co)
    # the housing just behind the lens (out of its own view) and a bracket up to the truss or back to the wall
    fx, fy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    hx, hy = x - 0.14 * fx, y - 0.14 * fy
    top = hgt + (2.0 if "drop-pole" in cs["mount"] else 0.4)
    for (x0, y0, z0, x1, y1, z1) in ((hx - 0.09, hy - 0.09, hgt - 0.05, hx + 0.09, hy + 0.09, hgt + 0.08),
                                     (hx - 0.03, hy - 0.03, hgt + 0.08, hx + 0.03, hy + 0.03, top)):
        r = bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=(x1 - x0, y1 - y0, z1 - z0), verts=r["verts"])
        bmesh.ops.translate(bm, vec=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), verts=r["verts"])
    added.append(cs["id"])
if added:
    me = bpy.data.meshes.new("cctv_checkpoint_housings")
    bm.to_mesh(me)
    ob = bpy.data.objects.new("cctv_checkpoint_housings", me)
    old = bpy.data.objects.get("cctv_housings")
    if old is not None and old.data.materials:
        me.materials.append(old.data.materials[0])
    coll.objects.link(ob)
bm.free()
print("CHK_CAMS added", added)
if args.save:
    bpy.ops.wm.save_as_mainfile(filepath=args.save)
