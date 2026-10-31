"""Workers for the Spoor demo hub: Microsoft Rocketbox avatars (MIT) in CONTOH Express uniform + hi-vis vests,
placed by station, each facing their task with their own clip and start offset (no two neighbours in sync).

Imported by dress_hub.py (--people). Rocketbox has walk / idle / work-at-table / work-mid / crouch / trolley /
documents / talk / phone clips but NO carry, lift or push: those come from Mixamo on the CC BY vest worker once its
files exist (third_party/mixamo/).

Uniform: the avatars' clothing is a baked texture atlas, so the upper-body garment is re-tinted to the brand teal in
the shader (skin is kept by a hue/saturation test, legs by a height band in rest-pose coordinates). The hi-vis vest is
cut from each avatar's own torso faces (shoulders to just over the belt, wide armholes, V-neck), so it deforms with
the body. Avatar meshes are in cm under a 0.01-scale armature, so mesh-space sizes below are in cm.
"""

import math
import random
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

RB = None  # set by add_workers()
HEADWEAR_ALLOWED = False  # review 013c (15:18, Rexton's headwear strike): NO caps or hard hats on any worker. Closed
USE_MIXAMO = False  # owner decision 2026-10-30: every worker is Rocketbox (MIT) + procedural contact (contact.py)
FACING_OFFSET = math.radians(90)  # Rocketbox avatars face -Y at rest: +90° turns them to face +X at heading 0
CLIP_FPS = 30.0  # Rocketbox clips; the scene runs at the CCTV rate (10 fps) -> strips play at fps/30 scale
VEST_COLOURS = {"orange": (0.78, 0.28, 0.05), "yellow": (0.72, 0.78, 0.06), "lime": (0.42, 0.74, 0.08)}  # a bit faded
TEAL = (0.012, 0.2, 0.19)  # CONTOH Express teal #0e7c7b in linear

# Station plan. Each worker faces their task (heading in degrees, 0 = east, 90 = north); most show back or side to
# the cameras. Walkers stay on the yellow walkways. vest=None: plain CONTOH uniform T-shirt (~30 % of the crowd,
# never at the docks or near the forklift lane). Carry / lift / push / HMI / phone / typing / break-table roles are
# Mixamo vest workers (mixamo_workers.py).
# keys: role, at (x, y) or path [(x, y), ...], face, clip, avatar, vest; optional: scanner, hat ("hard"/"cap"),
# gloves, open (vest worn open)
STATIONS = [
    # QA 2026-10-30: every Rocketbox "work" clip mimed at nothing (no surface under the hands): removed. Station work
    # (induction, docks, chutes, bag opening) is done by flow-driven IK workers instead (stations.py).
    # the cage checker: clipboard against the cage's destination card (right front post)
    # (the cage checker is now stations.Ambient: contact toolkit, true facing)
]

_templates, _clips, _clip_rest, _retargeted, _mats, _pending_props = {}, {}, {}, {}, {}, {}


def _hidden_collection(scene):
    c = bpy.data.collections.get("PeopleTemplates")
    if c is None:
        c = bpy.data.collections.new("PeopleTemplates")
        scene.collection.children.link(c)
        c.hide_render = c.hide_viewport = True
    return c


def _img(path, colour=True):
    im = bpy.data.images.load(str(path), check_existing=True)
    im.colorspace_settings.name = "sRGB" if colour else "Non-Color"
    return im


def _m(nt, op, a, b=None):
    x = nt.nodes.new("ShaderNodeMath")
    x.operation = op
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            x.inputs[i].default_value = v
        else:
            nt.links.new(v, x.inputs[i])
    return x.outputs[0]


def _skin_safe_teal(nt, tex_color, bsdf, gloves=False):
    """Re-tint the upper-body garment to brand teal; keep skin (hue/sat test) and legs (rest-pose height band).
    gloves: the hands (outermost part of the T-pose rest) become dark work gloves."""
    n = nt.nodes
    hsv = n.new("ShaderNodeSeparateColor")
    hsv.mode = "HSV"
    nt.links.new(tex_color, hsv.inputs["Color"])
    h, s, v = hsv.outputs[0], hsv.outputs[1], hsv.outputs[2]
    skin = _m(nt, "MULTIPLY", _m(nt, "MULTIPLY", _m(nt, "LESS_THAN", h, 0.11), _m(nt, "GREATER_THAN", s, 0.15)),
              _m(nt, "MULTIPLY", _m(nt, "LESS_THAN", s, 0.72), _m(nt, "GREATER_THAN", v, 0.22)))
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])  # undeformed (rest pose) 0..1 box coords
    band = _m(nt, "MULTIPLY", _m(nt, "GREATER_THAN", sep.outputs["Z"], 0.56), _m(nt, "LESS_THAN", sep.outputs["Z"], 0.84))
    arms_in = _m(nt, "LESS_THAN", _m(nt, "ABSOLUTE", _m(nt, "SUBTRACT", sep.outputs["X"], 0.5)), 0.39)  # not hands
    mask = _m(nt, "MULTIPLY", _m(nt, "MULTIPLY", band, arms_in), _m(nt, "SUBTRACT", 1.0, skin))
    teal = n.new("ShaderNodeMix")
    teal.data_type, teal.blend_type = "RGBA", "MULTIPLY"
    teal.inputs["Factor"].default_value = 1.0
    teal.inputs["A"].default_value = (*[c * 4.5 for c in TEAL], 1)  # keep the fabric's own shading (value)
    nt.links.new(v, teal.inputs["B"])
    mix = n.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(mask, mix.inputs["Factor"])
    nt.links.new(tex_color, mix.inputs["A"])
    nt.links.new(teal.outputs["Result"], mix.inputs["B"])
    out = mix.outputs["Result"]
    if gloves:
        hand = _m(nt, "GREATER_THAN", _m(nt, "ABSOLUTE", _m(nt, "SUBTRACT", sep.outputs["X"], 0.5)), 0.405)
        g = n.new("ShaderNodeMix")
        g.data_type = "RGBA"
        nt.links.new(hand, g.inputs["Factor"])
        nt.links.new(out, g.inputs["A"])
        g.inputs["B"].default_value = (0.05, 0.05, 0.045, 1)
        out = g.outputs["Result"]
    nt.links.new(out, bsdf.inputs["Base Color"])


def _build_material(mat, key, tex, gloves=False):
    nt = mat.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Roughness"].default_value = 0.65
    col = tex.get(f"{key}_color")
    if col:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = _img(col)
        if key.endswith("_body"):
            _skin_safe_teal(nt, t.outputs["Color"], bsdf, gloves)
        elif key == "f202_head":  # the tudung: white cloth in the head texture -> matte maroon fabric
            hsv = nt.nodes.new("ShaderNodeSeparateColor")
            hsv.mode = "HSV"
            nt.links.new(t.outputs["Color"], hsv.inputs["Color"])
            uv = nt.nodes.new("ShaderNodeUVMap")
            sep = nt.nodes.new("ShaderNodeSeparateXYZ")
            nt.links.new(uv.outputs["UV"], sep.inputs["Vector"])
            cloth = _m(nt, "MULTIPLY", _m(nt, "LESS_THAN", hsv.outputs[1], 0.2), _m(nt, "GREATER_THAN", hsv.outputs[2], 0.42))
            eyes = _m(nt, "MULTIPLY", _m(nt, "LESS_THAN", sep.outputs["X"], 0.56), _m(nt, "LESS_THAN", sep.outputs["Y"], 0.28))
            mask = _m(nt, "MULTIPLY", cloth, _m(nt, "SUBTRACT", 1.0, eyes))
            tint = nt.nodes.new("ShaderNodeMix")
            tint.data_type, tint.blend_type = "RGBA", "MULTIPLY"
            tint.inputs["Factor"].default_value = 1.0
            tint.inputs["A"].default_value = (0.2, 0.028, 0.045, 1)  # maroon, keeps the fabric's own shading
            nt.links.new(_m(nt, "MULTIPLY", hsv.outputs[2], 1.25), tint.inputs["B"])
            mix = nt.nodes.new("ShaderNodeMix")
            mix.data_type = "RGBA"
            nt.links.new(mask, mix.inputs["Factor"])
            nt.links.new(t.outputs["Color"], mix.inputs["A"])
            nt.links.new(tint.outputs["Result"], mix.inputs["B"])
            nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
            nt.links.new(_m(nt, "ADD", _m(nt, "MULTIPLY", mask, 0.2), 0.65), bsdf.inputs["Roughness"])  # cloth 0.85
            bsdf.inputs["Metallic"].default_value = 0.0
        else:
            nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
        if key.endswith("_opacity"):  # hair / lashes: cut-out alpha
            nt.links.new(t.outputs["Alpha"], bsdf.inputs["Alpha"])
            if hasattr(mat, "surface_render_method"):
                mat.surface_render_method = "DITHERED"
    nrm = tex.get(f"{key}_normal")
    if nrm:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = _img(nrm, colour=False)
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = 0.7
        nt.links.new(t.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])


def _fix_materials(obj, folder):
    """Relink textures by file name to the 1K PNGs and rebuild simple PBR materials (+ a gloved body variant)."""
    tex = {p.stem: p for p in (folder / "Textures").glob("*.png")}
    gloved = None
    for slot in obj.material_slots:
        mat = slot.material
        if mat is None:
            continue
        key = mat.name.split(".")[0]  # m009_body / m009_head / m009_opacity
        _build_material(mat, key, tex)
        if key.endswith("_body"):
            gloved = mat.copy()
            gloved.name = f"{key}_gloves"
            _build_material(gloved, key, tex, gloves=True)
    return gloved


# ------------------------------------------------------------------------------------------------ hi-vis vest
def _cat(bone):
    if any(k in bone for k in ("UpperArm", "Forearm", "Hand", "Finger")):
        return "arm"
    if any(k in bone for k in ("Thigh", "Calf", "Foot", "Toe")):
        return "leg"
    if bone in ("Bip01 Pelvis", "Bip01 Spine", "Bip01 Spine1", "Bip01 Spine2", "Bip01 L Clavicle", "Bip01 R Clavicle"):
        return "torso"
    return "head"


