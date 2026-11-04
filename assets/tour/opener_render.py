"""The video's opening shot (DEMO_SCRIPT 0:00, Rexton 4 Nov): the whole hub from the drone, turning slowly while the
belts run and the workers work, as a 3x timelapse (from this height real time hardly moves). The same hall, roof and near walls hidden, and the same corner and
elevation as the page's "Whole hub" ring (spin_render.py's "ov"), but a continuous eased arc with a gentle push in,
at 30 fps; the hub's own animation is 10 fps, so at other speeds a video frame samples it between its keys (subframes).

  blender -b <hub blend> -P assets/tour/opener_render.py -- --out assets/tour/opener [--res 1920x1080 --samples 16
      --seconds 10 --fps 30 --sim-start 380 --test]
"""
import argparse
import math
import random
import re
import sys
import time
from pathlib import Path

import bpy
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--res", default="1920x1080")
ap.add_argument("--samples", type=int, default=16)
ap.add_argument("--seconds", type=float, default=10.0)
ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--sim-start", type=float, default=41.0, help="the hub's frame (10 fps) the shot starts on: its busiest stretch")
ap.add_argument("--speed", type=float, default=3.0, help="timelapse: at real time the belts barely move from up here")
ap.add_argument("--from-arc", type=float, default=-102.0, help="degrees round the middle, -90 = due south")
ap.add_argument("--to-arc", type=float, default=-66.0)
ap.add_argument("--push", type=float, default=0.9, help="distance at the end as a share of the start")
ap.add_argument("--fill", type=float, default=0.8, help="share of the free sorter carriers given a parcel")
ap.add_argument("--test", action="store_true", help="first, middle and last frame only")
ap.add_argument("--from-frame", type=int, default=0, help="skip frames already on disk before this")
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])

# the roof, near walls and the LED light rails (they cross the whole picture from up here)
HIDE = re.compile(r"^(roof|roof_lights|roof_services|highbay|mounted_fluorescent|wall_S|wall_E|structure|led_rows)")
LOOK = Vector((30.0, 20.0, 0.0))
R0, H0 = 36.0, 33.0   # the "ov" ring's start: (0, -36, 33) from the middle, 42.5 deg down

sc = bpy.context.scene
rx, ry = (int(v) for v in args.res.split("x"))
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, 100
sc.render.image_settings.file_format = "JPEG"
sc.render.image_settings.quality = 95
sc.render.use_stamp = False
sc.eevee.taa_render_samples = args.samples
sc.eevee.use_raytracing = False
sc.eevee.shadow_resolution_scale = 0.5
sc.view_settings.exposure = 0.2
for o in sc.objects:   # the people and the moving cartons stay
    if HIDE.match(o.name):
        o.hide_render = True
    if o.type == "LIGHT" and o.name.startswith("ledrow_"):
        o.data.use_shadow = False

# Traffic for this shot only (Rexton 4 Nov, "fill the belts"): the simulation keeps ~25 parcels in the hall at once, so
# from the drone the sorter looks idle. Extra parcels (copies of the simulation's own parcel meshes) ride the sorter's
# animated carriers (parented, so they go exactly where the carriers go) and the line A / line B belts at the
# simulation's belt speeds (flow.py). Never in any evidence render: only opener_render.py adds them.
rnd = random.Random(7)
meshes = [o.data for o in sc.objects if o.name.startswith("flow_parcel_") and o.type == "MESH"]
traffic = bpy.data.collections.new("OpenerTraffic")
sc.collection.children.link(traffic)
carriers = sorted([o for o in sc.objects if o.name.startswith("carrier_") and o.type == "MESH"], key=lambda o: o.name)
flows = [o for o in sc.objects if o.name.startswith("flow_parcel_") and o.type == "MESH"]
n_frames = round(args.seconds * args.fps)
busy = set()   # carriers that carry a simulated parcel at any moment of the shot: left alone
for k in range(0, n_frames, 6):
    sim = args.sim_start + k * 10.0 * args.speed / args.fps
    sc.frame_set(int(sim), subframe=sim - int(sim))
    held = [o.matrix_world.translation.copy() for o in flows if o.matrix_world.translation.z > 1.3]
    for c in carriers:
        if any((c.matrix_world.translation.xy - h.xy).length < 0.6 for h in held):
            busy.add(c.name)
