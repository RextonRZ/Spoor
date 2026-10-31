"""Mixamo vest workers: the CC BY 'Construction Worker in Safety Vest' rigged on Mixamo, with all 17 Mixamo clips.

Imported by people.add_workers(). The rig, a decimated body (~30k tris) and the 17 actions come from ONE library
file baked by prep_mixamo.py (build/third_party/mixamo/mixamo_worker.blend), so the hub holds one copy of the
worker. Retargeting Mixamo motion onto the Rocketbox (Biped) skeletons was not reliable enough (different bone axes
and proportions -> wrist / shoulder flips), so these roles use the vest worker itself, with colour variants: shirt
(red original / teal uniform / navy / grey) and vest (yellow original / orange / lime).

Every clip is in place (prep removed root motion and stored the true ground speed), so movers follow a path at the
clip's own speed (feet don't slide); Talking Phone Pacing keeps its own root motion (a 42 s clip never wraps within a
30 s scenario).
"""

import math
import random
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

import people as P

CLIP_FPS = 30.0
FACING_OFFSET = math.radians(90)  # the vest worker faces -Y at rest (as Rocketbox): +90° -> +X at heading 0
SHIRTS = {"red": None, "teal": (0.012, 0.2, 0.19), "navy": (0.018, 0.03, 0.085), "grey": (0.09, 0.09, 0.088)}
SOLE_LIFT = 0.016  # the scan's soles sit 1.6 cm into the floor on every clip (gesture audit: lowest point -0.017)
SKIN = (0.46, 0.26, 0.17, 1.0)  # linear; light-medium tan, close to the scanned face
VEST_HUE = {"yellow": 0.0, "orange": -0.125, "lime": 0.07}  # hue shift of the vest's own yellow

# Mixamo roles (owner's clip-per-role list). keys: role, clip or seq [(clip, seconds | "once")], at+face or path,
# shirt, vest; optional: hat, carry (box in hands), cage (pushed roll cage), one_way (walk the path once, then
# breathing idle), loop (repeat the seq), seat, hmi / dockbox (furniture placed with the worker), drift (root motion)
CARRY = [("carrying", 3.5), ("carrying_turn", "once"), ("carrying", 2.5), ("carrying_turn", "once"), ("carrying", 0.6),
         ("carrying_turn", "once"), ("carrying", 0.6), ("carrying_turn", "once")]  # W stack, S belt, quick E / N
STATIONS = [
    # walking between stations: W1 -> zebra ZX2 across the forklift lane, and back
    # walking from the office door the full length of walkway W1 towards the docks (48 m = the whole 30 s)
    dict(role="walk", clip="walking", path=[(51.0, 1.35), (5.9, 1.35)], one_way=True, shirt="teal", vest="orange",
         hat=None),  # starts west of the supervisor: never passes through him
    dict(role="walk", clip="walking", path=[(57.5, 23.8), (14.0, 23.8)], one_way=True, shirt="grey", vest="lime",
         hat=None),  # bagging aisle W3
    # lifting: heavy parcel from the west pallet in Z09 (clear of the forklift lane, x < 7.5) and a full bag at C08
    # picking up: induction (one parcel at a time, scan gesture) and bagging at a chute
    # pushing roll cages at walking pace with the calm Push clip (Pushing leans in like a heavy load: owner said too
    # much for a roll cage): along the staging aisle (never arrives within 30 s) and staging -> door D12 across the
    # lane (arrives after ~22 s, then waits)
    # pushers: an upright walk at ~1 m/s (HSE: roll cages pushed no faster than walking pace, handles ~1 m) with
    # both hands IK'd on the cage's back posts - the Mixamo push clips lean 45 deg like shoving a wall (QA)
    dict(role="cages", clip="walking", rate=0.62, path=[(52.0, 28.85), (25.6, 28.85)], one_way=True, shirt="navy",
         vest="orange", cage=True, lead_frames=25),  # along the staging aisle between the two bay rows (y 28.2-29.5)
    dict(role="cages", clip="walking", rate=0.62, path=[(49.0, 37.7), (49.0, 28.85), (25.6, 28.85)], one_way=True,
         shirt="teal",
         vest="yellow",
         cage=True, hat=None, lead_frames=25),  # bringing an emptied cage back from door D12 to staging
    # technician at an HMI next to the DWS tunnel (Button Pushing), then waiting (Breathing Idle)
    dict(role="technician", seq=[("button_pushing", 9.0), ("breathing_idle", None)], at=(21.2, 13.05), face=90,
         shirt="grey", vest="yellow", hat=None, hmi=(21.2, 13.65)),
    # dock-control box beside outbound door D09
    dict(role="dock", seq=[("button_pushing", "once"), ("breathing_idle", None)], at=(39.35, 39.25), face=90,
         shirt="teal", vest="lime", hat=None, dockbox=(39.35, 39.8)),  # presses once, then watches the door
    # talking at a station: partner of the Rocketbox talker at the outbound queue
    dict(role="idle", clip="talking", at=(37.0, 36.65), face=90, shirt="red", vest="orange"),
    # the ONE supervisor, on walkway W1 outside the office: on the phone, then pacing (its own slow drift)
    # (both clips start where the phone is already at his ear: they open with the hand coming up from his side)
    dict(role="supervisor", seq=[("talking_on_phone", None, 80)], at=(52.6, 1.0), face=180, shirt="navy",
         vest="orange", hat=None, device="phone"),  # standing call (the pacing clip's feet slid: QA)
    # exception bench: seated on a raised stool (bench top 0.9 m) at the east corner, settles in to type, types
    # (faces 60°, not 90°: square to the bench he would face CAM_12 across it for the whole clip)
    dict(role="exception", seq=[("typing", 5.0), ("sit_to_type", "once"), ("typing", None)], at=(27.35, 20.55),
         face=125, shirt="teal", vest="yellow", seat=True),
    # break table at the edge (Z11 side, between walkway W5 and the racks)
    dict(role="break", clip="talking_when_sit", at=(4.3, 32.1), face=270, shirt="red", vest="lime", seat=True),
    dict(role="break", clip="texting_while_standing", at=(5.75, 31.9), face=200, shirt="teal", vest="orange",
         device="phone"),
    # on the phone, walking W5b -> W5 to the break table (last step off the walkway, to the table), then stands
    dict(role="to_break", clip="walking_while_texting", path=[(13.8, 25.0), (13.8, 29.2), (6.0, 29.2), (6.0, 30.45)],
         one_way=True, arrive="texting_while_standing", shirt="grey", vest="yellow", device="phone"),
]
BREAK_TABLE = (4.55, 31.35)

