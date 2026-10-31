"""QA pass: automatic per-frame checks of every worker in the dressed hub (no fixes, report only).

  blender -b --factory-startup assets/hub/build/hub_dressed.blend -P assets/hub/qa_checks.py

Writes assets/hub/build/qa/:
  auto_flags.csv   worker_name, role, clip_name, frame_start, frame_end, check, severity, detail
  summary.txt      flags per worker / check / severity
  timeline.json    per worker, the clip playing at each frame 1-300 (used by qa_render.py for burn-in)
  visibility.json  per worker, the cameras that see it (frustum, <= 40 m, unoccluded line of sight)

Frames 1-300 = the planned 30 s scenario at 10 fps. Distances in metres, world space.
"""

import csv
import json
import math
import os
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

HUB = Path(bpy.path.abspath("//")).resolve().parent
QA = Path(os.environ["QA_OUT"]) if os.environ.get("QA_OUT") else HUB / "build" / "qa"  # QA_OUT: parallel runs
QA.mkdir(parents=True, exist_ok=True)
SPEC = json.loads((HUB / "hub_spec.json").read_text(encoding="utf-8"))
WORKERS_JSON = json.loads((HUB / "build" / "truth" / "workers.json").read_text(encoding="utf-8"))
ROLE = {w["name"]: w["role"] for w in WORKERS_JSON["workers"]}
for _pre, _role in (("worker_dock_", "dock"), ("worker_induct_", "induction"), ("worker_cage_", "cages"),
                    ("worker_bag_", "chutes"), ("worker_walk_", "walk")):  # station workers (stations.py, flow stage)
    for _o in bpy.data.objects:
        if _o.type == "ARMATURE" and _o.name.startswith(_pre):
            ROLE.setdefault(_o.name, _role)
F0, F1, PLAN_FPS = 1, int(os.environ.get("QA_F1", "300")), 10  # QA_F1: a longer scenario window (S2: 900)
SAMPLE = 4  # every 4th body vertex for clipping tests

sc = bpy.context.scene
t_start = time.time()
RIGS = sorted([o for o in sc.objects if o.type == "ARMATURE" and o.name.startswith("worker_")], key=lambda o: o.name)
CAMS = sorted([o for o in sc.objects if o.type == "CAMERA" and o.name.startswith("CAM_")], key=lambda o: o.name)
HELD = ("_phone", "_terminal", "_clipboard", "_carton", "_scanner", "_cage")
FLOOR_EXCL = {"floor_slab", "ground", "yard_north", "yard_west", "roof", "roof_lights", "roof_services",
              "highbay_fixtures", "cctv_housings", "wall_base_grime"}
IDLE_CLIPS = {"breathing_idle", "idle_neutral_01", "idle_neutral_02", "idle_look_around_01", "talking",
              "gestic_talk_neutral_01", "texting_while_standing", "talking_on_phone", "talking_phone_pacing",
              "talking_when_sit", "walking_while_texting"}
IDLE_ROLES = {"idle", "break", "supervisor", "to_break"}
SEATED = {"worker_mx_12_exception", "worker_mx_13_break"}

BONES = {
    "rb": dict(hand_R="Bip01 R Hand", hand_L="Bip01 L Hand", toe_R="Bip01 R Toe0", toe_L="Bip01 L Toe0",
               sh_R="Bip01 R UpperArm", sh_L="Bip01 L UpperArm", chest="Bip01 Spine2", head="Bip01 Head",
               pelvis="Bip01 Pelvis",
               pose=["Bip01 Pelvis", "Bip01 Spine1", "Bip01 Spine2", "Bip01 Neck", "Bip01 Head", "Bip01 L UpperArm",
                     "Bip01 R UpperArm", "Bip01 L Forearm", "Bip01 R Forearm", "Bip01 L Thigh", "Bip01 R Thigh",
                     "Bip01 L Calf", "Bip01 R Calf"]),
    "mx": dict(hand_R="mixamorig:RightHand", hand_L="mixamorig:LeftHand", toe_R="mixamorig:RightToeBase",
               toe_L="mixamorig:LeftToeBase", sh_R="mixamorig:RightArm", sh_L="mixamorig:LeftArm",
               chest="mixamorig:Spine2", head="mixamorig:Head", pelvis="mixamorig:Hips",
               pose=["mixamorig:Hips", "mixamorig:Spine1", "mixamorig:Spine2", "mixamorig:Neck", "mixamorig:Head",
                     "mixamorig:LeftArm", "mixamorig:RightArm", "mixamorig:LeftForeArm", "mixamorig:RightForeArm",
                     "mixamorig:LeftUpLeg", "mixamorig:RightUpLeg", "mixamorig:LeftLeg", "mixamorig:RightLeg"]),
}


def log(*a):
    print("QA", f"{time.time() - t_start:7.1f}s", *a, flush=True)


# ------------------------------------------------------------------------------------------------ worker setup
def side_of(name):
    if " R " in name or "Right" in name:
        return "R"
    if " L " in name or "Left" in name:
        return "L"
    return ""


class W:
    pass


