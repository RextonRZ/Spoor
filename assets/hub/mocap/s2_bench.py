"""Bench for S2's removal actor on mocap (scenarios_v2 S2 #2, remover.py) in the real hub (layout b build): the S11
roll cage with a mid shelf, the small COD box on it, worker_s2_1 walking in, taking it, carrying it into the exception
store. Saves a blend for collision_check.py and writes the motion report + stills.

  blender -b --factory-startup -P assets/hub/mocap/s2_bench.py -- --out qa/review/s2_actor
          [--save assets/hub/build/qa/s2_bench.blend] [--stills]
"""
import argparse
import json
import math
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
ap.add_argument("--save", default=str(HUB / "build" / "qa" / "s2_bench.blend"))
ap.add_argument("--seconds", type=float, default=90.0)
ap.add_argument("--fps", type=float, default=10.0)
ap.add_argument("--avatar", default="Male_Adult_05")
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

# ---------------------------------------------------------------- the S11 cage with a mid shelf + the COD box
rnd = random.Random(2002)
stations._clear_bay(sc, SPEC, stations.S2_CAGE_BAY)
cage, _ = stations._cage_parts("cage_s2_S11", coll, rnd, loaded=True)
cage.location = stations.S2_CAGE
SHELF_Z = stations.S2_SHELF_Z  # removable wire shelf hooked into the side frames (roll containers with a mid shelf)
shm = bpy.data.meshes.new("cage_s2_shelf")
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bmesh.ops.scale(bm, vec=(0.68, 0.76, 0.02), verts=bm.verts)
bmesh.ops.translate(bm, vec=(0, 0, SHELF_Z - 0.01), verts=bm.verts)
bm.to_mesh(shm)
bm.free()
shm.materials.append(cage.material_slots[0].material if cage.material_slots else None)
shelf = bpy.data.objects.new("cage_s2_S11_shelf", shm)
coll.objects.link(shelf)
shelf.parent = cage
DIMS = stations.S2_PARCEL_DIMS  # w across the hands (x), d (y), h: a COD carton (review 021 #1)
# stations.S2_BOX_DX off the cage's centre line (was 7 cm left: his right shoulder had touched the front-right post,
# but his head then passed 1 mm off the front-left post as he turned out with it - review 021b #2; both measured
# by s2_close_proof.py)
C0 = Vector((stations.S2_CAGE.x + stations.S2_BOX_DX, stations.S2_CAGE.y - 0.40 + stations.S2_BOX_IN + DIMS[1] / 2, SHELF_Z + DIMS[2] / 2))
bxm = bpy.data.meshes.new("s2_box")
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bmesh.ops.scale(bm, vec=DIMS, verts=bm.verts)
bm.to_mesh(bxm)
bm.free()
mat = bpy.data.materials.new("s2_box_card")
mat.diffuse_color = (0.55, 0.42, 0.28, 1)
mat.use_nodes = True
mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.42, 0.28, 1)
bxm.materials.append(mat)
box = bpy.data.objects.new("flow_parcel_s2_story", bxm)
coll.objects.link(box)
lbm_ = bpy.data.meshes.new("s2_box_label")  # the white waybill on top (as flow's parcels)
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5,
                      matrix=Matrix.Translation((0.02, 0.0, DIMS[2] / 2 + 0.001)) @ Matrix.Diagonal((0.10, 0.15, 1, 1)))
bm.to_mesh(lbm_)
bm.free()
lmat_ = bpy.data.materials.new("s2_box_label")
lmat_.diffuse_color = (0.93, 0.93, 0.9, 1)
lbm_.materials.append(lmat_)
lab_ = bpy.data.objects.new("flow_parcel_s2_story_label", lbm_)
coll.objects.link(lab_)
lab_.parent = box

# ---------------------------------------------------------------- the avatar (no vest: as the S2 actor before)
before_o, before_a = set(sc.objects), set(bpy.data.actions)
bpy.ops.import_scene.fbx(filepath=str(Path(a.rb) / a.avatar / f"{a.avatar}.fbx"))
new_o = [o for o in sc.objects if o not in before_o]
arm = next(o for o in new_o if o.type == "ARMATURE")
body = next(o for o in new_o if o.type == "MESH" and o.parent == arm)
people._fix_materials(body, Path(a.rb) / a.avatar)
for o in new_o:
    if o.animation_data:
        o.animation_data.action = None
    for c_ in list(o.users_collection):
        c_.objects.unlink(o)
    coll.objects.link(o)
for act in [x for x in bpy.data.actions if x not in before_a]:
    bpy.data.actions.remove(act)