def _vest(body, arm, open_front=False):
    """A real vest from the avatar's own torso: shoulders down to just over the belt, sleeveless with wide armholes,
    V-neck, front opening; pushed 1.9 cm off the shirt and a little looser (with folds) at the waist."""
    me = body.data
    cat = {g.index: _cat(g.name) for g in body.vertex_groups}
    eyes = {g.index for g in body.vertex_groups if g.name in ("Bip01 REye", "Bip01 LEye")}
    zs = [v.co.z for v in me.vertices]
    zmin, zmax = min(zs), max(zs)
    H = zmax - zmin
    w = {}
    eye_pts, head_pts, torso_pts = [], [], []
    for v in me.vertices:
        acc = {"arm": 0.0, "leg": 0.0, "torso": 0.0, "head": 0.0}
        tot = sum(g.weight for g in v.groups) or 1.0
        for g in v.groups:
            acc[cat.get(g.group, "head")] += g.weight / tot
        w[v.index] = acc
        if any(g.group in eyes and g.weight > 0.5 for g in v.groups):
            eye_pts.append(v.co.copy())
        if acc["head"] > 0.8:
            head_pts.append(v.co.copy())
        if acc["torso"] > 0.8:
            torso_pts.append(v.co.copy())
    fwd = Vector((0, -1, 0))
    if eye_pts and head_pts:
        f = sum(eye_pts, Vector()) / len(eye_pts) - sum(head_pts, Vector()) / len(head_pts)
        f.z = 0
        if f.length > 1e-6:
            fwd = f.normalized()
    up = Vector((0, 0, 1))
    side = up.cross(fwd).normalized()
    c = sum(torso_pts, Vector()) / max(len(torso_pts), 1)
    z_lo, z_hi, z_v = zmin + 0.525 * H, zmin + 0.865 * H, zmin + 0.80 * H
    keep = set()
    for v in me.vertices:
        a = w[v.index]
        if not (z_lo <= v.co.z <= z_hi) or a["arm"] > 0.03 or a["head"] > 0.3 or a["leg"] > 0.3:
            continue
        lat = abs((v.co - c).dot(side))
        front = (v.co - c).dot(fwd) > 0
        if front and v.co.z > z_v and lat < 0.012 * H + (v.co.z - z_v) * 0.9:
            continue  # V-neck
        if open_front and front and lat < 0.03 * H:
            continue  # worn open: a gap down the front
        keep.add(v.index)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if not all(v.index in keep for v in f.verts)], context="FACES")
    bm.normal_update()
    waist = zmin + 0.62 * H
    for v in bm.verts:
        loose = max(0.0, min(1.0, (waist - v.co.z) / (0.08 * H)))
        lat = (v.co - c).dot(side)
        fold = 0.6 * math.sin(lat / 4.0 + v.co.z / 9.0) * loose
        v.co += v.normal * (1.9 + 1.5 * loose + fold)
    vme = bpy.data.meshes.new(f"{body.data.name}_vest{'_open' if open_front else ''}")
    bm.to_mesh(vme)
    bm.free()
    vme.materials.clear()
    vme.materials.append(None)  # one slot; each worker links its own vest colour on the object
    vest = bpy.data.objects.new(f"{body.name}_vest{'_open' if open_front else ''}", vme)
    for g in body.vertex_groups:
        vest.vertex_groups.new(name=g.name)
    vest.modifiers.new("cloth", "SOLIDIFY").thickness = 0.5
    vest.modifiers.new("arm", "ARMATURE").object = arm
    vest.parent = arm
    vest.matrix_parent_inverse = body.matrix_parent_inverse.copy()
    vest.matrix_basis = body.matrix_basis.copy()
    vest["front_is_low_y"] = fwd.y < 0
    return vest


def _vest_material(name, rgb, open_front, front_low_y=True):
    """Matte hi-vis fabric (not emissive): 2 silver bands round the torso, 2 over the shoulders front and back,
    a dark front-opening line (closed vests), grime on the lower hem, slight fading."""
    key = f"hivis_{name}{'_open' if open_front else ''}"
    if key in _mats:
        return _mats[key]
    m = bpy.data.materials.new(key)
    if hasattr(m, "use_nodes"):
        m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    b.inputs["Roughness"].default_value = 0.7
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
    gx, gy, gz = sep.outputs["X"], sep.outputs["Y"], sep.outputs["Z"]

    def between(x, lo, hi):
        return _m(nt, "MULTIPLY", _m(nt, "GREATER_THAN", x, lo), _m(nt, "LESS_THAN", x, hi))
    horiz = _m(nt, "MAXIMUM", between(gz, 0.16, 0.25), between(gz, 0.50, 0.585))
    off = _m(nt, "ABSOLUTE", _m(nt, "SUBTRACT", gx, 0.5))
    vert = _m(nt, "MULTIPLY", between(off, 0.12, 0.185), _m(nt, "GREATER_THAN", gz, 0.585))
    band = _m(nt, "MAXIMUM", horiz, vert)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 6.0
    nt.links.new(tc.outputs["Generated"], noise.inputs["Vector"])
    fade = nt.nodes.new("ShaderNodeMix")  # slight fading / wash wear
    fade.data_type = "RGBA"
    fade.inputs["A"].default_value = (*rgb, 1)
    fade.inputs["B"].default_value = (rgb[0] * 0.8 + 0.06, rgb[1] * 0.8 + 0.06, rgb[2] * 0.8 + 0.06, 1)
    nt.links.new(noise.outputs["Fac"], fade.inputs["Factor"])
    col = fade.outputs["Result"]
    hem = _m(nt, "MULTIPLY", _m(nt, "LESS_THAN", gz, 0.13), noise.outputs["Fac"])  # grime on the lower hem
    dirty = nt.nodes.new("ShaderNodeMix")
    dirty.data_type, dirty.blend_type = "RGBA", "MULTIPLY"
    nt.links.new(hem, dirty.inputs["Factor"])
    nt.links.new(col, dirty.inputs["A"])
    dirty.inputs["B"].default_value = (0.45, 0.42, 0.38, 1)
    col = dirty.outputs["Result"]
    silver = nt.nodes.new("ShaderNodeMix")
    silver.data_type = "RGBA"
    nt.links.new(band, silver.inputs["Factor"])
    nt.links.new(col, silver.inputs["A"])
    silver.inputs["B"].default_value = (0.62, 0.63, 0.64, 1)
    col = silver.outputs["Result"]
    if not open_front:  # front opening line (zip / velcro seam) down the centre front
        front = _m(nt, "LESS_THAN", gy, 0.5) if front_low_y else _m(nt, "GREATER_THAN", gy, 0.5)
        seam = _m(nt, "MULTIPLY", front, _m(nt, "LESS_THAN", off, 0.007))
        sm = nt.nodes.new("ShaderNodeMix")
        sm.data_type = "RGBA"
        nt.links.new(seam, sm.inputs["Factor"])
        nt.links.new(col, sm.inputs["A"])
        sm.inputs["B"].default_value = (0.08, 0.08, 0.08, 1)
        col = sm.outputs["Result"]
    nt.links.new(col, b.inputs["Base Color"])
    nt.links.new(_m(nt, "ADD", _m(nt, "MULTIPLY", band, -0.35), 0.7), b.inputs["Roughness"])  # bands a bit shinier
    _mats[key] = m
    return m


# ------------------------------------------------------------------------------------------------ props (cm, bone space)
def _mat(name, rgb, rough=0.5, metal=0.0, emit=0.0):
    if name in _mats:
        return _mats[name]
    m = bpy.data.materials.new(name)
    m.use_backface_culling = False
    if hasattr(m, "surface_render_method"):
        m.surface_render_method = "DITHERED"  # opaque (BLENDED is the transparent mode)
    if hasattr(m, "use_nodes"):
        m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*rgb, 1)
        b.inputs["Emission Strength"].default_value = emit
    _mats[name] = m
    return m


def _cube(bm, x0, y0, z0, x1, y1, z1, mi):
    r = bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
                              @ Matrix.Diagonal((x1 - x0, y1 - y0, z1 - z0, 1)))
    for f in {f for v in r["verts"] for f in v.link_faces}:
        f.material_index = mi


def _prop_mesh(key, build, mats):
    if key in _mats:
        return _mats[key]
    me = bpy.data.meshes.new(key)
    bm = bmesh.new()
    build(bm)
    bm.to_mesh(me)
    bm.free()
    for mt in mats:
        me.materials.append(mt)
    _mats[key] = me
    return me


def _scanner(bm):  # handheld scanner, ~17 cm long, grip down
    _cube(bm, -2.2, -2.5, -1.8, 2.2, 14.0, 2.4, 0)  # body
    _cube(bm, -1.6, -1.0, -11.0, 1.6, 3.5, -1.8, 0)  # grip
    _cube(bm, -1.0, 3.5, -5.0, 1.0, 4.8, -2.5, 1)  # trigger
    _cube(bm, -1.8, 14.0, -1.4, 1.8, 14.3, 2.0, 2)  # scan window


def _hard_hat(bm):  # dome + brim, about 27 x 23 cm (24 x 14 segments, shaded smooth: facets showed at follow-cam range)
    r = bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=14, radius=1.0)
    for v in r["verts"]:
        v.co.x, v.co.y, v.co.z = v.co.x * 13.0, v.co.y * 15.0, max(v.co.z, -0.05) * 11.0
    bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=15.5, radius2=15.5, depth=0.8,
                          matrix=Matrix.Translation((0, 1.5, 0.0)) @ Matrix.Diagonal((1.0, 1.15, 1.0, 1.0)))


CAP_RX, CAP_RY, CAP_H = 10.0, 11.0, 10.0  # crown radii at the band and height (cm); +Y = the front


def _cap(bm):
    """Baseball-type work cap (cm, origin = centre of the band, +Y front): an OPEN crown (upper half of an ellipsoid,
    no hidden bottom disc), 10 cm tall, and a curved brim ~7 cm long round the front 140 deg of the band, its sides
    curving down (review 013: the old squashed sphere read as a mushroom with a flat duckbill)."""
    r = bmesh.ops.create_uvsphere(bm, u_segments=28, v_segments=14, radius=1.0)
    bmesh.ops.delete(bm, geom=[v for v in r["verts"] if v.co.z < -1e-4], context="VERTS")
    for v in bm.verts:
        v.co.x, v.co.y, v.co.z = v.co.x * CAP_RX, v.co.y * CAP_RY, max(v.co.z, 0.0) * CAP_H
    nu, nv, L = 15, 5, 7.0
    rows = []
    for j in range(nv + 1):
        vv = j / nv
        row = []
        for i in range(nu + 1):
            th = math.radians(-70 + 140 * i / nu)
            x0, y0 = 0.985 * CAP_RX * math.sin(th), 0.985 * CAP_RY * math.cos(th)  # joined just inside the crown
            reach = L * (0.55 + 0.45 * math.cos(th)) * vv  # longest at the middle
            nx, ny = math.sin(th) * 0.35, 1.0
            ln = math.hypot(nx, ny)
            z = -0.15 * reach - 1.4 * (math.sin(th) ** 2) * vv  # a little down, sides curved down
            row.append(bm.verts.new((x0 + nx / ln * reach, y0 + ny / ln * reach, z)))  # (2 mm below the band
            # it left a dark slit between crown and brim)
        rows.append(row)
    for j in range(nv):
        for i in range(nu):
            f = bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
            f.material_index = 0
    for f in bm.faces:
        f.smooth = True


def _phone(bm):  # smartphone 7.2 x 15 x 0.8 cm: body (0), screen on +Z (1); long axis Y
    _cube(bm, -3.6, -7.5, -0.4, 3.6, 7.5, 0.4, 0)
    _cube(bm, -3.3, -6.9, 0.4, 3.3, 7.0, 0.43, 1)


def _terminal(bm):  # rugged handheld mobile computer (cage-load / bag scans) 8 x 16.5 x 2.2 cm, yellow bumpers
    _cube(bm, -4.0, -8.25, -1.1, 4.0, 8.25, 1.1, 0)
    _cube(bm, -3.3, -5.0, 1.1, 3.3, 5.6, 1.14, 1)  # screen
    _cube(bm, -3.0, -7.6, 1.1, 3.0, -5.6, 1.16, 0)  # keypad area
    for sx in (-1, 1):
        for sy in (-1, 1):
            _cube(bm, sx * 4.0 - 0.9 * (sx > 0) - 0.15 * (sx < 0), sy * 8.25 - 1.6 * (sy > 0) - 0.2 * (sy < 0), -1.25,
                  sx * 4.0 + 0.15 * (sx > 0) + 0.9 * (sx < 0), sy * 8.25 + 0.2 * (sy > 0) + 1.6 * (sy < 0), 1.25, 2)
    _cube(bm, -1.6, 8.25, -0.6, 1.6, 8.7, 0.6, 3)  # scan window at the top end


