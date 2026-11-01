"""Bench for window W2's actor (six checkpoints, stations.w2_legs): in the real hub (layout b build), the S11 roll cage
with its mid shelf (as S2), the story carton on top of C12's bag, Female_Adult_17 walking up, taking it out of the bag,
carrying it round the bay rows and setting it on S11's mid shelf at S2's frame-1 pose, then walking off. Saves a
blend for collision_check.py, writes the motion report (release time: the cage scan) and stills from CHK_CAGE_W and
CAM_13 / CHK_CHUTE.

  blender -b --factory-startup -P assets/hub/mocap/w2_bench.py -- --out qa/review/w2_actor [--stills]
"""
import argparse
import json
import random
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
HUB = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HUB))
import inductor as I  # noqa: E402
import people  # noqa: E402
import remover as RM  # noqa: E402
import retarget as R  # noqa: E402
import stations  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--save", default=str(HUB / "build" / "qa" / "w2_bench.blend"))
ap.add_argument("--seconds", type=float, default=40.0)
ap.add_argument("--fps", type=float, default=10.0)
ap.add_argument("--stills", action="store_true")
ap.add_argument("--rb", default=str(HUB / "build" / "third_party" / "rocketbox"))
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
OUT = Path(a.out).resolve()
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(HUB / "build" / "hub_lineAb_dressed_lit.blend"))
sc = bpy.context.scene
for o in list(sc.objects):
    if o.name.startswith(("flow_parcel_", "worker_")):
        bpy.data.objects.remove(o, do_unlink=True)
SPEC = json.loads((HUB / "hub_spec_lineAb.json").read_text(encoding="utf-8"))
F = int(round(a.seconds * a.fps))
coll = bpy.data.collections.get("People") or bpy.data.collections.new("People")
if coll.name not in sc.collection.children:
    sc.collection.children.link(coll)

# ---------------------------------------------------------------- the S11 cage with its mid shelf (as S2)
rnd = random.Random(2002)
stations._clear_bay(sc, SPEC, stations.S2_CAGE_BAY)
cage, _ = stations._cage_parts("cage_s2_S11", coll, rnd, loaded=True)
cage.location = stations.S2_CAGE
shm = bpy.data.meshes.new("cage_s2_shelf")
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bmesh.ops.scale(bm, vec=(0.68, 0.76, 0.02), verts=bm.verts)
bmesh.ops.translate(bm, vec=(0, 0, stations.S2_SHELF_Z - 0.01), verts=bm.verts)
bm.to_mesh(shm)
bm.free()
shm.materials.append(cage.material_slots[0].material if cage.material_slots else None)
shelf = bpy.data.objects.new("cage_s2_S11_shelf", shm)
coll.objects.link(shelf)
shelf.parent = cage
bpy.context.view_layer.update()

# ---------------------------------------------------------------- the carton on top of C12's bag (measured by ray)
DIMS = stations.S2_PARCEL_DIMS
dg = bpy.context.evaluated_depsgraph_get()
bx, by_ = stations.W2_BAG
hit, loc_, nrm_, _i, ob_hit, _m = sc.ray_cast(dg, Vector((bx, by_, 2.5)), Vector((0, 0, -1)), distance=3.0)
top = loc_.z if hit else 0.85
print("W2 bag top", round(top, 3), ob_hit.name if hit else None, flush=True)
PICK_C = (bx, by_, top + DIMS[2] / 2 + 0.02)  # on the bag's soft top, a little proud (fingers 2 cm into it: check)
PLACE_C = stations.w2_place_c()
bxm = bpy.data.meshes.new("w2_box")
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bmesh.ops.scale(bm, vec=DIMS, verts=bm.verts)
bm.to_mesh(bxm)
bm.free()
mat = bpy.data.materials.new("w2_box_card")
mat.use_nodes = True
mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.42, 0.28, 1)
bxm.materials.append(mat)
box = bpy.data.objects.new("flow_parcel_w2_story", bxm)
coll.objects.link(box)
lbm_ = bpy.data.meshes.new("w2_box_label")
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5,
                      matrix=Matrix.Translation((0.02, 0.0, DIMS[2] / 2 + 0.001)) @ Matrix.Diagonal((0.10, 0.15, 1, 1)))
bm.to_mesh(lbm_)
bm.free()
lmat_ = bpy.data.materials.new("w2_box_label")
lmat_.diffuse_color = (0.93, 0.93, 0.9, 1)
lbm_.materials.append(lmat_)
lab_ = bpy.data.objects.new("flow_parcel_w2_story_label", lbm_)
coll.objects.link(lab_)
lab_.parent = box

