"""Landing hero ground truth: which cameras really saw the story parcel, when, and where in their (final-look) frame.

  blender -b <S2 blend> -P assets/hub/landing_truth.py -- --object flow_parcel_5013 --out frontend/public/landing/tracks.json

Per camera (CAM_01..CAM_19) and per sampled frame: the parcel's 8 box corners projected into the camera, then warped
through the same barrel the CCTV pass applies (cctv_look._lens_maps, render_truth lens_k1, the spec's hfov), so a box
drawn on the final-look clip sits on the parcel. Seen = at least 35 % of 9 sample points (centre + corners pulled 10 %
in) have a clear line of sight from the camera (people and everything else occlude; the parcel and its label don't).
Seen frames merge into sightings (gaps up to 1 s bridged, runs under 1 s dropped). Boxes are normalised to the frame.
Ground truth, not tracking output: the page must not call it SAM. Reads render_truth (render side): only the lens
curvature enters the boxes; no clock offset is written out (the footage's own on-screen clock is what is shown).
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

HUB = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--object", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--step", type=int, default=2)
ap.add_argument("--min-seen", type=float, default=0.35)
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])

sc = bpy.context.scene
W, H = 2688, 1520  # the render's aspect: projections are normalised, so any size with this aspect matches
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
spec = json.loads((HUB / "hub_spec.json").read_text(encoding="utf-8"))
truth = json.loads((HUB / "render_truth.json").read_text(encoding="utf-8"))["cameras"]
scen = json.loads((HUB / "build" / "truth" / "scenario_S2.json").read_text(encoding="utf-8"))
CAMS = {c["id"]: c for c in spec["cameras"]}
obj = sc.objects[a.object]
skip = {obj.name} | {c.name for c in obj.children}
F0, F1 = sc.frame_start, sc.frame_end
FPS = 10


def warp(u, v, k1, hfov):
    """Raw pixel -> final-look pixel through cctv_look's barrel (green channel): solve o = c + (s - c) / scale(o)."""
    f = W / (2 * math.tan(math.radians(hfov / 2)))
    edge = (W / 2 / f) ** 2
    ox, oy = u, v
    for _ in range(8):
        x, y = (ox - W / 2) / f, (oy - H / 2) / f
        s = (1 - k1 * (x * x + y * y)) / (1 - k1 * edge)
        ox, oy = W / 2 + (u - W / 2) / s, H / 2 + (v - H / 2) / s
    return ox, oy


def seen_fraction(cam, pts, dg):
    o = cam.matrix_world.translation
    ok = 0
    for p in pts:
        d = p - o
        L = d.length
        org, hit_other = o.copy(), False
        for _ in range(10):
            hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, org, d.normalized(), distance=max(0.0, L - (org - o).length - 0.01))
            if not hit:
                break
            if ob.name in skip:
                break  # reached the parcel itself
            if ob.type == "MESH" and not ob.visible_get():
                org = loc + d.normalized() * 0.005
                continue
            hit_other = True
            break
        ok += 0 if hit_other else 1
    return ok / len(pts)


cams = [sc.objects[c] for c in sorted(CAMS) if c in sc.objects and sc.objects[c].type == "CAMERA"]
per = {c.name: {} for c in cams}
path = []  # the parcel on the floor plan: [t_s, x, y] (the mini plan's trail)
for f in range(F0, F1 + 1, a.step):
    sc.frame_set(f)
    if obj.hide_render or not obj.visible_get():
        continue
    dg = bpy.context.evaluated_depsgraph_get()
    M = obj.matrix_world
    corners = [M @ Vector(c) for c in obj.bound_box]
    ctr = sum(corners, Vector()) / 8
    if (f - F0) % 10 == 0:
        path.append([round((f - F0) / FPS, 1), round(ctr.x, 2), round(ctr.y, 2)])
    pts = [ctr] + [ctr + (c - ctr) * 0.9 for c in corners]
    for cam in cams:
        uv = [world_to_camera_view(sc, cam, c) for c in corners]
        if any(q.z <= 0.1 for q in uv):
            continue
        k1 = truth.get(cam.name, {}).get("lens_k1", -0.06)
        hfov = CAMS[cam.name].get("hfov_deg", 103.0)
        px = [warp(q.x * W, (1 - q.y) * H, k1, hfov) for q in uv]
        x0, x1 = min(p[0] for p in px), max(p[0] for p in px)
        y0, y1 = min(p[1] for p in px), max(p[1] for p in px)
        if x1 < W * 0.02 or x0 > W * 0.98 or y1 < H * 0.02 or y0 > H * 0.98:
            continue
        sf = seen_fraction(cam, pts, dg)
        if sf >= a.min_seen:
            per[cam.name][f] = [round(max(0.0, x0 / W), 4), round(max(0.0, y0 / H), 4),
                                round(min(1.0, x1 / W), 4), round(min(1.0, y1 / H), 4), round(sf, 2)]

sightings = []
for cam in cams:
    fr = sorted(per[cam.name])
    runs, cur = [], []
    for f in fr:
        if cur and f - cur[-1] > FPS * 1.0:
            runs.append(cur)
            cur = []
        cur.append(f)
    if cur:
        runs.append(cur)
    for r in runs:
        if (r[-1] - r[0]) / FPS < 1.0:
            continue
        sightings.append(dict(camera=cam.name, f0=r[0], f1=r[-1], t0_s=round((r[0] - F0) / FPS, 1),
                              t1_s=round((r[-1] - F0) / FPS, 1),
                              boxes={str(f): per[cam.name][f][:4] for f in r if f in per[cam.name]},
                              seen={str(f): per[cam.name][f][4] for f in r if f in per[cam.name]}))
sightings.sort(key=lambda s: (s["f0"], s["camera"]))
out = dict(
    kind="ground_truth", note="Blender ground truth of the S2 render (not a tracker's output)",
    object=a.object, story_parcel=scen.get("story_parcel"), fps=FPS, frames=[F0, F1], t0=scen.get("t0"),
    scenario=dict(picked_t_s=scen.get("picked_t_s"), enters_blind_t_s=scen.get("enters_blind_t_s"),
                  exits_empty_t_s=scen.get("exits_empty_t_s"), cage_id=scen.get("cage_id")),
    cameras=[dict(id=c, name=CAMS[c].get("osd_label") or c, seen_frames=len(per.get(c, {})))
             for c in sorted(CAMS)],
    sightings=sightings, path=path,
    camera_xy={c: [CAMS[c]["position_m"][0], CAMS[c]["position_m"][1]] for c in sorted(CAMS)})
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
Path(a.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
print("LANDING_TRUTH", json.dumps([(s["camera"], s["t0_s"], s["t1_s"], len(s["boxes"])) for s in sightings]))