riders = 0
for c in carriers:
    if c.name in busy or rnd.random() > args.fill:
        continue
    ob = bpy.data.objects.new(f"opener_rider_{riders:03d}", rnd.choice(meshes))
    traffic.objects.link(ob)
    ob.parent = c
    ob.location = (rnd.uniform(-0.05, 0.05), rnd.uniform(-0.12, 0.12), -0.023)   # the carrier's top, local
    ob.rotation_euler = (0, 0, rnd.choice((0.0, math.pi / 2)) + rnd.uniform(-0.25, 0.25))
    riders += 1
BELTS = [  # (points x, y, surface z; speed m/s), as flow.py builds them; a parcel leaving one end re-enters the other
    ([(5.6, 9.5, 1.0), (15.0, 9.5, 1.0), (17.5, 9.5, 1.5)], 1.5),    # line A induction, ramping up
    ([(17.5, 9.5, 1.5), (23.0, 9.5, 1.5)], 1.5),                     # the scan tunnel
    ([(23.0, 9.5, 1.5), (27.6, 9.5, 1.5), (29.4, 10.6, 1.5)], 1.8),  # merge, ending short of the carriers' band
    ([(40.8, 7.6, 1.0), (44.0, 7.6, 1.0), (45.6, 9.2, 1.5), (46.3, 10.4, 1.5)], 1.5),   # line B
]
belt_riders = []   # (object, belt points, cumulative lengths, speed, start s)
for pts, v in BELTS:
    cum = [0.0]
    for a, b in zip(pts, pts[1:]):
        cum.append(cum[-1] + math.dist(a, b))
    s = rnd.uniform(0, 1.2)
    while s < cum[-1]:
        ob = bpy.data.objects.new(f"opener_belt_{len(belt_riders):03d}", rnd.choice(meshes))
        traffic.objects.link(ob)
        belt_riders.append((ob, pts, cum, v, s, rnd.uniform(-0.2, 0.2)))
        s += rnd.uniform(1.3, 2.4)
print(f"OPENER traffic: {riders} on carriers ({len(busy)} busy skipped), {len(belt_riders)} on belts", flush=True)


def place_belt(t):
    for ob, pts, cum, v, s0, yaw in belt_riders:
        s = (s0 + v * t) % cum[-1]
        i = max(j for j in range(len(cum) - 1) if cum[j] <= s)
        u = (s - cum[i]) / max(cum[i + 1] - cum[i], 1e-6)
        a, b = pts[i], pts[i + 1]
        ob.location = tuple(a[q] + (b[q] - a[q]) * u for q in range(3))
        ob.rotation_euler = (0, 0, math.atan2(b[1] - a[1], b[0] - a[0]) + yaw)


cd = bpy.data.cameras.new("opener_cam")
cd.lens, cd.sensor_width, cd.clip_end = 22, 36, 400
cam = bpy.data.objects.new("opener_cam", cd)
sc.collection.objects.link(cam)
sc.camera = cam


def ease(u):
    """Sine in-out: the turn starts and ends at rest."""
    return 0.5 - 0.5 * math.cos(math.pi * u)


n = round(args.seconds * args.fps)
out = Path(args.out).resolve()
(out / "frames").mkdir(parents=True, exist_ok=True)
keep = [0, n // 2, n - 1] if args.test else range(n)
t0 = time.time()
for i in keep:
    path = out / "frames" / f"f{i:04d}.jpg"
    if i < args.from_frame and path.exists():
        continue
    u = ease(i / (n - 1))
    a = math.radians(args.from_arc + (args.to_arc - args.from_arc) * u)
    s = 1 + (args.push - 1) * u
    cam.location = LOOK + Vector((R0 * s * math.cos(a), R0 * s * math.sin(a), H0 * s))
    cam.rotation_euler = (LOOK - cam.location).to_track_quat("-Z", "Y").to_euler()
    sim = args.sim_start + i * 10.0 * args.speed / args.fps
    sc.frame_set(int(sim), subframe=sim - int(sim))
    place_belt(sim / 10.0)
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    if i % 30 == 0:
        print(f"OPENER frame {i}/{n} {time.time() - t0:.0f}s", flush=True)
print(f"OPENER done in {time.time() - t0:.0f}s")
