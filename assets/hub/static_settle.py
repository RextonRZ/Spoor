"""Loose static items (cartons, mailers, cage loads, lorry fill) resting on something (zone audit 1 Nov: cartons with
air under them in cages, mailers 4 cm over a table, a carton at 0.9 m over the floor where a bench had been, chute
sacks filled with a top layer only). Run after dress_hub.py (rebuild_lineAb.sh), and on run blends by touchup_final.py.

Support = a horizontal surface of anything else - another object, or another item of the same merged mesh - from 3.5 cm
under the item's bottom to 3 cm over it (sunk into its bench / deck: resting - the collision check reports the sinking;
a 5 mm window read mailers sunk 7 mm into a bench as unsupported and dropped them 4 cm into it) over its footprint (5 x 5 points, a mesh lookup: stacked cartons share the plane where they touch).
An item counts as supported only when its support chains down to something fixed (overlapping cartons held each other
up: a pile on nothing passed one by one). An unsupported item:
- in a container (a chute sack, the rework bin): plain cartons fill under it down to the container (the pile's top -
  what is seen, what falling parcels land on - stays where it is);
- more than 0.5 m over what is under it: taken out (nothing it could have slid down onto);
- otherwise lowered onto what is under it (the items on it follow on the next pass).

  blender -b <blend> -P assets/hub/static_settle.py -- [--save <out>] [--report <json>]   (zone_audit.py: unsupported())
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

HUB = Path(__file__).resolve().parent
LOOSE = ("parcels_static_merged", "cage_loads_merged", "clutter_procedural", "truck_fill")  # (sacks hang on hooks)
SKIP = ("worker_", "flow_parcel_", "carrier_", "cage_rolling", "bag_C07", "dws_monitor", "scanin", "SCANNER")
MAX_DROP = 0.5
CONTAINERS = ("sacks_merged", "reject_bin", "bag_")


class World:
    """World-space BVHs of the static meshes (built on demand) and their boxes."""

    def __init__(self, sc):
        from mathutils import Vector
        self.objs = [o for o in sc.objects if o.type == "MESH" and not o.hide_render and not o.name.startswith(SKIP)
                     and not (o.animation_data and o.animation_data.action)]
        self.bb, self.trees = {}, {}
        for o in self.objs:
            bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
            self.bb[o.name] = ([min(v[i] for v in bb) for i in range(3)], [max(v[i] for v in bb) for i in range(3)])

    def tree(self, o):
        from mathutils.bvhtree import BVHTree
        if o.name not in self.trees:
            M = o.matrix_world
            self.trees[o.name] = BVHTree.FromPolygons([M @ v.co for v in o.data.vertices],
                                                      [p.vertices[:] for p in o.data.polygons])
        return self.trees[o.name]

    def forget(self, o):
        self.trees.pop(o.name, None)

    def near(self, xs, ys, z0, z1):
        return [o for o in self.objs if (lambda a, b: a[0] < max(xs) and b[0] > min(xs) and a[1] < max(ys)
                                         and b[1] > min(ys) and a[2] < z1 and b[2] > z0)(*self.bb[o.name])]


def islands(o):
    """(vertex lists, polygon -> island) of a merged mesh: its loose parts (an item's own faces)."""
    me = o.data
    adj = defaultdict(set)
    for e in me.edges:
        adj[e.vertices[0]].add(e.vertices[1])
        adj[e.vertices[1]].add(e.vertices[0])
    v_isl, isls = [-1] * len(me.vertices), []
    for v0 in range(len(me.vertices)):
        if v_isl[v0] >= 0:
            continue
        st, isl = [v0], []
        v_isl[v0] = len(isls)
        while st:
            i = st.pop()
            isl.append(i)
            for j in adj[i]:
                if v_isl[j] < 0:
                    v_isl[j] = len(isls)
                    st.append(j)
        isls.append(isl)
    return isls, [v_isl[p.vertices[0]] for p in me.polygons]


def _grid(xs, ys):
    for i in range(5):
        for j in range(5):
            yield min(xs) + (max(xs) - min(xs)) * (0.1 + 0.2 * i), min(ys) + (max(ys) - min(ys)) * (0.1 + 0.2 * j)


def supporters(W, o, k, poly_isl, xs, ys, lo):
    """What holds the item up: {(object name, island)} - island -1 for anything but the item's own merged mesh."""
    from mathutils import Vector
    out = set()
    cands = W.near(xs, ys, lo - 0.04, lo + 0.035)
    for x, y in _grid(xs, ys):
        q = Vector((x, y, lo - 0.002))
        for o2 in cands:
            loose2 = o2.name.startswith(LOOSE)
            for co, no, idx, _d in W.tree(o2).find_nearest_range(q, 0.035):
                # under its own footprint (a neighbour's top beside it is no support), facing up - or either way on a
                # fixed object (single-sided sack / table surfaces); never another loose item's bottom (two items
                # hovering side by side held each other up)
                if (lo - 0.035 <= co.z <= lo + 0.03 and min(xs) - 0.003 <= co.x <= max(xs) + 0.003
                        and min(ys) - 0.003 <= co.y <= max(ys) + 0.003 and (no.z > 0.5 or (not loose2 and no.z < -0.5))
                        and not (o2 is o and poly_isl[idx] == k)):
                    out.add((o2.name, poly_isl[idx] if o2 is o else -1))
    return out


def unsupported(W, o):
    """(items, islands, poly -> island, [(item, the islands of o it may not stand on)]): the items of o whose support
    does not reach anything fixed. Overlapping cartons hold each other up: a pile on nothing (Z02, between the benches,
    0.9 m over the floor) passed one by one - here every item must chain down to a fixed object, the floor or an item
    of another mesh."""
    its, isls, poly_isl = items(o)
    judged = {it[0] for it in its}
    sup = {it[0]: supporters(W, o, it[0], poly_isl, it[4], it[5], it[2]) for it in its}
    grounded = {k for k, ss in sup.items() if any(n != o.name or j not in judged for n, j in ss)}
    grow = True
    while grow:
        grow = False
        for k, ss in sup.items():
            if k not in grounded and any(n == o.name and j in grounded for n, j in ss):
                grounded.add(k)
                grow = True
    free = {k for k in sup if k not in grounded}
    return its, isls, poly_isl, [(it, free) for it in its if it[0] in free]


def under(W, o, k, poly_isl, xs, ys, lo, skip=()):
    """Highest horizontal surface under the footprint (z, object name), anything but the item itself, from 3 cm over its
    bottom down (only called for an item unsupported() found nothing fixed under)."""
    from mathutils import Vector
    best = (0.0, "floor")
    cands = W.near(xs, ys, -0.5, lo)
    for x, y in _grid(xs, ys):
        for o2 in cands:
            org = Vector((x, y, lo + 0.03))
            for _ in range(20):
                loc, no, idx, d = W.tree(o2).ray_cast(org, Vector((0, 0, -1)), 5.0)
                if loc is None:
                    break
                if (no.z > 0.5 or (not o2.name.startswith(LOOSE) and no.z < -0.5)) and not (
                        o2 is o and (poly_isl[idx] == k or poly_isl[idx] in skip)):
                    if loc.z > best[0]:
                        best = (loc.z, o2.name)
                    break
                org = loc - Vector((0, 0, 1e-4))
    return best


def in_sack(spec, x, y):
    return any(c["x"] - 0.5 <= x <= c["x"] + 0.5 and c["bag_frame_y"] <= y <= c["bag_frame_y"] + 0.8
               for c in spec["machines"]["chutes"] if c.get("bag_frame_y") is not None)


def items(o):
    """The loose items of a merged mesh to judge: [(island, vertex ids, lo, hi, xs, ys)]. Thin pieces (labels, tape
    strips) count in the carton meshes - a label left in the air when its carton went is a defect - but not in the cage
    loads (their wires / rods hang from their ends)."""
    M = o.matrix_world
    isls, poly_isl = islands(o)
    out = []
    for k, isl in enumerate(isls):
        pts = [M @ o.data.vertices[i].co for i in isl]
        lo, hi = min(p.z for p in pts), max(p.z for p in pts)
        xs, ys = [p.x for p in pts], [p.y for p in pts]
        if not (0.05 < lo < 2.2) or hi > 3.2 or len(isl) < 4:
            continue
        if min(max(xs) - min(xs), max(ys) - min(ys), hi - lo) < 0.025 and o.name.startswith("cage_loads"):
            continue
        out.append((k, isl, lo, hi, xs, ys))
    return out, isls, poly_isl


def attached(it, all_items):
    """An item's own parts - they move / go with it: inside its footprint (+1.5 cm) and thin (a label, tape: under
    1.2 cm through), lying on its top (within 1 cm), or the same box (a carton built of equal pieces). A carton standing
    through a mailer is not the mailer's: it is another item."""
    k, isl, lo, hi, xs, ys = it
    out = []
    for j, isl2, lo2, hi2, xs2, ys2 in all_items:
        if j == k or not (min(xs2) >= min(xs) - 0.015 and max(xs2) <= max(xs) + 0.015 and min(ys2) >= min(ys) - 0.015
                          and max(ys2) <= max(ys) + 0.015 and lo - 0.005 <= lo2 <= hi + 0.01):
            continue
        flat = hi2 - lo2 < 0.012  # a label / tape on its top - on THIS item's top (an overlapping mailer's label inside
        # a carton's footprint is the mailer's: it went 30 cm with the carton, 1 Nov)
        side = min(max(xs2) - min(xs2), max(ys2) - min(ys2)) < 0.012 and min(
            abs(min(xs2) - min(xs)), abs(max(xs2) - max(xs)), abs(min(ys2) - min(ys)), abs(max(ys2) - max(ys))) < 0.012
        thin = (flat and abs(lo2 - hi) < 0.012) or side
        same = all(abs(a_ - b_) < 0.005 for a_, b_ in ((min(xs2), min(xs)), (max(xs2), max(xs)), (min(ys2), min(ys)),
                                                          (max(ys2), max(ys)), (lo2, lo), (hi2, hi)))
        if thin or lo2 >= hi - 0.01 or (same and len(isl2) <= len(isl)):
            out.append(j)
    return out


def settle(sc, spec, passes=12, log=print):
    """Settle every loose item (see the module text). Returns the report rows."""
    import bmesh
    from mathutils import Matrix, Vector
    W = World(sc)
    rep = []
    for ps in range(passes):
        moved = 0
        for o in [o for o in W.objs if o.name.startswith(LOOSE)]:
            M, Mi = o.matrix_world, o.matrix_world.inverted()
            its, isls, poly_isl, bad = unsupported(W, o)
            todo = []
            for it, free in sorted(bad, key=lambda t: -len(t[0][1])):  # (biggest first: a carton before its label)
                k, isl, lo, hi, xs, ys = it
                z_, on = under(W, o, k, poly_isl, xs, ys, lo, free)
                box = (min(xs), max(xs), min(ys), max(ys))
                # in a container the animation drops parcels into (a chute sack, the rework bin): filled under, its top -
                # what falling parcels land on - stays; elsewhere lowered, or taken out when there is nothing it could
                # have slid down onto
                act = "fill" if (on.startswith(CONTAINERS) or in_sack(spec, (box[0] + box[1]) / 2, (box[2] + box[3]) / 2))                     else ("remove" if lo - z_ > MAX_DROP else "lower")
                todo.append(dict(k=k, act=act, lo=lo, gap=lo - z_, z=z_, box=box, on=on, att=attached(it, its)))
            # bottom-up: an item over another one moving this pass waits for the next (it was measured to where that one
            # was: two stacked cartons dropped by their own gaps ended 1-2 cm apart)
            def over_mover(t):  # (fills too: one fill per stack, under its lowest item first)
                return t["act"] != "remove" and any(
                    u is not t and u["act"] != "remove" and u["lo"] < t["lo"] - 0.01 and u["box"][0] < t["box"][1]
                    and u["box"][1] > t["box"][0] and u["box"][2] < t["box"][3] and u["box"][3] > t["box"][2] for u in todo)
            todo = [t for t in todo if not over_mover(t)]
            if not todo:
                continue
            bm = bmesh.new()
            bm.from_mesh(o.data)
            bm.verts.ensure_lookup_table()
            dead, done = [], set()
            card = next((i for i, m in enumerate(o.data.materials) if m and m.name.startswith("cardboard")), 0)
            for t in todo:
                if t["k"] in done:
                    continue  # (moved / gone with the item it lies on)
                group = [j for j in [t["k"]] + t["att"] if j not in done]
                done.update(group)
                x0, x1, y0, y1 = t["box"]
                rep.append(dict(pass_=ps, obj=o.name, at=[round((x0 + x1) / 2, 2), round((y0 + y1) / 2, 2), round(t["lo"], 3)],
                                action=t["act"], gap_cm=round(t["gap"] * 100, 1), over=t["on"], with_parts=len(group) - 1))
                if t["act"] == "lower":
                    for j in group:
                        for i in isls[j]:
                            bm.verts[i].co = Mi @ (M @ bm.verts[i].co - Vector((0, 0, t["gap"])))
                elif t["act"] == "remove":
                    dead += [bm.verts[i] for j in group for i in isls[j]]
                else:  # a plain carton (cardboard) under it, 6 % inside its footprint
                    cx, cy, w, d = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) * 0.88, (y1 - y0) * 0.88
                    r = bmesh.ops.create_cube(bm, size=1.0, matrix=Mi @ Matrix.Translation(
                        (cx, cy, t["z"] + t["gap"] / 2)) @ Matrix.Diagonal((w, d, t["gap"] - 0.002, 1)))
                    for f in {f for v in r["verts"] for f in v.link_faces}:
                        f.material_index = card
                    bm.verts.ensure_lookup_table()  # (new verts go on the end: the items' indices hold)
                moved += 1
            if dead:
                bmesh.ops.delete(bm, geom=dead, context="VERTS")
            bm.to_mesh(o.data)
            bm.free()
            o.data.update()
            W.forget(o)
        log(f"SETTLE pass {ps}: {moved} items")
        if not moved:
            break
    return rep


