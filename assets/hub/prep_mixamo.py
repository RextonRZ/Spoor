"""Bake the 17 Mixamo clips (rigged on the CC BY vest worker) into ONE library .blend that people.py appends from.

  blender -b --factory-startup -P assets/hub/prep_mixamo.py

Each Mixamo FBX holds the same skinned worker. The mesh + rig come in once (from Breathing Idle), the four mesh
parts are joined and decimated to ~30k triangles (a CCTV camera sees a worker as a few hundred pixels tall); the other
16 files only contribute their action. Root motion is measured and removed: every clip ends up in place, and its
true ground speed is stored on the action (people.py moves the worker along a path at that speed, so feet don't
slide). For in-place clips the speed comes from the planted foot sliding back under the hips. Turning clips store the
yaw they add. Output: build/third_party/mixamo/mixamo_worker.blend (gitignored with the FBXs).
"""

import json
import math
import statistics
from pathlib import Path

import bmesh
import bpy

MIX = Path(__file__).resolve().parent / "build" / "third_party" / "mixamo"
OUT = MIX / "mixamo_worker.blend"
FPS = 30.0
TARGET_TRIS = 30000
BAKE_PX = 2048

FIRST = "Breathing Idle"


def fcurves(act):
    out = []
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for cb in getattr(strip, "channelbags", []):
                out += list(cb.fcurves)
    return out or list(getattr(act, "fcurves", []))


def import_fbx(path):
    before_o, before_a = set(bpy.data.objects), set(bpy.data.actions)
    bpy.ops.import_scene.fbx(filepath=str(path))
    return ([o for o in bpy.data.objects if o not in before_o], [a for a in bpy.data.actions if a not in before_a])


def world(arm, bone):
    return arm.matrix_world @ arm.pose.bones[bone].head


