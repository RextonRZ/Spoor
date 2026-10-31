"""S2 perimeter proof (scenarios_v2 #1): every way out of BLIND_NW (Z11) must be inside some camera's view.
Ray-casts from each CCTV camera to sample points on each exit face of the corner, in the real hub geometry
(racks, sack piles, walls, cages), with the camera's frustum at its render resolution.

  blender -b build/hub_dressed.blend --python mocap/s2_perimeter.py -- --out <json>

Exits (from hub_spec blind_corner + build_hub): the walk-in gap x 13.4-15.2 between the south rack (x 0.2-13.4,
y 33.0-33.6) and the east rack (x 15.2-15.8, y 33.0-39.8); the racks run flush to the west / north walls, which
have no doors north of y 28.5 / west of x 27.5. The only other way is OVER the 3 m racks: checked as a plane 0.3 m
above each rack top.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out = argv[argv.index("--out") + 1]
sc = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()
RX, RY = 2688, 1520
SKIP = ("worker_", "flow_parcel", "parcel_")  # moving things don't block the static view

cams = [o for o in sc.objects if o.type == "CAMERA" and o.name.startswith("CAM_")]
cams = sorted(cams, key=lambda o: o.name)


TRUTH = json.loads((Path(bpy.data.filepath).parents[1] / "render_truth.json").read_text())["cameras"]


def lens_keeps(cam, x, y):
    """Is render pixel (x, y) still in the footage after cctv_look.lens (barrel remap with this camera's k1)? The remap
    samples the render at c + (out - c) * s(r_out), s < 1 towards the top / bottom: content at the frame top and
    bottom edges is cropped. Visible iff the output frame edge in this pixel's direction maps beyond it."""
    k1 = TRUTH.get(cam.name, {}).get("lens_k1", -0.06)
    f = RX / (2 * math.tan(cam.data.angle_x / 2))
    dx, dy = x - RX / 2, y - RY / 2
    r_in = math.hypot(dx, dy)
    if r_in < 1:
        return True
    t_edge = min((RX / 2) / abs(dx) if abs(dx) > 1e-9 else 1e9, (RY / 2) / abs(dy) if abs(dy) > 1e-9 else 1e9)
    ex, ey = dx * t_edge / f, dy * t_edge / f  # the output edge point in this direction (normalised)
    sc_ = (1 - k1 * (ex * ex + ey * ey)) / (1 - k1 * (RX / 2 / f) ** 2)
    return r_in <= math.hypot(ex, ey) * f * sc_ - 2  # 2 px margin


def visible(cam, p):
    inv = cam.matrix_world.inverted()
    pc = inv @ p
    if pc.z > -0.1:
        return False, None
    tx = math.tan(cam.data.angle_x / 2) if RX >= RY else math.tan(cam.data.angle_y / 2) * RX / RY
    ty = tx * RY / RX
    if abs(pc.x / -pc.z) > tx * 0.98 or abs(pc.y / -pc.z) > ty * 0.98:  # 1 % inside the frame edge
        return False, None
    if not lens_keeps(cam, RX / 2 + pc.x / -pc.z / tx * RX / 2, RY / 2 - pc.y / -pc.z / ty * RY / 2):
        return False, None
    o = cam.matrix_world.translation
    d = p - o
    L = d.length
    org = o.copy()
    while True:
        hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, org, d.normalized(), distance=L - (org - o).length - 0.02)
        if not hit:
            break
        if ob.name.startswith(SKIP):
            org = loc + d.normalized() * 0.005
            continue
        return False, ob.name
    # pixels per metre at p (horizontal)
    ppm = RX / (2 * math.tan(cam.data.angle_x / 2) * -pc.z)
    return True, round(ppm, 1)


def face(name, pts):
    res = {}
    for cam in cams:
        vis = [visible(cam, p) for p in pts]
        n = sum(1 for v, _ in vis if v)
        if n:
            ppms = [x for v, x in vis if v]
            res[cam.name] = dict(frac=round(n / len(pts), 3), ppm_min=min(ppms), ppm_max=max(ppms))
    blockers = {}
    for cam in cams:
        for v, x in (visible(cam, p) for p in pts):
            if not v and x:
                blockers[x] = blockers.get(x, 0) + 1
    seen = [any(visible(c, p)[0] for c in cams) for p in pts]
    union = sum(seen)
    return dict(face=name, samples=len(pts), union_frac=round(union / len(pts), 3), cameras=res,
                top_blockers=sorted(blockers.items(), key=lambda kv: -kv[1])[:6],
                unseen=[[round(c, 2) for c in p] for p, s_ in zip(pts, seen) if not s_])


faces = []
# the walk-in gap: a person or a carried parcel crossing it passes through the plane y 33.0-33.6 (rack depth),
# sampled on its south face, middle and north face, z 0.1-2.0 (a carried parcel / a person's body)
gx = [13.45 + i * 0.1 for i in range(18)]
gz = [0.1 + i * 0.1 for i in range(20)]
for y, tag in ((32.95, "gap_south_face"), (33.3, "gap_mid"), (33.65, "gap_north_face")):
    faces.append(face(tag, [Vector((x, y, z)) for x in gx for z in gz]))
# a person standing in the gap (0.5 m wide body column at the gap centre line)
faces.append(face("gap_person_column", [Vector((14.3 + dx, 33.3, z)) for dx in (-0.25, 0, 0.25)
                                        for z in (0.5, 1.0, 1.5, 1.7)]))
# over the racks: 0.3 m above the 3.0 m rack top, along both racks
over = [Vector((x, 33.3, 3.3)) for x in [0.5 + i * 0.5 for i in range(26)]] + \
       [Vector((15.5, y, 3.3)) for y in [33.2 + i * 0.5 for i in range(13)]]
faces.append(face("over_racks_z3.3", over))
# inside Z11 (must stay unseen: "no camera sees inside Z11"): the floor-to-head volume, 0.5 m grid
inside = [Vector((x, y, z)) for x in [0.5 + i * 0.5 for i in range(30)] for y in [33.9 + j * 0.5 for j in range(12)]
          for z in (0.2, 1.0, 1.7)]
faces.append(face("inside_Z11", inside))
# where a parcel thrown over a rack would land: the 1.5 m floor band outside each rack (z 0.1 / 0.5)
band = [Vector((x, y, z)) for x in [0.5 + i * 0.5 for i in range(26)] for y in (31.8, 32.4) for z in (0.1, 0.5)] +        [Vector((x, y, z)) for x in (16.2, 16.9) for y in [33.2 + i * 0.5 for i in range(13)] for z in (0.1, 0.5)]
faces.append(face("landing_band_outside_racks", band))
# the corner flush joins (wall / rack): proof there is no slot
probe = {}
for tag, a, b in (("south_rack_west_end", Vector((0.1, 33.3, 1.0)), Vector((0.3, 33.3, 1.0))),
                  ("east_rack_north_end", Vector((15.5, 39.7, 1.0)), Vector((15.5, 39.95, 1.0)))):
    hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, a, (b - a).normalized(), distance=(b - a).length)
    probe[tag] = ob.name if hit else None
rep = dict(blend=bpy.data.filepath, cameras_checked=[c.name for c in cams], faces=faces, joins_probe=probe)
with open(out, "w") as fh:
    json.dump(rep, fh, indent=1)
for f in faces:
    print(f["face"], f["union_frac"], {k: v["frac"] for k, v in f["cameras"].items()}, f["top_blockers"][:3])
print("joins", probe)
