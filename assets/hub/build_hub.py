"""Build the Spoor demo hub (fictional CONTOH Express hub, Klang Valley) in Blender from hub_spec.json.

Pass 1 — "procedural blockout": every machine, wall, door, walkway, sign and CCTV camera at its spec position and
size, with procedural materials. No downloaded models yet (that is the dressing pass, from the assets list in the
spec). No AI-generated models or images. Ground truth (render_truth.yaml) is NOT read here.

Run headless (does not touch an open Blender window):
  "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --factory-startup ^
      -P assets\\hub\\build_hub.py -- --spec assets\\hub\\hub_spec.json --out assets\\hub\\build\\hub.blend ^
      [--preview CAM_07,CAM_09 --preview-dir <folder>]

Frame: metres, X east, Y north, Z up (same as the spec); inside floor z = 0, truck yard z = -1.2 (dock height).
"""

import argparse
import ctypes
import json
import math
import os
import random
import sys
import time
from pathlib import Path

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--spec", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--preview", default="", help="comma-separated camera ids to render one still each")
ap.add_argument("--preview-dir", default="")
ap.add_argument("--samples", type=int, default=16)
args = ap.parse_args(argv)
SPEC = json.loads(Path(args.spec).read_text(encoding="utf-8"))
random.seed(20261028)
BALE_RND = random.Random(20261031)  # rack bale heights (own stream: the global one drives the rest of the hub)

BW, BD = SPEC["building"]["footprint_m"]
EAVES = SPEC["building"]["eaves_m"]
LOOP = SPEC["machines"]["loop"]
DECK = LOOP["deck_height"]
YARD_Z = -1.2  # dock height: truck bed level = inside floor
WALL_T = 0.2


def keep_awake(on: bool):
    if os.name == "nt":
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | (0x00000001 if on else 0))


# ------------------------------------------------------------------------------------------------ scene + materials
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"


def coll(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent or scene.collection).children.link(c)
    return c


C = {n: coll(n) for n in ("Shell", "Structure", "Machines", "Circulation", "Fixtures", "Clutter", "Signs",
                          "Lights", "CCTV", "Yard")}


def srgb(h):
    h = h.lstrip("#")
    return tuple(((int(h[i:i + 2], 16) / 255) ** 2.2) for i in (0, 2, 4))


def material(name, hexcol, rough=0.6, metal=0.0, noise=0.0, emit=0.0, transmit=0.0, alpha=1.0):
    m = bpy.data.materials.new(name)
    if hasattr(m, "use_nodes"):
        m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF") or nt.nodes.new("ShaderNodeBsdfPrincipled")
    col = (*srgb(hexcol), 1.0)
    bsdf.inputs["Base Color"].default_value = col
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if emit:
        bsdf.inputs["Emission Color"].default_value = col
        bsdf.inputs["Emission Strength"].default_value = emit
    if transmit:
        bsdf.inputs["Transmission Weight"].default_value = transmit
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
    if noise:  # wear: noise varies roughness and darkens the colour slightly
        n = nt.nodes.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = noise
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["To Min"].default_value = rough * 0.7
        mr.inputs["To Max"].default_value = min(1.0, rough * 1.3)
        nt.links.new(n.outputs["Fac"], mr.inputs["Value"])
        nt.links.new(mr.outputs["Result"], bsdf.inputs["Roughness"])
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.inputs["Factor"].default_value = 0.25
        mix.inputs["A"].default_value = col
        mix.inputs["B"].default_value = (col[0] * 0.7, col[1] * 0.7, col[2] * 0.7, 1)
        nt.links.new(n.outputs["Fac"], mix.inputs["Factor"])
        nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    return m


BRAND = "#0e7c7b"  # CONTOH Express teal (fictional; chosen to avoid the colours of real Malaysian couriers)
M = {
    "floor": material("floor_epoxy_concrete", "#8d8c88", 0.45, noise=3.0),
    "asphalt": material("asphalt", "#3a3a3a", 0.9, noise=8.0),
    "ground": material("ground_gravel", "#6b665c", 0.95, noise=5.0),
    "cladding": material("cladding_steel", "#c9cdd1", 0.45, 0.6),
    "wall_in": material("wall_inside", "#d9d9d4", 0.8, noise=2.0),
    "steel": material("galvanised_steel", "#9aa0a6", 0.4, 1.0),
    "frame": material("painted_frame", "#5f6b78", 0.5, 0.3),
    "yellow": material("safety_yellow", "#f2c21b", 0.5),
    "black": material("black_rubber", "#141414", 0.85),
    "belt": material("belt_rubber", "#202224", 0.7, noise=20.0),
    "carrier": material("carrier", "#2b3a4a", 0.5),
    "red": material("reject_red", "#c0392b", 0.5),
    "blue": material("crate_blue", "#1f5fa8", 0.6),
    "orange": material("rack_orange", "#e46b12", 0.5),
    "rack_blue": material("rack_blue", "#244a8c", 0.5),
    "glass": material("glass", "#dfe8ec", 0.05, transmit=1.0),
    "white": material("white_paint", "#f2f2ee", 0.6),
    "wood": material("pallet_wood", "#a07a4e", 0.85, noise=30.0),
    "card": material("cardboard", "#a8825a", 0.85, noise=25.0),
    "label": material("label_white", "#fbfbf8", 0.5),
    "fly_grey": material("flyer_grey", "#8a8d91", 0.4),
    "fly_black": material("flyer_black", "#1c1c1e", 0.35),
    "fly_white": material("flyer_white", "#e9e9ea", 0.4),
    "fly_red": material("flyer_red", "#c4231d", 0.4),
    "fly_blue": material("flyer_blue", "#1f4fb0", 0.4),
    "fly_purple": material("flyer_purple", "#6a2f8f", 0.4),
    "cage_red": material("powder_coat_red", "#a82a20", 0.55, 0.3, noise=18.0),
    "cage_yellow": material("powder_coat_yellow", "#d1a10e", 0.55, 0.3, noise=18.0),
    "sack": material("woven_sack", "#e6e3da", 0.9, noise=60.0),
    "sack_blue": material("woven_sack_blue", "#3d6fb0", 0.9, noise=60.0),
    "brand": material("brand_teal", BRAND, 0.5),
    "lamp": material("lamp_emit", "#fff4e6", 0.5, emit=8.0),
    "lightbar": material("tunnel_lightbar", "#ff6a2a", 0.5, emit=10.0),  # red-orange LED scanner light
    "scan_led": material("tunnel_scan_led", "#ff4a1a", 0.4, emit=6.0),
    "exit": material("exit_green_emit", "#1fa64a", 0.5, emit=6.0),
    "screen": material("screen_emit", "#7fc7ff", 0.3, emit=2.0),
    "sign": material("sign_board", "#fafafa", 0.6),
    "ink": material("sign_ink", "#1a1a1a", 0.6),
    "ink_red": material("sign_red", "#c62828", 0.6),
    "wrap": material("stretch_wrap", "#c9cfcd", 0.25, noise=40.0, alpha=0.65),  # milky film: cartons show faintly
    "rooflight": material("rooflight_panel", "#eef3f5", 0.6, emit=1.2),  # translucent sheet: glows, not see-through
    "pipe_red": material("sprinkler_red", "#b3261e", 0.5),
    "board_blue": material("door_board_blue", "#12305a", 0.45, 0.3),
    "sack_grey": material("woven_sack_grey", "#9a9d9f", 0.9, noise=60.0),
    "wrap_thin": material("stretch_wrap_thin", "#d9dedd", 0.2, noise=30.0, alpha=0.38),
    "lamp_red": material("dock_lamp_red", "#ff2a1a", 0.3, emit=6.0),
    "lamp_green": material("dock_lamp_green", "#23ff4a", 0.3, emit=6.0),
    "lamp_off": material("dock_lamp_off", "#2a2a2a", 0.4),
    "stencil": material("floor_stencil", "#d9d9d2", 0.85, noise=6.0, alpha=0.5),
    "scuff": material("wall_scuff", "#262624", 0.9, noise=25.0, alpha=0.55),
    "cork": material("notice_cork", "#9c7447", 0.9, noise=40.0),
    "poster_green": material("poster_green", "#1e7a3c", 0.6),
    "panel_grey": material("electrical_panel", "#9aa1a6", 0.45, 0.4),
    "camera": material("camera_housing", "#ececec", 0.35),
}


# ------------------------------------------------------------------------------------------------ geometry helpers
def mat_aabb(x0, y0, z0, x1, y1, z1):
    return Matrix.Translation(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)) @ Matrix.Diagonal(
        (abs(x1 - x0), abs(y1 - y0), abs(z1 - z0), 1.0))


def mat_seg(p0, p1, w, h):
    """Box from p0 to p1 (centreline), w wide (sideways), h tall."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    yaw = math.atan2(d.y, d.x)
    pitch = math.atan2(d.z, math.hypot(d.x, d.y))
    return (Matrix.Translation((p0 + p1) / 2) @ Euler((0, -pitch, yaw)).to_matrix().to_4x4()
            @ Matrix.Diagonal((d.length, w, h, 1.0)))


def mesh_obj(name, items, mats, collection, kind="cube"):
    """One object from many transformed unit cubes (or spheres): items = [(matrix, material_index)]."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    for m, mi in items:
        if kind == "sphere":
            r = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.5, matrix=m)
        else:
            r = bmesh.ops.create_cube(bm, size=1.0, matrix=m)
        faces = {f for v in r["verts"] for f in v.link_faces}
        for f in faces:
            f.material_index = mi
        if kind == "openbox":  # bin / crate without a lid
            top = max(faces, key=lambda f: f.calc_center_median().z)
            bmesh.ops.delete(bm, geom=[top], context="FACES_ONLY")
        if kind == "sack":  # open-top bag: drop the lid, flare the mouth over the frame rim
            top = max(faces, key=lambda f: f.calc_center_median().z)
            mouth = list(top.verts)
            bmesh.ops.delete(bm, geom=[top], context="FACES_ONLY")
            c = sum((v.co for v in mouth), Vector()) / len(mouth)
            for v in mouth:
                v.co.x, v.co.y = c.x + (v.co.x - c.x) * 1.12, c.y + (v.co.y - c.y) * 1.12
    bm.to_mesh(me)
    bm.free()
    for mt in mats:
        me.materials.append(M[mt])
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    return ob