def _clipboard(bm):  # A4 clipboard 23 x 32 cm: hardboard (0), manifest sheets (1), steel clip (2)
    _cube(bm, -11.5, -16.0, -0.25, 11.5, 16.0, 0.25, 0)
    _cube(bm, -10.5, -14.8, 0.25, 10.5, 14.0, 0.32, 1)
    _cube(bm, -4.0, 13.2, 0.25, 4.0, 15.6, 1.0, 2)


def device_mesh(kind):
    if kind == "clipboard":
        return _prop_mesh("clipboard", _clipboard, [_mat("hardboard", (0.32, 0.2, 0.1), 0.6),
                                                    _mat("manifest_paper", (0.8, 0.8, 0.78), 0.8),
                                                    _mat("clip_steel", (0.55, 0.56, 0.58), 0.3, metal=0.9)])
    if kind == "phone":
        return _prop_mesh("phone_in_hand", _phone, [_mat("phone_body", (0.02, 0.02, 0.025), 0.35),
                                                    _mat("phone_screen", (0.25, 0.35, 0.45), 0.15, emit=0.6)])
    return _prop_mesh("handheld_terminal", _terminal, [_mat("terminal_grey", (0.12, 0.12, 0.13), 0.5),
                                                       _mat("terminal_screen", (0.3, 0.42, 0.5), 0.15, emit=0.8),
                                                       _mat("terminal_bumper", (0.85, 0.62, 0.04), 0.55),
                                                       _mat("scanner_window", (0.9, 0.05, 0.03), 0.2, emit=1.5)])


HAND_BONES = {  # hand, index knuckle, middle knuckle, pinky knuckle, middle fingertip, thumb tip
    "rocketbox": lambda sd: tuple(f"Bip01 {sd} {n}" for n in ("Hand", "Finger1", "Finger2", "Finger4", "Finger22",
                                                               "Finger02")),
    "mixamo": lambda sd: tuple(f"mixamorig:{'Right' if sd == 'R' else 'Left'}{n}"
                               for n in ("Hand", "HandIndex1", "HandMiddle1", "HandPinky1", "HandMiddle3", "HandThumb3")),
}


def _palm(arm, rig_kind, sd):
    """Palm centre, along-hand axis and palm-face normal of one posed hand (world), from its knuckles."""
    mw = arm.matrix_world
    names = HAND_BONES[rig_kind](sd)
    pbs = [arm.pose.bones[n] for n in names]
    h, i1, m1, p1 = (mw @ pb.head for pb in pbs[:4])
    tip, thumb = mw @ pbs[4].tail, mw @ pbs[5].tail
    along = (m1 - h).normalized()
    across = (p1 - i1)
    across = (across - along * across.dot(along)).normalized()
    n = across.cross(along).normalized()
    if n.dot(tip - m1) + n.dot(thumb - h) < 0:  # palm side = where the fingers and thumb curl to
        n = -n
    return names[0], h + (m1 - h) * 0.6 + n * 0.018, along, n


def hold_device(ob, arm, body, rig_kind, head_bone, half_thick, half_xy, frames=range(1, 301, 12)):
    """Hold a phone / terminal the way the clip's hands actually hold it, without a finger ever passing through it.
    Start: on the palm of the hand nearest the face (screen out of the palm), or BETWEEN both palms when the clip
    holds it two-handed (texting: phone across both hands, screen to the eyes). Then search ~1000 nearby positions /
    angles and score each over the whole clip (25 sampled frames, every hand and finger vertex of both hands; thumbs
    free to lie on the screen; the face must stay out too): no vertex inside the device first, then the smallest
    gap to the fingers behind it, so it is gripped, not hovering. Bound to the holding hand's bone."""
    import numpy as np
    scene = bpy.context.scene
    f0 = scene.frame_current
    bpy.context.view_layer.update()
    mw = arm.matrix_world
    head = mw @ arm.pose.bones[head_bone].head + Vector((0, 0, 0.08))
    palms = {sd: _palm(arm, rig_kind, sd) for sd in ("R", "L")}
    sd = min(palms, key=lambda k: (palms[k][1] - head).length)
    hb, pc, along, n = palms[sd]
    other = palms["L" if sd == "R" else "R"]
    two_hand = (other[1] - pc).length < 0.2
    if two_hand:  # phone across both hands, screen to the eyes
        centre = (pc + other[1]) / 2
        n = (head - centre).normalized()
        x = other[1] - pc
        x = (x - n * x.dot(n)).normalized()
        along = n.cross(x).normalized()
    else:
        centre = pc + n * (half_thick + 0.002) + along * 0.02
        x = along.cross(n).normalized()
    pb = arm.pose.bones[hb]
    dev0 = Matrix.Translation(centre) @ Matrix((x, along, n)).transposed().to_4x4()
    rel0 = (mw @ pb.matrix).inverted() @ dev0  # device in the holding hand bone's space
    keys = ("Hand", "Finger", "Index", "Middle", "Ring", "Pinky")
    hand_g = {g.index for g in body.vertex_groups if any(k in g.name for k in keys)
              and not any(k in g.name for k in ("Thumb", "Finger0"))}
    head_g = {g.index for g in body.vertex_groups if g.name == head_bone}
    sel = [v.index for v in body.data.vertices if any((g.group in hand_g and g.weight > 0.3) or
                                                      (g.group in head_g and g.weight > 0.5) for g in v.groups)]
    fingers = len(sel)
    thumb_g = {g.index for g in body.vertex_groups if any(k in g.name for k in ("Thumb", "Finger0"))}
    selset = set(sel)
    sel += [v.index for v in list(body.data.vertices)[::3] if v.index not in selset  # the rest of the body (clothes,
            and not any(g.group in thumb_g and g.weight > 0.3 for g in v.groups)]  # thigh, chest) stays out too
    pts, kinds, fidx, bvhs = [], [], [], []  # vertices in the holding bone's space per frame; 1 = hand / face
    from mathutils.bvhtree import BVHTree
    for k, f in enumerate(frames):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        binv = (arm.matrix_world @ pb.matrix).inverted()
        ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = ev.to_mesh()
        m = binv @ ev.matrix_world
        pts += [(m @ me.vertices[i].co)[:] for i in sel]
        kinds += [1] * fingers + [0] * (len(sel) - fingers)
        fidx += [k] * len(sel)
        # the whole body surface (bone space) for the "device buried in the body" test
        bvhs.append(BVHTree.FromPolygons([m @ v.co for v in me.vertices], [p.vertices[:] for p in me.polygons]))
        ev.to_mesh_clear()
    scene.frame_set(f0)
    bpy.context.view_layer.update()
    V = np.c_[np.array(pts), np.ones(len(pts))]
    K = np.array(kinds, dtype=bool)
    F = np.array(fidx)
    nF = len(bvhs)
    hx, hy, ht = half_xy[0], half_xy[1], half_thick
    probe = [Vector((sx * hx * 0.8, sy * hy * 0.8, sz * ht)) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    probe.append(Vector((0, 0, 0)))

    def buried(cand):  # device points inside the body surface, all frames (the hand gripping it excepted: edges)
        n_in = 0
        for bvh in bvhs:
            for q in probe:
                w = cand @ q
                hit = bvh.find_nearest(w)
                if hit[0] is not None and (w - hit[0]).dot(hit[1]) < -0.004:
                    n_in += 1
        return n_in

    scored = []
    for dz in np.arange(-0.02, 0.055, 0.005):
        for dy in np.arange(-0.03, 0.031, 0.015):
            for dx in (np.arange(-0.02, 0.021, 0.01) if two_hand else (0.0,)):
                for ang in (0.0, -0.26, 0.26):
                    cand = rel0 @ Matrix.Translation((dx, dy, dz)) @ Matrix.Rotation(ang, 4, "Z")
                    L = V @ np.array(cand.inverted()).T
                    foot = (np.abs(L[:, 0]) < hx) & (np.abs(L[:, 1]) < hy)
                    inside = int(np.count_nonzero(foot & (np.abs(L[:, 2]) < ht - 0.0005)))
                    # gripped at EVERY moment: per frame, the nearest finger behind the back; averaged
                    mask = foot & K & (L[:, 2] <= -ht + 0.0005)
                    near = np.full(nF, -1.0)
                    np.maximum.at(near, F[mask], L[mask, 2])
                    gaps = np.where(near > -0.5, -ht - near, 0.05)
                    gap = float(np.clip(gaps, 0, None).mean())
                    scored.append((inside * 1.0 + gap * 100.0, cand, inside, gap))
    scored.sort(key=lambda t: t[0])
    best = None
    for sc_, cand, inside, gap in scored[:40]:  # the body test is slower: only on the 40 best candidates
        b_in = buried(cand)
        tot = sc_ + b_in * 5.0
        if best is None or tot < best[0]:
            best = (tot, cand, inside, gap, b_in)
    best, b_in = best[:4], best[4]
    _, rel, inside, gap = best
    _bind_world(ob, arm, hb, (mw @ pb.matrix) @ rel @ Matrix.Diagonal((0.01, 0.01, 0.01, 1.0)))
    ob["grip"] = (f"{'two-hand' if two_hand else 'one-hand'}; verts inside {inside}; mean gap {gap * 100:.1f} cm; "
                  f"points buried in body {b_in}")
    return hb


FINGER_CHAINS = {  # thumb first; each chain proximal -> distal
    "rocketbox": lambda sd: [[f"Bip01 {sd} Finger{k}{j}" for j in ("", "1", "2")] for k in range(5)],
    "mixamo": lambda sd: [[f"mixamorig:{'Right' if sd == 'R' else 'Left'}Hand{n}{j}" for j in (1, 2, 3)]
                          for n in ("Thumb", "Index", "Middle", "Ring", "Pinky")],
}


def grip_device(ob, arm, rig_kind, head_bone, half_thick, half_xy, side=None):
    """A real one-hand grip, the way animation rigs do it: the fingers are posed FOR the device instead of the
    device chasing the clip's fingers. With the animation muted (rest pose), the holding hand's fingers are
    straightened and the device laid across the palm like a phone in a real one-hand hold (long side angled ~50 deg
    towards the thumb, far long edge at the middle finger joints, screen out of the palm). Each finger then curls
    joint by joint until it touches the device (back and far edge) and the thumb comes down until it rests on the
    screen. That hand pose is locked as a top animation layer for the whole clip (finger bones only): the wrist, arm
    and body keep the clip's motion and the device, bound to the hand, can never drift through a finger."""
    import math as _m
    scene = bpy.context.scene
    if side is None:
        side = "R"
    # which side is the palm: read it from the CLIP's pose (fingers naturally curled there), in the hand's own space;
    # in the rest pose the fingers are straight and the curl test can guess the wrong side
    bpy.context.view_layer.update()
    hb_a = HAND_BONES[rig_kind](side)[0]
    tips = [ch[-1] for ch in FINGER_CHAINS[rig_kind](side)[1:]]

    def tips_local():
        binv = (arm.matrix_world @ arm.pose.bones[hb_a].matrix).inverted()
        return [binv @ (arm.matrix_world @ arm.pose.bones[t].tail) for t in tips if t in arm.pose.bones]
    tips_clip = tips_local()
    ad = arm.animation_data
    saved = (ad.action, ad.use_nla) if ad else (None, True)
    if ad:
        ad.use_nla = False
        ad.action = None
    for pb in arm.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    bpy.context.view_layer.update()
    mw = arm.matrix_world
    hb, pc, along, n = _palm(arm, rig_kind, side)
    names = HAND_BONES[rig_kind](side)
    # fingers only ever bend TOWARDS the palm: the palm side is where the clip's (curled) fingertips moved to from
    # the straight rest pose, in the hand's own space (the thumb or bone layout can mislead any other test)
    delta = sum((c - r for c, r in zip(tips_clip, tips_local())), Vector())
    n_rest = (mw @ arm.pose.bones[hb].matrix).to_3x3() @ delta
    n_rest = n_rest - along * n_rest.dot(along)
    n_rest = n_rest.normalized() if n_rest.length > 1e-4 else n
    if n_rest.dot(n) < 0:  # the rest-pose guess was the back of the hand: move the palm centre to the real palm
        hh = mw @ arm.pose.bones[names[0]].head
        mm = mw @ arm.pose.bones[names[2]].head
        pc = hh + (mm - hh) * 0.6 + n_rest * 0.018
    n = n_rest
    i1, p1 = mw @ arm.pose.bones[names[1]].head, mw @ arm.pose.bones[names[3]].head
    across = (p1 - i1)
    across = (across - n * across.dot(n)).normalized()  # index -> pinky
    long_ax = (along * _m.cos(_m.radians(50)) - across * _m.sin(_m.radians(50))).normalized()  # towards the thumb
    long_ax = (long_ax - n * long_ax.dot(n)).normalized()
    wide = long_ax.cross(n).normalized()
    if wide.dot(along) < 0:  # turn 180 deg about the screen normal (both axes): never a mirror
        wide, long_ax = -wide, -long_ax
    hx, hy, ht = half_xy[0], half_xy[1], half_thick
    centre = pc + n * (0.0025 + ht) + along * 0.012 - across * 0.008
    rot = Matrix((wide, long_ax, n)).transposed().to_4x4()  # device x across (to fingertips), y long, z screen
    D = Matrix.Translation(centre) @ rot
    Dinv = D.inverted()

    def box_dist(p):
        q = Dinv @ p
        d = Vector((max(abs(q.x) - hx, 0), max(abs(q.y) - hy, 0), max(abs(q.z) - ht, 0)))
        if d.length == 0:  # inside: negative depth
            return -min(hx - abs(q.x), hy - abs(q.y), ht - abs(q.z))
        return d.length

    def chain_pts(chain):
        out = []
        for bn in chain:
            pb = arm.pose.bones[bn]
            a_, b_ = mw @ pb.head, mw @ pb.tail
            out += [a_ + (b_ - a_) * t for t in (0.25, 0.5, 0.75, 1.0)]
        return out

    def flex_axis(bn, target):
        """The local axis + sign that curls this joint towards the device side (n)."""
        pb = arm.pose.bones[bn]
        bpy.context.view_layer.update()
        t0 = mw @ pb.tail
        best = None
        for ax in ("X", "Z"):
            for sg in (1, -1):
                pb.rotation_quaternion = Quaternion(Vector((1 if ax == "X" else 0, 0, 1 if ax == "Z" else 0)), sg * 0.3)
                bpy.context.view_layer.update()
                gain = ((mw @ pb.tail) - t0).dot(target)
                if best is None or gain > best[0]:
                    best = (gain, ax, sg)
                pb.rotation_quaternion = (1, 0, 0, 0)
        bpy.context.view_layer.update()
        return Vector((1 if best[1] == "X" else 0, 0, 1 if best[1] == "Z" else 0)), best[2]

    chains = FINGER_CHAINS[rig_kind](side)
    # straight fingers must start clear of the device (a thicker hand mesh would otherwise "touch" at 0 deg)
    for _ in range(12):
        bpy.context.view_layer.update()
        dmin = min(box_dist(p_) for ch in chains[1:] for p_ in chain_pts([b for b in ch if b in arm.pose.bones]))
        if dmin >= 0.009:
            break
        centre = centre + n * (0.009 - dmin + 0.001)
        D = Matrix.Translation(centre) @ rot
        Dinv = D.inverted()
    pose = {}
    report = []
    for ci, chain in enumerate(chains):
        chain = [bn for bn in chain if bn in arm.pose.bones]
        thumb = ci == 0
        axes = [flex_axis(bn, n) for bn in chain]
        weights = (0.7, 1.0, 0.8) if not thumb else (0.6, 0.8, 0.7)
        radius = 0.007 if not thumb else 0.008
        ang = 0.0
        touched = False
        while ang < _m.radians(95):
            for (axv, sg), bn, w in zip(axes, chain, weights):
                arm.pose.bones[bn].rotation_quaternion = Quaternion(axv, sg * ang * w)
            bpy.context.view_layer.update()
            dmin = min(box_dist(p_) for p_ in chain_pts(chain))
            if dmin < radius:
                touched = True
                ang = max(0.0, ang - _m.radians(2))  # back off to just touching
                for (axv, sg), bn, w in zip(axes, chain, weights):
                    arm.pose.bones[bn].rotation_quaternion = Quaternion(axv, sg * ang * w)
                break
            ang += _m.radians(2)
        bpy.context.view_layer.update()
        for bn in chain:
            pose[bn] = arm.pose.bones[bn].rotation_quaternion.copy()
        report.append((chain[0].split(":")[-1] if ":" in chain[0] else chain[0], round(_m.degrees(ang)), touched))
    pb = arm.pose.bones[hb]
    rel = (mw @ pb.matrix).inverted() @ D  # device in the hand bone's space (rest == any frame: fingers locked)
    # restore the animation and lock the grip on top of it
    if ad:
        ad.action, ad.use_nla = saved
    grip = bpy.data.actions.new(f"grip_{arm.name}")
    keep = ad.action if ad else None
    ad = arm.animation_data_create()
    ad.action = grip
    for bn, q in pose.items():
        arm.pose.bones[bn].rotation_quaternion = q
        arm.pose.bones[bn].keyframe_insert("rotation_quaternion", frame=1)
    ad.action = keep
    tr = ad.nla_tracks.new()
    tr.name = "grip"
    st = tr.strips.new(grip.name, -200, grip)
    if hasattr(st, "action_slot") and getattr(grip, "slots", None):
        st.action_slot = grip.slots[0]
    st.extrapolation, st.blend_type = "HOLD", "REPLACE"
    st.frame_end = 600
    scene.frame_set(scene.frame_current)
    bpy.context.view_layer.update()
    _bind_world(ob, arm, hb, (arm.matrix_world @ arm.pose.bones[hb].matrix) @ rel
                @ Matrix.Diagonal((0.01, 0.01, 0.01, 1.0)))
    ob["grip"] = "; ".join(f"{c} {d} deg{' touch' if t else ' (free)'}" for c, d, t in report)
    return hb


HAT_COLOURS = [(0.85, 0.75, 0.05), (0.92, 0.92, 0.9), (0.85, 0.4, 0.05), (0.15, 0.35, 0.75)]


def _attach(obj, arm, bone, loc, rot=(0, 0, 0)):
    """Parent a prop to a bone (bone space, cm because the armature object is scaled 0.01)."""
    obj.parent = arm
    obj.parent_type = "BONE"
    obj.parent_bone = bone
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.location = loc
    obj.rotation_euler = [math.radians(a) for a in rot]


def bind_rest(obj, arm, bone, world_rest):
    """Parent obj to a bone given its world matrix in the armature's REST pose: the local transform is computed
    against the bone's rest matrix (bone-parented children hang from the bone's tail), so it is exact for every
    frame of every clip - a hat can never slide, drift or come off."""
    b = arm.data.bones[bone]
    tail_rest = arm.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))
    obj.parent = arm
    obj.parent_type = "BONE"
    obj.parent_bone = bone
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.matrix_basis = tail_rest.inverted() @ world_rest


