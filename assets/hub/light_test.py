"""Tier 1.5 lighting test (owner: CAM_07 + CAM_13 only, before relighting the whole hub).

  blender -b --factory-startup assets/hub/build/hub_dressed.blend -P assets/hub/light_test.py -- \
      --cams CAM_07,CAM_13 --out <dir> [--row-w 520] [--exposure 1.2] [--samples 4]

What real hubs look like (docs/hub/reference_frames README: dpd_t138/t145, beesort_t202/t250): long rows of linear
LED strip lights under a white / light-grey roof, white walls, bright and clean, yet with pools between rows,
shadows under machines and darker corners. So: the round high-bay spots are switched off and replaced by
continuous east-west LED rows (batten fittings on a trunking line, 3.6 m apart). Light comes from one rectangular
area light per 12 m of row (55 lights), shadows only from rows the camera sees within 22 m (as the high-bays).
The Z11 store corner row is out (darkest corner stays), one row segment is dimmer. Walls, roof and trusses are
painted white / light grey. Nothing is saved: this only renders the test frames.
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ap = argparse.ArgumentParser()
ap.add_argument("--cams", default="CAM_07,CAM_13")
ap.add_argument("--out", required=True)
ap.add_argument("--row-w", type=float, default=520.0)  # W per 12 m area light
ap.add_argument("--exposure", type=float, default=None)
ap.add_argument("--samples", type=int, default=4)
ap.add_argument("--repeat", type=int, default=2)
ap.add_argument("--save", default="")
ap.add_argument("--area-shadows", type=int, default=0)  # 1: every LED area light casts shadows (~52 s/frame)
ap.add_argument("--floor-mul", type=float, default=1.0)  # darken the floor's base colour (mid-grey epoxy)
ap.add_argument("--floor-rough", type=float, default=0.6)
ap.add_argument("--floor-spec", type=float, default=0.3)
ap.add_argument("--spots", type=float, default=0.45)  # keep the high-bay spots (fixtures hidden) as the shadow
#                                                       casters, at this fraction of their power; 0 = off
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
scene = bpy.context.scene
out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)

ROW_Z = 8.5
ROWS_Y = [2.2 + 3.6 * k for k in range(11)]  # 2.2 .. 38.2
SEG = 12.0
DEAD = lambda x, y: x < 13.0 and y > 32.0  # Z11 store corner: out (darkest corner of the hall)
DIM = lambda x, y: 36.0 <= x < 48.0 and abs(y - 27.4) < 0.1  # one segment over staging is a bit dim

# ---------------------------------------------------------------- off: round high-bays
for o in scene.objects:
    if o.type == "LIGHT" and o.name.startswith("highbay_"):
        if args.spots > 0:
            o.data.energy *= args.spots
        else:
            o.hide_render = True
    if o.name == "highbay_fixtures":
        o.hide_render = True

# ---------------------------------------------------------------- on: linear LED rows
coll = bpy.data.collections.new("LED_rows")
scene.collection.children.link(coll)


def mat(name, rgb, rough=0.5, metal=0.0, emit=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*rgb, 1)
        b.inputs["Emission Strength"].default_value = emit
    return m


m_trunk = mat("led_trunking", (0.78, 0.79, 0.8), 0.45, 0.3)
m_led = mat("led_diffuser", (1.0, 0.98, 0.95), 0.3, emit=18.0)
m_led_dim = mat("led_diffuser_dim", (1.0, 0.95, 0.86), 0.3, emit=12.0)
bm = bmesh.new()


def box(x0, y0, z0, x1, y1, z1, mi):
    r = bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
                              @ Matrix.Diagonal((x1 - x0, y1 - y0, z1 - z0, 1)))
    for f in {f for v in r["verts"] for f in v.link_faces}:
        f.material_index = mi


lights = []
for y in ROWS_Y:
    box(0.4, y - 0.04, ROW_Z + 0.06, 59.6, y + 0.04, ROW_Z + 0.12, 0)  # trunking rail
    for k in range(5):
        x0 = 0.5 + k * SEG
        dead = DEAD(x0 + SEG / 2, y)
        dim = DIM(x0, y)
        for j in range(7):  # 1.6 m batten fittings with short gaps
            fx = x0 + 0.15 + j * 1.7
            box(fx, y - 0.075, ROW_Z, fx + 1.6, y + 0.075, ROW_Z + 0.06, 0)
            if not dead:
                box(fx + 0.02, y - 0.06, ROW_Z - 0.004, fx + 1.58, y + 0.06, ROW_Z + 0.002, 2 if dim else 1)
        if dead:
            continue
        ld = bpy.data.lights.new(f"ledrow_{k}_{y:.1f}", "AREA")
        ld.shape, ld.size, ld.size_y = "RECTANGLE", SEG - 0.4, 0.15
        ld.energy = args.row_w * (0.72 if dim else 1.0)
        ld.color = (1.0, 0.97, 0.92) if not dim else (1.0, 0.93, 0.82)
        lo = bpy.data.objects.new(ld.name, ld)
        lo.location = (x0 + SEG / 2, y, ROW_Z - 0.01)
        coll.objects.link(lo)
        lights.append(lo)
me = bpy.data.meshes.new("led_rows")
bm.to_mesh(me)
bm.free()
for m in (m_trunk, m_led, m_led_dim):
    me.materials.append(m)
coll.objects.link(bpy.data.objects.new("led_rows", me))


# ---------------------------------------------------------------- paint: white walls / roof, light-grey trusses
def lighten(name, rgb, factor, metal=None, rough=None):
    m = bpy.data.materials.get(name)
    if m is None or not m.use_nodes:
        return False
    nt = m.node_tree
    b = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if b is None:
        return False
    link = next((lk for lk in nt.links if lk.to_socket == b.inputs["Base Color"]), None)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["Factor"].default_value = factor
    mix.inputs["B"].default_value = (*rgb, 1)
    if link:
        nt.links.new(link.from_socket, mix.inputs["A"])
    else:
        mix.inputs["A"].default_value = b.inputs["Base Color"].default_value
    nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
    if metal is not None:
        b.inputs["Metallic"].default_value = metal
    if rough is not None and not any(lk.to_socket == b.inputs["Roughness"] for lk in nt.links):
        b.inputs["Roughness"].default_value = rough
    return True


def darken(name, mul):
    """Multiply a material's base colour (texture kept): the hall floor reads mid-grey epoxy, darker than walls."""
    m = bpy.data.materials.get(name)
    if m is None or not m.use_nodes:
        return False
    nt = m.node_tree
    b = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    link = next((lk for lk in nt.links if lk.to_socket == b.inputs["Base Color"]), None)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
    mix.inputs["Factor"].default_value = 1.0
    mix.inputs["B"].default_value = (mul, mul, mul, 1)
    if link:
        nt.links.new(link.from_socket, mix.inputs["A"])
    else:
        mix.inputs["A"].default_value = b.inputs["Base Color"].default_value
    nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
    # worn epoxy is semi-matte: roughness at least 0.6 and a weaker specular, so the LED rows don't mirror in it
    rl = next((lk for lk in nt.links if lk.to_socket == b.inputs["Roughness"]), None)
    mx = nt.nodes.new("ShaderNodeMath")
    mx.operation = "MAXIMUM"
    mx.inputs[1].default_value = args.floor_rough
    if rl:
        nt.links.new(rl.from_socket, mx.inputs[0])
    else:
        mx.inputs[0].default_value = b.inputs["Roughness"].default_value
    nt.links.new(mx.outputs["Value"], b.inputs["Roughness"])
    if "Specular IOR Level" in b.inputs:
        b.inputs["Specular IOR Level"].default_value = args.floor_spec
    return True