def measure(arm, act):
    """Ground speed, net displacement, added yaw and lowest foot height of one clip on this armature."""
    sc = bpy.context.scene
    arm.animation_data.action = act
    if getattr(act, "slots", None):
        arm.animation_data.action_slot = act.slots[0]
    f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
    hips, feet, yaw = [], [], []
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        hips.append(world(arm, "mixamorig:Hips").copy())
        feet.append([world(arm, f"mixamorig:{s}ToeBase").copy() for s in ("Left", "Right")])
        m = arm.matrix_world @ arm.pose.bones["mixamorig:Hips"].matrix
        fwd = m.to_3x3().col[2]  # Mixamo hips +Z bone axis points forward
        yaw.append(math.atan2(fwd.y, fwd.x))
    dur = (f1 - f0) / FPS
    net = hips[-1] - hips[0]
    net_xy = math.hypot(net.x, net.y)
    # foot speed relative to the hips while that foot is planted (lowest 25 % of its height)
    rel = []
    for s in (0, 1):
        zs = [fe[s].z for fe in feet]
        low = sorted(zs)[len(zs) // 4]
        for k in range(1, len(feet)):
            if feet[k][s].z <= low and feet[k - 1][s].z <= low:
                d = (feet[k][s] - hips[k]) - (feet[k - 1][s] - hips[k - 1])
                rel.append(math.hypot(d.x, d.y) * FPS)
    foot_speed = statistics.median(rel) if rel else 0.0
    dyaw = (yaw[-1] - yaw[0] + math.pi) % (2 * math.pi) - math.pi
    min_foot = min(min(fe[0].z, fe[1].z) for fe in feet)
    root_fwd = []
    if net_xy > 0.3:  # the hips' forward travel per clip frame (uneven: a push starts standing, steps in bursts)
        ux, uy = net.x / net_xy, net.y / net_xy
        root_fwd = [round((h.x - hips[0].x) * ux + (h.y - hips[0].y) * uy, 4) for h in hips]
    return dict(seconds=round(dur, 2), net_xy_m=round(net_xy, 2), root_speed=round(net_xy / dur, 2) if dur else 0,
                foot_speed=round(foot_speed, 2), yaw_deg=round(math.degrees(dyaw)), min_foot_z=round(min_foot, 3),
                hip_z=round(hips[0].z, 3), root_fwd=root_fwd)


LOOP_BONES = ["Spine", "Spine1", "Spine2", "Neck", "Head", "LeftArm", "LeftForeArm", "RightArm", "RightForeArm",
              "LeftUpLeg", "LeftLeg", "RightUpLeg", "RightLeg"]


def loop_window(arm, act, min_len=60):
    """A clip that opens standing (Push) pops back to that pose every time it loops. Find the two most alike poses
    (body-part rotations + hip height) at least min_len clip frames apart inside the clip: looping only that
    stretch gives a seamless, continuous action."""
    sc = bpy.context.scene
    arm.animation_data.action = act
    if getattr(act, "slots", None):
        arm.animation_data.action_slot = act.slots[0]
    f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
    poses = []
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        q = [arm.pose.bones[f"mixamorig:{b}"].matrix_basis.to_quaternion() for b in LOOP_BONES]
        poses.append((q, world(arm, "mixamorig:Hips").z))
    # only inside the longest run where he is actually working (hips lowered vs. the upright frames at the ends)
    hz = [h for _, h in poses]
    upright = max(hz[0], hz[-1])
    working = [h < upright - 0.03 for h in hz]
    runs, start = [], None
    for i, w in enumerate(working + [False]):
        if w and start is None:
            start = i
        elif not w and start is not None:
            runs.append((start, i - 1))
            start = None
    if not runs:
        return (0.0, 0, len(poses) - 1)
    r0, r1 = max(runs, key=lambda r: r[1] - r[0])
    min_len = min(min_len, max(10, (r1 - r0) * 2 // 3))
    best = None
    for a in range(r0, r1 - min_len + 1):
        for b in range(a + min_len, r1 + 1):
            d = sum(1 - abs(x.dot(y)) for x, y in zip(poses[a][0], poses[b][0])) + 4 * abs(poses[a][1] - poses[b][1])
            if best is None or d < best[0]:
                best = (d, a, b)
    return best or (0.0, r0, r1)


def loop_window_any(arm, act, min_frac=0.6):
    """Seamless loop for any in-place clip: the two most alike poses at least min_frac of the clip apart."""
    sc = bpy.context.scene
    arm.animation_data.action = act
    if getattr(act, "slots", None):
        arm.animation_data.action_slot = act.slots[0]
    f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
    poses = []
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        poses.append(([arm.pose.bones[f"mixamorig:{b}"].matrix_basis.to_quaternion() for b in LOOP_BONES],
                      world(arm, "mixamorig:Hips").z))
    n = len(poses)
    min_len = max(10, int(n * min_frac))
    best = None
    for a in range(0, n - min_len, 2):
        for b in range(a + min_len, n, 2):
            d = sum(1 - abs(x.dot(y)) for x, y in zip(poses[a][0], poses[b][0])) + 4 * abs(poses[a][1] - poses[b][1])
            if best is None or d < best[0]:
                best = (d, a, b)
    return best


def make_in_place(act):
    """Take out ALL of the hips' forward travel (raw Z = forward on this rig) so it can be put back exactly, frame by
    frame, as the worker's own motion (root_fwd); the sideways sway (raw X) keeps all but its tiny net drift."""
    for fc in fcurves(act):
        if fc.data_path == 'pose.bones["mixamorig:Hips"].location' and fc.array_index == 2:
            ks = fc.keyframe_points
            z0 = ks[0].co.y if len(ks) else 0.0
            for kp in ks:
                d = kp.co.y - z0
                kp.co.y -= d
                kp.handle_left.y -= d
                kp.handle_right.y -= d
            fc.update()
        if fc.data_path == 'pose.bones["mixamorig:Hips"].location' and fc.array_index == 0:
            ks = fc.keyframe_points
            if len(ks) < 2:
                continue
            x0, y0, x1, y1 = ks[0].co.x, ks[0].co.y, ks[-1].co.x, ks[-1].co.y
            for kp in ks:
                k = (kp.co.x - x0) / (x1 - x0) if x1 != x0 else 0
                off = y0 + (y1 - y0) * k - y0
                kp.co.y -= off
                kp.handle_left.y -= off
                kp.handle_right.y -= off
            fc.update()


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.fps = int(FPS)
objs, acts = import_fbx(MIX / f"{FIRST}.fbx")
arm = next(o for o in objs if o.type == "ARMATURE")
meshes = [o for o in objs if o.type == "MESH"]
tris0 = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in meshes)
bpy.ops.object.select_all(action="DESELECT")
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
bpy.ops.object.join()
hi = meshes[0]
body = hi.copy()
body.data = hi.data.copy()
bpy.context.scene.collection.objects.link(body)
# The scan arrives as 4 jigsaw pieces of ONE surface, not welded: decimating opens their borders into cracks
# (black lines on the vest). Weld the low-poly copy into one closed surface first.
bm_w = bmesh.new()
bm_w.from_mesh(body.data)
welded = len(bm_w.verts)
bmesh.ops.remove_doubles(bm_w, verts=bm_w.verts, dist=0.0015)
welded -= len(bm_w.verts)
bm_w.to_mesh(body.data)
bm_w.free()
body.name = "mixamo_worker_body"
bpy.ops.object.select_all(action="DESELECT")
body.select_set(True)
bpy.context.view_layer.objects.active = body
dec = body.modifiers.new("decimate", "DECIMATE")
dec.ratio = TARGET_TRIS / tris0
bpy.ops.object.modifier_move_to_index(modifier="decimate", index=0)
bpy.ops.object.modifier_apply(modifier="decimate")
arm.name = "mixamo_worker_rig"

# Colour: the scan's texture is hundreds of tiny UV scraps (decimating smears faces across them: hair sampling
# shirt red), so the full 360k scan's colour is baked onto fresh UVs of the welded 30k mesh, with a wide margin so
# island borders never sample the empty background.
old_uvs = [u.name for u in body.data.uv_layers]
uv = body.data.uv_layers.new(name="baked")
body.data.uv_layers.active = uv
bpy.ops.object.select_all(action="DESELECT")
body.select_set(True)
bpy.context.view_layer.objects.active = body
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(70), island_margin=0.006)
bpy.ops.object.mode_set(mode="OBJECT")
img = bpy.data.images.new("mixamo_worker_albedo", BAKE_PX, BAKE_PX)
mat = bpy.data.materials.new("mixamo_worker_baked")
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes.get("Principled BSDF")
bsdf.inputs["Roughness"].default_value = 0.75
tex = nt.nodes.new("ShaderNodeTexImage")
tex.image = img
nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
nt.nodes.active = tex
body.data.materials.clear()
body.data.materials.append(mat)
arm.data.pose_position = "REST"
sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = 4
sc.render.bake.target = "IMAGE_TEXTURES"
bpy.ops.object.select_all(action="DESELECT")
hi.select_set(True)
body.select_set(True)
bpy.context.view_layer.objects.active = body
bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, use_selected_to_active=True, cage_extrusion=0.04,
                    max_ray_distance=0.2, margin=24, margin_type="EXTEND")
