"""Drag-to-spin turntables for the route in the Blender hub (Rexton 3 Nov, approved option 1: "spin around at every
step"). For every place on the case's route, and for the whole hub (the Overview), a ring of frames orbiting the place
from the hub model only (people, moving cartons and roof hidden, as in tour_render.py).

  blender -b <hub blend> -P assets/tour/spin_render.py -- --reel reel.json --out DIR [--res 1280x720 --n 36 --test]

Ring 0 starts at exactly the pose the fly-through lands on (tour_render.py's drone), so the page can cut from the
video to the turntable without a jump; ring 1 is the same distance from higher up (60 degrees). A wall the orbit has
passed behind is hidden for that frame (the inside stays in view; the yard and lorries stay). For every frame the
script writes where each step's point and each camera on the route fall on the image, so the page draws the evidence's
marks over a picture of the building, exactly as the fly-through does.
"""
import argparse
import json
import math
import re
import sys
import time
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument("--reel", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--res", default="1280x720")
ap.add_argument("--samples", type=int, default=8)
ap.add_argument("--n", type=int, default=36, help="frames per ring")
ap.add_argument("--high", type=float, default=60.0, help="ring 1 elevation, degrees")
ap.add_argument("--only", default="", help="comma list of ring names to render (p0..p6, ov)")
ap.add_argument("--test", action="store_true", help="4 angles per ring at half size, to judge the look and speed")
ap.add_argument("--fmt", default="WEBP", help="WEBP for the page's rings; JPEG (q95) when the ring becomes a video")
ap.add_argument("--limit", type=int, default=0, help="render only the first N frames of each ring (timing)")
ap.add_argument("--table-only", action="store_true", help="write the tables (with each frame's projection matrix), render nothing")
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])

# the fly-through's drone (tour_render.py): ring 0 starts where it lands
OFFSET = Vector((-4.0, -11.0, 10.5))
LOOK_Z = PIN_Z = 0.8
HIDE = re.compile(r"^(roof|roof_lights|roof_services|highbay|mounted_fluorescent|wall_S|wall_E|structure)")
HALL = (0.0, 0.0, 60.0, 40.0)

sc = bpy.context.scene
rx, ry = (int(v) for v in args.res.split("x"))
if args.test:
    rx, ry = rx // 2, ry // 2
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, 100
sc.render.image_settings.file_format = args.fmt
sc.render.image_settings.quality = 95 if args.fmt == "JPEG" else 78
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
wall_w, wall_n = sc.objects.get("wall_W"), sc.objects.get("wall_N")
signs = sc.objects.get("text_signs_merged")  # painted on the walls' inner faces: read backwards from outside

# the steps and their places, grouped as the page groups them (a step without a place shares the one before)
reel = json.loads(Path(args.reel).read_text(encoding="utf-8"))
steps = [c for c in reel["chapters"] if c.get("tone") != "card"]
pts = []
for c in steps:
    xy = c.get("xy") or (pts[-1] if pts else [0, 0])
    pts.append((float(xy[0]), float(xy[1])))
places = []  # (point, [step indexes])
for i, p in enumerate(pts):
    if places and math.dist(places[-1][0], p) < 0.5:
        places[-1][1].append(i)
    else:
        places.append((p, [i]))
cams = sorted({c["camera"] for c in steps if re.match(r"^(CAM|CHK)_", c.get("camera") or "")})
cam_at = {n: sc.objects[n].matrix_world.translation.copy() for n in cams if n in sc.objects}

cd = bpy.data.cameras.new("spin_cam")
cd.lens, cd.sensor_width, cd.clip_end = 22, 36, 400
cam = bpy.data.objects.new("spin_cam", cd)
sc.collection.objects.link(cam)
sc.camera = cam


def arrival(p):
    """The fly-through's landing pose on point p: (look-at point, camera location)."""
    loc = Vector((p[0], p[1], 0)) + OFFSET
    loc.x = min(57.0, max(4.0, loc.x))
    return Vector((p[0], p[1], LOOK_Z)), loc