floor_dark = darken("floor_epoxy_concrete", args.floor_mul)
painted = {n: lighten(n, rgb, f, metal, rough) for n, rgb, f, metal, rough in (
    ("cladding_steel", (0.86, 0.87, 0.88), 0.78, 0.1, 0.5),  # walls + roof sheet: white-painted profile
    ("painted_frame", (0.78, 0.79, 0.8), 0.7, 0.15, None),  # trusses, purlins, frames: light grey
)}

# ---------------------------------------------------------------- render
if args.exposure is not None:
    scene.view_settings.exposure = args.exposure
scene.eevee.taa_render_samples = args.samples
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"


def spot_shadows_for(cam, radius=22.0):  # as dress_hub: only pools the camera sees, within 22 m
    inv = cam.matrix_world.inverted()
    tx = math.tan(cam.data.angle_x / 2)
    ty = tx * scene.render.resolution_y / scene.render.resolution_x
    for o in scene.objects:
        if o.type != "LIGHT" or not o.name.startswith("highbay_"):
            continue
        vis = False
        if math.hypot(o.location.x - cam.location.x, o.location.y - cam.location.y) <= radius:
            for dx, dy in ((0, 0), (4, 0), (-4, 0), (0, 4), (0, -4), (3, 3), (-3, 3), (3, -3), (-3, -3)):
                pc = inv @ Vector((o.location.x + dx, o.location.y + dy, 0.5))
                if pc.z < -0.1 and abs(pc.x / -pc.z) <= tx and abs(pc.y / -pc.z) <= ty:
                    vis = True
                    break
        o.data.use_shadow = vis


