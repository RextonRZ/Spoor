"""Dressing pass (pass 2) for the whole hub, following the reference pack's realism checklist: textured surfaces,
uneven high-bays (one dim, one off), cooler/brighter docks, hard daylight through the open doors, floor wear (tyre
tracks heaviest where forklifts turn, oil at the docks, dust in corners, scuffed lines), clutter and CC0 props in
work areas with walkways kept clear, extra signs, and one camera mounted 1.5 deg off level.

  blender -b --factory-startup assets/hub/build/hub.blend -P assets/hub/dress_hub.py -- ^
      --save assets/hub/build/hub_dressed.blend [--preview CAM_01,CAM_09 --preview-dir <dir>] [--exposure 2.2]

Reads hub_spec.json (design) and render_truth.json (RENDER SIDE ONLY: actual mount roll). Spoor's runtime never
reads render_truth. All props are CC0 (Poly Haven, listed in CREDITS.md); no AI-generated models or images.
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
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--save", default="")
ap.add_argument("--preview", default="")
ap.add_argument("--preview-dir", default="")
ap.add_argument("--exposure", type=float, default=1.7)
ap.add_argument("--samples", type=int, default=4)  # 4 vs 8 indistinguishable after the CCTV pass; ~43 % faster
ap.add_argument("--raytrace", type=int, default=1)
ap.add_argument("--pct", type=int, default=100)
ap.add_argument("--repeat", type=int, default=1)
ap.add_argument("--people", type=int, default=1)
ap.add_argument("--no-shadows", action="store_true")
ap.add_argument("--shadow-res", type=float, default=0.05)  # metres per shadow texel at the light
ap.add_argument("--shadow-steps", type=int, default=2)
ap.add_argument("--shadow-radius", type=float, default=22.0)
args = ap.parse_args(argv)

BUILD = Path(bpy.path.abspath("//")).resolve()
SPEC = json.loads((BUILD.parent / "hub_spec.json").read_text(encoding="utf-8"))
TRUTH = json.loads((BUILD.parent / "render_truth.json").read_text(encoding="utf-8"))  # render side only
TP = BUILD / "third_party"
LM_PER_W = 683.0
HIGHBAY_LM = 24000  # LED high-bay, 75° beam (same lumens as a wide one: brighter below, darker between)
# Blender rates a spot by the point light it would be: P = I * 4π / 683, with I = lm / beam solid angle
SPOT_W = HIGHBAY_LM / (2 * math.pi * (1 - math.cos(math.radians(37.5)))) * 4 * math.pi / LM_PER_W  # ≈ 340 W
SHADOW_RADIUS = 18.0
random.seed(31)
scene = bpy.context.scene
BW, BD = SPEC["building"]["footprint_m"]
if os.name == "nt":
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)

dress = bpy.data.collections.new("Dressing")
scene.collection.children.link(dress)


# ------------------------------------------------------------------------------------------------ circulation guard
def _rect(r, pad=0.0):
    return (r[0] - pad, r[1] - pad, r[2] + pad, r[3] + pad)


CI = SPEC["circulation"]
KEEP_CLEAR = [_rect(w["rect_m"]) for w in CI["walkways"]] + [_rect(z["rect_m"]) for z in CI["zebra_crossings"]]
hw = CI["forklift_lane"]["width_m"] / 2
for (ax, ay), (bx, by) in zip(CI["forklift_lane"]["centreline_m"], CI["forklift_lane"]["centreline_m"][1:]):
    KEEP_CLEAR.append((min(ax, bx) - hw, min(ay, by) - hw, max(ax, bx) + hw, max(ay, by) + hw))
skipped = []


def clear(x, y, radius):
    return not any(r[0] - radius < x < r[2] + radius and r[1] - radius < y < r[3] + radius for r in KEEP_CLEAR)


# ------------------------------------------------------------------------------------------------ materials
def _nodes(m):
    return m.node_tree.nodes, m.node_tree.links


def textured(mat_name, tex_id, scale_m, metal=None, tint=None, rough_mul=1.0, saturation=1.0):
    """Rebuild a material as box-projected Poly Haven PBR (diffuse, GL normal, roughness, optional metal)."""
    m = bpy.data.materials.get(mat_name)
    folder = TP / tex_id
    if m is None or not folder.exists():
        print(f"skip material {mat_name}")
        return None
    nodes, links = _nodes(m)
    for n in list(nodes):
        nodes.remove(n)
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    tc = nodes.new("ShaderNodeTexCoord")
    mp = nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 / scale_m,) * 3
    links.new(tc.outputs["Object"], mp.inputs["Vector"])

    def img(suffix, colour):
        f = next(iter(sorted(folder.rglob(f"*_{suffix}_*k.jpg"))), None)
        if f is None:
            return None
        n = nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(str(f), check_existing=True)
        n.image.colorspace_settings.name = "sRGB" if colour else "Non-Color"
        n.projection, n.projection_blend = "BOX", 0.25
        links.new(mp.outputs["Vector"], n.inputs["Vector"])
        return n

    d = img("diff", True)
    col_out = d.outputs["Color"] if d else None
    if d and saturation != 1.0:  # e.g. the cladding photo is painted red-brown; hub walls inside are grey
        hs = nodes.new("ShaderNodeHueSaturation")
        hs.inputs["Saturation"].default_value = saturation
        links.new(col_out, hs.inputs["Color"])
        col_out = hs.outputs["Color"]
    if d and tint:
        mix = nodes.new("ShaderNodeMix")
        mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        mix.inputs["B"].default_value = (*tint, 1)
        links.new(col_out, mix.inputs["A"])
        col_out = mix.outputs["Result"]
    if col_out:
        links.new(col_out, bsdf.inputs["Base Color"])
    r = img("rough", False)
    if r:
        mr = nodes.new("ShaderNodeMath")
        mr.operation, mr.inputs[1].default_value = "MULTIPLY", rough_mul
        links.new(r.outputs["Color"], mr.inputs[0])
        links.new(mr.outputs["Value"], bsdf.inputs["Roughness"])
    nm = img("nor_gl", False)
    if nm:
        nmap = nodes.new("ShaderNodeNormalMap")
        nmap.inputs["Strength"].default_value = 0.6
        links.new(nm.outputs["Color"], nmap.inputs["Color"])
        links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    mt = img("metal", False)
    if mt:
        links.new(mt.outputs["Color"], bsdf.inputs["Metallic"])
    elif metal is not None:
        bsdf.inputs["Metallic"].default_value = metal
    return m


def grime(mat_name, scale_m, dark=0.72, rough_add=0.15):
    """Large soft blotches of dirt over whatever colour the material has (dust, traffic grime)."""
    m = bpy.data.materials.get(mat_name)
    if m is None:
        return
    nodes, links = _nodes(m)
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    base_link = next((lk for lk in m.node_tree.links if lk.to_socket == bsdf.inputs["Base Color"]), None)
    tc = nodes.new("ShaderNodeTexCoord")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1 / scale_m
    noise.inputs["Detail"].default_value = 6
    links.new(tc.outputs["Object"], noise.inputs["Vector"])
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = 0.45, 0.75
    ramp.color_ramp.elements[0].color = (1, 1, 1, 1)
    ramp.color_ramp.elements[1].color = (dark, dark * 0.97, dark * 0.92, 1)
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    mix = nodes.new("ShaderNodeMix")
    mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
    mix.inputs["Factor"].default_value = 1.0
    if base_link:
        links.new(base_link.from_socket, mix.inputs["A"])
    else:
        mix.inputs["A"].default_value = bsdf.inputs["Base Color"].default_value
    links.new(ramp.outputs["Color"], mix.inputs["B"])
    links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    if not any(lk.to_socket == bsdf.inputs["Roughness"] for lk in m.node_tree.links):
        bsdf.inputs["Roughness"].default_value = min(1.0, bsdf.inputs["Roughness"].default_value + rough_add)


def worn_paint(mat_name, floor_rgb=(0.11, 0.105, 0.095), amount=0.5, scale_m=0.35):
    """Scuffed, faded floor paint: small patches where the concrete shows through, rougher. Applied to floor-marking
    COPIES only, so rails and handrails that share the paint stay intact."""
    m = bpy.data.materials.get(mat_name)
    if m is None:
        return
    nodes, links = _nodes(m)
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    b0 = bsdf.inputs["Base Color"].default_value
    base = (b0[0] * 0.7 + 0.03, b0[1] * 0.7 + 0.03, b0[2] * 0.7 + 0.03, 1.0)  # duller, dirtier paint
    tc = nodes.new("ShaderNodeTexCoord")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1 / scale_m
    noise.inputs["Detail"].default_value = 8
    links.new(tc.outputs["Object"], noise.inputs["Vector"])
    ramp = nodes.new("ShaderNodeValToRGB")
    lo = 0.5 - amount * 0.35  # amount 0..1: share of the line worn through
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = lo, lo + 0.08
    ramp.color_ramp.elements[0].color = (*floor_rgb, 1)
    ramp.color_ramp.elements[1].color = base
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.75


textured("floor_epoxy_concrete", "smooth_concrete_floor", 2.5, metal=0.0, tint=(0.78, 0.8, 0.8), rough_mul=0.5,
         saturation=0.35)  # grey sealed epoxy: light pools glint
grime("floor_epoxy_concrete", 6.0, dark=0.7)
textured("cladding_steel", "box_profile_metal_sheet", 2.0, tint=(0.95, 0.97, 1.0), saturation=0.08)
textured("galvanised_steel", "galvanized_sheet_metal", 1.5)
grime("galvanised_steel", 1.5, dark=0.85)
textured("painted_frame", "painted_metal_shutter", 1.5, metal=0.3, tint=(0.55, 0.6, 0.68))
grime("painted_frame", 2.0, dark=0.8)
textured("reject_red", "painted_metal_shutter", 1.2, metal=0.2, tint=(0.75, 0.12, 0.1))
# cartons: plain brown kraft, procedural (box-projecting the Poly Haven box's UV atlas printed unwrapped flaps
# and arrows across every carton - QA 2026-10-30). Mottled kraft colour + faint flute ribs + light scuffs.


def kraft(mat_name, rgb, var=0.12):
    m = bpy.data.materials.get(mat_name) or bpy.data.materials.new(mat_name)
    nodes, links = _nodes(m)
    for n in list(nodes):
        nodes.remove(n)
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    tc = nodes.new("ShaderNodeTexCoord")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 9.0
    noise.inputs["Detail"].default_value = 4.0
    links.new(tc.outputs["Object"], noise.inputs["Vector"])
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*(c * (1 - var) for c in rgb), 1)
    ramp.color_ramp.elements[1].color = (*(min(1.0, c * (1 + var)) for c in rgb), 1)
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.86
    bsdf.inputs["Metallic"].default_value = 0.0
    wave = nodes.new("ShaderNodeTexWave")  # corrugation flutes, very faint
    wave.inputs["Scale"].default_value = 160.0
    links.new(tc.outputs["Object"], wave.inputs["Vector"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.04
    links.new(wave.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    m.diffuse_color = (*rgb, 1)
    return m


kraft("cardboard", (0.40, 0.27, 0.15))
kraft("cardboard_white", (0.74, 0.72, 0.68), var=0.05)
grime("cardboard", 0.3, dark=0.88)
grime("carrier", 1.0, dark=0.8)
grime("pallet_wood", 0.4, dark=0.7)


def film_wrinkles(mat_name):
    """Stretch film: horizontal wrap bands and creases (noise stretched along X/Y, tight along Z) as a bump."""
    m = bpy.data.materials.get(mat_name)
    if m is None:
        return
    nodes, links = _nodes(m)
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    tc, mp = nodes.new("ShaderNodeTexCoord"), nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (3.0, 3.0, 28.0)
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Detail"].default_value = 6
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.45
    links.new(tc.outputs["Object"], mp.inputs["Vector"])
    links.new(mp.outputs["Vector"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


film_wrinkles("stretch_wrap")


def woven(mat_name, tape_mm=3.0):
    """Woven PP sack: two crossed wave patterns make the tape weave (bump + slight colour beat), plus creases."""
    m = bpy.data.materials.get(mat_name)
    if m is None:
        return
    nodes, links = _nodes(m)
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    tc = nodes.new("ShaderNodeTexCoord")
    waves = []
    for axis in ("X", "Y"):
        w = nodes.new("ShaderNodeTexWave")
        w.wave_type, w.bands_direction = "BANDS", axis
        w.inputs["Scale"].default_value = 1000.0 / tape_mm / 6.0
        w.inputs["Distortion"].default_value = 0.4
        links.new(tc.outputs["Object"], w.inputs["Vector"])
        waves.append(w)
    mx = nodes.new("ShaderNodeMath")
    mx.operation = "MULTIPLY"
    links.new(waves[0].outputs["Fac"], mx.inputs[0])
    links.new(waves[1].outputs["Fac"], mx.inputs[1])
    crease = nodes.new("ShaderNodeTexNoise")
    crease.inputs["Scale"].default_value = 6.0
    crease.inputs["Detail"].default_value = 8
    links.new(tc.outputs["Object"], crease.inputs["Vector"])
    add = nodes.new("ShaderNodeMath")
    add.operation = "ADD"
    links.new(mx.outputs["Value"], add.inputs[0])
    links.new(crease.outputs["Fac"], add.inputs[1])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    links.new(add.outputs["Value"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    base = tuple(bsdf.inputs["Base Color"].default_value)
    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = base
    mix.inputs["B"].default_value = (base[0] * 0.8, base[1] * 0.8, base[2] * 0.8, 1)
    links.new(mx.outputs["Value"], mix.inputs["Factor"])
    links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.7


for m_ in ("woven_sack", "woven_sack_blue", "woven_sack_grey"):
    woven(m_)
    grime(m_, 0.5, dark=0.78)  # handled, dragged across the floor
film_wrinkles("stretch_wrap_thin")
for o in scene.objects:  # woven sacks: soften the lofted shapes
    if o.type == "MESH" and (o.name.startswith("sack_") or "_bag" in o.name):
        sub = o.modifiers.new("soft", "SUBSURF")
        sub.levels = sub.render_levels = 1


# ------------------------------------------------------------------------------------------------ floor decals
def decal_material(name, rgb, rough, mask="strip", alpha_max=0.85, noise_scale=3.0):
    """Alpha decal: UV mask (strip = soft across, fades at the ends; blob = radial; edge = strongest at v=1)
    multiplied by patchy noise, so no decal has a clean rectangular outline."""
    m = bpy.data.materials.new(name)
    if hasattr(m, "use_nodes"):
        m.use_nodes = True
    if hasattr(m, "surface_render_method"):
        m.surface_render_method = "DITHERED"
    nodes, links = _nodes(m)
    bsdf = nodes.get("Principled BSDF") or nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = rough
    uv = nodes.new("ShaderNodeUVMap")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(uv.outputs["UV"], sep.inputs["Vector"])

    def math_node(op, a, b=None):
        n = nodes.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                links.new(v, n.inputs[i])
        return n.outputs[0]

    u, v = sep.outputs["X"], sep.outputs["Y"]
    if mask == "blob":
        du = math_node("SUBTRACT", u, 0.5)
        dv = math_node("SUBTRACT", v, 0.5)
        r2 = math_node("ADD", math_node("MULTIPLY", du, du), math_node("MULTIPLY", dv, dv))
        m_ = math_node("MAXIMUM", math_node("SUBTRACT", 1.0, math_node("MULTIPLY", r2, 4.0)), 0.0)
    elif mask == "edge":
        m_ = math_node("POWER", v, 2.0)
    else:
        across = math_node("MULTIPLY", math_node("MULTIPLY", v, math_node("SUBTRACT", 1.0, v)), 4.0)
        along = math_node("MINIMUM", math_node("MULTIPLY", math_node("MULTIPLY", u, math_node("SUBTRACT", 1.0, u)),
                                                           12.0), 1.0)
        m_ = math_node("MULTIPLY", across, along)
    tc = nodes.new("ShaderNodeTexCoord")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = noise_scale
    noise.inputs["Detail"].default_value = 8
    links.new(tc.outputs["Object"], noise.inputs["Vector"])
    patch = math_node("MAXIMUM", math_node("MULTIPLY", math_node("SUBTRACT", noise.outputs["Fac"], 0.35), 3.0), 0.0)
    alpha = math_node("MINIMUM", math_node("MULTIPLY", math_node("MULTIPLY", m_, patch), alpha_max), alpha_max)
    links.new(alpha, bsdf.inputs["Alpha"])
    return m


def decals(name, quads, mat, z=0.006):
    """quads: [(cx, cy, length, width, angle_rad)] -> one object, UV u along length, v across width."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new()
    for cx, cy, ln, wd, a in quads:
        ca, sa = math.cos(a), math.sin(a)
        corners = [(-ln / 2, -wd / 2, 0, 0), (ln / 2, -wd / 2, 1, 0), (ln / 2, wd / 2, 1, 1), (-ln / 2, wd / 2, 0, 1)]
        vs = [bm.verts.new((cx + x * ca - y * sa, cy + x * sa + y * ca, z)) for x, y, _, _ in corners]
        f = bm.faces.new(vs)
        for loop, (_, _, uu, vv) in zip(f.loops, corners):
            loop[uvl].uv = (uu, vv)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    dress.objects.link(ob)
    return ob


