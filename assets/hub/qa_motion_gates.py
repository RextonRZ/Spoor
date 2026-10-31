"""Motion gates on a saved scenario blend (reviewer builder notes 05:15 #2 and 05:45):

  blender -b <scenario.blend> -P assets/hub/qa_motion_gates.py -- --out <dir> [--frames 1-900]

1. Pelvis height: every worker's pelvis >= 0.6 m in every frame (a fallen / dropped rig lies on the floor); per
   worker the minimum and the frames under, "lying" if under 0.35 m (a seated break worker sits at ~0.5 m).
2. Held-object jumps (builder note 05:45): every parcel / sack / tote with the same palm within 0.30 m in two frames
   is in the hands; a jump is a slip off that palm (> 5 cm relative to it in a frame) or a teleport of hands and object
   together (> 0.25 m = 2.5 m/s, or > 30 deg). The note's literal 0.08 m / 15 deg is listed apart: a walking carry
   moves 0.12-0.15 m per frame, so world displacement alone flags every carry. Not in the hands: displacement <= the
   fastest conveyor + 20 % (on the cross-belt loop, within 0.6 m of a carrier: 2.0 m/s; elsewhere the merge belt,
   the fastest: 1.8 m/s), at 10 fps. Frames where it is hidden (either side) are skipped (spawn / leave).
Writes <dir>/motion_gates.json (+ a short summary on stdout). Exit 1 if any gate row.
"""
import argparse
import csv
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--frames", default="1-900")
ap.add_argument("--fps", type=float, default=10.0)
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
OUT = Path(a.out)
OUT.mkdir(parents=True, exist_ok=True)
F0, F1 = (int(x) for x in a.frames.split("-"))
sc = bpy.context.scene
DT = 1.0 / a.fps
V_LOOP, V_BELT = 2.0, 1.8

workers = [o for o in sc.objects if o.type == "ARMATURE" and o.name.startswith("worker_")]


def pelvis_bone(arm):
    for n in ("Bip01 Pelvis", "Hips", "mixamorig:Hips", "pelvis"):
        if n in arm.pose.bones:
            return n
    return None


def hand_bones(arm):
    return [n for n in ("Bip01 L Hand", "Bip01 R Hand", "mixamorig:LeftHand", "mixamorig:RightHand") if n in arm.pose.bones]


def animated(o):
    p = o
    while p is not None:
        if p.animation_data and (p.animation_data.action or len(p.animation_data.nla_tracks)):
            return True
        p = p.parent
    return False


objs = [o for o in sc.objects if o.type == "MESH" and animated(o) and not o.name.endswith("_label")
        and o.name.startswith(("flow_parcel_", "bag_", "sack", "tote"))]
carriers = [o for o in sc.objects if o.name.startswith("carrier_") and o.type == "MESH"]
print(f"GATES {len(workers)} workers, {len(objs)} objects, {len(carriers)} carriers", flush=True)