img.pack()
for n in old_uvs:
    body.data.uv_layers.remove(body.data.uv_layers[n])
body.data.uv_layers["baked"].active_render = True
arm.data.pose_position = "POSE"
hi_mesh = hi.data
bpy.data.objects.remove(hi, do_unlink=True)
bpy.data.meshes.remove(hi_mesh)
clips = {FIRST: acts[0]}
for f in sorted(MIX.glob("*.fbx")):
    if f.stem == FIRST:
        continue
    o2, a2 = import_fbx(f)
    clips[f.stem] = a2[0]
    for o in o2:
        data = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if data is not None and data.users == 0:
            (bpy.data.meshes if isinstance(data, bpy.types.Mesh) else bpy.data.armatures).remove(data)
report = {"welded_verts": welded, "source_tris": tris0, "tris": sum(len(p.vertices) - 2 for p in body.data.polygons), "clips": {}}
for name, act in clips.items():
    m = measure(arm, act)
    root_motion = m["net_xy_m"] > 0.3
    if root_motion:
        make_in_place(act)
    speed = m["root_speed"] if root_motion else m["foot_speed"]
    act.name = "mx_" + name.lower().replace(" ", "_")
    act.use_fake_user = True
    act["speed"] = speed if speed > 0.15 else 0.0
    act["root_speed"] = m["root_speed"]  # drift a clip like Talking Phone Pacing really makes (forward)
    act["root_motion_removed"] = root_motion
    act["yaw_deg"] = m["yaw_deg"]
    act["hip_z"] = m["hip_z"]
    act["min_foot_z"] = m["min_foot_z"]
    act["root_fwd"] = m["root_fwd"]
    if root_motion and name in ("Push", "Pushing"):  # clips that open/close standing (walk clips are true cycles)
        d, a, b = loop_window(arm, act)
        act["loop_a"], act["loop_b"] = a, b
        m["loop"] = [a, b, round(d, 3)]
    elif not root_motion and name not in ("Sit To Type", "Carrying Turn") and m["seconds"] > 2.0:
        d, a, b = loop_window_any(arm, act)  # loops seamlessly (no pop back to the clip's first pose)
        act["loop_a"], act["loop_b"] = a, b
        m["loop"] = [a, b, round(d, 3)]
    report["clips"][act.name] = dict({k: v for k, v in m.items() if k != "root_fwd"}, root_motion_removed=root_motion,
                                     speed_used=act["speed"])
arm.animation_data.action = clips[FIRST]
for m in body.data.materials:
    m.use_fake_user = True
for c in (arm, body):
    c.use_fake_user = True
bpy.ops.outliner.orphans_purge(do_recursive=True)
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT), compress=True)
report["out"] = str(OUT)
report["out_mb"] = round(OUT.stat().st_size / 1e6, 1)
print("PREP " + json.dumps(report), flush=True)
