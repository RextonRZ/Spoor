"""M4 (014_GO): line A with 4 mocap inductors (M0 layout: x 7.0 / 8.6 / 10.2 / 11.8, 1.6 m apart, facing belt A,
roller table at each front-left, one diverter per table mouth) in the lit hub. Each worker: own avatar (flat shoes
only), own seed (clip order, retime ratios, carton sizes), random start offset over 0-1 cycle (no phase lock), no two
neighbours on the same take at the same moment. QA per worker on the EVALUATED pose + person spacing (< 0.3 m = fail).

  blender -b --factory-startup -P assets/hub/mocap/m4_line_a.py -- --out qa/review/m4_line_a [--seconds 30] [--render]
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
from mathutils.kdtree import KDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import inductor as I  # noqa: E402
import people  # noqa: E402
import retarget as R  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--seconds", type=float, default=30.0)
ap.add_argument("--fps", type=float, default=10.0)
ap.add_argument("--seed", type=int, default=11)
ap.add_argument("--render", action="store_true")
ap.add_argument("--avatars", default="")  # override, comma-separated, in station order
ap.add_argument("--stations", default="0,2")  # staffed tables (option a: I1 + I3; "0,1,2,3" = all four)
ap.add_argument("--rb", default=str(HERE.parent / "build" / "third_party" / "rocketbox"))
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
OUT = Path(a.out).resolve()
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(HERE.parent / "build" / "hub_dressed_lit.blend"))
sc = bpy.context.scene
import stations  # noqa: E402

stations._cut_region(sc, ["conveyors"], 5.3, 9.4, 10.4, 11.3, 0.3, 1.3)  # the old feed run (as M0)
for o in list(sc.objects):
    if o.name.startswith(("flow_parcel_", "worker_")):
        bpy.data.objects.remove(o, do_unlink=True)

INDUCT_X = [7.0, 8.6, 10.2, 11.8]
AVATARS = ["Male_Adult_04", "Male_Adult_12", "Male_Adult_09", "Male_Adult_05"]  # flat shoes, trousers (014c #5); F09 hands fail the grip (todo)
VESTS = ["yellow", "orange", "lime", "yellow"]
if a.avatars:
    AVATARS = a.avatars.split(",")
# review 015 option (b): one induct point per operator. Line A moves 0.9 m north so a 1.2 m induct belt fits between
# each worker and belt A: it starts 0.5 m in front of the worker and runs 45 deg (+x, -y) into belt A's edge
OP_Y, BELT_Y, BELT_HALF, BELT_TOP, FEED_Y = 11.15, 9.49, 0.36, 1.0, 12.25  # the hub's belt A: flush, y 9.10-9.85
TDX, TY0, TY1, TZ0, TZ1, TW = 0.68, OP_Y + 0.63, OP_Y - 0.10, 0.95, 0.88, 0.5
IND_D = np.array([math.sqrt(0.5), -math.sqrt(0.5)])  # induct belt direction (45 deg into belt A, downstream)
IND_HW = 0.25
IND_LEN = (OP_Y - 0.5 - (BELT_Y + BELT_HALF - 0.05)) / math.sqrt(0.5)  # ~1.2 m, ends 5 cm over belt A's edge
STOP_Y = TY1 - 0.03
SLOPE = math.atan((TZ0 - TZ1) / (TY0 - TY1))
F = int(a.seconds * a.fps)
statics = {"belt": (np.array([5.6, BELT_Y - BELT_HALF, 0.80]), np.array([15.0, BELT_Y + BELT_HALF, BELT_TOP]))}


def mat(name, rgb):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1)
    return m


M_ST, M_BELT, M_ROL, M_BOX, M_DIV = mat("m4_steel", (0.5, 0.52, 0.55)), mat("m4_belt", (0.04, 0.04, 0.04)), \
    mat("m4_roller", (0.7, 0.7, 0.72)), mat("m4_carton", (0.55, 0.4, 0.22)), mat("m4_diverter", (0.85, 0.65, 0.05))
CARTON_MATS = [M_BOX, mat("m4_carton_dark", (0.42, 0.29, 0.15)), mat("m4_carton_kraft", (0.62, 0.48, 0.30)),
               mat("m4_carton_white", (0.78, 0.78, 0.76))]
M_LABEL = mat("m4_label", (0.9, 0.9, 0.88))


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


# ---------------------------------------------------------------- geometry: feed belt (gaps at the 4 mouths), tables
box("m4_feed_belt", 5.6, FEED_Y - 0.4, 0.94, 13.0, FEED_Y + 0.4, 1.0, M_BELT)
box("m4_feed_frame_far", 5.6, FEED_Y + 0.41, 0.86, 13.0, FEED_Y + 0.45, 1.04, M_ST)
edges = [5.6] + sum([[x + TDX - TW / 2 - 0.03, x + TDX + TW / 2 + 0.03] for x in INDUCT_X], []) + [13.0]
for i in range(0, len(edges), 2):
    box(f"m4_feed_frame_near_{i}", edges[i], FEED_Y - 0.45, 0.86, edges[i + 1], FEED_Y - 0.41, 1.04, M_ST)
box("m4_feed_endplate", 13.0, FEED_Y - 0.45, 0.92, 13.04, FEED_Y + 0.45, 1.14, M_ST)
for lx in [5.8 + 1.8 * k for k in range(5)]:
    for sg_ in (-1, 1):
        box(f"m4_feed_leg_{lx:.1f}_{sg_}", lx - 0.03, FEED_Y + sg_ * 0.36 - 0.03, 0, lx + 0.03, FEED_Y + sg_ * 0.36 + 0.03,
            0.86, M_ST)
DIV = {}


def induct_belt(k, x0):
    """A 1.2 m x 0.5 m induct belt (rotated mesh, 4 legs) + its QA volume as 6 stepped boxes along it."""
    S = np.array([x0 - 0.15, OP_Y - 0.5])  # starts a little to his right: the 45 deg run passes in front of him
    c = S + IND_D * IND_LEN / 2
    me = bpy.data.meshes.new(f"m4_induct_{k}")
    bm = bmesh.new()
    ang = math.atan2(IND_D[1], IND_D[0])
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((c[0], c[1], BELT_TOP - 0.03))
                          @ Matrix.Rotation(ang, 4, "Z") @ Matrix.Diagonal((IND_LEN, 2 * IND_HW, 0.06, 1)))
    nrm = np.array([-IND_D[1], IND_D[0]])
    for leg in (0.15, IND_LEN - 0.15):
        for side in (-1, 1):
            q = S + IND_D * leg + nrm * side * (IND_HW - 0.05)
            bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((q[0], q[1], (BELT_TOP - 0.06) / 2))
                                  @ Matrix.Diagonal((0.05, 0.05, BELT_TOP - 0.06, 1)))
    bm.to_mesh(me)
    bm.free()
    me.materials.append(M_BELT)
    ob = bpy.data.objects.new(f"m4_induct_{k}", me)
    sc.collection.objects.link(ob)
    boxes = []
    for j in range(6):
        pts = [S + IND_D * IND_LEN * (j + u) / 6 + nrm * v * IND_HW for u in (0, 1) for v in (-1, 1)]
        lo, hi = np.min(pts, 0), np.max(pts, 0)
        statics[f"m4_induct_{k}_{j}"] = (np.array([lo[0], lo[1], BELT_TOP - 0.06]), np.array([hi[0], hi[1], BELT_TOP]))
        boxes.append((lo[0], lo[1], hi[0], hi[1], BELT_TOP))
    return S, boxes


INDUCT = {}
for k, x0 in enumerate(INDUCT_X):
    INDUCT[k] = induct_belt(k, x0)
    TX = x0 + TDX
    for j in range(9):
        u = j / 8
        y = TY0 + (TY1 - TY0) * u
        z = TZ0 + (TZ1 - TZ0) * u
        box(f"m4_t{k}_roller_{j}", TX - TW / 2, y - 0.025, z - 0.05, TX + TW / 2, y + 0.025, z, M_ROL)
    TYM = (TY0 + TY1) / 2
    for sg_ in (-1, 1):
        box(f"m4_t{k}_side_{sg_}", TX + sg_ * TW / 2 - 0.02, TY1 - 0.03, 0.80, TX + sg_ * TW / 2 + 0.02, TYM, TZ1 + 0.045, M_ST)
        box(f"m4_t{k}_sideB_{sg_}", TX + sg_ * TW / 2 - 0.02, TYM, 0.80, TX + sg_ * TW / 2 + 0.02, TY0, TZ0 + 0.03, M_ST)
    box(f"m4_t{k}_stop", TX - TW / 2, STOP_Y - 0.03, 0.85, TX + TW / 2, STOP_Y, 0.92, M_ST)
    for kk in (-1, 1):
        for yy in (TY1 + 0.05, TY0 - 0.08):
            box(f"m4_t{k}_leg_{kk}_{yy:.2f}", TX + kk * 0.2 - 0.02, yy - 0.02, 0, TX + kk * 0.2 + 0.02, yy + 0.02, 0.8,
                M_ST, static=False)
    me_ = bpy.data.meshes.new(f"m4_diverter_{k}")
    bm_ = bmesh.new()
    bmesh.ops.create_cube(bm_, size=1.0, matrix=Matrix.Translation((-0.32, 0, 0)) @ Matrix.Diagonal((0.64, 0.025, 0.1, 1)))
    bm_.to_mesh(me_)
    bm_.free()
    me_.materials.append(M_DIV)
    DIV[k] = bpy.data.objects.new(f"m4_diverter_{k}", me_)
    sc.collection.objects.link(DIV[k])
    DIV[k].location = (TX + TW / 2 + 0.05, FEED_Y + 0.37, 1.06)

# ---------------------------------------------------------------- workers (upstream first: belt A runs +x)


def floor_fix(w):
    """Mesh-measured floor lift for this worker (others present), then rebuild (as M3)."""
    low = 1e9
    for f in range(1, F + 1):
        sc.frame_set(f)
        ob_ = w["body"].evaluated_get(bpy.context.evaluated_depsgraph_get())
        me_ = ob_.to_mesh()
        co_ = np.empty(len(me_.vertices) * 3)
        me_.vertices.foreach_get("co", co_)
        M_ = np.array(ob_.matrix_world)
        low = min(low, float((co_.reshape(-1, 3) @ M_[:3, :3].T + M_[:3, 3])[:, 2].min()))
        ob_.to_mesh_clear()
    w["st"]["lift"] = -low
    bpy.data.actions.remove(w["res"]["action"])
    import copy
    w["res"] = I.build(w["rig"], copy.deepcopy(w["segs"]), w["st"], w["parcels"], F + w["off"], a.fps,
                       frame0=1 - w["off"], name=f"inductor@{w['av']}#{w['k']}")


def merge_fix(w):
    """Conveyor gap control at the merge: a carton reaching the end of its induct belt waits there (that belt stops)
    until belt A is clear at the merge point (+-(both half sizes + 0.15 m)) for its next 0.6 s; then it rides belt A.
    Registers its belt-A run for the workers downstream (built after this one)."""
    off, Fb = w["off"], F + w["off"]
    for n, tr in sorted(w["res"]["tracks"].items()):
        r_ = tr["release"]
        if r_ >= Fb - 1:
            continue
        loc = tr["loc"]
        on_a = np.nonzero(loc[r_ + 1:, 1] <= BELT_Y + 1e-3)[0]
        if not len(on_a):
            continue
        m = r_ + 1 + int(on_a[0])  # first index on belt A
        ext = 0.5 * math.hypot(tr["dims"][0], tr["dims"][1])
        xm = loc[m][0]

        def clear(d):
            for (fs, xs, e2) in belt_a:  # scene frames, x positions, half size
                for j in range(6):
                    fr = m + d + j - off + 1
                    hit = np.nonzero(fs == fr)[0]
                    if len(hit) and abs(xs[hit[0]] - (xm + 1.5 * j / a.fps)) < ext + e2 + 0.15:
                        return False
            return True
        d = 0
        while d < 40 and not clear(d):
            d += 1
        if d:
            tail = loc[m:].copy()
            loc[m:m + d] = loc[m - 1]
            loc[m + d:] = tail[:len(loc) - m - d]
            tr["merge_wait_s"] = round(d / a.fps, 1)
        fs = np.arange(m, len(loc)) - off + 1
        belt_a.append((fs, loc[m:, 0].copy(), ext))


belt_a = []
picks, places = I.candidates()
rnd0 = random.Random(a.seed)
workers = []
STAFFED = [int(x) for x in a.stations.split(",")]
for k, (x0, av) in enumerate(zip(INDUCT_X, AVATARS)):
    if k not in STAFFED:
        continue
    TX = x0 + TDX
    RAIL_X = TX - TW / 2 - 0.02
    before_o, before_a = set(sc.objects), set(bpy.data.actions)
    bpy.ops.import_scene.fbx(filepath=str(Path(a.rb) / av / f"{av}.fbx"))
    new_o = [o for o in sc.objects if o not in before_o]
    arm = next(o for o in new_o if o.type == "ARMATURE")
    body = next(o for o in new_o if o.type == "MESH" and o.parent == arm)
    people._fix_materials(body, Path(a.rb) / av)
    for o in new_o:
        if o.animation_data:
            o.animation_data.action = None
    for act in [x for x in bpy.data.actions if x not in before_a]:
        bpy.data.actions.remove(act)
    arm.name = f"worker_induct_{k + 1}"
    try:
        vest = people._vest(body, arm)
        sc.collection.objects.link(vest)
        vest.material_slots[0].link = "OBJECT"
        vest.material_slots[0].material = people._vest_material(VESTS[k], people.VEST_COLOURS[VESTS[k]], False,
                                                                vest["front_is_low_y"])
    except Exception as e:  # noqa: BLE001
        print("vest failed", repr(e), flush=True)
    arm.location.x, arm.location.y = x0, OP_Y
    bpy.context.view_layer.update()
    # trunk clearance from this avatar's own body (rest pose, facing -y): furthest-forward torso vertex from the
    # Spine2 line, + the hi-vis vest (~3.5 cm) + 2 cm
    me_r = body.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    co_r = np.empty(len(me_r.vertices) * 3)
    me_r.vertices.foreach_get("co", co_r)
    co_r = co_r.reshape(-1, 3) @ np.array(body.matrix_world)[:3, :3].T + np.array(body.matrix_world)[:3, 3]
    body.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear()
    sp2 = arm.matrix_world @ arm.pose.bones["Bip01 Spine2"].head
    pel = arm.matrix_world @ arm.pose.bones["Bip01 Pelvis"].head
    band = (co_r[:, 2] > pel.z) & (co_r[:, 2] < sp2.z + 0.1) & (np.abs(co_r[:, 0] - sp2.x) < 0.2)
    trunk_clear = float(np.max(sp2.y - co_r[band, 1])) + 0.035 + 0.02
    print("trunk_clear", av, round(trunk_clear, 3), flush=True)
    rnd = random.Random(a.seed * 100 + k)
    # neighbours never start on the same take: rotate the pick pool per worker
    pk_k = picks[k % len(picks):] + picks[:k % len(picks)]
    rig = R.setup(arm, I.take(pk_k[0]["take"]))
    # palm offset from this avatar's own bind-pose finger curl: how far the little-finger tip sits on the palm side
    # of the palm point (the held fingers go to the bind pose), + 4 cm
    bi_, rh_, MRr = rig["bi"], rig["rhead"] * rig["scale"], rig["MR"]
    curl = 0.0
    for x_ in ("L", "R"):
        hd_ = bi_[f"Bip01 {x_} Hand"]
        n_loc = rig["AT"][hd_].T @ (MRr.T @ np.array([0.0, 0.0, -1.0]))
        n_rest = rig["rest"][hd_] @ n_loc
        palm = rh_[hd_] + 0.55 * (rh_[bi_[f"Bip01 {x_} Finger2"]] - rh_[hd_])
        f41, f42 = rh_[bi_[f"Bip01 {x_} Finger41"]], rh_[bi_[f"Bip01 {x_} Finger42"]]
        tip = f42 + (f42 - f41) * 0.9
        curl = max(curl, float(np.dot(tip - palm, n_rest)))
    palm_off = 0.04  # the fingers are un-curled into the palm plane while holding (inductor.build); curl kept for the log
    print("palm_off", av, round(palm_off, 3), "bind curl", round(curl, 3), flush=True)
    S_k, ind_boxes = INDUCT[k]
    st = dict(x=x0, belt_yaw=0.0, table_pt=(TX, STOP_Y + 0.12, TZ1 + 0.01),
              place_xy=tuple(S_k + IND_D * 0.22), induct_start=tuple(S_k), induct_dir=tuple(IND_D), induct_half_w=IND_HW,
              main_y=BELT_Y, clear_y=OP_Y - 0.10, grip_axis_yaw=-math.pi / 2, trunk_clear=trunk_clear, palm_off=palm_off,
              root_min_y=OP_Y - 0.13, refill_s=1.0 + (TY0 - TY1 - 0.15) / 0.4, divert_s=0.6,
              pick_root_max=(RAIL_X - max(0.26, trunk_clear - 0.035 + 0.06), 1e9), pick_grip_min_z=TZ1 + 0.045 + 0.05,
              table_align_x=RAIL_X + 0.02,
              surfaces=[(5.6, BELT_Y - BELT_HALF, 15.0, BELT_Y + BELT_HALF, BELT_TOP),
                        (TX - TW / 2, TY1 - 0.03, TX + TW / 2, TY0, TZ0)] + ind_boxes,
              place_x=(x0 - 0.4, x0 + 0.4), place_y_range=(BELT_Y - BELT_HALF + 0.05, BELT_Y + BELT_HALF - 0.05),
              belt_top=BELT_TOP, belt_speed=1.5, belt_dir=1.0, table_slope=SLOPE)
    off = rnd0.randrange(int(1.0 * a.fps), int(4.0 * a.fps))  # start offset 1-4 s: the first approach is off-screen
    Fb = F + off
    import copy
    # gap control: when upstream cartons pass this worker's spot (x0 +- 0.7 m + half the carton), in build time
    busy = []  # each operator has an own induct belt: no gap waiting by the people (the conveyor merges)
    segs = I.plan_cycles(rig, st, Fb, a.fps, rnd, pk_k, places, busy=busy)
    segs0 = copy.deepcopy(segs)
    # review 015 #3: mixed sizes (shoebox .. 45 cm), within a two-hand grip span; colours + labels at keying
    parcels = {n: dict(dims=(rnd.uniform(0.18, 0.40), rnd.uniform(0.14, 0.34), rnd.uniform(0.12, 0.30))) for n in range(80)}
    res = I.build(rig, segs, st, parcels, Fb, a.fps, frame0=1 - off, name=f"inductor@{av}#{k}")
    w = dict(k=k, x0=x0, TX=TX, av=av, arm=arm, body=body, rig=rig, st=st, off=off, segs=segs0, parcels=parcels,
             res=res, gap_waits=[sg_.get("gap_wait", 0.0) for sg_ in segs0 if sg_["kind"] == "place"])
    workers.append(w)
    floor_fix(w)
    merge_fix(w)

print("built", len(workers), flush=True)


sc.render.fps = int(a.fps)
sc.frame_start, sc.frame_end = 1, F


def table_z(y, h):
    return TZ1 + (y - TY1) * (TZ0 - TZ1) / (TY0 - TY1) + h / 2


# ---------------------------------------------------------------- cartons (index i of a worker's arrays = frame i + 1 - off)
for w in workers:
    res, off, TX, k = w["res"], w["off"], w["TX"], w["k"]
    lifts = {e["n"]: int(round(e["t"] * a.fps)) for e in res["events"] if e["kind"] == "lift"}
    w["pobs"] = {}
    for n, tr in res["tracks"].items():
        if tr["release"] < off - 30 or tr["grasp"] > F + off + 30:
            continue
        w_, d_, h_ = tr["dims"]
        crnd = random.Random(a.seed * 1000 + k * 100 + n)
        ob = box(f"m4_parcel_{k}_{n}", -w_ / 2, -d_ / 2, -h_ / 2, w_ / 2, d_ / 2, h_ / 2,
                 crnd.choices(CARTON_MATS, weights=(4, 3, 3, 1))[0], static=False)
        ob.rotation_mode = "ZYX"
        # shipping label: top (70 %) or a side face, a little off-centre, 1 mm proud
        lw, lh = min(0.10, w_ - 0.04), min(0.15, d_ - 0.04, h_ - 0.03)
        lme = bpy.data.meshes.new(f"m4_label_{k}_{n}")
        lbm = bmesh.new()
        if crnd.random() < 0.7:
            M_ = Matrix.Translation((crnd.uniform(-0.3, 0.3) * (w_ - lw) / 2, crnd.uniform(-0.3, 0.3) * (d_ - lh) / 2,
                                     h_ / 2 + 0.001)) @ Matrix.Diagonal((lw, lh, 1, 1))
        else:
            M_ = Matrix.Translation((0, d_ / 2 + 0.001, 0)) @ Matrix.Rotation(math.pi / 2, 4, "X") @ \
                Matrix.Diagonal((lw, min(lh, h_ - 0.03), 1, 1))
        bmesh.ops.create_grid(lbm, x_segments=1, y_segments=1, size=0.5, matrix=M_)
        lbm.to_mesh(lme)
        lbm.free()
        lme.materials.append(M_LABEL)
        lab = bpy.data.objects.new(f"m4_label_{k}_{n}", lme)
        sc.collection.objects.link(lab)
        lab.parent = ob
        ext_y = 0.5 * (abs(w_ * math.sin(tr["yaw"][0])) + abs(d_ * math.cos(tr["yaw"][0])))
        stop_c = tr["loc"][tr["grasp"]][1]
        q_c = TY0 - ext_y - 0.02
        t_in = (lifts[n - 1] + int(round(1.0 * a.fps))) if n - 1 in lifts else -10 ** 6  # divert 0.6 s after the lift, 0.4 s slide
        tdv = t_in - int(round(0.4 * a.fps))
        for f in range(1, F + 1):
            i = f - 1 + off
            loc = np.array(tr["loc"][i])
            if tr["state"][i] == "table":
                y = q_c if i < t_in else max(stop_c, q_c - 0.4 * (i - t_in) / a.fps)
                loc = np.array([loc[0], y, table_z(y, h_)])
                if i < t_in and t_in > -10 ** 5:
                    if i < tdv:
                        loc = np.array([loc[0] - 0.6 * (tdv - i) / a.fps, FEED_Y, 1.0 + h_ / 2])
                    else:
                        u_ = (i - tdv) / max(1, t_in - tdv)
                        loc = np.array([loc[0], FEED_Y + (q_c - FEED_Y) * u_,
                                        1.0 + h_ / 2 + (table_z(q_c, h_) - 1.0 - h_ / 2) * u_])
            ob.location = tuple(loc)
            ob.rotation_euler = (tr["pitch"][i], 0.0, tr["yaw"][i])
            vis = loc[0] >= 5.6 and (tr["state"][i] != "belt" or loc[0] < 15.0)
            ob.hide_render = not vis
            lab.hide_render = not vis
            lab.keyframe_insert("hide_render", frame=f)
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("rotation_euler", frame=f)
            ob.keyframe_insert("hide_render", frame=f)
        w["pobs"][n] = ob
        for fk, ang in ((tdv - 2, 0.0), (tdv, 45.0), (tdv + 3, 45.0), (tdv + 6, 0.0)):
            if 1 <= fk - off + 1 <= F:
                DIV[k].rotation_euler = (0, 0, math.radians(-ang))
                DIV[k].keyframe_insert("rotation_euler", frame=fk - off + 1)

# ---------------------------------------------------------------- QA (evaluated) per worker + spacing
for w in workers:
    vgn = {g_.index: g_.name for g_ in w["body"].vertex_groups}
    w["dom"] = np.array([vgn[max(v.groups, key=lambda g_: g_.weight).group] if len(v.groups) else "-"
                         for v in w["body"].data.vertices])
    w.update(ev=[], lows=[], pen={}, gaps=[], cos=[])
spacing = []
for f in range(1, F + 1):
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    for w in workers:
        ob = w["body"].evaluated_get(dg)
        me = ob.to_mesh()
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        M = np.array(ob.matrix_world)
        co = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
        ob.to_mesh_clear()
        w["cos"] = co
        w["lows"].append(co[:, 2].min())
        bi = w["rig"]["bi"]
        Ma = w["arm"].matrix_world
        w["ev"].append([tuple(Ma @ w["arm"].pose.bones[n].head) for n in bi])
        hits = []
        for nm, (lo, hi) in statics.items():
            ins = np.all((co > lo) & (co < hi), axis=1)
            if ins.any():
                dd = np.minimum(co[ins] - lo, hi - co[ins]).min(1)
                hits.append((nm, float(dd.max()), str(w["dom"][ins][int(np.argmax(dd))])))
        for w2 in workers:
            for n, pob in w2["pobs"].items():
                if pob.hide_render:
                    continue
                Mi = np.array(pob.matrix_world.inverted())
                loc = co @ Mi[:3, :3].T + Mi[:3, 3]
                hb = np.array(w2["res"]["tracks"][n]["dims"]) / 2
                ins = np.all(np.abs(loc) < hb, axis=1)
                if ins.any():
                    dd = (hb - np.abs(loc[ins])).min(1)
                    hits.append((pob.name, float(dd.max()), str(w["dom"][ins][int(np.argmax(dd))])))
        for nm, dep, part in hits:
            if dep > 0.01:
                w["pen"].setdefault(nm, []).append((f, round(dep * 1000), part.replace("Bip01 ", "")))
    for w1, w2 in zip(workers, workers[1:]):  # neighbours: closest body points (every 7th vertex)
        kd = KDTree(len(w2["cos"][::7]))
        for i_, c_ in enumerate(w2["cos"][::7]):
            kd.insert(c_, i_)
        kd.balance()
        spacing.append((f, w1["k"], w2["k"], min(kd.find(c_)[2] for c_ in w1["cos"][::7])))

out = dict(frames=F, fps=a.fps, workers=[], spacing_min_m=round(min((s[3] for s in spacing), default=99.0), 3),
           spacing_frames_under_0p3=sum(1 for s in spacing if s[3] < 0.3))
for w in workers:
    res, off, bi = w["res"], w["off"], w["rig"]["bi"]
    ev = np.array(w["ev"])
    src = res["src"][off:off + F]
    J = res["J"]
    sk = []
    for sd, sj in (("L", "LeftAnkle"), ("R", "RightAnkle")):
        tp = ev[:, bi[f"Bip01 {sd} Foot"], :2]
        for i, j in R.contacts(src[:, J[sj]], a.fps):
            sk.append(float(np.max(np.linalg.norm(tp[i:j + 1] - tp[i], axis=1))))
    gr = sorted(tr["grasp"] - off for tr in res["tracks"].values() if 0 <= tr["grasp"] - off < F)
    hl = ev[:, bi["Bip01 L Thigh"]] - ev[:, bi["Bip01 R Thigh"]]
    head = np.unwrap(np.arctan2(hl[:, 1], hl[:, 0]))
    yaw_hold = [round(math.degrees(float(np.ptp(head[max(0, tr["grasp"] - off):tr["release"] - off + 1]))), 1)
                for tr in res["tracks"].values() if 0 <= tr["grasp"] - off and tr["release"] - off < F]
    first_take = next(s["clip"]["take"] for s in w["segs"] if s["kind"] == "pick")
    out["workers"].append(dict(
        k=w["k"] + 1, avatar=w["av"], x=w["x0"], start_offset_s=round(off / a.fps, 1), first_pick_take=first_take,
        cycles=len(gr), cycle_s=[round(float(c), 2) for c in np.diff(gr) / a.fps],
        foot_skate_max_mm=round(max(sk) * 1000, 1) if sk else None,
        ground_pen_frames=int((np.array(w["lows"]) < -0.0005).sum()),
        yaw_while_holding_deg=yaw_hold,
        frames_over_1cm={nm: len(v) for nm, v in w["pen"].items()},
        worst_over_1cm={nm: max(v, key=lambda e: e[1]) for nm, v in w["pen"].items()},
        gap_waits_s=w["gap_waits"],
        trunk_clear_m=round(w["st"]["trunk_clear"], 3),
        lean_deg_max=round(res["sol"].get("lean_deg_max", 0.0), 1),
        unstoop_deg_max=round(res["sol"].get("unstoop_deg_max", 0.0), 1)))
grasps = [[tr["grasp"] - w["off"] for tr in w["res"]["tracks"].values()] for w in workers]
out["grasp_frames_per_worker"] = [[g for g in gl if 0 <= g < F] for gl in grasps]
out["release_frames_per_worker"] = [[tr["release"] - w["off"] + 1 for tr in w["res"]["tracks"].values()
                                     if 0 <= tr["release"] - w["off"] < F] for w in workers]
out["detail_over_1cm"] = {w["k"] + 1: w["pen"] for w in workers}
out["carton_events"] = {w["k"] + 1: {n: (tr["grasp"] - w["off"] + 1, tr["release"] - w["off"] + 1)
                                     for n, tr in w["res"]["tracks"].items()} for w in workers}
print("M4 QA", json.dumps(out), flush=True)
(OUT / "m4_qa.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "m4_line_a.blend"))

if a.render:
    sc.render.image_settings.file_format = "PNG"
    (OUT / "frames").mkdir(exist_ok=True)
    for tag, cam_name, res_ in (("cctv", "CAM_01", (2688, 1520, 50)), ("front", None, (1280, 640, 100))):
        if cam_name:
            cam = sc.objects[cam_name]
        else:
            cd = bpy.data.cameras.new("m4_front")
            cd.lens = 24
            cam = bpy.data.objects.new("m4_front", cd)
            sc.collection.objects.link(cam)
            cam.location = (9.4, 6.4, 2.4)
            cam.rotation_euler = (Vector((9.4, 10.4, 0.9)) - Vector(cam.location)).to_track_quat("-Z", "Y").to_euler()
        sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = res_
        sc.camera = cam
        sc.render.filepath = str(OUT / "frames" / f"{tag}_####")
        bpy.ops.render.render(animation=True)
    print("M4 rendered", flush=True)
