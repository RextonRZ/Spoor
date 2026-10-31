"""Scan checkpoints in the hub (Rexton 31 Oct): static objects + worn scanners, patched into a scenario blend (no flow
re-run), then a collision gate for these objects only and which CCTV cameras see each one.

  blender -b <S2.blend> -P assets/hub/scan_checkpoints.py -- --save <out.blend>
  blender -b <out.blend> -P assets/hub/scan_checkpoints.py -- --check --out <dir> [--frames 1-900]

Objects (references: Mettler-Toledo TLX / SICK DWS terminals - one HMI per tunnel with the last parcel's record; UPS'
RS507 ring imager + wrist terminal for loading / unloading; a pistol-grip handheld in a hip holster for the chutes):
  1. dws_monitor_A / _B: a 22" monitor on a steel arm at line A's tunnel exit (north wall) and on line B's DWS arch
     post; screen = make_dws_screen.py texture (fictional brand), lit.
  2. scanin_*: the exception store's SCAN IN point east of its door (on the S2 actor's way in): a wall shelf on two
     brackets on the rack face, a handheld scanner standing in its cradle, the sign above (scan_in_sign.png).
  3. worn: ring scanner (right index finger) + wrist terminal (left forearm) on the D05 unloaders; a pistol-grip
     scanner in a holster on the bagger's right hip (chute / bag / cage scans). Parented to their bones.
The check writes <dir>/scan_checkpoints.json: per object the CCTV cameras that see it (>= 2 of 9 sample points in
frame, inside the lens crop, not behind the static hub, at any of 3 frames) and every frame-hit with a worker /
parcel / static object (BVH overlap; worn props against their own body are listed apart).
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HUB = Path(__file__).resolve().parent
sys.path.insert(0, str(HUB))
ap = argparse.ArgumentParser()
ap.add_argument("--save", default="")
ap.add_argument("--check", action="store_true")
ap.add_argument("--out", default="")
ap.add_argument("--frames", default="1-900")
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
sc = bpy.context.scene
SIGNS = HUB / "build" / "signs"
TAG = "scanchk"  # every object made here carries obj["scanchk"] = its group


def coll():
    c = bpy.data.collections.get("ScanCheckpoints") or bpy.data.collections.new("ScanCheckpoints")
    if c.name not in sc.collection.children:
        sc.collection.children.link(c)
    return c


def mat(name, rgb, rough=0.5, metal=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def img_mat(name, png, emit=0.0):
    """Image on the front: a lit screen (emit > 0) or a printed sign plate."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = bpy.data.images.load(str(SIGNS / png), check_existing=True)
    t.image.pack()  # travels with the blend (Modal)
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.25 if emit else 0.5
    if emit:
        nt.links.new(t.outputs["Color"], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = emit
    return m


def box_obj(name, group, boxes, mats, parent=None):
    """One object from axis-aligned boxes in its own local frame: [(x0, y0, z0, x1, y1, z1, material index)]."""
    bm = bmesh.new()
    for x0, y0, z0, x1, y1, z1, mi in boxes:
        r = bmesh.ops.create_cube(bm, size=1.0)
        for v in r["verts"]:
            v.co = Vector((x0 + (v.co.x + 0.5) * (x1 - x0), y0 + (v.co.y + 0.5) * (y1 - y0), z0 + (v.co.z + 0.5) * (z1 - z0)))
        for f in {f for v in r["verts"] for f in v.link_faces}:
            f.material_index = mi
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    ob[TAG] = group
    coll().objects.link(ob)
    return ob


def screen_quad(name, group, w, h, m):
    """A UV-mapped plane facing local -Y (the image upright)."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new()
    for li, (u, v) in zip(range(4), ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[li].uv = (u, v)
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    ob[TAG] = group
    coll().objects.link(ob)
    return ob


def place(ob, loc, yaw=0.0, tilt=0.0):
    ob.matrix_world = Matrix.Translation(loc) @ Matrix.Rotation(yaw, 4, "Z") @ Matrix.Rotation(tilt, 4, "X")


def monitor(tag, centre, yaw, tilt, arm_from, png):
    """15.6" touch panel (0.39 x 0.245 x 0.035, its screen 0.345 x 0.194 = 16:9) facing local -Y turned by yaw, tilted
    down by tilt (+: the screen looks down), on a short swivel bracket (40 mm square) from arm_from (a point on the
    structure) to its back - as BeeVision's tunnel HMI, at standing eye height beside the belt (BeeSort video 2:14)."""
    steel, black = mat("chk_steel", (0.42, 0.43, 0.45), 0.45, 0.6), mat("chk_black", (0.03, 0.03, 0.035), 0.4)
    body = box_obj(f"dws_monitor_{tag}", "monitor", [(-0.195, 0.0, -0.1225, 0.195, 0.035, 0.1225, 0),
                                                       (-0.05, 0.035, -0.05, 0.05, 0.055, 0.05, 1)], [black, steel])
    place(body, Vector(centre), yaw, tilt)
    scr = screen_quad(f"dws_monitor_{tag}_screen", "monitor", 0.345, 0.194, img_mat(f"dws_screen_{tag}", png, emit=2.0))
    scr.matrix_world = body.matrix_world @ Matrix.Translation((0, -0.0015, 0.0))
    back = body.matrix_world @ Vector((0, 0.055, 0))
    d = back - Vector(arm_from)
    L = d.length
    arm = box_obj(f"dws_monitor_{tag}_arm", "monitor", [(-0.02, 0.0, -0.02, 0.02, L, 0.02, 0)], [steel])
    arm.matrix_world = Matrix.Translation(arm_from) @ d.to_track_quat("Y", "Z").to_matrix().to_4x4()
    return [body, scr, arm]


def scanner_mesh(name, group):
    import people  # the hub's handheld (people._scanner, cm units), its materials
    grey, yel, red = (people._mat("scanner_grey", (0.12, 0.12, 0.13), 0.4), people._mat("scanner_yellow", (0.8, 0.6, 0.05), 0.5),
                      people._mat("scanner_window", (0.9, 0.05, 0.03), 0.2, emit=1.5))
    ob = bpy.data.objects.new(name, people._prop_mesh("handheld_scanner", people._scanner, [grey, yel, red]))
    ob[TAG] = group
    coll().objects.link(ob)
    return ob


def scan_in_station():
    """In the bay east of Z11's door (between the uprights at x 15.24 and 15.75, its panel at y 33.005 facing -Y):
    a 0.40 x 0.18 m shelf top at 1.045 m on two brackets, the handheld standing in its cradle nose along the shelf (out
    over the aisle, the S2 actor's body brushed it: run 8 check), the sign above at 1.45 m. 0.5 m wide bay: wider, both
    went into the next upright."""
    steel, black = mat("chk_steel", (0.42, 0.43, 0.45), 0.45, 0.6), mat("chk_black", (0.03, 0.03, 0.035), 0.4)
    shelf = box_obj("scanin_shelf", "scanin", [(15.30, 32.82, 1.02, 15.70, 32.999, 1.045, 0),
                                               (15.33, 32.85, 0.92, 15.35, 32.999, 1.02, 0),
                                               (15.65, 32.85, 0.92, 15.67, 32.999, 1.02, 0),
                                               (15.50, 32.88, 1.045, 15.60, 32.96, 1.10, 1)], [steel, black])
    sca = scanner_mesh("scanin_scanner", "scanin")  # grip down in the cradle, nose east along the shelf
    sca.matrix_world = Matrix.Translation((15.55, 32.92, 1.10 + 0.08)) @ Matrix.Rotation(-math.pi / 2, 4, "Z")         @ Matrix.Diagonal((0.01, 0.01, 0.01, 1.0))
    plate = box_obj("scanin_sign_board", "scanin", [(-0.2, 0.0, -0.12, 0.2, 0.003, 0.12, 0)],
                    [mat("chk_white", (0.95, 0.95, 0.93), 0.6)])
    place(plate, Vector((15.50, 32.996, 1.45)))
    face = screen_quad("scanin_sign", "scanin", 0.392, 0.235, img_mat("scan_in_sign", "scan_in_sign.png"))
    place(face, Vector((15.50, 32.9945, 1.45)))  # (1.5 mm off the board: at 0.5 mm, z-fighting, run 11)
    return [shelf, sca, plate, face]


def bone_mat(arm, bn):
    pb = arm.pose.bones[bn]
    return arm.matrix_world @ pb.matrix


def attach(ob, arm, bn, W):
    ob.parent, ob.parent_type, ob.parent_bone = arm, "BONE", bn
    bpy.context.view_layer.update()
    ob.matrix_world = W


def dorsal(arm, side):
    """Back-of-hand direction from the finger bones (palm down: right hand index - pinky x finger = up)."""
    g = lambda b: arm.matrix_world @ arm.pose.bones[f"Bip01 {side} {b}"].head  # noqa: E731
    fdir = (g("Finger11") - g("Finger1")).normalized()
    across = g("Finger1") - g("Finger4")
    n = fdir.cross(across) if side == "R" else across.cross(fdir)
    return fdir, n.normalized()


def on_skin(arm, guess, half, along, groups, gap=0.002):
    """Sits a worn prop ON its wearer's skin (frame 1): the body surface nearest the guess, the prop's local Z along
    its outward normal at half its thickness + 2 mm out, local Y along `along` (made square to the normal). A fixed
    offset from the bone left the wrist terminals floating 3-5 cm off the forearm (crop check). Only the skin of the
    bone it is parented to (vertex groups whose names hold one of `groups`): the nearest skin overall was her thigh
    for a ring on a hand resting by the hip."""
    body = next(c for c in arm.children if c.name.endswith("_body"))
    gi = {g.index for g in body.vertex_groups if any(k in g.name for k in groups)}
    keep = {v.index for v in body.data.vertices if v.groups and max(v.groups, key=lambda g: g.weight).group in gi}
    dg = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg)
    me = ev.to_mesh()
    M = ev.matrix_world
    t = BVHTree.FromPolygons([M @ v.co for v in me.vertices],
                             [tuple(q.vertices) for q in me.polygons if all(i in keep for i in q.vertices)])
    ev.to_mesh_clear()
    loc, nrm, _i, _d = t.find_nearest(guess)
    if nrm.dot(guess - loc) < 0:
        nrm = -nrm
    y = (along - nrm * along.dot(nrm)).normalized()
    return Matrix.Translation(loc + nrm * (half + gap)) @ Matrix((y.cross(nrm), y, nrm)).transposed().to_4x4()