def _bind_world(obj, arm, bone, world):
    """Put obj at a world matrix now, then parent it to a bone so it follows that bone from here on."""
    pb = arm.pose.bones[bone]
    parent = arm.matrix_world @ pb.matrix @ Matrix.Translation((0, pb.bone.length, 0))
    obj.parent = arm
    obj.parent_type = "BONE"
    obj.parent_bone = bone
    obj.matrix_parent_inverse = parent.inverted()
    obj.matrix_basis = world


def fit_hat(ob, arm, body, head_verts, head_bone, kind, heading):
    """Seat a cap / hard hat on THIS head. Fitted once in the REST pose (head upright, facing the worker's heading,
    so up is truly up), sized to the measured head + hair, pulled down to the forehead like a real one (cap band
    ~8.5 cm, hard-hat brim ~9.5 cm below the crown; the shell rides ~3 cm above on its harness), then bound to the
    head bone: in the clip it tilts and turns exactly with the head. Hat meshes (cm): cap dome 21 x 23 x 7.5,
    hard-hat shell 26 x 30 x 11."""
    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg)
    me = ev.to_mesh()
    pts = [ev.matrix_world @ me.vertices[i].co for i in head_verts if i < len(me.vertices)]
    ev.to_mesh_clear()
    # the head bone's own up axis (in the rest pose the Rocketbox head is pitched: a cap squared to world-up came out
    # tilted ~30 deg back once bound), forward = the worker's heading squared to it
    Mb = arm.matrix_world @ arm.data.bones[head_bone].matrix_local
    axes = [Vector(Mb.col[i][:3]).normalized() for i in range(3)]
    up = max((sg * ax for ax in axes for sg in (1, -1)), key=lambda v: v.z)
    fwd0 = Vector((math.cos(heading), math.sin(heading), 0))
    fwd = (fwd0 - up * fwd0.dot(up)).normalized()
    side = fwd.cross(up).normalized()
    top = max(p.dot(up) for p in pts)
    band = [p for p in pts if top - 0.12 < p.dot(up) < top - 0.05]
    w = (max(p.dot(side) for p in band) - min(p.dot(side) for p in band)) if band else 0.16
    d = (max(p.dot(fwd) for p in band) - min(p.dot(fwd) for p in band)) if band else 0.2
    mid = sum(band, Vector()) / len(band) if band else sum(pts, Vector()) / len(pts)
    w, d = max(w, 0.14), max(d, 0.17)
    c = mid + up * (top - mid.dot(up))
    if kind == "cap":
        # rigid (review 013: no shrinkwrap). The band sits 7.5 cm below the top of the head (~2.5 cm above the brows),
        # sized to the head's cross-section there + 6 mm; the 10 cm crown clears the skull above it
        L = top - 0.075
        sec = [p for p in pts if abs(p.dot(up) - L) < 0.012]
        if len(sec) > 8:
            xs_, ys_ = [p.dot(side) for p in sec], [p.dot(fwd) for p in sec]
            w, d = max(xs_) - min(xs_), max(ys_) - min(ys_)
            mid = side * (max(xs_) + min(xs_)) / 2 + fwd * (max(ys_) + min(ys_)) / 2 + up * L
        else:
            mid = c - up * 0.075
        rx, ry = w / 2 + 0.006, d / 2 + 0.006
        k_ = 1.0  # widen until no head point above the band pokes through the crown (ellipsoid test)
        for p in pts:
            hz = (p - mid).dot(up)
            if 0.0 < hz < CAP_H / 100:
                q = ((p - mid).dot(side) / rx) ** 2 + ((p - mid).dot(fwd) / ry) ** 2
                lim = 1.0 - (hz / (CAP_H / 100)) ** 2
                if lim > 1e-3:
                    k_ = max(k_, (q / lim) ** 0.5 / 0.97)
        rx, ry = rx * k_, ry * k_
        # the band follows THIS head's own outline (an ellipse sized to its widest points stood 1.7-2.1 cm off the
        # flatter sides: QA accessory_fit): per 10 deg, the head's radius round the band (+-1.5 cm of its height),
        # smoothed, + 6 mm; the crown's lowest 4 cm blend from that outline to the ellipse; the brim follows. A rigid
        # shape made once in the rest pose, on this worker's own copy of the mesh: nothing deforms at run time
        nb = 36
        prof = [0.0] * nb
        for p in pts:
            d_ = p - mid
            if abs(d_.dot(up)) < 0.02:
                x_, y_ = d_.dot(side), d_.dot(fwd)
                k = int(((math.atan2(y_, x_) + math.pi) / (2 * math.pi)) * nb) % nb
                prof[k] = max(prof[k], math.hypot(x_, y_))
        if sum(1 for v in prof if v > 0) > nb * 0.5:  # (a sparse head mesh left too few bins at 0.7)
            for _ in range(nb // 2):  # empty bins: from the neighbours (repeated: runs of empty bins)
                for k in range(nb):
                    if prof[k] == 0.0:
                        prof[k] = max(prof[(k - 1) % nb], prof[(k + 1) % nb])
            prof = [(prof[(k - 1) % nb] + 2 * prof[k] + prof[(k + 1) % nb]) / 4 for k in range(nb)]
            ob.data = ob.data.copy()
            sxm, sym = rx / CAP_RX, ry / CAP_RY  # m per mesh cm

            def scale_at(vx, vy):
                X, Y = vx * sxm, vy * sym
                ang = math.atan2(Y, X)
                kf = ((ang + math.pi) / (2 * math.pi)) * nb - 0.5
                k0 = int(math.floor(kf)) % nb
                t_ = kf - math.floor(kf)
                want = prof[k0] * (1 - t_) + prof[(k0 + 1) % nb] * t_ + 0.006
                ce, se = math.cos(ang), math.sin(ang)
                r_ell = 1.0 / math.sqrt((ce / rx) ** 2 + (se / ry) ** 2)  # the ellipse's radius that way
                return want / r_ell
            # ...and above the band the crown never comes within 8 mm of the head at that height (pulled in to the
            # band outline, the forehead / hair showed through the crown's front: review 014 head sheets)
            slices = []
            for z0 in (0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08):
                pr = [0.0] * nb
                for p in pts:
                    d_ = p - mid
                    if abs(d_.dot(up) - z0) < 0.006:
                        x_, y_ = d_.dot(side), d_.dot(fwd)
                        k = int(((math.atan2(y_, x_) + math.pi) / (2 * math.pi)) * nb) % nb
                        pr[k] = max(pr[k], math.hypot(x_, y_))
                slices.append((z0, [max(pr[(k - 1) % nb], pr[k], pr[(k + 1) % nb]) for k in range(nb)]))

            def head_r(ang, hz):  # the head's radius that way at height hz above the band (0 = no head there)
                if hz < 0.005:
                    return 0.0
                k = int(((ang + math.pi) / (2 * math.pi)) * nb) % nb
                lo = max((sl for sl in slices if sl[0] <= hz), key=lambda sl: sl[0], default=slices[0])
                hi = min((sl for sl in slices if sl[0] >= hz), key=lambda sl: sl[0], default=slices[-1])
                return max(lo[1][k], hi[1][k])
            ring_need, pending = {}, []
            for v in ob.data.vertices:
                rr = math.hypot(v.co.x / CAP_RX, v.co.y / CAP_RY)
                if rr < 1e-6:
                    continue
                if (v.co.x / CAP_RX) ** 2 + (v.co.y / CAP_RY) ** 2 <= 1.0001 or v.co.z > -1e-3 and rr <= 1.0001:
                    w = max(0.0, min(1.0, 1.0 - v.co.z / 4.0))  # crown: the lowest 4 cm
                else:
                    w = 1.0  # the brim: moves with the band where it joins
                f_ = 1.0 + w * (scale_at(v.co.x, v.co.y) - 1.0) if w > 0.0 else 1.0
                X, Y = v.co.x * f_ * sxm, v.co.y * f_ * sym
                need = head_r(math.atan2(Y, X), v.co.z / 100.0) + 0.008
                r_now = math.hypot(X, Y)
                ratio = need / r_now if need > 0.008 and r_now > 1e-6 else 1.0
                zk = round(v.co.z, 1)
                ring_need[zk] = max(ring_need.get(zk, 1.0), ratio)
                pending.append((v, f_, zk))
            # each height ring inflated evenly by what its tightest point needs (per point, the crown went lumpy
            # round hair spikes: review 014 sheets)
            for v, f_, zk in pending:
                f_ *= ring_need.get(zk, 1.0)
                v.co.x *= f_
                v.co.y *= f_
            ob.data.update()
        rot = Matrix((side, fwd, up)).transposed().to_4x4()
        bind_rest(ob, arm, head_bone, Matrix.Translation(mid) @ rot
                  @ Matrix.Diagonal((rx / CAP_RX, ry / CAP_RY, 0.01, 1.0)))
        arm.data.pose_position = "POSE"
        bpy.context.view_layer.update()
        return
    else:
        drop, sx, sy, sz = 0.095, (w / 2 + 0.014) / 0.13, (d / 2 + 0.017) / 0.15, 0.135 / 0.11  # shell on its
        # harness ~2 cm out (2.5 / 3 cm left its rim 3.6-4.2 cm off the skull: QA accessory_fit, max 3.5)
    rot = Matrix((side, fwd, up)).transposed().to_4x4()  # hat x -> side, +y (visor / brim) -> face, z -> up
    M = Matrix.Translation(c - up * drop) @ rot @ Matrix.Diagonal((0.01 * sx, 0.01 * sy, 0.01 * sz, 1.0))
    bind_rest(ob, arm, head_bone, M)
    if kind == "cap":  # the band hugs THIS skull (review 009d/009e: a rigid dome square to the head touched the
        _wrap_band(ob, body)  # forehead and stood 2-8 cm off elsewhere; tilted to fit, it sat 25 deg off the head)
    arm.data.pose_position = "POSE"
    bpy.context.view_layer.update()


def _wrap_band(ob, body):
    """A cap's band (the lower half of its dome) is shrinkwrapped onto the head skin, 4 mm off it, fading to the
    stiff crown; the visor / brim follows the band's front. Evaluated every frame (the body deforms with the clip)."""
    me = ob.data
    zs = [v.co.z for v in me.vertices if (v.co.x * v.co.x + v.co.y * v.co.y) ** 0.5 < 13.5]
    if not zs:
        return
    z0, z1 = min(zs), max(zs)
    vg = ob.vertex_groups.get("band") or ob.vertex_groups.new(name="band")
    for v in me.vertices:
        rn = ((v.co.x / 10.5) ** 2 + (v.co.y / 11.5) ** 2) ** 0.5
        if rn > 0.85 and (v.co.x * v.co.x + v.co.y * v.co.y) ** 0.5 < 13.5:  # the band edge and the dome's lowest
            w = max(0.0, min(1.0, 1.0 - (v.co.z - z0 - 2.5) / 1.5))  # 2.5-4 cm (never the flat disc inside the head)
        else:  # crown, the inner disc, the visor
            w = 0.0
        if w > 0.0:
            vg.add([v.index], w, "REPLACE")
    md = ob.modifiers.new("band_fit", "SHRINKWRAP")
    md.target = body
    md.wrap_method = "NEAREST_SURFACEPOINT"
    md.wrap_mode = "ON_SURFACE"
    md.offset = 0.004  # WORLD units (measured: not the hat's cm mesh units): 4 mm off the skin
    md.vertex_group = "band"
    sm = ob.modifiers.new("band_smooth", "SMOOTH")  # the wrap snapped some band points onto hair cards: a sawtooth
    sm.vertex_group, sm.factor, sm.iterations = "band", 0.7, 8  # edge (req 013 head sheets) - smoothed along it


def _fit_cap(ob, body, head_verts, c, side, fwd, up, sx, sy, sz):
    """Cap pose on the skull in the rest pose: pitch about the ear-to-ear axis, drop below the crown and size
    searched so the dome's band ring hugs the head SKIN (smallest 90th-percentile gap) with no cap vertex > 3 mm
    inside it. Returns the world matrix (None if the head mesh is missing)."""
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg)
    me = ev.to_mesh()
    hv = set(head_verts)
    vs = [ev.matrix_world @ v.co for v in me.vertices]
    polys = [tuple(pl.vertices) for pl in me.polygons if all(i in hv for i in pl.vertices)]
    ev.to_mesh_clear()
    if not polys:
        return None
    bvh = BVHTree.FromPolygons(vs, polys)
    loc_v = [v.co.copy() for v in ob.data.vertices]
    zmin = min(v.z for v in loc_v)
    ring = [v for v in loc_v if v.z < zmin + 0.6 and (v.x * v.x + v.y * v.y) ** 0.5 < 13.5][::2]
    dome = [v for v in loc_v if (v.x * v.x + v.y * v.y) ** 0.5 < 13.5][::4]

    def sd(p):
        hit = bvh.find_nearest(p)
        return None if hit[0] is None else (p - hit[0]).dot(hit[1])
    best = None
    for pitch_d in range(-30, 31, 5):
        Rp = Matrix.Rotation(math.radians(pitch_d), 3, side)
        u_, f_ = Rp @ up, Rp @ fwd
        rot = Matrix((side, f_, u_)).transposed().to_4x4()
        for drop in (0.07, 0.08, 0.09, 0.10, 0.11, 0.12):
            for k in (0.84, 0.88, 0.92, 0.96, 1.0, 1.04):
                M = Matrix.Translation(c - u_ * drop) @ rot @ Matrix.Diagonal((0.01 * sx * k, 0.01 * sy * k,
                                                                               0.01 * sz, 1.0))
                inside = 0.0
                for v in dome:
                    d_ = sd(M @ v)
                    if d_ is not None:
                        inside = max(inside, -d_ - 0.003)
                gaps = sorted(d_ for d_ in (sd(M @ v) for v in ring) if d_ is not None)
                if not gaps:
                    continue
                score = 100.0 * max(inside, 0.0) + gaps[int(len(gaps) * 0.9)] + 0.5 * gaps[len(gaps) // 2]
                if best is None or score < best[0]:
                    best = (score, M)
    return best[1] if best else None


def _fit_props(scene, arm, body, t, heading, props):
    """Hat on the crown (from the posed head vertices), scanner in the right hand, both facing the work."""
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg)
    me = ev.to_mesh()
    pts = [ev.matrix_world @ me.vertices[i].co for i in t["head_verts"] if i < len(me.vertices)]
    ev.to_mesh_clear()
    yaw = Matrix.Rotation(heading - math.pi / 2, 4, "Z")  # prop +Y (brim / scanner nose) -> the worker's forward
    cm = Matrix.Diagonal((0.01, 0.01, 0.01, 1.0))
    for kind, ob in props:
        if kind == "hat" and pts:
            fit_hat(ob, arm, body, t.get("head_skin", t["head_verts"]), "Bip01 Head",
                    "cap" if ob.name.endswith("_cap") else "hard", heading)
        elif kind == "device":
            dims = {"_terminal": (0.011, (0.04, 0.0825)), "_clipboard": (0.004, (0.115, 0.16)),
                    "_phone": (0.004, (0.036, 0.075))}
            ht_, hxy_ = next(v for k, v in dims.items() if ob.name.endswith(k))
            grip_device(ob, arm, "rocketbox", "Bip01 Head", ht_, hxy_, side="R")
        elif kind == "scanner":
            pb = arm.pose.bones["Bip01 R Hand"]
            head, tail = arm.matrix_world @ pb.head, arm.matrix_world @ pb.tail
            palm = head + (tail - head) * 0.6
            _bind_world(ob, arm, "Bip01 R Hand", Matrix.Translation(palm + Vector((0, 0, 0.03))) @ yaw
                        @ Matrix.Rotation(math.radians(-12), 4, "X") @ cm)


