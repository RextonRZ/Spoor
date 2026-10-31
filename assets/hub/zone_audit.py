"""Zone-by-zone geometry audit of the hub (Rexton 1 Nov, from the locator review: gaps, transfers, chute outlets, floating
items). Read only - nothing is changed or saved. Every finding carries its zone (hub_spec zones), object and position.

  blender -b <scene.blend> -P assets/hub/zone_audit.py -- --belts <belts.json> --out <dir>
     belts.json: flow.py --dump-belts (the simulation's own belt paths: a gap there is a parcel riding over nothing)
Writes <dir>/audit.json and <dir>/defects.md. Static-vs-static intersections: collision_check.py --static-only.
"""
import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import bpy
from mathutils import Vector

HUB = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--belts", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
sc = bpy.context.scene
sc.frame_set(1)
dg = bpy.context.evaluated_depsgraph_get()
SPEC = json.loads((HUB / "hub_spec_lineAb.json").read_text(encoding="utf-8"))
ZONES = [(z["id"], z["name"], pp) for z in SPEC["zones"]  # (the yard is several parts)
         for pp in (z["polygon_m"].values() if isinstance(z["polygon_m"], dict) else [z["polygon_m"]])]
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
find = []


def zone_of(x, y):
    for zid, name, poly in ZONES:
        inside = False
        for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
            if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                inside = not inside
        if inside:
            return zid
    return "outside zones"


def add(kind, zone, obj, at, detail, sev="fix"):
    find.append(dict(kind=kind, zone=zone, object=obj, at=[round(v, 2) for v in at], detail=detail, severity=sev))


def down(x, y, z, skip=(), up_only=False):
    """First surface under (x, y, z); up_only: only faces looking up (a ray starting inside a box - a lid or tape strip
    lying on a carton - passes its bottom face from inside, which is not a support)."""
    o = Vector((x, y, z))
    for _ in range(8):
        ok, loc, n, i, ob, M = sc.ray_cast(dg, o, Vector((0, 0, -1)), distance=5.0)
        if not ok:
            return None, None
        if ob.name in skip or ob.name.startswith(("worker_", "flow_parcel_", "carrier_")) or (up_only and n.z <= 0.1):
            o = loc - Vector((0, 0, 1e-3))
            continue
        return ob.name, loc.z
    return None, None


# 1-2. belts: runs of path points with no belt under them; transfers to the next belt
B = json.loads(Path(a.belts).read_text(encoding="utf-8"))
gp = defaultdict(list)
for bn, x, y in B["gaps"]:
    gp[bn].append((x, y))
