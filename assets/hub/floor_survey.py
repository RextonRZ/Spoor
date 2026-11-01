"""Floor survey per CCTV camera (the install-time calibration a real hub does once: floor marks measured on the plan and
clicked in each camera's picture). Here the marks come from the scene itself: rays through a grid of picture points,
kept where they land on open floor (not on a rack, a cage, a belt or a person), then moved through the same barrel lens
the CCTV look applies (cctv_look.lens), at the delivered frame size. Every 4th point is held out so the backend's fit
reports its own error.

  blender -b assets/hub/build/hub_lineAb_S2_final.blend --python assets/hub/floor_survey.py -- <out.json> [--wh 1920 1086]

Output: {camera: {"image_wh_px": [w, h], "fit": [[u, v, x, y]...], "holdout": [...], "lens_k1": k1}}; POST each to
/v1/cameras/cam_<name>/calibrations (frontend/scripts/seed_calibrations.py).
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HUB = Path(__file__).resolve().parent
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = Path(argv[0])
W, H = (int(argv[argv.index("--wh") + 1]), int(argv[argv.index("--wh") + 2])) if "--wh" in argv else (1920, 1086)
TRUTH = json.loads((HUB / "render_truth.json").read_text(encoding="utf-8"))["cameras"]
sc = bpy.context.scene
sc.frame_set(1)
dg = bpy.context.evaluated_depsgraph_get()
RX, RY = sc.render.resolution_x, sc.render.resolution_y
GRID = (48, 27)


def distort(xs, ys, k1, f, w):
    """Undistorted normalised point -> where cctv_look.lens puts it (it samples source = x * scale(r) at output x)."""
    edge = (w / 2 / f) ** 2
    xo, yo = xs, ys
    for _ in range(30):
        s = (1 - k1 * (xo * xo + yo * yo)) / (1 - k1 * edge)
        xo, yo = xs / s, ys / s
    return xo, yo


def floor_hit(o, rot, cx, cy):
    hit, loc, nrm, _i, ob, _m = sc.ray_cast(dg, o, (rot @ Vector((cx, cy, -1.0))).normalized(), distance=200.0)
    if not hit or nrm.z < 0.97 or abs(loc.z) > 0.03 or ob.name.startswith(("worker_", "flow_parcel", "parcel_", "cage", "bag_")):
        return None
    return loc


out = {}
for cam in sorted((o for o in bpy.data.objects if o.type == "CAMERA" and o.name.startswith("CAM_")), key=lambda o: o.name):
    k1 = TRUTH.get(cam.name, {}).get("lens_k1", -0.06)
    tx = math.tan(cam.data.angle_x / 2)
    ty = tx * RY / RX
    f = RX / (2 * tx)
    o = cam.matrix_world.translation
    rot = cam.matrix_world.to_3x3()
    pts = []
    for j in range(GRID[1]):
        for i in range(GRID[0]):
            nx, ny = (i + 0.5) / GRID[0] * 2 - 1, (j + 0.5) / GRID[1] * 2 - 1  # undistorted picture, -1..1
            loc = floor_hit(o, rot, nx * tx, -ny * ty)
            # a mark a person could click: open floor here AND just around it (not floor glimpsed through a grating)
            ring = [floor_hit(o, rot, (nx + ex) * tx, -(ny + ey) * ty) for ex, ey in
                    ((0.012, 0), (-0.012, 0), (0, 0.02), (0, -0.02))]
            if loc is None or any(r is None or (r - loc).length > 0.6 for r in ring):
                continue
            xo, yo = distort(nx * tx, ny * ty, k1, f, RX)  # picture x right, y down, in units of f
            u, v = (xo * f + RX / 2) * W / RX, (yo * f + RY / 2) * H / RY
            if 4 <= u <= W - 4 and 4 <= v <= H - 4:
                pts.append([round(u, 1), round(v, 1), round(loc.x, 3), round(loc.y, 3)])
    out[cam.name] = {"image_wh_px": [W, H], "lens_k1": k1, "lens_hfov_deg": round(math.degrees(cam.data.angle_x), 3), "fit": [p for n, p in enumerate(pts) if n % 4],
                     "holdout": [p for n, p in enumerate(pts) if n % 4 == 0]}
    print(f"SURVEY {cam.name}: {len(pts)} floor points")
OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
print("WROTE", OUT)
