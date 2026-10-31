"""QA close proof for S2's removal actor (review 021b): numbers + close crops on a saved S2 blend (bench or full hub).

  blender -b <s2 blend> -P assets/hub/mocap/s2_close_proof.py -- <out dir> [--reach 50 75] [--place 300 345]
          [--after 400] [--carry 90 120 160 200 388]

1. Reach into the cage: per frame the head's minimum distance to the cage's meshes (head = body vertices weighted
   > 0.5 to the head / neck bones; cage = cage_s2_S11 and its parts, shelf included), plus side crops.
2. Place on the store shelf: per frame the gap between the carton's bottom and the surface under it (rays down from
   4 inset corners + the centre, the carton and its label skipped; negative = sunk in), plus 3/4 crops.
3. Carry hands: close crops on the hands. Every follow camera checks its line of sight to the target first and turns
   round the subject until nothing but the worker / carton / cage is in the way (review 021b #4).
Workbench renders (shape proof, not the CCTV look).
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--worker", default="worker_s2_1")
ap.add_argument("--reach", type=int, nargs=2, default=(50, 75))
ap.add_argument("--place", type=int, nargs=2, default=(300, 345))
ap.add_argument("--after", type=int, nargs="*", default=[400])
ap.add_argument("--rest", type=int, nargs="*", default=[20, 40, 55])  # on the cage shelf before the grasp
ap.add_argument("--carry", type=int, nargs="*", default=[90, 120, 160, 200, 388])
ap.add_argument("--shelf", type=float, nargs=2, default=(10.5, 33.87))
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
OUT = Path(a.out).resolve()
OUT.mkdir(parents=True, exist_ok=True)
sc = bpy.context.scene
arm = sc.objects[a.worker]
body = next(o for o in sc.objects if o.type == "MESH" and o.parent == arm and o.vertex_groups.get("Bip01 Head"))
gi = {body.vertex_groups[n].index for n in ("Bip01 Head", "Bip01 Neck") if body.vertex_groups.get(n)}
head_ix = np.array([v.index for v in body.data.vertices if sum(g.weight for g in v.groups if g.group in gi) > 0.5])
gs = {body.vertex_groups[n].index for n in ("Bip01 L Clavicle", "Bip01 R Clavicle", "Bip01 L UpperArm",
                                              "Bip01 R UpperArm") if body.vertex_groups.get(n)}
sh_ix = np.array([v.index for v in body.data.vertices if sum(g.weight for g in v.groups if g.group in gs) > 0.5])
cage_root = sc.objects["cage_s2_S11"]


def _parents(o):
    while o.parent is not None:
        o = o.parent
        yield o


cage_parts = [o for o in sc.objects if o.type == "MESH" and (o.name.startswith("cage_s2_S11") or cage_root in
                                                              list(_parents(o)))]


def world_co(ob, dg):
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    M = np.array(ev.matrix_world)
    me.calc_loop_triangles()
    tri = np.empty(len(me.loop_triangles) * 3, dtype=np.int32)
    me.loop_triangles.foreach_get("vertices", tri)
    ev.to_mesh_clear()
    return co @ M[:3, :3].T + M[:3, 3], tri.reshape(-1, 3)


def bone_w(name):
    return arm.matrix_world @ arm.pose.bones[name].head


# the carton: the flow parcel / bench box nearest the store shelf at the last place frame
sc.frame_set(a.after[0] if a.after else a.place[1])
cands = [o for o in sc.objects if o.type == "MESH" and o.name.startswith("flow_parcel_") and not o.name.endswith("_label")]
carton = min(cands, key=lambda o: (Vector(o.matrix_world.translation.xy) - Vector(a.shelf)).length)
label = sc.objects.get(carton.name + "_label")
skip = {carton.name} | ({label.name} if label else set())
res = dict(carton=carton.name, cage_meshes=[o.name for o in cage_parts])

# ---------------------------------------------------------------- 1. head to cage
rows = []
for f in range(a.reach[0], a.reach[1] + 1):
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    bv, _ = world_co(body, dg)
    hv, sv = bv[head_ix], bv[sh_ix]
    best, best_s = (9.0, None), (9.0, None)
    for o in cage_parts:
        co, tri = world_co(o, dg)
        if not len(tri):
            continue
        t_ = BVHTree.FromPolygons([tuple(c) for c in co], [tuple(t) for t in tri])
        for v in hv:
            hit = t_.find_nearest(Vector(v), 0.5)
            if hit[0] is not None and hit[3] < best[0]:
                best = (hit[3], o.name)
        for v in sv[::2]:
            hit = t_.find_nearest(Vector(v), 0.3)
            if hit[0] is not None and hit[3] < best_s[0]:
                best_s = (hit[3], o.name)
    pv = bone_w("Bip01 Pelvis")
    sp = bone_w("Bip01 Neck")
    tilt = math.degrees(math.atan2((Vector(sp.xy) - Vector(pv.xy)).length, sp.z - pv.z))
    rows.append(dict(frame=f, head_cage_min_cm=round(best[0] * 100, 1), nearest=best[1], trunk_tilt_deg=round(tilt, 1),
                     shoulders_cage_min_cm=round(best_s[0] * 100, 1), shoulders_nearest=best_s[1]))
res["head_cage"] = rows
res["head_cage_min_cm"] = min(r["head_cage_min_cm"] for r in rows)
res["trunk_tilt_deg_max_reach"] = max(r["trunk_tilt_deg"] for r in rows)
res["shoulders_cage_min_cm"] = min(r["shoulders_cage_min_cm"] for r in rows)

# ---------------------------------------------------------------- 2. carton on the store shelf
gaps = []
for f in list(a.rest) + list(range(a.place[0], a.place[1] + 1)) + list(a.after):
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    co, _ = world_co(carton, dg)
    zb = float(co[:, 2].min())
    lo, hi = co.min(0), co.max(0)
    c = (lo + hi) / 2
    ins = 0.02
    pts = [(c[0], c[1])] + [(c[0] + sx * ((hi[0] - lo[0]) / 2 - ins), c[1] + sy * ((hi[1] - lo[1]) / 2 - ins))
                            for sx in (-1, 1) for sy in (-1, 1)]
    zs = []
    hid = [o for o in (carton, label) if o is not None]  # out of the way of the rays (a board flush with its bottom
    for o in hid:                                         # face was stepped past when skipping the carton's own hit)
        o.hide_viewport = True
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    for x, y in pts:
        ok, loc, nrm, idx, ob, M = sc.ray_cast(dg, Vector((x, y, zb + 0.03)), Vector((0, 0, -1)), distance=0.5)
        zs.append(loc.z if ok else None)
    for o in hid:
        o.hide_viewport = False
    zz = [z for z in zs if z is not None]
    gaps.append(dict(frame=f, bottom_z=round(zb, 4), surface_z=(round(max(zz), 4) if zz else None),
                     gap_mm=(round((zb - max(zz)) * 1000, 1) if zz else None),
                     corners_on_support=sum(1 for z in zs if z is not None and abs(zb - z) < 0.01)))
res["place"] = gaps

# ---------------------------------------------------------------- renders
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.light = "STUDIO"
sc.display.shading.color_type = "TEXTURE"
sc.display.shading.show_shadows = True
sc.display.shading.show_cavity = True
sc.render.image_settings.file_format = "JPEG"
sc.render.image_settings.quality = 88
sc.render.resolution_x, sc.render.resolution_y = 800, 800
cd = bpy.data.cameras.new("proof_cam")
cam = bpy.data.objects.new("proof_cam", cd)
sc.collection.objects.link(cam)
OK_HIT = {body.name, arm.name} | skip | {o.name for o in cage_parts} | {"cage_s2_S11"}


def clear_view(dg, eye, tgt):
    """True if nothing but the worker / carton / cage lies between eye and tgt (and within 0.25 m of tgt)."""
    d = tgt - eye
    dist = d.length
    org = eye.copy()
    for _ in range(10):
        ok, loc, nrm, idx, ob, M = sc.ray_cast(dg, org, d.normalized(), distance=dist - (org - eye).length)
        if not ok:
            return True
        nm = ob.name
        if nm in OK_HIT or (ob.parent is not None and ob.parent.name in OK_HIT) or (tgt - loc).length < 0.25 \
                or nm.startswith(("Male_", "Female_", "worker_s2")):
            org = loc + d.normalized() * 1e-3
            continue
        return False
    return True


def shoot(f, name, tgt, fwd, az_list, dist, dz, lens=40):
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    lat = Vector((fwd.y, -fwd.x, 0))
    used = None
    for az in az_list:
        r = math.radians(az)
        dirv = fwd * math.cos(r) + lat * math.sin(r)
        eye = tgt + dirv * dist + Vector((0, 0, dz))
        if clear_view(dg, eye, tgt):
            used = az
            break
    if used is None:
        return None
    cd.lens = lens
    cam.location = eye
    cam.rotation_euler = (tgt - eye).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    sc.render.filepath = str(OUT / f"{name}_f{f:03d}.jpg")
    bpy.ops.render.render(write_still=True)
    return used


def body_fwd():
    L, Rr = bone_w("Bip01 L UpperArm"), bone_w("Bip01 R UpperArm")
    lat = L - Rr
    lat.z = 0
    lat.normalize()
    return Vector((lat.y, -lat.x, 0))  # (L - R) rotated -90 deg: the way he faces


AZ = [35, -35, 60, -60, 0, 90, -90, 120, -120]
shots = {}
for f in range(a.reach[0] + 6, a.reach[1] - 4, 2):  # side crops of the reach (head over the cage)
    sc.frame_set(f)
    shots[f"reach_side_f{f:03d}"] = shoot(f, "reach_side", bone_w("Bip01 Head") - Vector((0, 0, 0.2)), body_fwd(),
                                          [90, -90, 70, -70, 110, -110], 2.0, 0.1, lens=35)
sc.frame_set((a.place[0] + a.place[1]) // 2)  # (he still faces the shelf: after the release he stands, then turns)
PLACE_FWD = -body_fwd()  # from the carton back towards him: azimuths +-75..90 put the camera beside him
for f in list(range(a.place[0] + 6, a.place[1] - 4, 4)) + list(a.after):  # the carton landing on the shelf
    sc.frame_set(f)
    t_ = carton.matrix_world.translation.copy()
    # beside him, along the shelf's face (he faces the shelf: from behind his body hides the carton)
    shots[f"place_34_f{f:03d}"] = shoot(f, "place_34", t_, PLACE_FWD, [75, -75, 90, -90, 60, -60],
                                        1.3, 0.3, lens=35)
for f in a.carry:  # carry hands close
    sc.frame_set(f)
    hm = (bone_w("Bip01 L Hand") + bone_w("Bip01 R Hand")) / 2
    shots[f"hands_f{f:03d}"] = shoot(f, "hands", hm, body_fwd(), AZ, 1.1, 0.25, lens=45)
    shots[f"follow_f{f:03d}"] = shoot(f, "follow", bone_w("Bip01 Spine2"), body_fwd(), AZ, 2.6, 0.5, lens=35)
res["shots_azimuth_deg"] = shots
(OUT / "close_proof.json").write_text(json.dumps(res, indent=1))
print("CLOSEPROOF", json.dumps(dict(head_cage_min_cm=res["head_cage_min_cm"],
                                    shoulders_cage_min_cm=res["shoulders_cage_min_cm"],
                                    trunk_tilt_deg_max_reach=res["trunk_tilt_deg_max_reach"],
                                    place=[(g["frame"], g["gap_mm"]) for g in gaps[::5]],
                                    blocked=[k for k, v in shots.items() if v is None])), flush=True)