tyre_mat = decal_material("decal_tyre", (0.05, 0.05, 0.05), 0.6, "strip", 0.7, 4.0)
smear_mat = decal_material("decal_turn_smear", (0.07, 0.065, 0.06), 0.55, "blob", 0.55, 1.5)
oil_mat = decal_material("decal_oil", (0.02, 0.02, 0.018), 0.15, "blob", 0.8, 2.0)
dust_mat = decal_material("decal_dust", (0.22, 0.2, 0.17), 0.95, "edge", 0.7, 1.2)

lane = CI["forklift_lane"]["centreline_m"]
tracks, smears = [], []
for (ax, ay), (bx, by) in zip(lane, lane[1:]):
    ang = math.atan2(by - ay, bx - ax)
    ln = math.hypot(bx - ax, by - ay)
    nx, ny = -math.sin(ang), math.cos(ang)
    for off in (-0.48, 0.48):  # two wheel tracks
        tracks.append(((ax + bx) / 2 + nx * off, (ay + by) / 2 + ny * off, ln, 0.16, ang))
for x, y in lane[1:-1]:  # forklifts scrub the floor most where they turn
    smears.append((x, y, 3.4, 3.4, random.uniform(0, math.pi)))
OPEN_DOCKS = {"D02", "D03", "D05", "D08", "D09", "D11"}  # same as build_hub.py
oils = []
for d in SPEC["building"]["doors"]:
    if d["kind"] != "dock":
        continue
    cx, cy = d["centre"]
    inward = (1, 0) if d["wall"] == "W" else (0, -1)
    if d["id"] in OPEN_DOCKS:  # pallet-jack tracks from the door into the hall
        for off in (-0.35, 0.35):
            px = cx + inward[0] * 3.2 + (0 if d["wall"] == "W" else off)
            py = cy + inward[1] * 3.2 + (off if d["wall"] == "W" else 0)
            tracks.append((px, py, 5.0, 0.12, 0.0 if d["wall"] == "W" else math.pi / 2))
    for _ in range(random.randint(1, 3)):  # oil drips where lorries and jacks stand
        size = random.uniform(0.5, 1.4)
        oils.append((cx + inward[0] * random.uniform(0.6, 2.5) + random.uniform(-1.2, 1.2) * (inward[1] != 0),
                     cy + inward[1] * random.uniform(0.6, 2.5) + random.uniform(-1.2, 1.2) * (inward[0] != 0),
                     size, size * random.uniform(0.6, 1.0), random.uniform(0, math.pi)))