_lib = {}


# ------------------------------------------------------------------------------------------------ library
def _load(lib_path, scene):
    if _lib:
        return _lib
    with bpy.data.libraries.load(str(lib_path), link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n in ("mixamo_worker_rig", "mixamo_worker_body")]
        dst.actions = [n for n in src.actions if n.startswith("mx_")]
    hide = P._hidden_collection(scene)
    for o in dst.objects:
        hide.objects.link(o)
    rig = next(o for o in dst.objects if o.type == "ARMATURE")
    body = next(o for o in dst.objects if o.type == "MESH")
    rig.animation_data_clear()
    head = {g.index for g in body.vertex_groups if g.name == "mixamorig:Head"}
    _lib.update(rig=rig, body=body, actions={a.name[3:]: a for a in dst.actions},
                head_verts=[v.index for v in body.data.vertices if any(g.group in head and g.weight > 0.8
                                                                      for g in v.groups)])
    return _lib


def _variant_material(base, shirt, vest):
    """Recolour the baked texture: the red shirt (hue test) and the yellow vest (hue shift); skin, trousers, boots
    and the silver bands keep their own colours."""
    key = f"mx_worker_{shirt}_{vest}"
    if key in P._mats:
        return P._mats[key]
    m = base.copy()
    m.name = key
    P._mats[key] = m
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    link = next((lk for lk in nt.links if lk.to_socket == bsdf.inputs["Base Color"]), None)
    if link is None:
        return m
    src = link.from_socket
    hsv = nt.nodes.new("ShaderNodeSeparateColor")
    hsv.mode = "HSV"
    nt.links.new(src, hsv.inputs["Color"])
    h, s, v = hsv.outputs[0], hsv.outputs[1], hsv.outputs[2]
    out = src
    if SHIRTS[shirt] is not None:
        red = P._m(nt, "MULTIPLY", P._m(nt, "MAXIMUM", P._m(nt, "LESS_THAN", h, 0.035), P._m(nt, "GREATER_THAN", h, 0.95)),
                   P._m(nt, "MULTIPLY", P._m(nt, "GREATER_THAN", s, 0.62), P._m(nt, "GREATER_THAN", v, 0.06)))
        # (saturated, not dark: brown hair and reddish skin stay as they are; and below the neck only: lips / ears)
        tcn = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(tcn.outputs["Generated"], sep.inputs["Vector"])
        red = P._m(nt, "MULTIPLY", red, P._m(nt, "LESS_THAN", sep.outputs["Z"], 0.83))
        tint = nt.nodes.new("ShaderNodeMix")
        tint.data_type, tint.blend_type = "RGBA", "MULTIPLY"
        tint.inputs["Factor"].default_value = 1.0
        tint.inputs["A"].default_value = (*[c * 2.5 for c in SHIRTS[shirt]], 1)
        nt.links.new(v, tint.inputs["B"])
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        nt.links.new(red, mix.inputs["Factor"])
        nt.links.new(out, mix.inputs["A"])
        nt.links.new(tint.outputs["Result"], mix.inputs["B"])
        out = mix.outputs["Result"]
    if VEST_HUE[vest]:
        yel = P._m(nt, "MULTIPLY", P._m(nt, "MULTIPLY", P._m(nt, "GREATER_THAN", h, 0.1), P._m(nt, "LESS_THAN", h, 0.22)),
                   P._m(nt, "GREATER_THAN", s, 0.45))
        hs = nt.nodes.new("ShaderNodeHueSaturation")
        hs.inputs["Hue"].default_value = 0.5 + VEST_HUE[vest]
        nt.links.new(src, hs.inputs["Color"])
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        nt.links.new(yel, mix.inputs["Factor"])
        nt.links.new(out, mix.inputs["A"])
        nt.links.new(hs.outputs["Color"], mix.inputs["B"])
        out = mix.outputs["Result"]
    # hands: the scan never saw into the finger gaps (black patches, pale grey fingers): an even skin tone, keeping
    # only a little of the scan's shading. Hands are the outermost part of the T-pose rest (generated X).
    tc2 = nt.nodes.new("ShaderNodeTexCoord")
    sep2 = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc2.outputs["Generated"], sep2.inputs["Vector"])
    hand = P._m(nt, "GREATER_THAN", P._m(nt, "ABSOLUTE", P._m(nt, "SUBTRACT", sep2.outputs["X"], 0.5)), 0.405)
    shade = nt.nodes.new("ShaderNodeMapRange")  # 0.85 .. 1.0 of the skin tone from the scan's own brightness
    nt.links.new(v, shade.inputs["Value"])
    shade.inputs["From Min"].default_value, shade.inputs["From Max"].default_value = 0.0, 0.6
    shade.inputs["To Min"].default_value, shade.inputs["To Max"].default_value = 0.85, 1.0
    skin = nt.nodes.new("ShaderNodeMix")
    skin.data_type, skin.blend_type = "RGBA", "MULTIPLY"
    skin.inputs["Factor"].default_value = 1.0
    skin.inputs["A"].default_value = SKIN
    nt.links.new(shade.outputs["Result"], skin.inputs["B"])
    hm = nt.nodes.new("ShaderNodeMix")
    hm.data_type = "RGBA"
    nt.links.new(hand, hm.inputs["Factor"])
    nt.links.new(out, hm.inputs["A"])
    nt.links.new(skin.outputs["Result"], hm.inputs["B"])
    nt.links.new(hm.outputs["Result"], bsdf.inputs["Base Color"])
    return m


