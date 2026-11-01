"""QA (render side): does each plan scan point sit on real hardware in the scene? For every read point, the small
objects (and the parts of merged device meshes) within 2 m, nearest first, with their distance to the plan position.
A fixed device (tunnel, arch, RFID antennas, store scan-in) must be within 0.25 m of its plan point; a handheld scan
or a PLC event has no device by design and is reported as such.

  blender -b assets/hub/build/hub_lineAb_S2_final.blend --python assets/hub/qa_scan_points.py -- <plan.json> <out.json>
"""
import json
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

plan_path, out_path = sys.argv[sys.argv.index("--") + 1:][:2]
plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
sc = bpy.context.scene
sc.frame_set(1)
SKIP = ("worker_", "flow_parcel", "parcel_", "bag_", "cage", "floor", "wall", "roof", "ceiling", "structure", "led_rows",
        "highbay", "mounted_fluorescent", "label", "sign", "decal", "paint", "line_", "marking", "CAM_")


def parts(o):
    """World boxes of an object's loose parts (merged meshes hold many devices)."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    seen, out = set(), []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, comp = [v], []
        seen.add(v.index)
        while stack:
            a = stack.pop()
            comp.append(o.matrix_world @ a.co)
            for e in a.link_edges:
                b = e.other_vert(a)
                if b.index not in seen:
                    seen.add(b.index)
                    stack.append(b)
        lo = Vector([min(p[i] for p in comp) for i in range(3)])
        hi = Vector([max(p[i] for p in comp) for i in range(3)])
        out.append((lo, hi))
    bm.free()
    return out


boxes = []
for o in bpy.data.objects:
    if o.type != "MESH" or not o.visible_get() or o.name.lower().startswith(tuple(s.lower() for s in SKIP)):
        continue
    for lo, hi in parts(o) if len(o.data.vertices) < 200000 else []:
        if (hi - lo).length < 1.6:  # a device-sized part, not a wall or a belt
            boxes.append((o.name, lo, hi))


def dist(p, lo, hi):
    return Vector([max(lo[i] - p[i], 0, p[i] - hi[i]) for i in range(3)]).length


out = []
for r in plan["read_points"]:
    p = Vector(r["position_m"])
    near = sorted(((dist(p, lo, hi), n, lo, hi) for n, lo, hi in boxes), key=lambda t: t[0])[:4]
    near = [{"object": n, "dist_m": round(d, 2), "centre_m": [round(v, 2) for v in (lo + hi) / 2],
             "size_m": [round(v, 2) for v in hi - lo]} for d, n, lo, hi in near if d < 2.0]
    out.append({"id": r["scan_point_id"], "kind": r["device_kind"], "plan_m": r["position_m"], "near": near})
    top = near[0] if near else None
    print(f"SP {r['scan_point_id']:14s} {r['device_kind']:11s} plan {r['position_m']}  nearest: "
          + (f"{top['object']} {top['dist_m']} m away, centre {top['centre_m']} size {top['size_m']}" if top else "nothing device-sized within 2 m"))
Path(out_path).write_text(json.dumps(out, indent=1), encoding="utf-8")
