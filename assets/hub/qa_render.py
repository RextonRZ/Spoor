"""QA review renders (frames only; qa_videos.py burns in labels and encodes). Run by qa_videos.py:

  blender -b --factory-startup assets/hub/build/hub_dressed.blend -P assets/hub/qa_render.py -- \
      --jobs worker:worker_mx_06_cages,cam:CAM_07 --out assets/hub/build/qa/_frames

worker:<name>  follow camera ~4 m away, 3/4 view from above (front side of the worker's start heading), clip_start
               cut so walls / lorries between camera and worker never hide them; Workbench (texture colour, cavity,
               shadow) for speed; workers > 6 m away hidden.
cam:<CAM_xx>   the CCTV camera itself, Workbench too (EEVEE at 1 sample measured ~7 s/frame: too slow for QA).
Frames 1-300 at 960 x 540 PNG -> <out>/<job>/####.png, then a 'done' marker.
"""

import argparse
import math
import sys
import time
from pathlib import Path

import bpy
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument("--jobs", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--frames", default="1-300")
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
F0, F1 = (int(x) for x in args.frames.split("-"))
OUT = Path(args.out).resolve()
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 960, 540, 100
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGB"
sc.render.use_stamp = False
sc.frame_start, sc.frame_end = F0, F1
RIGS = [o for o in sc.objects if o.type == "ARMATURE" and o.name.startswith("worker_")]
for r in RIGS:
    for o in [r] + list(r.children_recursive):
        o.hide_render = False


def show_workers(keep):
    for r in RIGS:
        vis = keep is None or r.name in keep
        for o in [r] + list(r.children_recursive):
            o.hide_render = o.hide_viewport = not vis


# Workbench colours: materials without an image texture show their viewport colour; take it from the node tree
for m in bpy.data.materials:
    if not m.use_nodes or m.node_tree is None:
        continue
    b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if b is None:
        continue
    sock = b.inputs["Base Color"]
    col = None
    if not sock.is_linked:
        col = sock.default_value
    else:
        for n in m.node_tree.nodes:
            if n.type == "MIX" and getattr(n, "data_type", "") == "RGBA" and not n.inputs["A"].is_linked:
                col = n.inputs["A"].default_value
                break
            if n.type == "RGB":
                col = n.outputs[0].default_value
                break
    if col is not None:
        m.diffuse_color = (col[0], col[1], col[2], 1.0)

roots = {}
for f in range(F0, F1 + 1, 10):
    sc.frame_set(f)
    for r in RIGS:
        roots.setdefault(r.name, []).append(r.matrix_world.translation.copy())


def near_workers(name, radius=6.0):
    me_ = roots[name]
    return {r.name for r in RIGS if min((a - b).length for a, b in zip(me_, roots[r.name])) <= radius}


def shadows_for(cam, radius=22.0):
    inv = cam.matrix_world.inverted()
    tx = math.tan(cam.data.angle_x / 2)
    ty = tx * 1520 / 2688
    for o in sc.objects:
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


def workbench():
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light, sh.color_type = "STUDIO", "TEXTURE"
    sh.show_cavity, sh.cavity_type = True, "BOTH"
    sh.show_shadows = True
    sc.display.render_aa = "FXAA"


follow = bpy.data.objects.new("qa_follow", bpy.data.cameras.new("qa_follow"))
sc.collection.objects.link(follow)
for job in [j for j in args.jobs.split(",") if j]:
    kind, name = job.split(":", 1)
    d = OUT / name
    if (d / "done").exists():
        print("QAR skip", name, flush=True)
        continue
    d.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if kind == "worker":
        rig = sc.objects[name]
        show_workers(near_workers(name))
        workbench()
        follow.animation_data_clear()
        follow.data.lens = 35
        sc.frame_set(F0)
        yaw = rig.matrix_world.to_euler()[2] - math.radians(90)  # the worker's facing at frame 1
        fwd = Vector((math.cos(yaw), math.sin(yaw), 0))
        side = Vector((-fwd.y, fwd.x, 0))
        dg = bpy.context.evaluated_depsgraph_get()
        own = {rig.name} | {c.name for c in rig.children_recursive}

        def blocked(off, clip):
            """Rays from the lens (past the clipped zone) to the head / chest / hips at three frames: hits by
            anything but this worker."""
            n = 0
            for f in (F0, (F0 + F1) // 2, F1 - 1):
                sc.frame_set(f)
                root = rig.matrix_world.translation
                for z in (0.5, 1.1, 1.6):
                    t = root + Vector((0, 0, z))
                    c = root + off
                    d = t - c
                    L = d.length
                    o = c + d / L * clip
                    hit, loc, nrm, idx, ob, _ = sc.ray_cast(dg, o, d / L, distance=max(0.01, L - clip - 0.15))
                    n += bool(hit and ob.name not in own)
            return n
        best = None
        for ang, dist, up in [(a, d, u) for (d, u) in ((3.1, 2.6), (2.0, 1.9), (1.5, 1.6)) for a in (40, -40, 140, -140)]:
            a_ = math.radians(ang)  # 3/4 views; closer and lower for workers inside lorries / between racks
            off_ = (fwd * math.cos(a_) + side * math.sin(a_)) * dist + Vector((0, 0, up))
            head_d = (off_ - Vector((0, 0, 1.75))).length  # lens to the top of the head / cap
            clip_ = max(0.1, head_d - 0.7)  # cut only what is > 0.7 m in front of the head (never the cap)
            nb = blocked(off_, clip_)
            if best is None or nb < best[0]:
                best = (nb, off_, clip_, ang)
        _, off, clip, view_ang = best
        follow.data.clip_start = clip
        follow.data.clip_end = 200
        prev = None
        for f in range(F0, F1 + 1):
            sc.frame_set(f)
            p = rig.matrix_world.translation.copy()
            p.z = max(0.0, p.z)
            p = p if prev is None else prev * 0.6 + p * 0.4  # gentle smoothing of the follow
            prev = p
            tgt = p + Vector((0, 0, 0.95))
            follow.location = p + off
            follow.rotation_euler = (tgt - follow.location).to_track_quat("-Z", "Y").to_euler()
            follow.keyframe_insert("location", frame=f)
            follow.keyframe_insert("rotation_euler", frame=f)
        sc.camera = follow
    else:
        cam = sc.objects[name]
        show_workers(None)
        workbench()  # EEVEE even at 1 sample is ~7 s/frame here (36 deforming workers + shadow maps): QA only
        sc.camera = cam
    sc.render.filepath = str(d / "####")
    bpy.ops.render.render(animation=True)
    (d / "done").write_text(f"{time.time() - t0:.1f}", encoding="utf-8")
    print("QAR done", name, f"{time.time() - t0:.1f}s", flush=True)
