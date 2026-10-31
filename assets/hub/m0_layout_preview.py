"""M0 (014_GO): line-A induction re-laid so nobody spins with a parcel. Preview only (layout judgement): the
current dressed hub with the old feed run cut out, the new feed belt, one gravity-roller buffer table per inductor
at his front-left, and stand-in figures (1.7 m, vest-yellow) on the inductor spots; top + front EEVEE stills.

  blender -b --factory-startup build/hub_dressed_lit.blend -P assets/hub/m0_layout_preview.py -- --out <dir>

Layout (proposed, to be wired into build_hub / flow / stations at M3):
  induction belt   y 9.5 (unchanged), flat x 5.6-15, frames to y 9.95
  feed belt        moved north: y 11.35, x 5.0-13.0 (frames from y 10.90) -> aisle between frames 0.95 m
  inductors        x 7.0 / 8.6 / 10.2 / 11.8 (1.6 m apart: 1 per induct point), y 10.25, FACING the induction belt
  buffer tables    one per inductor, from the feed belt to his front-left: x = his x + 0.55, y 10.95 -> 10.15,
                   0.5 m wide, rollers falling 0.95 -> 0.88 m toward him (75-110 cm handling zone)
  per parcel       glance left -> reach (~80 deg trunk turn) -> slide / short two-hand lift -> label up -> turn back ->
                   push forward into the gap; feet planted (one small step at most)
"""
import argparse
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
OUT = Path(a.out)
OUT.mkdir(parents=True, exist_ok=True)
sc = bpy.context.scene
HERE = Path(bpy.path.abspath("//")).resolve().parent
sys.path.insert(0, str(HERE))
import stations  # noqa: E402

INDUCT_X = [7.0, 8.6, 10.2, 11.8]
OP_Y, FEED_Y, FEED_X1 = 10.25, 11.35, 13.0
TABLE_DX, TABLE_Y0, TABLE_Y1, TABLE_W = 0.55, 10.95, 10.15, 0.5

# 1. the old feed run (y 10.85, x 5-9.2) and its parcels out of the preview
cut = stations._cut_region(sc, ["conveyors"], 5.3, 9.4, 10.4, 11.3, 0.3, 1.3)
for o in list(sc.objects):
    if o.name.startswith(("flow_parcel_", "worker_")):
        bpy.data.objects.remove(o, do_unlink=True)
mat = {n: bpy.data.materials.get(n) for n in ("steel", "belt", "rubber", "yellow", "cardboard")}


def material(name, rgb):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1)
    return m


steel = mat["steel"] or material("m0_steel", (0.55, 0.57, 0.6))
beltm = mat["belt"] or mat["rubber"] or material("m0_belt", (0.05, 0.05, 0.05))
vest = material("m0_vest", (0.85, 0.85, 0.05))
skin = material("m0_skin", (0.45, 0.32, 0.25))
roller = material("m0_roller", (0.75, 0.75, 0.78))
mark = material("m0_mark", (0.95, 0.75, 0.0))


def box(name, x0, y0, z0, x1, y1, z1, m, rot=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    M = Matrix.Translation(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)) @ Matrix.Diagonal((x1 - x0, y1 - y0, z1 - z0, 1))
    bmesh.ops.create_cube(bm, size=1.0, matrix=M)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    return ob


# 2. the new feed belt (frames, belt, legs)
box("m0_feed_belt", 5.0, FEED_Y - 0.4, 0.94, FEED_X1, FEED_Y + 0.4, 1.0, beltm)
for s in (-1, 1):
    box(f"m0_feed_frame_{s}", 5.0, FEED_Y + s * 0.43 - 0.02, 0.86, FEED_X1, FEED_Y + s * 0.43 + 0.02, 1.04, steel)
for x in [5.2 + 1.9 * k for k in range(5)]:
    for s in (-1, 1):
        box(f"m0_feed_leg_{x:.1f}_{s}", x - 0.03, FEED_Y + s * 0.36 - 0.03, 0, x + 0.03, FEED_Y + s * 0.36 + 0.03, 0.86, steel)