decals("floor_tyre_tracks", tracks, tyre_mat)
decals("floor_turn_smears", smears, smear_mat, z=0.005)
decals("floor_oil", oils, oil_mat, z=0.007)
dust = [(BW / 2, 0.55, BW - 0.4, 0.7, math.pi), (BW / 2, BD - 0.55, BW - 0.4, 0.7, 0.0),
        (0.55, BD / 2, BD - 0.4, 0.7, math.pi / 2), (BW - 0.55, BD / 2, BD - 0.4, 0.7, -math.pi / 2)]
decals("floor_dust_edges", dust, dust_mat, z=0.004)  # v = 1 at the wall side: dust collects in corners
wall_grime_mat = decal_material("decal_wall_grime", (0.12, 0.11, 0.09), 0.95, "edge", 0.75, 2.5)


def wall_grime(height=0.7):
    """Dirt splashed up the bottom of every inside wall (strongest at the floor), skipping door openings."""
    me = bpy.data.meshes.new("wall_base_grime")
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new()
    doors = SPEC["building"]["doors"]
    for side, fixed, length, inward in (("W", 0.2 + 0.012, BD, 1), ("E", BW - 0.2 - 0.012, BD, -1),
                                        ("S", 0.2 + 0.012, BW, 1), ("N", BD - 0.2 - 0.012, BW, -1)):
        horiz = side in ("S", "N")
        cuts = sorted((d["centre"][0 if horiz else 1] - d["width"] / 2, d["centre"][0 if horiz else 1] + d["width"] / 2)
                      for d in doors if d["wall"] == side)
        cur, spans = 0.3, []
        for a, b in cuts + [(length - 0.3, length - 0.3)]:
            if a > cur:
                spans.append((cur, a))
            cur = max(cur, b)
        for a, b in spans:
            pts = [(a, 0.0), (b, 0.0), (b, height), (a, height)]
            vs = [bm.verts.new((u, fixed, z) if horiz else (fixed, u, z)) for u, z in pts]
            f = bm.faces.new(vs)
            for loop, (u, z) in zip(f.loops, pts):
                loop[uvl].uv = ((u - a) / max(b - a, 1e-6), 1.0 - z / height)  # v = 1 at the floor
    bm.to_mesh(me)
    bm.free()
    me.materials.append(wall_grime_mat)
    dress.objects.link(bpy.data.objects.new("wall_base_grime", me))