def _instance(coll, name, st):
    rig = _lib["rig"].copy()
    rig.name = name
    rig.animation_data_clear()
    coll.objects.link(rig)
    body = _lib["body"].copy()
    body.name = f"{name}_body"
    body.parent = rig
    for md in body.modifiers:
        if md.type == "ARMATURE":
            md.object = rig
    coll.objects.link(body)
    for slot in body.material_slots:
        if slot.material:
            slot.link = "OBJECT"
            slot.material = _variant_material(_lib["body"].material_slots[0].material, st["shirt"], st["vest"])
    return rig, body


# ------------------------------------------------------------------------------------------------ motion
def _strip(rig, act, start, fps, track, until=None, extrap="HOLD_FORWARD", once=False, clip_from=0, xfade=False,
           rate=1.0):
    ad = rig.animation_data_create()
    if xfade and not once:  # standing loops: crossfaded seams (path-driven clips keep one strip: feet stay in phase)
        f0 = act.frame_range[0]
        a0 = f0 + (int(act["loop_a"]) if "loop_a" in act else 0) + clip_from
        a1 = f0 + int(act["loop_b"]) if "loop_b" in act else act.frame_range[1]
        return P.crossfade_loop(ad, act, start, until or 420, fps / CLIP_FPS, a0, a1, track,
                                first_extrap="HOLD" if extrap == "HOLD" else "HOLD_FORWARD")
    tr = ad.nla_tracks.new()
    tr.name = track
    st = tr.strips.new(act.name, int(start), act)
    if hasattr(st, "action_slot") and getattr(act, "slots", None):
        st.action_slot = act.slots[0]
    if clip_from:  # start inside the clip (e.g. the phone already at the ear, not on its way up)
        st.action_frame_start = act.frame_range[0] + clip_from
    if "loop_a" in act and not once:  # loop only the seamless stretch (no pop back to the clip's first pose)
        f0 = act.frame_range[0]
        st.action_frame_end = f0 + int(act["loop_b"])
        st.action_frame_start = f0 + int(act["loop_a"])
    st.scale = fps / CLIP_FPS / rate
    length = (st.action_frame_end - st.action_frame_start) * st.scale
    if not once:
        st.repeat = max(1.0, ((until or 420) - start) / max(length, 1))
    st.extrapolation = extrap
    return st, length


def _key_pose(rig, frame, xy, heading, z=0.0):
    rig.location = (xy[0], xy[1], z)
    rig.rotation_euler[2] = heading + FACING_OFFSET
    rig.keyframe_insert("location", frame=frame)
    rig.keyframe_insert("rotation_euler", frame=frame)


def _set_pose(rig, xy, heading, z=0.0):
    """Static worker: no keys (people culling keeps animated-transform workers always on)."""
    rig.location = (xy[0], xy[1], z)
    rig.rotation_euler[2] = heading + FACING_OFFSET


def _interp(rig, rot_constant=False):
    for bag, fcs in P._channelbag_fcurves(rig.animation_data.action):
        for fc in fcs:
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT" if rot_constant and fc.data_path == "rotation_euler" else "LINEAR"


def _path_motion(rig, pts, speed, fps, offset, frames=420, one_way=False):
    """Along a polyline at `speed`, facing the direction of travel: back and forth, or once (returns arrival frame)."""
    seg = [(a, b, math.dist(a, b)) for a, b in zip(pts, pts[1:])]
    route = seg if one_way else seg + [(b, a, d) for a, b, d in reversed(seg)]
    period = sum(d for _, _, d in route) / speed * fps
    f = 1 - (0 if one_way else offset % period)
    while f < frames:
        for a, b, d in route:
            heading = math.atan2(b[1] - a[1], b[0] - a[0])
            _key_pose(rig, f, a, heading)
            f += d / speed * fps
            _key_pose(rig, f - 0.01, b, heading)
        if one_way:
            break
    _interp(rig)
    return f if one_way else None


def _root_dist(act, clip_t):
    """Forward distance the clip's hips have travelled after clip_t clip frames, looping (exact root motion); only
    the clip's seamless loop window when it has one (loop_a..loop_b)."""
    curve = list(act.get("root_fwd", []))
    if curve and "loop_a" in act:
        a, b = int(act["loop_a"]), int(act["loop_b"])
        curve = [c - curve[a] for c in curve[a:b + 1]]
    if not curve:
        return float(act.get("speed", 0.0)) * clip_t / CLIP_FPS
    n = len(curve) - 1
    loops, ph = divmod(max(clip_t, 0.0), n)
    i = int(ph)
    frac = ph - i
    return loops * curve[-1] + curve[i] + (curve[min(i + 1, n)] - curve[i]) * frac


def _follow_root(rig, act, pts, start, fps, frames=420, rate=1.0):
    """One way along a polyline, moved EXACTLY as far as the clip's hips travel each frame (feet stay planted:
    a push starts standing and steps in bursts). Keyed every frame from the strip start; returns the arrival frame."""
    seg = [(a, b, math.dist(a, b)) for a, b in zip(pts, pts[1:])]
    total = sum(d for _, _, d in seg)

    def at(dist):
        rem = min(max(dist, 0.0), total)
        for a, b, d in seg:
            if rem <= d or (a, b, d) == seg[-1]:
                k = rem / d if d else 0
                return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
            rem -= d
    f = start
    keys = []
    while f <= frames:
        dist = min(_root_dist(act, (f - start) * CLIP_FPS / fps * rate), total)
        keys.append((f, dist))
        if dist >= total:
            break
        f += 1
    prev_h = None
    for f, dist in keys:  # heading = travel direction smoothed over +-0.35 m: corners turn over ~0.7 m, no snap
        p0, p1 = at(dist - 0.35), at(dist + 0.35)
        h = math.atan2(p1[1] - p0[1], p1[0] - p0[0]) if (p0 != p1) else prev_h or 0.0
        if prev_h is not None:  # keep the angle continuous
            while h - prev_h > math.pi:
                h -= 2 * math.pi
            while h - prev_h < -math.pi:
                h += 2 * math.pi
        prev_h = h
        _key_pose(rig, f, at(dist), h)
    _interp(rig)
    return f


