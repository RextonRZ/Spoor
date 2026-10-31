"""Global collision check (owner rule, review 009d): nothing passes through anything, in any frame.

  blender -b --factory-startup <scenario.blend> -P assets/hub/collision_check.py -- --out <dir> [--frames 1-300]
      [--step 1] [--static-only]

Every moving thing (people = evaluated body meshes, flow parcels, sacks, pushed cages) against everything else (the
static hub and the other moving things), every frame: AABB pre-filter -> BVH surface overlap -> depth = how far the
overlapping triangles' vertices lie inside the other surface. A pair counts when the depth is >= 1 cm (touching, e.g.
a parcel resting on a belt or a palm on a carton, does not). The floor / ground / decals are left to the feet checks.
--static-only: the dressed hub at frame 1, static vs static (parked cages, racks, tables, signs, posts).

Writes <out>/collisions.csv (frame, a, b, pair_type, depth_cm, x, y, z) and <out>/collisions_summary.txt (counts by pair
type, by object pair, worst 20 frames). Exit code 1 if any hit (used by qa_gate.py).
Feet / toes touching anything below 2 cm height (floor paint lettering, door sills) count as floor contact, like the
floor itself: grounding is the feet checks' job (foot slide / sole height), not this one.
"""
import argparse
import csv
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--frames", default="1-300")
ap.add_argument("--step", type=int, default=1)
ap.add_argument("--tol", type=float, default=0.01)
ap.add_argument("--static-only", action="store_true")
ap.add_argument("--cage-rule", default="new", choices=["new", "old"])  # old: the rule before 31 Oct (comparison only)
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
OUT = Path(args.out)
OUT.mkdir(parents=True, exist_ok=True)
sc = bpy.context.scene
F0, F1 = (int(x) for x in args.frames.split("-"))
TOL = args.tol

SKIP = ("floor", "yard_", "ground", "decal", "wall_base_grime")  # surfaces feet / decals live on


def animated(o):
    p = o
    while p is not None:
        ad = p.animation_data
        if ad and (ad.action or len(ad.nla_tracks)):
            return True
        p = p.parent
    return False


def kind(o):
    n = o.name
    if n.startswith("worker_") and n.endswith("_body"):
        return "person"
    if n.startswith("flow_parcel_"):
        return "parcel"
    if "cage" in n and o.parent is None:
        return "cage"
    if args.cage_rule == "new" and o.parent is not None and "cage" in o.parent.name and o.parent.parent is None:
        return "cagepart"  # a cage's mid shelf, sacks, castors: they move with it (builder note 0415 #2)
    if n.startswith(("bag_", "sack")):
        return "sack"
    if n.startswith("carrier_"):  # the sorter's carriers: checked against the merge belts and what they meet
        return "carrier"
    return "asset"


def owner(o):
    """Worker name a mesh belongs to (its own props never count against it)."""
    p = o
    while p is not None:
        if p.type == "ARMATURE" and p.name.startswith("worker_"):
            return p.name
        p = p.parent
    return None


meshes = [o for o in sc.objects if o.type == "MESH" and not o.name.lower().startswith(SKIP)
          and not any(s in o.name.lower() for s in ("floor_", "_decal", "floor_markings"))]
moving = [o for o in meshes if animated(o) and kind(o) != "asset" or kind(o) == "person"]
static = [o for o in meshes if o not in moving and not animated(o) and owner(o) is None]
print(f"COLL {len(moving)} moving, {len(static)} static objects", flush=True)


BONE_OF = {}  # person mesh name -> [dominant vertex group per vertex]


def bones_of(o):
    if o.name not in BONE_OF:
        names = {g.index: g.name.replace("Bip01 ", "") for g in o.vertex_groups}
        BONE_OF[o.name] = [names.get(max(v.groups, key=lambda g: g.weight).group, "?") if v.groups else "?"
                           for v in o.data.vertices]
    return BONE_OF[o.name]


def bvh_aabb(o, dg):
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    M = o.matrix_world
    vs = [M @ v.co for v in me.vertices]
    tris = []
    me.calc_loop_triangles()
    for t in me.loop_triangles:
        tris.append(tuple(t.vertices))
    ev.to_mesh_clear()
    if not vs or not tris:
        return None
    lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
    hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    return BVHTree.FromPolygons(vs, tris, epsilon=0.0), lo, hi, vs, tris


