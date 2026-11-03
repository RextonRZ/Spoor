"""The case's route in the Blender hub (Rexton 3 Nov: "the 3D should be from Blender, not three"). A drone camera
glides from step to step over the hub model; nothing about the parcel comes from the simulation.

  blender -b <hub blend> -P assets/tour/tour_render.py -- --reel reel.json --out DIR [--res 1600x900 --samples 8 --test]

The hub is the model only: people, the moving cartons (Flow) and the roof are hidden, so no frame shows where the real
carton was. The step positions are the case's evidence (the reel's chapters: camera and scan positions). For every
frame the script writes where each step's point and the moving marker fall on the image (world_to_camera_view), and
the page draws the pins and the marker on top of the video from that table, so the marks are the evidence's, drawn
over a picture of the building.
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
ap.add_argument("--res", default="1600x900")
ap.add_argument("--samples", type=int, default=8)
ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--test", action="store_true", help="render one frame per distinct place, to judge the look and speed")
ap.add_argument("--from-frame", type=int, default=0, help="resume: skip frames already on disk before this one")
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])

OFFSET = Vector((-4.0, -11.0, 10.5))   # the drone sits south-west of the point, above it: north stays up, as on the plan
LOOK_Z = 0.8                           # a parcel's height on a belt or in a cage, roughly
PIN_Z = 0.8
HOLD, SAME_HOLD = 1.0, 0.7             # seconds the camera rests on a step (a step at the same place rests less)
HIDE = re.compile(r"^(roof|roof_lights|roof_services|highbay|mounted_fluorescent|wall_S|wall_E|structure)")

sc = bpy.context.scene
rx, ry = (int(v) for v in args.res.split("x"))
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, 100
sc.render.image_settings.file_format = "JPEG"
sc.render.image_settings.quality = 92
sc.render.use_stamp = False
sc.eevee.taa_render_samples = args.samples
sc.eevee.use_raytracing = False
sc.eevee.shadow_resolution_scale = 0.5
sc.view_settings.exposure = 0.2

hidden = 0
for coll in ("People", "PeopleTemplates", "Flow"):
    c = bpy.data.collections.get(coll)
    if c:
        c.hide_render = True
for o in sc.objects:
    if HIDE.match(o.name) or o.name.startswith(("worker_", "flow_", "Bip01")) or o.type == "ARMATURE":
        o.hide_render = True
        hidden += 1
    if o.type == "LIGHT" and o.name.startswith("ledrow_"):
        o.data.use_shadow = False
print(f"TOUR hidden {hidden} objects + People/Flow collections")
sc.frame_set(400)  # any frame: what moves is hidden

# the steps, as the reel numbers them (the timing cards are not steps)
reel = json.loads(Path(args.reel).read_text(encoding="utf-8"))
steps = [c for c in reel["chapters"] if c.get("tone") != "card"]
pts = []
for c in steps:
    xy = c.get("xy") or (pts[-1][:2] if pts else [0, 0])
    pts.append((float(xy[0]), float(xy[1])))

# the timeline: arrive at step 1, rest; glide to the next place (time by distance), rest; same place: rest only
fps = args.fps
ease = lambda u: 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2  # ease-in-out cubic
keys = []   # (frame, step index) when the camera arrives at that step
segs = []   # (f0, f1, a, b): a glide from step a's place to step b's
f = 0
for i, p in enumerate(pts):
    if i:
        d = math.dist(pts[i - 1], p)
        if d > 0.5:
            m = round(fps * min(2.6, max(1.4, d / 10)))
            segs.append((f, f + m, i - 1, i))
            f += m
    keys.append((f, i))
    f += round(fps * (HOLD if i == 0 or math.dist(pts[i - 1], p) > 0.5 else SAME_HOLD))
total = f + round(fps * 0.5)


def place(frame):
    """(point the camera looks at, the marker's point) at this frame."""
    for f0, f1, a, b in segs:
        if f0 <= frame < f1:
            u = ease((frame - f0) / (f1 - f0))
            pa, pb = Vector((*pts[a], 0)), Vector((*pts[b], 0))
            return pa.lerp(pb, u), pa.lerp(pb, u)
    last = max((k for k in keys if k[0] <= frame), default=keys[0])
    p = Vector((*pts[last[1]], 0))
    return p, p


cam_data = bpy.data.cameras.new("tour_cam")
cam_data.lens, cam_data.sensor_width, cam_data.clip_end = 22, 36, 300
cam = bpy.data.objects.new("tour_cam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam


def aim(target):
    loc = target + OFFSET
    loc.x = min(57.0, max(4.0, loc.x))  # the drone stays inside the hall (the inbound doors are on the west wall)
    cam.location = loc
    look = Vector((target.x, target.y, LOOK_Z)) - cam.location
    cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()


out = Path(args.out).resolve()
(out / "frames").mkdir(parents=True, exist_ok=True)
frames = [k[0] for k in keys if k[0] == min(kk[0] for kk in keys if math.dist(pts[kk[1]], pts[k[1]]) < 0.5)] if args.test else range(total)
proj, marker = [], []
t0 = time.time()
for fr in frames:
    tgt, mk = place(fr)
    aim(tgt)
    uv = lambda p: [round(v, 4) for v in world_to_camera_view(sc, cam, Vector((p[0], p[1], PIN_Z)))[:2]]
    proj.append([uv(p) for p in pts])
    marker.append(uv(mk))
    path = out / "frames" / f"f{fr:05d}.jpg"
    if fr >= args.from_frame or not path.exists():
        sc.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
    if fr % 30 == 0 or args.test:
        print(f"TOUR frame {fr}/{total} {time.time() - t0:.0f}s", flush=True)

meta = {"fps": fps, "frames": total, "size": [rx, ry], "test": args.test,
        "steps": [{"n": i + 1, "arrive": k, "title": steps[i]["title"], "tone": steps[i]["tone"]} for k, i in keys],
        "pins": proj, "marker": marker}
(out / ("tour_test.json" if args.test else "tour.json")).write_text(json.dumps(meta, separators=(",", ":")), encoding="utf-8")
print(f"TOUR done {len(list(frames)) if args.test else total} frames in {time.time() - t0:.0f}s")
