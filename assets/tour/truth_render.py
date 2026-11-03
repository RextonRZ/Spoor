"""What really happened, for the "Compare with what really happened" button (reviewer 01:25, Rexton): the simulation's
own story parcel, rendered from the hub blend with its people and moving cartons visible, the drone following the
parcel the way the fly-through follows Spoor's evidence. Ground truth used only to grade: Spoor never reads it, and
the page shows this clip only behind its own button, labelled "Simulation ground truth. Not used by Spoor."

The parcel's position comes from the render-side truth (truth/flow_truth_<S>.json, its per-frame track); the moment
(picked off the cage, into the store, out empty-handed) from truth/scenario_<S>.json. Workers are the anonymous 3D
characters of the scene, seen from the drone's height (no faces close up).

  blender -b <hub blend> -P assets/tour/truth_render.py -- --scenario assets/hub/build/truth/scenario_S2.json \
      --out assets/tour/truth [--res 1600x900 --samples 8 --pad 2 --every 1]
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument("--scenario", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--res", default="1600x900")
ap.add_argument("--samples", type=int, default=8)
ap.add_argument("--pad", type=float, default=2.0, help="seconds before the pick and after the empty-handed exit")
ap.add_argument("--every", type=int, default=1)
ap.add_argument("--hub", default="frontend/src/data/hub.generated.json")
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])

OFFSET = Vector((-1.6, -5.2, 9.6))   # steeper than the fly-through (~60 deg): it sees over the store's 3 m partitions
HIDE = re.compile(r"^(roof|roof_lights|roof_services|highbay|mounted_fluorescent|wall_S|wall_E|structure)")

scn = json.loads(Path(args.scenario).read_text(encoding="utf-8"))
truth_dir = Path(args.scenario).parent
flow = json.loads((truth_dir / f"flow_truth_{scn['scenario']}.json").read_text(encoding="utf-8"))
fps = flow["fps"]
track = next(p for p in flow["parcels"] if p["object"] == scn["story_object"])["track"]
f_pick, f_out = round(scn["picked_t_s"] * fps) + 1, round(scn["exits_empty_t_s"] * fps) + 1
f0, f1 = max(flow["frames"][0], f_pick - round(args.pad * fps)), min(flow["frames"][1], f_out + round(args.pad * fps))

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
for o in sc.objects:   # the building's lid and near walls only; the people and the moving cartons stay
    if HIDE.match(o.name):
        o.hide_render = True
    if o.type == "LIGHT" and o.name.startswith("ledrow_"):
        o.data.use_shadow = False

cd = bpy.data.cameras.new("truth_cam")
cd.lens, cd.sensor_width, cd.clip_end = 22, 36, 300
cam = bpy.data.objects.new("truth_cam", cd)
sc.collection.objects.link(cam)
sc.camera = cam


def pos(f):
    p = track.get(str(f)) or track[str(min(track, key=lambda k: abs(int(k) - f)))]
    return Vector(p)


# the drone follows the parcel, smoothed over ~1.6 s so a turn in the person's walk is a glide, not a jerk
W = round(0.8 * fps)
look = {f: sum((pos(min(f1, max(f0, g))) for g in range(f - W, f + W + 1)), Vector()) / (2 * W + 1) for f in range(f0, f1 + 1)}
out = Path(args.out).resolve()
(out / "frames").mkdir(parents=True, exist_ok=True)
mats, marker = [], []
t0 = time.time()
for i, f in enumerate(range(f0, f1 + 1, args.every)):
    sc.frame_set(f)
    tgt = look[f]
    cam.location = Vector((tgt.x, tgt.y, 0)) + OFFSET
    cam.location.x = min(57.0, max(4.0, cam.location.x))
    cam.rotation_euler = (Vector((tgt.x, tgt.y, 0.8)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()
    P = cam.calc_matrix_camera(bpy.context.evaluated_depsgraph_get(), x=rx, y=ry) @ cam.matrix_world.inverted()
    mats.append([round(v, 5) for row in P for v in row])
    marker.append([round(v, 4) for v in world_to_camera_view(sc, cam, pos(f))[:2]])
    sc.render.filepath = str(out / "frames" / f"f{i:05d}.jpg")
    bpy.ops.render.render(write_still=True)
    if i % 30 == 0:
        print(f"TRUTH frame {i}/{(f1 - f0) // args.every + 1} {time.time() - t0:.0f}s", flush=True)

hub = json.loads(Path(args.hub).read_text(encoding="utf-8"))
zone = scn["final_location"]["zone"]
meta = {"label": "Simulation ground truth. Not used by Spoor.", "scenario": scn["scenario"], "parcel_id": scn["story_parcel"],
        "fps": fps, "frames": len(mats), "size": [rx, ry], "sim_frames": [f0, f1], "t0": scn["t0"],
        "start_t_s": round((f0 - 1) / fps, 1), "moments_t_s": {k: scn[k] for k in ("picked_t_s", "enters_blind_t_s", "placed_t_s", "exits_empty_t_s")},
        "truth": {"zone": zone, "zone_name": next((z["name"] for z in hub["zones"] if z["id"] == zone), zone),
                  "where": scn["final_location"]["where"]},
        "P": mats, "marker": marker}
(out / "truth.json").write_text(json.dumps(meta, separators=(",", ":")), encoding="utf-8")
print(f"TRUTH done {len(mats)} frames in {time.time() - t0:.0f}s")