def rings_for(look, start):
    """Ring 0 through `start`; ring 1 the same distance away, higher. Each: (elevation deg, [camera location per frame])."""
    d = start - look
    r0, h0 = math.hypot(d.x, d.y), d.z
    a0 = math.atan2(d.y, d.x)
    dist = math.hypot(r0, h0)
    out = []
    for r, h in ((r0, h0), (dist * math.cos(math.radians(args.high)), dist * math.sin(math.radians(args.high)))):
        # frame k turns the camera k steps anticlockwise seen from above: dragging left spins the hub left
        locs = [look + Vector((r * math.cos(a0 + 2 * math.pi * k / args.n), r * math.sin(a0 + 2 * math.pi * k / args.n), h))
                for k in range(args.n)]
        out.append((round(math.degrees(math.atan2(h, r)), 1), locs))
    return out


def uv(p):
    q = world_to_camera_view(sc, cam, p)
    return [round(q.x, 4), round(q.y, 4)] if q.z > 0.1 else None


jobs = []  # (name, look, steps at this place)
for k, (p, idx) in enumerate(places):
    look, start = arrival(p)
    jobs.append((f"p{k}", look, idx, rings_for(look, start)))
# the Overview: the whole hall from the corner the overview still uses, turning about its middle
ov_look = Vector((30.0, 20.0, 0.0))
jobs.append(("ov", ov_look, [], rings_for(ov_look, ov_look + Vector((0.0, -36.0, 33.0)))))
only = set(filter(None, args.only.split(",")))

out = Path(args.out).resolve()
meta = {"n": args.n, "size": [rx, ry], "test": args.test, "cams": cams, "rings": {}}
old = out / "spin.json"
if only and old.exists():
    meta["rings"] = json.loads(old.read_text(encoding="utf-8")).get("rings", {})
t0 = time.time()
done = 0
for name, look, idx, rings in jobs:
    if only and name not in only:
        continue
    meta["rings"][name] = {"steps": [i + 1 for i in idx], "look": [round(look.x, 2), round(look.y, 2)], "rings": []}
    for e, (elev, locs) in enumerate(rings):
        d = out / name / str(e)
        d.mkdir(parents=True, exist_ok=True)
        pins, cuv, mats = [], [], []
        for k, loc in enumerate(locs):
            cam.location = loc
            cam.rotation_euler = (look - loc).to_track_quat("-Z", "Y").to_euler()
            # a wall the camera has gone behind would fill the frame: hide it for this frame only
            if wall_w:
                wall_w.hide_render = loc.x < HALL[0] + 0.3
            if wall_n:
                wall_n.hide_render = loc.y > HALL[3] - 0.3
            if signs:
                signs.hide_render = loc.x < HALL[0] + 0.3 or loc.y > HALL[3] - 0.3
            bpy.context.view_layer.update()
            pins.append([uv(Vector((x, y, PIN_Z))) for x, y in pts])
            cuv.append({n: uv(a) for n, a in cam_at.items()})
            # the camera's projection, so the page can place any point of the hub on this frame (the answer zone)
            P = cam.calc_matrix_camera(bpy.context.evaluated_depsgraph_get(), x=rx, y=ry) @ cam.matrix_world.inverted()
            mats.append([round(v, 5) for row in P for v in row])
            if args.table_only:
                continue
            if args.test and k % (args.n // 4):
                continue
            if args.limit and k >= args.limit:
                continue
            sc.render.filepath = str(d / f"f{k:0{3 if args.n > 100 else 2}d}.{'jpg' if args.fmt == 'JPEG' else 'webp'}")
            bpy.ops.render.render(write_still=True)
            done += 1
        meta["rings"][name]["rings"].append({"elev": elev, "pins": pins, "cams": cuv, "P": mats})
        print(f"SPIN {name} ring {e} ({elev} deg) {done} frames {time.time() - t0:.0f}s", flush=True)
        (out / "spin.json").write_text(json.dumps(meta, separators=(",", ":")), encoding="utf-8")
print(f"SPIN done {done} frames in {time.time() - t0:.0f}s")