pel_rows = []
pel_at = []  # (frame, worker, pelvis xyz): for the in-view pass
turn_all = []  # every turn over 10 deg/frame
prev = {}
jump_rows, regrip, conv_rows, turn_rows = [], [], [], []
max_held = {}
for f in range(F0, F1 + 1):
    sc.frame_set(f)
    palms = []
    for w in workers:
        pb = pelvis_bone(w)
        if pb is not None and not w.hide_render:
            z = (w.matrix_world @ w.pose.bones[pb].head).z
            if z < 0.6:
                pel_rows.append((f, w.name, round(z, 3)))
                pv_ = w.matrix_world @ w.pose.bones[pb].head
                pel_at.append((f, w.name, [round(pv_.x, 2), round(pv_.y, 2), round(pv_.z, 2)]))
        if pb is not None and not w.hide_render and "Bip01 L Thigh" in w.pose.bones:  # whole-body turn rate
            L_, R_ = w.matrix_world @ w.pose.bones["Bip01 L Thigh"].head, w.matrix_world @ w.pose.bones["Bip01 R Thigh"].head
            hy = math.degrees(math.atan2(R_.y - L_.y, R_.x - L_.x))
            hp = prev.get("__hip__" + w.name)
            if hp is not None:
                dd_ = (hy - hp + 180) % 360 - 180
                if abs(dd_) > 10.0:  # the fastest turns at any size (builder note 0650: top 5 with crops)
                    pv_ = (L_ + R_) / 2
                    turn_all.append(dict(frame=f, worker=w.name, deg=round(dd_, 1),
                                         at=[round(pv_.x, 2), round(pv_.y, 2), round(pv_.z, 2)]))
                if abs(dd_) > 25.0:
                    pv_ = (L_ + R_) / 2
                    turn_rows.append(dict(frame=f, worker=w.name, deg=round(dd_, 1),
                                          at=[round(pv_.x, 2), round(pv_.y, 2), round(pv_.z, 2)]))
            prev["__hip__" + w.name] = hy
        for hb in hand_bones(w):
            palms.append(np.array(w.matrix_world @ w.pose.bones[hb].tail))
    palm_prev = prev.get("__palms__")
    palms = np.array(palms) if palms else np.zeros((0, 3))
    cpos = np.array([np.array(c.matrix_world.translation) for c in carriers]) if carriers else np.zeros((0, 3))
    for o in objs:
        vis = not o.hide_render and o.visible_get()
        M = o.matrix_world
        p = np.array(M.translation)
        Rm = np.array(M.to_3x3().normalized())
        near, rel = False, None
        q0 = prev.get(o.name)
        if len(palms) and palm_prev is not None and q0 is not None:
            dd = np.linalg.norm(palms - p, axis=1)
            j = int(np.argmin(dd))
            if dd[j] < 0.30 and np.linalg.norm(palm_prev[j] - q0["p"]) < 0.30:  # the same palm by it in both frames
                near = True
                rel = float(np.linalg.norm((p - q0["p"]) - (palms[j] - palm_prev[j])))
        held = near and rel is not None and rel < 0.05
        on_loop = bool(len(cpos)) and float(np.min(np.linalg.norm(cpos[:, :2] - p[:2], axis=1))) < 0.6
        q = q0
        if q is not None and vis and q["vis"]:
            d = float(np.linalg.norm(p - q["p"]))
            ang = math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(q["R"].T @ Rm) - 1) / 2))))
            row = dict(frame=f, obj=o.name, d_m=round(d, 3), rot_deg=round(ang, 1), at=[round(float(c), 2) for c in p],
                       rel_to_palm_m=(round(rel, 3) if rel is not None else None))
            pend = q.get("pending")
            if pend is not None and held:  # off the palm for a frame, back on it the next: a slip / glitch
                jump_rows.append(dict(pend, kind="slip"))
            pending = None
            if (q["held"] or held) and (d > 0.25 or ang > 30.0):  # hands and object teleported together
                jump_rows.append(dict(row, kind="teleport"))
            elif q["held"] and near and rel is not None and rel > 0.05 and d > 0.03:
                pending = row  # confirmed only if it is back with the palm next frame (else: a release)
            if q["held"] and held and (d > 0.08 or ang > 15.0):  # the note's literal 0.08 m / 15 deg
                regrip.append(row)
            if not near and not q["near"] and not q["held"]:
                lim = (V_LOOP if (on_loop or q["loop"]) else V_BELT) * 1.2 * DT
                if d > lim:
                    conv_rows.append(dict(row, limit_m=round(lim, 3), loop=on_loop))
        else:
            pending = None
        prev[o.name] = dict(p=p, R=Rm, vis=vis, held=held, near=near, loop=on_loop, pending=pending)
    prev["__palms__"] = palms
    if (f - F0) % 100 == 0:
        print(f"GATES f{f} pelvis {len(pel_rows)} held {len(jump_rows)} conveyed {len(conv_rows)}", flush=True)

# 3. piles (builder note 06:50): every 10th frame, each visible parcel at rest (not moved since the frame before):
#    floating (> 2 cm over whatever is under its base), stacked higher than its support allows (base > the non-parcel
#    surface under it + its own height + 2 cm), or over a chute bag with its top > 1.2 m
from mathutils import Vector  # noqa: E402
SPEC_ = json.loads((Path(__file__).resolve().parent / "hub_spec_lineAb.json").read_text(encoding="utf-8"))
BAGS = [(c["x"] - 0.5, c["bag_frame_y"], c["x"] + 0.5, c["bag_frame_y"] + 0.8) for c in SPEC_["machines"]["chutes"]
        if c.get("bag_frame_y") is not None]  # (the reject bin has none)