workers = []
for rig in RIGS:
    w = W()
    w.rig, w.name = rig, rig.name
    w.kind = "mx" if rig.name.startswith("worker_mx") else "rb"
    w.B = BONES[w.kind]
    w.role = ROLE.get(rig.name, "?")
    w.body = next(c for c in rig.children if c.name.endswith("_body"))
    w.held = [c for c in rig.children_recursive if c.type == "MESH" and c.name.endswith(HELD)]
    w.own = {rig.name} | {c.name for c in rig.children_recursive}
    me = w.body.data
    gname = {g.index: g.name for g in w.body.vertex_groups}
    n = len(me.vertices)
    cat = np.zeros(n, dtype=np.int8)  # 0 body, 1 hand, 2 forearm, 3 foot
    side = np.zeros(n, dtype=np.int8)  # 0 none, 1 R, 2 L
    for v in me.vertices:
        if not v.groups:
            continue
        g = max(v.groups, key=lambda g: g.weight)
        nm = gname.get(g.group, "")
        if "Hand" in nm or "Finger" in nm:
            cat[v.index] = 1
        elif "Forearm" in nm or "ForeArm" in nm:
            cat[v.index] = 2
        elif "Foot" in nm or "Toe" in nm:
            cat[v.index] = 3
        sd = side_of(nm)
        side[v.index] = 1 if sd == "R" else 2 if sd == "L" else 0
    w.cat, w.side, w.n = cat, side, n
    w.sample = np.arange(0, n, SAMPLE)
    me.calc_loop_triangles()
    tri = np.empty(len(me.loop_triangles) * 3, dtype=np.int32)
    me.loop_triangles.foreach_get("vertices", tri)
    w.tris = tri.reshape(-1, 3).tolist()
    w.flags = []  # (frame, check, severity, key, value, detail)
    workers.append(w)
WBY = {w.name: w for w in workers}
log("workers", len(workers))


def active_clip(rig, f):
    """Clip playing at frame f: the top unmuted NLA strip covering f (the 'grip' hand layer ignored)."""
    ad = rig.animation_data
    best = None
    if ad:
        for tr in ad.nla_tracks:
            if tr.mute or tr.name == "grip":
                continue
            for st in tr.strips:
                if not st.mute and st.frame_start <= f < st.frame_end and st.action:
                    best = st
    if best is None:
        return "?", None
    nm = best.action.name.split("@")[0]
    for pre in ("clip_m_", "clip_f_", "clip_", "mx_"):
        if nm.startswith(pre):
            nm = nm[len(pre):]
            break
    a0, a1 = best.action_frame_start, best.action_frame_end
    span = max(a1 - a0, 1)
    phase = ((f - best.frame_start) / best.scale) % span
    return nm, (best, phase)


# ------------------------------------------------------------------------------------------------ static geometry
dg = bpy.context.evaluated_depsgraph_get()
sc.frame_set(F0)


def is_static(o):
    if o.type != "MESH" or o.hide_render or not o.visible_get():
        return False
    nm = o.name.split(".")[0]
    if nm in FLOOR_EXCL or nm.startswith(("floor_", "yard_", "carrier_", "decal")):
        return False
    if o.name.startswith("worker_"):  # their stools / HMIs / dock boxes are static; held props are not
        return o.parent is None
    p = o
    while p is not None:  # animated things (flow parcels, rolling cages, swapped bags) are not static geometry:
        ad = p.animation_data  # a frame-1 snapshot of them only produced false "inside" flags
        if ad and (ad.action or len(ad.nla_tracks)):
            return False
        if p is not o and p.type == "ARMATURE" and p.name.startswith("worker_"):
            return False
        p = p.parent
    return True


STATIC = [o for o in sc.objects if is_static(o)]


def _animated(o):
    p_ = o
    while p_ is not None:
        ad = p_.animation_data
        if ad and (ad.action or len(ad.nla_tracks)):
            return True
        p_ = p_.parent
    return False


# moving objects a head can run into (flow parcels, carried sacks): checked as boxes (their local bounds) against a
# head sphere (review 006 P0 #1: cartons carried through the head; flow parcels are not rig children)
ANIM_SMALL = [o for o in sc.objects if o.type == "MESH" and not o.name.startswith("worker_") and "cage" not in o.name
              and _animated(o) and max(o.dimensions) < 1.2]