# ------------------------------------------------------------------------------------------------ avatars + clips
def _template(scene, avatar):
    if avatar in _templates:
        return _templates[avatar]
    folder = RB / avatar
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(folder / f"{avatar}.fbx"))
    new = [o for o in bpy.data.objects if o not in before]
    hide = _hidden_collection(scene)
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        hide.objects.link(o)
    arm = next(o for o in new if o.type == "ARMATURE")
    body = next(o for o in new if o.type == "MESH")
    gloved = _fix_materials(body, folder)
    head_idx = {g.index for g in body.vertex_groups if g.name == "Bip01 Head"}
    head_verts = [v.index for v in body.data.vertices if any(g.group in head_idx and g.weight > 0.8 for g in v.groups)]
    # the skull: head vertices on the skin material only (the hair cut-out cards / buns made the cap sit on the hair:
    # review 009d)
    skin = {i for pl in body.data.polygons if body.data.materials[pl.material_index]
            and body.data.materials[pl.material_index].name.endswith("_head") for i in pl.vertices}
    head_skin = [i for i in head_verts if i in skin] or head_verts
    vest, vest_open = _vest(body, arm), _vest(body, arm, open_front=True)
    hide.objects.link(vest)
    hide.objects.link(vest_open)
    _templates[avatar] = dict(arm=arm, body=body, vest=vest, vest_open=vest_open, gloved=gloved,
                              head_verts=head_verts, head_skin=head_skin)
    return _templates[avatar]