wall_grime()


# ------------------------------------------------------------------------------------------------ CC0 props
_src_cache = {}


def prop(model_id, x, y, rot_deg=0.0, z=0.0, scale=1.0, radius=0.4, allow_on_walkway=False):
    """Place a Poly Haven glTF (imported once, then linked copies). Refuses spots on walkways / the lane."""
    if not allow_on_walkway and not clear(x, y, radius):
        skipped.append(f"{model_id}@({x},{y})")
        return None
    if model_id not in _src_cache:
        f = next(iter(sorted((TP / model_id).glob("*.gltf"))), None)
        if f is None:
            skipped.append(f"{model_id} (not downloaded)")
            return None
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(f))
        new = [o for o in bpy.data.objects if o not in before]
        holder = bpy.data.objects.new(f"src_{model_id}", None)
        dress.objects.link(holder)
        for o in new:
            for c in o.users_collection:
                c.objects.unlink(o)
            dress.objects.link(o)
            if o.parent is None:
                o.parent = holder
        holder.hide_render = holder.hide_viewport = True
        for o in new:
            o.hide_render = o.hide_viewport = True
        _src_cache[model_id] = (holder, new)
    holder, parts = _src_cache[model_id]
    root = bpy.data.objects.new(f"{model_id}_{len(dress.objects)}", None)
    dress.objects.link(root)
    root.location, root.rotation_euler, root.scale = (x, y, z), (0, 0, math.radians(rot_deg)), (scale,) * 3
    mapping = {holder: root}
    for o in parts:  # copy the hierarchy, sharing mesh data
        c = o.copy()
        c.hide_render = c.hide_viewport = False
        dress.objects.link(c)
        mapping[o] = c
    for o in parts:
        mapping[o].parent = mapping.get(o.parent, root)
    return root


