"""EEVEE timing test for the Spoor demo hub. NOT the hub: a cost-representative 24 x 24 m slice built from
procedural stand-ins (no downloads, no AI assets) so we can measure seconds per CCTV frame on this PC.

Run headless (no GUI, no MCP bridge, user add-ons off), plugged in, lid open:
  "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b --factory-startup ^
      -P assets\\hub\\timing_test.py -- --out <folder> [--frames 10] [--sustained-s 300] [--total-frames 85500]

Measures, for a wide camera (like the loop cameras) and a close one (like the reject-chute camera):
  A  CCTV-lite   2688 x 1520, 16 samples, ray tracing off   <- the planned production setting
  B  half-res    1344 x 760,  same settings                 <- how time scales with pixels
  C  ray-traced  2688 x 1520, 16 samples, ray tracing on    <- the cost of the nicer look
Each config: 1 warm-up frame (shader compile, not counted) + --frames timed frames (render + PNG write). Then A on
the wide camera runs for --sustained-s seconds to catch thermal throttling (a 15 W laptop chip slows down under
long load). Writes timings.csv and summary.json with the extrapolation to --total-frames.

Keeps Windows awake for exactly as long as Blender runs (SetThreadExecutionState), so it does not depend on any
other session staying alive.
"""

import argparse
import csv
import ctypes
import json
import math
import os
import platform
import random
import statistics
import sys
import time
from pathlib import Path

import bmesh
import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--frames", type=int, default=10)
ap.add_argument("--sustained-s", type=int, default=300)
ap.add_argument("--total-frames", type=int, default=85500)
args = ap.parse_args(argv)
OUT = Path(args.out)
OUT.mkdir(parents=True, exist_ok=True)

ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001


def keep_awake(on: bool):
    if os.name == "nt":
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))


# ------------------------------------------------------------------------------------------------ scene
random.seed(7)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
FPS = 15
scene.render.fps = FPS