# ------------------------------------------------------------------------------------------------ props
def _box_mesh(bm):  # carried carton, ~40 x 30 x 25 cm (cm units: placed with a 0.01 scale)
    P._cube(bm, -20, -15, -12.5, 20, 15, 12.5, 0)
    P._cube(bm, -20.2, -2.5, 12.4, 20.2, 2.5, 12.7, 1)  # tape strip


def _stool_mesh(bm):  # raised steel stool, seat 0.63 m: round seat 36 cm, 4 legs, foot ring (cm, seat top z = 0)
    bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=18, radius2=18, depth=4,
                          matrix=Matrix.Translation((0, 0, -2)))
    for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        P._cube(bm, sx * 13 - 1.2, sy * 13 - 1.2, -63, sx * 13 + 1.2, sy * 13 + 1.2, -4, 1)
    P._cube(bm, -14, -14, -42, 14, 14, -40, 1)  # foot ring


def _hmi_mesh(bm):  # HMI on a stand: base plate, post, tilted screen box (cm, screen faces +Y)
    P._cube(bm, -20, -20, 0, 20, 20, 2, 1)
    P._cube(bm, -3, -3, 2, 3, 3, 120, 1)
    r = bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, 2, 132)) @ Matrix.Rotation(math.radians(-20), 4, "X")
                              @ Matrix.Diagonal((46, 8, 34, 1)))
    for fc in {fc for v in r["verts"] for fc in v.link_faces}:
        fc.material_index = 1
    r = bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, 6.2, 133.4)) @ Matrix.Rotation(math.radians(-20), 4, "X")
                              @ Matrix.Diagonal((40, 0.4, 27, 1)))
    for fc in {fc for v in r["verts"] for fc in v.link_faces}:
        fc.material_index = 2


def _dockbox_mesh(bm):  # dock-control box on the wall: grey box, red + green lamps, yellow button (cm, faces +Y)
    P._cube(bm, -15, 0, 120, 15, 12, 160, 0)
    for x, mi in ((-7, 1), (7, 2)):  # red (door moving) and green (safe) lamps
        r = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=3, radius2=3, depth=3,
                                  matrix=Matrix.Translation((x, 13.2, 152)) @ Matrix.Rotation(math.radians(90), 4, "X"))
        for fc in {fc for v in r["verts"] for fc in v.link_faces}:
            fc.material_index = mi
    P._cube(bm, -3, 12, 132, 3, 15, 138, 3)


def _table_mesh(bm):  # folding break table 1.5 x 0.75 m, 0.74 m high (cm)
    P._cube(bm, -75, -37.5, 71, 75, 37.5, 74, 0)
    for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        P._cube(bm, sx * 68 - 1.5, sy * 30 - 1.5, 0, sx * 68 + 1.5, sy * 30 + 1.5, 71, 1)


def _lathe(bm, profile, mi, seg=18):
    """Surface of revolution around Z from [(radius_cm, z_cm), ...] bottom to top, capped."""
    rings = [[bm.verts.new((r * math.cos(2 * math.pi * k / seg), r * math.sin(2 * math.pi * k / seg), z))
              for k in range(seg)] for r, z in profile]
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(seg):
            f = bm.faces.new((r0[k], r0[(k + 1) % seg], r1[(k + 1) % seg], r1[k]))
            f.material_index = mi
    for ring, rev in ((rings[0], True), (rings[-1], False)):
        f = bm.faces.new(list(reversed(ring)) if rev else ring)
        f.material_index = mi


# PET water bottles (1.5 L: 9 cm x 31 cm; 500 ml: 6.5 cm x 21 cm), ribbed, label band, blue cap; water to a level
def _pet_profile(d, h):
    r = d / 2
    return [(r * 0.8, 0), (r, 0.6), (r, h * 0.18), (r * 0.94, h * 0.2), (r, h * 0.22), (r, h * 0.6), (r * 0.94, h * 0.62),
            (r, h * 0.64), (r, h * 0.7), (r * 0.75, h * 0.82), (1.4, h * 0.92), (1.4, h * 0.97)]


def _bottle_1500(bm):
    _lathe(bm, _pet_profile(9.0, 31.0), 0)
    _lathe(bm, [(4.55, 31 * 0.3), (4.55, 31 * 0.5)], 1)  # label band
    _lathe(bm, [(1.6, 31 * 0.97), (1.6, 31 * 0.97 + 1.8)], 2)  # cap
    _lathe(bm, [(4.2, 0.7), (4.35, 6.0), (4.35, 13.5)], 3)  # water, about half full


def _bottle_500(bm):
    _lathe(bm, _pet_profile(6.5, 21.0), 0)
    _lathe(bm, [(3.3, 21 * 0.32), (3.3, 21 * 0.52)], 1)
    _lathe(bm, [(1.6, 21 * 0.97), (1.6, 21 * 0.97 + 1.6)], 2)
    _lathe(bm, [(2.95, 0.7), (3.1, 4.0), (3.1, 16.5)], 3)  # full