# exception bench (Z08): crooked tool cart, chair, cabinet
prop("tool_cart", 28.1, 20.5, 14)
prop("plastic_monobloc_chair_01", 25.7, 20.6, 200)
prop("drawer_cabinet", 23.3, 21.9, 90, radius=0.25)
# bag opening / induction (Z02, Z03): chairs, shelves, empty-bag piles
prop("plastic_monobloc_chair_01", 9.6, 25.5, 30)
prop("plastic_monobloc_chair_01", 10.5, 10.65, 200)  # beside the induct station, not alone in the aisle
# (no shelving in the bag-opening area: it read as a big table blocking CAM_01; shelving lives in the store)
prop("compost_bags", 12.2, 27.6, 20)
prop("compost_bags", 51.0, 21.4, -35)
prop("tool_cart", 22.6, 12.4, 92)
# empty-cage / bag store (Z11, outside the blind corner) and the office
for k, (sx_, sy_) in enumerate(SPEC["fixtures"]["store_shelves_m"]):
    prop("steel_frame_shelves_02" if k % 2 else "steel_frame_shelves_01", sx_, sy_, 0)
prop("metal_office_desk", 57.0, 2.2, 0, radius=0.2)
prop("plastic_monobloc_chair_01", 57.0, 3.1, 180, radius=0.2)
prop("drawer_cabinet", 59.2, 5.3, 180, radius=0.2)
prop("steel_frame_shelves_01", 59.3, 2.8, 90, radius=0.2)
prop("mounted_fluorescent_lights", 57.2, 3.0, 90, z=2.95, radius=0.0)
# fire extinguishers: by every exit and on the interior columns (wall/column side of the walkways)
for x, y in ((31.0, 0.3), (47.0, 0.3), (12.0, 24.68), (24.0, 24.68), (36.0, 24.68), (48.0, 24.68), (0.4, 13.0)):
    prop("korean_fire_extinguisher_01", x, y, random.uniform(0, 360), radius=0.0, allow_on_walkway=True)
prop("korean_fire_extinguisher_01", 59.65, 29.0, 180, radius=0.0, allow_on_walkway=True)
# yard
for x, y, r in ((28.0, 49.0, 0), (50.0, 49.0, 0), (-14.0, 31.0, 90)):
    prop("concrete_road_barrier", x, y, r, z=-1.2)
# cardboard boxes: on benches, beside pallets, staged at outbound doors, by chute ends
spots = [(random.uniform(6.4, 7.8), random.uniform(19.2, 26.8), 0.9) for _ in range(5)]
spots += [(random.uniform(8.2, 15.0), random.uniform(5.2, 6.3), 0.0) for _ in range(3)]
spots += [(random.uniform(26.0, 52.0), random.uniform(36.8, 38.6), 0.0) for _ in range(6)]
spots += [(random.uniform(30.5, 49.0), random.uniform(21.7, 22.1), 0.0) for _ in range(3)]
for x, y, z in spots:
    prop("cardboard_box_01", x, y, random.uniform(0, 360), z=z, scale=random.uniform(0.55, 1.1), radius=0.2)

