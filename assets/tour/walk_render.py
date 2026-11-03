"""Spoor Floor's walking directions in the Blender hub (reviewer 09:35, Rexton's plan: the Map tab as walking navigation,
"a tilted 3D view of the real hub from behind the walker"). A camera follows a walker along the route from the
supervisor's office to the search place, from behind and above, over the hub model only (people, moving cartons and
roof hidden, as in tour_render.py).

  blender -b <hub blend> -P assets/tour/walk_render.py -- --route "x,y;x,y;..." --out DIR [--res 600x1300 --speed 4 --test]

The walk is a simulation (indoors there is no GPS): the video is played faster than walking pace and the page says the
position comes from the last scan. For every frame the script writes the camera's projection matrix, so the page draws
the route ribbon, the destination and the landmark names over the picture in true perspective (nothing is baked in).
"""
import argparse
import json
import math
import re
import sys
import time
from pathlib import Path

import bpy
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument("--route", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--res", default="600x1300")
ap.add_argument("--samples", type=int, default=8)
ap.add_argument("--fps", type=int, default=24)
ap.add_argument("--speed", type=float, default=4.0, help="metres of route per second of video")
ap.add_argument("--test", action="store_true")
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])

BACK, UP, AHEAD = 9.0, 7.5, 7.0       # the camera: behind the walker, above, looking at a point ahead of them
HIDE = re.compile(r"^(roof|roof_lights|roof_services|highbay|mounted_fluorescent|wall_S|wall_E|structure)")

sc = bpy.context.scene
rx, ry = (int(v) for v in args.res.split("x"))
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, 100
sc.render.image_settings.file_format = "JPEG"
sc.render.image_settings.quality = 88
sc.render.use_stamp = False
sc.eevee.taa_render_samples = 4 if args.test else args.samples
sc.eevee.use_raytracing = False
sc.eevee.shadow_resolution_scale = 0.5
sc.view_settings.exposure = 0.2
for coll in ("People", "PeopleTemplates", "Flow"):
    if (c := bpy.data.collections.get(coll)):
        c.hide_render = True
for o in sc.objects:
    if HIDE.match(o.name) or o.name.startswith(("worker_", "flow_", "Bip01")) or o.type == "ARMATURE":
        o.hide_render = True
    if o.type == "LIGHT" and o.name.startswith("ledrow_"):
        o.data.use_shadow = False
sc.frame_set(400)
# the walk starts in the supervisor's office: its ceiling (part of the merged fixtures) would fill the first frames, so
# its faces are cut for this render only (the blend is not saved)
import bmesh
fx = sc.objects.get("fixtures")
if fx:
    bm = bmesh.new()
    bm.from_mesh(fx.data)
    mw = fx.matrix_world
    cut = [f for f in bm.faces if all((lambda w: 54.4 <= w.x <= 60.0 and 0.0 <= w.y <= 6.2 and w.z > 2.8)(mw @ v.co) for v in f.verts)]
    bmesh.ops.delete(bm, geom=cut, context="FACES")
    bm.to_mesh(fx.data)
    bm.free()
    print(f"WALK cut {len(cut)} office ceiling faces")

route = [tuple(float(v) for v in p.split(",")) for p in args.route.split(";")]
seg = [math.dist(route[i], route[i + 1]) for i in range(len(route) - 1)]
L = sum(seg)


def at(s):
    s = min(max(s, 0.0), L)
    for i, d in enumerate(seg):
        if s <= d or i == len(seg) - 1:
            u = s / d if d else 0
            a, b = route[i], route[i + 1]
            return Vector((a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, 0.0))
        s -= d


def heading(s):
    """The direction of travel, smoothed over the next few metres so the camera turns before the corner, not on it."""
    v = Vector((0.0, 0.0, 0.0))
    for k in range(-2, 7):
        a, b = at(s + k), at(s + k + 1)
        v += (b - a)
    v.z = 0
    return v.normalized() if v.length > 1e-6 else Vector((0.0, 1.0, 0.0))


cd = bpy.data.cameras.new("walk_cam")
cd.lens, cd.sensor_fit, cd.sensor_width, cd.clip_end = 18, "VERTICAL", 36, 300
cam = bpy.data.objects.new("walk_cam", cd)
sc.collection.objects.link(cam)
sc.camera = cam

ARRIVE = 12.0
END = at(L)
ARRIVE_AT = Vector((5.0, -9.0, 13.0))   # from the south-east, over the racks: the walls are the backdrop, not the view
fps = args.fps
hold0, hold1 = round(fps * 1.0), round(fps * 1.5)
moving = math.ceil(L / args.speed * fps)
total = hold0 + moving + hold1


def dist_at(f):
    """Metres walked at frame f: a short speed-up and slow-down (trapezoid), steady pace between."""
    if f < hold0:
        return 0.0
    u = min(1.0, (f - hold0) / moving)
    e, vmax = 0.08, 1 / 0.92
    if u < e:
        return L * vmax * u * u / (2 * e)
    if u > 1 - e:
        return L * (1 - vmax * (1 - u) ** 2 / (2 * e))
    return L * vmax * (u - e / 2)


out = Path(args.out).resolve()
(out / "frames").mkdir(parents=True, exist_ok=True)
frames = range(0, total, 24) if args.test else range(total)
mats, walker = [], []
dg = bpy.context.evaluated_depsgraph_get()
t0 = time.time()
for f in frames:
    s = dist_at(f)
    p, h = at(s), heading(s)
    loc, look = p - h * BACK + Vector((0, 0, UP)), p + h * AHEAD
    # the last metres: the camera rises and looks down on the place, so arrival shows where to search, not a wall
    b = min(1.0, max(0.0, (s - (L - ARRIVE)) / ARRIVE))
    b = b * b * (3 - 2 * b)
    loc = loc.lerp(END + ARRIVE_AT, b)
    look = look.lerp(END, b)
    cam.location = loc
    cam.rotation_euler = (look - cam.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()
    P = cam.calc_matrix_camera(dg, x=rx, y=ry) @ cam.matrix_world.inverted()
    mats.append([round(v, 5) for row in P for v in row])
    walker.append(round(s, 2))
    sc.render.filepath = str(out / "frames" / f"f{f:05d}.jpg")
    bpy.ops.render.render(write_still=True)
    if f % 48 == 0 or args.test:
        print(f"WALK frame {f}/{total} {time.time() - t0:.0f}s", flush=True)

meta = {"fps": fps, "frames": total, "size": [rx, ry], "test": args.test, "route": [list(p) for p in route], "length_m": round(L, 1),
        "speed": args.speed, "s": walker, "P": mats}
(out / ("walk_test.json" if args.test else "walk.json")).write_text(json.dumps(meta, separators=(",", ":")), encoding="utf-8")
print(f"WALK done {len(list(frames))} frames in {time.time() - t0:.0f}s")