def worn():
    out = []
    dark, scr = mat("chk_black", (0.03, 0.03, 0.035), 0.4), mat("chk_screen", (0.05, 0.12, 0.25), 0.2)
    red = mat("chk_red", (0.85, 0.05, 0.03), 0.3)
    sc.frame_set(1)
    for wn in ("worker_dock_D05_n", "worker_dock_D05_s"):
        arm = sc.objects.get(wn)
        if arm is None:
            continue
        fdir, up = dorsal(arm, "R")  # back-of-hand scanner (glove type, ProGlove at Yodel), its window to the fingers
        # (a ring on the index finger met the cartons it gripped, 5 frames, run 11-12 check)
        kh = arm.matrix_world @ arm.pose.bones["Bip01 R Hand"].tail
        ring = box_obj(f"{wn}_hand_scanner", "worn", [(-0.016, -0.022, -0.008, 0.016, 0.022, 0.008, 0),
                                                      (-0.012, 0.022, -0.006, 0.012, 0.024, 0.006, 1)], [dark, red])
        attach(ring, arm, "Bip01 R Hand", on_skin(arm, kh - fdir * 0.03 + up * 0.05, 0.008, fdir, ("R Hand",)))
        # the ring's terminal on the left hip, clipped to the belt (UPS: wrist- or hip-worn; on the forearm it met
        # the cartons he carries, 10 frames, and the boom, run 8 check)
        L_ = arm.matrix_world @ arm.pose.bones["Bip01 L Thigh"].head
        R_ = arm.matrix_world @ arm.pose.bones["Bip01 R Thigh"].head
        cy = 23.0 if "D05" in wn else 11.0  # the boom's centre line: the terminal on the hip away from it (on the near
        if abs(R_.y - cy) > abs(L_.y - cy):  # hip it met the boom's side frame, 6 frames, run 9 check)
            L_, R_ = R_, L_
        term = box_obj(f"{wn}_hip_terminal", "worn", [(-0.033, -0.05, -0.011, 0.033, 0.05, 0.011, 0),
                                                      (-0.026, -0.035, 0.011, 0.026, 0.035, 0.0125, 1)], [dark, scr])
        toe_ = (arm.matrix_world @ arm.pose.bones["Bip01 R Toe0"].head) - (arm.matrix_world @ arm.pose.bones["Bip01 R Foot"].head)
        out_l = (L_ - R_).normalized()
        fwd_ = Vector((out_l.y, -out_l.x, 0.0)).normalized()
        if fwd_.dot(toe_) < 0:
            fwd_ = -fwd_
        # at the back of that hip (at its side the bottom-row cartons he lifts met it, runs 15-16)
        attach(term, arm, "Bip01 Pelvis", on_skin(arm, L_ + out_l * 0.06 - fwd_ * 0.13 + Vector((0, 0, 0.02)), 0.012,
                                                  Vector((0, 0, 1)), ("Pelvis",), gap=0.015))  # (over the vest's hem)
        out += [ring, term]
    arm = sc.objects.get("worker_bag_1")
    if arm is not None:  # holster at the right hip from the belt line, the scanner in it nose down, grip back
        L_ = arm.matrix_world @ arm.pose.bones["Bip01 L Thigh"].head
        R_ = arm.matrix_world @ arm.pose.bones["Bip01 R Thigh"].head
        out_ = (R_ - L_).normalized()
        toe = (arm.matrix_world @ arm.pose.bones["Bip01 R Toe0"].head) - (arm.matrix_world @ arm.pose.bones["Bip01 R Foot"].head)
        fwd = Vector((out_.y, -out_.x, 0.0)).normalized()  # (these rigs turn by their bones: the foot says forward)
        if fwd.dot(toe) < 0:
            fwd = -fwd
        # at the back of the right hip (at the side his hanging hand passed through its grip, qa_checks run 11)
        W = on_skin(arm, R_ + out_ * 0.07 - fwd * 0.12 + Vector((0, 0, -0.02)), 0.026, out_, ("Pelvis",), gap=0.008)  # local Z out from the hip (from 0.2 m out the nearest skin was his hanging hand)
        Rh = W @ Matrix(((0, 0, 1, 0), (0, 1, 0, 0), (-1, 0, 0, 0), (0, 0, 0, 1)))  # box X (thickness) along the normal
        Rh = Matrix.Translation(Rh.translation) @ Rh.to_3x3().to_4x4()
        up_ = Rh.to_3x3() @ Vector((0, 0, 1))
        if up_.z < 0:  # keep the holster's top up
            Rh = Rh @ Matrix.Rotation(math.pi, 4, "Y")
        hol = box_obj("worker_bag_1_holster", "worn", [(-0.026, -0.045, -0.09, 0.026, 0.045, 0.06, 0)], [dark])
        attach(hol, arm, "Bip01 Pelvis", Rh)
        sca = scanner_mesh("worker_bag_1_scanner", "worn")  # nose (+Y) down into the holster, grip back out of it
        attach(sca, arm, "Bip01 Pelvis", Rh @ Matrix.Translation((0, 0, 0.05)) @ Matrix.Rotation(math.pi / 2, 4, "Z")
               @ Matrix.Rotation(-math.pi / 2, 4, "X") @ Matrix.Diagonal((0.01, 0.01, 0.01, 1.0)))  # (grip out of the
        # holster, away from his back)
        out += [hol, sca]
    return out


