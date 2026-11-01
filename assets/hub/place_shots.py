"""Three Blender pictures per scanner, each aimed at that scanner (Rexton 1 Nov: a row of 12 chutes needs the picture
on the right one; Blender looks better than the live model):
  tilt  the 3D map view: from the direction the zone's 3D map picture looks from, 11 m out and 8.5 m up, roof off
  top   straight down from above it, north up (orthographic, 18 m across), roof off, no hard sun shadows
  eye   1.6 m high, 3.5-6 m off, looking straight at it: from the tilt direction where clear, else the nearest clear
        direction (on the floor, not on equipment; nothing within 0.45 m; an open line to the scanner)
S2 final at one frame, workers in, the S2 actor and its parcel out (as place_views.py). A wall between a tilt camera
and the scanner is taken out for that shot (a cutaway).

  blender -b <S2_final.blend> -P assets/hub/place_shots.py -- --out assets/places/out/pt [--frame 300] [--ids SP-DIV-C12,...]
      -> <out>/<id>_<view>.jpg + <out>/pt.json (per scanner and view: its pixel, the zone's other scanners' pixels)
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
OUT = (ROOT / arg.get("out", "assets/places/out/pt")).resolve()
FRAME = int(arg.get("frame", 300))
SPEC = json.loads((HUB / "hub_spec.json").read_text(encoding="utf-8"))
PTS = [s for s in SPEC["scan_points"] if not arg.get("ids") or s["id"] in arg["ids"].split(",")]
W, H, EYE = 1600, 900, 1.6
ROOF = re.compile(r"^(roof|ceiling|highbay_fixtures|mounted_fluorescent|structure$|led_rows$)", re.I)
OUT.mkdir(parents=True, exist_ok=True)

sc = bpy.context.scene
sc.frame_set(FRAME)
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = int(arg.get("samples", 24))
sc.eevee.use_raytracing = False
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Medium High Contrast"
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.render.image_settings.file_format = "JPEG"
sc.render.image_settings.quality = 90


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
roof = [o for o in sc.objects if ROOF.match(o.name) and not o.hide_render]
walls = {k: sc.objects.get(f"wall_{k}") for k in "NSEW"}
suns = [o for o in sc.objects if o.type == "LIGHT" and o.data.type == "SUN"]
sys.path.insert(0, str(ROOT / "assets" / "locator"))
import cutaway  # the locator's office-ceiling cut (in memory only)

data = bpy.data.cameras.new("place_pt")
cam = bpy.data.objects.new("place_pt", data)
sc.collection.objects.link(cam)
sc.camera = cam
data.sensor_width, data.clip_start, data.clip_end = 36, 0.1, 400

# the direction the app's 3D map picture looks from, per zone (three.js camera3 -> site floor heading)
MAPDIR = {}
for zid in {s["zone"] for s in SPEC["scan_points"]}:
    j = ROOT / "assets" / "locator" / "out" / "_raw" / f"{zid}_map.json"
    if j.exists():
        c = json.loads(j.read_text(encoding="utf-8"))["three_camera"]
        MAPDIR[zid] = math.atan2(-(c["position"][2] - c["target"][2]), c["position"][0] - c["target"][0])


def dg():
    return bpy.context.evaluated_depsgraph_get()


def cast(o, d, dist):
    hit, loc, nrm, idx, obj, mat = sc.ray_cast(dg(), o, d.normalized(), distance=dist)
    return loc if hit else None


def open_line(c, t):
    loc = cast(c, t - c, (t - c).length)
    return loc is None or (loc - t).length < 0.7  # nothing between, or the hit is the scanner's own device


def clear(c, t):
    if not (0.6 < c.x < 59.4 and 0.6 < c.y < 39.4):
        return False
    loc = cast(c, Vector((0, 0, -1)), 3.0)
    if loc is None or loc.z > 0.08:  # standing on equipment, or nothing under it
        return False
    for k in range(8):
        a = k * math.pi / 4
        for z in (0.4, 1.0, 1.6):
            if cast(Vector((c.x, c.y, z)), Vector((math.cos(a), math.sin(a), 0)), 0.45) is not None:
                return False
    return open_line(c, t)


def eye_spot(s, t):
    base = MAPDIR.get(s["zone"], math.radians(-120))
    for dist in (4.5, 6.0, 3.5):
        for k in range(13):
            a = base + (1 if k % 2 else -1) * math.ceil(k / 2) * math.radians(30)
            c = Vector((t.x + dist * math.cos(a), t.y + dist * math.sin(a), EYE))
            if clear(c, t):
                return c
    return None


def look(c, t):
    cam.matrix_world = Matrix.Translation(c) @ (t - c).to_track_quat("-Z", "Y").to_matrix().to_4x4()


def px(p):
    v = world_to_camera_view(sc, cam, Vector(p))
    return [round(v.x * W, 1), round((1 - v.y) * H, 1)], (v.z > 0 and 0 <= v.x <= 1 and 0 <= v.y <= 1)


def roof_off(off):
    for r in roof:
        r.hide_render = r.hide_viewport = off


def shot(s, view, check_lines):
    bpy.context.view_layer.update()
    sc.render.filepath = str(OUT / f"{s['id']}_{view}.jpg")
    bpy.ops.render.render(write_still=True)
    here, _ = px(s["position_m"])
    c = cam.matrix_world.translation.copy()
    mates = {}
    for m in SPEC["scan_points"]:
        if m["id"] == s["id"] or m["zone"] != s["zone"]:
            continue
        q, inside = px(m["position_m"])
        if inside and (not check_lines or open_line(c, Vector(m["position_m"]))):
            mates[m["id"]] = {"x": q[0], "y": q[1]}
    return {"image": f"{s['id']}_{view}.jpg", "x": here[0], "y": here[1], "mates": mates}


meta = json.loads((OUT / "pt.json").read_text(encoding="utf-8")) if (OUT / "pt.json").exists() else {}
for s in PTS:
    t = Vector(s["position_m"])
    m = meta.setdefault(s["id"], {"zone": s["zone"]})
    base = MAPDIR.get(s["zone"], math.radians(-120))
    # tilt: roof off, the wall on the camera's side out
    roof_off(True)
    data.type, data.lens = "PERSP", 28
    c = Vector((t.x + 11 * math.cos(base), t.y + 11 * math.sin(base), 8.5))
    hid = [w for k, w in walls.items() if w and ((k == "S" and c.y < 1) or (k == "N" and c.y > 39) or (k == "W" and c.x < 1) or (k == "E" and c.x > 59))]
    for w in hid:
        w.hide_render = True
    look(c, Vector((t.x, t.y, 1.0)))
    m["tilt"] = shot(s, "tilt", False)
    for w in hid:
        w.hide_render = False
    # top: straight down, north up, roof and office ceiling off, no hard sun shadows, a touch darker (flat light)
    for o in suns:
        o.data.use_shadow = False
    cutaway.office_ceiling(sc, SPEC, next(z for z in SPEC["zones"] if z["kind"] == "office"))
    sc.view_settings.exposure = -0.7
    data.type, data.ortho_scale = "ORTHO", 18.0
    cam.matrix_world = Matrix.Translation((t.x, t.y, 30.0))
    m["top"] = shot(s, "top", False)
    sc.view_settings.exposure = 0.0
    cutaway.restore(sc)
    for o in suns:
        o.data.use_shadow = True
    roof_off(False)
    # eye: on the floor, aimed at it
    data.type, data.lens = "PERSP", 22
    c = eye_spot(s, t)
    if c:
        look(c, Vector((t.x, t.y, min(t.z, 1.4))))
        m["eye"] = shot(s, "eye", True)
        m["eye"]["camera_m"] = [round(c.x, 2), round(c.y, 2), EYE]
    else:
        m["eye"] = None
    (OUT / "pt.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print("PT", s["id"], "eye" if c else "no eye spot", flush=True)
print("PT done", len(PTS), flush=True)