def boxes_meet(a, b, pad=-0.005):
    return all(a[1][i] - pad <= b[2][i] and b[1][i] - pad <= a[2][i] for i in range(3))


def cage_depth(person, cage_ob, person_ob=None):
    """A person's vertices inside a cage's interior volume (its local box shrunk 2 cm): arms through the mesh or a body
    in the cage. The 4-5 mm wires are too thin for a surface depth >= 1 cm, so through the side / back walls this
    volume test is what counts; posts, rails and the deck are checked by their surfaces as well (person_cage).
    Only reaching in through the open front is exempt (builder note 0415 #3); hands are no longer skipped (old rule:
    every hand / finger vertex was)."""
    Mi = cage_ob.matrix_world.inverted()
    bb = cage_ob.bound_box
    lo = Vector((min(c[0] for c in bb), min(c[1] for c in bb), min(c[2] for c in bb))) + Vector((0.02, 0.02, 0.02))
    hi = Vector((max(c[0] for c in bb), max(c[1] for c in bb), max(c[2] for c in bb))) - Vector((0.02, 0.02, 0.02))
    best, at = 0.0, None
    skip = None
    if person_ob is not None and args.cage_rule == "old":  # old rule: hands round a handle post were a grip
        bo = bones_of(person_ob)
        skip = {i for i, g in enumerate(bo) if "Hand" in g or "Finger" in g}
    # a roll cage is open at its front (local -y, build_hub._cage): leaning / reaching in through that opening touches
    # nothing - a vertex inside counts only if the line from it to his pelvis does not pass through the open face
    # (S2 31 Oct: taking a carton off the cage shelf, the head 20 cm inside the opening counted as "in the cage")
    pq = None
    if args.cage_rule == "new" and person_ob is not None and person_ob.parent is not None             and "Bip01 Pelvis" in person_ob.parent.pose.bones:
        arm_ = person_ob.parent
        pq = Mi @ (arm_.matrix_world @ arm_.pose.bones["Bip01 Pelvis"].head)
        if pq.y >= lo.y:
            pq = None  # (pelvis not in front of the opening: no exemption)
    for vi in range(0, len(person[3]), 3 if args.cage_rule == "old" else 1):
        if skip and vi in skip:
            continue
        v = person[3][vi]
        q = Mi @ v
        if lo.x < q.x < hi.x and lo.y < q.y < hi.y and lo.z < q.z < hi.z:
            if pq is not None:
                t_ = (lo.y - pq.y) / (q.y - pq.y)
                xo, zo = pq.x + (q.x - pq.x) * t_, pq.z + (q.z - pq.z) * t_
                if lo.x < xo < hi.x and lo.z + 0.15 < zo < hi.z:  # through the open front (above the 0.17 m deck)
                    continue
            d = min(q.x - lo.x, hi.x - q.x, q.y - lo.y, hi.y - q.y)
            if d > best:
                best, at = d, v
                LAST_VI[0] = vi
    return best, at


def depth(A, B):
    """Deepest vertex of A's overlapping triangles inside B (signed by B's surface normal), and where."""
    pairs = A[0].overlap(B[0])
    if not pairs:
        return 0.0, None
    best, at = 0.0, None
    seen = set()
    for ia, ib in pairs[:400]:
        for vi in A[4][ia]:
            if vi in seen:
                continue
            seen.add(vi)
            v = A[3][vi]
            hit = B[0].find_nearest(v, 0.15)  # only near the other surface is the inside/outside sign trustworthy
            if hit[0] is None:
                continue
            d = -(v - hit[0]).dot(hit[1])
            if d > best:
                best, at = d, v
                LAST_VI[0] = vi
    return best, at


