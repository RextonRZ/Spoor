"""M4 part 2 (014_GO): the dock unloader on the same mocap engine (D05, the worker south of the telescopic boom).

The dock is line A turned 180 deg: facing the carton wall in the lorry he picks (wall = the "table" at his
front-left), turns right ~90 deg and sets the carton on the boom nose in front of him (the boom = the "belt", running
out of the lorry). Everything is built in that local frame under a parent empty, then the empty is put on the dock
(rotation 180 deg about z, origin at the worker): all engine conventions stay valid.

  blender -b --factory-startup -P assets/hub/mocap/m4_dock.py -- --out qa/review/m4_dock [--seconds 30] [--render]

Wall: loose-loaded columns 0.12 m apart (room for a hand) on his side of the boom, worked top-down; tiers 1.75 m
down to 0.45 m; the pick clip per carton comes from the AndyData pool nearest its grip height (crouch picks 0.67-0.69 m,
bent picks 0.77-0.86 m, standing picks ~0.97 m; higher cartons by IK + un-stoop).
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
ap.add_argument("--seconds", type=float, default=30.0)
ap.add_argument("--fps", type=float, default=10.0)
ap.add_argument("--seed", type=int, default=5)
ap.add_argument("--avatar", default="Male_Adult_12")
ap.add_argument("--render", action="store_true")
ap.add_argument("--rb", default=str(HERE.parent / "build" / "third_party" / "rocketbox"))
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
OUT = Path(a.out).resolve()
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(HERE.parent / "build" / "hub_dressed_lit.blend"))
sc = bpy.context.scene
for o in list(sc.objects):
    if o.name.startswith(("flow_parcel_", "worker_")):
        bpy.data.objects.remove(o, do_unlink=True)
F = int(a.seconds * a.fps)
ORIGIN = Vector((-1.25, 22.5, 0.0))  # the worker, south of boom_D05 (world); local frame = world turned 180 deg
BOOM = dict(x0=-2.65, x1=0.0, y0=-0.75, y1=-0.25, top=1.0)  # local; runs -x (out of the lorry)
WALL_X = 0.35  # wall face (local x)
COLS = [0.02, 0.40]  # column centres (local y), 12 cm gaps (0.46 puts the outer column against the trailer wall)
statics = {"boom": (np.array([BOOM["x0"], BOOM["y0"], 0.80]), np.array([BOOM["x1"], BOOM["y1"], BOOM["top"]]))}


def mat(name, rgb):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1)
    return m


CARTON_MATS = [mat("dk_carton", (0.55, 0.4, 0.22)), mat("dk_carton_dark", (0.42, 0.29, 0.15)),
               mat("dk_carton_kraft", (0.62, 0.48, 0.30)), mat("dk_carton_white", (0.78, 0.78, 0.76))]
M_LABEL = mat("dk_label", (0.9, 0.9, 0.88))
ROOT = bpy.data.objects.new("dock_mocap_root", None)  # identity while building; put on the dock at the end
sc.collection.objects.link(ROOT)


def box(name, c, dims, m, static=True):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Diagonal((*dims, 1)))
    bm.to_mesh(me)
    bm.free()
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    ob.location = c
    ob.parent = ROOT
    if static:
        statics[name] = (np.array(c) - np.array(dims) / 2, np.array(c) + np.array(dims) / 2)
    return ob


def label(ob, dims, crnd):
    w_, d_, h_ = dims
    lme = bpy.data.meshes.new(ob.name + "_label")
    lbm = bmesh.new()
    lw, lh = min(0.10, w_ - 0.04), min(0.15, d_ - 0.04)
    bmesh.ops.create_grid(lbm, x_segments=1, y_segments=1, size=0.5, matrix=Matrix.Translation(
        (crnd.uniform(-0.3, 0.3) * (w_ - lw) / 2, crnd.uniform(-0.3, 0.3) * (d_ - lh) / 2, h_ / 2 + 0.001))
        @ Matrix.Diagonal((lw, lh, 1, 1)))
    lbm.to_mesh(lme)
    lbm.free()
    lme.materials.append(M_LABEL)
    lab = bpy.data.objects.new(ob.name + "_label", lme)
    sc.collection.objects.link(lab)
    lab.parent = ob
    return lab


# ---------------------------------------------------------------- the wall: columns (picked top-down) + rows behind
rnd = random.Random(a.seed)
wall = []  # (column, tier, centre, dims)
for ci, cy_ in enumerate(COLS):
    z = 0.0
    tier = 0
    while z < 1.55:
        w_, d_, h_ = rnd.uniform(0.26, 0.32), rnd.uniform(0.26, 0.36), rnd.uniform(0.24, 0.36)
        if z + h_ > 1.8:
            break
        wall.append(dict(col=ci, tier=tier, c=np.array([WALL_X + d_ / 2, cy_, z + h_ / 2]), dims=(w_, d_, h_)))
        # (w_ runs along local y, d_ into the lorry along local x)
        z += h_ + 0.002
        tier += 1
# behind: two more rows of plain cartons up to ~1.75 m (never picked in 30 s)
for row in range(2):
    for ci, cy_ in enumerate(COLS + [-0.38]):
        z = 0.0
        while z < 1.5:
            h_ = rnd.uniform(0.26, 0.36)
            box(f"dk_back_{row}_{ci}_{z:.2f}", (WALL_X + 0.42 + row * 0.38, cy_, z + h_ / 2), (0.30, 0.34, h_),
                CARTON_MATS[rnd.randrange(4)])
            z += h_ + 0.002
# pick order: top-down, alternating columns
order = sorted(wall, key=lambda c: (-c["c"][2] - c["dims"][2] / 2, c["col"]))

# ---------------------------------------------------------------- the worker
before_o, before_a = set(sc.objects), set(bpy.data.actions)
bpy.ops.import_scene.fbx(filepath=str(Path(a.rb) / a.avatar / f"{a.avatar}.fbx"))
new_o = [o for o in sc.objects if o not in before_o]
arm = next(o for o in new_o if o.type == "ARMATURE")
body = next(o for o in new_o if o.type == "MESH" and o.parent == arm)
people._fix_materials(body, Path(a.rb) / a.avatar)
for o in new_o:
    if o.animation_data:
        o.animation_data.action = None
for act in [x for x in bpy.data.actions if x not in before_a]:
    bpy.data.actions.remove(act)
arm.name = "worker_dock_D05_s"
vest = people._vest(body, arm)
sc.collection.objects.link(vest)
vest.material_slots[0].link = "OBJECT"
vest.material_slots[0].material = people._vest_material("orange", people.VEST_COLOURS["orange"], False,
                                                        vest["front_is_low_y"])
arm.location.x, arm.location.y = 0.0, 0.0
bpy.context.view_layer.update()
me_r = body.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
co_r = np.empty(len(me_r.vertices) * 3)
me_r.vertices.foreach_get("co", co_r)
co_r = co_r.reshape(-1, 3) @ np.array(body.matrix_world)[:3, :3].T + np.array(body.matrix_world)[:3, 3]
sp2 = arm.matrix_world @ arm.pose.bones["Bip01 Spine2"].head
pel = arm.matrix_world @ arm.pose.bones["Bip01 Pelvis"].head
band = (co_r[:, 2] > pel.z) & (co_r[:, 2] < sp2.z + 0.1) & (np.abs(co_r[:, 0] - sp2.x) < 0.2)
trunk_clear = float(np.max(sp2.y - co_r[band, 1])) + 0.055

picks, places = I.candidates(min_pick_h=0.6, max_pick_dur=2.3)
rig = R.setup(arm, I.take(picks[0]["take"]))
parcels = {n: dict(dims=c["dims"]) for n, c in enumerate(order)}
pick_pts = {n: (c["c"][0], c["c"][1], c["c"][2] - c["dims"][2] / 2) for n, c in enumerate(order)}


def pool_for(k):
    """Pick clips nearest this carton's grip height (source hands, scaled ~0.84)."""
    if k >= len(order):
        return picks
    gz = order[k]["c"][2] + order[k]["dims"][2] / 2 - 0.055
    ranked = sorted(picks, key=lambda p_: abs(p_["hand_height_m"] * 0.84 - min(gz, 0.95)))
    best = abs(ranked[0]["hand_height_m"] * 0.84 - min(gz, 0.95))
    return [p_ for p_ in ranked if abs(p_["hand_height_m"] * 0.84 - min(gz, 0.95)) < best + 0.08]


