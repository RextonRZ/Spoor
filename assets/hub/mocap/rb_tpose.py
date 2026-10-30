"""M1 (014_GO): Rocketbox rig facts for the retarget + the shared T-pose.

  blender -b --factory-startup -P assets/hub/mocap/rb_tpose.py -- --avatar Male_Adult_04 --out qa/review/m1

For one avatar: imports the FBX, writes bones_<avatar>.txt (name, parent, rest head/tail in metres, length, the
head->child direction, the unit scale the importer applied, bind-pose arm angle), then poses a SWING-ONLY T-pose
(each bone turned about its head by the shortest arc from its bind direction to the T direction: no twist added,
so the bind's palm orientation is kept) with relaxed static fingers, and renders it front + side (EEVEE).
The same T-pose is what retarget.py aligns the BVH T-pose to (M2).
"""
import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ap = argparse.ArgumentParser()
ap.add_argument("--avatar", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--rb", default=str(Path(__file__).resolve().parents[1] / "build" / "third_party" / "rocketbox"))
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
OUT = Path(a.out).resolve()
OUT.mkdir(parents=True, exist_ok=True)
sc = bpy.context.scene

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.import_scene.fbx(filepath=str(Path(a.rb) / a.avatar / f"{a.avatar}.fbx"))
arm = next(o for o in sc.objects if o.type == "ARMATURE")
body = max((o for o in sc.objects if o.type == "MESH"), key=lambda o: len(o.data.vertices))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import people  # noqa: E402

for o in sc.objects:
    if o.type == "MESH":
        people._fix_materials(o, Path(a.rb) / a.avatar)
for o in sc.objects:  # the importer may leave an animation on: rest pose only
    if o.animation_data:
        o.animation_data.action = None
bpy.context.view_layer.update()
MW = arm.matrix_world
B = arm.data.bones


def P(n):
    return B.get(f"Bip01 {n}")


def child_of(b):
    """The bone's 'along' child: the first child whose head is not at the bone's head (Biped tails are unreliable)."""
    best = None
    for c in b.children:
        d = (c.head_local - b.head_local).length
        if d > 1e-4 and (best is None or c.name.endswith(("Finger2", "Forearm", "Calf", "Foot", "Neck", "Head", "Spine1",
                                                              "Spine2", "UpperArm"))):
            best = c
    return best


def world(v):
    return MW @ v


# ---------------------------------------------------------------- facts
UP = Vector((0, 0, 1))
left = world(P("L Thigh").head_local) - world(P("R Thigh").head_local)  # the hip line (toes splay ~14 deg out)
left.z = 0
left.normalize()
fwd = left.cross(UP).normalized()
head_top = max((body.matrix_world @ v.co).z for v in body.data.vertices)
lines = [f"avatar {a.avatar}",
         f"armature object scale {tuple(round(s, 6) for s in arm.scale)}  (FBX unit scale applied by the importer: "
         f"{arm.scale.x:.4f} => bone units x {arm.scale.x:.4f} = metres)",
         f"mesh height (top of head) {head_top:.3f} m",
         f"facing (normal to the hip line) {tuple(round(c, 3) for c in fwd)}; left {tuple(round(c, 3) for c in left)}"]
for sd, sg in (("L", 1), ("R", -1)):
    ua, fa = P(f"{sd} UpperArm"), P(f"{sd} Forearm")
    d = (world(fa.head_local) - world(ua.head_local)).normalized()
    below = math.degrees(math.asin(-d.z))
    fwd_ = math.degrees(math.asin(max(-1, min(1, d.dot(fwd)))))
    lines.append(f"bind upper arm {sd}: {below:.1f} deg below horizontal, {fwd_:.1f} deg forward of the frontal plane "
                 f"(dir {tuple(round(c, 3) for c in d)})")
lines.append("")
lines.append(f"{'bone':28s} {'parent':28s} {'head_m (world)':>26s} {'len_m':>6s}  along(child)")
for b in B:
    h = world(b.head_local)
    c = child_of(b)
    along = ""
    if c:
        dv = (world(c.head_local) - h).normalized()
        along = f"{c.name} {tuple(round(x, 3) for x in dv)}"
    lines.append(f"{b.name:28s} {(b.parent.name if b.parent else '-'):28s} "
                 f"{'(%.3f, %.3f, %.3f)' % tuple(h):>26s} {(world(b.tail_local) - h).length:6.3f}  {along}")
(OUT / f"bones_{a.avatar}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines[:8]), flush=True)

# ---------------------------------------------------------------- swing-only T-pose
pb = arm.pose.bones
Mi = MW.inverted()


def pose_head(n):
    return MW @ pb[n].matrix.translation


def swing(n, toward_child, target):
    """Turn bone n about its head by the shortest arc taking (child head - head) onto target (world)."""
    bpy.context.view_layer.update()
    h = pose_head(n)
    d = (pose_head(toward_child) - h).normalized()
    q = d.rotation_difference(target.normalized())
    R = Mi.to_3x3() @ q.to_matrix() @ MW.to_3x3()  # armature space
    hl = pb[n].matrix.translation.copy()
    pb[n].matrix = Matrix.Translation(hl) @ R.to_4x4() @ Matrix.Translation(-hl) @ pb[n].matrix


SPINE = ["Spine", "Spine1", "Spine2", "Neck", "Head"]
spine = [f"Bip01 {n}" for n in SPINE if P(n)]
for i in range(len(spine) - 1):
    swing(spine[i], spine[i + 1], UP)
for sd, out in (("L", left), ("R", -left)):
    swing(f"Bip01 {sd} UpperArm", f"Bip01 {sd} Forearm", out)
    swing(f"Bip01 {sd} Forearm", f"Bip01 {sd} Hand", out)
    swing(f"Bip01 {sd} Hand", f"Bip01 {sd} Finger2", out)
    swing(f"Bip01 {sd} Thigh", f"Bip01 {sd} Calf", -UP)
    swing(f"Bip01 {sd} Calf", f"Bip01 {sd} Foot", -UP)
bpy.context.view_layer.update()

# ---------------------------------------------------------------- relaxed static fingers
CURL = {0: (8, 12, 10), 1: (10, 18, 12), 2: (12, 20, 14), 3: (14, 22, 15), 4: (16, 24, 16)}  # deg, MCP/PIP/DIP


def segs(sd, f):
    base = f"Bip01 {sd} Finger{f}"
    return [n for n in (base, base + "1", base + "2") if n in pb]


for sd in ("L", "R"):
    h = pose_head(f"Bip01 {sd} Hand")
    n_ = (pose_head(segs(sd, 1)[0]) - h).cross(pose_head(segs(sd, 4)[0] if segs(sd, 4) else segs(sd, 3)[0]) - h)
    thumb = segs(sd, 0)
    if n_.dot(pose_head(thumb[-1]) - h) < 0:  # palm side = the side the thumb sits on
        n_ = -n_
    n_.normalize()
    for f in range(5):
        chain = segs(sd, f)
        for k, nm in enumerate(chain):
            bpy.context.view_layer.update()
            hh = pose_head(nm)
            nxt = chain[k + 1] if k + 1 < len(chain) else None
            d = ((pose_head(nxt) - hh) if nxt else (MW @ pb[nm].tail - hh)).normalized()
            ax = d.cross(n_)
            if ax.length < 1e-4:
                continue
            ang = math.radians(CURL[f][min(k, 2)] * (0.5 if f == 0 else 1.0))
            R = Mi.to_3x3() @ Matrix.Rotation(ang, 3, ax.normalized()) @ MW.to_3x3()
            hl = pb[nm].matrix.translation.copy()
            pb[nm].matrix = Matrix.Translation(hl) @ R.to_4x4() @ Matrix.Translation(-hl) @ pb[nm].matrix
bpy.context.view_layer.update()

# T-pose check: arms horizontal + lateral, legs vertical
chk = []
for sd, out in (("L", left), ("R", -left)):
    d = (pose_head(f"Bip01 {sd} Hand") - pose_head(f"Bip01 {sd} UpperArm")).normalized()
    chk.append(f"T-pose {sd} arm: {math.degrees(d.angle(out)):.2f} deg off lateral-horizontal")
    d = (pose_head(f"Bip01 {sd} Foot") - pose_head(f"Bip01 {sd} Thigh")).normalized()
    chk.append(f"T-pose {sd} leg: {math.degrees(d.angle(-UP)):.2f} deg off vertical")
with open(OUT / f"bones_{a.avatar}.txt", "a", encoding="utf-8") as fh:
    fh.write("\n" + "\n".join(chk) + "\n")
print("\n".join(chk), flush=True)

# ---------------------------------------------------------------- render front + side
sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in {e.identifier for e in
                                                                   bpy.types.RenderSettings.bl_rna.properties["engine"]
                                                                   .enum_items} else "BLENDER_EEVEE"
sc.render.resolution_x, sc.render.resolution_y = 1080, 1080
sc.render.image_settings.file_format = "PNG"
w = bpy.data.worlds.new("w")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.35, 0.36, 0.38, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
sc.world = w
ld = bpy.data.lights.new("key", "SUN")
ld.energy = 3.0
lo = bpy.data.objects.new("key", ld)
sc.collection.objects.link(lo)
lo.rotation_euler = (math.radians(50), 0, math.radians(30))
c = Vector((0, 0, head_top / 2)) + MW.translation * Vector((1, 1, 0))
for tag, dirv in (("front", fwd), ("side", left)):
    cd = bpy.data.cameras.new(tag)
    cd.type, cd.ortho_scale = "ORTHO", 2.1
    cam = bpy.data.objects.new(tag, cd)
    sc.collection.objects.link(cam)
    cam.location = c + dirv * 6
    cam.rotation_euler = (-dirv).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    sc.render.filepath = str(OUT / f"tpose_{a.avatar}_{tag}.png")
    bpy.ops.render.render(write_still=True)
# close-up of the left hand from above and from the front (relaxed static fingers)
hl = pose_head("Bip01 L Hand") + left * 0.08
for tag, dirv in (("hand_top", UP), ("hand_front", fwd)):
    cd = bpy.data.cameras.new(tag)
    cd.type, cd.ortho_scale = "ORTHO", 0.32
    cam = bpy.data.objects.new(tag, cd)
    sc.collection.objects.link(cam)
    cam.location = hl + dirv * 2
    cam.rotation_euler = (-dirv).to_track_quat("-Z", "Y" if dirv is fwd else "Z").to_euler()
    if dirv is UP:
        cam.rotation_euler = (-dirv).to_track_quat("-Z", "X").to_euler()
    cd.clip_start = 0.5
    sc.camera = cam
    sc.render.resolution_x = sc.render.resolution_y = 720
    sc.render.filepath = str(OUT / f"tpose_{a.avatar}_{tag}.png")
    bpy.ops.render.render(write_still=True)
print("M1 done", a.avatar, flush=True)
