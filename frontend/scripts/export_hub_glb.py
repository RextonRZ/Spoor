"""Export the dressed hub to a web GLB for the Spoor frontend (QUEUE C2).

Run headless on a COPY of hub_dressed.blend (the builder rewrites the original while it works):

    "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --factory-startup <copy.blend> \
        -P frontend/scripts/export_hub_glb.py -- --src-dir assets/hub/build --spec assets/hub/hub_spec.json \
        --out frontend/public/hub.glb

What it does (on the in-memory copy only; nothing is saved back to any .blend):
- drops objects that are not rendered (asset templates parked at the origin, hidden helpers);
- drops people (collections People / PeopleTemplates, objects worker_* / Bip01* / mixamo*), animated parcels
  (collection Flow, objects flow_*), lamps and Blender cameras (frusta come from hub_spec, not from the mesh);
- clears every animation so carriers sit at their rest pose;
- decimates heavy meshes, shrinks textures to <= 512 px, writes JPEG textures and Draco-compressed geometry;
- tags every exported node with glTF extras: `spoor_id` (= object name) and `zone_id` (hub_spec zone containing the
  object's footprint centre, or none), so the web scene uses the same IDs as hub_spec.

The blend is in the site frame (metres, X east, Y north, Z up, origin SW outside corner). The glTF exporter's +Y-up
conversion maps Blender (x, y, z) -> glTF (x, z, -y), identical to backend spoor.spatial.frames.site_to_renderer.
"""

import json
import re
import sys
from pathlib import Path

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
args = dict(zip(argv[::2], argv[1::2], strict=False))
SRC_DIR = Path(args.get("--src-dir", "assets/hub/build")).resolve()
SPEC = json.loads(Path(args.get("--spec", "assets/hub/hub_spec.json")).read_text(encoding="utf-8"))
OUT = Path(args.get("--out", "frontend/public/hub.glb")).resolve()
REPORT = OUT.with_suffix(".export.json")
MAX_TEX = int(args.get("--max-tex", "512"))
TARGET_FACES = int(args.get("--target-faces", "2500"))

DROP_COLLECTIONS = {"People", "PeopleTemplates", "Flow"}
DROP_PREFIXES = ("worker_", "Bip01", "mixamo", "flow_")
PERSON_ASSET = re.compile(r"^[fm]\d{3}_")  # Rocketbox character meshes (f019_..., m007_...)
KEEP_FULL = {"text_signs_merged", "floor_markings", "structure", "floor_slab"}  # thin text/lines decimate badly

report = {"source": bpy.data.filepath, "dropped": [], "decimated": {}, "kept": 0}

# --- 1. drop people, animated parcels, lamps, cameras ---------------------------------------------------------
drop = set()
for c in bpy.data.collections:
    if c.name in DROP_COLLECTIONS:
        drop.update(c.all_objects)
for o in bpy.data.objects:
    if o.type == "MESH" and not o.name.startswith(("wall", "roof", "structure", "text_signs")):
        top = max((o.matrix_world @ Vector(c)).z for c in o.bound_box)
        if top > SPEC["building"]["eaves_m"] + 1.5:  # a prop above the roof is a scale error in the source scene
            report.setdefault("dropped_oversize", []).append({"name": o.name, "top_z_m": round(top, 2)})
            drop.add(o)
            continue
    animated_parcel = "parcel" in o.name.lower() and o.animation_data is not None
    not_rendered = o.hide_render or not o.visible_get()  # asset templates parked at the origin, helpers
    if o.name.startswith(DROP_PREFIXES) or PERSON_ASSET.match(o.name) or o.type in {"LIGHT", "CAMERA", "ARMATURE"} or animated_parcel or not_rendered:
        drop.add(o)
for o in drop:
    report["dropped"].append(o.name)
for o in list(drop):
    bpy.data.objects.remove(o, do_unlink=True)
for c in list(bpy.data.collections):
    if c.name in DROP_COLLECTIONS:
        bpy.data.collections.remove(c)

# --- 2. freeze: no animation, rest frame ----------------------------------------------------------------------
bpy.context.scene.frame_set(1)
for o in bpy.data.objects:
    if o.animation_data:
        o.animation_data_clear()
    if o.type == "MESH" and o.data.shape_keys and o.data.shape_keys.animation_data:
        o.data.shape_keys.animation_data_clear()

