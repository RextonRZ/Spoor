"""Where-is-it pictures for the app's Places (Rexton 1 Nov): per zone a straight-down view (roof off, north up) and an
eye-height photo WITH the station workers (the locator's own eye camera, assets/locator/out/_raw/<zone>_eye.json), from
the S2 final at one frame; plus a top-down of the whole hub. The tilted 3D maps are the locator agent's
(assets/locator/out/<zone>_map.png) and are not re-rendered here.

For every picture (ours and the locator's maps) places.json gives the pixel position of each scan point (a "place" in
the app) and the zone outline, so the app can draw the pins and the outline itself (crisp, clickable).

  blender -b <S2_final.blend> -P assets/hub/place_views.py -- --out assets/places/out [--frame 300] [--zones Z01,Z03]
      [--only top|hub]   (re-render the from-above pictures only; eye / map entries kept from places.json)
"""
import json
import math
import re
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Euler, Matrix, Vector

HUB = Path(__file__).resolve().parent
ROOT = HUB.parent.parent
LOC = ROOT / "assets" / "locator" / "out"
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
arg = {k[2:]: v for k, v in zip(argv[::2], argv[1::2])}
OUT = (ROOT / arg.get("out", "assets/places/out")).resolve()
FRAME = int(arg.get("frame", 300))
SPEC = json.loads((HUB / "hub_spec.json").read_text(encoding="utf-8"))
ZONES = [z for z in SPEC["zones"] if not arg.get("zones") or z["id"] in arg["zones"].split(",")]
W, H = 1600, 900
ROOF = re.compile(r"^(roof|ceiling|highbay_fixtures|mounted_fluorescent|structure$|led_rows$)", re.I)
S2_ACTOR = "worker_s2_1"  # the S2 case's person: never in a where-is-it picture (it would give the case away)

sc = bpy.context.scene
sc.frame_set(FRAME)
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 32
sc.eevee.use_raytracing = False
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Medium High Contrast"
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.render.image_settings.file_format = "JPEG"
sc.render.image_settings.quality = 90
OUT.mkdir(parents=True, exist_ok=True)


def tree(o):
    yield o
    for c in o.children:
        yield from tree(c)


# the S2 actor and whatever it carries (any parcel within 0.9 m of its hips at this frame)
actor = sc.objects.get(S2_ACTOR)
hidden_s2 = []
if actor:
    hips = actor.matrix_world @ actor.pose.bones[0].head
    for o in sc.objects:
        near = o.name.startswith("flow_parcel") and (o.matrix_world.translation - hips).length < 0.9
        if o in set(tree(actor)) or near:
            o.hide_render = o.hide_viewport = True
            hidden_s2.append(o.name)
roof = [o for o in sc.objects if ROOF.match(o.name) and not o.hide_render]
suns = [o for o in sc.objects if o.type == "LIGHT" and o.data.type == "SUN"]
sys.path.insert(0, str(ROOT / "assets" / "locator"))
import cutaway  # the locator's office-ceiling cut (in memory only)

data = bpy.data.cameras.new("place_view")
cam = bpy.data.objects.new("place_view", data)
sc.collection.objects.link(cam)
sc.camera = cam
data.clip_start, data.clip_end, data.sensor_fit = 0.1, 500, "HORIZONTAL"


def polys(z):
    v = z["polygon_m"]
    return list(v.values()) if isinstance(v, dict) else [v]


def floor_z(z):
    return -1.2 if z["kind"] == "yard" else 0.0


def px(p):
    v = world_to_camera_view(sc, cam, Vector(p))
    return [round(v.x * W, 1), round((1 - v.y) * H, 1), v.z > 0 and 0 <= v.x <= 1 and 0 <= v.y <= 1]


def seen(p, own=()):
    """Line of sight from the camera to a point (people / parcels count as blockers too; `own`: the point's own
    objects, a hit on those still counts as seen)."""
    o = cam.matrix_world.translation
    d = Vector(p) - o
    hit, loc, nrm, idx, obj, mat = sc.ray_cast(bpy.context.evaluated_depsgraph_get(), o, d.normalized(),
                                               distance=d.length - 0.15)
    return not hit or (obj is not None and obj.original.name in own)


def project(zone_id=None, occlusion=False):
    """Pixel positions of every scan point and every zone outline for the current camera."""
    bpy.context.view_layer.update()
    pts = {}
    for s in SPEC["scan_points"]:
        x, y, z = px(s["position_m"])
        if z:
            pts[s["id"]] = {"x": x, "y": y, "zone": s["zone"], **({"seen": seen(s["position_m"])} if occlusion else {})}
    zones = {}
    for z in SPEC["zones"]:
        if zone_id and z["id"] != zone_id:
            continue
        fz = floor_z(z)
        zones[z["id"]] = [[px((p[0], p[1], fz))[:2] for p in poly] for poly in polys(z)]
    return {"scan_points": pts, "zones": zones}