def tube_matrix(p0, p1, r):
    """Unit cylinder (radius 1, depth 1 along Z) placed from p0 to p1 with radius r."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    rot = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    return Matrix.Translation((p0 + p1) / 2) @ rot @ Matrix.Diagonal((r, r, d.length, 1.0))


def tubes_into(bm, segs, mi, sides=8):
    for p0, p1, r in segs:
        res = bmesh.ops.create_cone(bm, cap_ends=True, segments=sides, radius1=1.0, radius2=1.0, depth=1.0,
                                    matrix=tube_matrix(p0, p1, r))
        for f in {f for v in res["verts"] for f in v.link_faces}:
            f.material_index = mi


def superellipse(a, b, n=24, p=4.0):
    out = []
    for i in range(n):
        th = 2 * math.pi * i / n
        c, s_ = math.cos(th), math.sin(th)
        out.append((a * math.copysign(abs(c) ** (2 / p), c), b * math.copysign(abs(s_) ** (2 / p), s_), th))
    return out


def loft_into(bm, rings, mi, cap_bottom=True, cap_top=False):
    """rings: list of [(x, y, z)] with equal counts, top to bottom -> skin (+ caps)."""
    vr = [[bm.verts.new(p) for p in ring] for ring in rings]
    n = len(rings[0])
    faces = []
    for a, b in zip(vr, vr[1:]):
        for i in range(n):
            faces.append(bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i])))
    if cap_bottom:
        faces.append(bm.faces.new(list(reversed(vr[-1]))))
    if cap_top:
        faces.append(bm.faces.new(vr[0]))
    for f in faces:
        f.material_index = mi


SACK_A, SACK_B, RIM = 0.46, 0.36, 0.9  # mouth half-sizes clipped to the bag frame rim (frame 1.0 x 0.8, rim 0.9 m)


def sack_rings(kind, seed):
    """Woven sack hung from the rim, mouth clipped open: empty (limp), half, full (resting on the floor)."""
    rnd = random.Random(seed)
    ph = rnd.uniform(0, 6.28)
    # parcel corners pushing the weave out: local sharp bumps (angle, depth along the bag, size)
    bumps = [] if kind == "empty" else [(rnd.uniform(0, 6.28), rnd.uniform(0.3 if kind == "half" else 0.15, 0.9),
                                         rnd.uniform(0.05, 0.11)) for _ in range(rnd.randint(6, 10))]
    rings = [[(x * 1.06, y * 1.06, RIM - 0.07) for x, y, _ in superellipse(SACK_A, SACK_B)],  # lip folded over rim
             [(x * 1.02, y * 1.02, RIM + 0.015) for x, y, _ in superellipse(SACK_A, SACK_B)]]
    for k in range(12):
        t = k / 11
        if kind == "empty":
            z, sc, amp = RIM - 0.72 * t, 1.0 - 0.5 * t, 0.07
        elif kind == "half":
            z = RIM - 0.86 * t
            sc = 0.93 + 0.1 * math.sin(math.pi * min(max((t - 0.4) / 0.6, 0), 1))
            amp = 0.06 if t < 0.45 else 0.015
        else:  # full: fills the frame almost like a box (a big belly under a narrow rim read as a vase: review 006)
            z, sc, amp = RIM - 0.86 * t, 1.0 + 0.05 * math.sin(math.pi * min(max((t - 0.05) / 0.95, 0), 1)), 0.012
        if t > 0.92 and kind != "empty":
            sc *= 0.92  # flattened where it sits on the floor
        ring = []
        lump = 0.0 if kind == "empty" else 0.07 * math.sin(math.pi * t)  # parcels pushing the weave out
        if t < 0.22:  # pleats where the mouth is gathered into the clips
            amp += 0.06 * (1 - t / 0.22)
        lean = 0.06 * t * t * (1 if seed % 2 else -1)  # a hanging sack slumps to one side
        for x, y, th in superellipse(SACK_A, SACK_B):
            w = 1 + amp * (0.6 * math.sin(7 * th + 5 * t + ph) + 0.4 * math.sin(13 * th - 3 * t + ph))
            w += lump * (math.sin(2 * th + ph * 1.7) + 0.6 * math.sin(3 * th + ph * 0.6))
            if t < 0.22:
                w += 0.05 * (1 - t / 0.22) * math.sin(11 * th + ph)
            for bth, bt, ba in bumps:
                dth = (th - bth + math.pi) % (2 * math.pi) - math.pi
                w += ba * math.exp(-(dth / 0.22) ** 2 - ((t - bt) / 0.1) ** 2)
            ring.append((x * sc * w + lean, y * sc * w, z))
        rings.append(ring)
    return rings


def tied_sack_rings(seed):
    """Full sack tied at the neck, standing on the floor (waiting to go into a cage)."""
    rnd = random.Random(seed)
    ph = rnd.uniform(0, 6.28)
    prof = [(0.0, 0.8), (0.04, 0.95), (0.2, 1.05), (0.45, 1.08), (0.6, 0.95), (0.68, 0.6), (0.73, 0.15), (0.76, 0.12),
            (0.84, 0.3), (0.88, 0.05)]
    # parcel corners pushing the weave out (a smooth body read as a white ball / vase: review 006 #7)
    bumps = [(rnd.uniform(0, 6.28), rnd.uniform(0.08, 0.6), rnd.uniform(0.06, 0.12)) for _ in range(rnd.randint(6, 9))]
    rings = []
    for z, sc in reversed(prof):
        ring = []
        body = 0.2 < z < 0.6
        for x, y, th in superellipse(0.36, 0.28, p=3.0):
            w = 1 + 0.05 * math.sin(9 * th + 7 * z + ph) + (0.09 * (math.sin(2 * th + ph) + 0.5 * math.sin(3 * th - ph))
                                                             if body else 0.0)
            for bth, bz, ba in bumps:
                dth = (th - bth + math.pi) % (2 * math.pi) - math.pi
                w += ba * math.exp(-(dth / 0.25) ** 2 - ((z - bz) / 0.09) ** 2)
            ring.append((x * sc * w + 0.04 * z * math.sin(ph), y * sc * w, z))
        rings.append(ring)
    return rings


def slumped_sack_rings(seed):
    """A full sack closed and slumped: low, wide, lumpy, the neck folded under (no bottle shape)."""
    rnd = random.Random(seed)
    ph, ph2 = rnd.uniform(0, 6.28), rnd.uniform(0, 6.28)
    h = rnd.uniform(0.26, 0.34)  # lying, slumped flat (not a ball)
    prof = [(0.0, 0.84), (0.05, 1.0), (0.4, 1.12), (0.7, 1.06), (0.85, 0.9), (0.95, 0.62), (1.0, 0.2)]
    rings = []
    for zf, sc in reversed(prof):
        ring = []
        for x, y, th in superellipse(0.255, 0.2, p=3.6):  # boxy pillow, sized to sit INSIDE a roll cage
            w = 1 + 0.1 * (math.sin(2 * th + ph) + 0.6 * math.sin(3 * th - ph2)) * math.sin(math.pi * min(zf, 0.95))
            w += 0.05 * math.sin(9 * th + 6 * zf + ph2) + 0.025 * math.sin(17 * th + ph)  # creases
            z = zf * h
            if zf > 0.8:  # sewn top: corner ears stick up, the middle slumps into a saddle
                ear = abs(math.cos(th)) ** 6
                z += (0.07 * ear - 0.05 * (1 - abs(math.cos(th)))) * (zf - 0.8) / 0.2
            ring.append((x * sc * w + 0.02 * zf * math.cos(ph), y * sc * w, z))
        rings.append(ring)
    return rings


_mesh_cache = {}


def shared_mesh(key, build, mats):
    if key not in _mesh_cache:
        me = bpy.data.meshes.new(key)
        bm = bmesh.new()
        build(bm)
        bm.to_mesh(me)
        bm.free()
        for mt in mats:
            me.materials.append(M[mt])
        if key.startswith("sack"):  # woven fabric reads soft, never faceted
            me.shade_smooth()
        _mesh_cache[key] = me
    return _mesh_cache[key]


def place(mesh, name, loc, rot_z=0.0, scale=1.0, collection=None):
    ob = bpy.data.objects.new(name, mesh)
    ob.location, ob.rotation_euler[2], ob.scale = loc, rot_z, (scale,) * 3
    (collection or C["Clutter"]).objects.link(ob)
    return ob


def boxes(name, mats_items, collection):
    """mats_items: {material: [matrix, ...]} -> one multi-material object."""
    mats = list(mats_items)
    return mesh_obj(name, [(m, i) for i, mt in enumerate(mats) for m in mats_items[mt]], mats, collection)


def cylinder(name, loc, r, depth, mat, collection, caps=True, segs=16):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=caps, segments=segs, radius1=r, radius2=r, depth=depth,
                          matrix=Matrix.Translation(loc))
    bm.to_mesh(me)
    bm.free()
    me.materials.append(M[mat])
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    return ob


FONT_PATH = Path(args.out).resolve().parent / "third_party" / "fonts" / "BarlowCondensed-Bold.ttf"
BOARD_FONT = bpy.data.fonts.load(str(FONT_PATH)) if FONT_PATH.exists() else None  # OFL; "1" never reads as "I"


def text(name, body, loc, rot_deg, size, mat, collection, extrude=0.005, font=None):
    cu = bpy.data.curves.new(name, "FONT")
    cu.resolution_u = 2  # glyph curves: a few pixels on CCTV, default 12 tessellates ~2.5k tris per sign
    cu.body = body
    if font is not None:
        cu.font = font
    cu.size = size
    cu.extrude = extrude
    cu.align_x, cu.align_y = "CENTER", "CENTER"
    ob = bpy.data.objects.new(name, cu)
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot_deg]
    ob.data.materials.append(M[mat])
    collection.objects.link(ob)
    return ob


# wall-facing rotations for upright text (text faces the given direction, reads correctly from the viewer)
FACE = {"+Y": (90, 0, 180), "-Y": (90, 0, 0), "+X": (90, 0, 90), "-X": (90, 0, -90)}


def sign(name, body, centre, facing, size=0.3, board=None, ink="ink", board_mat="sign"):
    x, y, z = centre
    off = {"+Y": (0, 0.03, 0), "-Y": (0, -0.03, 0), "+X": (0.03, 0, 0), "-X": (-0.03, 0, 0)}[facing]
    if board:
        w, h = board
        bx = (w, 0.03) if facing in ("+Y", "-Y") else (0.03, w)
        boxes(f"{name}_board", {board_mat: [mat_aabb(x - bx[0] / 2, y - bx[1] / 2, z - h / 2,
                                                     x + bx[0] / 2, y + bx[1] / 2, z + h / 2)]}, C["Signs"])
    return text(name, body, (x + off[0], y + off[1], z), FACE[facing], size, ink, C["Signs"])


SIGN_DIR = Path(args.spec).resolve().parent / "build" / "signs"
_sign_mats = {}


def image_sign(name, sign_id, centre, facing, size=(0.3, 0.4), double=False, collection=None):
    """A 3 mm HIPS sign plate (make_signs.py texture: real catalogue layout + wording) facing +X/-X/+Y/-Y; double:
    printed both sides (hung over a crossing). Back and edges plain white."""
    if sign_id not in _sign_mats:
        m = bpy.data.materials.new(f"safety_sign_{sign_id}")
        m.use_nodes = True
        nt = m.node_tree
        b = nt.nodes.get("Principled BSDF")
        b.inputs["Roughness"].default_value = 0.45
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(SIGN_DIR / f"{sign_id}.png"), check_existing=True)
        nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
        _sign_mats[sign_id] = m
    w, h = size
    x, y, z = centre
    yaw = {"+Y": 0.0, "-Y": math.pi, "+X": -math.pi / 2, "-X": math.pi / 2}[facing]
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.verify()
    r = bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Diagonal((w, 0.003, h, 1)))
    for f in {f for v in r["verts"] for f in v.link_faces}:
        f.material_index = 0
        n = f.normal
        if n.y > 0.9 or (double and n.y < -0.9):  # printed face(s): +Y before rotation
            f.material_index = 1
            for loop in f.loops:  # a viewer facing the +Y face has +X on their LEFT: mirror u, else text reads backwards
                u = (0.5 - loop.vert.co.x / w) if n.y > 0 else (loop.vert.co.x / w + 0.5)
                loop[uvl].uv = (u, loop.vert.co.z / h + 0.5)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(M["sign"])
    me.materials.append(_sign_mats[sign_id])
    ob = bpy.data.objects.new(name, me)
    ob.location, ob.rotation_euler[2] = (x, y, z), yaw
    (collection or C["Signs"]).objects.link(ob)
    return ob


# ------------------------------------------------------------------------------------------------ ground + shell
DOORS = SPEC["building"]["doors"]
boxes("floor_slab", {"floor": [mat_aabb(0.003, 0.003, -0.3, BW - 0.003, BD - 0.003, 0)]}, C["Shell"])  # its edges
# 3 mm inside the walls' outer faces (flush, they z-fought along the building's base: mesh_hygiene)
boxes("ground", {"ground": [mat_aabb(-45, -25, YARD_Z - 0.3, BW + 30, BD + 40, YARD_Z - 0.02)]}, C["Yard"])
yard = next(z for z in SPEC["zones"] if z["id"] == "Z14")["polygon_m"]
for side, poly in yard.items():
    (x0, y0), (x1, y1) = poly[0], poly[2]
    boxes(f"yard_{side}", {"asphalt": [mat_aabb(x0, y0, YARD_Z - 0.02, x1, y1, YARD_Z)]}, C["Yard"])


def wall(side):
    """Wall along one side with door openings; dock walls (W, N) run down to the yard."""
    horizontal = side in ("S", "N")
    length = BW if horizontal else BD
    fixed = {"S": 0.0, "N": BD - WALL_T, "W": 0.0, "E": BW - WALL_T}[side]
    zbot = YARD_Z
    ops = sorted((d["centre"][0 if horizontal else 1] - d["width"] / 2, d["centre"][0 if horizontal else 1]
                  + d["width"] / 2, d["height"]) for d in DOORS if d["wall"] == side)
    pieces, cur = [], 0.0
    for a, b, hgt in ops + [(length, length, 0)]:
        if a > cur:
            pieces.append((cur, a, zbot, EAVES))
        if b > a:
            pieces.append((a, b, zbot, -0.003))  # below the opening (dock face / plinth), 3 mm under the slab top
            # (at z 0 its top z-fought with the slab in every doorway: mesh_hygiene)
            pieces.append((a, b, hgt, EAVES))  # lintel and wall above
        cur = b
    mats = []
    for a, b, z0, z1 in pieces:
        if horizontal:
            mats.append(mat_aabb(a, fixed, z0, b, fixed + WALL_T, z1))
        else:  # W / E fit between the N and S walls (full length, their ends z-fought in the corners)
            a, b = max(a, WALL_T), min(b, BD - WALL_T)
            if b - a > 1e-4:
                mats.append(mat_aabb(fixed, a, z0, fixed + WALL_T, b, z1))
    boxes(f"wall_{side}", {"cladding": mats}, C["Shell"])


for s_ in ("S", "N", "W", "E"):
    wall(s_)
boxes("roof", {"cladding": [mat_aabb(0, 0, EAVES, BW, BD, EAVES + 0.15)]}, C["Shell"])
# translucent roof-light strips (real sheds use them; lets soft daylight in from above)
boxes("roof_lights", {"rooflight": [mat_aabb(x - 0.6, 2, EAVES - 0.01, x + 0.6, BD - 2, EAVES + 0.16)
                                for x in (6, 18, 30, 42, 54)]}, C["Shell"])

# doors: dock shutters (rolled up where a lorry is docked, else closed), levellers, bumpers, fire exits
DOCK_FIT = []
OPEN_DOCKS = {"D02", "D05", "D03", "D08", "D11", "D09"}
LORRY_DOCKS = {"D02", "D05", "D08", "D11"}  # a lorry is docked: shutter up, dock light green
dock_items = {"steel": [], "black": [], "frame": []}
for d in DOORS:
    cx, cy = d["centre"]
    hw, hh = d["width"] / 2, d["height"]
    if d["kind"] == "dock":
        if d["wall"] == "W":
            dock_items["frame"].append(mat_aabb(WALL_T, cy - hw - 0.1, hh, WALL_T + 0.5, cy + hw + 0.1, hh + 0.5))
            dock_items["steel"].append(mat_aabb(WALL_T, cy - hw + 0.1, -0.02, WALL_T + 2.0, cy + hw - 0.1, 0.005))
            dock_items["black"] += [mat_aabb(-0.15, cy + s * (hw - 0.3) - 0.15, -0.9, 0, cy + s * (hw - 0.3) + 0.15,
                                             -0.3) for s in (-1, 1)]
            if d["id"] not in OPEN_DOCKS:
                dock_items["frame"].append(mat_aabb(0.05, cy - hw, 0, 0.12, cy + hw, hh))
        else:  # north
            dock_items["frame"].append(mat_aabb(cx - hw - 0.1, BD - WALL_T - 0.5, hh, cx + hw + 0.1, BD - WALL_T, hh + 0.5))
            dock_items["steel"].append(mat_aabb(cx - hw + 0.1, BD - WALL_T - 2.0, -0.02, cx + hw - 0.1, BD - WALL_T, 0.005))
            dock_items["black"] += [mat_aabb(cx + s * (hw - 0.3) - 0.15, BD, -0.9, cx + s * (hw - 0.3) + 0.15, BD + 0.15,
                                             -0.3) for s in (-1, 1)]
            if d["id"] not in OPEN_DOCKS:
                dock_items["frame"].append(mat_aabb(cx - hw, BD - 0.12, 0, cx + hw, BD - 0.05, hh))
        DOCK_FIT.append(d)
    else:  # fire exit / staff door: closed leaf, landing + steps outside, lit KELUAR sign inside
        if d["wall"] == "S":
            dock_items["frame"].append(mat_aabb(cx - hw, 0.05, 0, cx + hw, 0.1, hh))
            dock_items["steel"].append(mat_aabb(cx - 0.75, -1.5, YARD_Z, cx + 0.75, 0, 0))
            boxes(f"exit_sign_{d['id']}", {"exit": [mat_aabb(cx - 0.2, WALL_T, hh + 0.2, cx + 0.2, WALL_T + 0.06,
                                                             hh + 0.35)]}, C["Signs"])
            text(f"exit_txt_{d['id']}", "KELUAR", (cx, WALL_T + 0.07, hh + 0.275), FACE["+Y"], 0.09, "white",
                 C["Signs"])
        else:  # east
            dock_items["frame"].append(mat_aabb(BW - 0.1, cy - hw, 0, BW - 0.05, cy + hw, hh))
            dock_items["steel"].append(mat_aabb(BW, cy - 0.75, YARD_Z, BW + 1.5, cy + 0.75, 0))
            boxes(f"exit_sign_{d['id']}", {"exit": [mat_aabb(BW - WALL_T - 0.06, cy - 0.2, hh + 0.2, BW - WALL_T,
                                                             cy + 0.2, hh + 0.35)]}, C["Signs"])
            text(f"exit_txt_{d['id']}", "KELUAR", (BW - WALL_T - 0.07, cy, hh + 0.275), FACE["-X"], 0.09, "white",
                 C["Signs"])
boxes("doors_docks", dock_items, C["Shell"])


def dock_furniture():
    """Per dock door: rigid number board, guard posts, red/green dock light, dock seal, floor stencil, scuffs."""
    items = {"board_blue": [], "black": [], "lamp_red": [], "lamp_green": [], "lamp_off": [], "scuff": [],
             "panel_grey": []}
    post_bm = bmesh.new()
    for d in DOCK_FIT:
        cx, cy = d["centre"]
        hw, hh = d["width"] / 2, d["height"]
        west = d["wall"] == "W"
        lorry = d["id"] in LORRY_DOCKS

        def at(along, out, z0, z1, a_half, o_half):  # box in door-local axes (along the wall / out of the wall)
            if west:
                return mat_aabb(WALL_T + out - o_half, cy + along - a_half, z0, WALL_T + out + o_half, cy + along + a_half, z1)
            return mat_aabb(cx + along - a_half, BD - WALL_T - out - o_half, z0, cx + along + a_half,
                            BD - WALL_T - out + o_half, z1)
        items["board_blue"].append(at(0, 0.03, hh + 0.55, hh + 1.15, 0.55, 0.025))  # rigid metal board
        facing = "+X" if west else "-Y"
        loc = (WALL_T + 0.06, cy, hh + 0.85) if west else (cx, BD - WALL_T - 0.06, hh + 0.85)
        text(f"door_board_{d['id']}", d["board"], loc, FACE[facing], 0.55, "white", C["Signs"], font=BOARD_FONT)
        for sgn in (-1, 1):  # guard posts, yellow with black bands
            px, py = ((WALL_T + 0.45, cy + sgn * (hw + 0.3)) if west else (cx + sgn * (hw + 0.3), BD - WALL_T - 0.45))
            for k in range(6):
                tubes_into(post_bm, [((px, py, 0.2 * k), (px, py, 0.2 * (k + 1)), 0.09)], k % 2, sides=12)
            items["scuff"].append(at(sgn * (hw + 0.65), 0.004, 0.12, 0.6, 0.35, 0.002))  # forklift-height scuffs
        items["panel_grey"].append(at(hw + 0.75, 0.05, 1.9, 2.4, 0.09, 0.05))  # dock light housing
        items["lamp_green" if lorry else "lamp_off"].append(at(hw + 0.75, 0.11, 2.17, 2.31, 0.06, 0.01))
        items["lamp_off" if lorry else "lamp_red"].append(at(hw + 0.75, 0.11, 1.99, 2.13, 0.06, 0.01))
        for sgn in (-1, 1):  # dock seal: 0.3 m black foam pads either side of the opening, on the outside face
            a0, a1 = sorted((sgn * hw, sgn * (hw + 0.3)))
            if west:
                items["black"].append(mat_aabb(-0.35, cy + a0, 0, 0, cy + a1, hh))
            else:
                items["black"].append(mat_aabb(cx + a0, BD, 0, cx + a1, BD + 0.35, hh))
        items["black"].append(mat_aabb(-0.35, cy - hw - 0.3, hh, 0, cy + hw + 0.3, hh + 0.4) if west else
                              mat_aabb(cx - hw - 0.3, BD, hh, cx + hw + 0.3, BD + 0.35, hh + 0.4))
        sloc = (2.9, cy, 0.006) if west else (cx, BD - 2.9, 0.006)  # faded bay number on the floor
        text(f"floor_stencil_{d['id']}", d["board"], sloc, (0, 0, -90 if west else 180), 1.0, "stencil", C["Circulation"],
             extrude=0.0, font=BOARD_FONT)
    boxes("dock_furniture", items, C["Shell"])
    me = bpy.data.meshes.new("dock_guard_posts")
    post_bm.to_mesh(me)
    post_bm.free()
    for mt in ("yellow", "black"):
        me.materials.append(M[mt])
    C["Shell"].objects.link(bpy.data.objects.new("dock_guard_posts", me))
    for body, loc, facing in (("PENERIMAAN / RECEIVING", (WALL_T + 0.04, 17.0, 5.6), "+X"),
                              ("PENGHANTARAN / DISPATCH", (39.0, BD - WALL_T - 0.04, 5.6), "-Y")):
        x, y, z = loc
        bx = (0.04, 7.0) if facing == "+X" else (7.0, 0.04)
        boxes(f"zone_board_{body[:6]}", {"board_blue": [mat_aabb(x - bx[0] / 2, y - bx[1] / 2, z - 0.45,
                                                                 x + bx[0] / 2, y + bx[1] / 2, z + 0.45)]}, C["Signs"])
        off = (0.04, 0) if facing == "+X" else (0, -0.04)
        text(f"zone_text_{body[:6]}", body, (x + off[0], y + off[1], z), FACE[facing], 0.55, "white", C["Signs"],
             font=BOARD_FONT)


dock_furniture()

# ------------------------------------------------------------------------------------------------ steel structure
col_items = {"frame": [], "yellow": []}
for x, y in SPEC["building"]["columns"]:
    # 3 mm clear of the walls' inner faces (flush, they z-fought with the walls: mesh_hygiene)
    x = min(max(x, WALL_T + 0.153), BW - WALL_T - 0.153)
    y = min(max(y, WALL_T + 0.203), BD - WALL_T - 0.203)
    col_items["frame"] += [mat_aabb(x - 0.15, y - 0.2, 0, x + 0.15, y - 0.17, EAVES),  # I-section: two flanges
                           mat_aabb(x - 0.15, y + 0.17, 0, x + 0.15, y + 0.2, EAVES),
                           mat_aabb(x - 0.01, y - 0.17, 0, x + 0.01, y + 0.17, EAVES)]  # web
    if 0 < y < BD - 1:
        col_items["yellow"].append(mat_aabb(x - 0.3, y - 0.3, 0, x + 0.3, y + 0.3, 1.0))  # forklift guard
TRUSS_BOTTOM = EAVES - 1.2
for x in (WALL_T + 0.083, 12, 24, 36, 48, BW - WALL_T - 0.083):  # trusses span north-south: chords + zig-zag web
    col_items["frame"] += [mat_aabb(x - 0.08, WALL_T, EAVES - 0.25, x + 0.08, BD - WALL_T, EAVES - 0.05),
                           mat_aabb(x - 0.06, WALL_T, TRUSS_BOTTOM, x + 0.06, BD - WALL_T, TRUSS_BOTTOM + 0.15)]
    # (ending flush with the walls' outer faces, the chords z-fought with them: mesh_hygiene)
    for k in range(int(BD / 1.5)):
        y0_, y1_ = max(1.5 * k, WALL_T + 0.003), min(1.5 * (k + 1), BD - WALL_T - 0.003)
        za, zb = (TRUSS_BOTTOM + 0.15, EAVES - 0.25) if k % 2 == 0 else (EAVES - 0.25, TRUSS_BOTTOM + 0.15)
        col_items["frame"].append(mat_seg((x, y0_, za), (x, y1_, zb), 0.05, 0.05))
for y in [1.5 + 2.5 * k for k in range(16)]:  # purlins
    col_items["frame"].append(mat_aabb(WALL_T + 0.003, y - 0.05, EAVES - 0.1, BW - WALL_T - 0.003, y + 0.05, EAVES))
boxes("structure", col_items, C["Structure"])
roof_items = {"steel": [], "black": [], "pipe_red": []}
for y in (8.5, 21.5, 31.0):  # ladder cable trays under the trusses, with cable bundles and drop rods
    roof_items["steel"] += [mat_aabb(0.4, y - 0.2, 8.9, BW - 0.4, y - 0.17, 9.0),
                            mat_aabb(0.4, y + 0.17, 8.9, BW - 0.4, y + 0.2, 9.0),
                            mat_aabb(0.4, y - 0.17, 8.9, BW - 0.4, y + 0.17, 8.91)]
    roof_items["black"].append(mat_aabb(0.4, y - 0.12, 8.91, BW - 0.4, y + 0.05, 8.97))
    roof_items["steel"] += [mat_aabb(x - 0.01, y - 0.19, 9.0, x + 0.01, y - 0.17, TRUSS_BOTTOM) for x in range(3, 60, 3)]
for y in range(3, 40, 6):  # sprinkler mains
    roof_items["pipe_red"].append(mat_aabb(0.4, y - 0.05, EAVES - 0.75, BW - 0.4, y + 0.05, EAVES - 0.65))
boxes("roof_services", roof_items, C["Structure"])

# ------------------------------------------------------------------------------------------------ conveyors
conv = {"belt": [], "steel": [], "frame": []}
BOOM_SPOTS = []
BOOM_END_X = 4.55  # booms end at the collector's west side frame (x 4.57); flow.py hands over from here
BOOM_BELT_X = 4.595  # the belt + bed run on through the frame's opening to 5 mm off the collector's belt (zone audit
# 1 Nov: a 5 cm gap at x 4.55-4.60, the carton crossed over the floor)
BOOM_YS = [cv["path"][0][1] for cv in SPEC["machines"]["conveyors"] if cv["kind"] == "telescopic"]
door_at_y = {d["centre"][1]: d["id"] for d in DOORS if d["wall"] == "W"}
for cv in SPEC["machines"]["conveyors"]:
    if cv["kind"] != "telescopic":
        continue
    y, h = cv["path"][0][1], cv["height"]
    extended = door_at_y.get(y) in LORRY_DOCKS  # boom runs out through the door into the lorry body
    conv["frame"].append(mat_aabb(1.4, y - 0.5, 0.35, 4.4, y + 0.5, h - 0.15))  # base unit on legs
    # belt bed up to the collector's edge (to x 5.0 it ran into the collector; owner rule: nothing through anything)
    conv["frame"].append(mat_aabb(1.4, y - 0.33, h - 0.2, BOOM_BELT_X, y + 0.33, h - 0.05))
    conv["belt"].append(mat_aabb(1.4, y - 0.29, h - 0.05, BOOM_BELT_X, y + 0.29, h))
    for lx in (1.5, 4.3):
        for ly in (y - 0.42, y + 0.42):
            conv["steel"].append(mat_aabb(lx - 0.04, ly - 0.04, 0, lx + 0.04, ly + 0.04, 0.35))
    # extended: the nose reaches 1.2 m into the trailer, at the parcel wall (early in the unload, so the
    # unloaders stand just inside the doors where the hall cameras can see them)
    sections = [(0.6, 1.4, 0.62)] + ([(-1.2, 0.6, 0.56)] if extended else [])
    for k, (xa, xb, wd) in enumerate(sections):
        zt = h - 0.03 * k  # each nested section's frame sits a little lower ...
        conv["frame"].append(mat_aabb(xa, y - wd / 2, zt - 0.2, xb, y + wd / 2, zt - 0.05))
        # ... but one belt runs over all of them at h (a 3 cm step up at x 0.6 put stalled parcels 2-3 cm into it)
        conv["belt"].append(mat_aabb(xa, y - wd / 2 + 0.04, zt - 0.05, xb, y + wd / 2 - 0.04, h))
    if extended:  # parcels riding the boom out of the lorry
        BOOM_SPOTS.extend((random.uniform(-5.5, 1.0), y + random.uniform(-0.12, 0.12), h - 0.06) for _ in range(5))
# line A option (b) (reviews 015 / 016): one induct point per inductor. Active only when the spec carries
# "line_a": {"layout": "b", ...}; the collector's path in that spec already turns east at the new feed line.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import line_a_geom  # noqa: E402  (line A (b) geometry, shared with flow / stations)

LA, LA_MOUTHS, LA_INDUCT, LA_MERGES = line_a_geom.derive(SPEC.get("line_a"))
LINE_A_B = LA.get("layout") == "b"
_r2 = math.sqrt(0.5)
for cv in SPEC["machines"]["conveyors"]:
    if cv["kind"] == "telescopic":
        continue
    path, h = cv["path"], cv["height"]
    w = 0.6 if cv["kind"] == "telescopic" else 0.8
    if cv["id"] in ("merge", "induction_B"):  # the belt ends where its corners clear the carriers' band (+-0.425 m
        # round the loop line + 5 cm); drawn to the loop line, the carriers ran through its end. The parcel crosses
        # the last stretch onto its booked carrier (flow.py)
        (ax_, ay_), (bx_, by_) = path[-2], path[-1]
        th_ = math.atan2(by_ - ay_, bx_ - ax_)
        # (zone audit 1 Nov: and short of the loop's deck body, y >= south_y - 0.6 at 1.15-1.45 m - the belt's box, its
        # side guides and end legs stood 7-9 cm in it; the thin nose below runs on over the deck to the carriers)
        y_end = LOOP["south_y"] - 0.605 - (w / 2 + 0.05) * abs(math.cos(th_))
        u_ = (y_end - ay_) / (by_ - ay_)
        path = path[:-1] + [[ax_ + (bx_ - ax_) * u_, y_end]]
    hts = cv.get("heights")  # per-point heights (line B's ramp up to the deck)
    if cv["id"] == "induction" and path[-1][0] > 15:  # last stretch inclines up to the tunnel deck from x 15: its own
        # segment (the flat run was drawn as a belt only - no side guides, no legs: zone audit 1 Nov, 9.4 m floating)
        path = path[:-1] + [[15.0, path[-1][1]], path[-1]]
        hts = [h] * (len(path) - 1) + [DECK]
    for (ax, ay), (bx, by) in zip(path, path[1:]):
        za = zb = h
        if hts:
            ki = path.index([ax, ay])
            za, zb = hts[ki], hts[ki + 1]
        conv["belt"].append(mat_seg((ax, ay, za - 0.06), (bx, by, zb - 0.06), w, 0.12))
        k_seg = path.index([bx, by]) - 1 if [bx, by] in path else 0
        ln_ = math.hypot(bx - ax, by - ay) or 1
        dx, dy = (bx - ax) / ln_, (by - ay) / ln_
        turn_in = turn_out = 0.0  # corners: the inner side frame stops short of the other belt (it crossed it)
        straight_in = False  # (a straight continuation - induction's flat run into its incline - is no corner)
        if k_seg + 2 < len(path):  # a corner at this segment's end
            cx_, cy_ = path[k_seg + 2][0] - bx, path[k_seg + 2][1] - by
            if abs(dx * cy_ - dy * cx_) > 1e-6:
                turn_out = 1.0 if dx * cy_ - dy * cx_ > 0 else -1.0
        if k_seg > 0:  # a corner at this segment's start
            px_, py_ = ax - path[k_seg - 1][0], ay - path[k_seg - 1][1]
            if abs(px_ * dy - py_ * dx) > 1e-6:
                turn_in = 1.0 if px_ * dy - py_ * dx > 0 else -1.0
            else:
                straight_in = True
        for s in (-1, 1):  # side frames (s = +1: left of travel)
            nx, ny = -(by - ay), (bx - ax)
            ln = math.hypot(nx, ny) or 1
            ox, oy = s * nx / ln * (w / 2 + 0.03), s * ny / ln * (w / 2 + 0.03)
            cut = w / 2 + 0.05
            a0 = cut if turn_in == s else 0.0  # the inner side of a left turn is the left frame (s = +1)
            b0 = cut if turn_out == s else 0.0
            spans = [(a0, ln_ - b0)]
            if LINE_A_B and cv["id"] == "collector" and s == -1 and abs(dy) < 0.1:  # line A (b): table mouths (south)
                # + where D02's stub comes in from the south at the feed's corner (a closed frame there: collision check)
                t_ = (5.0 - ax) / dx if dx else -1  # (0.5: a carton sliding across from the stub to the feed's middle
                # caught the frame's start at 0.38, hub run 4)
                spans = [(u0, u1) for (lo, hi) in spans
                         for (u0, u1) in ((lo, min(hi, t_ - 0.5)), (max(lo, t_ + 0.5), hi)) if u1 - u0 > 0.05]
                for mx_ in LA_MOUTHS:
                    t_ = (mx_ - ax) / dx if dx else -1
                    spans = [(u0, u1) for (lo, hi) in spans
                             for (u0, u1) in ((lo, min(hi, t_ - LA["table_w"] / 2 - 0.05)),
                                              (max(lo, t_ + LA["table_w"] / 2 + 0.05), hi)) if u1 - u0 > 0.05]
            if LINE_A_B and cv["id"] == "induction" and s == 1 and abs(dy) < 0.1:  # line A (b): induct belts merge (north)
                for mx_ in LA_MERGES:
                    t_ = (mx_ - ax) / dx if dx else -1
                    # (+0.80 downstream: the induct belt's 45-degree nose reaches merge +0.55 at belt A's edge, and a
                    # carton coming across still overhangs A's edge for ~0.2 m while it squares up - S2 gate, 1 Nov:
                    # cartons 1-4 cm into the guide at merge +0.56..+0.73)
                    spans = [(u0, u1) for (lo, hi) in spans
                             for (u0, u1) in ((lo, min(hi, t_ - 0.42)), (max(lo, t_ + 0.80), hi)) if u1 - u0 > 0.05]
            # openings where the booms feed in (west side). D02's stub too: in line A (b) its boom hands over there, and
            # a closed frame put every D02 parcel 4 cm into it (hub run 3, CAM_01)
            if cv["id"] in ("collector", "d02_stub") and ox < 0 and abs(dx) < 0.1:
                for by_ in BOOM_YS:
                    t_ = (by_ - ay) / dy if dy else -1
                    if 0 < t_ < ln_:
                        spans = [(u0, u1) for (lo, hi) in spans
                                 for (u0, u1) in ((lo, min(hi, t_ - 0.38)), (max(lo, t_ + 0.38), hi)) if u1 - u0 > 0.05]
            for u0, u1 in spans:
                p0 = (ax + dx * u0 + ox, ay + dy * u0 + oy, za + (zb - za) * u0 / ln_ - 0.05)
                p1 = (ax + dx * u1 + ox, ay + dy * u1 + oy, za + (zb - za) * u1 / ln_ - 0.05)
                conv["frame"].append(mat_seg(p0, p1, 0.04, 0.18))
        n = max(1, int(math.hypot(bx - ax, by - ay) / 2.0))
        for k in range(n + 1):
            t = k / n
            px, py, pz = ax + (bx - ax) * t, ay + (by - ay) * t, za + (zb - za) * t
            if px < 0.3 and cv["kind"] == "telescopic":
                continue  # the boom outside the wall hangs free, no legs
            if k == 0 and straight_in:
                continue  # (the run before it has legs here)
            if cv["id"] in ("merge", "induction_B") and py + w / 2 > LOOP["south_y"] - 0.6:
                continue  # (it would stand in the loop's deck body: the belt's end is carried by the sorter frame)
            conv["steel"].append(mat_aabb(px - 0.04, py - w / 2, 0, px + 0.04, py - w / 2 + 0.06, pz - 0.12))
            conv["steel"].append(mat_aabb(px - 0.04, py + w / 2 - 0.06, 0, px + 0.04, py + w / 2, pz - 0.12))
    if cv["id"] == "collector":  # the accumulation (feed) run ends at a steel end plate: parcels queue against it
        ex, ey = path[-1]
        conv["steel"].append(mat_aabb(ex + 0.02, ey - w / 2 - 0.03, h - 0.08, ex + 0.06, ey + w / 2 + 0.03, h + 0.14))
    # corners (zone audit 1 Nov: two square-ended boxes left an open wedge on the outside of every bend - 40 x 40 cm
    # of floor at the collector's turn onto the feed, right where D02's stub hands over): each side's belt runs on to
    # the mitre line, 2 / 4 mm under the top (no coplanar faces), and a guard closes the outside of the bend
    hz = hts or [h] * len(path)
    for i in range(1, len(path) - 1):
        c = Vector((*path[i], 0.0))
        d1 = (c - Vector((*path[i - 1], 0.0))).normalized()
        d2 = (Vector((*path[i + 1], 0.0)) - c).normalized()
        th = math.acos(max(-1.0, min(1.0, d1.dot(d2))))
        if th < math.radians(2):
            continue
        zc, e = hz[i], (w / 2) * math.tan(th / 2) - 0.003
        sl1, sl2 = hz[i] != hz[i - 1], hz[i + 1] != hz[i]  # a ramp: start at the corner (its top rises past it)
        conv["belt"].append(mat_seg((*(c - d1 * (0 if sl1 else 0.01)).xy, zc - 0.052), (*(c + d1 * e).xy, zc - 0.052),
                                    w - 0.004, 0.1))
        conv["belt"].append(mat_seg((*(c - d2 * e).xy, zc - 0.054), (*(c + d2 * (0 if sl2 else 0.01)).xy, zc - 0.054),
                                    w - 0.004, 0.1))
        if cv["id"] == "collector":  # (its outside is where the stub comes in: closed by the stub's guard below)
            continue
        out_ = -1.0 if d1.x * d2.y - d1.y * d2.x > 0 else 1.0  # left turn: the outside is the right
        f_off = w / 2 + 0.03  # each outside guard runs on along its own line to where they meet (a mitre); 2 mm gaps
        # at the guards' ends, the second piece 2 mm inside the first's top / bottom (no coplanar faces)
        p1 = c + Vector((-d1.y, d1.x, 0)) * out_ * f_off
        p2 = c + Vector((-d2.y, d2.x, 0)) * out_ * f_off
        mf = p1 + d1 * f_off * math.tan(th / 2)
        conv["frame"].append(mat_seg((*(p1 + d1 * 0.002).xy, zc - 0.05), (*mf.xy, zc - 0.05), 0.04, 0.18))
        conv["frame"].append(mat_seg((*mf.xy, zc - 0.05), (*(p2 - d2 * 0.002).xy, zc - 0.05), 0.04, 0.176))
    if cv["id"] in ("merge", "induction_B"):  # nose on to 3 cm off the carriers' band, its end square to the loop (as
        # a sorter's induction belt meets the carriers); 4 cm thick, over the deck rails (top 1.45). Zone audit 1 Nov:
        # 0.4 m of floor between the belt's end and the carriers
        ex, ey = path[-1]
        dd = Vector((bx_ - ax_, by_ - ay_)).normalized()
        y_n0, y_n1 = ey - (w / 2) * abs(dd.x) - 0.01, LOOP["south_y"] - 0.425 - 0.03
        y_nc, hn = (y_n0 + y_n1) / 2, hz[-1]
        ln_n = (y_n1 - y_n0) / dd.y
        conv["belt"].append(Matrix(((dd.x * ln_n, -(w - 0.004) / abs(dd.y), 0, ex + dd.x / dd.y * (y_nc - ey)),  # (-: a
                                    # positive determinant - northbound, +x made it a mirror box, faces inward)
                                    (dd.y * ln_n, 0, 0, y_nc), (0, 0, 0.04, hn - 0.022), (0, 0, 0, 1))))
    if cv["id"] == "d02_stub":  # on to 5 mm off the feed's belt (it stopped 5 cm short), and its west guard runs on
        # round the outside of the collector's turn onto the feed (2 mm off the collector's guard)
        (sx_, sy_), (ex, ey) = path[0], path[-1]
        conv["belt"].append(mat_aabb(ex - w / 2 + 0.002, ey - 0.01, h - 0.102, ex + w / 2 - 0.002, LA["feed_y"] - LA["feed_half"] - 0.005,
                                     h - 0.002))
        conv["frame"].append(mat_aabb(ex - w / 2 - 0.05, ey + 0.002, h - 0.14, ex - w / 2 - 0.01, LA["feed_y"] - 0.002, h + 0.04))
if LINE_A_B:
    for (sx, sy), (ex, ey) in LA_INDUCT:  # induct belts (0.5 m wide), both ends cut parallel to belt A's edge
        wi = LA["induct_w"]
        # sheared boxes (parallelograms): along the belt (45 deg) x along x, so the far end meets belt A's frame flush
        # and the near end squares up to the worker (a square end poked 18 cm into belt A)
        dvx, dvy = ex - sx, ey - sy
        kx = wi / abs(dvy / math.hypot(dvx, dvy))  # x-length of a cut with the perpendicular width wi

        def slab(cx, cy, cz, ln_x, ht, ex_=1.0):
            m = Matrix(((dvx * ex_, ln_x, 0, cx), (dvy * ex_, 0, 0, cy), (0, 0, ht, cz), (0, 0, 0, 1)))
            return m
        cxm, cym = (sx + ex) / 2, (sy + ey) / 2
        conv["belt"].append(slab(cxm, cym, 0.94, kx, 0.12))
        # nose: on from the end (flush with belt A's frame line, y_end) to 5 mm off belt A's belt, 2 mm under the top
        # (zone audit 1 Nov: the carton crossed a 5 cm gap over the floor onto A)
        y_n0, y_n1 = ey + 0.01, LA["belt_a_y"] + LA["belt_a_half"] + 0.005
        f_n = (y_n1 - y_n0) / dvy
        y_nc = (y_n0 + y_n1) / 2
        conv["belt"].append(Matrix(((dvx * f_n, kx - 0.004 / abs(dvy / math.hypot(dvx, dvy)), 0, ex + dvx / dvy * (y_nc - ey)),
                                    (dvy * f_n, 0, 0, y_nc), (0, 0, 0.1, 0.948), (0, 0, 0, 1))))
        ln_i = math.hypot(dvx, dvy)
        cut_e = 0.12  # the side guides stop 12 cm short of belt A: a carton turning onto A at the merge caught their
        # ends (1-5 cm, hub run 4)
        cxf, cyf = cxm - dvx / ln_i * (cut_e / 2 - 0.01), cym - dvy / ln_i * (cut_e / 2 - 0.01)
        for sg in (-1, 1):
            off = sg * (kx / 2 + 0.03 / abs(dvy / ln_i))
            conv["frame"].append(slab(cxf + off, cyf, 0.95, 0.04 / abs(dvy / ln_i), 0.18, (ln_i - cut_e) / ln_i))
            for u in (0.15, 0.85):
                lx, ly = sx + dvx * u + off * 0.8, sy + dvy * u
                conv["steel"].append(mat_aabb(lx - 0.03, ly - 0.03, 0, lx + 0.03, ly + 0.03, 0.88))
    t_hi, t_lo = LA["table_top"]
    y0t, y1t = LA["op_y"] - 0.10, LA["op_y"] - 0.10 + LA["table_len"]  # near end (stop) .. head (at the feed)
    for tx in LA_MOUTHS:  # gravity roller tables falling towards the operator, guides 3 cm above the rollers
        tw = LA["table_w"]
        for j in range(9):
            u = j / 8
            y = y1t + (y0t - y1t) * u
            z = t_hi + (t_lo - t_hi) * u
            conv["steel"].append(mat_aabb(tx - tw / 2, y - 0.025, z - 0.05, tx + tw / 2, y + 0.025, z))
        # head roller under the feed's edge (zone audit 1 Nov: 4.5 cm open between the feed's belt and the top roller)
        conv["steel"].append(mat_aabb(tx - tw / 2, y1t + 0.027, t_hi - 0.05, tx + tw / 2,
                                      LA["feed_y"] - LA["feed_half"] - 0.005, t_hi))
        ym = (y0t + y1t) / 2
        for sg in (-1, 1):
            conv["frame"].append(mat_aabb(tx + sg * tw / 2 - 0.02, y0t - 0.03, 0.80, tx + sg * tw / 2 + 0.02, ym,
                                          t_lo + 0.045))
            conv["frame"].append(mat_aabb(tx + sg * tw / 2 - 0.02, ym, 0.80, tx + sg * tw / 2 + 0.02, y1t, t_hi + 0.03))
            for yy in (y0t + 0.05, y1t - 0.08):
                conv["steel"].append(mat_aabb(tx + sg * 0.2 - 0.02, yy - 0.02, 0, tx + sg * 0.2 + 0.02, yy + 0.02, 0.8))
        conv["frame"].append(mat_aabb(tx - tw / 2, y0t - 0.06, 0.85, tx + tw / 2, y0t - 0.03, 0.92))  # low end stop
boxes("conveyors", conv, C["Machines"])
if LINE_A_B:  # diverter paddles at the table mouths (yellow; flow.py swings them)
    feed_y = next(cv for cv in SPEC["machines"]["conveyors"] if cv["id"] == "collector")["path"][-1][1]
    boxes("line_a_diverters", {"yellow": [mat_aabb(tx + LA["table_w"] / 2 + 0.05 - 0.64, feed_y + 0.37 - 0.0125, 1.01,
                                                   tx + LA["table_w"] / 2 + 0.05, feed_y + 0.37 + 0.0125, 1.11)
                                          for tx in LA_MOUTHS]}, C["Machines"])

# scan tunnel (DWS): open front/back box, light bars, display; weigh platform before it
# (B2 pre-review #5: it read as a plain white box) painted body, red-orange LED bars and scanner strips glowing
# inside, scanner heads on the roof, yellow guard posts at the corners; the DWS screen on its stand beside it
tun = {"frame": [mat_aabb(19.5, 8.6, DECK + 1.3, 22.0, 10.4, DECK + 1.4),
                 mat_aabb(19.5, 8.6, DECK - 0.4, 22.0, 8.7, DECK + 1.4),
                 mat_aabb(19.5, 10.3, DECK - 0.4, 22.0, 10.4, DECK + 1.4),
                 mat_aabb(22.1, 10.5, 0, 22.7, 11.1, 1.8)],
       "lightbar": [mat_aabb(19.7 + 0.5 * k, 8.75, DECK + 1.2, 19.9 + 0.5 * k, 10.25, DECK + 1.28) for k in range(4)],
       "scan_led": [mat_aabb(19.85 + 0.7 * k, y0, DECK + 0.1, 19.9 + 0.7 * k, y1, DECK + 1.15)
                    for k in range(3) for (y0, y1) in ((8.7, 8.72), (10.28, 10.3))],
       "black": [mat_aabb(19.9 + 0.75 * k, 9.2, DECK + 1.4, 20.25 + 0.75 * k, 9.8, DECK + 1.58) for k in range(3)]
       + [mat_aabb(x - 0.06, y - 0.06, 1.0, x + 0.06, y + 0.06, 1.12) for x in (19.35, 22.15) for y in (8.45, 10.55)],
       "yellow": [mat_aabb(17.52, 9.07, DECK - 0.08, 18.98, 9.93, DECK - 0.04)],  # 2 mm in from the belt's
       # start and edges (flush, they z-fought: mesh_hygiene)
       "screen": [mat_aabb(22.15, 10.49, 1.3, 22.65, 10.5, 1.7)]}
tun["yellow"] += [mat_aabb(x - 0.05, y - 0.05, 0.0, x + 0.05, y + 0.05, 1.0) for x in (19.35, 22.15)
                  for y in (8.45, 10.55)]  # guard posts at the corners, black caps above
boxes("scan_tunnel_DWS-01", tun, C["Machines"])
# DWS arch B on induction line B's ramp (SP-TUNNEL-B): two posts and a head beam square to the belt, red-orange LED
# strips inside, a scanner head on top
_lb = next(cv for cv in SPEC["machines"]["conveyors"] if cv["id"] == "induction_B")
_pa, _pb = Vector((*_lb["path"][1], _lb["heights"][1])), Vector((*_lb["path"][2], _lb["heights"][2]))
_pc = _pa.lerp(_pb, 0.75)  # near the top of the ramp
_d = (_pb - _pa).normalized()
_n = Vector((-_d.y, _d.x, 0.0)).normalized()
arch = {"frame": [], "scan_led": [], "black": []}
for _sg in (-1, 1):
    _base = _pc + _n * _sg * 0.5
    arch["frame"].append(mat_seg(_base - Vector((0, 0, 0.1)), _base + Vector((0, 0, 1.0)), 0.12, 0.12))
    arch["scan_led"].append(mat_seg(_pc + _n * _sg * 0.43 + Vector((0, 0, 0.1)), _pc + _n * _sg * 0.43 + Vector((0, 0, 0.9)),
                                    0.02, 0.05))
arch["frame"].append(mat_seg(_pc - _n * 0.56 + Vector((0, 0, 1.0)), _pc + _n * 0.56 + Vector((0, 0, 1.0)), 0.16, 0.12))
arch["black"].append(mat_seg(_pc - _n * 0.18 + Vector((0, 0, 1.12)), _pc + _n * 0.18 + Vector((0, 0, 1.12)), 0.2, 0.12))
boxes("scan_arch_DWS-B", arch, C["Machines"])
sign("tunnel_plate", "DWS-01", (20.75, 8.58, DECK + 1.0), "-Y", 0.18)

# ------------------------------------------------------------------------------------------------ cross-belt loop
def loop_samples(step=0.25):
    wcx, ecx, sy, ny, cy, r = (LOOP[k] for k in ("west_cx", "east_cx", "south_y", "north_y", "cy", "radius"))
    pts, n, m = [], int((ecx - wcx) / step), int(math.pi * r / step)
    pts += [(wcx + i * step, sy, 0.0) for i in range(n)]
    pts += [(ecx + r * math.cos(-math.pi / 2 + math.pi * i / m), cy + r * math.sin(-math.pi / 2 + math.pi * i / m),
             math.pi * i / m) for i in range(m)]
    pts += [(ecx - i * step, ny, math.pi) for i in range(n)]
    pts += [(wcx + r * math.cos(math.pi / 2 + math.pi * i / m), cy + r * math.sin(math.pi / 2 + math.pi * i / m),
             math.pi + math.pi * i / m) for i in range(m)]
    return pts


LS = loop_samples()
CHUTES = SPEC["machines"]["chutes"]
def merge_gaps(y_line, clear=0.3):
    """x ranges where a merge belt (main merge, line B) crosses the horizontal line y = y_line: the outer guard rail
    and the machine fence are open there (parcels on the merge belts ran through the rail: collision check)."""
    gaps = []
    for cv in SPEC["machines"]["conveyors"]:
        if cv["id"] not in ("merge", "induction_B"):
            continue
        for (ax, ay), (bx, by) in zip(cv["path"], cv["path"][1:]):
            if (ay - y_line) * (by - y_line) > 0 or ay == by:
                continue
            u = (y_line - ay) / (by - ay)
            xc = ax + (bx - ax) * u
            half = 0.4 / abs(math.sin(math.atan2(by - ay, bx - ax))) + clear  # belt half-width along the line
            gaps.append((xc - half, xc + half))
    return gaps


RAIL_GAPS = merge_gaps(LOOP["south_y"] - 0.64)
loop_items = {"frame": [], "steel": [], "yellow": []}
for i, (x, y, t) in enumerate(LS):
    x2, y2, _ = LS[(i + 1) % len(LS)]
    nx, ny_ = -math.sin(t), math.cos(t)  # inward normal (loop runs counter-clockwise)
    loop_items["frame"].append(mat_seg((x, y, DECK - 0.2), (x2, y2, DECK - 0.2), 1.2, 0.3))  # deck body
    for side in (1, -1):  # guard rails; the outer rail is open at every chute mouth on the north straight
        ox, oy = x + side * nx * 0.64, y + side * ny_ * 0.64
        if side == -1 and abs(t - math.pi) < 1e-6 and any(abs(x - c["x"]) < 0.55 for c in CHUTES):
            continue
        if side == -1 and abs(t) < 1e-6 and any(min(x, x2) < g1 and max(x, x2) > g0 for g0, g1 in RAIL_GAPS):
            continue  # open where a merge belt comes in
        loop_items["yellow"].append(mat_seg((ox, oy, DECK + 0.2), (x2 + side * nx * 0.64, y2 + side * ny_ * 0.64,
                                                                   DECK + 0.2), 0.04, 0.4))
    if i % 12 == 0:
        for side in (1, -1):
            px, py = x + side * nx * 0.5, y + side * ny_ * 0.5
            loop_items["steel"].append(mat_aabb(px - 0.06, py - 0.06, 0, px + 0.06, py + 0.06, DECK - 0.35))
boxes("loop_deck_rails", loop_items, C["Machines"])


# machine guarding round the loop's walkable sides (QA review 001 #5; reference dpd_t068 / t075): 2.0 m galvanised
# mesh panels between 60 mm yellow posts, 0.5 m out from the deck. North side stays open (chutes + bagging aisle);
# the merge belt passes through a gap at the south-west; the XO-1 stair passes over the fence (it is ~3 m up there).
# A yellow-framed access gate (padlocked) on the south side. E-stop boxes every ~10 m on the posts, 3 stack lights.
def fence_runs():
    sy, ny, wcx, ecx, r = (LOOP[k] for k in ("south_y", "north_y", "west_cx", "east_cx", "radius"))
    off = r + 0.62 + 0.5  # loop centreline radius + half deck + clearance
    cy = (sy + ny) / 2
    runs, x0 = [], 30.4  # south: from just east of the merge belt, open where line B's ramp comes through
    for g0, g1 in sorted(merge_gaps(sy - 1.12, 0.15)):
        if g0 > x0:
            runs.append([(x0, sy - 1.12), (g0, sy - 1.12)])
            x0 = g1
    runs.append([(x0, sy - 1.12), (ecx, sy - 1.12)])
    east = [(ecx + off * math.cos(a), cy + off * math.sin(a)) for a in [math.radians(d) for d in range(-90, 91, 15)]]
    runs.append(east[:-1] + [(ecx + 0.6, ny + 1.0)])  # round the east curve up to the chute row
    west = [(wcx + off * math.cos(a), cy + off * math.sin(a)) for a in [math.radians(d) for d in range(90, 271, 15)]]
    runs.append([(wcx - 0.6, ny + 1.0)] + west[1:-2])  # west curve, stops clear of the merge belt (240 deg)
    return runs


fence = {"steel": [], "yellow": [], "black": [], "red": []}
fence_bm = bmesh.new()
post_pts = []
for run in fence_runs():
    for (ax, ay), (bx, by) in zip(run, run[1:]):
        seg_len = math.hypot(bx - ax, by - ay)
        n = max(1, int(round(seg_len / 2.0)))
        for k in range(n):
            x0, y0 = ax + (bx - ax) * k / n, ay + (by - ay) * k / n
            x1, y1 = ax + (bx - ax) * (k + 1) / n, ay + (by - ay) * (k + 1) / n
            post_pts.append((x0, y0))
            gate = abs(x0 - 36.0) < 1.0 and abs(y0 - (LOOP["south_y"] - 1.12)) < 0.01
            segs = [((x0, y0, 0.05), (x1, y1, 0.05), 0.012), ((x0, y0, 2.0), (x1, y1, 2.0), 0.012),
                    ((x0, y0, 1.0), (x1, y1, 1.0), 0.008)]  # frame rails
            m = int(math.hypot(x1 - x0, y1 - y0) / 0.1)
            segs += [((x0 + (x1 - x0) * j / m, y0 + (y1 - y0) * j / m, 0.05),
                      (x0 + (x1 - x0) * j / m, y0 + (y1 - y0) * j / m, 2.0), 0.0018) for j in range(1, m)]
            segs += [((x0, y0, z), (x1, y1, z), 0.0018) for z in [0.05 + 0.1 * j for j in range(1, 20)]]
            tubes_into(fence_bm, segs, 0, sides=4)
            if gate:  # access gate: yellow frame inside the panel (hinge + latch stiles, top rail) + padlock
                ga, gb = min(x0, x1) + 0.08, max(x0, x1) - 0.08
                fence["yellow"] += [mat_aabb(ga - 0.02, y0 - 0.02, 0.08, ga + 0.02, y0 + 0.02, 1.95),
                                    mat_aabb(gb - 0.02, y0 - 0.02, 0.08, gb + 0.02, y0 + 0.02, 1.95),
                                    mat_aabb(ga, y0 - 0.02, 1.91, gb, y0 + 0.02, 1.95)]
                fence["black"].append(mat_aabb(gb - 0.06, y0 - 0.06, 1.0, gb - 0.02, y0 - 0.02, 1.08))
    post_pts.append(run[-1])
for i, (px, py) in enumerate(post_pts):
    fence["yellow"].append(mat_aabb(px - 0.03, py - 0.03, 0.0, px + 0.03, py + 0.03, 2.05))
    if i % 5 == 2:  # e-stop box (yellow) with a red mushroom head, on the aisle side of the post
        fence["yellow"].append(mat_aabb(px - 0.06, py - 0.1, 1.05, px + 0.06, py - 0.03, 1.2))
        fence["red"].append(mat_aabb(px - 0.025, py - 0.125, 1.11, px + 0.025, py - 0.1, 1.15))
me = bpy.data.meshes.new("loop_fence_mesh")
fence_bm.to_mesh(me)
fence_bm.free()
me.materials.append(M["steel"])
fob = bpy.data.objects.new("loop_fence_mesh", me)
C["Machines"].objects.link(fob)
boxes("loop_fence_posts", fence, C["Machines"])
# stack lights on the loop (green lit = running): at the merge, at XO-1, on the east curve
for k, (lx, ly) in enumerate(((30.6, LOOP["south_y"] - 1.12), (40.6, LOOP["south_y"] - 1.12),
                              (LOOP["east_cx"] + LOOP["radius"] + 1.12, (LOOP["south_y"] + LOOP["north_y"]) / 2))):
    boxes(f"loop_stacklight_{k}", {"steel": [mat_aabb(lx - 0.015, ly - 0.015, 2.05, lx + 0.015, ly + 0.015, 2.3)],
                                   "lamp_green": [mat_aabb(lx - 0.04, ly - 0.04, 2.3, lx + 0.04, ly + 0.04, 2.38)],
                                   "lamp_off": [mat_aabb(lx - 0.04, ly - 0.04, 2.38, lx + 0.04, ly + 0.04, 2.54)]},
          C["Machines"])

# carriers: 850 x 440 mm belts at 700 mm pitch; the 260 mm between them is the cover plate (deck top)
carrier_src = boxes("carrier_src", {"carrier": [mat_aabb(-0.22, -0.425, -0.063, 0.22, 0.425, -0.023)],
                                    "belt": [mat_aabb(-0.2, -0.41, -0.023, 0.2, 0.41, -0.003)]}, C["Machines"])
# (carrier tops 3 mm under the deck line: level with the merge belts' end they z-fought - mesh_hygiene)
seglen = [math.dist(LS[i][:2], LS[(i + 1) % len(LS)][:2]) for i in range(len(LS))]
total = sum(seglen)
n_car = round(total / 0.7)
acc, idx = 0.0, 0
LOOP_SPOTS = []
for k in range(n_car):
    s = k * total / n_car
    while acc + seglen[idx] < s:
        acc += seglen[idx]
        idx += 1
    x, y, t = LS[idx]
    ob = carrier_src if k == 0 else bpy.data.objects.new(f"carrier_{k:03d}", carrier_src.data)
    if k:
        C["Machines"].objects.link(ob)
    ob.matrix_world = Matrix.Translation((x, y, DECK)) @ Euler((0, 0, t)).to_matrix().to_4x4()
    if random.random() < 0.45:
        LOOP_SPOTS.append((x, y, DECK))
carrier_src.name = "carrier_000"

# chutes + bag frames + sacks + destination boards
SORT = SPEC["sort_plans"][0]["chutes"]
ch = {"steel": [], "red": []}
FILL = ["full", "half", "empty", "half", "full", "half", "empty", "half", "full", "half", "empty", "half"]
CHUTE_SPOTS, BAG_SPOTS = [], []
frame_bm = bmesh.new()
clips = []
for c in CHUTES:
    reject = c["id"] == "REJECT"
    mt = "red" if reject else "steel"
    x, lip = c["x"], c["lip_z"]
    ch[mt].append(mat_seg((x, c["mouth_y"], DECK - 0.05), (x, c["end_y"], lip), 1.0, 0.03))
    for sgn in (-1, 1):
        ch[mt].append(mat_seg((x + sgn * 0.5, c["mouth_y"], DECK + 0.1), (x + sgn * 0.5, c["end_y"], lip + 0.15),
                              0.03, 0.3))
        ch["steel"].append(mat_aabb(x + sgn * 0.45 - 0.03, c["mouth_y"] + 0.15, 0, x + sgn * 0.45 + 0.03,
                                    c["mouth_y"] + 0.21, DECK - 0.1))  # hanger legs under the mouth
    # (no static parcels resting on the chutes: on an open chute a parcel slides on into the bag - they only pile
    # up on a chute closed for a full bag - and the sorted parcels slid through them: collision check)
    random.choice([0, 1, 2, 3, 4])  # keeps the random stream (and every later placement) as it was
    for _ in range(0):
        CHUTE_SPOTS.append((x, c["mouth_y"], DECK))
    if reject:  # blue rework bin under the reject lip
        y0, y1 = c["bin"]["y"]
        bw, _, bh = c["bin"]["size_m"]
        mesh_obj("reject_bin", [(mat_aabb(x - bw / 2, y0, 0, x + bw / 2, y1, bh), 0)], ["blue"], C["Machines"],
                 kind="openbox")
        CHUTE_SPOTS += [(x + random.uniform(-0.25, 0.25), random.uniform(y0 + 0.15, y1 - 0.15), bh - 0.25)
                        for _ in range(4)]
    else:  # open tube frame: 4 legs, rim at 0.9 m, low stretchers; sack clipped to the rim
        by = c["bag_frame_y"]
        fw, fd, rim = 1.0, 0.8, 0.9
        xa, xb, ya, yb = x - fw / 2, x + fw / 2, by, by + fd
        segs = [((px, py, 0), (px, py, rim), 0.022) for px in (xa, xb) for py in (ya, yb)]
        segs += [((xa, ya, rim), (xb, ya, rim), 0.02), ((xa, yb, rim), (xb, yb, rim), 0.02),
                 ((xa, ya, rim), (xa, yb, rim), 0.02), ((xb, ya, rim), (xb, yb, rim), 0.02),
                 ((xa, ya, 0.1), (xa, yb, 0.1), 0.016), ((xb, ya, 0.1), (xb, yb, 0.1), 0.016),
                 ((xa, yb, 0.1), (xb, yb, 0.1), 0.016)]
        tubes_into(frame_bm, segs, 0)
        # spring clips: thin plates OUTSIDE the sack's lip folded over the rim tube (solid cubes on the tube ran
        # through the lip: owner rule - nothing passes through anything)
        for px, py, ox, oy in ((x, ya, 0, -1), (x, yb, 0, 1), (xa, by + fd / 2, -1, 0), (xb, by + fd / 2, 1, 0)):
            c0, c1 = 0.034, 0.046  # out from the tube centre: tube 2 cm + lip ~1.2 cm
            if ox:
                clips.append(mat_aabb(px + ox * c0 if ox > 0 else px - c1, py - 0.03, rim - 0.05,
                                      px + c1 if ox > 0 else px - c0, py + 0.03, rim + 0.035))
            else:
                clips.append(mat_aabb(px - 0.03, py + oy * c0 if oy > 0 else py - c1, rim - 0.05,
                                      px + 0.03, py + c1 if oy > 0 else py - c0, rim + 0.035))
        k = int(c["id"][1:]) - 1
        kind = FILL[k]
        mat = ["sack", "sack", "sack_blue", "sack", "sack_grey", "sack", "sack_blue", "sack", "sack", "sack_grey",
               "sack", "sack_blue"][k]
        me = shared_mesh(f"sack_{kind}_{k % 3}_{mat}", lambda bm, kd=kind, sd=k % 3: loft_into(bm, sack_rings(kd, sd), 0),
                         [mat])
        place(me, f"sack_{c['id']}", (x, by + fd / 2, 0.0))
        if kind != "empty":  # printed band on the aisle side: brand + destination
            text(f"sack_print_{c['id']}", f"CONTOH EXPRESS\n{SORT[c['id']].upper()}", (x, by + fd / 2 + SACK_B * 1.16, 0.42),
                 (90, 0, 180), 0.034, "brand", C["Clutter"], extrude=0.0, font=BOARD_FONT)
        if c["id"] == "C03":  # an empty folded sack hanging ready on a hook at the frame side
            boxes("sack_spare_C03", {"sack": [mat_aabb(xb + 0.03, by + 0.12, 0.25, xb + 0.045, by + 0.62, 0.86)],
                                     "steel": [mat_aabb(xb, by + 0.35, 0.86, xb + 0.06, by + 0.39, 0.9)]}, C["Clutter"])
        if kind != "empty":  # parcels visible in the mouth
            zf = 0.42 if kind == "half" else 0.65  # (0.8 left no room under the chute lip for the next parcel: it
            # rested against the chute, collision check)
            BAG_SPOTS += [(x + random.uniform(-0.25, 0.25), by + fd / 2 + random.uniform(-0.18, 0.18), zf)
                          for _ in range(random.randint(3, 5))]
    label = "REJECT / NO READ" if reject else f"{c['id']}  {SORT[c['id']].upper()}"
    sign(f"chute_board_{c['id']}", label, (x, c["mouth_y"] + 0.4, 3.2), "-Y", 0.075 if not reject else 0.09,
         board=(1.3, 0.35), ink="ink_red" if reject else "ink")
boxes("chutes", ch, C["Machines"])
frame_me = bpy.data.meshes.new("bag_frames")
frame_bm.to_mesh(frame_me)
frame_bm.free()
frame_me.materials.append(M["steel"])
C["Machines"].objects.link(bpy.data.objects.new("bag_frames", frame_me))
boxes("bag_frame_clips", {"black": clips}, C["Machines"])
TIED = shared_mesh("sack_tied", lambda bm: loft_into(bm, tied_sack_rings(4), 0, cap_bottom=True, cap_top=True),
                   ["sack"])
TIED_BLUE = shared_mesh("sack_tied_blue", lambda bm: loft_into(bm, tied_sack_rings(9), 0, cap_bottom=True,
                                                                  cap_top=True), ["sack_blue"])
c05 = next(c for c in CHUTES if c["id"] == "C05")  # one tied + tagged sack waiting in the bagging aisle
place(TIED, "sack_tied_waiting_C05", (c05["x"] + 0.1, c05["bag_frame_y"] + 1.25, 0.0), 0.3)
boxes("sack_tag_C05", {"label": [mat_aabb(c05["x"] + 0.12, c05["bag_frame_y"] + 1.24, 0.66, c05["x"] + 0.2,
                                          c05["bag_frame_y"] + 1.25, 0.76)]}, C["Clutter"])
# yellow pedestrian barrier between the break table (stations.BREAK_TABLE, 4.55 / 31.35) and the dock lane / the
# collector's tail (review 006b): 1 m posts every ~1.3 m, rails at 0.5 and 1.0 m
_bar = []
_bx0, _bx1, _by = 3.2, 6.0, 30.25
for _k in range(4):
    _x = _bx0 + (_bx1 - _bx0) * _k / 3
    _bar.append(mat_aabb(_x - 0.03, _by - 0.03, 0.0, _x + 0.03, _by + 0.03, 1.02))
for _z in (0.5, 0.98):
    _bar.append(mat_aabb(_bx0, _by - 0.02, _z - 0.02, _bx1, _by + 0.02, _z + 0.02))
boxes("break_barrier", {"yellow": _bar}, C["Clutter"])

# ------------------------------------------------------------------------------------------------ fixtures
FX = SPEC["fixtures"]
fx = {"frame": [], "wood": [], "rack_blue": [], "orange": [], "sack": [], "white": [], "screen": [], "black": []}
for b in FX["benches"]:
    x0, y0, x1, y1 = b["rect_m"]
    fx["wood"].append(mat_aabb(x0, y0, b["height_m"] - 0.05, x1, y1, b["height_m"]))
    for lx, ly in ((x0 + 0.1, y0 + 0.1), (x1 - 0.1, y0 + 0.1), (x0 + 0.1, y1 - 0.1), (x1 - 0.1, y1 - 0.1)):
        fx["frame"].append(mat_aabb(lx - 0.03, ly - 0.03, 0, lx + 0.03, ly + 0.03, b["height_m"] - 0.05))
fx["black"].append(mat_aabb(25.0, 21.6, 0.9, 25.35, 21.9, 1.12))  # label printer on the exception bench
for r in FX["racks"]:  # pallet racking: blue uprights, orange beams, shelves of folded sacks
    x0, y0, x1, y1 = r["rect_m"]
    along_x = (x1 - x0) > (y1 - y0)
    n = max(1, int(((x1 - x0) if along_x else (y1 - y0)) / 2.7))
    for k in range(n + 1):
        t = k / n
        px, py = (x0 + (x1 - x0) * t, y0) if along_x else (x0, y0 + (y1 - y0) * t)
        for e in (0, 1):
            ux, uy = (px, py + e * (y1 - y0)) if along_x else (px + e * (x1 - x0), py)
            fx["rack_blue"].append(mat_aabb(ux - 0.05, uy - 0.05, 0, ux + 0.05, uy + 0.05, r["height_m"]))
    # loaded from the floor up and packed (these racks wall the BLIND_NW corner: a camera must not see through
    # them - raycast check 30 Oct: CAM_01 saw into the corner under the first beam and between sparse piles)
    # S2 perimeter raycast 31 Oct: 16 % of the corner was still seen through the 4-18 cm slots between the bale tops
    # and the next beam and the 0.5 m left open at each run's end -> bales fill each bay end to end, pressed up to
    # 1-3 cm under the next beam (wrapped bales of folded sacks are stacked to the beam)
    run = (x1 - x0) if along_x else (y1 - y0)
    nb = math.ceil(run / 0.9)
    for z in (0.0, 0.9, 1.9, 2.9):
        if z > 0:
            fx["orange"].append(mat_aabb(x0, y0, z - 0.1, x1, y1, z))
        else:
            fx["frame"].append(mat_aabb(x0 + 0.02, y0 + 0.02, 0.0, x1 - 0.02, y1 - 0.02, 0.12))  # floor pallets
        if z > 2.5:
            continue  # the top beam carries nothing (sprinkler clearance)
        base = z + (0.12 if z == 0 else 0.0)
        top = (0.9 if z == 0 else z + 1.0) - 0.1  # underside of the next beam
        for _ in range(int(run / 0.9)):  # the old bales' draws: keeps the global stream (the rest of the hub) as it was
            random.uniform(0.62, 0.76)
        for k in range(nb):
            a, b = k * run / nb + 0.005, (k + 1) * run / nb - 0.005
            hgt = top - base - BALE_RND.uniform(0.01, 0.03)
            fx["sack"].append(mat_aabb(x0 + a, y0 + 0.04, base, x0 + b, y1 - 0.04, base + hgt) if along_x else
                              mat_aabb(x0 + 0.04, y0 + a, base, x1 - 0.04, y0 + b, base + hgt))
# supervisor office: walls 3 m, glass north wall, door on the west wall onto walkway W1
ox0, oy0, ox1, oy1 = 54.6, 0.2, 59.8, 6.0
fx["white"] += [mat_aabb(ox0, oy0, 0, ox0 + 0.15, 0.55, 3.0), mat_aabb(ox0, 1.45, 0, ox0 + 0.15, oy1, 3.0),
                mat_aabb(ox0, 0.55, 2.1, ox0 + 0.15, 1.45, 3.0), mat_aabb(ox0, oy1 - 0.15, 0, ox1, oy1, 0.9),
                mat_aabb(ox0, oy1 - 0.15, 2.7, ox1, oy1, 3.0), mat_aabb(ox0, oy0, 3.0, ox1, oy1, 3.08)]
fx["frame"].append(mat_aabb(56.0, 4.6, 0.72, 58.0, 5.4, 0.76))  # desk
fx["screen"].append(mat_aabb(56.8, 5.2, 0.76, 57.4, 5.25, 1.12))
boxes("fixtures", fx, C["Fixtures"])
boxes("office_glass", {"glass": [mat_aabb(ox0 + 0.003, oy1 - 0.1, 0.9, ox1 - 0.003, oy1 - 0.05, 2.7)]},
      C["Fixtures"])  # 3 mm in from the frame (mesh_hygiene)

# roll cages (0.72 x 0.80 x 1.80 m): mesh-wire box + base; in staging bays and nested in the empty-cage store
def _cage(bm):
    """3-sided roll cage 0.72 x 0.80 x 1.80 m: 32 mm corner posts, rails, 10 mm mesh wires, deck, 4 castors."""
    W, D, H, base = 0.72, 0.80, 1.80, 0.17
    hx, hy = W / 2, D / 2
    segs = [((x, y, base), (x, y, H), 0.016) for x, y in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy))]
    for z in (base + 0.02, 0.75, 1.3, H):  # rails on back (+y) and both sides; front (-y) open
        segs += [((-hx, hy, z), (hx, hy, z), 0.011), ((-hx, -hy, z), (-hx, hy, z), 0.011),
                 ((hx, -hy, z), (hx, hy, z), 0.011)]
    wires = [((-hx + W * k / 6, hy, base), (-hx + W * k / 6, hy, H), 0.005) for k in range(1, 6)]
    for k in range(1, 7):
        y = -hy + D * k / 7
        if k in (3, 5):  # two side wires bent in by knocks (wear)
            mid = (-hx + 0.035, y + 0.01, 0.9)
            wires += [((-hx, y, base), mid, 0.005), (mid, (-hx, y, H), 0.005)]
        else:
            wires += [((-hx, y, base), (-hx, y, H), 0.005)]
        wires += [((hx, y, base), (hx, y, H), 0.005)]
    for z in [base + 0.2 * k for k in range(1, 8)]:
        wires += [((-hx, hy, z), (hx, hy, z), 0.004), ((-hx, -hy, z), (-hx, hy, z), 0.004),
                  ((hx, -hy, z), (hx, hy, z), 0.004)]
    tubes_into(bm, segs, 0, sides=8)
    tubes_into(bm, wires, 0, sides=5)
    r = bmesh.ops.create_cube(bm, size=1.0, matrix=mat_aabb(-hx, -hy, base - 0.04, hx, hy, base))
    for x, y in ((-hx + 0.06, -hy + 0.06), (hx - 0.06, -hy + 0.06), (hx - 0.06, hy - 0.06), (-hx + 0.06, hy - 0.06)):
        tubes_into(bm, [((x - 0.02, y, 0.055), (x + 0.02, y, 0.055), 0.055)], 1, sides=12)  # wheel
        bmesh.ops.create_cube(bm, size=1.0, matrix=mat_aabb(x - 0.03, y - 0.03, 0.06, x + 0.03, y + 0.03, base - 0.04))


CAGE_MESH = shared_mesh("roll_cage", _cage, ["steel", "black"])


def _gate(bm):
    """The fourth (front) side as a hinged gate: frame + mesh, hinge on the left front post (origin)."""
    W, H, base = 0.72, 1.80, 0.17
    segs = [((0, 0, base + 0.05), (W, 0, base + 0.05), 0.01), ((0, 0, H - 0.02), (W, 0, H - 0.02), 0.01),
            ((W, 0, base + 0.05), (W, 0, H - 0.02), 0.012), ((0.02, 0, 0.95), (W, 0, 0.95), 0.008)]
    segs += [((W * k / 6, 0, base + 0.05), (W * k / 6, 0, H - 0.02), 0.004) for k in range(1, 6)]
    segs += [((0, 0, z), (W, 0, z), 0.0035) for z in (0.45, 0.65, 1.15, 1.35, 1.55)]
    tubes_into(bm, segs, 0, sides=5)


GATE_MESH = shared_mesh("roll_cage_gate", _gate, ["steel"])
SLUMPED = [shared_mesh(f"sack_slumped_{k}_{m}", lambda bm, k=k: loft_into(bm, slumped_sack_rings(k), 0, cap_bottom=True,
                                                                          cap_top=True), [m])
           for k in range(4) for m in ("sack", "sack_blue", "sack_grey")]
for _me in SLUMPED:  # woven fabric reads soft, not faceted
    _me.shade_smooth()
CAGE_PARCEL_SPOTS = []  # (x, y, z, yaw, (kind, height, dims index)) -> placed once the parcel kit exists
# what fits one stack cell (0.30 x 0.34 m): small boxes (BOX_DIMS 0-3, 10) and small mailers (MAILER_DIMS 0-1)
CAGE_ITEMS = [("box", 0.08, 0), ("box", 0.10, 1), ("box", 0.12, 2), ("box", 0.15, 3), ("box", 0.25, 10),
              ("mailer", 0.045, 0), ("mailer", 0.05, 1), ("mailer", 0.05, 1)]
SHORT = {"C01": "PENANG", "C02": "KEDAH", "C03": "IPOH", "C04": "KLANG", "C05": "KL", "C06": "SEREMBAN", "C07": "MELAKA",
         "C08": "JB", "C09": "KUANTAN", "C10": "KOTA BHARU", "C11": "KOTA KINABALU", "C12": "KUCHING"}


def roll_cage(name, x, y, rot=0.0, fill="full", gate="closed", tag=True, padlock=False):
    """fill: empty | half (2–3 sacks) | full (4–5 sacks) | parcels (loose); gate: closed | open | None (nested)."""
    ob = place(CAGE_MESH, name, (x, y, 0.0), rot, collection=C["Fixtures"])
    coat = random.choices([None, "cage_red", "cage_yellow"], weights=[55, 25, 20])[0]
    if coat:
        ob.material_slots[0].link = "OBJECT"
        ob.material_slots[0].material = M[coat]
    ca, sa = math.cos(rot), math.sin(rot)

    def world(lx, ly):
        return x + lx * ca - ly * sa, y + lx * sa + ly * ca
    if gate:
        gx, gy = world(-0.36, -0.40)
        # an open gate swings flat against the side (hinge stop ~90 deg): wider went through the side mesh (QA 001 #3)
        g = place(GATE_MESH, f"{name}_gate", (gx, gy, 0.0), rot + (0.0 if gate == "closed" else -random.uniform(1.48, 1.56)),
                  collection=C["Fixtures"])
        if coat:
            g.material_slots[0].link = "OBJECT"
            g.material_slots[0].material = M[coat]
    # real hub cages (reference beesort_t202 / t234, dpd_t022) hold mostly LOOSE cartons and parcels; sacks lie
    # flat and uneven, 1-3 of them, never a centred tower
    n = {"empty": 0, "half": random.randint(1, 2), "full": 3, "parcels": 0}[fill]
    z = 0.17
    for k in range(n):  # lying sacks, each settled on the one below, a little off-centre and tilted
        wx, wy = world(random.uniform(-0.04, 0.04), random.uniform(-0.04, 0.04))
        sk = place(random.choice(SLUMPED), f"{name}_sack{k}", (wx, wy, z), rot + math.pi / 2 + random.uniform(-0.08, 0.08),
                   random.uniform(0.86, 1.0))
        sk.rotation_euler[0], sk.rotation_euler[1] = random.uniform(-0.15, 0.15), random.uniform(-0.15, 0.15)
        z += random.uniform(0.2, 0.26)  # sacks squash into each other
    if fill == "parcels":  # loose parcels packed in a 2 x 2 grid of stacks, sizes that fit the cage
        for cx_, cy_ in ((-0.15, -0.17), (0.15, -0.17), (-0.15, 0.17), (0.15, 0.17)):
            zc, top = 0.17, random.uniform(0.45, 1.25)
            while zc < top:
                item = random.choice(CAGE_ITEMS)
                small = item[0] == "mailer" or item[2] in (0, 1)  # footprint <= 0.2 m: can sit skewed
                CAGE_PARCEL_SPOTS.append((*world(cx_ + random.uniform(-0.02, 0.02), cy_ + random.uniform(-0.025, 0.025)),
                                          zc, rot + random.uniform(-0.3, 0.3) * (1 if small else 0.35), item))
                zc += item[1] + 0.005
    if tag:  # destination tag card on the right front post
        cid = random.choice(list(SHORT))
        tx, ty = world(0.36, -0.42)
        boxes(f"{name}_tag", {"label": [Matrix.Translation((tx, ty, 1.2)) @ Euler((0, 0, rot)).to_matrix().to_4x4()
                                        @ Matrix.Diagonal((0.09, 0.004, 0.13, 1))]}, C["Clutter"])
        text(f"{name}_tagtext", f"{cid}\n{SHORT[cid]}", (tx, ty - 0.004 * ca, 1.2), (90, 0, math.degrees(rot)), 0.022,
             "ink", C["Clutter"], extrude=0.0, font=BOARD_FONT)
    if padlock:
        px_, py_ = world(0.36, -0.40)
        boxes(f"{name}_padlock", {"black": [mat_aabb(px_ - 0.025, py_ - 0.03, 1.0, px_ + 0.025, py_ - 0.01, 1.07)]},
              C["Fixtures"])
    return ob


marks = {"yellow": [], "white": [], "black": []}
for i, bay in enumerate(FX["cage_bays"]):
    bx, by = bay["sw_corner_m"]
    s = bay["size_m"]
    for cx_, cy_, sx, sy in ((bx, by, 1, 1), (bx + s, by, -1, 1), (bx, by + s, 1, -1), (bx + s, by + s, -1, -1)):
        marks["yellow"] += [mat_aabb(min(cx_, cx_ + sx * 0.5), cy_ - 0.04, 0.001, max(cx_, cx_ + sx * 0.5), cy_ + 0.04,
                                     0.004),
                            mat_aabb(cx_ - 0.04, min(cy_, cy_ + sy * 0.5), 0.001, cx_ + 0.04, max(cy_, cy_ + sy * 0.5),
                                     0.004)]  # corner marks only
    if random.random() < 0.85:
        roll_cage(f"cage_{bay['id']}", bx + s / 2 + random.uniform(-0.15, 0.15), by + s / 2 + random.uniform(-0.15, 0.15),
                  random.uniform(-0.06, 0.06),  # parked square in its bay (QA 001 #3)
                  fill=random.choices(["empty", "half", "full", "parcels"], weights=[15, 20, 15, 50])[0],
                  gate="open" if random.random() < 0.15 else "closed")
for k in range(18):  # nested empty cages in Z11, outside the blind corner
    roll_cage(f"cage_empty_{k:02d}", 17.0 + 0.95 * (k % 6), 34.0 + 1.6 * (k // 6), 0.0, fill="empty", gate=None, tag=False)
# loaded, waiting at D08 / D10, either side of the door's centre lane (the pushers bring cages up the middle)
for k, (qx, qy) in enumerate(((31.55, 37.9), (34.55, 37.9), (39.55, 37.9), (42.45, 37.9))):
    roll_cage(f"cage_outbound_queue_{k}", qx, qy, math.pi + random.uniform(-0.1, 0.1), fill="full")
# locked damage-hold cage south of the exception bench (clear of walkway W3 at y 23.2–24.4)
roll_cage("cage_damaged_hold", 24.0, 20.55, 0.06, fill="half", padlock=True)
sign("sign_damaged", "BARANG ROSAK", (24.0, 20.1, 2.0), "-Y", 0.12, board=(1.0, 0.25), ink="ink_red")

# ------------------------------------------------------------------------------------------------ circulation
CI = SPEC["circulation"]
for w in CI["walkways"]:  # 100 mm yellow edge lines along the long sides
    x0, y0, x1, y1 = w["rect_m"]
    if (x1 - x0) >= (y1 - y0):
        marks["yellow"] += [mat_aabb(x0, y0, 0.001, x1, y0 + 0.1, 0.004), mat_aabb(x0, y1 - 0.1, 0.001, x1, y1, 0.004)]
    else:
        marks["yellow"] += [mat_aabb(x0, y0, 0.001, x0 + 0.1, y1, 0.004), mat_aabb(x1 - 0.1, y0, 0.001, x1, y1, 0.004)]
lane = CI["forklift_lane"]
hw = lane["width_m"] / 2
for (ax, ay), (bx, by) in zip(lane["centreline_m"], lane["centreline_m"][1:]):  # dashed yellow lane edges
    for s in (-1, 1):
        if ay == by:
            x0, x1 = min(ax, bx) - hw, max(ax, bx) + hw
            y = ay + s * hw
            marks["yellow"] += [mat_aabb(xk, y - 0.05, 0.001, min(xk + 1.0, x1), y + 0.05, 0.004)
                                for xk in [x0 + 1.6 * k for k in range(int((x1 - x0) / 1.6) + 1)] if xk < x1]
        else:
            y0, y1 = min(ay, by) - hw, max(ay, by) + hw
            x = ax + s * hw
            marks["yellow"] += [mat_aabb(x - 0.05, yk, 0.001, x + 0.05, min(yk + 1.0, y1), 0.004)
                                for yk in [y0 + 1.6 * k for k in range(int((y1 - y0) / 1.6) + 1)] if yk < y1]
for z in CI["zebra_crossings"]:
    x0, y0, x1, y1 = z["rect_m"]
    if (x1 - x0) < (y1 - y0):  # stripes run across the walking direction
        marks["white"] += [mat_aabb(x0, y, 0.002, x1, min(y + 0.3, y1), 0.005) for y in
                           [y0 + 0.6 * k for k in range(int((y1 - y0) / 0.6) + 1)] if y < y1]
    else:
        marks["white"] += [mat_aabb(x, y0, 0.002, min(x + 0.3, x1), y1, 0.005) for x in
                           [x0 + 0.6 * k for k in range(int((x1 - x0) / 0.6) + 1)] if x < x1]
    image_sign(f"sign_{z['id']}_forklift", "ws115_forklift", ((x0 + x1) / 2, (y0 + y1) / 2, 3.0),
               "+Y" if (x1 - x0) < (y1 - y0) else "-X", size=(0.4, 0.6), double=True)  # 400 x 600, hung on chains
    hx, hy = ((x0 + x1) / 2, (y0 + y1) / 2)
    marks.setdefault("steel", [])  # galvanised suspension chains (black ones read as cables down to the floor
    marks["steel"] += [mat_aabb(hx + dx - 0.004, hy - 0.004, 3.3, hx + dx + 0.004, hy + 0.004, EAVES - 1.2)
                       for dx in (-0.15, 0.15)]  # where the sign was seen edge-on: B2 pre-review #9)
z09 = next(z for z in SPEC["zones"] if z["id"] == "Z09")["polygon_m"]
marks["yellow"] += [mat_aabb(z09[0][0] + 0.3, 2.0, 0.001, z09[1][0] - 0.3, 2.1, 0.004)]  # oversize box line
boxes("floor_markings", marks, C["Circulation"])

xo = {"steel": [], "yellow": [], "frame": []}
for c in CI["crossovers"]:
    x0, x1, dk = c["x"] - c["width"] / 2, c["x"] + c["width"] / 2, c["deck_m"]
    for (ya, yb), up in ((c["south_stair_y"], True), (c["north_stair_y"], False)):
        n = math.ceil(dk / 0.19)
        run = (yb - ya) / n
        for k in range(n):
            zt = dk * ((k + 1) / n if up else (n - k) / n)
            xo["steel"].append(mat_aabb(x0 + 0.06, ya + k * run, zt - 0.04, x1 - 0.06, ya + (k + 1) * run, zt))
        z_a, z_b = (0.0, dk) if up else (dk, 0.0)
        for xs in (x0 + 0.03, x1 - 0.03):
            xo["frame"].append(mat_seg((xs, ya, z_a - 0.1), (xs, yb, z_b - 0.1), 0.06, 0.25))  # stringer
            xo["yellow"].append(mat_seg((xs, ya, z_a + 1.0), (xs, yb, z_b + 1.0), 0.05, 0.05))  # handrail
    by0, by1 = c["bridge_y"]
    xo["steel"].append(mat_aabb(x0, by0, dk - 0.06, x1, by1, dk))
    for xs in (x0 + 0.03, x1 - 0.03):
        xo["yellow"].append(mat_aabb(xs - 0.025, by0, dk + 0.97, xs + 0.025, by1, dk + 1.03))
        xo["yellow"].append(mat_aabb(xs - 0.025, by0, dk + 0.47, xs + 0.025, by1, dk + 0.51))
        for yk in [by0 + 1.5 * k for k in range(int((by1 - by0) / 1.5) + 1)]:
            xo["yellow"].append(mat_aabb(xs - 0.025, yk - 0.025, dk, xs + 0.025, yk + 0.025, dk + 1.03))
    for yk in (by0 + 0.3, (by0 + by1) / 2, by1 - 0.3):  # support posts (inside the loop / clear of belts)
        if c["id"] == "XO-2" and abs(yk - 9.5) < 0.6:
            continue
        xo["frame"].append(mat_aabb(c["x"] - 0.08, yk - 0.08, 0, c["x"] + 0.08, yk + 0.08, dk - 0.06))
    sign(f"sign_{c['id']}", "GUNA JAMBATAN", (c["x"], c["south_stair_y"][0] - 0.3, 2.3), "-Y", 0.1,
         board=(1.0, 0.25))
boxes("crossovers", xo, C["Circulation"])

# RFID portals at the outbound doors (cages are read leaving; neighbours can cross-read)
rfid = {"frame": [], "white": []}
for d in DOORS:
    if d["kind"] == "dock" and d["wall"] == "N":
        cx = d["centre"][0]
        for s in (-1, 1):
            rfid["frame"].append(mat_aabb(cx + s * 1.7 - 0.08, BD - 0.9, 0, cx + s * 1.7 + 0.08, BD - 0.7, 2.4))
            rfid["white"].append(mat_aabb(cx + s * 1.7 - 0.1, BD - 0.95, 1.2, cx + s * 1.7 + 0.1, BD - 0.88, 1.8))
boxes("rfid_portals", rfid, C["Machines"])

# ------------------------------------------------------------------------------------------------ clutter: parcels
FLYER_SIZES = [(0.24, 0.32), (0.27, 0.37), (0.31, 0.44)]  # A4-ish, B4-ish, A3-ish mailers


def _flyer(bm, w, h, seed):
    """Flat poly mailer: pillowed middle, crimped seams, a few creases; label on top (material 1)."""
    rnd = random.Random(seed)
    nx_, ny_ = 8, 10
    grid = []
    for j in range(ny_ + 1):
        row = []
        for i in range(nx_ + 1):
            u, v = i / nx_, j / ny_
            puff = 0.032 * math.sin(math.pi * u) * math.sin(math.pi * v)
            crease = 0.004 * math.sin(11 * u + 7 * v + rnd.uniform(0, 6)) + 0.003 * math.sin(17 * v + rnd.uniform(0, 6))
            row.append(bm.verts.new(((u - 0.5) * w, (v - 0.5) * h, 0.006 + puff + crease)))
        grid.append(row)
    for j in range(ny_):
        for i in range(nx_):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    edge = [grid[0][i] for i in range(nx_ + 1)] + [grid[j][nx_] for j in range(1, ny_ + 1)] + \
           [grid[ny_][i] for i in range(nx_ - 1, -1, -1)] + [grid[j][0] for j in range(ny_ - 1, 0, -1)]
    low = [bm.verts.new((v.co.x, v.co.y, 0.0)) for v in edge]  # underside: flat on whatever it lies on
    for a in range(len(edge)):
        b = (a + 1) % len(edge)
        bm.faces.new((edge[a], edge[b], low[b], low[a]))
    bm.faces.new(list(reversed(low)))
    lw, lh = min(0.10, w * 0.45), min(0.15, h * 0.45)
    r = bmesh.ops.create_cube(bm, size=1.0, matrix=mat_aabb(-lw / 2 + 0.02, -lh / 2, 0.036, lw / 2 + 0.02, lh / 2, 0.04))
    for f in {f for v in r["verts"] for f in v.link_faces}:
        f.material_index = 1


LABEL_DIR = Path(args.out).resolve().parent / "labels"
LABEL_META = json.loads((LABEL_DIR / "labels.json").read_text(encoding="utf-8"))
L_COLS, L_ROWS = LABEL_META["cols"], LABEL_META["rows"]
ATLAS = bpy.data.images.load(str(LABEL_DIR / "label_atlas.png"))
STICKER_TILES = LABEL_META["sticker_tiles"]
_bg_tiles = iter(t for t in range(32, LABEL_META["label_tiles"]))  # 0–31 reserved for scenario parcels
PARCELS = []  # registry (render side): which waybill ID sits where -> build/truth/parcels_registry.json


def atlas_material(name, attr):
    """Label / sticker material: one atlas, the tile picked per object from a custom property (unique labels,
    one material)."""
    m = bpy.data.materials.new(name)
    if hasattr(m, "use_nodes"):
        m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    b.inputs["Roughness"].default_value = 0.45
    uv = nt.nodes.new("ShaderNodeUVMap")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(uv.outputs["UV"], sep.inputs["Vector"])
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_type, at.attribute_name = "OBJECT", attr

    def mth(op, a, bb):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, bb)):
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                nt.links.new(v, n.inputs[i])
        return n.outputs[0]
    col = mth("MODULO", at.outputs["Fac"], float(L_COLS))
    row = mth("FLOOR", mth("DIVIDE", at.outputs["Fac"], float(L_COLS)), 0.0)
    u = mth("DIVIDE", mth("ADD", sep.outputs["X"], col), float(L_COLS))
    v = mth("DIVIDE", mth("ADD", sep.outputs["Y"], mth("SUBTRACT", float(L_ROWS - 1), row)), float(L_ROWS))
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(u, comb.inputs["X"])
    nt.links.new(v, comb.inputs["Y"])
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = ATLAS
    tex.interpolation = "Linear"
    nt.links.new(comb.outputs["Vector"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    return m


def print_material(name, base_hex, ink_hex, kind):
    """Generic printed mailer (no brands): white dots or wavy stripes on a colour, in object space."""
    m = material(name, base_hex, 0.4)
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    th = nt.nodes.new("ShaderNodeMath")
    if kind == "dots":
        t = nt.nodes.new("ShaderNodeTexVoronoi")
        t.inputs["Scale"].default_value = 38.0
        nt.links.new(tc.outputs["Object"], t.inputs["Vector"])
        th.operation = "LESS_THAN"
        nt.links.new(t.outputs["Distance"], th.inputs[0])
        th.inputs[1].default_value = 0.22
    else:
        t = nt.nodes.new("ShaderNodeTexWave")
        t.inputs["Scale"].default_value = 7.0
        t.inputs["Distortion"].default_value = 3.0
        nt.links.new(tc.outputs["Object"], t.inputs["Vector"])
        th.operation = "GREATER_THAN"
        nt.links.new(t.outputs["Fac"], th.inputs[0])
        th.inputs[1].default_value = 0.62
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (*srgb(base_hex), 1)
    mix.inputs["B"].default_value = (*srgb(ink_hex), 1)
    nt.links.new(th.outputs[0], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
    return m


M["fly_print_dots"] = print_material("flyer_print_dots", "#d9488f", "#f2eee8", "dots")
M["fly_print_waves"] = print_material("flyer_print_waves", "#2a9d8f", "#f4e9c8", "waves")
M["parcel_label"] = atlas_material("parcel_label", "label_tile")
M["parcel_sticker"] = atlas_material("parcel_sticker", "sticker_tile")
M["tape"] = material("packing_tape", "#b08850", 0.25)
M["card_white"] = material("cardboard_white", "#e8e6df", 0.8, noise=25.0)
M["padded_kraft"] = material("padded_envelope", "#d8b64a", 0.7, noise=15.0)
M["fly_bag"] = material("bag_wrap_grey", "#7d8186", 0.35)
PARCEL_SLOTS = ["card", "parcel_label", "tape", "parcel_sticker"]  # slot 0 = body colour (overridden per object)


def _uvquad(bm, uvl, cx, cy, z, w, h, ang, mi, nz=1.0):
    ca, sa = math.cos(ang), math.sin(ang)
    corners = [(-w / 2, -h / 2, 0, 0), (w / 2, -h / 2, 1, 0), (w / 2, h / 2, 1, 1), (-w / 2, h / 2, 0, 1)]
    vs = [bm.verts.new((cx + x * ca - y * sa, cy + x * sa + y * ca, z)) for x, y, _, _ in corners]
    f = bm.faces.new(vs if nz > 0 else list(reversed(vs)))
    loops = list(f.loops) if nz > 0 else list(reversed(list(f.loops)))
    for loop, (_, _, uu, vv) in zip(loops, corners):
        loop[uvl].uv = (uu, vv)
    f.material_index = mi


def _box_parcel(bm, dims, seed, crushed, sticker):
    rnd = random.Random(seed)
    uvl = bm.loops.layers.uv.verify()
    sx, sy, sz = dims
    r = bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, 0, sz / 2)) @ Matrix.Diagonal((sx, sy, sz, 1)))
    if crushed:  # one top corner pushed in (handling damage)
        top = [v for v in r["verts"] if v.co.z > sz * 0.9]
        v = rnd.choice(top)
        v.co.z -= rnd.uniform(0.025, 0.05)
        v.co.x *= 0.88
        v.co.y *= 0.9
    z = sz + 0.0015
    _uvquad(bm, uvl, 0, 0, z, sx + 0.002, 0.05, 0.0, 2)  # tape along the top seam
    if rnd.random() < 0.5:
        _uvquad(bm, uvl, 0, 0, z + 0.0005, 0.05, sy + 0.002, 0.0, 2)  # extra cross tape
    lw, lh = min(0.10, sx * 0.7), min(0.15, sy * 0.7)
    _uvquad(bm, uvl, rnd.uniform(-0.15, 0.15) * sx, rnd.uniform(-0.15, 0.15) * sy, z + 0.001, lw, lh,
            rnd.uniform(-0.4, 0.4), 1)
    if sticker:
        _uvquad(bm, uvl, rnd.uniform(-0.3, 0.3) * sx, rnd.uniform(-0.3, 0.3) * sy, z + 0.0012, 0.06, 0.09,
                rnd.uniform(0, 3.1), 3)


def _mailer_parcel(bm, w, h, seed, sticker):
    _flyer(bm, w, h, seed)  # pillow body (material 0) + legacy label box (material 1, UV'd below)
    uvl = bm.loops.layers.uv.verify()
    rnd = random.Random(seed + 7)
    for f in [f for f in bm.faces if f.material_index == 1]:  # replace the plain label box with a UV'd label quad
        bm.faces.remove(f)
    lw, lh = min(0.10, w * 0.45), min(0.15, h * 0.45)
    _uvquad(bm, uvl, rnd.uniform(-0.2, 0.2) * w, rnd.uniform(-0.2, 0.2) * h, 0.041, lw, lh, rnd.uniform(-0.3, 0.3), 1)
    if sticker:
        _uvquad(bm, uvl, rnd.uniform(-0.3, 0.3) * w, rnd.uniform(-0.3, 0.3) * h, 0.042, 0.05, 0.075, rnd.uniform(0, 3), 3)


def _tube_parcel(bm):
    uvl = bm.loops.layers.uv.verify()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.045, radius2=0.045, depth=0.5,
                          matrix=Matrix.Translation((0, 0, 0.045)) @ Euler((0, math.pi / 2, 0)).to_matrix().to_4x4())
    _uvquad(bm, uvl, 0.0, 0.0, 0.091, 0.15, 0.08, math.pi / 2, 1)


def _wrapped_item(bm, seed):
    rnd = random.Random(seed)
    uvl = bm.loops.layers.uv.verify()
    r = bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.5)
    for v in r["verts"]:
        v.co.x *= 0.34 * (1 + rnd.uniform(-0.15, 0.15))
        v.co.y *= 0.26 * (1 + rnd.uniform(-0.15, 0.15))
        v.co.z = (v.co.z + 0.5) * 0.18
    _uvquad(bm, uvl, 0.0, 0.0, 0.185, 0.10, 0.15, 0.3, 1)


BOX_DIMS = [(0.15, 0.10, 0.08), (0.20, 0.15, 0.10), (0.25, 0.18, 0.12), (0.30, 0.20, 0.15), (0.30, 0.30, 0.25),
            (0.35, 0.25, 0.20), (0.40, 0.30, 0.25), (0.45, 0.35, 0.30), (0.50, 0.40, 0.30), (0.60, 0.40, 0.40),
            (0.25, 0.25, 0.25), (0.40, 0.25, 0.10)]
MAILER_DIMS = [(0.17, 0.24), (0.24, 0.32), (0.27, 0.37), (0.31, 0.44)]
BOX_MESHES = [shared_mesh(f"pbox_{k}_{c}{s}", lambda bm, k=k, c=c, s=s: _box_parcel(bm, BOX_DIMS[k], 100 + k, c, s),
                          PARCEL_SLOTS) for k in range(len(BOX_DIMS)) for c in (0, 1) for s in (0, 1)]
MAILER_MESHES = [shared_mesh(f"pmail_{k}_{s}", lambda bm, k=k, s=s: _mailer_parcel(bm, *MAILER_DIMS[k], 200 + k, s),
                             PARCEL_SLOTS) for k in range(len(MAILER_DIMS)) for s in (0, 1)]
TUBE_MESH = shared_mesh("ptube", _tube_parcel, PARCEL_SLOTS)
WRAPPED_MESH = shared_mesh("pwrapped", lambda bm: _wrapped_item(bm, 7), PARCEL_SLOTS)


def parcel(name, x, y, z, yaw=None, kind=None, tile=None, body=None, mesh=None, tags=None, collection=None,
           scale=None):
    """One parcel object with a unique CONTOH label (atlas tile) and a registry entry."""
    yaw = random.uniform(0, math.pi * 2) if yaw is None else yaw
    if kind is None:
        kind = random.choices(["mailer", "box", "padded", "tube", "wrapped"], weights=[60, 35, 2, 1.5, 1.5])[0]
    if mesh is None:
        mesh = {"mailer": lambda: random.choice(MAILER_MESHES), "box": lambda: random.choice(BOX_MESHES),
                "padded": lambda: MAILER_MESHES[2], "tube": lambda: TUBE_MESH, "wrapped": lambda: WRAPPED_MESH}[kind]()
    if body is None:
        body = {"mailer": lambda: random.choices(["fly_grey", "fly_black", "fly_white", "fly_red", "fly_blue",
                                                   "fly_purple", "fly_print_dots", "fly_print_waves"],
                                                  weights=[28, 22, 14, 9, 9, 6, 6, 6])[0],
                "box": lambda: "card_white" if random.random() < 0.15 else "card", "padded": lambda: "padded_kraft",
                "tube": lambda: "card", "wrapped": lambda: "fly_bag"}[kind]()
    ob = place(mesh, name, (x, y, z), yaw, random.uniform(0.92, 1.08) if scale is None else scale,
               collection=collection)
    if kind == "mailer":
        ob.rotation_euler[0] = random.uniform(-0.05, 0.05)
    ob.material_slots[0].link = "OBJECT"
    ob.material_slots[0].material = M[body]
    reused = False
    if tile is None:
        tile = next(_bg_tiles, None)
        if tile is None:  # more parcels than unique labels: reuse, flagged in the registry
            tile = random.randrange(32, LABEL_META["label_tiles"])
            reused = True
    ob["label_tile"] = float(tile)
    ob["sticker_tile"] = float(random.choice(STICKER_TILES))
    lab = LABEL_META["labels"][tile]
    ob["parcel_id"] = lab["parcel_id"]
    PARCELS.append({"object": ob.name, "parcel_id": lab["parcel_id"], "tile": tile, "kind": kind, "body": body,
                    "mesh": mesh.name, "position_m": [round(x, 3), round(y, 3), round(z, 3)], "tags": tags or [],
                    "label_reused": reused})
    return ob


def parcels(name, spots):
    """spots: [(x, y, z_base)] -> mixed parcels (~60 % mailers, ~35 % boxes, ~5 % odd), each uniquely labelled."""
    for k, (x, y, z) in enumerate(spots):
        parcel(f"{name}_{k:03d}", x, y, z)


for k, (x, y, z, yaw, (kind, _, di)) in enumerate(CAGE_PARCEL_SPOTS):
    mesh = BOX_MESHES[di * 4 + random.randrange(4)] if kind == "box" else MAILER_MESHES[di * 2 + random.randrange(2)]
    parcel(f"cage_loose_{k:03d}", x, y, z, yaw=yaw + (math.pi / 2 if kind == "mailer" else 0.0), kind=kind, mesh=mesh,
           scale=1.0)
# (belts, booms and the loop carry moving parcels: flow.py simulates and bakes them)
parcels("chute_piles", CHUTE_SPOTS)
parcels("bag_contents", BAG_SPOTS)
parcels("bag_opening", [(random.uniform(6.4, 7.8), random.uniform(19.2, 26.8), 0.9) for _ in range(14)])
# the two benches are y 19-22 and 24-27: the ones drawn into the 2 m between them stood on nothing, 0.9 m over the floor
# (zone audit 1 Nov). Still drawn (the same random draws: every later placement is unchanged), taken out here.
_benches = [b["rect_m"] for b in FX["benches"] if b["name"].startswith("bag-opening")]
for _p in [p_ for p_ in PARCELS if p_["object"].startswith("bag_opening_")]:
    _x, _y = _p["position_m"][:2]
    if not any(r[0] <= _x <= r[2] and r[1] <= _y <= r[3] for r in _benches):
        bpy.data.objects.remove(bpy.data.objects[_p["object"]], do_unlink=True)
        PARCELS.remove(_p)
# on top of what is already in the rework bin (y 20.6-21.2, rim 0.6 m). They floated 0.35 m up, 0.9 m past the bin,
# over a crate that was never built (B2 pre-review P0 #2); same random draws, so every later placement is unchanged
parcels("reject_crate", [(29.3 + random.uniform(-0.2, 0.2), 20.9 + random.uniform(-0.15, 0.15), 0.45)
                         for _ in range(3)])
parcels("exception_bench", [(random.uniform(23.8, 27.8), random.uniform(21.3, 22.5), 0.9) for _ in range(6)])
# parcels on the floor where workers pick them up (mixamo_workers 'Picking Up Object' bends to the floor): the
# overflow pile beside the induction belt and one that missed the C04 bag
# ONE deliberate floor parcel (registered, tagged): it missed the C04 bag and lies by the frame - realistic mess,
# not a false lead (QA review 001 #4)
parcel("floor_spill_000", 44.82, 21.62, 0.0, tags=["dropped_on_floor"])  # aisle side of the C04 frame, not under it
# scenario 5 look-alike pair: same mailer, colour, size and sticker, side by side on bag-opening bench 2; only the
# labels differ (tile 30 -> C12 Kuching, tile 31 -> C03 Ipoh). Both IDs are in the scenario truth, nowhere else.
for k, (tile, (lx, ly)) in enumerate(((30, (7.05, 25.15)), (31, (7.15, 25.62)))):
    parcel(f"lookalike_{k}", lx, ly, 0.9, yaw=0.12 + 0.1 * k, kind="mailer", tile=tile, body="fly_blue",
           mesh=MAILER_MESHES[3], scale=1.0, tags=["lookalike_pair", "scenario_5"])
pal = {"wood": []}
WRAPS, WRAPPED_PALLET = [], []
# oversize area: pallets kept OUT of the forklift lane (it starts inside Z09): a row along the north edge
# (y 5.45–6.45, clear of crossover XO-2 at x 15.9) and two by the west edge (x 5.8–6.8)
PALLETS = [(9.0 + 1.4 * k, 5.95, 0.0) for k in range(5)] + [(6.3, 2.8, math.pi / 2), (6.3, 4.2, math.pi / 2)]
for k, (px, py, rz) in enumerate(PALLETS):
    sx, sy = (0.6, 0.5) if rz == 0 else (0.5, 0.6)
    pal["wood"].append(mat_aabb(px - sx, py - sy, 0, px + sx, py + sy, 0.15))
    if k % 3:  # stacked cartons; only pallet 1 is wrapped (thin film, cartons visible through it)
        top = 0.15 + random.uniform(0.6, 1.3)
        layers = max(2, int((top - 0.15) / 0.32))
        for lv in range(layers):
            for ix in range(2):
                for iy in range(2):
                    pal.setdefault("card", []).append(mat_aabb(
                        px - sx + 0.07 + ix * (sx - 0.07), py - sy + 0.07 + iy * (sy - 0.07), 0.15 + lv * 0.32,
                        px - sx + 0.07 + (ix + 1) * (sx - 0.07) - 0.01, py - sy + 0.07 + (iy + 1) * (sy - 0.07) - 0.01,
                        0.15 + (lv + 1) * 0.32 - 0.01))
        top_z = 0.15 + layers * 0.32
        if k != 1:
            continue
        WRAPS.append((mat_aabb(px - sx + 0.05, py - sy + 0.05, 0.15, px + sx - 0.05, py + sy - 0.05, top_z - 0.04), 0))
        WRAPS.append((mat_aabb(px - sx + 0.045, py - sy + 0.045, top_z - 0.1, px + sx - 0.045, py + sy - 0.045,
                               top_z - 0.03), 0))  # rolled film edge: a thicker band just below the top layer
        WRAPS.append((Matrix.Translation((px + sx - 0.02, py - sy + 0.1, 0.55)) @ Euler((0.0, 0.35, -0.6)).to_matrix().to_4x4()
                      @ Matrix.Diagonal((0.004, 0.22, 0.75, 1)), 0))  # loose film tail hanging off a corner
        WRAPPED_PALLET.append((px, py - sy + 0.045, 0.75))  # shipping label goes on the film face
        for k2 in (-0.25, 0.25):  # two straps over the top and down the sides
            pal.setdefault("black", []).append(mat_aabb(px + k2 * sx - 0.012, py - sy + 0.04, top_z, px + k2 * sx + 0.012,
                                                        py + sy - 0.04, top_z + 0.006))
            for e in (-1, 1):
                pal["black"].append(mat_aabb(px + k2 * sx - 0.012, py + e * (sy - 0.04) - 0.004, 0.05,
                                             px + k2 * sx + 0.012, py + e * (sy - 0.04) + 0.004, top_z + 0.006))
boxes("oversize_pallets", pal, C["Clutter"])
mesh_obj("oversize_wrap", WRAPS, ["wrap_thin"], C["Clutter"], kind="openbox")
for lx, ly, lz in WRAPPED_PALLET:  # consignment label on the film (its waybill is in the registry)
    lab_me = shared_mesh("label_on_film", lambda bm: _uvquad(bm, bm.loops.layers.uv.verify(), 0, 0, 0, 0.10, 0.15, 0, 0),
                         ["parcel_label"])
    lab = place(lab_me, "pallet_consignment_label", (lx, ly - 0.004, lz), 0.0)
    lab.rotation_euler[0] = math.radians(90)
    tile = next(_bg_tiles)
    lab["label_tile"] = float(tile)
    PARCELS.append({"object": lab.name, "parcel_id": LABEL_META["labels"][tile]["parcel_id"], "tile": tile,
                    "kind": "pallet_consignment", "position_m": [lx, ly, lz], "tags": ["wrapped pallet, Z09"]})
parcels("oversize_big", [(px, py, 0.15) for k, (px, py, _) in enumerate(PALLETS) if k % 3 == 0])

# ------------------------------------------------------------------------------------------------ wall details
def wall_details():
    items = {"panel_grey": [], "cork": [], "white": [], "pipe_red": [], "black": []}
    pipes = bmesh.new()
    # electrical distribution boards + conduit risers (W wall south end, N wall east end, E wall north)
    G = 0.003  # 3 mm proud of the wall (review mesh_hygiene: never coplanar)
    for (x0, y0, x1, y1) in ((WALL_T + G, 1.4, WALL_T + 0.25, 2.2), (WALL_T + G, 2.6, WALL_T + 0.25, 3.4),
                             (55.4, BD - WALL_T - 0.25, 56.4, BD - WALL_T - G),
                             (BW - WALL_T - 0.25, 34.0, BW - WALL_T - G, 34.9)):
        items["panel_grey"].append(mat_aabb(x0, y0, 0.9, x1, y1, 2.1))
        cxp, cyp = (x0 + x1) / 2, (y0 + y1) / 2
        tubes_into(pipes, [((cxp, cyp, 2.1), (cxp, cyp, 3.8), 0.025)], 0)
    for a, b in (((WALL_T + 0.1, 0.5, 3.8), (WALL_T + 0.1, BD - 0.5, 3.8)),
                 ((0.5, BD - WALL_T - 0.1, 3.8), (BW - 0.5, BD - WALL_T - 0.1, 3.8)),
                 ((BW - WALL_T - 0.1, 8.0, 3.8), (BW - WALL_T - 0.1, BD - 0.5, 3.8)),
                 ((0.5, WALL_T + 0.1, 3.8), (54.0, WALL_T + 0.1, 3.8))):
        tubes_into(pipes, [(a, b, 0.03)], 0)  # conduit runs along the walls above the door headers
    # fire hose reels: red drum on a wall bracket
    for (x, y, facing) in ((WALL_T + 0.2, 29.7, "+X"), (BW - WALL_T - 0.2, 22.0, "-X"), (26.5, BD - WALL_T - 0.2, "-Y"),
                           (20.0, WALL_T + 0.2, "+Y")):
        ax = {"+X": (1, 0), "-X": (-1, 0), "+Y": (0, 1), "-Y": (0, -1)}[facing]
        tubes_into(pipes, [((x - ax[0] * 0.08, y - ax[1] * 0.08, 1.45), (x + ax[0] * 0.08, y + ax[1] * 0.08, 1.45), 0.32)], 1,
                   sides=20)
        items["pipe_red"].append(mat_aabb(x - 0.12 - abs(ax[1]) * 0.25, y - 0.12 - abs(ax[0]) * 0.25, 0.9,
                                          x + 0.12 + abs(ax[1]) * 0.25, y + 0.12 + abs(ax[0]) * 0.25, 1.0))
    me = bpy.data.meshes.new("wall_conduit_hosereels")
    pipes.to_mesh(me)
    pipes.free()
    me.materials.append(M["panel_grey"])
    me.materials.append(M["pipe_red"])
    C["Shell"].objects.link(bpy.data.objects.new("wall_conduit_hosereels", me))
    # notice boards with pinned sheets
    for (x, y, facing) in ((53.3, BD - WALL_T - 0.03, "-Y"), (38.5, WALL_T + 0.03, "+Y")):  # (at x 55.5 it
        # overlapped the electrical board beside it: B2 stills CAM_14 / CAM_16)
        along = (1, 0)
        items["cork"].append(mat_aabb(x - 0.6, y - 0.02, 1.1, x + 0.6, y + 0.02, 2.0))
        for k in range(6):
            dx, dz = -0.45 + 0.3 * (k % 4), 1.25 + 0.38 * (k // 4)
            items["white"].append(mat_aabb(x + dx - 0.1, y - 0.03 * (1 if facing == "-Y" else -1) - 0.005, dz,
                                           x + dx + 0.1, y - 0.03 * (1 if facing == "-Y" else -1) + 0.005, dz + 0.28))
    boxes("wall_details", items, C["Shell"])
    # real-format safety signs (make_signs.py: QuickSign catalogue layout + wording, ISO 7010 pictograms), centre
    # 1.8 m, where sites put them: PPE pair + CCTV at the staff entrance and the dock rows, no smoking, first aid by
    # the office, walkway sign where W1 starts, moving-machinery / no-walking-on-conveyor zip-tied to the loop guards
    E, Wx, S_, N_ = BW - WALL_T - 0.005, WALL_T + 0.005, WALL_T + 0.005, BD - WALL_T - 0.005
    plan = [("ws053_cctv", (E, 10.3, 1.8), "-X"), ("ms017_vest", (E, 13.7, 1.8), "-X"), ("ms027_shoes", (E, 14.1, 1.8), "-X"),
            ("ms017_vest", (Wx, 31.0, 1.8), "+X"), ("ms027_shoes", (Wx, 31.4, 1.8), "+X"), ("ws053_cctv", (Wx, 3.2, 2.45), "+X"),
            ("ms017_vest", (25.6, N_, 1.8), "-Y"), ("ms027_shoes", (26.0, N_, 1.8), "-Y"), ("ws053_cctv", (53.5, N_, 2.0), "-Y"),
            ("p002_nosmoking", (35.0, S_, 1.8), "+Y"), ("e003_firstaid", (E, 7.6, 1.8), "-X"),
            ("ms038_walkway", (51.0, S_, 1.8), "+Y")]
    lg = SPEC["machines"]["loop"]["south_y"] - 0.64 - 0.025  # outer face of the south-straight guard panel
    plan += [("ws021_machinery", (31.0, lg, DECK + 0.2), "-Y"), ("ps061_conveyor", (37.4, lg, DECK + 0.2), "-Y"),
             ("ws021_machinery", (44.0, lg, DECK + 0.2), "-Y")]
    for k, (sid, loc, facing) in enumerate(plan):
        image_sign(f"safety_sign_{k:02d}_{sid}", sid, loc, facing)


wall_details()

# ------------------------------------------------------------------------------------------------ signs (Malay/English)
sign("sign_awas", "AWAS - KENDERAAN", (WALL_T + 0.02, 17.0, 4.2), "+X", 0.22, board=(2.6, 0.5), ink="ink_red")
sign("sign_bukabeg", "BUKA BEG DI SINI", (11.0, 29.0, 3.0), "-Y", 0.2, board=(2.4, 0.45))
sign("sign_label", "LABEL MENGHADAP ATAS", (11.0, 9.5, 2.4), "-Y", 0.14, board=(2.2, 0.35))
sign("sign_mesin", "DILARANG MASUK - ZON MESIN", (39.0, 6.2, 2.6), "-Y", 0.16, board=(3.2, 0.4), ink="ink_red")
sign("sign_kosong", "SANGKAR KOSONG", (20.0, 30.2, 2.6), "-Y", 0.18, board=(2.2, 0.4))
# the exception store's doorway (BLIND_NW entrance gap x 13.4-15.2; review 019 #2, scenarios_v2 S2 #4: a lawful
# reason to carry a parcel in there, readable in CAM_19): a header beam across the two rack ends, the sign under it
# (1 cm short of each rack end: flush, its end faces z-fought the uprights' faces, mesh_hygiene 31 Oct; its top 1 cm
# under the uprights' tops: level with them, it z-fought both, mesh_hygiene run 7; 1 cm in from their front and back
# faces: flush with them it z-fought both, run 8)
boxes("store_header", {"orange": [mat_aabb(13.36, 32.96, 2.92, 15.24, 33.04, 2.99)]}, C["Fixtures"])
sign("sign_stor", "STOR PENGECUALIAN", (14.3, 32.96, 2.72), "-Y", 0.13, board=(1.75, 0.40))  # bolted under the beam
text("sign_stor_en", "EXCEPTION STORE", (14.3, 32.93, 2.57), FACE["-Y"], 0.09, "ink", C["Signs"])
sign("sign_pejabat", "PEJABAT PENYELIA", (54.55, 3.0, 2.5), "-X", 0.13, board=(1.8, 0.3))
sign("brand_inside", "CONTOH Express", (WALL_T + 0.02, 33.0, 7.0), "+X", 0.9, ink="brand")
sign("brand_outside", "CONTOH Express", (39.0, BD + 0.03, 7.5), "+Y", 1.6, ink="brand")

# ------------------------------------------------------------------------------------------------ yard: lorries
lorry_box = {"brand": [], "white": [], "black": [], "frame": [], "glass": [], "steel": [], "yellow": [],
             "line_yellow": []}
LORRY_WHEELS = []  # (centre, axis) - round tyres, built below


def lorry(d):
    """A rigid box lorry backed onto door d, in its own frame: u out from the wall, v across, z up. Hollow box open
    at the door, cab with windscreen / grille / bumper (~3 m above the yard), chassis rails, side underrun bars,
    twin round wheels (the CCTV yard camera showed block lorries on a flat slab: B2 pre-review #6)."""
    cx, cy = d["centre"]
    west = d["wall"] == "W"

    def box(key, u0, u1, v0, v1, z0, z1):
        if west:
            lorry_box[key].append(mat_aabb(-u1, cy + v0, z0, -u0, cy + v1, z1))
        else:
            lorry_box[key].append(mat_aabb(cx + v0, BD + u0, z0, cx + v1, BD + u1, z1))

    def wheel(u, v):
        LORRY_WHEELS.append(((-u, cy + v, YARD_Z + 0.5) if west else (cx + v, BD + u, YARD_Z + 0.5), "Y" if west else "X"))

    box("white", 0.15, 7.2, -1.2, 1.2, -0.12, 0.0)  # floor (dock level)
    box("white", 0.15, 7.2, -1.2, 1.2, 2.5, 2.6)  # roof
    box("white", 0.15, 7.2, -1.2, -1.12, 0.0, 2.5)  # side walls
    box("white", 0.15, 7.2, 1.12, 1.2, 0.0, 2.5)
    box("white", 7.12, 7.2, -1.12, 1.12, 0.0, 2.5)  # front wall
    box("brand", 0.4, 7.0, -1.21, -1.2, 1.0, 1.6)  # livery band, outside only
    box("brand", 0.4, 7.0, 1.2, 1.21, 1.0, 1.6)
    box("black", 0.3, 9.3, -0.5, -0.38, YARD_Z + 0.55, -0.12)  # chassis rails
    box("black", 0.3, 9.3, 0.38, 0.5, YARD_Z + 0.55, -0.12)
    for sv in (-1.17, 1.07):  # side underrun bars between the axles
        box("steel", 2.6, 4.9, sv, sv + 0.1, YARD_Z + 0.55, YARD_Z + 0.65)
    box("frame", 7.3, 9.4, -1.15, 1.15, YARD_Z + 0.75, 1.75)  # cab: 3 m above the yard
    box("glass", 9.4, 9.42, -1.02, 1.02, 0.75, 1.55)  # windscreen
    for sv in (-1.16, 1.14):  # side windows
        box("glass", 7.6, 8.9, sv, sv + 0.02, 0.85, 1.5)
    box("black", 9.4, 9.43, -0.8, 0.8, YARD_Z + 0.95, YARD_Z + 1.55)  # grille
    box("black", 9.35, 9.55, -1.2, 1.2, YARD_Z + 0.5, YARD_Z + 0.8)  # bumper
    for sv in (-1.32, 1.22):  # mirrors
        box("black", 9.2, 9.3, sv, sv + 0.1, 0.9, 1.3)
    for u in (2.0, 5.5, 8.6):  # twin tyres on the rear axles, singles at the front
        for sv in ((-0.95, -0.65, 0.65, 0.95) if u < 8 else (-0.95, 0.95)):
            wheel(u, sv)
    box("line_yellow", 0.0, 12.0, -1.75, -1.65, YARD_Z + 0.001, YARD_Z + 0.004)  # bay lines either side
    box("line_yellow", 0.0, 12.0, 1.65, 1.75, YARD_Z + 0.001, YARD_Z + 0.004)
    box("yellow", 0.25, 0.45, -1.0, -0.6, YARD_Z, YARD_Z + 0.12)  # wheel stops
    box("yellow", 0.25, 0.45, 0.6, 1.0, YARD_Z, YARD_Z + 0.12)


for d in DOORS:
    if d["id"] in LORRY_DOCKS:
        lorry(d)
M["line_yellow"] = M["yellow"]
boxes("lorries", lorry_box, C["Yard"])
_wme = bpy.data.meshes.new("lorry_wheels")
_wbm = bmesh.new()
for (wx, wy, wz), ax in LORRY_WHEELS:
    rot = Matrix.Rotation(math.pi / 2, 4, "Y" if ax == "X" else "X")
    for r_, w_, mi in ((0.5, 0.3, 0), (0.28, 0.32, 1)):  # tyre, then the hub just proud of it
        res = bmesh.ops.create_cone(_wbm, cap_ends=True, segments=24, radius1=r_, radius2=r_, depth=w_,
                                    matrix=Matrix.Translation((wx, wy, wz)) @ rot)
        for f in {f for v in res["verts"] for f in v.link_faces}:
            f.material_index = mi
_wbm.to_mesh(_wme)
_wbm.free()
for mt in ("black", "steel"):
    _wme.materials.append(M[mt])
C["Yard"].objects.link(bpy.data.objects.new("lorry_wheels", _wme))
for d in DOORS:
    # D02 / D05 are being unloaded: their stacked parcel wall and the unloaders are built by stations.py (flow
    # stage), because the parcels the workers lift become flow parcels on the booms
    if d["id"] in ("D08", "D11"):  # being loaded: cages already inside
        cx = d["centre"][0]
        for k in range(4):
            roll_cage(f"cage_truck_{d['id']}_{k}", cx + (k % 2 - 0.5) * 0.85, BD + 6.2 - 0.95 * (k // 2), 0.0,
                      fill="full")
for k in range(3):  # bags just unloaded at the inbound dock
    place(random.choice(SLUMPED), f"sack_unloaded_{k}", (2.2 + 0.7 * k, 13.0 + random.uniform(-0.2, 0.2), 0.0),
          random.uniform(0, 3.1))

# ------------------------------------------------------------------------------------------------ lights
lamps, housings, chains = [], [], []
HIGHBAY_Z = 8.6  # hung on chains below the trusses
for x in [3 + 6 * k for k in range(10)]:
    for y in [3.5 + 6.6 * k for k in range(6)]:
        dead = 8 <= x <= 16 and y >= 33  # the store's corner light is out (realism note for Z11)
        ld = bpy.data.lights.new(f"highbay_{x}_{y:.0f}", "SPOT")  # LED high-bay: 75° beam -> pools of light
        ld.spot_size, ld.spot_blend = math.radians(75), 0.85  # tighter optics: distinct pools, darker between
        ld.shadow_soft_size = 0.25
        ld.energy = 0.0 if dead else 165.0  # calibrated in the dressing pass
        ld.color = (1.0, 0.95, 0.88)
        lo = bpy.data.objects.new(ld.name, ld)
        lo.location = (x, y, HIGHBAY_Z - 0.02)
        C["Lights"].objects.link(lo)
        chains.append(mat_aabb(x - 0.01, y - 0.01, HIGHBAY_Z + 0.12, x + 0.01, y + 0.01, EAVES - 1.2))
        housings.append(mat_aabb(x - 0.28, y - 0.28, HIGHBAY_Z + 0.02, x + 0.28, y + 0.28, HIGHBAY_Z + 0.12))
        if not dead:
            lamps.append(mat_aabb(x - 0.25, y - 0.25, HIGHBAY_Z, x + 0.25, y + 0.25, HIGHBAY_Z + 0.02))
boxes("highbay_fixtures", {"lamp": lamps, "frame": housings, "steel": chains}, C["Lights"])
for k, x in enumerate((56.0, 58.4)):
    ld = bpy.data.lights.new(f"office_{k}", "AREA")
    ld.shape, ld.size, ld.size_y, ld.energy = "RECTANGLE", 1.2, 0.3, 120
    lo = bpy.data.objects.new(ld.name, ld)
    lo.location = (x, 3.0, 2.95)
    C["Lights"].objects.link(lo)
sun_d = bpy.data.lights.new("sun_overcast", "SUN")
sun_d.energy, sun_d.angle = 2.5, math.radians(25)  # soft: overcast Klang Valley afternoon
sun = bpy.data.objects.new("sun_overcast", sun_d)
sun.rotation_euler = (math.radians(55), 0, math.radians(215))
C["Lights"].objects.link(sun)
world = bpy.data.worlds.new("overcast_sky")
if hasattr(world, "use_nodes"):
    world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (*srgb("#c9d3dc"), 1)
bg.inputs["Strength"].default_value = 0.6
scene.world = world

# ------------------------------------------------------------------------------------------------ CCTV cameras
housing = {"camera": [], "frame": []}
CAMS = {}
for cs in SPEC["cameras"]:
    x, y = cs["position_m"]
    hgt, yaw, tilt = cs["height_m"], cs["heading_deg"], cs["tilt_down_deg"]
    cd = bpy.data.cameras.new(cs["id"])
    cd.sensor_fit = "HORIZONTAL"
    cd.angle_x = math.radians(cs["hfov_deg"])
    cd.clip_start, cd.clip_end = 0.05, 150.0
    co = bpy.data.objects.new(cs["id"], cd)
    co.location = (x, y, hgt)
    co.rotation_euler = (math.radians(90 - tilt), 0, math.radians(yaw - 90))
    co["question"] = cs["question"]
    co["detail_target"] = cs["detail_target"]
    C["CCTV"].objects.link(co)
    CAMS[cs["id"]] = co
    fx_, fy_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    hx, hy = x - 0.14 * fx_, y - 0.14 * fy_  # housing sits just behind the lens, out of its own view
    housing["camera"].append(mat_aabb(hx - 0.09, hy - 0.09, hgt - 0.05, hx + 0.09, hy + 0.09, hgt + 0.08))
    if "drop-pole" in cs["mount"]:
        housing["frame"].append(mat_aabb(hx - 0.03, hy - 0.03, hgt + 0.08, hx + 0.03, hy + 0.03, EAVES - 0.7))
    else:  # bracket arm back to the nearest wall / column
        housing["frame"].append(mat_aabb(hx - 0.03, hy - 0.03, hgt + 0.08, hx + 0.03, hy + 0.03, hgt + 0.4))
boxes("cctv_housings", housing, C["CCTV"])

# ------------------------------------------------------------------------------------------------ merge static clutter
def baked_atlas_material(name):
    """Label / sticker material for merged meshes: the tile is already in the UVs (no per-object attribute)."""
    m = bpy.data.materials.new(name)
    if hasattr(m, "use_nodes"):
        m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    b.inputs["Roughness"].default_value = 0.45
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = ATLAS
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    return m


M["parcel_label_baked"] = baked_atlas_material("parcel_label_baked")
M["parcel_sticker_baked"] = baked_atlas_material("parcel_sticker_baked")


def merge_static(objs, name, collection):
    """Bake many small static objects (linked duplicates, text) into ONE mesh: transforms, per-object material
    overrides and each parcel's label / sticker tile (shifted into the UVs). Same look, far fewer draw calls and
    shadow casters. Returns the merged object; the originals are removed."""
    objs = [o for o in objs if o.type in ("MESH", "FONT") and o.name in bpy.data.objects]
    if not objs:
        return None
    dg = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    mats, index = [], {}

    def mat_idx(m):
        key = m.name if m else "_none_"
        if key not in index:
            index[key] = len(mats)
            mats.append(m)
        return index[key]
    for o in objs:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        slots = [s.material for s in o.material_slots] or [None]
        tile = o.get("label_tile")
        sticker = o.get("sticker_tile")
        remap = []
        for m in slots:
            if m is not None and m.name == "parcel_label":
                m = M["parcel_label_baked"]
            elif m is not None and m.name == "parcel_sticker":
                m = M["parcel_sticker_baked"]
            remap.append(mat_idx(m))
        v0, f0 = len(bm.verts), len(bm.faces)
        bm.from_mesh(me)
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        mw = o.matrix_world.copy()
        for v in bm.verts[v0:]:
            v.co = mw @ v.co
        uvl = bm.loops.layers.uv.active
        for f in bm.faces[f0:]:
            src = f.material_index if f.material_index < len(slots) else 0
            orig = slots[src]
            f.material_index = remap[src]
            t = None
            if orig is not None and orig.name == "parcel_label" and tile is not None:
                t = int(tile)
            elif orig is not None and orig.name == "parcel_sticker" and sticker is not None:
                t = int(sticker)
            if t is not None and uvl is not None:
                col, row = t % L_COLS, t // L_COLS
                for loop in f.loops:
                    u, v = loop[uvl].uv
                    loop[uvl].uv = ((u + col) / L_COLS, (v + (L_ROWS - 1 - row)) / L_ROWS)
        ev.to_mesh_clear()
    out = bpy.data.meshes.new(name)
    bm.to_mesh(out)
    bm.free()
    for m in mats:
        out.materials.append(m)
    ob = bpy.data.objects.new(name, out)
    collection.objects.link(ob)
    for o in objs:
        bpy.data.objects.remove(o, do_unlink=True)
    return ob


_static_parcels = [o for o in scene.objects if "parcel_id" in o.keys()]
merge_static(_static_parcels, "parcels_static_merged", C["Clutter"])
merge_static([o for o in scene.objects if o.name.startswith("cage_") and ("_sack" in o.name or "_gate" in o.name
                                                                          or "_tag" in o.name or "_padlock" in o.name)],
             "cage_loads_merged", C["Clutter"])
merge_static([o for o in scene.objects if o.type == "FONT"], "text_signs_merged", C["Signs"])
merge_static([o for o in scene.objects if o.name.startswith("sack_") or o.name.startswith("pallet_consignment")],
             "sacks_merged", C["Clutter"])

# ------------------------------------------------------------------------------------------------ render settings
engines = bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys()
scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
r_ = SPEC["cameras"][0]["resolution"]
scene.render.resolution_x, scene.render.resolution_y = r_
scene.render.resolution_percentage = 100
scene.render.fps = SPEC["cameras"][0]["fps"]
scene.view_settings.view_transform = "Standard"
for attr, val in (("taa_render_samples", args.samples), ("use_raytracing", False), ("use_gtao", True)):
    if hasattr(scene.eevee, attr):
        setattr(scene.eevee, attr, val)
scene.camera = CAMS["CAM_07"]
scene["spoor_label"] = "synthetic footage of a fictional hub"

# ------------------------------------------------------------------------------------------------ save + stats
out = Path(args.out).resolve()  # Blender resolves relative render paths against the drive root; use absolute
_truth = out.parent / "truth"
_truth.mkdir(parents=True, exist_ok=True)
(_truth / "parcels_registry.json").write_text(json.dumps({"note": "render-side truth: which waybill ID sits where; "
                                                          "Spoor runtime never reads this", "parcels": PARCELS},
                                                         indent=1), encoding="utf-8")
out.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
deps = bpy.context.evaluated_depsgraph_get()
tris = 0
for o in scene.objects:
    if o.type == "MESH":
        me = o.evaluated_get(deps).to_mesh()
        tris += sum(len(p.vertices) - 2 for p in me.polygons)
        o.evaluated_get(deps).to_mesh_clear()
print(json.dumps({"saved": str(out), "objects": len(scene.objects), "triangles": tris,
                  "lights": sum(1 for o in scene.objects if o.type == "LIGHT"), "cameras": len(CAMS)}), flush=True)

if args.preview:
    pdir = Path(args.preview_dir).resolve() if args.preview_dir else out.parent / "preview"
    pdir.mkdir(parents=True, exist_ok=True)
    scene.render.image_settings.file_format = "PNG"
    keep_awake(True)
    try:
        for cid in [c.strip() for c in args.preview.split(",") if c.strip()]:
            scene.camera = CAMS[cid]
            scene.render.filepath = str(pdir / f"{cid}.png")
            t = time.perf_counter()
            bpy.ops.render.render(write_still=True)
            print(json.dumps({"preview": cid, "seconds": round(time.perf_counter() - t, 2)}), flush=True)
    finally:
        keep_awake(False)