def material(name, color, rough=0.6, metal=0.0, noise=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if noise:  # cheap wear: noise drives roughness, like the real worn concrete / cardboard materials will
        n = nt.nodes.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = noise
        ramp = nt.nodes.new("ShaderNodeMapRange")
        ramp.inputs["To Min"].default_value = rough * 0.6
        ramp.inputs["To Max"].default_value = min(1.0, rough * 1.4)
        nt.links.new(n.outputs["Fac"], ramp.inputs["Value"])
        nt.links.new(ramp.outputs["Result"], bsdf.inputs["Roughness"])
    return m


M = {"concrete": material("concrete", (0.42, 0.41, 0.39), 0.75, noise=6.0),
     "steel": material("steel", (0.55, 0.57, 0.6), 0.35, 1.0),
     "yellow": material("yellow", (0.85, 0.65, 0.05), 0.5),
     "rubber": material("rubber", (0.04, 0.04, 0.04), 0.8),
     "card": material("card", (0.55, 0.40, 0.24), 0.8, noise=25.0),
     "flyer": material("flyer", (0.15, 0.15, 0.17), 0.45),
     "cladding": material("cladding", (0.7, 0.72, 0.74), 0.5, 0.6),
     "skin": material("worker", (0.2, 0.3, 0.55), 0.7)}


def box(name, size, loc, mat, rot_z=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=(0, 0, rot_z))
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    o.data.materials.append(M[mat])
    return o


def instance(src, loc, rot_z=0.0):
    o = src.copy()  # linked duplicate: shares mesh data, like instanced carriers / cages in the real build
    o.location = loc
    o.rotation_euler[2] = rot_z
    scene.collection.objects.link(o)
    return o


# shell: floor, two walls with a dock door, roof, columns, trusses
box("floor", (24, 24, 0.2), (12, 12, -0.1), "concrete")
box("wall_w", (0.2, 24, 11), (0, 12, 5.5), "cladding")
box("wall_n_a", (10, 0.2, 11), (5, 24, 5.5), "cladding")
box("wall_n_b", (11, 0.2, 11), (18.5, 24, 5.5), "cladding")
box("wall_n_top", (3, 0.2, 8), (11.5, 24, 7), "cladding")  # 3 x 3 m door opening below
box("roof", (24, 24, 0.2), (12, 12, 11.1), "cladding")
for x in (0.3, 12, 23.7):
    for y in (0.3, 12, 23.7):
        box(f"col_{x}_{y}", (0.4, 0.4, 11), (x, y, 5.5), "steel")
for y in range(0, 25, 6):
    box(f"truss_{y}", (24, 0.15, 0.6), (12, y, 10.2), "steel")
    for k in range(12):
        box(f"web_{y}_{k}", (0.06, 0.06, 0.9), (1 + 2 * k, y, 10.2), "steel", rot_z=0.0)

# cross-belt straight: deck frame, guard rails, 28 carriers on a moving parent
box("deck", (20, 1.2, 0.25), (12, 8, 1.35), "steel")
for dy in (-0.62, 0.62):
    box(f"rail_{dy}", (20, 0.05, 0.5), (12, 8 + dy, 1.75), "yellow")
for x in range(3, 22, 2):
    box(f"leg_{x}", (0.1, 1.0, 1.25), (x, 8, 0.62), "steel")
carrier_parent = bpy.data.objects.new("carriers", None)
scene.collection.objects.link(carrier_parent)
carrier = box("carrier", (0.85, 0.44, 0.06), (0, 0, 0), "rubber")
carriers = [carrier] + [instance(carrier, (0, 0, 0)) for _ in range(27)]
for i, c in enumerate(carriers):
    c.parent = carrier_parent
    c.location = (2.0 + i * 0.7, 8, 1.52)

# 6 chutes and bag frames (tube frames: wireframe modifier on a box)
for k in range(6):
    x = 5 + 2.5 * k
    ch = box(f"chute_{k}", (1.0, 2.0, 0.04), (x, 10.0, 1.2), "steel")
    ch.rotation_euler[0] = math.radians(-14)
    fr = box(f"frame_{k}", (1.0, 0.8, 1.1), (x, 11.6, 0.55), "steel")
    fr.modifiers.new("tube", "WIREFRAME").thickness = 0.03

# roll cages: subdivided box + wireframe modifier (mesh-heavy, like real cages)
cage_mesh = bpy.data.meshes.new("cage")
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=8, use_grid_fill=True)
bm.to_mesh(cage_mesh)
bm.free()
cage = bpy.data.objects.new("cage", cage_mesh)
cage.scale = (0.72, 0.80, 1.80)
cage.data.materials.append(M["steel"])
wire = cage.modifiers.new("wire", "WIREFRAME")
wire.thickness = 0.012
scene.collection.objects.link(cage)
cage.location = (3, 16, 0.9)
for k in range(1, 12):
    instance(cage, (3 + 1.5 * (k % 8), 16 + 2.5 * (k // 8), 0.9), rot_z=random.uniform(-0.1, 0.1))

# parcels: boxes on the floor / carriers, flyers in bag frames
for k in range(60):
    s = (random.uniform(0.15, 0.6), random.uniform(0.15, 0.5), random.uniform(0.08, 0.45))
    on_belt = k < 14
    loc = (2.0 + 1.4 * k, 8, 1.55 + s[2] / 2) if on_belt else (random.uniform(2, 22), random.uniform(13, 22), s[2] / 2)
    p = box(f"parcel_{k}", s, loc, "card", rot_z=random.uniform(0, 3.14))
    if on_belt:
        p.parent = carrier_parent
for k in range(30):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.2, location=(5 + 2.5 * (k % 6), 11.6, 0.2 + 0.1 * (k // 6)))
    f = bpy.context.active_object
    f.scale = (1.2, 0.9, 0.35)
    f.modifiers.new("sub", "SUBSURF").levels = 1
    f.data.materials.append(M["flyer"])

# 6 workers (proxy: capsule body + head), moving a little each frame
workers = []
for k in range(6):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.22, depth=1.3, location=(4 + 3 * k, 13 + (k % 2) * 4, 0.9))
    body = bpy.context.active_object
    body.data.materials.append(M["skin"])
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=(0, 0, 0.8))
    head = bpy.context.active_object
    head.parent = body
    head.data.materials.append(M["skin"])
    workers.append((body, body.location.x))


def animate(scn, *_):
    """Carriers run at 2.5 m/s and repeat every 0.7 m pitch (so the belt is always full); workers walk 1.2 m/s.
    A frame handler, not keyframes: the action API changed in Blender 4.4/5.0 and this works on both."""
    t = (scn.frame_current - 1) / FPS
    carrier_parent.location.x = (2.5 * t) % 0.7
    for body, x0 in workers:
        body.location.x = x0 + (1.2 * t) % 3.0


bpy.app.handlers.frame_change_pre.append(animate)

# lights: 12 high-bay discs + daylight through the door + dim world
for x in (4, 12, 20):
    for y in (4, 10, 16, 22):
        ld = bpy.data.lights.new(f"bay_{x}_{y}", "AREA")
        ld.shape = "DISK"
        ld.size = 0.5
        ld.energy = 900
        ld.color = (1.0, 0.96, 0.9)
        lo = bpy.data.objects.new(ld.name, ld)
        lo.location = (x, y, 9.8)
        scene.collection.objects.link(lo)
sun_d = bpy.data.lights.new("daylight", "SUN")
sun_d.energy = 3.0
sun = bpy.data.objects.new("daylight", sun_d)
sun.rotation_euler = (math.radians(60), 0, math.radians(200))
scene.collection.objects.link(sun)
world = bpy.data.worlds.new("overcast")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.6, 0.65, 0.7, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.3
scene.world = world


def cctv_camera(name, pos, yaw, tilt):
    cd = bpy.data.cameras.new(name)
    cd.sensor_fit = "HORIZONTAL"
    cd.angle_x = math.radians(103.0)  # the planned 2.8 mm dome: 103 x 58 deg at 16:9
    cd.clip_start, cd.clip_end = 0.1, 120
    co = bpy.data.objects.new(name, cd)
    co.location = pos
    co.rotation_euler = (math.radians(90 - tilt), 0, math.radians(yaw - 90))
    scene.collection.objects.link(co)
    return co


CAMS = {"wide (loop-like, 8.5 m)": cctv_camera("wide", (12, 1.0, 8.5), 90, 50),
        "close (reject-chute-like, 3.5 m)": cctv_camera("close", (6, 14.0, 3.5), 270, 55)}


# ------------------------------------------------------------------------------------------------ render setup
def set_engine():
    engines = bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items.keys()
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"


def configure(res, raytrace):
    set_engine()
    r = scene.render
    r.resolution_x, r.resolution_y = res
    r.resolution_percentage = 100
    r.image_settings.file_format = "PNG"
    r.image_settings.color_depth = "8"
    r.image_settings.compression = 15
    scene.view_settings.view_transform = "Standard"
    ee = scene.eevee
    for attr, val in (("taa_render_samples", 16), ("use_raytracing", raytrace), ("use_gtao", True),
                      ("use_motion_blur", False), ("use_bloom", False)):
        if hasattr(ee, attr):
            setattr(ee, attr, val)


def render_frame(cam, frame, path):
    scene.camera = cam
    scene.frame_set(frame)
    scene.render.filepath = str(path)
    t = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    return time.perf_counter() - t


def gpu_name():
    try:
        import gpu

        return gpu.platform.renderer_get()
    except Exception as exc:  # background mode may not expose it
        return f"unknown ({exc.__class__.__name__})"


# ------------------------------------------------------------------------------------------------ run
CONFIGS = {"A_cctv_lite_full": ((2688, 1520), False), "B_half_res": ((1344, 760), False),
           "C_raytraced_full": ((2688, 1520), True)}
rows, summary = [], {"blender": bpy.app.version_string, "gpu": gpu_name(), "cpu": platform.processor(),
                     "engine": None, "triangles_approx": None, "configs": {}}
try:
    deps = bpy.context.evaluated_depsgraph_get()
    summary["triangles_approx"] = sum(len(o.evaluated_get(deps).data.polygons) * 2 for o in scene.objects
                                      if o.type == "MESH")
except Exception as exc:  # informational only
    summary["triangles_approx"] = f"unknown ({exc.__class__.__name__})"
keep_awake(True)
try:
    for cfg, (res, rt) in CONFIGS.items():
        configure(res, rt)
        summary["engine"] = scene.render.engine
        for cam_label, cam in CAMS.items():
            warm = render_frame(cam, 1, OUT / f"{cfg}_{cam.name}_warm.png")
            times = [render_frame(cam, 2 + i, OUT / f"{cfg}_{cam.name}_{i:03d}.png") for i in range(args.frames)]
            rows += [{"config": cfg, "camera": cam_label, "frame": i, "seconds": round(s, 3)}
                     for i, s in enumerate(times)]
            summary["configs"][f"{cfg} / {cam_label}"] = {
                "warmup_s": round(warm, 2), "median_s": round(statistics.median(times), 2),
                "max_s": round(max(times), 2)}
            print(cfg, cam_label, summary["configs"][f"{cfg} / {cam_label}"], flush=True)
    # sustained run: does the laptop throttle?
    configure(CONFIGS["A_cctv_lite_full"][0], False)
    cam = CAMS["wide (loop-like, 8.5 m)"]
    t0, sus, i = time.perf_counter(), [], 0
    while time.perf_counter() - t0 < args.sustained_s:
        sus.append((time.perf_counter() - t0, render_frame(cam, 2 + i % 118, OUT / "sustained_last.png")))
        i += 1
    first = [s for t, s in sus if t < 60] or [sus[0][1]]
    last = [s for t, s in sus if t >= args.sustained_s - 60] or [sus[-1][1]]
    summary["sustained"] = {"frames": len(sus), "first_minute_median_s": round(statistics.median(first), 2),
                            "last_minute_median_s": round(statistics.median(last), 2),
                            "throttle_factor": round(statistics.median(last) / statistics.median(first), 2)}
    rows += [{"config": "sustained_A_wide", "camera": "wide", "frame": k, "seconds": round(s, 3)}
             for k, (_, s) in enumerate(sus)]
finally:
    keep_awake(False)

per_frame = summary["sustained"]["last_minute_median_s"]  # plan on the throttled speed, not the fresh one
summary["extrapolation"] = {
    "total_frames": args.total_frames, "seconds_per_frame_used": per_frame,
    "hours": round(per_frame * args.total_frames / 3600, 1),
    "days_nonstop": round(per_frame * args.total_frames / 86400, 1),
    "note": "test slice is ~1/4 of the hub's floor; the real hub has more geometry and lights per view, so treat "
            "this as a lower bound and re-time one real camera once the hub exists"}
with (OUT / "timings.csv").open("w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["config", "camera", "frame", "seconds"])
    w.writeheader()
    w.writerows(rows)
(OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2), flush=True)