def depth_sampled(A, B, step=0.01):
    """Like depth(), on points every `step` over A's overlapping triangles (inside B's box) instead of A's vertices:
    a thin board through a carton has no vertex inside the other (S2 31 Oct: a carton 15 mm into the store shelf's
    1.5 cm board read 0). Used for parcels / sacks / cages, not people (their vertices are dense)."""
    pairs = A[0].overlap(B[0])
    if not pairs:
        return 0.0, None
    lo, hi = np.array(B[1]) - 0.01, np.array(B[2]) + 0.01
    best, at = 0.0, None
    for ia in sorted({p[0] for p in pairs})[:400]:
        P = np.array([A[3][i] for i in A[4][ia]])
        n = int(min(150, max(2, np.ceil(max(np.linalg.norm(P[1] - P[0]), np.linalg.norm(P[2] - P[0]),
                                            np.linalg.norm(P[2] - P[1])) / step))))
        u, v = np.meshgrid(np.arange(n + 1), np.arange(n + 1))
        m = (u + v) <= n
        u, v = u[m] / n, v[m] / n
        Q = P[0] + np.outer(u, P[1] - P[0]) + np.outer(v, P[2] - P[0])
        Q = Q[np.all((Q >= lo) & (Q <= hi), axis=1)]
        for q in Q:
            q = Vector(q)
            hit = B[0].find_nearest(q, 0.15)
            if hit[0] is None:
                continue
            d = -(q - hit[0]).dot(hit[1])
            if d > best:
                best, at = d, q
    return best, at


LAST_VI = [None]  # vertex index of the deepest vertex found by the last depth() / cage_depth() call
_KD = {}  # (frame, person) -> KDTree of its evaluated vertices


def near_bone(f, pname, P, at):
    """'~bone' of the person vertex nearest to `at` (a carton corner inside a body names the part it is in)."""
    from mathutils.kdtree import KDTree
    key = (f, pname)
    if key not in _KD:
        kd = KDTree(len(P[3]))
        for i, v in enumerate(P[3]):
            kd.insert(v, i)
        kd.balance()
        _KD.clear()
        _KD[key] = kd
    _co, vi, _d = _KD[key].find(at)
    return "~" + bones_of(sc.objects[pname])[vi]


rows = []
dg = bpy.context.evaluated_depsgraph_get()
t0 = time.time()
if args.static_only:
    sc.frame_set(F0)
    dg = bpy.context.evaluated_depsgraph_get()
    S = {o.name: bvh_aabb(o, dg) for o in static}
    S = {k: v for k, v in S.items() if v}
    names = sorted(S)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if not boxes_meet(S[a], S[b]):
                continue
            dpt, at = depth(S[a], S[b])
            d2, at2 = depth(S[b], S[a])
            if d2 > dpt:
                dpt, at = d2, at2
            if dpt >= TOL:
                rows.append((F0, a, b, "static-static", round(dpt * 100, 1), *[round(c, 2) for c in at], ""))
