"""Turntable per scanner (Rexton 1 Nov: Blender quality you can turn, low and high): two rings of N frames around the
scanner, looking at it, roof off: "mid" 9 m out and 5.5 m up, "high" 6 m out and 16 m up (nearly straight down); frame 0
of each ring is where the zone's 3D map picture looks from (the "3D" view), then every 360/N degrees anticlockwise
seen from above. A wall between the camera and the scanner is out for that frame (a
cutaway). The app drags through the frames. S2 final at one frame, workers in, the S2 actor and its parcel out.

  blender -b <S2_final.blend> -P assets/hub/place_turn.py -- --out assets/places/out/turn [--n 24] [--ids SP-DIV-C12,...]
      [--res 1280x720] [--samples 16]
      [--mapdir headings.json]   (zone -> heading in radians, when the locator's folder is not there, e.g. on Modal)
      -> <out>/<id>/<ring>_<k>.jpg + <out>/turn.json (per scanner, ring and frame: its pixel, the others' pixels)
"""
import json
import math
import re
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

HUB = Path(__file__).resolve().parent
ROOT = HUB.parent.parent
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
arg = {k[2:]: v for k, v in zip(argv[::2], argv[1::2])}
OUT = (ROOT / arg.get("out", "assets/places/out/turn")).resolve()
N = int(arg.get("n", 24))
W, H = (int(v) for v in arg.get("res", "1280x720").split("x"))
SPEC = json.loads((HUB / "hub_spec.json").read_text(encoding="utf-8"))
PTS = [s for s in SPEC["scan_points"] if not arg.get("ids") or s["id"] in arg["ids"].split(",")]
RINGS = {"mid": (9.0, 5.5), "high": (6.0, 16.0)}  # radius, height (m)
ROOF = re.compile(r"^(roof|ceiling|highbay_fixtures|mounted_fluorescent|structure$|led_rows$)", re.I)
OUT.mkdir(parents=True, exist_ok=True)

sc = bpy.context.scene
sc.frame_set(int(arg.get("frame", 300)))
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = int(arg.get("samples", 16))
sc.eevee.use_raytracing = False
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Medium High Contrast"
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.render.image_settings.file_format = "JPEG"
sc.render.image_settings.quality = 85


def tree(o):
    yield o
    for c in o.children:
        yield from tree(c)


actor = sc.objects.get("worker_s2_1")  # the S2 case's person: never in a where-is-it picture
if actor:
    hips = actor.matrix_world @ actor.pose.bones[0].head
    for o in sc.objects:
        if o in set(tree(actor)) or (o.name.startswith("flow_parcel") and (o.matrix_world.translation - hips).length < 0.9):
            o.hide_render = o.hide_viewport = True
for o in sc.objects:
    if ROOF.match(o.name):
        o.hide_render = True
walls = {k: sc.objects.get(f"wall_{k}") for k in "NSEW"}
data = bpy.data.cameras.new("place_turn")
cam = bpy.data.objects.new("place_turn", data)
sc.collection.objects.link(cam)
sc.camera = cam
data.lens, data.sensor_width, data.clip_start, data.clip_end = 28, 36, 0.1, 400

MAPDIR = json.loads(Path(arg["mapdir"]).read_text(encoding="utf-8")) if arg.get("mapdir") else {}
for zid in {s["zone"] for s in SPEC["scan_points"]}:
    j = ROOT / "assets" / "locator" / "out" / "_raw" / f"{zid}_map.json"
    if zid not in MAPDIR and j.exists():
        c = json.loads(j.read_text(encoding="utf-8"))["three_camera"]
        MAPDIR[zid] = math.atan2(-(c["position"][2] - c["target"][2]), c["position"][0] - c["target"][0])


def px(p):
    v = world_to_camera_view(sc, cam, Vector(p))
    return [round(v.x * 1600, 1), round((1 - v.y) * 900, 1)], (v.z > 0 and 0 <= v.x <= 1 and 0 <= v.y <= 1)  # 1600x900 units


meta = json.loads((OUT / "turn.json").read_text(encoding="utf-8")) if (OUT / "turn.json").exists() else {}
for s in PTS:
    t = Vector(s["position_m"])
    aim = Vector((t.x, t.y, 1.0))
    base = MAPDIR.get(s["zone"], math.radians(-120))
    d = OUT / s["id"]
    d.mkdir(exist_ok=True)
    rings = {}
    for ring, (radius, height) in RINGS.items():
        frames = rings[ring] = []
        for k in range(N):
            a = base + 2 * math.pi * k / N
            c = Vector((t.x + radius * math.cos(a), t.y + radius * math.sin(a), height))
            for key, w in walls.items():  # the wall on the camera's side goes while the camera is beyond it
                if w:
                    w.hide_render = (key == "S" and c.y < 0.5) or (key == "N" and c.y > 39.5) or (key == "W" and c.x < 0.5) or (key == "E" and c.x > 59.5)
            cam.matrix_world = Matrix.Translation(c) @ (aim - c).to_track_quat("-Z", "Y").to_matrix().to_4x4()
            bpy.context.view_layer.update()
            sc.render.filepath = str(d / f"{ring}_{k:02d}.jpg")
            bpy.ops.render.render(write_still=True)
            here, _ = px(s["position_m"])
            mates = {}
            for m in SPEC["scan_points"]:
                if m["id"] != s["id"] and m["zone"] == s["zone"]:
                    q, inside = px(m["position_m"])
                    if inside:
                        mates[m["id"]] = {"x": q[0], "y": q[1]}
            frames.append({"x": here[0], "y": here[1], "mates": mates})
    meta[s["id"]] = {"zone": s["zone"], "n": N, "rings": rings}
    (OUT / "turn.json").write_text(json.dumps(meta, separators=(",", ":")), encoding="utf-8")
    print("TURN", s["id"], flush=True)
print("TURN done", len(PTS), flush=True)