def _channelbag_fcurves(act):
    """All F-curves of an action (Blender 4.4+ layered actions, with the legacy list as fallback)."""
    out = []
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for cb in getattr(strip, "channelbags", []):
                out.append((cb, list(cb.fcurves)))
    if not out and hasattr(act, "fcurves"):
        out.append((act, list(act.fcurves)))
    return out


def _clip(scene, gender, name):
    key = f"{gender}_{name}"
    if key in _clips:
        return _clips[key]
    before_o, before_a = set(bpy.data.objects), set(bpy.data.actions)
    bpy.ops.import_scene.fbx(filepath=str(RB / "animations" / f"{key}.fbx"))
    new_o = [o for o in bpy.data.objects if o not in before_o]
    acts = [a for a in bpy.data.actions if a not in before_a and a.name.startswith("Bip01")
            and "Footsteps" not in a.name]
    clip_arm = next((o for o in new_o if o.type == "ARMATURE"), None)
    helper = next((o for o in new_o if o.name.startswith("MotionExtractionHelper")), None)
    hip_z, speed = None, None
    if clip_arm is not None:
        f0 = scene.frame_current
        fr = clip_arm.animation_data.action.frame_range if clip_arm.animation_data and clip_arm.animation_data.action \
            else (1, 1)
        scene.frame_set(int(fr[0]))
        pb = clip_arm.pose.bones.get("Bip01 Pelvis")
        hip_z = (clip_arm.matrix_world @ pb.head).z if pb else None
        if helper is not None:  # the motion the clip extracted from the root = its true walking speed (no sliding)
            p0 = helper.matrix_world.translation.copy()
            scene.frame_set(int(fr[1]))
            p1 = helper.matrix_world.translation.copy()
            dur = (fr[1] - fr[0]) / CLIP_FPS
            d = math.hypot(p1.x - p0.x, p1.y - p0.y)
            speed = d / dur if dur > 0 and d > 0.05 else None
        scene.frame_set(f0)
        _clip_rest[key] = {b.name: b.matrix.to_quaternion() for b in clip_arm.data.bones}
    for o in new_o:
        bpy.data.objects.remove(o, do_unlink=True)
    act = acts[0] if acts else None
    if act:
        act["hip_z"] = hip_z if hip_z is not None else -1.0
        act["speed"] = speed if speed else -1.0
        act.name = f"clip_{key}"
        act.use_fake_user = True
        for bag, fcs in _channelbag_fcurves(act):  # keep bone channels only: we place and turn the worker ourselves
            for fc in fcs:
                if not fc.data_path.startswith("pose.bones"):
                    bag.fcurves.remove(fc)
    _clips[key] = act
    return act


def _retarget(key, act, avatar):
    """Rocketbox clips were exported on a skeleton whose rest pose differs from the avatars' (upper arms ~35–40°
    apart), so raw keys put the arms out. Re-express every rotation key against the avatar's rest:
    q_avatar = rest_avatar⁻¹ · rest_clip · q_clip (per bone, rest relative to parent). Only the pelvis keeps its
    translation (so each avatar keeps its own proportions); scale keys are dropped. Cached per (clip, avatar)."""
    ck = (key, avatar)
    if ck in _retargeted:
        return _retargeted[ck]
    av_arm = _templates[avatar]["arm"]
    crest = _clip_rest.get(key, {})
    new = act.copy()
    new.name = f"{act.name}@{avatar}"
    new.use_fake_user = True
    for bag, fcs in _channelbag_fcurves(new):
        groups = {}
        for fc in fcs:
            if fc.data_path.startswith('pose.bones["'):
                bone = fc.data_path.split('"')[1]
                prop = fc.data_path.rsplit(".", 1)[1]
                groups.setdefault((bone, prop), {})[fc.array_index] = fc
        for (bone, prop), chans in groups.items():
            if prop == "scale" or (prop == "location" and bone != "Bip01 Pelvis"):
                for fc in chans.values():
                    bag.fcurves.remove(fc)
                continue
            if bone not in av_arm.data.bones or bone not in crest:
                continue
            n = 4 if prop == "rotation_quaternion" else 3
            if len(chans) != n:
                continue
            corr = av_arm.data.bones[bone].matrix.to_quaternion().inverted() @ crest[bone]
            frames = sorted({kp.co.x for fc in chans.values() for kp in fc.keyframe_points})
            vals, prev = [], None
            for f in frames:
                v = [chans[i].evaluate(f) for i in range(n)]
                if n == 4:
                    q = corr @ Quaternion(v)
                    if prev is not None and prev.dot(q) < 0:  # keep the quaternion path continuous
                        q.negate()
                    prev = q
                    vals.append(list(q))
                else:
                    vals.append(list(corr @ Vector(v)))
            for i in range(n):
                fc = chans[i]
                fc.keyframe_points.clear()
                fc.keyframe_points.add(len(frames))
                co = []
                for f, out in zip(frames, vals):
                    co += [f, out[i]]
                fc.keyframe_points.foreach_set("co", co)
                fc.update()
    _retargeted[ck] = new
    return new


def _instance(scene, coll, st, name, hat_colour):
    t = _template(scene, st["avatar"])
    arm = t["arm"].copy()
    arm.name = name
    arm.animation_data_clear()
    coll.objects.link(arm)
    vest_src = None if st["vest"] is None else t["vest_open"] if st.get("open") else t["vest"]
    for src in [t["body"]] + ([vest_src] if vest_src else []):
        o = src.copy()
        o.name = f"{name}_{'vest' if src is vest_src else 'body'}"
        o.parent = arm
        for md in o.modifiers:
            if md.type == "ARMATURE":
                md.object = arm
        coll.objects.link(o)
        if src is vest_src:
            o.material_slots[0].link = "OBJECT"
            o.material_slots[0].material = _vest_material(st["vest"], VEST_COLOURS[st["vest"]], bool(st.get("open")),
                                                          bool(vest_src.get("front_is_low_y", True)))
        elif st.get("gloves") and t["gloved"] is not None:
            for slot in o.material_slots:
                if slot.material and slot.material.name.split(".")[0].endswith("_body"):
                    slot.link = "OBJECT"
                    slot.material = t["gloved"]
    grey, black = _mat("scanner_grey", (0.12, 0.12, 0.13), 0.4), _mat("scanner_yellow", (0.8, 0.6, 0.05), 0.5)
    red = _mat("scanner_window", (0.9, 0.05, 0.03), 0.2, emit=1.5)
    props = []
    if st.get("scanner"):
        sc = bpy.data.objects.new(f"{name}_scanner", _prop_mesh("handheld_scanner", _scanner, [grey, black, red]))
        coll.objects.link(sc)
        props.append(("scanner", sc))
    if st.get("device"):  # phone / rugged terminal held to the face
        dv = bpy.data.objects.new(f"{name}_{st['device']}", device_mesh(st["device"]))
        coll.objects.link(dv)
        props.append(("device", dv))
    if HEADWEAR_ALLOWED and st.get("hat") and st["avatar"] != "Female_Adult_06":  # the tudung stays as it is
        mesh = _prop_mesh("hard_hat", _hard_hat, [_mat("hat_shell", (0.8, 0.8, 0.8), 0.35)]) if st["hat"] == "hard" \
            else _prop_mesh("work_cap", _cap, [_mat("cap_teal", (0.02, 0.18, 0.17), 0.85)])  # cotton: no gloss
        for poly in mesh.polygons:
            poly.use_smooth = True
        h = bpy.data.objects.new(f"{name}_{st['hat']}", mesh)
        coll.objects.link(h)
        if st["hat"] == "hard":
            h.material_slots[0].link = "OBJECT"
            h.material_slots[0].material = _mat(f"hat_{hat_colour}", HAT_COLOURS[hat_colour], 0.35)
        props.append(("hat", h))
    arm["_props"] = [ob.name for _, ob in props]
    _pending_props[arm.name] = props
    return arm


def crossfade_loop(ad, act, start, until, scale, a0, a1, name, overlap=4.0, first_extrap="HOLD"):
    """Loop act[a0:a1] from `start` to `until` as overlapping copies: lower track at full weight, upper track blending
    in / out over `overlap` frames, so every loop seam is a crossfade instead of a jump back to the first pose.
    Returns (first strip, loop length in scene frames)."""
    L = (a1 - a0) * scale
    ov = min(overlap, L / 4)
    lo, hi = ad.nla_tracks.new(), ad.nla_tracks.new()
    lo.name, hi.name = name + "_a", name + "_b"
    t, i, first, last = float(start), 0, None, None
    while t < until:
        tr = lo if i % 2 == 0 else hi
        st = tr.strips.new(f"{act.name}~{i}", int(round(t)), act)
        if hasattr(st, "action_slot") and getattr(act, "slots", None):
            st.action_slot = act.slots[0]
        st.action_frame_start, st.action_frame_end = a0, a1
        st.scale = scale
        st.extrapolation = first_extrap if i == 0 else "NOTHING"  # HOLD_FORWARD in a sequence: never backwards
        if i % 2:
            st.blend_in = st.blend_out = ov
        first = first or st
        last = st
        t += L - ov
        i += 1
    if last is not None and last is not first:
        last.extrapolation = "HOLD_FORWARD"
    return first, L