box("m0_feed_endplate", FEED_X1, FEED_Y - 0.45, 0.92, FEED_X1 + 0.04, FEED_Y + 0.45, 1.14, steel)
# 3. buffer tables: gravity rollers from the feed belt down to each inductor's front-left
for k, x in enumerate(INDUCT_X):
    tx = x + TABLE_DX
    n = 9
    for i in range(n):
        u = i / (n - 1)
        y = TABLE_Y0 + (TABLE_Y1 - TABLE_Y0) * u
        z = 0.95 + (0.88 - 0.95) * u
        box(f"m0_t{k}_roller_{i}", tx - TABLE_W / 2, y - 0.025, z - 0.05, tx + TABLE_W / 2, y + 0.025, z, roller)
    for s in (-1, 1):
        box(f"m0_t{k}_side_{s}", tx + s * TABLE_W / 2 - 0.02, TABLE_Y1 - 0.03, 0.8, tx + s * TABLE_W / 2 + 0.02, TABLE_Y0,
            0.97, steel)
    box(f"m0_t{k}_stop", tx - TABLE_W / 2, TABLE_Y1 - 0.06, 0.85, tx + TABLE_W / 2, TABLE_Y1 - 0.03, 0.95, steel)
    for (lx, ly) in ((tx - 0.2, TABLE_Y1 + 0.05), (tx + 0.2, TABLE_Y1 + 0.05), (tx - 0.2, TABLE_Y0 - 0.1),
                     (tx + 0.2, TABLE_Y0 - 0.1)):
        box(f"m0_t{k}_leg_{lx:.2f}_{ly:.2f}", lx - 0.02, ly - 0.02, 0, lx + 0.02, ly + 0.02, 0.85, steel)
    # two parcels waiting on it, one on the feed belt behind
    box(f"m0_t{k}_parcel_a", tx - 0.15, TABLE_Y1 + 0.02, 0.88, tx + 0.15, TABLE_Y1 + 0.24, 1.03, mat["cardboard"] or vest)
    box(f"m0_t{k}_parcel_b", tx - 0.12, TABLE_Y1 + 0.3, 0.9, tx + 0.13, TABLE_Y1 + 0.48, 1.02, mat["cardboard"] or vest)
    # 4. the inductor: stand-in figure facing the induction belt (south), feet marks
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.17, radius2=0.2, depth=0.7,
                          matrix=Matrix.Translation((x, OP_Y, 1.1)))  # torso
    for lx in (-0.09, 0.09):
        bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.07, radius2=0.08, depth=0.75,
                              matrix=Matrix.Translation((x + lx, OP_Y, 0.375)))  # legs
    me = bpy.data.meshes.new(f"m0_inductor_{k + 1}")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(vest)
    ob = bpy.data.objects.new(f"m0_inductor_{k + 1}", me)
    sc.collection.objects.link(ob)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=0.11, matrix=Matrix.Translation((x, OP_Y, 1.6)))
    bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.04, radius2=0.0, depth=0.12,
                          matrix=Matrix.Translation((x, OP_Y - 0.14, 1.6)) @ Matrix.Rotation(math.pi / 2, 4, "X"))  # nose: facing
    me = bpy.data.meshes.new(f"m0_head_{k + 1}")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(skin)
    sc.collection.objects.link(bpy.data.objects.new(f"m0_head_{k + 1}", me))
    for fx in (-0.1, 0.1):
        box(f"m0_foot_{k}_{fx}", x + fx - 0.05, OP_Y - 0.17, 0.001, x + fx + 0.05, OP_Y + 0.08, 0.004, mark)
    # 5. text label on the floor
    cu = bpy.data.curves.new(f"m0_lbl_{k}", "FONT")
    cu.body = f"I{k + 1}"
    cu.size = 0.25
    tl = bpy.data.objects.new(f"m0_lbl_{k}", cu)
    tl.location = (x - 0.12, OP_Y + 0.25, 0.006)
    cu.materials.append(mark)
    sc.collection.objects.link(tl)

# 6. cameras: top (orthographic) and front (perspective, from the induction side)
sc.render.engine = "BLENDER_EEVEE_NEXT" if sc.render.engine == "BLENDER_WORKBENCH" else sc.render.engine
sc.render.image_settings.file_format = "PNG"
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
if hasattr(sc.eevee, "taa_render_samples"):
    sc.eevee.taa_render_samples = 16
for tag, loc, tgt, ortho in (("top", (9.4, 10.5, 9.0), (9.4, 10.5, 0.0), 9.5),
                             ("front", (9.0, 6.6, 3.0), (9.6, 10.6, 0.9), None),
                             ("operator_view", (13.6, 9.9, 1.8), (9.0, 10.6, 0.9), None)):
    cd = bpy.data.cameras.new(f"m0_{tag}")
    cam = bpy.data.objects.new(f"m0_{tag}", cd)
    sc.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    if ortho:
        cd.type, cd.ortho_scale = "ORTHO", ortho
    else:
        cd.lens = 24
    cd.clip_start = 0.05
    sc.camera = cam
    sc.render.filepath = str(OUT / f"m0_{tag}.png")
    bpy.ops.render.render(write_still=True)
    print("M0 wrote", tag, flush=True)
print("M0 cut", cut, flush=True)