def _bottle_500_empty(bm):  # drunk, cap on, lying on its side (built lying along X)
    me = bmesh.new()
    _lathe(me, _pet_profile(6.5, 21.0), 0)
    _lathe(me, [(3.3, 21 * 0.32), (3.3, 21 * 0.52)], 1)
    _lathe(me, [(1.6, 21 * 0.97), (1.6, 21 * 0.97 + 1.6)], 2)
    bmesh.ops.rotate(me, verts=me.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, "Y"))
    bmesh.ops.translate(me, verts=me.verts, vec=(-10.5, 0, 3.25))
    tmp = bpy.data.meshes.new("_tmp")
    me.to_mesh(tmp)
    me.free()
    bm.from_mesh(tmp)
    bpy.data.meshes.remove(tmp)


def _mug(bm):  # ceramic mug 8 cm x 9.5 cm with coffee, handle
    _lathe(bm, [(3.6, 0), (4.0, 0.4), (4.0, 9.5), (3.7, 9.5), (3.7, 1.0)], 0)
    _lathe(bm, [(3.65, 6.8), (3.65, 7.0)], 1)  # coffee surface
    P._cube(bm, 3.9, -0.6, 2.5, 6.2, 0.6, 3.3, 0)
    P._cube(bm, 5.5, -0.6, 3.3, 6.2, 0.6, 6.8, 0)
    P._cube(bm, 3.9, -0.6, 6.8, 6.2, 0.6, 7.6, 0)


def _food_box(bm):  # closed white foam takeaway clamshell 20 x 14 x 7 cm, seam line
    P._cube(bm, -10, -7, 0, 10, 7, 3.6, 0)
    P._cube(bm, -9.6, -6.6, 3.6, 9.6, 6.6, 7.0, 0)
    P._cube(bm, -10.2, -7.2, 3.4, 10.2, 7.2, 3.8, 0)  # rim


def _phone(bm):  # phone face down
    P._cube(bm, -3.7, -7.6, 0, 3.7, 7.6, 0.85, 0)


def _clear(name, tint, rough=0.06):
    if name in P._mats:
        return P._mats[name]
    m = P._mat(name, tint, rough)
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["IOR"].default_value = 1.4
    if hasattr(m, "surface_render_method"):
        m.surface_render_method = "DITHERED"
    if hasattr(m, "use_raytrace_refraction"):
        m.use_raytrace_refraction = True
    return m


CM = Matrix.Diagonal((0.01, 0.01, 0.01, 1.0))


def _place(coll, name, mesh, xy, z, heading_deg, mats=None):
    ob = bpy.data.objects.new(name, mesh)
    coll.objects.link(ob)
    ob.matrix_world = Matrix.Translation((xy[0], xy[1], z)) @ Matrix.Rotation(math.radians(heading_deg - 90), 4, "Z") @ CM
    return ob


def _hand_box(scene, rig, coll, name):
    """Carton held between the palms: as wide as the gap between the hands, in front of the chest (never through it),
    bound to the right hand so it travels with the carry."""
    bpy.context.view_layer.update()
    mw = rig.matrix_world
    lh = mw @ rig.pose.bones["mixamorig:LeftHand"].head
    rh = mw @ rig.pose.bones["mixamorig:RightHand"].head
    chest = mw @ rig.pose.bones["mixamorig:Spine2"].head
    mid = (lh + rh) / 2
    across = rh - lh
    width = max(0.18, across.length - 0.05)  # palms on the sides, ~2.5 cm of hand each side
    fwd = mid - chest
    fwd.z = 0
    reach = fwd.length
    fwd = fwd.normalized() if reach > 1e-4 else Vector((math.cos(0), math.sin(0), 0))
    depth = max(0.14, min(0.32, 2 * (reach - 0.12)))  # back face >= 12 cm in front of the chest
    centre = chest + fwd * (reach - depth / 2 + depth / 2) + Vector((0, 0, mid.z - chest.z + 0.03))
    centre = Vector((mid.x, mid.y, mid.z + 0.03)) + fwd * 0.02
    x = across.normalized()
    y = fwd - x * fwd.dot(x)
    y = y.normalized()
    z = x.cross(y)
    rot = Matrix((x, y, z)).transposed().to_4x4()
    mesh = P._prop_mesh("carried_carton", _box_mesh, [P._mat("carton_brown", (0.36, 0.23, 0.12), 0.8),
                                                      P._mat("tape_clear", (0.42, 0.33, 0.2), 0.3)])
    ob = bpy.data.objects.new(f"{name}_carton", mesh)
    coll.objects.link(ob)
    P._bind_world(ob, rig, "mixamorig:RightHand", Matrix.Translation(centre) @ rot
                  @ Matrix.Diagonal((width / 40.0, depth / 30.0, 0.22 / 25.0, 1.0)))
    ob["fit"] = f"width {width * 100:.0f} cm, depth {depth * 100:.0f} cm"
    return ob