def _play(arm, action, offset_frames, fps, frames=400):
    ad = arm.animation_data_create()
    a0, a1 = action.frame_range
    crossfade_loop(ad, action, 1 - offset_frames, frames, fps / CLIP_FPS, a0, a1, "loop")  # starts mid-cycle


def _turn(arm, yaw):
    """Heading only: keep the FBX import's own axis rotation in X/Y."""
    arm.rotation_euler[2] = yaw


def _walk_path(arm, pts, speed, fps, offset_frames, frames=400):
    """Loop back and forth along a polyline at the clip's own speed; face the direction of travel."""
    seg = [(a, b, math.dist(a, b)) for a, b in zip(pts, pts[1:])]
    total = sum(s[2] for s in seg)
    route = seg + [(b, a, d) for a, b, d in reversed(seg)]
    period = 2 * total / speed * fps
    for f in range(1, frames + 1, 2):
        t = ((f + offset_frames) % period) / period * 2 * total
        for a, b, d in route:
            if t <= d:
                k = t / d if d else 0
                arm.location = (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, 0.0)
                _turn(arm, math.atan2(b[1] - a[1], b[0] - a[0]) + FACING_OFFSET)
                break
            t -= d
        arm.keyframe_insert("location", frame=f)
        arm.keyframe_insert("rotation_euler", frame=f)
    for bag, fcs in _channelbag_fcurves(arm.animation_data.action):  # constant speed between keys (no easing)
        for fc in fcs:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"