else:
    sc.frame_set(F0)
    dg = bpy.context.evaluated_depsgraph_get()
    S = {o.name: bvh_aabb(o, dg) for o in static}
    S = {k: v for k, v in S.items() if v}
    for f in range(F0, F1 + 1, args.step):
        sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        live = {}
        for o in moving:
            if o.hide_render or not o.visible_get():
                continue
            r = bvh_aabb(o, dg)
            if r:
                live[o.name] = (r, kind(o), owner(o))
        names = sorted(live)
        for i, a in enumerate(names):
            A, ka, oa = live[a]
            for sname, B in S.items():  # moving vs static
                if ka == "carrier" and sname.startswith(("loop", "chutes")):
                    continue  # its own deck, rails and the chute mouths it runs past
                if not boxes_meet(A, B):
                    continue
                dpt, at = depth(A, B)
                bone = bones_of(sc.objects[a])[LAST_VI[0]] if ka == "person" and dpt >= TOL else ""
                if ka != "person":  # a parcel / cage resting on something: test the other way round as well
                    d2, at2 = depth(B, A)
                    if d2 > dpt:
                        dpt, at = d2, at2
                    if dpt < TOL and ka == "parcel":  # a thin board / plate through it: its surface inside the box
                        d3, at3 = depth_sampled(B, A)
                        if d3 > dpt:
                            dpt, at = d3, at3
                if dpt >= TOL and ka == "person" and at.z < 0.02 and any(k in bone for k in ("Foot", "Toe")):
                    continue  # a sole on floor-level paint / a door sill: floor contact, left to the feet checks
                if dpt >= TOL:
                    rows.append((f, a, sname, f"{ka}-static", round(dpt * 100, 1), *[round(c, 2) for c in at], bone))
            for b in names[i + 1:]:  # moving vs moving
                Bm, kb, ob = live[b]
                if oa and oa == ob:  # a worker and its own props
                    continue
                if not boxes_meet(A, Bm):
                    continue
                bone = ""
                pa_, pb_ = sc.objects[a].parent, sc.objects[b].parent
                if "cagepart" in (ka, kb) and (pa_ is not None and pa_.name == b or pb_ is not None and pb_.name == a
                                               or ka == kb == "cagepart" and pa_ == pb_):
                    continue  # a cage and its own shelf / sacks / castors
                if {ka, kb} == {"person", "cage"}:
                    pers, cg, pn = (A, b, a) if ka == "person" else (Bm, a, b)
                    PC = Bm if ka == "person" else A
                    dpt, at = cage_depth(pers, sc.objects[cg], sc.objects[pn])
                    bone = bones_of(sc.objects[pn])[LAST_VI[0]] if dpt >= TOL else ""
                    if args.cage_rule == "new":  # + its posts, rails, deck by their surfaces, open front or not
                        d2, at2 = depth(pers, PC)
                        if d2 > dpt:
                            dpt, at = d2, at2
                            bone = bones_of(sc.objects[pn])[LAST_VI[0]] if dpt >= TOL else ""
                elif "cage" in (ka, kb):  # a bag / parcel in a cage is where it belongs; wires are not a volume
                    continue
                else:
                    dpt, at = depth(A, Bm)
                    if ka == "person" and dpt >= TOL:
                        bone = bones_of(sc.objects[a])[LAST_VI[0]]
                    elif kb == "person" and dpt >= TOL:  # a's vertex inside the person b
                        bone = near_bone(f, b, Bm, at)
                    d2, at2 = depth(Bm, A)
                    if d2 > dpt:
                        dpt, at = d2, at2
                        bone = bones_of(sc.objects[b])[LAST_VI[0]] if kb == "person" else ""
                        if ka == "person" and dpt >= TOL:  # the other's vertex is inside this person
                            bone = near_bone(f, a, A, at)
                if dpt >= TOL:
                    rows.append((f, a, b, "-".join(sorted((ka, kb))), round(dpt * 100, 1), *[round(c, 2) for c in at],
                                 bone))
        if (f - F0) % 30 == 0:
            print(f"COLL f{f} hits so far {len(rows)} ({time.time() - t0:.0f}s)", flush=True)

with open(OUT / "collisions.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["frame", "a", "b", "pair_type", "depth_cm", "x", "y", "z", "bone"])
    w.writerows(rows)
by_type = Counter(r[3] for r in rows)
by_pair = Counter((r[1], r[2]) for r in rows)
deep = defaultdict(float)
for r in rows:
    deep[(r[1], r[2])] = max(deep[(r[1], r[2])], r[4])
worst = sorted(rows, key=lambda r: -r[4])[:20]
lines = [f"Collision check (owner rule): {len(rows)} hits >= {TOL * 100:.0f} cm, frames {F0}-{F1} step {args.step}",
         "", "By pair type (frame-hits):"] + [f"  {k:22s} {v}" for k, v in by_type.most_common()]
lines += ["", "By object pair (frames, max depth cm):"] + [f"  {a} | {b}: {n} frames, {deep[(a, b)]:.1f} cm"
                                                             for (a, b), n in by_pair.most_common(60)]
bone_ct = Counter((r[1] if "body" in r[1] else r[2], r[8]) for r in rows if r[8])
lines += ["", "Person hits by body part (frames):"] + [f"  {w_} {b_}: {n}" for (w_, b_), n in bone_ct.most_common(40)]
lines += ["", "Worst 20:"] + [f"  f{r[0]} {r[1]} | {r[2]} {r[4]} cm at ({r[5]}, {r[6]}, {r[7]})" for r in worst]
(OUT / "collisions_summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"COLL done: {len(rows)} hits in {time.time() - t0:.0f}s", flush=True)
sys.exit(1 if rows else 0)