# procedural clutter: standing fans, overhead cable tray, torn tape, wrapped pallets at the outbound queue
clutter = {}


def add_box(mat, x0, y0, z0, x1, y1, z1):
    clutter.setdefault(mat, []).append((x0, y0, z0, x1, y1, z1))


for fx, fy in ((9.8, 19.6), (13.6, 11.8), (49.9, 22.4)):  # standing fans (crude, hot-climate essential)
    if clear(fx, fy, 0.3):
        add_box("black_rubber", fx - 0.25, fy - 0.25, 0, fx + 0.25, fy + 0.25, 0.05)
        add_box("galvanised_steel", fx - 0.02, fy - 0.02, 0.05, fx + 0.02, fy + 0.02, 1.25)
        add_box("black_rubber", fx - 0.3, fy - 0.08, 1.05, fx + 0.3, fy + 0.08, 1.65)
add_box("galvanised_steel", 22.3, 10.9, 1.8, 22.5, 11.1, 4.6)  # DWS cabinet cable riser + tray to the column
add_box("galvanised_steel", 22.25, 10.9, 4.5, 22.55, 25.0, 4.6)
for _ in range(14):  # torn tape scraps near work benches and the bagging aisle
    x, y = random.choice([(random.uniform(6, 9), random.uniform(18, 28)), (random.uniform(23, 28), random.uniform(20, 21)),
                          (random.uniform(30, 49), random.uniform(21.7, 22.2))])
    a = random.uniform(0, math.pi)
    ln = random.uniform(0.15, 0.4)
    add_box("cardboard", x, y, 0.002, x + ln * abs(math.cos(a)) + 0.04, y + ln * abs(math.sin(a)) + 0.04, 0.004)
# (outbound queue: loaded roll cages are built in build_hub.py; no wrapped pallets at the doors)
me = bpy.data.meshes.new("clutter")
bm = bmesh.new()
mats = list(clutter)
for i, mt in enumerate(mats):
    for x0, y0, z0, x1, y1, z1 in clutter[mt]:
        r = bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
                                  @ Matrix.Diagonal((x1 - x0, y1 - y0, z1 - z0, 1)))
        for f in {f for v in r["verts"] for f in v.link_faces}:
            f.material_index = i
bm.to_mesh(me)
bm.free()
for mt in mats:
    me.materials.append(bpy.data.materials[mt])
dress.objects.link(bpy.data.objects.new("clutter_procedural", me))


# signs: no smoking (Malay), floor arrows along the forklift lane
def text_sign(name, body, loc, rot, size, mat):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body, cu.size, cu.extrude = body, size, 0.004
    cu.align_x, cu.align_y = "CENTER", "CENTER"
    ob = bpy.data.objects.new(name, cu)
    ob.location, ob.rotation_euler = loc, [math.radians(a) for a in rot]
    cu.materials.append(bpy.data.materials[mat])
    dress.objects.link(ob)


# (no-smoking signs are real-format image signs from build_hub.py / make_signs.py now)
arrows = []
for (ax, ay), (bx, by) in zip(lane, lane[1:]):
    ang = math.atan2(by - ay, bx - ax)
    ln = math.hypot(bx - ax, by - ay)
    for k in range(1, int(ln / 10) + 1):
        t = k * 10 / ln
        if t < 0.95:
            arrows.append((ax + (bx - ax) * t, ay + (by - ay) * t, ang))
me = bpy.data.meshes.new("floor_arrows")
bm = bmesh.new()
shape = [(-0.9, -0.12), (0.2, -0.12), (0.2, -0.35), (0.9, 0.0), (0.2, 0.35), (0.2, 0.12), (-0.9, 0.12)]
for cx, cy, a in arrows:
    ca, sa = math.cos(a), math.sin(a)
    bm.faces.new([bm.verts.new((cx + x * ca - y * sa, cy + x * sa + y * ca, 0.006)) for x, y in shape])
bm.to_mesh(me)
bm.free()
me.materials.append(bpy.data.materials["white_paint"])
dress.objects.link(bpy.data.objects.new("floor_arrows", me))
for obj_name in ("floor_markings", "floor_arrows"):  # worn copies for paint on the floor only
    ob = bpy.data.objects.get(obj_name) or next((o for o in dress.objects if o.name == obj_name), None)
    if ob is None:
        continue
    for slot in ob.material_slots:
        if slot.material and slot.material.name in ("safety_yellow", "white_paint"):
            copy = bpy.data.materials.get(f"floor_{slot.material.name}") or slot.material.copy()
            copy.name = f"floor_{slot.material.name}"
            slot.material = copy
worn_paint("floor_safety_yellow", amount=0.25)
worn_paint("floor_white_paint", amount=0.35)

# ------------------------------------------------------------------------------------------------ lighting
highbays = [o for o in scene.objects if o.type == "LIGHT" and o.name.startswith("highbay_") and o.data.energy > 0]
dim = min(highbays, key=lambda o: (o.location - Vector((39.0, 29.9, o.location.z))).length)  # one dim (Z10)
for o in highbays:
    e = SPOT_W * random.uniform(0.9, 1.1)  # ±10 % (pack)
    dock = o.location.x < 7 or o.location.y > 33
    if dock:  # docks brighter and cooler (pack: 5000 K+ at loading docks)
        e *= 1.15
        o.data.color = (0.93, 0.97, 1.0)
    else:
        o.data.color = (1.0, 0.96, 0.9)
    if o is dim:
        e *= 0.45
    o.data.energy = e