# ------------------------------------------------------------------------------------------------ checks
def _planted_foot_speed(scene, arm, fps, frames=range(1, 61)):
    """Walking speed the clip's feet imply: while a toe is planted (within 1.2 cm of its lowest point) it slides
    backward under the in-place body at exactly the speed the body must travel for it to stay still on the floor."""
    tracks = {}
    for f in frames:
        scene.frame_set(f)
        bpy.context.view_layer.update()
        for t in ("Bip01 L Toe0", "Bip01 R Toe0"):
            pb = arm.pose.bones.get(t)
            if pb:
                tracks.setdefault(t, []).append(arm.matrix_world @ pb.head)
    v = []
    for pts in tracks.values():
        zmin = min(p.z for p in pts)
        for a, b in zip(pts, pts[1:]):
            if a.z < zmin + 0.012 and b.z < zmin + 0.012:
                v.append(math.hypot(b.x - a.x, b.y - a.y) * fps)
    scene.frame_set(1)
    v.sort()
    return v[len(v) // 2] if len(v) >= 4 else None


def _on_walkways(path, spec):
    rects = [w["rect_m"] for w in spec["circulation"]["walkways"]] + [z["rect_m"] for z in
                                                                      spec["circulation"]["zebra_crossings"]]
    bad = []
    for (ax, ay), (bx, by) in zip(path, path[1:]):
        for k in range(21):
            x, y = ax + (bx - ax) * k / 20, ay + (by - ay) * k / 20
            if not any(r[0] - 0.05 <= x <= r[2] + 0.05 and r[1] - 0.05 <= y <= r[3] + 0.05 for r in rects):
                bad.append((round(x, 2), round(y, 2)))
    return bad


def facing_report(spec, placed, max_dist=15.0, cone_deg=35.0):
    """Static workers whose chest faces a nearby camera that covers them (within cone_deg of straight at it).
    Cameras > 15 m away (e.g. the loop cameras across the sorter) see a worker as a few dozen pixels: not counted."""
    out = []
    for p in placed:
        if p["role"] == "walk" or "at" not in p:
            continue
        x, y = p["at"]
        hd = math.radians(p["face"])
        fx, fy = math.cos(hd), math.sin(hd)
        for c in spec["cameras"]:
            cx, cy = c["position_m"]
            dx, dy = cx - x, cy - y
            dist = math.hypot(dx, dy)
            if dist > max_dist or dist < 0.5:
                continue
            yaw = math.radians(c["heading_deg"])  # is the worker inside the camera's horizontal view?
            ang_cam = abs((math.degrees(math.atan2(-dy, -dx) - yaw) + 180) % 360 - 180)
            if ang_cam > c["hfov_deg"] / 2:
                continue
            d = c.get("duty_area_m")
            if d and not (d["x"][0] - 3 <= x <= d["x"][1] + 3 and d["y"][0] - 3 <= y <= d["y"][1] + 3):
                continue
            ang = math.degrees(math.acos(max(-1, min(1, (fx * dx + fy * dy) / dist))))
            if ang < cone_deg:
                out.append({"worker": p["name"], "camera": c["id"], "angle_deg": round(ang)})
    return out


def _snap_to_cage(bays, side, gap=0.42):
    """Stand at a parked cage: 'back' = behind its closed back (hands on the handle rail), 'front' = at its open
    front. Cages are 0.72 x 0.80 m, front = local -Y. Returns at + face toward the cage."""
    for bay in bays:
        ob = bpy.data.objects.get(f"cage_{bay}") or bpy.data.objects.get(bay)
        if ob is None:
            continue
        r = ob.rotation_euler[2]
        if side == "tag":  # at the right front post, where the destination card hangs (build_hub: local 0.36, -0.42)
            lx, ly, tx_, ty_ = 0.62, -0.78, 0.36, -0.42
            ca, sa = math.cos(r), math.sin(r)
            x, y = ob.location.x + lx * ca - ly * sa, ob.location.y + lx * sa + ly * ca
            px, py = ob.location.x + tx_ * ca - ty_ * sa, ob.location.y + tx_ * sa + ty_ * ca
            face = math.degrees(math.atan2(py - y, px - x)) % 360
            return {"at": (round(x, 3), round(y, 3)), "face": round(face, 1), "cage_bay": bay}
        sgn = 1 if side == "back" else -1
        d = 0.4 + gap
        x, y = ob.location.x - sgn * d * math.sin(r), ob.location.y + sgn * d * math.cos(r)
        face = math.degrees(math.atan2(ob.location.y - y, ob.location.x - x)) % 360
        return {"at": (round(x, 3), round(y, 3)), "face": round(face, 1), "cage_bay": bay}
    raise RuntimeError(f"no parked cage in bays {bays}")


SEATED = {"worker_mx_12_exception", "worker_mx_13_break"}
FLOOR_EXCL = {"floor_slab", "ground", "yard_north", "yard_west", "roof", "roof_lights", "roof_services",
              "highbay_fixtures", "cctv_housings", "wall_base_grime"}


def _moves(rig):
    """True if the worker travels (location keys that change)."""
    ad = rig.animation_data
    if not ad or not ad.action:
        return False
    for bag, fcs in _channelbag_fcurves(ad.action):
        for fc in fcs:
            if fc.data_path == "location" and fc.array_index < 2:
                ys = [kp.co.y for kp in fc.keyframe_points]
                if ys and max(ys) - min(ys) > 0.05:
                    return True
    return False


def _static_triangles(scene):
    """World triangles of everything a worker must not stand inside (floors excluded; roll cages as SOLID boxes)."""
    import numpy as np
    dg = bpy.context.evaluated_depsgraph_get()
    tris, owner = [], []
    for o in scene.objects:
        if o.type != "MESH" or o.hide_render or not o.visible_get():
            continue
        nm = o.name.split(".")[0]
        if nm in FLOOR_EXCL or nm.startswith(("floor_", "yard_", "carrier_")):
            continue
        par, dyn = o.parent, False
        while par is not None:
            dyn |= par.type == "ARMATURE" and par.name.startswith("worker_")
            par = par.parent
        if dyn:
            continue
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        if len(me.loop_triangles):
            co = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get("co", co)
            M = np.array(ev.matrix_world)
            co = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
            t = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
            me.loop_triangles.foreach_get("vertices", t)
            tris.append(co[t.reshape(-1, 3)])
            owner += [o.name] * (len(t) // 3)
        ev.to_mesh_clear()
        if o.data.name.startswith("roll_cage") and not o.data.name.endswith("gate"):
            c = [o.matrix_world @ Vector((x, y, z)) for x in (-0.36, 0.36) for y in (-0.4, 0.4) for z in (0.17, 1.8)]
            q = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
            box = []
            for a, b, c_, d in q:
                box += [(c[a], c[b], c[c_]), (c[a], c[c_], c[d])]
            tris.append(np.array([[list(v) for v in t3] for t3 in box]))
            owner += [o.name + " (box)"] * len(box)
    return np.concatenate(tris), owner


def _body_points(scene, rig, frames, step, exclude_hands=True):
    import numpy as np
    body = next(c for c in rig.children if c.name.endswith("_body"))
    gname = {g.index: g.name for g in body.vertex_groups}
    keep = []
    for v in body.data.vertices:
        if exclude_hands and v.groups:
            g = max(v.groups, key=lambda g: g.weight)
            nm = gname.get(g.group, "")
            if any(k in nm for k in ("Hand", "Finger", "Forearm", "ForeArm")):
                continue
        keep.append(v.index)
    keep = np.array(keep[::step])
    out = []
    for f in frames:
        scene.frame_set(f)
        bpy.context.view_layer.update()
        ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        ev.to_mesh_clear()
        M = np.array(ev.matrix_world)
        out.append(co.reshape(-1, 3)[keep] @ M[:3, :3].T + M[:3, 3])
    scene.frame_set(1)
    return np.concatenate(out)


def settle_workers(scene, rigs, frames=range(1, 301, 10), max_r=0.6, approach=()):
    """Move each standing worker to the nearest spot (<= 60 cm) where no body part (hands excepted: they work IN
    bags and cages) is inside anything, over the whole clip. Their stool / HMI / dock box moves with them.
    Workers in `approach` then step forward (2.5 cm steps, up to 80 cm) while still clean: the torso ends at the
    belt / bench / bag edge and the hands work over it, instead of gesturing in the air a metre away."""
    import numpy as np
    from mathutils.bvhtree import BVHTree
    TRI, OWN = _static_triangles(scene)
    OWN = np.array(OWN)
    moved = {}
    for rig in rigs:
        P = _body_points(scene, rig, frames, 5)
        lo, hi = P.min(axis=0) - 0.8, P.max(axis=0) + 0.8
        sel = np.nonzero(np.all((TRI.max(axis=1) >= lo) & (TRI.min(axis=1) <= hi), axis=1)
                         & ~np.char.startswith(OWN.astype(str), rig.name + "_"))[0]
        if not len(sel):
            continue
        bvh = BVHTree.FromPolygons(TRI[sel].reshape(-1, 3).tolist(), [(3 * k, 3 * k + 1, 3 * k + 2) for k in range(len(sel))])
        near = [p for p in P.tolist() if bvh.find_nearest(p, max_r + 0.1)[0] is not None]

        def score(dx, dy):
            n = 0
            for x, y, z in near:
                h = bvh.find_nearest((x + dx, y + dy, z), 0.08)
                if h[0] is not None and ((x + dx - h[0].x) * h[1].x + (y + dy - h[0].y) * h[1].y + (z - h[0].z) * h[1].z) < -0.01:
                    n += 1
            return n
        s0 = score(0, 0)
        best = (s0, 0.0, 0.0, 0.0)
        for r in [0.05 * k for k in range(1, int(max_r / 0.05) + 1)]:
            for k in range(16):
                a = 2 * math.pi * k / 16
                sc_ = score(r * math.cos(a), r * math.sin(a))
                if sc_ < best[0]:
                    best = (sc_, r, r * math.cos(a), r * math.sin(a))
            if best[0] <= 2:
                break
            if s0 <= 2:  # already clean: no need to move away
                break
        dx, dy = best[2], best[3]
        if rig.name in approach:
            hd = rig.rotation_euler[2] - FACING_OFFSET
            fx, fy = math.cos(hd), math.sin(hd)
            limit = max(2, best[0])
            k = 0
            while k < 32 and score(dx + fx * 0.025 * (k + 1), dy + fy * 0.025 * (k + 1)) <= limit:
                k += 1
            dx, dy = dx + fx * 0.025 * k, dy + fy * 0.025 * k
        if abs(dx) + abs(dy) < 1e-6:
            continue
        movers = [rig] + [o for o in scene.objects if o.name.startswith(rig.name + "_") and o.parent is None]
        for o in movers:
            fcs = []
            if o.animation_data and o.animation_data.action:
                fcs = [fc for bag, f_ in _channelbag_fcurves(o.animation_data.action) for fc in f_
                       if fc.data_path == "location" and fc.array_index < 2]
            if fcs:
                for fc in fcs:
                    for kp in fc.keyframe_points:
                        d = dx if fc.array_index == 0 else dy
                        kp.co.y += d
                        kp.handle_left.y += d
                        kp.handle_right.y += d
            else:
                o.location.x += dx
                o.location.y += dy
        moved[rig.name] = {"moved_cm": round(math.hypot(dx, dy) * 100), "inside_before": s0, "inside_after": best[0]}
    scene.frame_set(1)
    return moved


def place_work_items(scene, rigs, coll, frames=range(1, 301, 5)):
    """A real parcel under each working worker's hands: where the hands reach lowest in their clip, cast down to
    the surface below (belt / bench / bag / parcel wall) and set a parcel there, so the hands work ON something.
    Returns per worker the surface hit (or None: no surface under the hands -> rework or remove)."""
    out = {}
    dg = bpy.context.evaluated_depsgraph_get()
    def _parcel_cm(bm):  # 30 x 22 x 14 cm carton, packing tape over the top seam
        _cube(bm, -15, -11, 0, 15, 11, 14, 0)
        _cube(bm, -15.2, -2.5, 13.9, 15.2, 2.5, 14.2, 1)
    mesh = _prop_mesh("work_parcel", _parcel_cm, [bpy.data.materials.get("cardboard") or
                                                  _mat("carton_brown", (0.36, 0.23, 0.12), 0.8),
                                                  _mat("tape_clear", (0.42, 0.33, 0.2), 0.3)])
    for rig in rigs:
        hands = []
        for f in frames:
            scene.frame_set(f)
            mw = rig.matrix_world
            for b in ("Bip01 L Hand", "Bip01 R Hand"):
                pb = rig.pose.bones.get(b)
                if pb:
                    hands.append(mw @ pb.head)
        if not hands:
            continue
        hands.sort(key=lambda v: v.z)
        low = hands[: max(4, len(hands) // 3)]
        c = sum(low, Vector()) / len(low)
        own = {rig.name} | {o.name for o in rig.children_recursive}
        hit, loc, nrm, idx, ob, _ = scene.ray_cast(dg, c + Vector((0, 0, 0.05)), Vector((0, 0, -1)), distance=0.7)
        while hit and (ob.name in own or ob.name.startswith("worker_")):
            hit, loc, nrm, idx, ob, _ = scene.ray_cast(dg, loc + Vector((0, 0, -0.01)), Vector((0, 0, -1)), distance=0.7)
        if not hit or loc.z < 0.3:
            out[rig.name] = None
            continue
        if mesh is not None:
            pr = bpy.data.objects.new(f"{rig.name}_work_parcel", mesh)
            coll.objects.link(pr)
            pr.location = (loc.x, loc.y, loc.z)
            pr.rotation_euler[2] = rig.rotation_euler[2] + 0.3
            pr.scale = (0.01, 0.01, 0.01)
        out[rig.name] = {"surface": ob.name, "z": round(loc.z, 2)}
    scene.frame_set(1)
    return out


def ground_workers(scene, rigs, frames=range(1, 301)):
    """Feet on the floor at every frame: the lowest body point is keyed to z = 0 through delta_location (added on
    top of any location animation), smoothed over 3 frames."""
    import numpy as np
    out = {}
    lows = {r.name: [] for r in rigs}
    bodies = {r.name: next(c for c in r.children if c.name.endswith("_body")) for r in rigs}
    for f in frames:
        scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        for r in rigs:
            ev = bodies[r.name].evaluated_get(dg)
            me = ev.to_mesh()
            co = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get("co", co)
            ev.to_mesh_clear()
            M = np.array(ev.matrix_world)
            z = co.reshape(-1, 3)[::4] @ M[2, :3] + M[2, 3]
            lows[r.name].append(float(z.min()))
    for r in rigs:
        lo = lows[r.name]
        sm = [sorted(lo[max(0, i - 1):i + 2])[len(lo[max(0, i - 1):i + 2]) // 2] for i in range(len(lo))]
        for f, z in zip(frames, sm):
            r.delta_location[2] = -z
            r.keyframe_insert("delta_location", index=2, frame=f)
        for bag, fcs in _channelbag_fcurves(r.animation_data.action):
            for fc in fcs:
                if fc.data_path == "delta_location":
                    for kp in fc.keyframe_points:
                        kp.interpolation = "LINEAR"
        out[r.name] = [round(-max(sm) * 100, 1), round(-min(sm) * 100, 1)]
    scene.frame_set(1)
    return out


def add_workers(scene, spec, rocketbox_dir, seed=29, prop=None):
    global RB
    RB = Path(rocketbox_dir)
    rnd = random.Random(seed)
    fps = scene.render.fps
    coll = bpy.data.collections.get("People") or bpy.data.collections.new("People")
    if coll.name not in scene.collection.children:
        scene.collection.children.link(coll)
    placed = []
    mixamo = sorted((RB.parent / "mixamo").glob("*.fbx")) if (RB.parent / "mixamo").exists() else []
    for i, st in enumerate(STATIONS):
        role = st["role"]
        gender = "f" if st["avatar"].startswith("Female") else "m"
        name = f"worker_{i:02d}_{role}"
        arm = _instance(scene, coll, st, name, i % len(HAT_COLOURS))
        offset = rnd.randint(0, 90)  # no two neighbours in sync (walkers: clip phase only, path from its start)
        if st.get("cage"):
            st = dict(st, **_snap_to_cage(*st["cage"]))
        act = _clip(scene, gender, st["clip"])
        if act:
            act = _retarget(f"{gender}_{st['clip']}", act, st["avatar"])
        status = "no clip"
        if act:
            _play(arm, act, offset, fps)
            status = "clip"
        speed = None
        if role == "walk":
            speed = _planted_foot_speed(scene, arm, fps) or (act.get("speed", -1.0) if act else -1.0)
            speed = speed if speed and speed > 0.3 else 1.25
            _walk_path(arm, st["path"], speed, fps, 0)
        else:
            arm.location = (st["at"][0], st["at"][1], 0.0)
            _turn(arm, math.radians(st["face"]) + FACING_OFFSET)
        if act is not None and act.get("hip_z", -1.0) > 0:
            scene.frame_set(1)
            bpy.context.view_layer.update()
            pb = arm.pose.bones.get("Bip01 Pelvis")
            dz = act["hip_z"] - (arm.matrix_world @ pb.head).z
            if role == "walk":  # walkers carry location keys: shift every key
                for bag, fcs in _channelbag_fcurves(arm.animation_data.action):
                    for fc in fcs:
                        if fc.data_path == "location" and fc.array_index == 2:
                            for kp in fc.keyframe_points:
                                kp.co.y += dz
                                kp.handle_left.y += dz
                                kp.handle_right.y += dz
            else:
                arm.location.z += dz
            status += f", hip lift {dz:+.2f} m"
        if role != "walk":
            body_g = next(o for o in arm.children if o.name.endswith("_body"))
            low = 9.0
            for fk in (1, 60, 120, 180, 240, 300):
                scene.frame_set(fk)
                bpy.context.view_layer.update()
                ev = body_g.evaluated_get(bpy.context.evaluated_depsgraph_get())
                me = ev.to_mesh()
                low = min(low, min((ev.matrix_world @ v.co).z for v in list(me.vertices)[::5]))
                ev.to_mesh_clear()
            ground = (st.get("floor_z", 0.0))
            if abs(low - ground) > 0.008:
                arm.location.z += ground - low
                status += f", grounded {ground - low:+.3f} m"
            scene.frame_set(1)
        if _pending_props.get(name):
            scene.frame_set(1)
            heading = math.radians(st["face"]) if role != "walk" else math.atan2(
                st["path"][1][1] - st["path"][0][1], st["path"][1][0] - st["path"][0][0])
            body = next(o for o in arm.children if o.name.endswith("_body"))
            _fit_props(scene, arm, body, _templates[st["avatar"]], heading, _pending_props.pop(name))
        rec = {"name": name, "role": role, "avatar": st["avatar"], "clip": f"{gender}_{st['clip']}",
               "vest": "none (uniform T-shirt)" if st["vest"] is None else st["vest"] + (" (open)" if st.get("open") else ""),
               "offset_frames": offset, "status": status,
               "hat": st.get("hat") if st["avatar"] != "Female_Adult_06" else None, "gloves": bool(st.get("gloves")),
               "scanner": bool(st.get("scanner"))}
        if role == "walk":
            rec.update(path=st["path"], speed_mps=round(speed, 2), off_walkway=_on_walkways(st["path"], spec))
        else:
            rec.update(at=st["at"], face=st["face"], **({"cage_bay": st["cage_bay"]} if "cage_bay" in st else {}))
        placed.append(rec)
    mx_report = {}
    if USE_MIXAMO:  # owner decision 2026-10-30: Rocketbox (MIT) only in the render path
        import mixamo_workers  # noqa: E402  (it imports this module: load it only once this one is complete)
        mx_placed, mx_report = mixamo_workers.add(scene, spec, RB.parent / "mixamo" / "mixamo_worker.blend", coll,
                                                  rnd, prop=prop, fps=fps)
        placed += mx_placed
    rigs = [bpy.data.objects[p["name"]] for p in placed]
    work = {p["name"] for p in placed if p["role"] in ("dock", "bag_opening", "induction", "chutes", "exception")
            and any(c in p.get("clip", "") for c in ("work_mid", "work_table"))}
    settled = settle_workers(scene, [r for r in rigs if not _moves(r)], approach=work)
    grounded = ground_workers(scene, [r for r in rigs if r.name not in SEATED])
    work_items = place_work_items(scene, [r for r in rigs if r.name in work], coll)
    for p in placed:
        if p["name"] in settled:
            p["settled_m"] = settled[p["name"]]
        p["grounding_cm"] = grounded.get(p["name"])
        if p["name"] in work_items:
            p["work_item"] = work_items[p["name"]]
    no_vest = sum(1 for p in placed if p["vest"].startswith("none"))
    return placed, {"mixamo_files": [p.name for p in mixamo], **mx_report, "settled": settled,
                    "work_items": work_items,
                    "uniform_tshirt_share": round(no_vest / max(len(placed), 1), 2),
                    "facing_camera": facing_report(spec, placed)}
