"""QA (render side): where test points TRULY land in each CCTV frame, from Blender's own cameras and the CCTV lens, so
Spoor's calibrated projection can be scored in pixels (backend/scripts/score_calibration.py). Test points per camera:
every scan point at its plan height, the store door (BLIND_NW's entrance gap) at floor and 2 m, a 2 m floor grid,
and the footprint of the cage that holds the story parcel at frame 1. Each point says if it is in frame and if the
camera actually sees it (ray from the camera reaches it).

  blender -b assets/hub/build/hub_lineAb_S2_final.blend --python assets/hub/qa_calibration.py -- <plan.json> <out.json>
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HUB = Path(__file__).resolve().parent
plan_path, out_path = sys.argv[sys.argv.index("--") + 1:][:2]
plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
TRUTH = json.loads((HUB / "render_truth.json").read_text(encoding="utf-8"))["cameras"]
story = json.loads((HUB / "build/truth/scenario_S2.json").read_text(encoding="utf-8"))["story_object"]
sc = bpy.context.scene
W, H = 1920, 1086
RX, RY = sc.render.resolution_x, sc.render.resolution_y

sc.frame_set(1)
dg = bpy.context.evaluated_depsgraph_get()
sp = bpy.data.objects[story].matrix_world.translation.copy()


def box(o):
    bb = [o.evaluated_get(dg).matrix_world @ Vector(c) for c in o.bound_box]
    return [min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb), max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)]


cage = None
for o in bpy.data.objects:
    if o.type == "MESH" and o.name.startswith("cage") and o.visible_get():
        b = box(o)
        one_cage = b[3] - b[0] < 1.6 and b[4] - b[1] < 1.6  # not a merged mesh of every cage's load
        if one_cage and b[0] - 0.05 <= sp.x <= b[3] + 0.05 and b[1] - 0.05 <= sp.y <= b[4] + 0.05 and b[2] < 0.3 and b[5] > sp.z:
            if cage is None or (b[3] - b[0]) * (b[4] - b[1]) > (cage[1][3] - cage[1][0]) * (cage[1][4] - cage[1][1]):
                cage = (o.name, b)
pts = [(r["scan_point_id"], r["position_m"]) for r in plan["read_points"]]
pts += [("store_door_W_floor", [13.4, 33.6, 0.0]), ("store_door_E_floor", [15.2, 33.6, 0.0]),
        ("store_door_W_2m", [13.4, 33.6, 2.0]), ("store_door_E_2m", [15.2, 33.6, 2.0])]
if cage:
    b = cage[1]
    pts += [(f"cage_{i}", [x, y, 0.0]) for i, (x, y) in enumerate(((b[0], b[1]), (b[3], b[1]), (b[3], b[4]), (b[0], b[4])))]
pts += [(f"floor_{x}_{y}", [float(x), float(y), 0.0]) for x in range(0, 60, 2) for y in range(0, 42, 2)]


def distort(xs, ys, k1, f):
    edge = (RX / 2 / f) ** 2
    xo, yo = xs, ys
    for _ in range(30):
        s = (1 - k1 * (xo * xo + yo * yo)) / (1 - k1 * edge)
        xo, yo = xs / s, ys / s
    return xo, yo


out = {"cage": cage, "cameras": {}}
for cam in sorted((o for o in bpy.data.objects if o.type == "CAMERA" and o.name.startswith("CAM_")), key=lambda o: o.name):
    k1 = TRUTH.get(cam.name, {}).get("lens_k1", -0.06)
    f = RX / (2 * math.tan(cam.data.angle_x / 2))
    inv = cam.matrix_world.inverted()
    o = cam.matrix_world.translation
    rows = []
    for name, p in pts:
        P = Vector(p)
        pc = inv @ P
        if pc.z > -0.1:
            continue
        xo, yo = distort(pc.x / -pc.z, -pc.y / -pc.z, k1, f)
        u, v = (xo * f + RX / 2) * W / RX, (yo * f + RY / 2) * H / RY
        if not (0 <= u <= W and 0 <= v <= H):
            continue
        d = P - o
        hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, o, d.normalized(), distance=d.length)
        seen = not hit or (loc - P).length < 0.35  # nothing in the way (or the hit is the device itself)
        rows.append({"id": name, "xyz": p, "uv": [round(u, 2), round(v, 2)], "seen": seen})
    out["cameras"][cam.name] = rows
Path(out_path).write_text(json.dumps(out), encoding="utf-8")
print("QA cage", cage and cage[0], {k: len(v) for k, v in out["cameras"].items()})