def shot(name):
    sc.render.filepath = str(OUT / name)
    bpy.ops.render.render(write_still=True)
    print("PLACE", name, flush=True)


def roof_off(off):
    """From above: roof, ceilings and the office ceiling off, and no hard sun shadows (with the roof gone the walls
    threw them across half the floor)."""
    for r in roof:
        r.hide_render = r.hide_viewport = off
    for o in suns:
        o.data.use_shadow = not off
    sc.view_settings.exposure = float(arg.get("top_exposure", -0.7)) if off else 0.0  # flat light reads washed out
    if off:
        cutaway.office_ceiling(sc, SPEC, next(z for z in SPEC["zones"] if z["kind"] == "office"))
    else:
        cutaway.restore(sc)


def top(cx, cy, w, h, fz):
    """Straight down, north up, the rectangle w x h (m) centred on (cx, cy) filling 16:9."""
    data.type = "ORTHO"
    data.ortho_scale = max(w, h * W / H)
    cam.matrix_world = Matrix.Translation((cx, cy, fz + 40.0))


def people_in_view():
    out = []
    for o in sc.objects:
        if o.type == "ARMATURE" and o.name.startswith("worker_") and not o.hide_render:
            p = o.matrix_world @ o.pose.bones[0].head
            x, y, ok = px(p)
            if ok and seen(p + Vector((0, 0, 0.5)), {t.name for t in tree(o)}):
                out.append(o.name)
    return out


_old = OUT / "places.json"
PREV = json.loads(_old.read_text(encoding="utf-8"))["zones"] if _old.exists() else {}
meta = {"frame": FRAME, "size": [W, H], "hidden_for_case": hidden_s2, "zones": {}}
for z in ([] if arg.get("only") == "hub" else ZONES):
    zid = z["id"]
    m = meta["zones"][zid] = {"name": z["name"]}
    fz = floor_z(z)
    xs = [p[0] for poly in polys(z) for p in poly]
    ys = [p[1] for poly in polys(z) for p in poly]
    pad = 2.0 if z["kind"] != "yard" else 3.0
    # top (roof off)
    roof_off(True)
    top((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad, fz)
    shot(f"{zid}_top.jpg")
    m["top"] = {"image": f"{zid}_top.jpg", **project(zid)}
    roof_off(False)
    if arg.get("only") == "top":
        m.update({k: v for k, v in PREV.get(zid, {}).items() if k in ("eye", "map")})
        continue
    # eye height, the locator's camera, people in
    ej = LOC / "_raw" / f"{zid}_eye.json"
    if ej.exists():
        c = json.loads(ej.read_text(encoding="utf-8"))["camera"]
        data.type, data.lens, data.sensor_width = "PERSP", c["lens"], c.get("sensor_width", 36)
        cam.matrix_world = Matrix.Translation(c["location"]) @ Euler(c["rotation"], "XYZ").to_matrix().to_4x4()
        bpy.context.view_layer.update()
        shot(f"{zid}_eye.jpg")
        m["eye"] = {"image": f"{zid}_eye.jpg", "people": people_in_view(), **project(zid, occlusion=True)}
    # the locator's tilted map: pins only (its picture is used as it is)
    mj = LOC / "_raw" / f"{zid}_map.json"
    if mj.exists():
        c = json.loads(mj.read_text(encoding="utf-8"))["camera"]
        data.type, data.lens, data.sensor_width = "PERSP", c["lens"], c.get("sensor_width", 36)
        cam.matrix_world = Matrix.Translation(c["location"]) @ Euler(c["rotation"], "XYZ").to_matrix().to_4x4()
        m["map"] = {"image": f"assets/locator/out/{zid}_map.png", **project(zid)}

if not arg.get("zones"):  # the whole hub, straight down
    roof_off(True)
    bx, by = SPEC["building"]["footprint_m"]  # the building (every scanner is inside; the yard made it tiny)
    top(bx / 2, by / 2, bx + 3, by + 3, 0.0)
    sc.render.resolution_percentage = 200  # 3200 x 1800: the app zooms into it (pixels stay in 1600 x 900 units)
    shot("hub_top.jpg")
    sc.render.resolution_percentage = 100
    meta["hub_top"] = {"image": "hub_top.jpg", "m_per_px": data.ortho_scale / W, **project()}

old = OUT / "places.json"
if (arg.get("zones") or arg.get("only") == "hub") and old.exists():
    prev = json.loads(old.read_text(encoding="utf-8"))
    prev["zones"].update(meta["zones"])
    meta = {**prev, **({"hub_top": meta["hub_top"]} if "hub_top" in meta else {}), "zones": prev["zones"]}
old.write_text(json.dumps(meta, indent=1), encoding="utf-8")
print("PLACES done", len(meta["zones"]), "zones; hidden for the case:", hidden_s2, flush=True)
