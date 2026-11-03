"""The hub's camera setup in Blender (Rexton 3 Nov: "a toggle to view the CCTV and camera setup; click a camera to see
what it sees"). One wide shot of the hub model (people, moving cartons and roof hidden, as in tour_render.py), and for
every CCTV camera in the blend: where it sits on that picture and the floor area it covers (its frustum's four corner
rays met with the floor), so the page can draw the pins and light up a camera's coverage on hover.

  blender -b <hub blend> -P assets/tour/overview_render.py -- --out DIR [--res 1920x1080 --samples 24]
"""
import argparse
import json
import re
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--res", default="1920x1080")
ap.add_argument("--samples", type=int, default=24)
ap.add_argument("--eye", default="30,-17,33")
ap.add_argument("--look", default="30,19,0")
ap.add_argument("--lens", type=float, default=22)
ap.add_argument("--test", action="store_true")
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])

HIDE = re.compile(r"^(roof|roof_lights|roof_services|highbay|mounted_fluorescent|wall_S|wall_E|structure)")
sc = bpy.context.scene
rx, ry = (int(v) for v in args.res.split("x"))
if args.test:
    rx, ry = rx // 2, ry // 2
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, 100
sc.render.image_settings.file_format = "JPEG"
sc.render.image_settings.quality = 92
sc.render.use_stamp = False
sc.eevee.taa_render_samples = 4 if args.test else args.samples
sc.eevee.use_raytracing = False
sc.eevee.shadow_resolution_scale = 0.5 if args.test else 1.0
sc.view_settings.exposure = 0.2
for coll in ("People", "PeopleTemplates", "Flow"):
    if (c := bpy.data.collections.get(coll)):
        c.hide_render = True
for o in sc.objects:
    if HIDE.match(o.name) or o.name.startswith(("worker_", "flow_", "Bip01")) or o.type == "ARMATURE":
        o.hide_render = True
    if o.type == "LIGHT" and o.name.startswith("ledrow_"):
        o.data.use_shadow = False
    if o.type == "MESH" and o.name.startswith("ledrow"):  # the strip fixtures cut across a shot from above; their light stays
        o.hide_render = True
sc.frame_set(400)

cctv = sorted((o for o in sc.objects if o.type == "CAMERA" and re.match(r"^(CAM|CHK)_", o.name)), key=lambda o: o.name)
eye = Vector([float(v) for v in args.eye.split(",")])
look = Vector([float(v) for v in args.look.split(",")])
cd = bpy.data.cameras.new("overview_cam")
cd.lens, cd.sensor_width, cd.clip_end = args.lens, 36, 400
ov = bpy.data.objects.new("overview_cam", cd)
sc.collection.objects.link(ov)
ov.location = eye
ov.rotation_euler = (look - eye).to_track_quat("-Z", "Y").to_euler()
sc.camera = ov
bpy.context.view_layer.update()


def uv(p):
    q = world_to_camera_view(sc, ov, p)
    return [round(q.x, 4), round(1 - q.y, 4)]  # top-left origin, as the page draws


FLOOR = (0.0, 0.0, 60.0, 41.0)  # the building's floor (x0, y0, x1, y1): a view running past the walls is cut there


def clip(poly):
    """Sutherland-Hodgman against the floor rectangle."""
    x0, y0, x1, y1 = FLOOR
    for inside, cut in ((lambda p: p.x >= x0, lambda a, b: a + (b - a) * ((x0 - a.x) / (b.x - a.x))),
                        (lambda p: p.x <= x1, lambda a, b: a + (b - a) * ((x1 - a.x) / (b.x - a.x))),
                        (lambda p: p.y >= y0, lambda a, b: a + (b - a) * ((y0 - a.y) / (b.y - a.y))),
                        (lambda p: p.y <= y1, lambda a, b: a + (b - a) * ((y1 - a.y) / (b.y - a.y)))):
        out = []
        for i, b in enumerate(poly):
            a = poly[i - 1]
            if inside(b):
                if not inside(a):
                    out.append(cut(a, b))
                out.append(b)
            elif inside(a):
                out.append(cut(a, b))
        poly = out
        if not poly:
            break
    return poly


def footprint(cam):
    """The floor the camera sees: its frame's four corner rays, met with the floor (capped at 45 m for rays that never land)."""
    mw = cam.matrix_world
    o = mw.translation
    pts = []
    for c in cam.data.view_frame(scene=sc):
        d = (mw @ c - o).normalized()
        t = -o.z / d.z if d.z < -1e-3 else 45.0
        t = min(t, 45.0)
        p = o + d * t
        pts.append(Vector((p.x, p.y, 0.0)))
    return [uv(p) for p in clip(pts)]


out = Path(args.out).resolve()
out.mkdir(parents=True, exist_ok=True)
cams = [{"id": c.name, "at": uv(c.matrix_world.translation), "floor": footprint(c),
         "height_m": round(c.matrix_world.translation.z, 2)} for c in cctv]
sc.render.filepath = str(out / ("overview_test.jpg" if args.test else "overview.jpg"))
bpy.ops.render.render(write_still=True)
(out / ("overview_test.json" if args.test else "overview.json")).write_text(json.dumps({"size": [rx, ry], "cameras": cams}), encoding="utf-8")
print("OVERVIEW", len(cams), [c["id"] for c in cams])