arm.name = "worker_s2_1"
body.name = "worker_s2_1_body"
bpy.context.view_layer.update()

import line_a_worker as LW  # noqa: E402

TRUNK = LW.trunk_clearance(arm, body) - 0.035 + 0.01  # his own torso + 1 cm (no vest: LW adds 3.5 cm for one)
_ap = stations.S2_CARRY["above_pelvis"]
CARRY = dict(stations.S2_CARRY, snug_clear=LW.torso_front(arm, body, _ap - 0.06, _ap + 0.06) + 0.008)
print("SNUG", round(TRUNK, 3), round(CARRY["snug_clear"], 3), flush=True)
LEGS = stations.s2_legs(C0)
PICK = LEGS[1]
rig = R.setup(arm, I.take(PICK["take"]))
cfg = dict(fps=a.fps, F=F, frame0=1, legs=LEGS, objects=stations.s2_objects(), palm_off=0.05, elbow_out=0.45, trunk_clear=TRUNK, finger_flat=0.6, carry=CARRY,
           box=dict(c=tuple(C0), yaw=0.0, dims=DIMS, support_z=SHELF_Z,
                    cage=(stations.S2_CAGE.x - 0.34, stations.S2_CAGE.y - 0.40, stations.S2_CAGE.x + 0.34,
                          stations.S2_CAGE.y + 0.38), supports=[stations.S2_STORE_SHELF_TOP],
                    lean_cap=stations.S2_BOX_LEAN_CAP, give_s=1.2, give_rise=0.6),
           name="worker_s2_1@remover")
res = RM.compose(rig, cfg)
# lowest body vertex -> lift (as m4_dock), then rebuild once
low = []
for f in range(1, F + 1, 2):
    sc.frame_set(f)
    ob_ = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me_ = ob_.to_mesh()
    co_ = np.empty(len(me_.vertices) * 3)
    me_.vertices.foreach_get("co", co_)
    M_ = np.array(ob_.matrix_world)
    low.append(float((co_.reshape(-1, 3) @ M_[:3, :3].T + M_[:3, 3])[:, 2].min()))
    ob_.to_mesh_clear()
cfg["lift"] = -float(np.percentile(low, 5))
bpy.data.actions.remove(res["action"])
rig = R.setup(arm, I.take(PICK["take"]))
res = RM.compose(rig, cfg)


def mesh_low():
    out = []
    for f in range(1, F + 1):
        sc.frame_set(f)
        ob_ = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me_ = ob_.to_mesh()
        co_ = np.empty(len(me_.vertices) * 3)
        me_.vertices.foreach_get("co", co_)
        M_ = np.array(ob_.matrix_world)
        out.append(float((co_.reshape(-1, 3) @ M_[:3, :3].T + M_[:3, 3])[:, 2].min()))
        ob_.to_mesh_clear()
    return np.array(out)


# joins: where the mesh still dips under the floor, lift the body by the dip (+2 mm), spread over +-2 frames
lows = mesh_low()
dip = np.where(lows < -0.004, -lows + 0.002, 0.0)
if dip.any():
    k_ = np.exp(-0.5 * (np.arange(-3, 4) / 1.2) ** 2)
    cfg["lift_f"] = np.maximum(np.convolve(dip, k_ / k_.max(), mode="same"), dip)
    bpy.data.actions.remove(res["action"])
    rig = R.setup(arm, I.take(PICK["take"]))
    res = RM.compose(rig, cfg)
rep = res["report"]
rep["lift_m"] = round(cfg["lift"], 4)
rep["trunk_clear_m"] = round(TRUNK, 3)
for f in range(1, F + 1):
    i = f - 1
    box.location = Vector(res["loc"][i])
    box.rotation_euler = (0.0, 0.0, float(res["yaw"][i]))
    box.keyframe_insert("location", frame=f)
    box.keyframe_insert("rotation_euler", frame=f)
for fc in box.animation_data.action.fcurves if hasattr(box.animation_data.action, "fcurves") else []:
    for kp in fc.keyframe_points:
        kp.interpolation = "LINEAR"
if "cage" in res["objects"]:  # the cage pushed to D07
    cl_, cy_ = res["objects"]["cage"]
    for f in range(1, F + 1):
        cage.location = stations.s2_cage_pose(cl_[f - 1], float(cy_[f - 1]))
        cage.rotation_euler = (0.0, 0.0, float(cy_[f - 1]))
        cage.keyframe_insert("location", frame=f)
        cage.keyframe_insert("rotation_euler", frame=f)
    rep["cage"] = res["report"]["frames"]["objects"].get("cage")