# --- 2b. walls: the cladding node tree does not survive glTF export (it falls back to a dark maroon factor), so the
# web copy gets a plain light material close to the white-walled CCTV look (review 004 #4).
wall_mat = bpy.data.materials.new("web_wall_light")
if hasattr(wall_mat, "use_nodes"):
    wall_mat.use_nodes = True
bsdf = next((n for n in wall_mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if wall_mat.node_tree else None
if bsdf is not None:
    bsdf.inputs["Base Color"].default_value = (0.78, 0.78, 0.76, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.85
wall_mat.diffuse_color = (0.78, 0.78, 0.76, 1.0)
for o in bpy.data.objects:
    if o.type == "MESH" and o.name in {"wall_N", "wall_S", "wall_E", "wall_W"}:
        o.data = o.data.copy()
        o.data.materials.clear()
        o.data.materials.append(wall_mat)
        report.setdefault("material_overrides", []).append(o.name)

# --- 3. zone tags ----------------------------------------------------------------------------------------------
ZONES = []
for z in SPEC["zones"]:  # Z14 (yard) is a dict of named parts; the rest are single polygons
    polys = z["polygon_m"].values() if isinstance(z["polygon_m"], dict) else [z["polygon_m"]]
    ZONES += [(z["id"], p) for p in polys]


def inside(pt, poly) -> bool:
    x, y = pt
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1], strict=True):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


for o in bpy.data.objects:
    o["spoor_id"] = o.name
    if o.type != "MESH":
        continue
    corners = [o.matrix_world @ Vector(c) for c in o.bound_box]
    cx = sum(c.x for c in corners) / 8
    cy = sum(c.y for c in corners) / 8
    span = max(c.x for c in corners) - min(c.x for c in corners), max(c.y for c in corners) - min(c.y for c in corners)
    if span[0] > 25 or span[1] > 25:  # merged hub-wide meshes belong to no single zone
        continue
    for zid, poly in ZONES:
        if inside((cx, cy), poly):
            o["zone_id"] = zid
            break

# --- 4. decimate heavy meshes ------------------------------------------------------------------------------------
for o in bpy.data.objects:
    if o.type != "MESH" or o.name in KEEP_FULL:
        continue
    n = len(o.data.polygons)
    if n <= TARGET_FACES:
        continue
    ratio = max(0.03, TARGET_FACES / n)
    m = o.modifiers.new("web_decimate", "DECIMATE")
    m.decimate_type = "COLLAPSE"
    m.ratio = ratio
    report["decimated"][o.name] = {"faces": n, "ratio": round(ratio, 3)}

# --- 5. textures: resolve paths against the ORIGINAL build dir, shrink -------------------------------------------
for img in bpy.data.images:
    if img.packed_file is None and img.filepath.startswith("//"):
        img.filepath = str(SRC_DIR / img.filepath[2:].replace("\\", "/"))
    try:
        if img.size[0] == 0:
            img.reload()
        w, h = img.size
        if max(w, h) > MAX_TEX:
            s = MAX_TEX / max(w, h)
            img.scale(max(1, int(w * s)), max(1, int(h * s)))
    except RuntimeError as e:  # missing file: exporter falls back to the material's base colour
        print("texture skipped", img.name, e)

report["kept"] = sum(1 for o in bpy.data.objects if o.type == "MESH")

# --- 6. export ---------------------------------------------------------------------------------------------------
OUT.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.export_scene.gltf(
    filepath=str(OUT),
    export_format="GLB",
    export_yup=True,
    export_apply=True,
    export_extras=True,
    export_animations=False,
    export_skins=False,
    export_morph=False,
    export_lights=False,
    export_cameras=False,
    export_image_format="JPEG",
    export_jpeg_quality=80,
    export_draco_mesh_compression_enable=True,
    export_draco_mesh_compression_level=6,
    export_draco_position_quantization=14,
    export_draco_normal_quantization=10,
    export_draco_texcoord_quantization=12,
)
report["bytes"] = OUT.stat().st_size
report["faces_after"] = sum(len(o.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.polygons)
                            for o in bpy.data.objects if o.type == "MESH")  # fmt: skip
REPORT.write_text(json.dumps(report, indent=1), encoding="utf-8")
print("EXPORT " + json.dumps({k: report[k] for k in ("bytes", "kept", "faces_after")} | {"dropped": len(report["dropped"])}))