PARCELS = [o for o in sc.objects if o.type == "MESH" and o.name.startswith("flow_parcel_")]
PARCEL_FLAGS = []
tri_xyz, tri_obj, obj_names = [], [], []
for oi, o in enumerate(STATIC):
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    nv = len(me.vertices)
    if nv == 0 or len(me.loop_triangles) == 0:
        ev.to_mesh_clear()
        continue
    co = np.empty(nv * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    M = np.array(ev.matrix_world)
    co = co @ M[:3, :3].T + M[:3, 3]
    tri = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", tri)
    tri_xyz.append(co[tri.reshape(-1, 3)])
    tri_obj.append(np.full(len(tri) // 3, len(obj_names)))
    obj_names.append(o.name)
    ev.to_mesh_clear()
TRI = np.concatenate(tri_xyz)
TOBJ = np.concatenate(tri_obj)
TCEN = TRI.mean(axis=1)
log("static triangles", len(TRI), "objects", len(obj_names))

# rig root track (also identifies movers)
ROOT = {w.name: [] for w in workers}
for f in range(F0, F1 + 1, 5):
    sc.frame_set(f)
    for w in workers:
        ROOT[w.name].append(w.rig.matrix_world.translation.copy())
for w in workers:
    pts = ROOT[w.name]
    xs, ys = [p.x for p in pts], [p.y for p in pts]
    w.mover = (max(xs) - min(xs)) + (max(ys) - min(ys)) > 0.15
    lo, hi = np.array([min(xs) - 1.2, min(ys) - 1.2, -0.05]), np.array([max(xs) + 1.2, max(ys) + 1.2, 2.6])
    sel = np.all((TRI.max(axis=1) >= lo) & (TRI.min(axis=1) <= hi), axis=1)
    idx = np.nonzero(sel)[0]
    w.st_obj = TOBJ[idx]
    verts = TRI[idx].reshape(-1, 3).tolist()
    w.bvh = BVHTree.FromPolygons(verts, [(3 * k, 3 * k + 1, 3 * k + 2) for k in range(len(idx))]) if len(idx) else None
log("per-worker static BVHs built")

CAGES = [o for o in sc.objects if o.type == "MESH" and o.data.name.startswith("roll_cage")
         and not o.data.name.endswith("gate") and o.visible_get()]
lane = SPEC["circulation"]["forklift_lane"]
LANE = []
for (ax, ay), (bx, by) in zip(lane["centreline_m"], lane["centreline_m"][1:]):
    hw = lane["width_m"] / 2
    LANE.append((min(ax, bx) - hw, min(ay, by) - hw, max(ax, bx) + hw, max(ay, by) + hw))
WALK = [w_["rect_m"] for w_ in SPEC["circulation"]["walkways"]]
ZEBRA = [z["rect_m"] for z in SPEC["circulation"]["zebra_crossings"]]


def in_rects(x, y, rects, pad=0.0):
    return any(r[0] - pad <= x <= r[2] + pad and r[1] - pad <= y <= r[3] + pad for r in rects)


RES_X, RES_Y = 2688, 1520


def frustum(cam, p):
    inv = cam.matrix_world.inverted()
    q = inv @ p
    if q.z > -0.1:
        return False
    tx = math.tan(cam.data.angle_x / 2)
    ty = tx * RES_Y / RES_X
    return abs(q.x / -q.z) <= tx and abs(q.y / -q.z) <= ty


def line_clear(a, b, own):
    """True if nothing but the worker's own objects lies between a and b."""
    d = b - a
    L = d.length
    if L < 1e-6:
        return True
    hit, loc, nrm, idx, ob, _ = sc.ray_cast(bpy.context.evaluated_depsgraph_get(), a, d / L, distance=L - 0.05)
    return (not hit) or ob.name in own or ob.name.split(".")[0] in own


def add_range(w, fa, fb, chk, sev, key, val, det):
    for ff in range(max(F0, int(fa)), min(F1, int(fb)) + 1):
        w.flags.append((ff, chk, sev, key, val, det))


# ------------------------------------------------------------------------------------------------ per-frame checks
POSE = {w.name: [] for w in workers}
CLIP = {w.name: [] for w in workers}
PHASE = {w.name: [] for w in workers}
TOE = {w.name: [] for w in workers}
FOOTZ = {w.name: [] for w in workers}
TORSO = {w.name: [] for w in workers}
POS = {w.name: [] for w in workers}
VIS = defaultdict(set)
FACING = defaultdict(list)  # (worker, cam) -> frames facing
IDLE_IN_VIEW = defaultdict(list)  # (cam, frame) -> idle workers visible
HELD_REL = {}


def bone_world(w, key):
    pb = w.rig.pose.bones.get(w.B[key])
    return w.rig.matrix_world @ pb.head if pb else None


for f in range(F0, F1 + 1):
    sc.frame_set(f)
    dgf = bpy.context.evaluated_depsgraph_get()
    WV = {}
    for w in workers:
        ev = w.body.evaluated_get(dgf)
        me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        ev.to_mesh_clear()
        M = np.array(ev.matrix_world)
        wv = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
        WV[w.name] = wv
        rigM = w.rig.matrix_world
        pos = rigM.translation.copy()
        POS[w.name].append(pos)
        clip, ph = active_clip(w.rig, f)
        CLIP[w.name].append(clip)
        PHASE[w.name].append((clip, ph[1] if ph else None))
        # pose vector (armature-space rotations of the main bones) for pops / loops
        POSE[w.name].append([(rigM @ w.rig.pose.bones[b].matrix).to_quaternion() for b in w.B["pose"]
                             if b in w.rig.pose.bones])  # world space: a turn handed over to the rig is no pop
        # feet
        fz = wv[w.cat == 3][:, 2]
        FOOTZ[w.name].append(float(fz.min()) if fz.size else float(wv[:, 2].min()))
        TOE[w.name].append((bone_world(w, "toe_L"), bone_world(w, "toe_R")))
        # torso forward = (left shoulder - right shoulder) x up
        l_, r_ = bone_world(w, "sh_L"), bone_world(w, "sh_R")
        fw = (l_ - r_).cross(Vector((0, 0, 1)))
        fw.z = 0
        TORSO[w.name].append(fw.normalized() if fw.length > 1e-6 else Vector((1, 0, 0)))

        # 1. body clipping vs static geometry (depth inside a surface > 1.2 cm)
        if w.bvh is not None:
            hits = defaultdict(lambda: [0, 0.0])
            for i in w.sample:
                p = wv[i]
                h = w.bvh.find_nearest(p, 0.08)
                if h[0] is None:
                    continue
                d = (p[0] - h[0].x) * h[1].x + (p[1] - h[0].y) * h[1].y + (p[2] - h[0].z) * h[1].z
                if d < -0.012:
                    on = obj_names[w.st_obj[h[2]]]
                    hits[on][0] += 1
                    hits[on][1] = max(hits[on][1], -d)
            for on, (cnt, dep) in hits.items():
                if cnt >= 3:
                    sev = "high" if (dep > 0.04 or cnt > 40) else "medium"
                    if on.startswith(w.name) or "chair" in on or "stool" in on:
                        sev = "low"  # own stool / chair: sitting contact
                    w.flags.append((f, "body_clip_static", sev, on, dep, f"{cnt} verts inside '{on}', max depth "
                                                                          f"{dep * 100:.1f} cm"))
        # 2. body inside a roll-cage volume (not the hands / forearms)
        nonhand = wv[(w.cat == 0) | (w.cat == 3)][::2]
        for cg in CAGES:
            if cg.parent is w.rig:
                continue
            if (cg.matrix_world.translation - pos).length > 1.6:
                continue
            Mi = np.array(cg.matrix_world.inverted())
            loc = nonhand @ Mi[:3, :3].T + Mi[:3, 3]
            inside = np.count_nonzero((np.abs(loc[:, 0]) < 0.33) & (np.abs(loc[:, 1]) < 0.37) & (loc[:, 2] > 0.2)
                                      & (loc[:, 2] < 1.75))
            if inside > 8:
                w.flags.append((f, "body_in_cage", "high", cg.name, inside, f"{inside} body verts inside cage "
                                                                            f"'{cg.name}'"))
        # 3. held objects
        for ob in w.held:
            obev = ob.evaluated_get(dgf)
            ome = obev.to_mesh()
            ome.calc_loop_triangles()
            oco = np.empty(len(ome.vertices) * 3)
            ome.vertices.foreach_get("co", oco)
            OM = np.array(obev.matrix_world)
            oco = oco.reshape(-1, 3) @ OM[:3, :3].T + OM[:3, 3]
            otr = np.empty(len(ome.loop_triangles) * 3, dtype=np.int32)
            ome.loop_triangles.foreach_get("vertices", otr)
            obev.to_mesh_clear()
            otr = otr.reshape(-1, 3)
            if np.linalg.det(OM[:3, :3]) < 0:  # mirrored placement: flip winding so normals point outward
                otr = otr[:, ::-1]
            obvh = BVHTree.FromPolygons(oco.tolist(), otr.tolist())
            lo_, hi_ = oco.min(axis=0) - 0.03, oco.max(axis=0) + 0.03
            near = np.nonzero(np.all((wv >= lo_) & (wv <= hi_), axis=1))[0]
            kind = ob.name.rsplit("_", 1)[-1]
            if kind == "cage":  # thin wires: count torso / legs inside the box instead
                Mi = np.array(ob.matrix_world.inverted())
                loc = nonhand @ Mi[:3, :3].T + Mi[:3, 3]
                inside = int(np.count_nonzero((np.abs(loc[:, 0]) < 0.33) & (np.abs(loc[:, 1]) < 0.37)
                                              & (loc[:, 2] > 0.2) & (loc[:, 2] < 1.75)))
                if inside > 8:
                    w.flags.append((f, "held_clip_body", "high", ob.name, inside,
                                    f"{inside} body verts inside own pushed cage"))
                hands = [bone_world(w, "hand_L"), bone_world(w, "hand_R")]
                gaps = [obvh.find_nearest(h)[3] for h in hands]
                gmax = max(g for g in gaps if g is not None)
                if gmax > 0.06:
                    w.flags.append((f, "push_contact", "high" if gmax > 0.15 else "medium", ob.name, gmax,
                                    f"hand {gmax * 100:.0f} cm off the cage (L {gaps[0] * 100:.0f}, R "
                                    f"{gaps[1] * 100:.0f})"))
                # cage moves with the worker
                if f > F0:
                    prev = HELD_REL.get((w.name, "cagepos"))
                    cp = ob.matrix_world.translation.copy()
                    if prev is not None:
                        dc, dr = cp - prev[0], pos - prev[1]
                        if (dc - dr).length > 0.01:
                            w.flags.append((f, "push_contact", "high", ob.name + ":motion", (dc - dr).length,
                                            f"cage moved {dc.length * 100:.1f} cm vs worker {dr.length * 100:.1f} cm"))
                    HELD_REL[(w.name, "cagepos")] = (cp, pos.copy())
                continue
            inside = 0
            for i in near:
                h = obvh.find_nearest(wv[i], 0.05)
                if h[0] is not None and (Vector(wv[i]) - h[0]).dot(h[1]) < -0.002:
                    inside += 1
            if inside >= 3:
                w.flags.append((f, "held_clip_body", "medium" if inside < 15 else "high", ob.name, inside,
                                f"{inside} hand/body verts pass through the {kind}"))
            hb = ob.parent_bone or ""
            sd = side_of(hb)
            hand_mask = (w.cat == 1) & ((w.side == (1 if sd == "R" else 2)) if sd and kind != "carton" else True)
            hv = wv[hand_mask]
            gap = min((obvh.find_nearest(p)[3] for p in hv[::3]), default=None) if hv.size else None
            if gap is not None and gap > 0.03:
                w.flags.append((f, "held_not_touching", "high" if gap > 0.08 else "medium", ob.name, gap,
                                f"{kind} {gap * 100:.1f} cm from the hand"))
            if hb in w.rig.pose.bones:
                Bm = w.rig.matrix_world @ w.rig.pose.bones[hb].matrix
                rel = Bm.inverted() @ ob.matrix_world
                key = (w.name, ob.name)
                if key not in HELD_REL:
                    HELD_REL[key] = rel
                pred = (Bm @ HELD_REL[key]).translation
                drift = (pred - ob.matrix_world.translation).length
                if drift > 0.005:
                    w.flags.append((f, "held_drift", "medium", ob.name, drift, f"{kind} drifted {drift * 100:.1f} cm "
                                                                               f"relative to the hand"))
    # 3a. head vs moving objects: head sphere r = 11 cm (centre 9 cm above the head joint) vs each object's box
    for w in workers:
        hpb = w.rig.pose.bones.get(w.B["head"])
        if hpb is None:
            continue
        hc = w.rig.matrix_world @ hpb.head + Vector((0, 0, 0.09))
        worst = None
        for ob in ANIM_SMALL:
            if ob.hide_render or (ob.matrix_world.translation - hc).length > 1.0:
                continue
            lc = ob.matrix_world.inverted() @ hc
            bb = ob.bound_box
            lo = Vector((min(c[0] for c in bb), min(c[1] for c in bb), min(c[2] for c in bb)))
            hi = Vector((max(c[0] for c in bb), max(c[1] for c in bb), max(c[2] for c in bb)))
            q = Vector((min(max(lc.x, lo.x), hi.x), min(max(lc.y, lo.y), hi.y), min(max(lc.z, lo.z), hi.z)))
            d = (ob.matrix_world @ q - hc).length
            if d < 0.11 and (worst is None or d < worst[1]):
                worst = (ob.name, d)
        if worst is not None:
            w.flags.append((f, "held_clip_head", "high", worst[0], 0.11 - worst[1],
                            f"'{worst[0]}' {(0.11 - worst[1]) * 100:.0f} cm into the head"))
    # 3a'. flow parcels inside each other (review 006 P0 #4): oriented boxes, 2-D separating axes + height overlap
    boxes = []
    for ob in PARCELS:
        if ob.hide_render:
            continue
        M = ob.matrix_world
        bb = [M @ Vector(c) for c in ob.bound_box]
        R = M.to_3x3().normalized()
        boxes.append((ob.name, M.translation.xy, [R.col[0].xy.normalized(), R.col[1].xy.normalized()],
                      [Vector(c).xy for c in bb], min(v.z for v in bb), max(v.z for v in bb)))
    for i in range(len(boxes)):
        na, ca, axa, pa, za0, za1 = boxes[i]
        for j in range(i + 1, len(boxes)):
            nb, cb, axb, pb_, zb0, zb1 = boxes[j]
            if (ca - cb).length > 1.0 or min(za1, zb1) - max(za0, zb0) < 0.01:
                continue
            depth = 9.0
            for ax in axa + axb:
                if ax.length < 1e-6:
                    continue
                a_ = [ax.dot(q) for q in pa]
                b_ = [ax.dot(q) for q in pb_]
                depth = min(depth, min(max(a_), max(b_)) - max(min(a_), min(b_)))
            if depth > 0.01:
                PARCEL_FLAGS.append((f, "parcel_overlap", "high", f"{na}|{nb}", depth,
                                     f"{na} and {nb} overlap by {depth * 100:.0f} cm at "
                                     f"({(ca.x + cb.x) / 2:.1f}, {(ca.y + cb.y) / 2:.1f})"))
    # 3a''. headwear fit (review 009d): the dome's lowest ring sits on the skull (cap <= 1.5 cm, hard hat <= 3.5 cm on
    # its harness) and the hat's up axis follows the head's (<= 8 deg) - every frame
    for w in workers:
        hats = [c for c in w.rig.children_recursive if c.name.endswith(("_hard", "_cap")) and c.type == "MESH"]
        if not hats or w.name not in WV:
            continue
        if not hasattr(w, "skin_idx"):
            me_ = w.body.data
            w.skin_idx = np.array(sorted({i for pl in me_.polygons if me_.materials[pl.material_index]
                                          and me_.materials[pl.material_index].name.endswith("_head")
                                          for i in pl.vertices}), dtype=np.int64)
            w.skin_polys = [tuple(pl.vertices) for pl in me_.polygons if me_.materials[pl.material_index]
                            and me_.materials[pl.material_index].name.endswith("_head")]
            hb_ = w.rig.data.bones.get(w.B["head"])
            Mr = w.rig.matrix_world @ hb_.matrix_local
            w.head_up_ax = max(((i, sg) for i in range(3) for sg in (1, -1)), key=lambda c: c[1] * Mr.col[c[0]][2])
        if w.skin_idx.size == 0:
            continue
        # distance to the head SURFACE (nearest skin vertex overstated the gap by up to ~1.5 cm: vertices 2-3 cm apart)
        verts_ = [Vector(v) for v in WV[w.name]]
        bvh_ = BVHTree.FromPolygons(verts_, w.skin_polys)
        Hm = w.rig.matrix_world @ w.rig.pose.bones[w.B["head"]].matrix
        i_, sg_ = w.head_up_ax
        head_up = Vector(Hm.col[i_][:3]).normalized() * sg_
        for hat in hats:
            if hat.hide_render:
                continue
            hv0 = [v.co for v in hat.data.vertices]  # ring picked on the rest mesh, measured on the deformed one
            zmin = min(v.z for v in hv0)
            # the band edge only: the dome's bottom is a flat disc INSIDE the head (its inner points read as 2-8 cm
            # "gaps"); hard-hat shell 13 x 15, cap dome 10.5 x 11.5 (mesh cm)
            if hat.name.endswith("_hard"):
                idx = [i for i, v in enumerate(hv0) if v.z < zmin + 0.6 and (v.x / 13.0) ** 2 + (v.y / 15.0) ** 2 > 0.85
                       and (v.x * v.x + v.y * v.y) ** 0.5 < 13.5]
            else:  # the open crown's band edge: exactly z = 0 (the brim joins it there and hangs lower; each cap's
                # band is shaped to its head, so no fixed radius)
                idx = [i for i, v in enumerate(hv0) if abs(v.z) < 0.05 and (v.x * v.x + v.y * v.y) ** 0.5 > 4.0]
            ev_ = hat.evaluated_get(bpy.context.evaluated_depsgraph_get())
            me_h = ev_.to_mesh()
            ring = [me_h.vertices[i].co.copy() for i in idx if i < len(me_h.vertices)]  # dome, not the brim
            ev_.to_mesh_clear()
            Mh = hat.matrix_world
            gaps = sorted(d_ for d_ in (bvh_.find_nearest(Mh @ v)[3] for v in ring[::2]) if d_ is not None)
            if not gaps:
                continue
            gap = gaps[len(gaps) // 2]
            tilt = math.degrees(Vector(Mh.col[2][:3]).normalized().angle(head_up))
            lim = 0.015 if hat.name.endswith("_cap") else 0.035
            if gap > lim or tilt > 8.0:
                w.flags.append((f, "accessory_fit", "high", hat.name, max(gap - lim, 0.0) + tilt / 1000,
                                f"{hat.name.rsplit('_', 1)[-1]} rim {gap * 100:.1f} cm off the skull (max "
                                f"{lim * 100:.1f}), tilted {tilt:.0f} deg from the head"))
    # 3b. hats / caps: on the head every frame (centre within 6 cm of where it sat at frame 1, relative to the head)
    for w in workers:
        for ob in [c for c in w.rig.children_recursive if c.name.endswith(("_hard", "_cap"))]:
            hb = ob.parent_bone or w.B["head"]
            Hm = w.rig.matrix_world @ w.rig.pose.bones[hb].matrix
            relM = Hm.inverted() @ ob.matrix_world
            rel = relM.translation
            key = (w.name, ob.name, "hat")
            if key not in HELD_REL:
                HELD_REL[key] = relM.copy()
            drift = (Hm @ HELD_REL[key].translation - Hm @ rel).length
            q0 = HELD_REL[key].to_3x3().normalized().to_quaternion()
            turn = math.degrees(q0.rotation_difference(relM.to_3x3().normalized().to_quaternion()).angle)
            if drift > 0.01 or turn > 3.0 or ob.hide_render:  # accessory_follow (review 013): 1 cm / 3 deg
                w.flags.append((f, "accessory_off_head", "high", ob.name, drift,
                                f"{ob.name.rsplit('_', 1)[-1]} moved {drift * 100:.1f} cm / {turn:.1f} deg on the head"
                                + (" (hidden)" if ob.hide_render else "")))
            if f == F0 and ob.name.endswith("_cap") and getattr(w, "skin_idx", None) is not None \
                    and w.skin_idx.size:  # accessory_face: nothing of the cap in front of the face below the brows
                Mh_ = ob.matrix_world
                up_ = Vector(Mh_.col[2][:3]).normalized()
                fw_ = Vector(Mh_.col[1][:3]).normalized()
                band_c = Mh_.translation
                top_ = max(Vector(WV[w.name][i]).dot(up_) for i in w.skin_idx)
                brow = top_ - 0.10
                low = [Mh_ @ v.co for v in ob.data.vertices if (Mh_ @ v.co - band_c).dot(fw_) > 0.05]
                worst = min((v.dot(up_) - brow for v in low), default=1.0)
                if worst < 0.0:
                    w.flags.append((f, "accessory_face", "high", ob.name, -worst,
                                    f"cap {-worst * 100:.1f} cm below the brow line in front of the face"))
    # 3c. owner rule 9: an object clip needs its object; kneeling / sitting needs a real prop under / at the worker
    NEEDS = {"push": "_cage", "pushing": "_cage", "carrying": "_carton", "carrying_turn": "_carton",
             "lifting_object": ("_box_big", "_sack", "_parcel", "_carton"),
             "picking_up_object": ("_box_big", "_sack", "_parcel", "_carton")}
    for w in workers:
        clip = CLIP[w.name][-1]
        need = NEEDS.get(clip)
        if need:
            have = [o for o in sc.objects if o.name.startswith(w.name + "_") and o.name.endswith(need)]
            if not have:
                w.flags.append((f, "clip_without_object", "high", clip, 0, f"plays '{clip}' with no {need} object"))
        if clip in ("crouch_idle", "sit_to_type", "typing", "talking_when_sit"):
            pel = bone_world(w, "pelvis")
            hit, loc, nrm, idx, ob, _ = sc.ray_cast(dgf, pel + Vector((0, 0, 0.05)), Vector((0, 0, -1)), distance=1.2)
            while hit and ob.name in w.own:
                hit, loc, nrm, idx, ob, _ = sc.ray_cast(dgf, loc + Vector((0, 0, -0.01)), Vector((0, 0, -1)), distance=1.2)
            seat = hit and loc.z > 0.25 and ("chair" in ob.name or "stool" in ob.name or "sack" in ob.name
                                             or "parcel" in ob.name or "box" in ob.name)
            if not seat:
                w.flags.append((f, "kneel_sit_without_prop", "high", clip, 0,
                                f"'{clip}' with nothing to sit / kneel at under the pelvis"
                                + (f" (hits '{ob.name}' at {loc.z:.2f} m)" if hit else "")))
    # 4. worker vs worker (pairs closer than 1.3 m)
    for a in workers:
        for b in workers:
            if a.name >= b.name:
                continue
            if (POS[a.name][-1] - POS[b.name][-1]).length > 1.3:
                continue
            bv = BVHTree.FromPolygons(WV[b.name].tolist(), b.tris)
            cnt, dep = 0, 0.0
            for i in a.sample[::2]:
                p = WV[a.name][i]
                h = bv.find_nearest(p, 0.06)
                if h[0] is not None:
                    d = (Vector(p) - h[0]).dot(h[1])
                    if d < -0.01:
                        cnt += 1
                        dep = max(dep, -d)
            if cnt >= 3:
                for x, y in ((a, b), (b, a)):
                    x.flags.append((f, "body_clip_worker", "high", y.name, dep,
                                    f"{cnt} verts inside {y.name}, max depth {dep * 100:.1f} cm"))
    # 5. cameras: visibility, facing, idle counts
    for w in workers:
        chest = bone_world(w, "chest")
        for cam in CAMS:
            cp = cam.matrix_world.translation
            dist = (chest - cp).length
            if dist > 40 or not frustum(cam, chest):
                continue
            if not line_clear(cp, chest, w.own):
                continue
            VIS[w.name].add(cam.name)
            if CLIP[w.name][-1] in IDLE_CLIPS or w.role in IDLE_ROLES:
                if dist <= 30:
                    IDLE_IN_VIEW[(cam.name, f)].append(w.name)
            if dist <= 15:
                to_cam = cp - chest
                to_cam.z = 0
                if to_cam.length > 1e-6 and TORSO[w.name][-1].angle(to_cam.normalized()) < math.radians(35):
                    FACING[(w.name, cam.name)].append(f)
    if f % 25 == 0:
        log("frame", f)

# ------------------------------------------------------------------------------------------------ whole-clip checks
for w in workers:
    fz = FOOTZ[w.name]
    seated = w.name in SEATED
    for i, z in enumerate(fz):
        f = F0 + i
        if not seated and z > 0.02:
            w.flags.append((f, "feet_floating", "high" if z > 0.05 else "medium", "", z,
                            f"lowest foot {z * 100:.1f} cm above the floor"))
        if z < -0.015:
            w.flags.append((f, "feet_sinking", "high" if z < -0.04 else "low", "", z,
                            f"lowest foot {z * 100:.1f} cm below the floor"))
    for s in (0, 1):  # sliding: toe planted (within 1.2 cm of its lowest height) on two frames, moved > 2 cm
        toes = [t[s] for t in TOE[w.name]]
        if not toes or toes[0] is None:
            continue
        zmin = min(t.z for t in toes)
        for i in range(1, len(toes)):
            a, b = toes[i - 1], toes[i]
            if a.z < zmin + 0.012 and b.z < zmin + 0.012:
                d = math.hypot(b.x - a.x, b.y - a.y)
                if d > 0.02:
                    w.flags.append((F0 + i, "feet_sliding", "high" if d > 0.06 else "medium", "LR"[s], d,
                                    f"{'LR'[s]} foot planted but slid {d * 100:.1f} cm in one frame"))
    # paths (movers)
    P = POS[w.name]
    if w.mover:
        speeds = []
        for i in range(1, len(P)):
            a, b = P[i - 1], P[i]
            step = math.hypot(b.x - a.x, b.y - a.y)
            speeds.append(step * PLAN_FPS)
            f = F0 + i
            if step > 0.002:
                for zz in (0.3, 1.0):
                    o = Vector((a.x, a.y, zz))
                    d = Vector((b.x - a.x, b.y - a.y, 0))
                    hit, loc, nrm, idx, ob, _ = sc.ray_cast(bpy.context.evaluated_depsgraph_get(), o, d.normalized(),
                                                            distance=d.length + 0.25)
                    if hit and ob.name not in w.own and not ob.name.startswith("worker_") \
                            and not ob.name.startswith("carrier_"):
                        w.flags.append((f, "path_obstacle", "high", ob.name, zz, f"route runs into '{ob.name}' at "
                                                                                 f"{zz} m height"))
            on_lane = in_rects(b.x, b.y, LANE) and not in_rects(b.x, b.y, ZEBRA, 0.1)
            if on_lane:
                w.flags.append((f, "path_forklift_lane", "high" if w.role in ("walk", "to_break") else "medium", "",
                                0, "on the forklift lane outside a zebra crossing"))
            if w.role in ("walk", "to_break") and not in_rects(b.x, b.y, WALK + ZEBRA, 0.1):
                w.flags.append((f, "path_off_walkway", "medium", "", 0, f"walker off the walkways at "
                                                                        f"({b.x:.1f}, {b.y:.1f})"))
        moving = [s for s in speeds if s > 0.05]
        if moving:
            med = statistics.median(moving)
            clip = max(set(CLIP[w.name]), key=CLIP[w.name].count)
            lo, hi = (0.5, 1.3) if "push" in clip else (0.9, 1.8)
            if not lo <= med <= hi:
                add_range(w, F0, F1, "timing_speed", "high", "", med,
                          f"ground speed {med:.2f} m/s at the planned {PLAN_FPS} fps (expected {lo}-{hi})")
    # playback rate: a 30 fps clip on a 10 fps timeline must play at strip scale 1/3
    ad = w.rig.animation_data
    if ad:
        for tr in ad.nla_tracks:
            for st in tr.strips:
                if tr.name != "grip" and abs(st.scale - 1 / 3) > 0.01:
                    add_range(w, st.frame_start, st.frame_end - 1, "timing_playback_rate", "high", "rate", st.scale,
                              f"clip strips play at scale {st.scale:.2f} (should be 0.33 for 30 fps clips on the "
                              f"{PLAN_FPS} fps timeline): motion {st.scale * 3:.1f}x slower than real time")
    # pops: spike in pose change vs its neighbourhood, or root teleport
    Q = POSE[w.name]
    diffs = [0.0] + [sum(1 - abs(a.dot(b)) for a, b in zip(Q[i - 1], Q[i])) for i in range(1, len(Q))]
    for i in range(2, len(diffs) - 1):
        win = diffs[max(1, i - 5):i] + diffs[i + 1:i + 6]
        base = statistics.median(win) if win else 0
        if diffs[i] > 0.02 and diffs[i] > 6 * max(base, 1e-4):
            w.flags.append((F0 + i, "loop_pop", "high" if (diffs[i] > 0.05 and diffs[i] > 10 * max(base, 1e-4))
                            else "medium",
                            CLIP[w.name][i], diffs[i], f"pose jumps {diffs[i]:.3f} (local median {base:.4f}) at "
                                                       f"'{CLIP[w.name][i - 1]}' -> '{CLIP[w.name][i]}'"))
    for i in range(1, len(P)):
        if (P[i] - P[i - 1]).length > 0.3:
            w.flags.append((F0 + i, "loop_pop", "high", "teleport", (P[i] - P[i - 1]).length,
                            f"worker jumps {(P[i] - P[i - 1]).length:.2f} m in one frame"))
    # facing a camera > 2 s
    for cam in CAMS:
        fr = FACING.get((w.name, cam.name), [])
        run, start = 0, None
        for k, f in enumerate(fr + [None]):
            if f is not None and start is not None and f == fr[k - 1] + 1:
                run += 1
                continue
            if start is not None and run + 1 > 2 * PLAN_FPS:
                add_range(w, start, fr[k - 1], "facing_camera", "medium", cam.name, run + 1,
                          f"faces {cam.name} for {(run + 1) / PLAN_FPS:.1f} s")
            start, run = f, 0
    # faces away from the task (static workers): nothing within 1.6 m in front of the chest
    if not w.mover:
        for f in (F0, (F0 + F1) // 2, F1):
            sc.frame_set(f)
            chest = bone_world(w, "chest")
            fw = TORSO[w.name][f - F0]
            found = False
            for yaw in (-35, 0, 35):
                d0 = fw.copy()
                d0.rotate(__import__("mathutils").Euler((0, 0, math.radians(yaw))))
                for pitch in (0, -25, -50):
                    d = Vector((d0.x * math.cos(math.radians(pitch)), d0.y * math.cos(math.radians(pitch)),
                                math.sin(math.radians(pitch))))
                    hit, loc, nrm, idx, ob, _ = sc.ray_cast(bpy.context.evaluated_depsgraph_get(), chest + d * 0.25,
                                                            d, distance=1.6)
                    if hit and ob.name not in w.own:
                        found = True
                        break
                if found:
                    break
            if not found:
                w.flags.append((f, "facing_away_from_task", "low", "", 0,
                                "nothing within 1.6 m in front of the chest (faces empty space)"))

# neighbours in sync: same clip, same phase (within 3 clip frames) on >= 80 % of shared frames, < 6 m apart
for a in workers:
    for b in workers:
        if a.name >= b.name or (POS[a.name][0] - POS[b.name][0]).length > 6:
            continue
        same, tot = 0, 0
        for (ca, pa), (cb, pb_) in zip(PHASE[a.name], PHASE[b.name]):
            if ca == cb and pa is not None and pb_ is not None:
                tot += 1
                same += abs(pa - pb_) < 3
        if tot > 30 and same / tot > 0.8:
            for x, y in ((a, b), (b, a)):
                add_range(x, F0, F1, "timing_in_sync", "medium", y.name, same / tot,
                          f"moves in sync with {y.name} ('{CLIP[a.name][0]}', {same / tot:.0%} of frames)")
# > 3 idle workers in one camera view
cam_flags = defaultdict(list)
for (cam, f), names in IDLE_IN_VIEW.items():
    if len(names) > 3:
        cam_flags[cam].append((f, len(names), sorted(names)))

# ------------------------------------------------------------------------------------------------ write
rows = []


def merge(flags):
    """Consecutive frames (gap <= 2) with the same check + key -> one row; detail of the worst frame."""
    out = []
    by = defaultdict(list)
    for fl in flags:
        by[(fl[1], fl[3])].append(fl)
    for (chk, key), fl in by.items():
        fl.sort(key=lambda t: t[0])
        cur = [fl[0]]
        for t in fl[1:]:
            if t[0] - cur[-1][0] <= 2:
                cur.append(t)
            else:
                out.append(cur)
                cur = [t]
        out.append(cur)
    res = []
    for grp in out:
        worst = max(grp, key=lambda t: abs(t[4]) if isinstance(t[4], (int, float)) else 0)
        sev = "high" if any(t[2] == "high" for t in grp) else "medium" if any(t[2] == "medium" for t in grp) else "low"
        res.append((grp[0][0], grp[-1][0], grp[0][1], sev, worst[5] + (f" [{len(grp)} frames]" if len(grp) > 1 else "")))
    return res


for w in workers:
    for f0, f1, chk, sev, det in merge(w.flags):
        rows.append([w.name, w.role, CLIP[w.name][min(max(f0, F0), F1) - F0], f0, f1, chk, sev, det])
for f0, f1, chk, sev, det in (merge(PARCEL_FLAGS) if PARCEL_FLAGS else []):
    rows.append(["parcels", "flow", "-", f0, f1, chk, sev, det])
for cam, fl in cam_flags.items():
    fl.sort()
    grp = [fl[0]]
    for t in fl[1:] + [None]:
        if t is not None and t[0] - grp[-1][0] <= 2:
            grp.append(t)
            continue
        worst = max(grp, key=lambda t: t[1])
        rows.append([cam, "camera", "-", grp[0][0], grp[-1][0], "timing_idle_count", "medium",
                     f"{worst[1]} idle workers in view: {', '.join(worst[2])}"])
        grp = [t] if t else []
SEV = {"high": 0, "medium": 1, "low": 2}
rows.sort(key=lambda r: (SEV[r[6]], r[0], r[3]))
with open(QA / "auto_flags.csv", "w", newline="", encoding="utf-8") as fh:
    cw = csv.writer(fh)
    cw.writerow(["worker_name", "role", "clip_name", "frame_start", "frame_end", "check", "severity", "detail"])
    cw.writerows(rows)

per_w, per_c, per_s = defaultdict(lambda: defaultdict(int)), defaultdict(int), defaultdict(int)
for r in rows:
    per_w[r[0]][r[6]] += 1
    per_c[r[5]] += 1
    per_s[r[6]] += 1
lines = [f"QA auto checks — {len(rows)} flag rows, frames {F0}-{F1} (planned {PLAN_FPS} fps), "
         f"scene fps as saved: {sc.render.fps}", "", "By severity:"]
lines += [f"  {s:7s} {per_s[s]}" for s in ("high", "medium", "low")]
lines += ["", "By check:"] + [f"  {c:24s} {n}" for c, n in sorted(per_c.items(), key=lambda t: -t[1])]
lines += ["", "By worker (high / medium / low):"]
for name in [w.name for w in workers] + sorted(cam_flags):
    d = per_w.get(name, {})
    lines.append(f"  {name:28s} {ROLE.get(name, 'camera'):12s} {d.get('high', 0):4d} {d.get('medium', 0):4d} "
                 f"{d.get('low', 0):4d}")
(QA / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
(QA / "timeline.json").write_text(json.dumps({w.name: {"role": w.role, "clips": CLIP[w.name]} for w in workers}),
                                  encoding="utf-8")
(QA / "visibility.json").write_text(json.dumps({w.name: sorted(VIS[w.name]) for w in workers}, indent=1),
                                    encoding="utf-8")
print("\n".join(lines), flush=True)
log("done")
