"""Every CCTV camera in the hub blend in world metres: where it is mounted and the floor it covers (its frustum's four
corner rays met with the floor, cut at the building, as overview_render.py does), so the Cameras page can draw both on
any frame of the overview turntable (spin_render.py's ring "ov", which carries each frame's projection matrix).
Renders nothing.

  blender -b <hub blend> -P assets/tour/cameras3d.py -- --out frontend/public/tour/hub/cameras3d.json
"""
import json
import re
import sys
from pathlib import Path

import bpy
from mathutils import Vector

out = Path(sys.argv[sys.argv.index("--") + 1:][1]).resolve()
sc = bpy.context.scene
sc.frame_set(400)
FLOOR = (0.0, 0.0, 60.0, 41.0)


def clip(poly):
    x0, y0, x1, y1 = FLOOR
    for inside, cut in ((lambda p: p.x >= x0, lambda a, b: a + (b - a) * ((x0 - a.x) / (b.x - a.x))),
                        (lambda p: p.x <= x1, lambda a, b: a + (b - a) * ((x1 - a.x) / (b.x - a.x))),
                        (lambda p: p.y >= y0, lambda a, b: a + (b - a) * ((y0 - a.y) / (b.y - a.y))),
                        (lambda p: p.y <= y1, lambda a, b: a + (b - a) * ((y1 - a.y) / (b.y - a.y)))):
        res = []
        for i, b in enumerate(poly):
            a = poly[i - 1]
            if inside(b):
                if not inside(a):
                    res.append(cut(a, b))
                res.append(b)
            elif inside(a):
                res.append(cut(a, b))
        poly = res
        if not poly:
            break
    return poly


def footprint(cam):
    mw = cam.matrix_world
    o = mw.translation
    pts = []
    for c in cam.data.view_frame(scene=sc):
        d = (mw @ c - o).normalized()
        t = min(-o.z / d.z if d.z < -1e-3 else 45.0, 45.0)
        p = o + d * t
        pts.append(Vector((p.x, p.y, 0.0)))
    return [[round(p.x, 3), round(p.y, 3)] for p in clip(pts)]


cctv = sorted((o for o in sc.objects if o.type == "CAMERA" and re.match(r"^(CAM|CHK)_", o.name)), key=lambda o: o.name)
cams = [{"id": c.name, "at": [round(v, 3) for v in c.matrix_world.translation], "floor": footprint(c)} for c in cctv]
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"cameras": cams}, separators=(",", ":")), encoding="utf-8")
print("CAMERAS3D", len(cams))