# ------------------------------------------------------------------------------------------------ check
RX, RY = 2688, 1520
TRUTH = json.loads((HUB / "render_truth.json").read_text())["cameras"]


def lens_keeps(cam, x, y):
    k1 = TRUTH.get(cam.name, {}).get("lens_k1", -0.06)
    f = RX / (2 * math.tan(cam.data.angle_x / 2))
    dx, dy = x - RX / 2, y - RY / 2
    r_in = math.hypot(dx, dy)
    if r_in < 1:
        return True
    t_edge = min((RX / 2) / abs(dx) if abs(dx) > 1e-9 else 1e9, (RY / 2) / abs(dy) if abs(dy) > 1e-9 else 1e9)
    ex, ey = dx * t_edge / f, dy * t_edge / f
    s_ = (1 - k1 * (ex * ex + ey * ey)) / (1 - k1 * (RX / 2 / f) ** 2)
    return r_in <= math.hypot(ex, ey) * f * s_ - 2


def sees(cam, p, ignore, dg):
    """(in view, pixel xy) as mocap/rows_in_view.py: in frame, inside the lens crop, no static hub in the way."""
    pc = cam.matrix_world.inverted() @ p
    if pc.z > -0.1:
        return False, None
    tx = math.tan(cam.data.angle_x / 2)
    ty = tx * RY / RX
    if abs(pc.x / -pc.z) > tx * 0.98 or abs(pc.y / -pc.z) > ty * 0.98:
        return False, None
    px = (RX / 2 + pc.x / -pc.z / tx * RX / 2, RY / 2 - pc.y / -pc.z / ty * RY / 2)
    if not lens_keeps(cam, *px):
        return False, None
    o = cam.matrix_world.translation
    d = p - o
    L = d.length
    org = o.copy()
    for _ in range(12):
        hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, org, d.normalized(), distance=max(0.0, L - (org - o).length - 0.02))
        if not hit:
            return True, px
        if ob.name in ignore or ob.name.startswith(("worker_", "flow_parcel", "parcel_", "bag_", "cage_rolling", "sack_")):
            org = loc + d.normalized() * 0.005
            continue
        return False, None
    return True, px