def _cage(scene, rig, coll, name, cage_mesh, heading, depth=0.8, frames=range(1, 61, 2)):
    """A roll cage pushed by this worker: its back face just beyond the furthest any body part reaches over the push
    cycle (the torso never enters it), parented to the worker's object; then both hands are IK'd to the two back
    posts (Blender IK, chain 2, pole behind-outside the elbow) so they stay on the cage while it moves."""
    fwd = Vector((math.cos(heading), math.sin(heading), 0))
    left = Vector((-fwd.y, fwd.x, 0))
    keys = ["LeftHand", "RightHand", "Head", "Spine2", "Spine", "LeftForeArm", "RightForeArm"]
    reach, hand_z, reaches = 0.0, [], []
    for f in frames:
        scene.frame_set(f)
        bpy.context.view_layer.update()
        root = rig.matrix_world.translation.copy()
        for k in keys:
            pt = rig.matrix_world @ rig.pose.bones[f"mixamorig:{k}"].head
            if k.endswith("Hand") or k.endswith("ForeArm"):
                reaches.append((pt - root).dot(fwd))  # arms are IK'd to the cage: only their typical reach counts
            else:
                reach = max(reach, (pt - root).dot(fwd))  # torso / head: never inside the cage
            if k.endswith("Hand"):
                hand_z.append(pt.z)
    scene.frame_set(1)
    bpy.context.view_layer.update()
    root = rig.matrix_world.translation
    reaches.sort()
    arm = reaches[int(len(reaches) * 0.8)] if reaches else 0.5
    back = max(reach + 0.12, min(arm, 0.55))  # hands reach the posts with a slight bend; torso >= 12 cm clear
    c = root + fwd * (back + depth / 2)
    ob = bpy.data.objects.new(f"{name}_cage", cage_mesh)
    coll.objects.link(ob)
    ob.matrix_world = Matrix.Translation((c.x, c.y, 0.0)) @ Matrix.Rotation(heading + math.pi / 2, 4, "Z")
    w = ob.matrix_world.copy()
    ob.parent = rig
    ob.matrix_parent_inverse = rig.matrix_world.inverted()
    ob.matrix_world = w
    hz = sorted(hand_z)[len(hand_z) // 2] if hand_z else 1.05
    hz = min(1.2, max(0.9, hz))
    for side, sgn in (("Left", 1), ("Right", -1)):
        post = c - fwd * (depth / 2 - 0.02) + left * sgn * 0.33 + Vector((0, 0, hz - c.z))
        tgt = bpy.data.objects.new(f"{name}_ik_{side}", None)
        coll.objects.link(tgt)
        tgt.matrix_world = Matrix.Translation(post)
        tm = tgt.matrix_world.copy()
        tgt.parent = ob
        tgt.matrix_parent_inverse = ob.matrix_world.inverted()
        tgt.matrix_world = tm
        tgt.hide_render = True
        pole = bpy.data.objects.new(f"{name}_pole_{side}", None)
        coll.objects.link(pole)
        pole.matrix_world = Matrix.Translation(root + left * sgn * 0.55 - fwd * 0.35 + Vector((0, 0, 0.9)))
        pm = pole.matrix_world.copy()
        pole.parent = rig
        pole.matrix_parent_inverse = rig.matrix_world.inverted()
        pole.matrix_world = pm
        pole.hide_render = True
        pb = rig.pose.bones[f"mixamorig:{side}ForeArm"]
        con = pb.constraints.new("IK")
        con.target, con.chain_count, con.use_tail = tgt, 2, True
        con.pole_target = pole
        best = None
        for ang in (-90, 0, 90, 180):  # the pole angle that puts the elbow nearest the pole (natural bend)
            con.pole_angle = math.radians(ang)
            bpy.context.view_layer.update()
            el = rig.matrix_world @ rig.pose.bones[f"mixamorig:{side}ForeArm"].head
            d = (el - pole.matrix_world.translation).length
            if best is None or d < best[0]:
                best = (d, ang)
        con.pole_angle = math.radians(best[1])
    bpy.context.view_layer.update()
    return ob


def _hat(scene, rig, body, coll, name, kind, colour, heading):
    mesh = P._prop_mesh("hard_hat", P._hard_hat, [P._mat("hat_shell", (0.8, 0.8, 0.8), 0.35)]) if kind == "hard"         else P._prop_mesh("work_cap", P._cap, [P._mat("cap_teal", (0.02, 0.18, 0.17), 0.8)])
    ob = bpy.data.objects.new(f"{name}_{kind}", mesh)
    coll.objects.link(ob)
    if kind == "hard":
        ob.material_slots[0].link = "OBJECT"
        ob.material_slots[0].material = P._mat(f"hat_{colour}", P.HAT_COLOURS[colour], 0.35)
    P.fit_hat(ob, rig, body, _lib["head_verts"], "mixamorig:Head", kind, heading)
    return ob


def _pickup(scene, rig, coll, name, kind, frames=range(1, 301)):
    """A real object for a pick-up / lift clip: placed on the floor under the hands' lowest point; each time the
    hands bottom out next to it, it attaches to the right hand (keeping its offset), follows while lifted and is set
    down where the hands next bottom out (snapped flat to the floor). Baked to keys on every frame."""
    if kind == "sack" and bpy.data.meshes.get("sack_tied"):
        mesh, sz = bpy.data.meshes["sack_tied"], 1.0
    else:
        mesh = P._prop_mesh("carried_carton", _box_mesh, [P._mat("carton_brown", (0.36, 0.23, 0.12), 0.8),
                                                          P._mat("tape_clear", (0.42, 0.33, 0.2), 0.3)])
        sz = {"box_big": 0.012, "parcel": 0.0065}.get(kind, 0.008)
    hz, mids, rhm = [], [], []
    for f in frames:
        scene.frame_set(f)
        mw = rig.matrix_world
        lh = mw @ rig.pose.bones["mixamorig:LeftHand"].head
        rh = mw @ rig.pose.bones["mixamorig:RightHand"].head
        mids.append((lh + rh) / 2)
        hz.append(min(lh.z, rh.z))
        rhm.append(mw @ rig.pose.bones["mixamorig:RightHand"].matrix)
    n = len(hz)
    low = min(hz)
    mins = [i for i in range(1, n - 1) if hz[i] <= hz[i - 1] and hz[i] < hz[i + 1] and hz[i] < low + 0.12]
    ob = bpy.data.objects.new(f"{name}_{kind}", mesh)
    coll.objects.link(ob)
    if not mins:
        ob.location = (mids[0].x, mids[0].y, 0.0)
        return "no pick-up low point found"
    i0 = mins[0]
    base = Matrix.Translation((mids[i0].x, mids[i0].y, 0.0)) @ Matrix.Rotation(rig.matrix_world.to_euler()[2], 4, "Z")
    if sz != 1.0:
        base = base @ Matrix.Diagonal((sz, sz, sz, 1.0))
    world = base.copy()
    held, rel, last_grab, events = False, None, -99, 0
    for i in range(n):
        if i in mins and i - last_grab >= 8:
            if not held:
                rel = rhm[i].inverted() @ world
                held, last_grab = True, i
                events += 1
            else:  # set down: flat on the floor where it is
                loc = world.to_translation()
                sca = world.to_scale()
                world = Matrix.Translation((loc.x, loc.y, 0.0)) @ Matrix.Rotation(world.to_euler()[2], 4, "Z") \
                    @ Matrix.Diagonal((sca.x, sca.y, sca.z, 1.0))
                held, last_grab = False, i
        if held:
            world = rhm[i] @ rel
        ob.matrix_world = world
        ob.keyframe_insert("location", frame=frames[i])
        ob.keyframe_insert("rotation_euler", frame=frames[i])
        ob.keyframe_insert("scale", frame=frames[i])
    scene.frame_set(1)
    return f"{events} lifts"


# ------------------------------------------------------------------------------------------------ main
def add(scene, spec, lib_path, coll, rnd, prop=None, fps=10):
    """Place the Mixamo workers; returns (placed records, clips used)."""
    if not Path(lib_path).exists():
        return [], {"error": f"{lib_path} missing: run prep_mixamo.py"}
    _load(lib_path, scene)
    A = _lib["actions"]  # fps comes from the caller: FBX imports reset scene.render.fps to the file's 30
    cage_mesh = next((o.data for o in scene.objects if o.type == "MESH" and o.data.name.startswith("roll_cage")), None)
    grey = P._mat("steel_grey", (0.32, 0.33, 0.34), 0.45, metal=0.8)
    dark = P._mat("hmi_case", (0.06, 0.065, 0.07), 0.5)
    screen = P._mat("hmi_screen", (0.08, 0.22, 0.42), 0.2, emit=2.2)
    placed, used = [], set()
    # break table + bottles + a chair for the seated worker
    tx, ty = BREAK_TABLE
    _place(coll, "break_table", P._prop_mesh("break_table", _table_mesh, [P._mat("table_top", (0.55, 0.53, 0.5), 0.6),
                                                                       grey]), (tx, ty), 0.0, 90)
    # what is really on a break table (the owner rule: clear PET counts as glass - it IS see-through)
    pet, water = _clear("pet_bottle", (0.92, 0.95, 0.96)), _clear("bottle_water", (0.85, 0.93, 0.97), 0.02)
    label = P._mat("bottle_label_band", (0.06, 0.32, 0.7), 0.35)
    cap = P._mat("bottle_cap_blue", (0.05, 0.22, 0.65), 0.4)
    white = P._mat("ceramic_white", (0.86, 0.86, 0.84), 0.2)
    coffee = P._mat("coffee", (0.09, 0.05, 0.03), 0.1)
    foam = P._mat("foam_white", (0.9, 0.9, 0.87), 0.85)
    black = P._mat("phone_black", (0.02, 0.02, 0.025), 0.3)
    items = [("bottle_1500", _bottle_1500, [pet, label, cap, water], (-0.42, 0.12), 0.0),
             ("bottle_500", _bottle_500, [pet, label, cap, water], (0.38, 0.2), 0.0),
             ("bottle_500_empty", _bottle_500_empty, [pet, label, cap], (-0.05, -0.2), 63.0),
             ("mug", _mug, [white, coffee], (0.52, -0.12), 140.0),
             ("food_box", _food_box, [foam], (-0.15, 0.16), 12.0),
             ("phone", _phone, [black], (0.2, -0.24), 77.0)]
    for key, build, mats, (dx, dy), rot in items:
        _place(coll, f"break_{key}", P._prop_mesh(f"break_{key}", build, mats), (tx + dx, ty + dy), 0.74, rot)
    if prop:
        prop("plastic_monobloc_chair_01", tx + 0.9, ty + 0.65, 160, radius=0.0)  # spare chair
    for i, st in enumerate(STATIONS):
        name = f"worker_mx_{i:02d}_{st['role']}"
        rig, body = _instance(coll, name, st)
        offset = rnd.randint(0, 90)
        hat_colour = (i + 1) % len(P.HAT_COLOURS)
        rec = {"name": name, "role": st["role"], "avatar": "vest_worker (Mixamo)", "status": "clip",
               "vest": f"{st['vest']} (shirt {st['shirt']})", "hat": st.get("hat"), "offset_frames": offset,
               "gloves": False, "scanner": False}
        if "path" in st:
            act = A[st["clip"]]
            used.add(st["clip"])
            speed = (float(act.get("speed", 0.0)) or 1.2) * st.get("rate", 1.0)
            if st.get("one_way"):  # exact root motion; pushers start mid-push (the clip opens standing still)
                start = 1 - (st.get("lead_frames", 0) if "loop_a" not in act else 0)
                arrival = _follow_root(rig, act, st["path"], start, fps, rate=st.get("rate", 1.0))
                arrival = arrival if arrival < 420 else None
                _strip(rig, act, start, fps, "walk", until=arrival or 420, extrap="HOLD", rate=st.get("rate", 1.0))
            else:
                arrival = _path_motion(rig, st["path"], speed, fps, offset)
            if arrival:
                idle = st.get("arrive", "breathing_idle")
                s2, _ = _strip(rig, A[idle], arrival, fps, "arrived", xfade=True)
                s2.blend_in = 3
                used.add(idle)
            elif not st.get("one_way"):
                _strip(rig, act, 1 - offset, fps, "walk")
            heading = math.atan2(st["path"][1][1] - st["path"][0][1], st["path"][1][0] - st["path"][0][0])
            rec.update(path=st["path"], speed_mps=round(speed, 2), clip=st["clip"],
                       off_walkway=P._on_walkways(st["path"], spec) if st["role"] == "walk" else [],
                       arrives_frame=round(arrival) if arrival else None)
        else:
            heading = math.radians(st["face"])
            seq = st.get("seq") or [(st["clip"], None)]
            z = 0.16 if st.get("seat") and st["role"] == "exception" else 0.0
            if len(seq) == 1:
                _strip(rig, A[seq[0][0]], 1 - offset, fps, "loop", clip_from=seq[0][2] if len(seq[0]) > 2 else 0,
                       xfade=True)
                used.add(seq[0][0])
                _set_pose(rig, st["at"], heading, z)
            else:
                loop = bool(st.get("loop"))
                f = 1 - (offset if loop else 0)
                h, k, keys, prev_yaw = heading, 0, [(f, heading)], 0
                drift_from = None
                while f < 420:
                    for j, item in enumerate(seq):
                        clip, secs = item[0], item[1]
                        clip_from = item[2] if len(item) > 2 else 0
                        act = A[clip]
                        used.add(clip)
                        once = secs == "once"
                        last = not loop and j == len(seq) - 1
                        strip, length = _strip(rig, act, f, fps, f"seq_{k}", once=once, clip_from=clip_from, xfade=True,
                                               until=None if (last or once) else f + secs * fps,
                                               extrap="HOLD" if k == 0 else "HOLD_FORWARD")
                        if k and not prev_yaw:
                            strip.blend_in = min(3.0, length / 3)
                        if st.get("drift") and clip == "talking_phone_pacing":
                            drift_from, pace_from = f, clip_from
                        k += 1
                        if last:
                            f = 420
                            break
                        f += length if once else secs * fps
                        prev_yaw = act.get("yaw_deg", 0) if once else 0
                        if prev_yaw:
                            h += math.radians(prev_yaw)
                            keys.append((f, h))
                    if not loop:
                        break
                if len(keys) > 1:  # turning clips: the heading steps by the clip's own yaw as it ends
                    for fk, hk in keys:
                        _key_pose(rig, fk, st["at"], hk, z)
                    _interp(rig, rot_constant=True)
                elif drift_from is not None:  # pacing: put back the clip's own steps, frame by frame
                    pace = A["talking_phone_pacing"]
                    _key_pose(rig, 1, st["at"], heading, z)
                    for fk in range(int(drift_from), 421):
                        dd = (_root_dist(pace, pace_from + (fk - drift_from) * CLIP_FPS / fps)
                              - _root_dist(pace, pace_from))
                        _key_pose(rig, fk, (st["at"][0] + math.cos(heading) * dd, st["at"][1] + math.sin(heading) * dd),
                                  heading, z)
                    _interp(rig)
                    rec["drift_m"] = round(dd, 2)
                else:
                    _set_pose(rig, st["at"], heading, z)
            rec.update(at=st["at"], face=st["face"], clip=" -> ".join(dict.fromkeys(it[0] for it in seq)))
        if st.get("seat"):  # raised steel stool at the bench (top 0.9 m); monobloc chair at the break table
            fwd = Vector((math.cos(heading), math.sin(heading), 0))
            sx, sy = st["at"][0] - fwd.x * 0.12, st["at"][1] - fwd.y * 0.12
            if st["role"] == "exception":
                _place(coll, f"{name}_stool", P._prop_mesh("tall_stool", _stool_mesh, [dark, grey]), (sx, sy), 0.63, 0)
            elif prop:
                prop("plastic_monobloc_chair_01", sx, sy, math.degrees(heading) + 90, radius=0.0)
        if st.get("hmi"):
            _place(coll, f"{name}_hmi", P._prop_mesh("hmi_stand", _hmi_mesh, [grey, dark, screen]), st["hmi"], 0.0,
                   math.degrees(heading) + 180)
        if st.get("dockbox"):
            _place(coll, f"{name}_dockbox", P._prop_mesh("dock_control_box", _dockbox_mesh,
                                                         [P._mat("box_grey", (0.55, 0.56, 0.55), 0.5),
                                                          P._mat("lamp_red_on", (0.9, 0.04, 0.02), 0.3, emit=3.0),
                                                          P._mat("lamp_green_on", (0.05, 0.8, 0.1), 0.3, emit=1.0),
                                                          P._mat("button_yellow", (0.85, 0.65, 0.04), 0.4)]),
                   st["dockbox"], 0.0, math.degrees(heading) + 180)
        scene.frame_set(1)
        if st.get("carry"):
            _hand_box(scene, rig, coll, name)
        if st.get("cage") and cage_mesh is not None:
            _cage(scene, rig, coll, name, cage_mesh, heading)
        if st.get("hat"):
            _hat(scene, rig, body, coll, name, st["hat"], hat_colour, heading)
        if st.get("pickup"):
            rec["pickup"] = _pickup(scene, rig, coll, name, st["pickup"])
        if st.get("device"):  # the phone the texting / calling clips hold: a locked one-hand grip (people.grip_device)
            dv = bpy.data.objects.new(f"{name}_{st['device']}", P.device_mesh(st["device"]))
            coll.objects.link(dv)
            scene.frame_set(1)
            P.grip_device(dv, rig, "mixamo", "mixamorig:Head", 0.004, (0.036, 0.075), side=st.get("hand", "R"))
            scene.frame_set(1)
        lift = 0.0 if st.get("seat") else SOLE_LIFT
        if lift:
            fcs = [fc for bag, f_ in P._channelbag_fcurves(rig.animation_data.action) for fc in f_] \
                if rig.animation_data and rig.animation_data.action else []
            zc = [fc for fc in fcs if fc.data_path == "location" and fc.array_index == 2]
            if zc:
                for kp in zc[0].keyframe_points:
                    kp.co.y += lift
                    kp.handle_left.y += lift
                    kp.handle_right.y += lift
            else:
                rig.location.z += lift
        placed.append(rec)
    return placed, {"mixamo_clips_used": sorted(used), "mixamo_clips_unused": sorted(set(A) - used)}