for o in scene.objects:
    if o.type == "LIGHT" and o.name.startswith("office_"):
        o.data.energy = 3000 / LM_PER_W
    if o.type == "LIGHT" and o.data.type == "SUN":  # low afternoon sun from the west: hard light into the docks
        o.data.energy = 30000 / LM_PER_W
        o.data.angle = math.radians(2.5)
        o.rotation_euler = (math.radians(60), 0, math.radians(-90))
nt = scene.world.node_tree
hdr = next(iter(sorted((TP / "overcast_industrial_courtyard").glob("*.hdr"))), None)
if hdr:
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(hdr))
    seen = nt.nodes["Background"]
    nt.links.new(env.outputs["Color"], seen.inputs["Color"])
    seen.inputs["Strength"].default_value = 1.0
    lit = nt.nodes.new("ShaderNodeBackground")  # what the sky contributes as light inside a roofed hall
    nt.links.new(env.outputs["Color"], lit.inputs["Color"])
    lit.inputs["Strength"].default_value = 0.08
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(lit.outputs["Background"], mix.inputs[1])
    nt.links.new(seen.outputs["Background"], mix.inputs[2])
    out = next(n for n in nt.nodes if n.type == "OUTPUT_WORLD")
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
for m in bpy.data.materials:
    b = m.node_tree.nodes.get("Principled BSDF") if m.node_tree else None
    if b and m.name in ("lamp_emit", "tunnel_lightbar", "exit_green_emit", "screen_emit"):
        b.inputs["Emission Strength"].default_value = {"lamp_emit": 6.0, "tunnel_lightbar": 4.0,
                                                       "exit_green_emit": 1.5, "screen_emit": 0.4}[m.name]

# stretch film: opaque (owner rule: nothing see-through but glass) - the cartons show THROUGH as a printed look:
# the cardboard texture, washed pale and glossy with film wrinkles, on the wrap surface itself
for _wn in ("stretch_wrap_thin", "stretch_wrap"):
    _wm = bpy.data.materials.get(_wn)
    if _wm is None or not _wm.use_nodes:
        continue
    _nt = _wm.node_tree
    _b = next((n for n in _nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if _b is None:
        continue
    _b.inputs["Alpha"].default_value = 1.0
    for _lk in list(_b.inputs["Alpha"].links):
        _nt.links.remove(_lk)
    if hasattr(_wm, "surface_render_method"):
        _wm.surface_render_method = "DITHERED"
    _card = bpy.data.materials.get("cardboard")
    _img = next((n.image for n in _card.node_tree.nodes if n.type == "TEX_IMAGE" and n.image), None) if _card else None
    if _img is not None:
        _tx = _nt.nodes.new("ShaderNodeTexImage")
        _tx.image = _img
        _tc = _nt.nodes.new("ShaderNodeTexCoord")
        _mp = _nt.nodes.new("ShaderNodeMapping")
        _mp.inputs["Scale"].default_value = (2.2, 2.2, 2.2)
        _nt.links.new(_tc.outputs["Object"], _mp.inputs["Vector"])
        _nt.links.new(_mp.outputs["Vector"], _tx.inputs["Vector"])
        _mx = _nt.nodes.new("ShaderNodeMix")
        _mx.data_type = "RGBA"
        _mx.inputs["Factor"].default_value = 0.45 if _wn.endswith("thin") else 0.7  # film over cartons
        _nt.links.new(_tx.outputs["Color"], _mx.inputs["A"])
        _mx.inputs["B"].default_value = (0.82, 0.84, 0.86, 1)
        _nt.links.new(_mx.outputs["Result"], _b.inputs["Base Color"])
    _b.inputs["Roughness"].default_value = 0.18
    _b.inputs["Metallic"].default_value = 0.0
    _wm.diffuse_color = (0.62, 0.55, 0.45, 1)  # preview / Workbench colour: cartons under film

# ------------------------------------------------------------------------------------------------ cameras (actual mount)
for cid, t in TRUTH["cameras"].items():
    roll = t.get("mount_roll_deg", 0.0)
    if roll and cid in bpy.data.objects:
        cam = bpy.data.objects[cid]
        cam.matrix_world = cam.matrix_world @ Matrix.Rotation(math.radians(roll), 4, "Z")

placed, people_report = [], {}
if args.people:
    sys.path.insert(0, str(BUILD.parent))
    import people  # noqa: E402  (assets/hub/people.py)

    fps0 = scene.render.fps  # FBX imports reset the scene to the files' 30 fps: restore the CCTV timeline
    placed, people_report = people.add_workers(scene, SPEC, TP / "rocketbox", prop=prop)
    scene.render.fps = fps0
    scene.frame_start, scene.frame_end = 1, SPEC["render_plan"]["seconds_per_scenario"] * fps0
    (BUILD / "truth").mkdir(exist_ok=True)
    (BUILD / "truth" / "workers.json").write_text(json.dumps({"note": "render-side truth; Spoor never reads this",
                                                              "workers": placed, "report": people_report}, indent=1),
                                                  encoding="utf-8")
views = [i.identifier for i in bpy.types.ColorManagedViewSettings.bl_rna.properties["view_transform"].enum_items]
scene.view_settings.view_transform = "AgX" if "AgX" in views else "Filmic"
looks = [i.identifier for i in bpy.types.ColorManagedViewSettings.bl_rna.properties["look"].enum_items]
for want in ("AgX - Medium High Contrast", "AgX - High Contrast", "Medium High Contrast"):
    if want in looks:
        scene.view_settings.look = want
        break
scene.view_settings.exposure = args.exposure
ee = scene.eevee
if hasattr(ee, "shadow_pool_size"):
    ee.shadow_pool_size = [i.identifier for i in ee.bl_rna.properties["shadow_pool_size"].enum_items][-1]
for attr, val in (("use_raytracing", bool(args.raytrace)), ("use_gtao", True), ("taa_render_samples", args.samples),
                  ("shadow_step_count", args.shadow_steps)):
    if hasattr(ee, attr):
        setattr(ee, attr, val)
# EEVEE defaults to 1 mm shadow texels; a CCTV camera metres away resolves a few cm at best (62–125 PPM),
# so coarser shadow maps look the same on camera and cost far less (timing: shadows were ~60 % of a frame)
for o in highbays:
    if hasattr(o.data, "shadow_maximum_resolution"):
        o.data.shadow_maximum_resolution = args.shadow_res

print(json.dumps({"workers": len(placed), "workers_without_clip": [w["name"] for w in placed if "clip" not in w["status"]],
                  "facing_camera": people_report.get("facing_camera"),
                  "mixamo_clips_used": len(people_report.get("mixamo_clips_used", [])),
                  "mixamo_clips_unused": people_report.get("mixamo_clips_unused"),
                  "uniform_tshirt_share": people_report.get("uniform_tshirt_share"),
                  "walkers": [(w["name"], w.get("speed_mps"), len(w.get("off_walkway", []))) for w in placed
                              if w["role"] == "walk"]}), flush=True)
print(json.dumps({"props_skipped_for_walkways_or_missing": skipped, "dim_light": dim.name,
                  "tyre_tracks": len(tracks), "oil_stains": len(oils), "arrows": len(arrows)}), flush=True)
if args.save:
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(args.save).resolve()), compress=True)