def bvh(ob, dg):
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    M = ev.matrix_world
    t = BVHTree.FromPolygons([M @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    bb = [M @ Vector(c) for c in ev.bound_box]
    ev.to_mesh_clear()
    return t, (Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb))),
               Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb))))


def bb_hit(a_, b_, m=0.02):
    return all(a_[0][i] - m <= b_[1][i] and b_[0][i] - m <= a_[1][i] for i in range(3))


def check():
    mine = [o for o in sc.objects if o.get(TAG)]
    groups = {}
    for o in mine:
        groups.setdefault(o.name.split("_screen")[0].split("_arm")[0], []).append(o)
    cams = sorted([o for o in sc.objects if o.type == "CAMERA" and o.name.startswith("CAM_")], key=lambda o: o.name)
    owner = {o.name: o.parent.name for o in mine if o.parent is not None}
    vis = {}
    for f in (1, 450, 900):
        sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        for g, obs in groups.items():
            bb = [o.matrix_world @ Vector(c) for o in obs for c in o.bound_box]
            lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
            hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
            pts = [lo.lerp(hi, 0.5)] + [Vector((lo.x + (hi.x - lo.x) * u, lo.y + (hi.y - lo.y) * v, lo.z + (hi.z - lo.z) * w))
                                        for u in (0.2, 0.8) for v in (0.2, 0.8) for w in (0.2, 0.8)]
            ign = {o.name for o in obs} | ({owner[obs[0].name], owner[obs[0].name] + "_body"} if obs[0].name in owner else set())
            for cam in cams:
                hits = [sees(cam, p_, ign, dg) for p_ in pts]
                ok = [h[1] for h in hits if h[0]]
                if len(ok) >= 2:
                    size = max(abs(ok[i][0] - ok[j][0]) + abs(ok[i][1] - ok[j][1]) for i in range(len(ok)) for j in range(len(ok)))
                    e = vis.setdefault(g, {}).setdefault(cam.name, dict(frames=[], px_span=0))
                    e["frames"].append(f)
                    e["px_span"] = max(e["px_span"], round(size))
    f0, f1 = (int(x) for x in a.frames.split("-"))
    movers = [o for o in sc.objects if o.type == "MESH" and not o.get(TAG) and (
        o.name.startswith(("flow_parcel_", "bag_", "cage_rolling", "sack")) or (o.parent and o.parent.name.startswith("worker_")))]
    statics = [o for o in sc.objects if o.type == "MESH" and not o.get(TAG) and o not in movers and not o.hide_render]
    hits, self_hits = [], []
    sc.frame_set(f0)
    dg = bpy.context.evaluated_depsgraph_get()
    st_bvh = {o.name: bvh(o, dg) for o in statics}
    for o in mine:  # static new objects vs the static hub (frame 1), worn ones every frame below
        if o.parent is not None:
            continue
        t_, b_ = bvh(o, dg)
        for n_, (t2, b2) in st_bvh.items():
            if bb_hit(b_, b2, 0.0) and t_.overlap(t2):
                hits.append(dict(frame=f0, a=o.name, b=n_, kind="static"))
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        mb = {}
        for o in mine:
            t_, b_ = bvh(o, dg)
            for m in movers:
                if m.hide_render or not m.visible_get():
                    continue
                if m.name not in mb:
                    ev = m.evaluated_get(dg)
                    bb = [ev.matrix_world @ Vector(c) for c in ev.bound_box]
                    mb[m.name] = ((Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb))),
                                   Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))), None)
                if not bb_hit(b_, mb[m.name][0]):
                    continue
                if mb[m.name][1] is None:
                    mb[m.name] = (mb[m.name][0], bvh(m, dg)[0])
                if t_.overlap(mb[m.name][1]):
                    row = dict(frame=f, a=o.name, b=m.name)
                    own = o.parent is not None and m.parent is not None and m.parent.name == o.parent.name
                    (self_hits if own else hits).append(row)
            if o.parent is not None:  # worn: against the static hub too
                for n_, (t2, b2) in st_bvh.items():
                    if bb_hit(b_, b2, 0.0) and t_.overlap(t2):
                        hits.append(dict(frame=f, a=o.name, b=n_, kind="static"))
        if (f - f0) % 100 == 0:
            print(f"CHECK f{f} hits {len(hits)} own-body {len(self_hits)}", flush=True)
    res = dict(objects=sorted(o.name for o in mine), visible_in=vis, hits=hits, hits_n=len(hits),
               worn_vs_own_body=self_hits[:200], worn_vs_own_body_n=len(self_hits),
               not_seen=[g for g in groups if g not in vis])
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "scan_checkpoints.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("CHECK", json.dumps(dict(hits=len(hits), own=len(self_hits), not_seen=res["not_seen"],
                                   seen={g: sorted(v) for g, v in vis.items()})), flush=True)