pile_rows = []
last = {}
for f in range(F0, F1 + 1, 10):
    for g_ in (f - 1, f):
        sc.frame_set(max(F0, g_))
        dg = bpy.context.evaluated_depsgraph_get()
        for o in objs:
            if not o.name.startswith("flow_parcel_"):
                continue
            ev = o.evaluated_get(dg)
            bb = [ev.matrix_world @ Vector(c) for c in o.bound_box]
            lo = min(v.z for v in bb)
            hi = max(v.z for v in bb)
            cx = sum(v.x for v in bb) / 8
            cy = sum(v.y for v in bb) / 8
            if g_ == f - 1:
                last[o.name] = (cx, cy, lo)
                continue
            q = last.get(o.name)
            vis = not o.hide_render and o.visible_get()
            if not vis or q is None or abs(q[0] - cx) + abs(q[1] - cy) + abs(q[2] - lo) > 0.003:
                continue  # moving / hidden
            # support under it: rays from its centre and 4 points 30 % in from its corners, the highest wins (one ray
            # from the centre fell between gravity rollers / between the two parcels it bridges: "floating" flags on
            # parcels at rest, hub run 4)
            xs_ = sorted(v.x for v in bb)
            ys_ = sorted(v.y for v in bb)
            pts_ = [(cx, cy)] + [(cx + (xx - cx) * 0.7, cy + (yy - cy) * 0.7) for xx in (xs_[0], xs_[-1])
                                 for yy in (ys_[0], ys_[-1])]
            z_any, z_str, sup_ = None, None, None
            for px_, py_ in pts_:
                org = Vector((px_, py_, lo + 0.01))  # from inside its own bottom (4 mm under it started below a support
                za, zs, so = None, None, None           # it rests exactly on, and read the board's underside as a gap)
                for _ in range(12):
                    ok, loc, nrm, idx, ob, M = sc.ray_cast(dg, org, Vector((0, 0, -1)), distance=5.0)
                    if not ok:
                        break
                    if ob.name == o.name or ob.name == o.name + "_label":
                        org = loc - Vector((0, 0, 1e-4))
                        continue
                    if za is None:
                        za = loc.z
                    if ob.name.startswith("flow_parcel_"):
                        org = loc - Vector((0, 0, 1e-3))
                        continue
                    zs, so = loc.z, ob.name
                    break
                if za is not None and (z_any is None or za > z_any):
                    z_any = za
                if zs is not None and (z_str is None or zs > z_str):
                    z_str, sup_ = zs, so
            h = hi - lo
            row = dict(frame=f, obj=o.name, base=round(lo, 3), top=round(hi, 3), at=[round(cx, 2), round(cy, 2)])
            if z_any is not None and lo - z_any > 0.02:
                pile_rows.append(dict(row, kind="floating", gap_m=round(lo - z_any, 3)))
            elif z_str is not None and lo > z_str + h + 0.02 and cx > 0.5 and "gaylord" not in (sup_ or ""):
                # (designed stacks are not piles: the parcel walls in the lorries, west of the dock wall, and the
                # gaylords at line B)
                pile_rows.append(dict(row, kind="stacked", over_support_m=round(lo - z_str, 3)))
            if hi > 1.2 and any(x0 <= cx <= x1 and y0 <= cy <= y1 for x0, y0, x1, y1 in BAGS):
                pile_rows.append(dict(row, kind="bag_top_over_1.2m"))
print("PILES", len(pile_rows), json.dumps(pile_rows[:10]), flush=True)

by_w = {}
for f_, wn, z in pel_rows:
    e = by_w.setdefault(wn, dict(frames=0, min_z=9.0, first=f_, last=f_))
    e["frames"] += 1
    e["min_z"] = min(e["min_z"], z)
    e["last"] = f_
for e in by_w.values():
    e["lying"] = e["min_z"] < 0.35
res = dict(frames=[F0, F1], pelvis_by_worker=by_w, pelvis_below_0_6=pel_rows, held_jumps=jump_rows, held_fast_walking_0_08=regrip,
           conveyed_over_speed=conv_rows, piles=pile_rows, turns_over_25deg=turn_rows,
           turns_fastest5=sorted(turn_all, key=lambda r: -abs(r["deg"]))[:5],
           turns_top5={w_: sorted([r for r in turn_rows if r["worker"] == w_], key=lambda r: -abs(r["deg"]))[:5]
                       for w_ in sorted({r["worker"] for r in turn_rows})},
           summary=dict(turns=len(turn_rows), piles=len(pile_rows), pelvis=len(pel_rows), held_jumps=len(jump_rows), held_fast_0_08=len(regrip), conveyed=len(conv_rows),
                        workers=len(workers), objects=len(objs)))
(OUT / "motion_gates.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
# every finding as a collision_check-style row (frame, a, b, kind, size, x, y, z): mocap/rows_in_view.py then keeps the
# ones a scenario's render cameras see (builder note 0650: the gates scoped like the collision rows)
with open(OUT / "gate_rows.csv", "w", encoding="utf-8", newline="") as fh_:
    wr_ = csv.writer(fh_)
    wr_.writerow(["frame", "a", "b", "pair_type", "depth_cm", "x", "y", "z", "bone"])
    for r_ in turn_rows:
        wr_.writerow([r_["frame"], r_["worker"], "", "gate-turn", abs(r_["deg"]), *r_["at"], ""])
    for f_, wn, at_ in pel_at:
        wr_.writerow([f_, wn, "", "gate-pelvis", "", *at_, ""])
    for r_ in jump_rows:
        wr_.writerow([r_["frame"], r_["obj"], "", "gate-held-" + r_.get("kind", "jump"), round(r_["d_m"] * 100, 1),
                      *r_["at"], ""])
    for r_ in pile_rows:
        wr_.writerow([r_["frame"], r_["obj"], "", "gate-pile-" + r_.get("kind", "pile"),
                      round(r_.get("gap_m", 0.0) * 100, 1), *r_["at"], round((r_["base"] + r_["top"]) / 2, 2), ""])
print("GATES", json.dumps(res["summary"]), flush=True)
print("PELVIS_BY_WORKER", json.dumps(by_w), flush=True)
for k in ("held_jumps", "held_fast_walking_0_08", "conveyed_over_speed"):
    print(k, json.dumps(res[k][:8]), flush=True)
sys.exit(1 if (any(e['lying'] for e in by_w.values()) or jump_rows or conv_rows or pile_rows) else 0)