# ------------------------------------------------------------------------------------------------ previews
def cull_people(cam, margin=0.15):
    """Render only the workers this camera can see (owner rule: per scenario only people visible in its cameras);
    every animated worker costs deformation + shadow updates each frame even when out of view."""
    inv = cam.matrix_world.inverted()
    tx = math.tan(cam.data.angle_x / 2) * (1 + margin)
    ty = tx * scene.render.resolution_y / scene.render.resolution_x
    shown = 0
    for arm in [o for o in scene.objects if o.type == "ARMATURE" and o.name.startswith("worker_")]:
        vis = bool(arm.animation_data and arm.animation_data.action)  # walkers move: keep them
        for z in (0.2, 1.0, 1.8):
            pc = inv @ (arm.matrix_world.translation + Vector((0, 0, z)))
            if pc.z < -0.1 and abs(pc.x / -pc.z) <= tx and abs(pc.y / -pc.z) <= ty * (1 + margin):
                vis = True
        for o in [arm] + list(arm.children_recursive):
            o.hide_render = not vis
        shown += vis
    return shown


def shadows_for(cam):
    """Only high-bays whose pool of light this camera actually sees cast shadows (cost goes where it shows)."""
    inv = cam.matrix_world.inverted()
    tx = math.tan(cam.data.angle_x / 2)
    ty = tx * scene.render.resolution_y / scene.render.resolution_x
    on = 0
    for o in scene.objects:
        if o.type != "LIGHT" or not o.name.startswith("highbay_"):
            continue
        lx, ly = o.location.x, o.location.y
        if math.hypot(lx - cam.location.x, ly - cam.location.y) > args.shadow_radius:
            o.data.use_shadow = False  # far pools are a few pixels on camera: shadow detail is invisible
            continue
        vis = False
        for dx, dy in ((0, 0), (4, 0), (-4, 0), (0, 4), (0, -4), (3, 3), (-3, 3), (3, -3), (-3, -3)):
            pc = inv @ Vector((lx + dx, ly + dy, 0.5))
            if pc.z < -0.1 and abs(pc.x / -pc.z) <= tx and abs(pc.y / -pc.z) <= ty:
                vis = True
                break
        o.data.use_shadow = vis
        on += vis
    return on


if args.preview:
    pdir = Path(args.preview_dir).resolve() if args.preview_dir else BUILD / "preview"
    pdir.mkdir(parents=True, exist_ok=True)
    scene.render.resolution_percentage = args.pct
    scene.render.image_settings.file_format = "PNG"
    for cid in [c.strip() for c in args.preview.split(",") if c.strip()]:
        cam = bpy.data.objects[cid]
        n_sh = shadows_for(cam)
        n_people = cull_people(cam)
        if args.no_shadows:  # profiling only
            for o in scene.objects:
                if o.type == "LIGHT" and o.name.startswith("highbay_"):
                    o.data.use_shadow = False
        scene.camera = cam
        scene.render.filepath = str(pdir / f"{cid}_raw.png")
        times = []
        for k in range(args.repeat):  # first frame includes shader compile / shadow setup; later ones are steady state
            scene.frame_set(1 + k)
            t0 = time.perf_counter()
            bpy.ops.render.render(write_still=True)
            times.append(round(time.perf_counter() - t0, 2))
        print(json.dumps({"preview": cid, "seconds": times, "shadow_lights": n_sh, "workers_in_view": n_people}),
              flush=True)
if os.name == "nt":
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
