"""M3 bench test: one line-A inductor (I2 of the M0 layout) on mocap, in a bare scene with the M0 pieces as boxes
(induction belt + frame, roller buffer table + end stop), parcels keyed from inductor.build. Gates measured on the
EVALUATED pose; optional front + side follow renders.

  blender -b --factory-startup -P assets/hub/mocap/m3_test.py -- --out qa/review/m3_test [--avatar Male_Adult_04]
          [--seconds 20] [--fps 10] [--seed 3] [--render]
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
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import inductor as I  # noqa: E402
import people  # noqa: E402
import retarget as R  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--avatar", default="Male_Adult_04")
ap.add_argument("--seconds", type=float, default=20.0)
ap.add_argument("--fps", type=float, default=10.0)
ap.add_argument("--seed", type=int, default=3)
ap.add_argument("--render", action="store_true")
ap.add_argument("--hub", action="store_true")  # in the lit hub (M0 pieces built in, old feed run cut, CAM_01)
ap.add_argument("--rb", default=str(HERE.parent / "build" / "third_party" / "rocketbox"))
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
OUT = Path(a.out).resolve()
OUT.mkdir(parents=True, exist_ok=True)
if a.hub:
    bpy.ops.wm.open_mainfile(filepath=str(HERE.parent / "build" / "hub_dressed_lit.blend"))
sc = bpy.context.scene
if a.hub:
    import stations  # noqa: E402
    stations._cut_region(sc, ["conveyors"], 5.3, 9.4, 10.4, 11.3, 0.3, 1.3)  # the old feed run (as M0)
    for o in list(sc.objects):
        if o.name.startswith(("flow_parcel_", "worker_")):
            bpy.data.objects.remove(o, do_unlink=True)
else:
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)

# ---------------------------------------------------------------- M0 geometry (I2)
X0, OP_Y = 8.6, 10.25
BELT_Y, BELT_HALF, BELT_TOP = 9.5, 0.45, 1.0
if a.hub:  # the hub's induction belt (raycast): flush top z 1.000 from y 9.10 to 9.85
    BELT_Y, BELT_HALF = 9.49, 0.36
FEED_Y = 11.35
TX, TY0, TY1, TZ0, TZ1, TW = X0 + 0.62, 10.88 if a.hub else 10.95, 10.15, 0.95, 0.88, 0.5
STOP_Y = TY1 - 0.03
SLOPE = math.atan((TZ0 - TZ1) / (TY0 - TY1))
statics = {}


def mat(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1)
    return m


M_ST, M_BELT, M_ROL, M_BOX = mat("steel", (0.5, 0.52, 0.55)), mat("belt", (0.04, 0.04, 0.04)), \
    mat("roller", (0.7, 0.7, 0.72)), mat("carton", (0.55, 0.4, 0.22))


def box(name, x0, y0, z0, x1, y1, z1, m, static=True):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
                          @ Matrix.Diagonal((x1 - x0, y1 - y0, z1 - z0, 1)))
    bm.to_mesh(me)
    bm.free()
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    if static:
        statics[name] = (np.array([x0, y0, z0]), np.array([x1, y1, z1]))
    return ob


if a.hub:  # the hub's own belt renders; its volume is checked
    statics["belt"] = (np.array([5.6, BELT_Y - BELT_HALF, 0.80]), np.array([15.0, BELT_Y + BELT_HALF, BELT_TOP]))
    # feed belt (M0: y 11.35, x 5-13): belt, far frame, near frame with a gap at the I2 table mouth, legs
    box("m0_feed_belt", 5.0, FEED_Y - 0.4, 0.94, 13.0, FEED_Y + 0.4, 1.0, M_BELT)
    box("m0_feed_frame_far", 5.0, FEED_Y + 0.41, 0.86, 13.0, FEED_Y + 0.45, 1.04, M_ST)
    box("m0_feed_frame_nearA", 5.0, FEED_Y - 0.45, 0.86, TX - TW / 2 - 0.03, FEED_Y - 0.41, 1.04, M_ST)
    box("m0_feed_frame_nearB", TX + TW / 2 + 0.03, FEED_Y - 0.45, 0.86, 13.0, FEED_Y - 0.41, 1.04, M_ST)
    box("m0_feed_endplate", 13.0, FEED_Y - 0.45, 0.92, 13.04, FEED_Y + 0.45, 1.14, M_ST)
    for lx in [5.2 + 1.9 * k for k in range(5)]:
        for sg_ in (-1, 1):
            box(f"m0_feed_leg_{lx:.1f}_{sg_}", lx - 0.03, FEED_Y + sg_ * 0.36 - 0.03, 0, lx + 0.03, FEED_Y + sg_ * 0.36 + 0.03,
                0.86, M_ST)
    # diverter paddle at the I2 mouth: pivots on the far frame downstream of the mouth, swings into the belt
    me_ = bpy.data.meshes.new("m0_diverter")
    bm_ = bmesh.new()
    bmesh.ops.create_cube(bm_, size=1.0, matrix=Matrix.Translation((-0.32, 0, 0)) @ Matrix.Diagonal((0.64, 0.025, 0.1, 1)))
    bm_.to_mesh(me_)
    bm_.free()
    me_.materials.append(mat("diverter_yellow", (0.85, 0.65, 0.05)))
    DIV = bpy.data.objects.new("m0_diverter", me_)
    sc.collection.objects.link(DIV)
    DIV.location = (TX + TW / 2 + 0.05, FEED_Y + 0.37, 1.06)
else:
    box("belt", 5.6, BELT_Y - BELT_HALF + 0.03, BELT_TOP - 0.06, 15.0, BELT_Y + BELT_HALF - 0.03, BELT_TOP, M_BELT)
    for sgn in (-1, 1):  # far side: 4 cm guide; operator side flush with the belt (parcels slide in over it)
        box(f"belt_frame_{sgn}", 5.6, BELT_Y + sgn * BELT_HALF - 0.03, 0.86, 15.0, BELT_Y + sgn * BELT_HALF + 0.03,
            BELT_TOP + (0.04 if sgn < 0 else 0.0), M_ST)
for k in range(9):
    u = k / 8
    y = TY0 + (TY1 - TY0) * u
    z = TZ0 + (TZ1 - TZ0) * u
    box(f"roller_{k}", TX - TW / 2, y - 0.025, z - 0.05, TX + TW / 2, y + 0.025, z, M_ROL)
TYM = (TY0 + TY1) / 2
for sgn in (-1, 1):  # side guides 3 cm above the rollers (two lengths: the table falls towards the operator)
    box(f"table_side_{sgn}", TX + sgn * TW / 2 - 0.02, TY1 - 0.03, 0.80, TX + sgn * TW / 2 + 0.02, TYM, TZ1 + 0.045, M_ST)
    box(f"table_sideB_{sgn}", TX + sgn * TW / 2 - 0.02, TYM, 0.80, TX + sgn * TW / 2 + 0.02, TY0, TZ0 + 0.03, M_ST)
box("table_stop", TX - TW / 2, STOP_Y - 0.03, 0.85, TX + TW / 2, STOP_Y, 0.92, M_ST)  # low end-stop plate
for k in (-1, 1):  # table legs
    for yy in (TY1 + 0.05, TY0 - 0.08):
        box(f"table_leg_{k}_{yy:.2f}", TX + k * 0.2 - 0.02, yy - 0.02, 0, TX + k * 0.2 + 0.02, yy + 0.02, 0.8, M_ST, static=False)
if not a.hub:
    bpy.ops.mesh.primitive_plane_add(size=40, location=(X0, OP_Y, 0))
    bpy.context.active_object.data.materials.append(mat("floor", (0.35, 0.35, 0.36)))

# ---------------------------------------------------------------- avatar + mocap
before_o, before_a = set(sc.objects), set(bpy.data.actions)
bpy.ops.import_scene.fbx(filepath=str(Path(a.rb) / a.avatar / f"{a.avatar}.fbx"))
new_o = [o for o in sc.objects if o not in before_o]
arm = next(o for o in new_o if o.type == "ARMATURE")
body = next(o for o in new_o if o.type == "MESH" and o.parent == arm)  # Rocketbox: one skinned mesh
people._fix_materials(body, Path(a.rb) / a.avatar)
for o in new_o:
    if o.animation_data:
        o.animation_data.action = None
for act in [x for x in bpy.data.actions if x not in before_a]:
    bpy.data.actions.remove(act)
if a.hub:  # the hub's hi-vis vest, as on every worker
    try:
        vest = people._vest(body, arm)
        sc.collection.objects.link(vest)
        vest.material_slots[0].link = "OBJECT"
        vest.material_slots[0].material = people._vest_material("yellow", people.VEST_COLOURS["yellow"], False,
                                                                vest["front_is_low_y"])
    except Exception as e:  # noqa: BLE001
        print("vest failed", repr(e), flush=True)
arm.location.x, arm.location.y = X0, OP_Y  # z stays: the FBX importer puts the object at pelvis height
bpy.context.view_layer.update()
rnd = random.Random(a.seed)
picks, places = I.candidates()
b0 = I.take(picks[0]["take"])
rig = R.setup(arm, b0)
F = int(a.seconds * a.fps)
RAIL_X = TX - TW / 2 - 0.02  # the table's near side rail
station = dict(x=X0, belt_yaw=0.0, table_pt=(TX, STOP_Y + 0.12, TZ1 + 0.01), place_y=BELT_Y + 0.25,
               clear_y=BELT_Y + BELT_HALF + 0.03 + 0.21,  # hip joints 21 cm off the belt frame's outer face
               grip_axis_yaw=-math.pi / 2,
               root_min_y=BELT_Y + BELT_HALF + 0.03 + 0.19,  # every frame, not just at the release
               refill_s=0.4 + (TY0 - TY1 - 0.15) / 0.4,  # diverter at the lift, roll 0.4 m/s down the table  # table carton: left hand upstream (+Y), right hand on the stop side
               pick_root_max=(RAIL_X - 0.26, 1e9), pick_grip_min_z=TZ1 + 0.045 + 0.05,  # guide top + half a palm
               table_align_x=RAIL_X + 0.02,  # skewed rollers: cartons run against the operator-side rail
               surfaces=[(5.6, BELT_Y - BELT_HALF, 15.0, BELT_Y + BELT_HALF, BELT_TOP),
                         (TX - TW / 2, TY1 - 0.03, TX + TW / 2, TY0, TZ0)],
               place_x=(X0 - 0.4, X0 + 0.4), place_y_range=(BELT_Y - BELT_HALF + 0.05, BELT_Y + BELT_HALF - 0.05),
               belt_top=BELT_TOP, belt_speed=1.5, belt_dir=1.0, table_slope=SLOPE)
segs = I.plan_cycles(rig, station, F, a.fps, rnd, picks, places)
parcels = {n: dict(dims=(rnd.uniform(0.22, 0.36), rnd.uniform(0.18, 0.28), rnd.uniform(0.12, 0.20))) for n in range(60)}
import copy  # noqa: E402
segs0 = copy.deepcopy(segs)
res = I.build(rig, segs, station, parcels, F, a.fps, name=f"inductor@{a.avatar}")
# pass 2: the lowest sole point over the whole take exactly on the floor (measured on the deformed mesh)
low = 1e9
for f in range(F):
    sc.frame_set(f + 1)
    ob_ = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me_ = ob_.to_mesh()
    co_ = np.empty(len(me_.vertices) * 3)
    me_.vertices.foreach_get("co", co_)
    low = min(low, float((co_.reshape(-1, 3) @ np.array(ob_.matrix_world)[:3, :3].T)[:, 2].min()
                         + ob_.matrix_world.translation.z))
    ob_.to_mesh_clear()
station["lift"] = -low
bpy.data.actions.remove(res["action"])
segs = segs0
res = I.build(rig, segs, station, parcels, F, a.fps, name=f"inductor@{a.avatar}")
sc.render.fps = int(a.fps)
sc.frame_start, sc.frame_end = 1, F

# ---------------------------------------------------------------- parcels (world matrix baked per frame)
pobs = {}
lifts = {e["n"]: min(F - 1, int(round(e["t"] * a.fps))) for e in res["events"] if e["kind"] == "lift"}


def table_z(y, h):
    return TZ1 + (y - TY1) * (TZ0 - TZ1) / (TY0 - TY1) + h / 2


for n, tr in res["tracks"].items():
    w_, d_, h_ = tr["dims"]
    ob = box(f"parcel_{n}", -w_ / 2, -d_ / 2, -h_ / 2, w_ / 2, d_ / 2, h_ / 2, M_BOX, static=False)
    ob.rotation_mode = "ZYX"
    ext_y = 0.5 * (abs(w_ * math.sin(tr["yaw"][0])) + abs(d_ * math.cos(tr["yaw"][0])))  # along the table
    stop_c = tr["loc"][tr["grasp"]][1]
    prev = res["tracks"].get(n - 1)
    # one carton on the table at a time: diverted onto the table head when the previous one is lifted, rolls down
    # at 0.4 m/s (gravity rollers) to the end stop
    q_c = TY0 - ext_y - 0.02
    t_in = (lifts[n - 1] + int(round(0.4 * a.fps))) if n - 1 in lifts else -1  # diverter 0.4 s after the lift
    t_show = t_in
    tdv = t_in - int(round(0.4 * a.fps))  # the diverter fires; the carton left the feed 0.4 s before rolling
    for f in range(F):
        loc = np.array(tr["loc"][f])
        if tr["state"][f] == "table":
            y = q_c if f < t_in else max(stop_c, q_c - 0.4 * (f - t_in) / a.fps)
            loc = np.array([loc[0], y, table_z(y, h_)])
            if a.hub and t_in >= 0 and f < t_in:
                if f < tdv:  # on the feed belt, 0.6 m/s towards the table mouth
                    loc = np.array([loc[0] - 0.6 * (tdv - f) / a.fps, FEED_Y, 1.0 + h_ / 2])
                else:  # pushed off by the paddle over the mouth onto the table head
                    u_ = (f - tdv) / max(1, t_in - tdv)
                    loc = np.array([loc[0], FEED_Y + (q_c - FEED_Y) * u_, 1.0 + h_ / 2 + (table_z(q_c, h_) - 1.0 - h_ / 2) * u_])
        ob.location = tuple(loc)
        ob.rotation_euler = (tr["pitch"][f], 0.0, tr["yaw"][f])
        vis = ((tr["state"][f] != "belt") or tr["loc"][f][0] < 15.0) and (f >= t_show if not a.hub else loc[0] >= 5.0)
        ob.hide_render = not vis
        ob.keyframe_insert("location", frame=f + 1)
        ob.keyframe_insert("rotation_euler", frame=f + 1)
        ob.keyframe_insert("hide_render", frame=f + 1)
    pobs[n] = ob
    if a.hub and t_in >= 0:  # the paddle: out 45 deg over 0.2 s as the carton reaches the mouth, back over 0.3 s
        for fk, ang in ((tdv - 2, 0.0), (tdv, 45.0), (tdv + 3, 45.0), (tdv + 6, 0.0)):
            if 0 <= fk < F:
                DIV.rotation_euler = (0, 0, math.radians(-ang))
                DIV.keyframe_insert("rotation_euler", frame=fk + 1)

# ---------------------------------------------------------------- QA on the evaluated pose
bi = rig["bi"]
names = list(bi)
vgn = {g_.index: g_.name for g_ in body.vertex_groups}
dom = np.array([vgn[max(v.groups, key=lambda g_: g_.weight).group] if len(v.groups) else "-" for v in body.data.vertices])


def part(bn):
    if "Finger" in bn:
        return bn.replace("Bip01 ", "")
    for k_, v_ in (("Finger", "fingers"), ("Hand", "hands"), ("Forearm", "forearms"), ("UpperArm", "upper arms"),
                   ("Thigh", "thighs"), ("Calf", "calves"), ("Foot", "feet"), ("Toe", "feet"), ("Head", "head")):
        if k_ in bn:
            return v_
    return "trunk"
ev = np.zeros((F, len(names), 3))
lows, inside_static, inside_parcel = [], {}, {}
gaps = []
gap_at = []
hand_v = {x_: np.array([("Bip01 %s Hand" % x_) in dm_ or ("Bip01 %s Finger" % x_) in dm_ for dm_ in dom]) for x_ in ("L", "R")}
for f in range(F):
    sc.frame_set(f + 1)
    M = arm.matrix_world
    ev[f] = [tuple(M @ arm.pose.bones[n].head) for n in names]
    dg = bpy.context.evaluated_depsgraph_get()
    ob = body.evaluated_get(dg)
    me = ob.to_mesh()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3) @ np.array(ob.matrix_world)[:3, :3].T + np.array(ob.matrix_world)[:3, 3]
    ob.to_mesh_clear()
    lows.append(co[:, 2].min())
    for nm, (lo, hi) in statics.items():
        ins = np.all((co > lo) & (co < hi), axis=1)
        if ins.any():
            dep = np.minimum(co[ins] - lo, hi - co[ins]).min(1)
            j_ = int(np.argmax(dep))
            inside_static.setdefault(nm, []).append((f + 1, float(dep[j_]), part(dom[ins][j_])))
    for n, pob in pobs.items():
        tr_ = res["tracks"][n]
        if tr_["grasp"] <= f <= tr_["release"]:  # signed gap of each hand's skin to the held carton
            Mi = np.array(pob.matrix_world.inverted())
            hb = np.array(tr_["dims"]) / 2
            for x_ in ("L", "R"):
                sel = hand_v[x_]
                lc = co[sel] @ Mi[:3, :3].T + Mi[:3, 3]
                q_ = np.abs(lc) - hb
                outside = np.linalg.norm(np.maximum(q_, 0), axis=1)
                sd_ = np.where(np.all(q_ < 0, axis=1), q_.max(1), outside)
                gaps.append(float(sd_.min()))
                gap_at.append((f + 1, n, x_, round(float(sd_.min()) * 1000, 1)))
        if pob.hide_render:
            continue
        Mi = np.array(pob.matrix_world.inverted())
        loc = co @ Mi[:3, :3].T + Mi[:3, 3]
        w_, d_, h_ = res["tracks"][n]["dims"]
        hb = np.array([w_, d_, h_]) / 2
        ins = np.all(np.abs(loc) < hb, axis=1)
        if ins.any():
            dep = (hb - np.abs(loc[ins])).min(1)
            j_ = int(np.argmax(dep))
            inside_parcel.setdefault(n, []).append((f + 1, float(dep[j_]), part(dom[ins][j_])))
pm = np.stack([ev[:, bi[f"Bip01 {x} Hand"]] + 0.55 * (ev[:, bi[f"Bip01 {x} Finger2"]] - ev[:, bi[f"Bip01 {x} Hand"]])
               for x in ("L", "R")], 1)
herr, yaw_hold = [], []
hips_fwd = None
for n, tr in res["tracks"].items():
    g, r_ = tr["grasp"], tr["release"]
    for f in range(g, r_ + 1):
        for i, x in enumerate(("L", "R")):
            herr.append(float(np.linalg.norm(pm[f, i] - res["targets"][x][f])))
# heading while holding: pelvis forward (hip line normal)
hl = ev[:, bi["Bip01 L Thigh"]] - ev[:, bi["Bip01 R Thigh"]]
head = np.unwrap(np.arctan2(hl[:, 1], hl[:, 0]))
for n, tr in res["tracks"].items():
    seg = head[tr["grasp"]:tr["release"] + 1]
    yaw_hold.append(round(math.degrees(float(seg.max() - seg.min())), 1))
src = res["src"]
J = res["J"]
contacts = []
for sd, sj in (("L", "LeftAnkle"), ("R", "RightAnkle")):
    tp = ev[:, bi[f"Bip01 {sd} Foot"], :2]
    for i, j in R.contacts(src[:, J[sj]], a.fps):
        contacts.append(round(float(np.max(np.linalg.norm(tp[i:j + 1] - tp[i], axis=1))) * 1000, 1))
gr = sorted(tr["grasp"] for tr in res["tracks"].values())
cyc = np.diff(gr) / a.fps
qa = dict(avatar=a.avatar, frames=F, fps=a.fps, cycles=len(res["tracks"]),
          cycle_s=dict(mean=round(float(cyc.mean()), 2), min=round(float(cyc.min()), 2), max=round(float(cyc.max()), 2))
          if len(cyc) else None,
          hand_to_socket_mm=dict(p95=round(float(np.percentile(herr, 95)) * 1000, 1), max=round(max(herr) * 1000, 1)),
          yaw_while_holding_deg=yaw_hold, foot_skate_mm_max=max(contacts), contacts=len(contacts),
          ground_pen_frames=int((np.array(lows) < -0.0005).sum()), lowest_mm=round(float(min(lows)) * 1000, 1),
          pen_static={k: dict(frames=len(v), frames_over_1cm=sum(d_ > 0.01 for _, d_, _ in v),
                              max_mm=round(max(d_ for _, d_, _ in v) * 1000, 1),
                              worst=max(v, key=lambda e: e[1])[2], at=max(v, key=lambda e: e[1])[0])
                      for k, v in inside_static.items()},
          pen_parcel={str(k): dict(frames=len(v), frames_over_1cm=sum(d_ > 0.01 for _, d_, _ in v),
                                   max_mm=round(max(d_ for _, d_, _ in v) * 1000, 1),
                                   worst=max(v, key=lambda e: e[1])[2], at=max(v, key=lambda e: e[1])[0])
                      for k, v in inside_parcel.items()},
          clips=[dict(kind=s_["kind"], take=s_["clip"]["take"][12:16], mirror=s_["clip"]["mirror"],
                      t0=round(s_["clip"]["t0"], 2), ratio=round(s_["ratio"], 3)) for s_ in segs if s_["kind"] != "hold"
                 and s_["out0"] < a.seconds])
mp = I.palm_pts(res["sol"], rig)
hold = np.zeros(F, bool)
for tr in res["tracks"].values():
    hold[tr["grasp"]:tr["release"] + 1] = True
qa["model_vs_blender_palm_mm"] = round(float(np.abs(mp - pm).max()) * 1000, 1)
qa["model_palm_to_target_hold_mm"] = round(float(max(np.linalg.norm(mp[hold, i] - res["targets"][x][hold], axis=1).max()
                                                    for i, x in enumerate(("L", "R")))) * 1000, 1)
qa["model_vs_blender_all_heads_mm"] = round(float(np.abs(res["sol"]["Hw"] - ev).max()) * 1000, 1)
qa["ik_short"] = {k: dict(frames_out_of_reach=v[0], worst_m=round(v[1], 3), ik_frames=v[2], arm_len_m=round(v[3], 3),
                          where=v[4])
                  for k, v in res["sol"].get("ik_short", {}).items()}
_H = res["sol"]["Hw"]
for f_ in (20, 25, 26):
    print("DBG f", f_ + 1, "tgtL", np.round(res["targets"]["L"][f_], 3), "tgtR", np.round(res["targets"]["R"][f_], 3),
          "shL", np.round(_H[f_, bi["Bip01 L UpperArm"]], 3), "shR", np.round(_H[f_, bi["Bip01 R UpperArm"]], 3),
          "pelvis", np.round(_H[f_, bi["Bip01 Pelvis"]], 3), "parcel", np.round(res["tracks"][0]["loc"][f_], 3),
          "yaw", round(float(np.degrees(res["tracks"][0]["yaw"][f_])), 1), "dims", np.round(res["tracks"][0]["dims"], 3),
          flush=True)
qa["lean_deg_max"] = round(res["sol"].get("lean_deg_max", 0.0), 1)
qa["unstoop_deg_max"] = round(res["sol"].get("unstoop_deg_max", 0.0), 1)
qa["hand_skin_to_carton_mm"] = dict(min=round(min(gaps) * 1000, 1), p05=round(float(np.percentile(gaps, 5)) * 1000, 1),
                                    p50=round(float(np.median(gaps)) * 1000, 1), p95=round(float(np.percentile(gaps, 95)) * 1000, 1),
                                    max=round(max(gaps) * 1000, 1))
qa["hold_gap_over_10mm"] = [g_ for g_ in gap_at if abs(g_[3]) > 10]
# 014d #3: hand height at the grasp, source (scaled, placed) vs target; #1: turn directions per cycle
hh = []
for n, tr in res["tracks"].items():
    g_ = tr["grasp"]
    hh.append(dict(n=n, source_palms_z=round(float(res["src_palms"][g_].mean(0)[2]), 3),
                   target_grip_z=round(float((res["targets"]["L"][g_][2] + res["targets"]["R"][g_][2]) / 2), 3)))
qa["hand_height_at_grasp_m"] = hh
turns = []
tl = sorted(res["tracks"].items())
for i_, (n, tr) in enumerate(tl):
    yg, yr = math.degrees(head[tr["grasp"]]), math.degrees(head[tr["release"]])
    row = dict(n=n, to_belt_deg=round(yr - yg, 1))
    if i_ > 0:
        row["to_table_deg"] = round(yg - math.degrees(head[tl[i_ - 1][1]["release"]]), 1)
    # facing vs the direction to the table carton at the grasp (never the back to it)
    pel = ev[tr["grasp"], bi["Bip01 Pelvis"], :2]
    tdir = tr["loc"][tr["grasp"]][:2] - pel
    fwd_ = np.array([math.sin(head[tr["grasp"]]), -math.cos(head[tr["grasp"]])])  # hip-line normal (facing)
    row["facing_vs_table_deg"] = round(math.degrees(math.acos(np.clip(np.dot(fwd_, tdir / np.linalg.norm(tdir)), -1, 1))), 1)
    turns.append(row)
qa["turns"] = turns
qa["events"] = {str(n): dict(grasp=tr["grasp"] + 1, release=tr["release"] + 1, belt_wait_s=tr.get("belt_wait_s"))
                for n, tr in res["tracks"].items()}
qa["detail_parcel"] = {str(k): [(f_, round(d_ * 1000), p_) for f_, d_, p_ in v] for k, v in inside_parcel.items()}
qa["detail_static"] = {k: [(f_, round(d_ * 1000), p_) for f_, d_, p_ in v] for k, v in inside_static.items()}
print("M3 QA", json.dumps(qa), flush=True)
(OUT / "m3_qa.json").write_text(json.dumps(qa, indent=1), encoding="utf-8")
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "m3_test.blend"))

if a.render:
    sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in {
        e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items} else "BLENDER_EEVEE"
    if hasattr(sc.eevee, "taa_render_samples"):
        sc.eevee.taa_render_samples = 8
    sc.render.image_settings.file_format = "PNG"
    if not a.hub:
        w = bpy.data.worlds.new("w")
        w.use_nodes = True
        w.node_tree.nodes["Background"].inputs[0].default_value = (0.4, 0.41, 0.43, 1)
        sc.world = w
        ld = bpy.data.lights.new("key", "SUN")
        ld.energy = 3.0
        lo = bpy.data.objects.new("key", ld)
        sc.collection.objects.link(lo)
        lo.rotation_euler = (math.radians(45), 0, math.radians(200))
    tgt = Vector((X0 + 0.25, OP_Y - 0.2, 0.95))
    views = [("front", (X0 + 0.25, BELT_Y - 3.2, 1.9)), ("side", (X0 - 3.3, OP_Y - 0.3, 1.7))]
    views.append(("cctv", "CAM_01") if a.hub else ("cctv", (X0 + 6.0, OP_Y - 6.0, 6.0)))
    (OUT / "frames").mkdir(exist_ok=True)
    for tag, loc in views:
        if isinstance(loc, str):  # the hub's own CCTV camera, half resolution
            cam = sc.objects[loc]
            sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 2688, 1520, 50
        else:
            sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 640, 640, 100
            cd = bpy.data.cameras.new(tag)
            cd.lens = 35 if tag != "cctv" else 28
            cam = bpy.data.objects.new(tag, cd)
            sc.collection.objects.link(cam)
            cam.location = loc
            cam.rotation_euler = (tgt - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        sc.camera = cam
        sc.render.filepath = str(OUT / "frames" / f"{tag}_####")
        bpy.ops.render.render(animation=True)
    print("M3 rendered", flush=True)