for bn, pts in gp.items():
    runs, cur = [], [pts[0]]
    for q in pts[1:]:
        if math.dist(q, cur[-1]) <= 0.15:
            cur.append(q)
        else:
            runs.append(cur)
            cur = [q]
    runs.append(cur)
    for r in runs:
        ln = max(0.1, sum(math.dist(p, q) for p, q in zip(r, r[1:])) + 0.1)
        mid = r[len(r) // 2]
        designed = bn == "merge" and ln > 0.5  # merge -> carrier: the belt stops at the carriers' band by design
        add("belt gap", zone_of(*mid), f"belt '{bn}' (conveyors)", (*mid, 0.0),
            f"{ln:.1f} m of its path ({r[0][0]:.2f},{r[0][1]:.2f})-({r[-1][0]:.2f},{r[-1][1]:.2f}) has no belt surface under"
            + (" (partly the designed hand-over onto the carriers; the part where parcels wait must have a belt)" if designed else ""),
            "check" if designed else "fix")
for bn, b in B["belts"].items():
    nx = b.get("nxt")
    if not nx or nx not in B["belts"] or not b["pts"]:
        continue
    e = b["pts"][-1]
    nb = B["belts"][nx]["pts"]
    j = min(nb, key=lambda q: math.dist(q[:2], e[:2]))
    dxy, dz = math.dist(j[:2], e[:2]), j[2] - e[2]
    if False and (dxy > 0.12 or abs(dz) > 0.03):  # (superseded by 2b: side entries read as "45 cm across")
        add("transfer", zone_of(*e[:2]), f"belt '{bn}' -> '{nx}'", e,
            f"end to the next belt: {dxy * 100:.0f} cm across, {dz * 100:+.0f} cm up/down")

# 2b. physical transfer path: from each belt's last 0.3 m across onto the belt it feeds (to that belt's centre line),
# rays at 3 points across a 0.3 m parcel: no surface (a gap > 3 cm wide), a step (> 2 cm) or anything standing over
# the belt top in the way (a side frame across the hand-over)
TRANSFERS = []
for bn, b in B["belts"].items():
    nx = b.get("nxt")
    if not nx or nx not in B["belts"] or len(b["pts"]) < 4:
        continue
    e, e0 = Vector(b["pts"][-1]), Vector(b["pts"][-4])
    j = Vector(min(B["belts"][nx]["pts"], key=lambda q: math.dist(q[:2], b["pts"][-1][:2])))
    d = (j - e0).xy
    if d.length < 1e-6:
        continue
    u, n = d.normalized(), Vector((-d.y, d.x)).normalized()
    top = max(e.z, j.z)
    worst_gap, worst_step, blocked = 0.0, 0.0, []
    for k in range(int(d.length / 0.02) + 1):
        c = e0.xy + u * k * 0.02
        for off in (-0.15, 0.0, 0.15):
            q = c + n * off
            name, z = down(q.x, q.y, top + 0.6)
            if z is None or z < top - 0.10:
                worst_gap += 0.02 / 3
            elif z > top + 0.02:
                blocked.append((name, round(z - top, 3), [round(q.x, 2), round(q.y, 2)]))
            elif abs(z - top) > 0.02:
                worst_step = max(worst_step, abs(z - top))
    TRANSFERS.append(dict(belt=bn, to=nx, gap_m=round(worst_gap, 3), step_m=round(worst_step, 3), blocked=blocked[:6]))
    if worst_gap > 0.03 or blocked or worst_step > 0.02:
        add("transfer path", zone_of(*e.xy), f"belt '{bn}' -> '{nx}'", e,
            f"no surface over {worst_gap * 100:.0f} cm; step {worst_step * 100:.0f} cm; in the way: "
            f"{sorted({x[0] for x in blocked}) or 'nothing'} (up to {max([x[1] for x in blocked], default=0) * 100:.0f} cm over the belt)")

# 3. chute outlets: what is under each chute's end (its bag / the rework bin)
for c in SPEC["machines"]["chutes"]:
    ex, ey, lz = c["x"], c["end_y"], c["lip_z"]
    hits = [down(ex + dx, ey + dy, lz + 0.5) for dx in (-0.2, 0.0, 0.2) for dy in (0.1, 0.3)]
    names = sorted({h[0] for h in hits if h[0]})
    target = "reject_bin" if c["id"] == "REJECT" else ("sack", "bag_")
    ok = any(any(t in (n or "") for t in ((target,) if isinstance(target, str) else target)) or "parcels_static" in (n or "")
             for n in names)
    if not ok:
        add("chute outlet", zone_of(ex, ey), f"chute {c['id']}", (ex, ey, lz),
            f"under its end: {names or 'nothing'} (no bag / bin to discharge into)")

# 4. floating static pieces: loose items with nothing within 3.5 cm under their footprint (static_settle.py's test:
# a mesh lookup, not rays - stacked cartons share the plane where they touch, a ray stepping past the upper one's bottom
# skipped the lower one's top: 176 false floats in a lorry)
sys.path.insert(0, str(HUB))
import static_settle  # noqa: E402
W = static_settle.World(sc)
for o in [o for o in W.objs if o.name.startswith(static_settle.LOOSE)]:
    its, isls, poly_isl, bad = static_settle.unsupported(W, o)
    for (k_, isl, lo, hi, xs, ys), free in bad:
        z_, on = static_settle.under(W, o, k_, poly_isl, xs, ys, lo, free)
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        add("floating", zone_of(cx, cy), o.name, (cx, cy, lo),
            f"a piece ({max(xs) - min(xs):.2f} x {max(ys) - min(ys):.2f} x {hi - lo:.2f} m) {(lo - z_) * 100:.0f} cm over "
            f"{on} (nothing within 3.5 cm under its footprint)")

(out / "audit.json").write_text(json.dumps(find, indent=1), encoding="utf-8")
(out / "transfers.json").write_text(json.dumps(TRANSFERS, indent=1), encoding="utf-8")
by = defaultdict(list)
for f_ in find:
    by[f_["zone"]].append(f_)
lines = ["# Hub zone audit (read only)", ""]
for zid, name in list(dict.fromkeys((z_[0], z_[1]) for z_ in ZONES)) + [("outside zones", "")]:
    rows = by.get(zid, [])
    lines.append(f"## {zid} {name} - {len(rows)} finding(s)")
    for r in rows:
        lines.append(f"- [{r['severity']}] {r['kind']}: {r['object']} at {r['at']} - {r['detail']}")
    lines.append("")
(out / "defects.md").write_text("\n".join(lines), encoding="utf-8")
print("AUDIT", len(find), "findings", json.dumps({k: len(v) for k, v in by.items()}), flush=True)
