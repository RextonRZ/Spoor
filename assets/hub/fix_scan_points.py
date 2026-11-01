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


cams = sorted((o for o in bpy.data.objects if o.type == "CAMERA" and o.name.startswith("CAM_")), key=lambda o: o.name)
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
        probes = sp["device_parts_m"] or [sp["position_m"]]
        vis = []
        for cam in cams:
            ppm = max(ppm_seen(cam, p) for p in probes)
            if ppm >= OBSERVE_PPM:
                vis.append({"camera": cam.name, "ppm": round(ppm)})
        sp["visible_by"] = vis
        new_vis = [v["camera"] for v in vis]
        if old_pos != sp["position_m"] or old_vis != new_vis:
            print(f"  {sp['id']:14s} pos {old_pos} -> {sp['position_m']}" if old_pos != sp["position_m"] else f"  {sp['id']:14s}",
                  f"| seen by {old_vis} -> {new_vis}" if old_vis != new_vis else "")
    if not DRY:
        path.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("dry run" if DRY else "written")