st = dict(x=0.0, belt_yaw=0.0, table_pt=tuple(pick_pts[0]), pick_pts=pick_pts,
          place_xy=(-0.35, -0.5), clear_y=-0.06, root_min_y=-0.08, grip_axis_yaw=-math.pi / 2, trunk_clear=trunk_clear,
          pick_root_max=(WALL_X - max(0.34, trunk_clear - 0.035 + 0.10), 1e9), pick_grip_min_z=0.0, ratio=(0.85, 0.95),
          surfaces=[(BOOM["x0"], BOOM["y0"], BOOM["x1"], BOOM["y1"], BOOM["top"])],
          place_x=(-0.75, -0.15), place_y_range=(BOOM["y0"] + 0.03, BOOM["y1"] - 0.03), belt_top=BOOM["top"],
          belt_speed=0.8, belt_dir=-1.0, table_slope=0.0, lift_rule=False, grip_axis_strict=True, elbow_out=0.3,
          elbow_down=0.3, lean_at_pick=False, flex_cap_pick=45.0)
# lower cartons: stand further back (a crouch puts the knees forward), up to +0.25 m at floor height
st["pick_root_max_n"] = {n: (st["pick_root_max"][0] - 0.25 * max(0.0, 1.0 - (pick_pts[n][2] + order[n]["dims"][2]) / 1.2),
                             1e9) for n in pick_pts}