# ---------------------------------------------------------------- the avatar
before_o, before_a = set(sc.objects), set(bpy.data.actions)
bpy.ops.import_scene.fbx(filepath=str(Path(a.rb) / stations.W2_AVATAR / f"{stations.W2_AVATAR}.fbx"))
new_o = [o for o in sc.objects if o not in before_o]
arm = next(o for o in new_o if o.type == "ARMATURE")
body = next(o for o in new_o if o.type == "MESH" and o.parent == arm)
people._fix_materials(body, Path(a.rb) / stations.W2_AVATAR)
for o in new_o:
    if o.animation_data:
        o.animation_data.action = None
    for c_ in list(o.users_collection):
        c_.objects.unlink(o)
    coll.objects.link(o)
for act in [x for x in bpy.data.actions if x not in before_a]:
    bpy.data.actions.remove(act)
arm.name = "worker_w2_1"
body.name = "worker_w2_1_body"
bpy.context.view_layer.update()

import line_a_worker as LW  # noqa: E402

TRUNK = LW.trunk_clearance(arm, body) - 0.035 + 0.01
_ap = stations.S2_CARRY["above_pelvis"]
CARRY = dict(stations.S2_CARRY, snug_clear=LW.torso_front(arm, body, _ap - 0.06, _ap + 0.06) + 0.008)
LEGS = stations.w2_legs(PICK_C, PLACE_C)
cx, cy = stations.S2_CAGE.x, stations.S2_CAGE.y
cfg = dict(fps=a.fps, F=F, frame0=1, legs=LEGS, objects={}, palm_off=0.05, elbow_out=0.45, trunk_clear=TRUNK,
           finger_flat=0.6, carry=CARRY,
           box=dict(c=tuple(PICK_C), yaw=float(np.pi), dims=DIMS, support_z=top,
                    supports=[(cx - 0.34, cy - 0.38, cx + 0.34, cy + 0.38, stations.S2_SHELF_Z), stations.W2_BAG_RIM],
                    lean_cap=stations.S2_BOX_LEAN_CAP, give_s=1.2, give_rise=0.6),
           name="worker_w2_1@remover")


def lows():
    out = []
    for f in range(1, F + 1, 2):
        sc.frame_set(f)
        ob_ = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me_ = ob_.to_mesh()
        co_ = np.empty(len(me_.vertices) * 3)
        me_.vertices.foreach_get("co", co_)
        M_ = np.array(ob_.matrix_world)
        out.append(float((co_.reshape(-1, 3) @ M_[:3, :3].T + M_[:3, 3])[:, 2].min()))
        ob_.to_mesh_clear()
    return np.array(out)


res = None
for it in range(2):  # as captured, then lifted so the soles sit on the floor
    if res is not None:
        bpy.data.actions.remove(res["action"])
    rig = R.setup(arm, I.take(LEGS[1]["take"]))
    res = RM.compose(rig, cfg)
    if it == 0:
        cfg["lift"] = -float(np.percentile(lows(), 5))
loc, yaw = res["loc"], res["yaw"]
for f in range(F):
    box.location = Vector((loc[f][0], loc[f][1], loc[f][2]))
    box.rotation_euler = (0.0, 0.0, float(yaw[f]))
    box.keyframe_insert("location", frame=f + 1)
    box.keyframe_insert("rotation_euler", frame=f + 1)
sc.frame_start, sc.frame_end = 1, F
rel = res["report"]["frames"].get("release")
grasp = res["report"]["clips"][0]["event_t"]
end_pose = [round(float(v), 3) for v in (loc[-1][0], loc[-1][1], loc[-1][2] - DIMS[2] / 2)]
want = [round(float(v), 3) for v in (PLACE_C[0], PLACE_C[1], PLACE_C[2] - DIMS[2] / 2)]
rep = dict(bag_top=round(top, 3), grasp_t=grasp, release_frame=rel, release_t=((rel - 1) / a.fps if rel else None),
           end_pose=end_pose, s2_frame1_pose=want,
           end_vs_s2_mm=[round((e - w) * 1000, 1) for e, w in zip(end_pose, want)], report=res["report"])
(OUT / "w2_report.json").write_text(json.dumps(rep, indent=1, default=str))
print("W2", json.dumps({k: rep[k] for k in ("bag_top", "grasp_t", "release_t", "end_pose", "end_vs_s2_mm")}), flush=True)
bpy.ops.wm.save_as_mainfile(filepath=a.save)
print("SAVED", a.save, flush=True)
