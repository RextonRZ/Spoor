"""Scan points against the built scene (reviewer, 1 Nov: "compare each plan scanner position with the real scanner
object"). Updates the hub spec's scan_points in place and prints every change:

- device_parts_m: where the hardware physically is, measured from the scene. RFID portals: the two antenna panels
  either side of the door (the read point moves onto their plane, centred between them); the store scan-in: its
  cradle scanner; tunnel / DWS arch: the read point, which lies inside the device. Handheld scans and sorter PLC
  events have no device by design (empty list): the scan happens in a work area or at a chute mouth.
- visible_by: re-checked in the scene for EVERY scan point (the planner's 2D estimate missed SP-STORE-IN, added to the
  spec after its check ran): in frame, inside the lens crop, a clear ray (nothing but the device itself in the way)
  and at least 62 px/m at the render size (the planner's "observe" level). A device counts as seen if any part is.

  blender -b assets/hub/build/hub_lineAb_S2_final.blend --python assets/hub/fix_scan_points.py -- [--dry-run]
"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

HUB = Path(__file__).resolve().parent
DRY = "--dry-run" in sys.argv
OBSERVE_PPM = 62
TRUTH = json.loads((HUB / "render_truth.json").read_text(encoding="utf-8"))["cameras"]
sc = bpy.context.scene
sc.frame_set(1)
dg = bpy.context.evaluated_depsgraph_get()
RX, RY = sc.render.resolution_x, sc.render.resolution_y


def parts(name):
    o = bpy.data.objects[name]
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
        out.append((Vector([min(p[i] for p in comp) for i in range(3)]), Vector([max(p[i] for p in comp) for i in range(3)])))
    bm.free()
    return out


def centre(box):
    return [round(v, 3) for v in (box[0] + box[1]) / 2]


panels = [b for b in parts("rfid_portals") if b[0].z > 1.0]  # antenna panels sit on the posts at 1.2-1.8 m


def merged_by_x(boxes, gap=0.15):
    out = []
    for lo, hi in sorted(boxes, key=lambda b: b[0].x):
        if out and lo.x <= out[-1][1].x + gap:
            out[-1] = (Vector(map(min, out[-1][0], lo)), Vector(map(max, out[-1][1], hi)))
        else:
            out.append((lo, hi))
    return out


def rect(x0, y0, x1, y1):
    return [[round(x0, 3), round(y0, 3)], [round(x1, 3), round(y0, 3)], [round(x1, 3), round(y1, 3)], [round(x0, 3), round(y1, 3)]]


def grow(lo, hi, m):
    return rect(lo[0] - m, lo[1] - m, hi[0] + m, hi[1] + m)


def obj_box(name):
    o = bpy.data.objects[name]
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return Vector([min(v[i] for v in bb) for i in range(3)]), Vector([max(v[i] for v in bb) for i in range(3)])


# Handheld scans happen in a WORK AREA, measured from what stands there (reviewer / owner, 1 Nov: the planner's single
# spots were 4-7 m off for unloading and cages). One or more floor polygons per point.
frames = merged_by_x(parts("bag_frames"))  # one bag frame per chute, at the chute's foot
bench = next(b for b in parts("fixtures") if 0.8 < b[1].z < 1.0 and b[1].x - b[0].x > 3.0
             and 20.5 < (b[0].y + b[1].y) / 2 < 23.5 and 22 < (b[0].x + b[1].x) / 2 < 28)  # the exception bench
sack_bench = [obj_box("waiting_sack_bench1_0"), obj_box("waiting_sack_bench1_1")]
wrap = obj_box("oversize_wrap")
BAYS_W, BAYS_E = (25.0, 38.0), (38.5, 51.5)  # the plan's cage bays S01-S05/S11-S15 and S06-S10/S16-S20
BAY_ROWS = ((26.0, 28.2), (29.5, 31.7))


def work_area(sp):
    """(floor polygons, the height the scan is made at). Heights are the surface the parcel or bag is on, or the
    scanner height measured in the window: bag rim 0.92 m (scans at 0.93), dock 1.10-1.25 m, cage shelf 0.66 m."""
    sid, (x, y, _z) = sp["id"], sp["position_m"]
    if sid.startswith("SP-BAG-C"):
        lo, hi = min(frames, key=lambda f: abs((f[0].x + f[1].x) / 2 - x))
        return [rect(lo.x, lo.y, hi.x, hi.y + 0.5)], round(hi.z, 2)  # the bag frame and the bagger's reach in front
    if sid in ("SP-IN-S", "SP-IN-N"):  # unloading happens in the trailer mouth at each of that side's dock doors
        ys = (7.0, 11.0, 15.0) if sid == "SP-IN-S" else (19.0, 23.0, 27.0)
        return [rect(-1.8, c - 1.5, 1.0, c + 1.5) for c in ys], 1.15
    if sid == "SP-BAGOPEN":
        lo = Vector(map(min, *[b[0] for b in sack_bench])); hi = Vector(map(max, *[b[1] for b in sack_bench]))
        return [grow(lo, hi, 0.5)], round(lo.z, 2)  # the sacks lie on the bench top
    if sid == "SP-OVERSIZE":
        return [grow(wrap[0], wrap[1], 0.5)], round(wrap[1].z, 2)
    if sid == "SP-REWORK":
        return [rect(bench[0].x, bench[0].y - 0.6, bench[1].x, bench[1].y)], round(bench[1].z, 2)  # bench + chair side
    if sid in ("SP-CAGE-W", "SP-CAGE-E"):
        x0, x1 = BAYS_W if sid == "SP-CAGE-W" else BAYS_E
        return [rect(x0, y0, x1, y1) for y0, y1 in BAY_ROWS], 0.66
    if sid.startswith("SP-LOAD-D"):
        return [rect(x - 1.5, 36.4, x + 1.5, 39.0)], 1.0  # the door apron the cage crosses (no scan in the window)
    return [], None
scanin = max(parts("scanin_scanner"), key=lambda b: (b[1] - b[0]).length)


def lens_keeps(k1, f, x, y):
    dx, dy = x - RX / 2, y - RY / 2
    r_in = math.hypot(dx, dy)
    if r_in < 1:
        return True
    t_edge = min((RX / 2) / abs(dx) if abs(dx) > 1e-9 else 1e9, (RY / 2) / abs(dy) if abs(dy) > 1e-9 else 1e9)
    ex, ey = dx * t_edge / f, dy * t_edge / f
    s = (1 - k1 * (ex * ex + ey * ey)) / (1 - k1 * (RX / 2 / f) ** 2)
    return r_in <= math.hypot(ex, ey) * f * s - 2


def ppm_seen(cam, p):
    """Pixels per metre at p if the camera truly sees it, else 0."""
    P = Vector(p)
    pc = cam.matrix_world.inverted() @ P
    if pc.z > -0.1:
        return 0
    tx = math.tan(cam.data.angle_x / 2)
    ty = tx * RY / RX
    if abs(pc.x / -pc.z) > tx or abs(pc.y / -pc.z) > ty:
        return 0
    f = RX / (2 * tx)
    if not lens_keeps(TRUTH.get(cam.name, {}).get("lens_k1", -0.06), f, RX / 2 + pc.x / -pc.z * f, RY / 2 - pc.y / -pc.z * f):
        return 0
    o = cam.matrix_world.translation
    d = P - o
    hit, loc, *_ = sc.ray_cast(dg, o, d.normalized(), distance=d.length)
    if hit and (loc - P).length > 0.35:
        return 0
    return f / -pc.z


def inside(poly, x, y):
    n, ok = len(poly), False
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            ok = not ok
    return ok


def check_work_areas(points):
    rows = [json.loads(line) for line in open(HUB / "build/sim/events_scan_simulated_S2.jsonl", encoding="utf-8") if line.strip()]
    truth = [json.loads(line) for line in open(HUB / "build/truth/events_truth_S2.jsonl", encoding="utf-8") if line.strip()]
    scanners = [o for o in bpy.data.objects if o.name.endswith("scanner") and "worker" in o.name]
    n = bad = 0
    for r, t in zip(rows, truth):
        if t.get("clock_domain") != "clkd_handheld" or t.get("true_t_s", -1) < 0 or r.get("scan_point") not in points:
            continue
        sp = points[r["scan_point"]]
        sc.frame_set(int(round(t["true_t_s"] * 10)) + 1)
        p = min((o.matrix_world.translation.copy() for o in scanners), key=lambda v: (v - Vector(sp["position_m"])).length)
        ok = any(inside(poly, p.x, p.y) for poly in sp["work_area_m"]) if sp["work_area_m"] else             (p - Vector(sp["position_m"])).length < 0.5
        n, bad = n + 1, bad + (not ok)
        if not ok:
            print(f"  OUTSIDE {r['scan_point']} at frame {sc.frame_current}: scanner {[round(v, 2) for v in p]}")
    print(f"  work-area check: {n - bad}/{n} handheld scans in the window happened inside their point's area")
    sc.frame_set(1)


cams = sorted((o for o in bpy.data.objects if o.type == "CAMERA" and o.name.startswith(("CAM_", "CHK_"))), key=lambda o: o.name)
for spec_name in ("hub_spec_lineAb.json", "hub_spec.json"):
    path = HUB / spec_name
    spec = json.loads(path.read_text(encoding="utf-8"))
    print(f"== {spec_name}")
    for sp in spec["scan_points"]:
        old_pos, old_vis = list(sp["position_m"]), [v["camera"] for v in sp.get("visible_by", [])]
        if sp["device_kind"] == "rfid_portal":
            x = sp["position_m"][0]
            left = max((b for b in panels if centre(b)[0] < x), key=lambda b: centre(b)[0])
            right = min((b for b in panels if centre(b)[0] > x), key=lambda b: centre(b)[0])
            sp["device_parts_m"] = [centre(left), centre(right)]
            sp["position_m"] = [round((centre(left)[0] + centre(right)[0]) / 2, 3), centre(left)[1], centre(left)[2]]
        elif sp["id"] == "SP-STORE-IN":
            sp["device_parts_m"] = [centre(scanin)]
        elif sp["device_kind"] == "tunnel":
            sp["device_parts_m"] = [list(sp["position_m"])]
        else:
            sp["device_parts_m"] = []
        area, height = work_area(sp) if sp["device_kind"] == "handheld" and not sp["device_parts_m"] else ([], None)
        sp["work_area_m"], sp["work_height_m"] = area, height
        if area:  # the nominal spot becomes the area's centre, at the height the scan is made
            pts = [q for poly in area for q in poly]
            sp["position_m"] = [round(sum(q[0] for q in pts) / len(pts), 3), round(sum(q[1] for q in pts) / len(pts), 3), height]
        probes = sp["device_parts_m"] or ([[q[0], q[1], height] for poly in sp["work_area_m"] for q in poly]
                                          + [sp["position_m"]] if sp["work_area_m"] else [sp["position_m"]])
        vis = []
        for cam in cams:
            got = [ppm_seen(cam, p) for p in probes]
            ok = [g for g in got if g >= OBSERVE_PPM]
            # a device counts if any part is seen; a work area only if the camera sees at least half of it
            if ok and (not sp["work_area_m"] or len(ok) * 2 >= len(probes)):
                vis.append({"camera": cam.name, "ppm": round(min(ok))})
        sp["visible_by"] = vis
        new_vis = [v["camera"] for v in vis]
        if old_pos != sp["position_m"] or old_vis != new_vis:
            print(f"  {sp['id']:14s} pos {old_pos} -> {sp['position_m']}" if old_pos != sp["position_m"] else f"  {sp['id']:14s}",
                  f"| seen by {old_vis} -> {new_vis}" if old_vis != new_vis else "")
    # check: every handheld scan in the rendered window happened inside its point's work area (scanner in hand)
    if spec_name == "hub_spec.json":
        check_work_areas({p["id"]: p for p in spec["scan_points"]})
    if not DRY:
        path.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("dry run" if DRY else "written")