off = int(1.5 * a.fps)
import copy  # noqa: E402

segs = I.plan_cycles(rig, st, F + off, a.fps, random.Random(a.seed + 1), picks, places, pick_pool=pool_for)
segs0 = copy.deepcopy(segs)
res = I.build(rig, segs, st, parcels, F + off, a.fps, frame0=1 - off, name=f"dock@{a.avatar}")
low = 1e9
for f in range(1, F + 1):
    sc.frame_set(f)
    ob_ = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me_ = ob_.to_mesh()
    co_ = np.empty(len(me_.vertices) * 3)
    me_.vertices.foreach_get("co", co_)
    M_ = np.array(ob_.matrix_world)
    low = min(low, float((co_.reshape(-1, 3) @ M_[:3, :3].T + M_[:3, 3])[:, 2].min()))
    ob_.to_mesh_clear()
st["lift"] = -low
bpy.data.actions.remove(res["action"])
res = I.build(rig, copy.deepcopy(segs0), st, parcels, F + off, a.fps, frame0=1 - off, name=f"dock@{a.avatar}")
sc.render.fps = int(a.fps)
sc.frame_start, sc.frame_end = 1, F

# ---------------------------------------------------------------- wall cartons: static until picked, then tracked
pobs = {}
for n, c in enumerate(order):
    tr = res["tracks"].get(n)
    crnd = random.Random(a.seed * 77 + n)
    # w (across the hands) runs along the wall (local y), d into the lorry (local x): the picked carton's own frame
    # is yawed -90 deg (grip across local y), so its mesh is w x d x h and the static ones are laid out to match
    if tr is None:
        ob = box(f"dk_wall_{n}", tuple(c["c"]), (c["dims"][1], c["dims"][0], c["dims"][2]), CARTON_MATS[crnd.randrange(4)])
    else:
        ob = box(f"dk_wall_{n}", (0, 0, 0), c["dims"], CARTON_MATS[crnd.randrange(4)], static=False)
    lab = label(ob, c["dims"], crnd)
    if tr is None:
        continue
    ob.rotation_mode = "ZYX"
    for f in range(1, F + 1):
        i = f - 1 + off
        ob.location = tuple(tr["loc"][i]) if tr["state"][i] != "table" else tuple(c["c"])
        ob.rotation_euler = (0.0, 0.0, tr["yaw"][i])
        vis = not (tr["state"][i] == "belt" and tr["loc"][i][0] < -2.6)
        ob.hide_render = lab.hide_render = not vis
        ob.keyframe_insert("location", frame=f)
        ob.keyframe_insert("rotation_euler", frame=f)
        ob.keyframe_insert("hide_render", frame=f)
        lab.keyframe_insert("hide_render", frame=f)
    pobs[n] = (ob, tr)
arm.parent = ROOT
vest.parent = arm