def shadows_for(cam, radius=22.0):
    if not args.area_shadows:
        for o in lights:
            o.data.use_shadow = False
        spot_shadows_for(cam, radius)
        return 0
    inv = cam.matrix_world.inverted()
    tx = math.tan(cam.data.angle_x / 2)
    ty = tx * scene.render.resolution_y / scene.render.resolution_x
    on = 0
    for o in lights:
        vis = False
        if math.hypot(o.location.x - cam.location.x, o.location.y - cam.location.y) <= radius + SEG / 2:
            for dx in (-5, 0, 5):
                for dy in (-2, 0, 2):
                    pc = inv @ Vector((o.location.x + dx, o.location.y + dy, 0.5))
                    if pc.z < -0.1 and abs(pc.x / -pc.z) <= tx and abs(pc.y / -pc.z) <= ty:
                        vis = True
        o.data.use_shadow = vis
        on += vis
    return on


def cull_people(cam, margin=0.15):
    inv = cam.matrix_world.inverted()
    tx = math.tan(cam.data.angle_x / 2) * (1 + margin)
    ty = tx * scene.render.resolution_y / scene.render.resolution_x
    for arm in [o for o in scene.objects if o.type == "ARMATURE" and o.name.startswith("worker_")]:
        vis = bool(arm.animation_data and arm.animation_data.action)
        for z in (0.2, 1.0, 1.8):
            pc = inv @ (arm.matrix_world.translation + Vector((0, 0, z)))
            if pc.z < -0.1 and abs(pc.x / -pc.z) <= tx and abs(pc.y / -pc.z) <= ty * (1 + margin):
                vis = True
        for o in [arm] + list(arm.children_recursive):
            o.hide_render = not vis


print(json.dumps({"led_area_lights": len(lights), "row_w": args.row_w, "painted": painted, "floor_dark": floor_dark,
                  "exposure": scene.view_settings.exposure}), flush=True)
for cid in [c.strip() for c in args.cams.split(",") if c.strip()]:
    cam = bpy.data.objects[cid]
    scene.camera = cam
    n_sh = shadows_for(cam)
    cull_people(cam)
    scene.render.filepath = str(out / f"{cid}_led_raw.png")
    times = []
    for k in range(args.repeat):
        scene.frame_set(1 + k)
        t0 = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        times.append(round(time.perf_counter() - t0, 2))
    print(json.dumps({"preview": cid, "seconds": times, "shadow_lights": n_sh}), flush=True)
if args.save:
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(args.save).resolve()), compress=True)