if a.check:
    check()
else:
    for o in [o for o in sc.objects if o.get(TAG)]:  # re-runnable: replace what an earlier patch made
        bpy.data.objects.remove(o, do_unlink=True)
    made = []
    # line A: on the tunnel's south side panel (y 8.6) just short of its exit (x 22.0), facing south, centre at standing
    # eye height, 5 deg down (on the north panel no CCTV camera saw it: they all look north, run 8 check)
    made += monitor("A", (21.70, 8.597 - 0.06 - 0.055, 1.55), 0.0, math.radians(5), (21.70, 8.597, 1.55),
                    "dws_screen_A.png")
    # line B: off the arch's north-west post (44.85, 9.15), facing out from the arch (north-west), 10 deg down
    nb = Vector((-math.sqrt(0.5), math.sqrt(0.5), 0.0))
    cB = Vector((44.85, 9.15, 1.65)) + nb * (0.061 + 0.06 + 0.055)
    made += monitor("B", tuple(cB), math.atan2(nb.y, nb.x) + math.pi / 2, math.radians(5),
                    tuple(Vector((44.85, 9.15, 1.65)) + nb * 0.12), "dws_screen_B.png")
    made += scan_in_station()
    made += worn()
    print("PATCH", len(made), [o.name for o in made], flush=True)
    if a.save:
        bpy.ops.wm.save_as_mainfile(filepath=str(Path(a.save).resolve()), compress=True)
