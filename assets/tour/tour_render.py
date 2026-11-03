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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import route_path  # noqa: E402  (the carton's way: belts while on them, walkways when carried)
import carton  # noqa: E402  (the parcel as a real object: a marker of what the evidence says)

ap = argparse.ArgumentParser()
ap.add_argument("--reel", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--res", default="1600x900")
ap.add_argument("--samples", type=int, default=8)
ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--test", action="store_true", help="render one frame per distinct place, to judge the look and speed")
ap.add_argument("--from-frame", type=int, default=0, help="resume: skip frames already on disk before this one")
ap.add_argument("--table-only", action="store_true", help="write tour.json (with each frame's projection matrix), render nothing")
ap.add_argument("--hub", default="frontend/src/data/hub.generated.json", help="the hub layout the carton's way is planned on")
ap.add_argument("--every", type=int, default=1, help="render every Nth frame only (a preview of the moves)")
ap.add_argument("--carton-scale", type=float, default=2.0,
                help="the carton drawn this many times its measured size: at true size it is ~16 px from the drone (LIMITATIONS)")
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

# the carton's way between steps (route_path.py): along the belts, carried along the walkways, or held where it was
# last seen when the next step is only a record
hub = json.loads(Path(args.hub).read_text(encoding="utf-8"))
ways = {j: (kind, path) for i, j, kind, path in route_path.legs(hub, steps)}


def held_at(i):
    """the step whose place the carton is at during step i: a record step leaves it where it was"""
    while i > 0 and steps[i].get("tone") == "record":
        i -= 1
    return i


# the timeline: arrive at step 1, rest; move to the next place, rest; same place: rest only. A carried move takes
# its time from its length along the way (a lap of the sort loop is longer than a hop across an aisle), within limits
fps = args.fps
ease = lambda u: 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2  # ease-in-out cubic
keys = []   # (frame, step index) when the camera arrives at that step
segs = []   # (f0, f1, a, b, kind, way): a move from step a's place to step b's
f = 0
for i, p in enumerate(pts):
    if i:
        d = math.dist(pts[i - 1], p)
        if d > 0.5:
            kind, way = ways.get(i, ("held", [pts[held_at(i - 1)]]))
            sec = min(2.6, max(1.4, d / 10)) if kind == "held" else min(4.2, max(1.4, route_path.length(way) / 9))
            m = round(fps * sec)
            segs.append((f, f + m, i - 1, i, kind, way))
            f += m
    keys.append((f, i))
    f += round(fps * (HOLD if i == 0 or math.dist(pts[i - 1], p) > 0.5 else SAME_HOLD))
# the ending (reviewer 01:05): from the last step the drone eases back to where the carton was left and settles a little
# closer, then holds: the page's answer ("Most likely here") is drawn on these frames
last = len(steps) - 1
store = pts[held_at(last)]
end_seg = None
if math.dist(pts[last], store) > 0.5:
    m = round(fps * 2.6)
    end_seg = (f, f + m)
    f += m
END_K = 0.72                     # the drone's offset at the end, as a share of the usual one
end_arrive = f
f += round(fps * 2.0)
total = f + round(fps * 0.3)
V = lambda xy: Vector((xy[0], xy[1], 0))
arrive_of = {i: k for k, i in keys}
LEFT = max(i for i in range(len(steps)) if steps[i].get("tone") != "record")   # where it is left: it settles there
SETTLE = round(fps * 0.7)
yaw_now = [0.0]


def carton_pose(frame):
    """(x, y, z, support z, yaw) of the carton at this frame: along its way while moving, else where it rests"""
    for f0, f1, a, b, kind, way in segs:
        if f0 <= frame < f1 and kind != "held":
            L = route_path.length(way)
            sd = ease((frame - f0) / (f1 - f0)) * L
            x, y, z, sup = route_path.pose_along(hub, way, kind, sd, route_path.rest_pose(hub, steps, held_at(a))[0],
                                                 route_path.rest_pose(hub, steps, b)[0])
            yaw_now[0] = carton.heading(route_path.at(way, max(0.0, sd - 0.15)), route_path.at(way, min(L, sd + 0.15)), yaw_now[0])
            return x, y, z, sup, yaw_now[0]
    cur = max((k for k in keys if k[0] <= frame), default=keys[0])[1]
    h = held_at(cur)
    z, sup = route_path.rest_pose(hub, steps, h)
    if h == LEFT and frame - arrive_of[LEFT] < SETTLE:   # put down: from the hands to the floor
        u = ease(max(0.0, (frame - arrive_of[LEFT]) / SETTLE))
        z = route_path.CARRIED + (z - route_path.CARRIED) * u
    return pts[h][0], pts[h][1], z, sup, yaw_now[0]


def place(frame):
    """(point the camera looks at, the marker's point) at this frame. The camera follows the carton along its way,
    smoothed over a few metres so it rounds a belt's corner instead of snapping; the smoothing shrinks to nothing at
    either end, so the camera lands exactly where it always did (the turntables start from that pose)."""
    for f0, f1, a, b, kind, way in segs:
        if f0 <= frame < f1:
            u = ease((frame - f0) / (f1 - f0))
            if kind == "held":
                return V(pts[a]).lerp(V(pts[b]), u), V(way[0]), 1.0
            L = route_path.length(way)
            s = u * L
            w = min(3.0, s, L - s)
            look = sum((V(route_path.at(way, s + w * k / 4)) for k in range(-4, 5)), Vector()) / 9
            return look, V(route_path.at(way, s)), 1.0
    if end_seg and end_seg[0] <= frame < end_seg[1]:
        u = ease((frame - end_seg[0]) / (end_seg[1] - end_seg[0]))
        return V(pts[last]).lerp(V(store), u), V(store), 1 + (END_K - 1) * u
    if frame >= end_arrive:
        return V(store), V(store), END_K
    cur = max((k for k in keys if k[0] <= frame), default=keys[0])
    return V(pts[cur[1]]), V(pts[held_at(cur[1])]), 1.0


cam_data = bpy.data.cameras.new("tour_cam")
cam_data.lens, cam_data.sensor_width, cam_data.clip_end = 22, 36, 300
cam = bpy.data.objects.new("tour_cam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam


def aim(target, k=1.0):
    loc = target + OFFSET * k
    loc.x = min(57.0, max(4.0, loc.x))  # the drone stays inside the hall (the inbound doors are on the west wall)
    cam.location = loc
    look = Vector((target.x, target.y, LOOK_Z)) - cam.location
    cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()


out = Path(args.out).resolve()
(out / "frames").mkdir(parents=True, exist_ok=True)
frames = [k[0] for k in keys if k[0] == min(kk[0] for kk in keys if math.dist(pts[kk[1]], pts[k[1]]) < 0.5)] if args.test else range(0, total, args.every)
proj, marker, mats = [], [], []
rig = carton.make()
t0 = time.time()
for fr in frames:
    tgt, mk, k_off = place(fr)
    aim(tgt, k_off)
    cx, cy, cz, csup, cyaw = carton_pose(fr)
    carton.place(rig, cx, cy, cz, cyaw, csup, args.carton_scale)
    uv = lambda p: [round(v, 4) for v in world_to_camera_view(sc, cam, Vector((p[0], p[1], PIN_Z)))[:2]]
    proj.append([uv(p) for p in pts])
    # the marker the page draws the carton's light trail from: where the carton touches its surface (belt or floor)
    marker.append([round(v, 4) for v in world_to_camera_view(sc, cam, Vector((cx, cy, csup)))[:2]])
    P = cam.calc_matrix_camera(bpy.context.evaluated_depsgraph_get(), x=rx, y=ry) @ cam.matrix_world.inverted()
    mats.append([round(v, 5) for row in P for v in row])
    if args.table_only:
        continue
    path = out / "frames" / f"f{fr:05d}.jpg"
    if fr >= args.from_frame or not path.exists():
        sc.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
    if fr % 30 == 0 or args.test:
        print(f"TOUR frame {fr}/{total} {time.time() - t0:.0f}s", flush=True)

meta = {"fps": fps, "frames": total, "size": [rx, ry], "test": args.test,
        "steps": [{"n": i + 1, "arrive": k, "title": steps[i]["title"], "tone": steps[i]["tone"]} for k, i in keys],
        "pins": proj, "marker": marker, "P": mats, "ending": {"arrive": end_arrive}}
(out / ("tour_test.json" if args.test else "tour.json")).write_text(json.dumps(meta, separators=(",", ":")), encoding="utf-8")
print(f"TOUR done {len(list(frames)) if args.test else total} frames in {time.time() - t0:.0f}s")