# ---------------------------------------------------------------- QA (local frame: ROOT still at identity)
bi = rig["bi"]
vgn = {g_.index: g_.name for g_ in body.vertex_groups}
dom = np.array([vgn[max(v.groups, key=lambda g_: g_.weight).group] if len(v.groups) else "-" for v in body.data.vertices])
pen, lows, ev = {}, [], []
for f in range(1, F + 1):
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    ob_ = body.evaluated_get(dg)
    me_ = ob_.to_mesh()
    co = np.empty(len(me_.vertices) * 3)
    me_.vertices.foreach_get("co", co)
    M_ = np.array(ob_.matrix_world)
    co = co.reshape(-1, 3) @ M_[:3, :3].T + M_[:3, 3]
    ob_.to_mesh_clear()
    lows.append(co[:, 2].min())
    ev.append([tuple(arm.matrix_world @ arm.pose.bones[n_].head) for n_ in bi])
    for nm, (lo, hi) in statics.items():
        ins = np.all((co > lo) & (co < hi), axis=1)
        if ins.any():
            dd = np.minimum(co[ins] - lo, hi - co[ins]).min(1)
            if dd.max() > 0.01:
                pen.setdefault(nm, []).append((f, round(float(dd.max()) * 1000), str(dom[ins][int(np.argmax(dd))])))
    for n, (pob, tr) in pobs.items():
        Mi = np.array(pob.matrix_world.inverted())
        loc = co @ Mi[:3, :3].T + Mi[:3, 3]
        hb = np.array(tr["dims"]) / 2
        ins = np.all(np.abs(loc) < hb, axis=1)
        if ins.any():
            dd = (hb - np.abs(loc[ins])).min(1)
            if dd.max() > 0.01:
                pen.setdefault(pob.name, []).append((f, round(float(dd.max()) * 1000), str(dom[ins][int(np.argmax(dd))])))
ev = np.array(ev)
src = res["src"][off:off + F]
sk = []
for sd, sj in (("L", "LeftAnkle"), ("R", "RightAnkle")):
    tp = ev[:, bi[f"Bip01 {sd} Foot"], :2]
    for i, j in R.contacts(src[:, res["J"][sj]], a.fps):
        sk.append(float(np.max(np.linalg.norm(tp[i:j + 1] - tp[i], axis=1))))
evs = {n: (tr["grasp"] - off + 1, tr["release"] - off + 1) for n, tr in res["tracks"].items()}
out = dict(avatar=a.avatar, frames=F, cartons=evs, pick_heights_m={n: round(float(pick_pts[n][2] + order[n]["dims"][2]), 2)
                                                                     for n in evs},
           clips=[(s_["kind"], s_["clip"]["take"][12:16], round(s_["clip"]["hand_height_m"], 2), s_["clip"]["mirror"])
                  for s_ in segs0 if s_["kind"] != "hold"][:16],
           foot_skate_max_mm=round(max(sk) * 1000, 1) if sk else None, ground_pen_frames=int((np.array(lows) < -0.0005).sum()),
           frames_over_1cm={k: len(v) for k, v in pen.items()}, detail_over_1cm=pen,
           lean_deg_max=round(res["sol"].get("lean_deg_max", 0.0), 1),
           unstoop_deg_max=round(res["sol"].get("unstoop_deg_max", 0.0), 1), trunk_clear_m=round(trunk_clear, 3))
print("DOCK QA", json.dumps(out)[:3000], flush=True)
(OUT / "m4_dock_qa.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

# ---------------------------------------------------------------- onto the dock: 180 deg about z at the worker
ROOT.location = ORIGIN
ROOT.rotation_euler = (0, 0, math.pi)
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "m4_dock.blend"))
if a.render:
    sc.render.image_settings.file_format = "PNG"
    (OUT / "frames").mkdir(exist_ok=True)
    cams = [("cctv", "CAM_02", (2688, 1520, 50))]
    for tag, pos in (("door", (-0.25, 23.85, 1.95)), ("behind", (-0.3, 22.0, 2.1))):  # inside the trailer, by the door
        cd = bpy.data.cameras.new(f"dk_{tag}")
        cd.lens = 22
        cd.clip_start = 0.05
        cam = bpy.data.objects.new(f"dk_{tag}", cd)
        sc.collection.objects.link(cam)
        cam.location = pos
        cam.rotation_euler = (Vector((-1.6, 22.5, 1.0)) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
        cams.append((tag, f"dk_{tag}", (640, 640, 100)))
    for tag, cname, rs in cams:
        sc.camera = sc.objects[cname]
        sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rs
        sc.render.filepath = str(OUT / "frames" / f"{tag}_####")
        bpy.ops.render.render(animation=True)
    print("DOCK rendered", flush=True)