sc.frame_start, sc.frame_end = 1, F
sc.render.fps = int(a.fps)

# ---------------------------------------------------------------- QA: feet (stance skate, ground), body height range
bi = rig["bi"]
Hw = res["sol"]["Hw"]
skate, ground = {}, []
for sd, sj in (("L", "LeftAnkle"), ("R", "RightAnkle")):
    iv = R.contacts(res["Pw"][:, res["J"][sj]], a.fps)
    ft = Hw[:, bi[f"Bip01 {sd} Foot"]]
    worst = 0.0
    for i0, i1 in iv:
        seg = ft[i0 + 1:i1, :2]  # the lock ramps in/out over the ends
        if len(seg) > 1:
            worst = max(worst, float(np.max(np.linalg.norm(seg - np.median(seg, 0), axis=1))))
    skate[sd] = round(worst * 1000, 1)
for f in range(1, F + 1):
    sc.frame_set(f)
    ob_ = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me_ = ob_.to_mesh()
    co_ = np.empty(len(me_.vertices) * 3)
    me_.vertices.foreach_get("co", co_)
    M_ = np.array(ob_.matrix_world)
    ground.append(float((co_.reshape(-1, 3) @ M_[:3, :3].T + M_[:3, 3])[:, 2].min()))
    ob_.to_mesh_clear()
rep["foot_skate_mm_max"] = skate
rep["ground_min_mm"] = round(min(ground) * 1000, 1)
rep["ground_pen_frames_gt_5mm"] = [(f + 1, round(z * 1000, 1)) for f, z in enumerate(ground) if z < -0.005]
# where he is when (pelvis), and when the box crosses into the gap / out of sight
pel = Hw[:, bi["Bip01 Pelvis"]]
loc = res["loc"]
cross = next((f + 1 for f in range(F) if loc[f][1] > 33.0 and 13.4 < loc[f][0] < 15.2), None)
inside = next((f + 1 for f in range(F) if loc[f][1] > 33.6 and loc[f][0] < 13.0), None)
rep["box_enters_gap_frame"] = cross
rep["box_behind_south_rack_frame"] = inside
rep["pelvis_xy_every_2s"] = {int(f + 1): [round(float(pel[f][0]), 2), round(float(pel[f][1]), 2)]
                             for f in range(0, F, int(2 * a.fps))}
(OUT / "motion_report.json").write_text(json.dumps(rep, indent=1, default=str))
print("S2BENCH", json.dumps(rep, default=str), flush=True)
Path(a.save).parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(Path(a.save).resolve()))

# ---------------------------------------------------------------- stills: follow cam (workbench) + CCTV views
if a.stills:
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "MATERIAL"
    sc.display.shading.show_shadows = True
    sc.display.shading.show_cavity = True
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 88
    cd = bpy.data.cameras.new("follow")
    cam = bpy.data.objects.new("follow", cd)
    sc.collection.objects.link(cam)
    cd.lens = 35
    sc.render.resolution_x, sc.render.resolution_y = 1000, 800
    fr = res["report"]["frames"]
    keys = sorted({fr["grasp"] - 20, fr["grasp"] - 5, fr["grasp"], fr["lift"], fr["lift"] + 10, 150, (cross or 210),
                   (fr["release"] or 330) - 15, (fr["release"] or 330), (fr["release"] or 330) + 15,
                   (fr["release"] or 330) + 40, (fr["release"] or 330) + 80, (fr["release"] or 330) + 120})
    for f in keys:
        if not 1 <= f <= F:
            continue
        sc.frame_set(f)
        p = Vector(pel[f - 1])
        for tag, off in (("side", Vector((2.2, -1.6, 0.6))), ("front", Vector((-0.6, -2.6, 0.5)))):
            cam.location = p + off
            cam.rotation_euler = (p + Vector((0, 0, 0.1)) - cam.location).to_track_quat("-Z", "Y").to_euler()
            sc.camera = cam
            sc.render.filepath = str(OUT / f"{tag}_f{f:03d}.jpg")
            bpy.ops.render.render(write_still=True)
    sc.render.resolution_x, sc.render.resolution_y = 2688, 1520
    for cid, fs in (("CAM_13", keys[:5]), ("CAM_19", [k for k in keys if k >= 150])):
        sc.camera = sc.objects[cid]
        for f in fs:
            sc.frame_set(f)
            sc.render.filepath = str(OUT / f"{cid}_f{f:03d}.jpg")
            bpy.ops.render.render(write_still=True)
print("S2BENCH done", flush=True)