def separate_on_benches(sc, spec, log=print):
    """Items standing on a bench (spec fixtures.benches) that run into each other (randomly placed: a carton through a
    mailer, two cartons inside each other on bag-opening bench 2 - zone audit 1 Nov): the smaller one, with its labels /
    tape, moves to the nearest free spot on the same bench (5 cm grid, 6 cm in from the edges, 2.5 cm apart). Returns
    the report rows."""
    import bmesh
    from mathutils import Vector
    o = sc.objects.get("parcels_static_merged")
    if o is None:
        return []
    M, Mi = o.matrix_world, o.matrix_world.inverted()
    its, isls, poly_isl = items(o)
    rep = []
    for b in spec["fixtures"]["benches"]:
        x0, y0, x1, y1 = b["rect_m"]
        h = b["height_m"]
        on, parts, claimed = [], {}, set()
        for it in sorted([it for it in its if abs(it[2] - h) < 0.012 and x0 < (min(it[4]) + max(it[4])) / 2 < x1
                          and y0 < (min(it[5]) + max(it[5])) / 2 < y1 and it[3] - it[2] > 0.02],
                         key=lambda t: -len(t[1])):  # (biggest first: its labels / equal pieces are its own)
            if it[0] in claimed:
                continue
            parts[it[0]] = attached(it, its)
            claimed.update([it[0]] + parts[it[0]])
            on.append(it)
        rect = {it[0]: [min(it[4]), min(it[5]), max(it[4]), max(it[5])] for it in on}

        def hit(r, k, pad=0.025):
            return [j for j, q in rect.items() if j != k and r[0] < q[2] + pad and q[0] < r[2] + pad
                    and r[1] < q[3] + pad and q[1] < r[3] + pad]
        moves = {}
        for it in sorted(on, key=lambda t: (max(t[4]) - min(t[4])) * (max(t[5]) - min(t[5]))):  # smallest first
            k = it[0]
            r = rect[k]
            if not hit(r, k, 0.0):
                continue
            w, d = r[2] - r[0], r[3] - r[1]
            best = None
            for ix in range(int((x1 - x0) / 0.05) + 1):
                for iy in range(int((y1 - y0) / 0.05) + 1):
                    nx, ny = x0 + 0.06 + ix * 0.05, y0 + 0.06 + iy * 0.05
                    if nx + w > x1 - 0.06 or ny + d > y1 - 0.06:
                        continue
                    q = [nx, ny, nx + w, ny + d]
                    if hit(q, k):
                        continue
                    dd = (nx - r[0]) ** 2 + (ny - r[1]) ** 2
                    if best is None or dd < best[0]:
                        best = (dd, nx - r[0], ny - r[1])
            if best is None:
                log(f"SEPARATE no free spot for an item on {b['name']}")
                continue
            moves[k] = (best[1], best[2])
            rect[k] = [r[0] + best[1], r[1] + best[2], r[2] + best[1], r[3] + best[2]]
            rep.append(dict(bench=b["name"], at=[round((r[0] + r[2]) / 2, 2), round((r[1] + r[3]) / 2, 2)],
                            move_cm=[round(best[1] * 100, 1), round(best[2] * 100, 1)], with_parts=len(parts[k])))
        if moves:
            bm = bmesh.new()
            bm.from_mesh(o.data)
            bm.verts.ensure_lookup_table()
            for k, (dx, dy) in moves.items():
                for j in [k] + parts[k]:
                    for i in isls[j]:
                        bm.verts[i].co = Mi @ (M @ bm.verts[i].co + Vector((dx, dy, 0)))
            bm.to_mesh(o.data)
            bm.free()
            o.data.update()
            its, isls, poly_isl = items(o)
    return rep


if __name__ == "__main__":
    import bpy
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", default="")  # (none: report only)
    ap.add_argument("--report", default="")
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    spec = json.loads((HUB / "hub_spec_lineAb.json").read_text(encoding="utf-8"))
    rows = settle(bpy.context.scene, spec, log=lambda s: print(s, flush=True))
    rows += [dict(r, action="separate") for r in separate_on_benches(bpy.context.scene, spec, log=lambda s: print(s, flush=True))]
    for r in rows:
        print("SETTLE", json.dumps(r), flush=True)
    if a.report:
        Path(a.report).write_text(json.dumps(rows, indent=1), encoding="utf-8")
    if a.save:
        bpy.ops.wm.save_as_mainfile(filepath=str(Path(a.save).resolve()), compress=True)
