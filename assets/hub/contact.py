"""Procedural contact layer for Rocketbox (Bip01) workers: real hand-object contact instead of library mimes.

The object drives the hands, never the reverse:
  * the parcel / handle / bag follows an authored path (keyed every frame by the caller);
  * each hand's wrist is solved (analytic two-bone IK, elbow toward a pole behind-outside it) to the point that
    puts its palm on a socket of that object, and the hand gets the absolute rotation that lays the palm on the
    face with the fingers along it;
  * the ankles are solved the same way to pinned floor poses (feet flat, never sliding), so the trunk can bend,
    drop and twist above planted feet;
  * trunk motion (hip hinge, pelvis drop, spine twist / flex) is an additive NLA layer (COMBINE) over a quiet
    standing idle, so the breathing / weight shift of the real clip stays underneath;
  * the head turns toward the current target (75 %, capped at 70 deg).
Order (apply()): trunk layer -> visual bake of idle + trunk to plain keys -> per frame, read that base pose and
overwrite the arm / leg / head rotations with the solved ones. No constraints, no helper objects, no depsgraph
cycles: the result is plain keys.

Why analytic and not Blender IK constraints: the Rocketbox FBX bones' tails do not point at their children
(tail -> child head = bone length x 1.41, measured), so Blender's IK puts the wrong point on the target. Other
skeleton facts used: the thighs hang from 'Bip01 Spine'; there are no forearm twist bones (Forearm -> Hand).
"""
import math

import bpy
from bpy_extras import anim_utils
from mathutils import Matrix, Quaternion, Vector

import people as P

UP = Vector((0, 0, 1))
S = 0.01  # Rocketbox armature object scale (cm skeleton)
ARM_CHAIN = ("Clavicle", "UpperArm", "Forearm", "Hand")
LEG_CHAIN = ("Thigh", "Calf", "Foot")


def smooth(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def yaw_vec(yaw):
    return Vector((math.cos(yaw), math.sin(yaw), 0.0))


def frame_from(along, normal):
    """Orthonormal 3x3 with columns (along, normal, along x normal)."""
    a = along.normalized()
    n = (normal - a * normal.dot(a)).normalized()
    return Matrix((a, n, a.cross(n))).transposed()


def two_bone(S_, a, b, T, pole):
    """Elbow / knee position for a chain of lengths a, b from S_ reaching T, bending toward pole.
    Returns (elbow, reached_target, clamped)."""
    d_vec = T - S_
    d = d_vec.length
    lo, hi = abs(a - b) + 1e-4, a + b - 1e-4
    clamped = not (lo <= d <= hi)
    d = min(max(d, lo), hi)
    axis = d_vec.normalized()
    T2 = S_ + axis * d
    cos_a = (a * a + d * d - b * b) / (2 * a * d)
    cos_a = min(max(cos_a, -1.0), 1.0)
    n = (pole - S_)
    n = n - axis * n.dot(axis)
    if n.length < 1e-6:
        n = axis.orthogonal()
    n.normalize()
    E = S_ + axis * (a * cos_a) + n * (a * math.sqrt(max(0.0, 1 - cos_a * cos_a)))
    return E, T2, clamped


class Worker:
    """One Rocketbox worker with contact rigging. heading = direction the FEET face (radians, world)."""

    def __init__(self, scene, coll, st, name, at, heading, floor_z=0.0, hat_colour=0, base_clip="idle_neutral_01",
                 clip_offset=0, fps=10):
        self.sc, self.coll, self.name = scene, coll, name
        self.heading, self.floor_z = heading, floor_z
        self.st = st
        self.arm = P._instance(scene, coll, st, name, hat_colour)
        scene.render.fps = fps  # FBX imports (avatar templates) reset the scene to 30 fps
        arm = self.arm
        arm.location = (at[0], at[1], floor_z)
        P._turn(arm, heading + P.FACING_OFFSET)
        gender = "f" if st["avatar"].startswith("Female") else "m"
        act = P._clip(scene, gender, base_clip)
        act = P._retarget(f"{gender}_{base_clip}", act, st["avatar"])
        P._play(arm, act, clip_offset, scene.render.fps)
        self.body = next(o for o in arm.children if o.name.endswith("_body"))
        # Rocketbox clips carry their own pelvis height: lift the rig so the pelvis sits where the clip had it,
        # then put the lowest vertex on the floor (same as people.add_workers)
        scene.frame_set(1)
        bpy.context.view_layer.update()
        if act.get("hip_z", -1.0) > 0:
            arm.location.z += act["hip_z"] - (arm.matrix_world @ arm.pose.bones["Bip01 Pelvis"].head).z
            bpy.context.view_layer.update()
        arm.location.z += floor_z - self._lowest()
        bpy.context.view_layer.update()
        # true facing from the hips (left thigh - right thigh = the body's left; measured: the retargeted clips'
        # pelvis yaw makes people.FACING_OFFSET wrong by ~90 deg), then turn the rig onto the wanted heading
        for _ in range(2):
            mw = arm.matrix_world
            lft = (mw @ arm.pose.bones["Bip01 L Thigh"].head) - (mw @ arm.pose.bones["Bip01 R Thigh"].head)
            actual = math.atan2(lft.y, lft.x) - math.pi / 2
            arm.rotation_euler.z += (heading - actual + math.pi) % (2 * math.pi) - math.pi
            bpy.context.view_layer.update()
        self.trunk, self.hands, self.feet, self.look = {}, {}, {}, {}
        self.loc0, self.rot0, self.heading0 = arm.location.copy(), arm.rotation_euler.z, heading
        self.gender = gender
        self.obj = {}  # frame -> (location, heading) when the rig walks (walk())
        self.walking = set()
        self.pyaw = {}  # frame -> extra pelvis yaw (the walk clip's own facing offset, corrected)
        self.motion_act = None
        self.flat = {}  # frame -> 1 when the fingers lie flat on a face
        self.hand_w = {}  # frame -> 0..1: blend from the clip's own arms (0) to the solved contact (1)
        self.last_n = {}
        self.extra_flex = {}
        self.extra_yaw = {}
        self.clamped = 0
        self.deficits = []  # (frame, end bone, cm beyond reach)
        self._f = None
        self._measure()

    def _lowest(self):
        ev = self.body.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = ev.to_mesh()
        low = min((ev.matrix_world @ v.co).z for v in me.vertices)
        ev.to_mesh_clear()
        return low

    # ------------------------------------------------------------------------------------------------ rest facts
    def _measure(self):
        arm = self.arm
        bones = arm.data.bones
        self.palm = {}
        for sd in ("L", "R"):  # palm contact point / normal / along-hand axis in the HAND bone's rest frame
            names = P.HAND_BONES["rocketbox"](sd)
            b = [bones[n] for n in names]
            h, i1, m1, p1 = (x.head_local for x in b[:4])
            tip, thumb = b[4].tail_local, b[5].tail_local
            along = (m1 - h).normalized()
            across = p1 - i1
            across = (across - along * across.dot(along)).normalized()
            n = across.cross(along).normalized()
            if n.dot(tip - m1) + n.dot(thumb - h) < 0:
                n = -n
            contact = h + (m1 - h) * 0.6 + n * 1.8  # cm (armature units): skin of the palm
            Mh = b[0].matrix_local
            R = Mh.to_3x3().inverted()
            self.palm[sd] = dict(offset=Mh.inverted() @ contact, along=(R @ along).normalized(),
                                 normal=(R @ n).normalized())
        hm = bones["Bip01 Head"].matrix_local.to_3x3()  # head forward axis (avatar faces -Y in armature space)
        cands = [(ax, sg) for ax in range(3) for sg in (1, -1)]
        self.head_fwd = max(cands, key=lambda c: c[1] * Vector(hm.col[c[0]]).normalized().dot(Vector((0, -1, 0))))
        self.sc.frame_set(1)
        bpy.context.view_layer.update()
        mw = arm.matrix_world
        self.foot0 = {sd: (mw @ arm.pose.bones[f"Bip01 {sd} Foot"].matrix) for sd in ("L", "R")}
        self.pelvis0 = (mw @ arm.pose.bones["Bip01 Pelvis"].head).copy()
        Ai = mw.inverted()
        self.foot_local = {sd: Ai @ M for sd, M in self.foot0.items()}
        self.pelvis_local = Ai @ self.pelvis0

    # ------------------------------------------------------------------------------------------------ rig motion
    def A(self, f):
        """The armature object's world matrix at frame f (static unless walk() moved it)."""
        loc, hd = self.obj.get(f, (self.loc0, self.heading0))
        return (Matrix.Translation(loc) @ Matrix.Rotation(self.rot0 + hd - self.heading0, 4, "Z")
                @ Matrix.Diagonal((S, S, S, 1.0)))

    def heading_at(self, f):
        return self.obj.get(f, (None, self.heading0))[1]

    def walk(self, legs, frames, turn_s=0.35, fps=10):
        """legs: [(f_start, [p0, p1, ...]), ...] in time order (world xy points). Each leg walks the polyline at
        the walk clip's own stride speed (no foot sliding) from f_start; between legs the rig stands where it
        stopped, facing its last walking direction (the work heading is reached with trunk twist / pivot steps).
        Returns [(f_start, f_end)] per leg."""
        frames = list(frames)
        arm = self.arm
        act = P._clip(self.sc, self.gender, "walk_neutral_01")
        act = P._retarget(f"{self.gender}_walk_neutral_01", act, self.st["avatar"])
        v = float(act.get("speed", -1.0))
        v = v if v > 0.5 else 1.25
        self.walk_speed = v
        loc, hd = self.loc0.copy(), self.heading0
        out = []
        timeline = {}
        rates = []
        for leg in legs:
            f_start, pts = leg[0], leg[1]
            rate = leg[2] if len(leg) > 2 else 1.0  # < 1: slower steps AND slower travel (pushing a cage)
            ts = leg[3] if len(leg) > 3 else turn_s  # longer: a turning step instead of a spin on the spot
            rates.append(rate)
            pts = [Vector((x, y, self.loc0.z)) for x, y in pts]
            segs = [(a, b, (b - a).length) for a, b in zip(pts, pts[1:]) if (b - a).length > 1e-3]
            total = sum(d for *_, d in segs)
            n = max(2, int(round(total / (v * rate) * fps)))
            for g in range(f_start, f_start + n + 1):
                dist = total * (g - f_start) / n
                for a, b, d in segs:
                    if dist <= d + 1e-9:
                        loc = a.lerp(b, dist / d)
                        want = math.atan2(b.y - a.y, b.x - a.x)
                        break
                    dist -= d
                hd = hd + ((want - hd + math.pi) % (2 * math.pi) - math.pi) * min(1.0, 1.0 / (ts * fps))
                timeline[g] = (loc.copy(), hd)
                if f_start < g < f_start + n:
                    self.walking.add(g)
            out.append((f_start, f_start + n))
        cur = (self.loc0.copy(), self.heading0)
        for f in frames:
            cur = timeline.get(f, cur)
            self.obj[f] = cur
        # key the object (its own action, kept through the bakes) and lay walk strips over the idle
        ad = arm.animation_data
        keep = ad.action
        for f in frames:
            l, h = self.obj[f]
            arm.location = l
            arm.rotation_euler.z = self.rot0 + h - self.heading0
            arm.keyframe_insert("location", frame=f)
            arm.keyframe_insert("rotation_euler", index=2, frame=f)
        self.motion_act = ad.action
        _linear_action(self.motion_act)
        a0, a1 = act.frame_range
        for i, (f0, f1) in enumerate(out):
            tr = ad.nla_tracks.new()
            tr.name = f"walk_{i}"
            st = tr.strips.new(f"walk_{i}", int(f0) - 2, act)
            if hasattr(st, "action_slot") and getattr(act, "slots", None):
                st.action_slot = act.slots[0]
            st.scale = fps / P.CLIP_FPS / rates[i]
            st.repeat = max(1.0, (f1 - f0 + 4) / ((a1 - a0) * st.scale))
            st.blend_in = st.blend_out = 3
            st.extrapolation = "NOTHING"
        ad.action = self.motion_act if keep is None else keep
        # the walk clip's own facing offset vs this rig (retargeted Rocketbox clips differ): measure, correct
        if out:
            offs = []
            inwin = [f for (f0, f1) in out for f in range(f0 + 3, f1 - 2) if f in self.obj]
            for f in inwin[:40]:
                self.sc.frame_set(f)
                mw = arm.matrix_world
                lft = (mw @ arm.pose.bones["Bip01 L Thigh"].head) - (mw @ arm.pose.bones["Bip01 R Thigh"].head)
                actual = math.atan2(lft.y, lft.x) - math.pi / 2
                offs.append((self.obj[f][1] - actual + math.pi) % (2 * math.pi) - math.pi)
            if offs:
                offs.sort()
                d = offs[len(offs) // 2]
                for (f0, f1) in out:
                    for g in range(f0 - 3, f1 + 4):
                        u = min(1.0, (g - (f0 - 3)) / 3, ((f1 + 3) - g) / 3)
                        self.pyaw[g] = d * max(0.0, u)
                self.walk_yaw_fix = d
        return out

    def rig(self):
        """(kept for the call order; the solver needs no helper objects)"""
        self.add_act = bpy.data.actions.new(f"{self.name}_trunk")

    # ------------------------------------------------------------------------------------------------ body model
    def torso_frame(self, f):
        """World frame of the chest from the authored trunk values (for neutral hands, elbow poles, look)."""
        yaw, flex, drop = self.trunk.get(f, (0.0, 0.0, 0.0))
        h = self.heading_at(f) + yaw
        fwd, left = yaw_vec(h), yaw_vec(h + math.pi / 2)
        pel = self.A(f) @ self.pelvis_local
        base = Vector((pel.x, pel.y, pel.z - drop))
        chest = base + (UP * math.cos(flex) + fwd * math.sin(flex)) * 0.42 - fwd * 0.1 * math.sin(flex)
        return chest, fwd, left, h

    def neutral_hands(self, f, kind="ready"):
        """Palm contact points + palm frames for empty hands. ready = in front of the belly, palms in;
        rest = hanging at the sides."""
        chest, fwd, left, h = self.torso_frame(f)
        out = {}
        for sd, sg in (("L", 1), ("R", -1)):
            if kind == "ready":
                p = chest + fwd * 0.28 + left * sg * 0.16 - UP * 0.36
                along, normal = (fwd * 0.9 - UP * 0.4), -left * sg
            else:
                p = chest + fwd * 0.03 + left * sg * 0.22 - UP * 0.64
                along, normal = (-UP + fwd * 0.12), -left * sg
            out[sd] = (p, frame_from(along, normal))
        return out

    def hand_target(self, sd, palm_point, R_contact):
        """World wrist matrix that puts this hand's palm contact point at palm_point, with the palm frame
        (along, normal, along x normal) = R_contact columns."""
        pm = self.palm[sd]
        Rl = frame_from(pm["along"], pm["normal"])
        Rw = R_contact @ Rl.inverted()
        wrist = palm_point - Rw @ (pm["offset"] * S)
        return Matrix.Translation(wrist) @ Rw.to_4x4()

    def set_hands(self, f, targets, fingers=None, weight=1.0):
        """targets: {sd: (palm_point, R_contact)} in world. fingers: None (the clip's) | 'flat' (laid straight
        along a carton face: no finger through the carton) | 'wrap' (the clip's curl, round a post)."""
        chest, fwd, left, h = self.torso_frame(f)
        if fingers == "flat":
            self.flat[f] = 1.0
        out = {}
        for sd, sg in (("L", 1), ("R", -1)):
            p, R = targets[sd]
            pole = (-UP * 0.9 + left * sg * 0.55 - fwd * 0.15).normalized()  # a DIRECTION: elbows down and out
            out[sd] = (self.hand_target(sd, p, R), pole, (p, R))
        self.hands[f] = out
        self.hand_w[f] = max(0.0, min(1.0, weight))

    def set_feet(self, f, feet=None, fy=0.0):
        """feet: explicit world foot matrices (else the pinned frame-1 pose); fy: their yaw (rel. to heading)."""
        fwd = yaw_vec(self.heading_at(f) + fy)
        out = {}
        for sd in ("L", "R"):
            M = feet[sd] if feet else self.A(f) @ self.foot_local[sd]
            out[sd] = (M, M.translation + fwd * 0.8 + UP * 0.45)
        self.feet[f] = out

    def auto_steps(self, frames, max_twist=0.95, rest_twist=0.45, step_s=0.55, fps=10):
        """Pivot steps: when the trunk would twist more than max_twist from the feet, the feet step round (the foot
        on the turning side first, a 5 cm lift each, ~0.55 s for both) to leave rest_twist; the pelvis follows the
        feet. Fills self.fy and the feet keys for every frame."""
        frames = list(frames)
        n = max(2, int(round(step_s * fps)))
        yaw = {f: (0.0 if f in self.walking else self.trunk.get(f, (0.0, 0.0, 0.0))[0]) for f in frames}
        fy = {}
        cur = 0.0
        steps = []  # (f0, f1, from, to)
        f = frames[0]
        while f <= frames[-1]:
            d = yaw[f] - cur
            if abs(d) > max_twist:
                ahead = yaw.get(min(f + n, frames[-1]), yaw[f])
                to = ahead - math.copysign(rest_twist, ahead - cur)
                steps.append((f, f + n, cur, to))
                for g in range(f, f + n + 1):
                    fy[g] = cur + (to - cur) * smooth((g - f) / n)
                cur = to
                f += n + 1
                continue
            fy[f] = cur
            f += 1
        self.fy = fy
        self.steps = steps
        def placed(sd, a, f):
            Fl, Fr = (self.A(f) @ self.foot_local[k] for k in ("L", "R"))
            c = (Fl.translation + Fr.translation) / 2
            c.z = 0.0
            return Matrix.Translation(c) @ Matrix.Rotation(a, 4, "Z") @ Matrix.Translation(-c) @ \
                (self.A(f) @ self.foot_local[sd])

        # where the stride leaves each foot at the end of every walk (evaluated from the walk clip, rig-relative)
        settle = {}
        for f in frames:
            if f in self.walking and (f + 1) not in self.walking and (f + 1) in fy:
                self.sc.frame_set(f)
                mw = self.arm.matrix_world
                ends = {sd: (mw @ self.arm.pose.bones[f"Bip01 {sd} Foot"].matrix).normalized() for sd in ("L", "R")}
                for g in range(f + 1, f + 9):
                    settle[g] = (f + 1, ends)
        for f in frames:
            if f in self.walking:
                self.feet.pop(f, None)
                continue
            a = fy.get(f, cur)
            feet = {sd: placed(sd, a, f) for sd in ("L", "R")}
            if f in settle:  # first 0.8 s after a walk: each foot steps from where the stride left it to stance
                f0, ends = settle[f]
                for i, sd in enumerate(("L", "R")):
                    u = min(max((f - f0 - i * 3) / 4.0, 0.0), 1.0)
                    lift = UP * 0.04 * math.sin(math.pi * u)
                    Me, Ms = ends[sd], feet[sd]
                    loc = Me.translation.lerp(Ms.translation, smooth(u))
                    loc.z = Ms.translation.z
                    rot = Me.to_quaternion().slerp(Ms.to_quaternion(), smooth(u)).to_matrix().to_4x4()
                    feet[sd] = Matrix.Translation(loc + lift) @ rot
            for (f0, f1, a0, a1) in steps:
                if f0 <= f <= f1:
                    first = "L" if a1 > a0 else "R"  # turning left: left foot leads
                    for sd in ("L", "R"):
                        u0, u1 = (0.0, 0.55) if sd == first else (0.45, 1.0)
                        u = min(max(((f - f0) / (f1 - f0) - u0) / (u1 - u0), 0.0), 1.0)
                        M = placed(sd, a0 + (a1 - a0) * smooth(u), f)
                        feet[sd] = Matrix.Translation(UP * 0.05 * math.sin(math.pi * u)) @ M
            self.set_feet(f, feet, fy=a)
        # hand the legs over to the walk clip gradually: pinned -> free across the walk strip's blend-in
        self.feet_w = {}
        for f in frames:
            if f in self.walking and (f - 1) not in self.walking:
                for i, g in enumerate((f - 3, f - 2, f - 1)):
                    if g in self.feet:
                        self.feet_w[g] = 0.75 - 0.25 * i

    def set_trunk(self, f, yaw, flex, drop):
        self.trunk[f] = (yaw, flex, drop)

    def set_look(self, f, point):
        self.look[f] = point.copy()

    # ------------------------------------------------------------------------------------------------ solve + keys
    @staticmethod
    def _gauss(vals, frames, sigma):
        """Gaussian-smooth a {frame: tuple|float} curve over the given frames (missing frames are skipped)."""
        if sigma <= 0:
            return vals
        r = int(3 * sigma)
        out = {}
        for f in frames:
            if f not in vals:
                continue
            acc, ws = None, 0.0
            for g in range(f - r, f + r + 1):
                if g in vals:
                    w = math.exp(-0.5 * ((g - f) / sigma) ** 2)
                    v = vals[g]
                    acc = (tuple(x * w for x in v) if acc is None else tuple(a_ + x * w for a_, x in zip(acc, v))) \
                        if isinstance(v, tuple) else ((v * w) if acc is None else acc + v * w)
                    ws += w
            out[f] = tuple(x / ws for x in acc) if isinstance(acc, tuple) else acc / ws
        return out

    def _smooth_inputs(self, frames):
        """No body part may jump: trunk curves low-passed; the gaze turns at most 12 deg per frame and eases."""
        sm_y = self._gauss({f: (v[0],) for f, v in self.trunk.items()}, frames, 1.2)  # twist: follows quickly
        sm_fd = self._gauss({f: (v[1], v[2]) for f, v in self.trunk.items()}, frames, 2.0)  # lean / drop: softer
        self.trunk = {f: (sm_y[f][0], *sm_fd[f]) for f in self.trunk}
        prev = None
        for f in frames:
            if f not in self.look:
                continue
            chest = self.torso_frame(f)[0] + UP * 0.25
            d = self.look[f] - chest
            dist = max(d.length, 0.5)
            d.normalize()
            if prev is not None:
                q = prev.rotation_difference(d)
                ang = q.angle
                lim = min(ang * 0.45, math.radians(12))  # eased, rate-limited
                d = (Quaternion(q.axis, lim) @ prev) if ang > 1e-6 else prev
            prev = d.copy()
            self.look[f] = chest + d * dist
        for f in frames:  # empty hands: low-pass too (gripping hands follow their object exactly)
            pass

    def apply(self, frames):
        frames = list(frames)
        arm = self.arm
        ad = arm.animation_data
        self.shift = {}
        self._smooth_inputs(frames)
        tr = ad.nla_tracks.new()
        tr.name = "trunk_add"
        self._key_trunk(frames)
        st = tr.strips.new("trunk", int(frames[0]), self.add_act)
        if hasattr(st, "action_slot") and getattr(self.add_act, "slots", None):
            st.action_slot = self.add_act.slots[0]
        st.blend_type = "COMBINE"
        st.extrapolation = "HOLD"
        # reach adaptation (3 passes): measure how far the wrists' targets are beyond reach, then LEAN toward the
        # work (extra hip hinge), drop for low work, and only then shift the hips a little (never while walking:
        # the walk clip's feet are not pinned and would slide). Curves are dilated and smoothed: no steps.
        self.adapt = []
        for it in range(3):
            act = self._bake(frames)
            if it == 0 and self.walking:
                self._ground_walk(frames)
            need = self._reach_need(frames)
            ad.action = self.motion_act
            bpy.data.actions.remove(act)
            moved = 0
            lean, shift = {}, {}
            for f, c in need.items():
                yaw = self.trunk.get(f, (0.0, 0.0, 0.0))[0]
                fwd = yaw_vec(self.heading_at(f) + yaw)
                cf = max(0.0, c.dot(fwd))
                lean[f] = min(cf / 0.5, 0.7)  # shoulders move ~0.5 m x angle; up to 40 deg over a belt
                rest = c - fwd * min(cf, 0.5 * 0.7)
                walking = f in self.walking
                h = Vector((rest.x, rest.y, 0.0)) if not walking else Vector()
                if h.length > 0.12:
                    h *= 0.12 / h.length
                z = 0.0 if walking else min(0.0, max(rest.z, -0.3))
                shift[f] = (h.x, h.y, z)
                moved += int(c.length > 0.005)
            lean = self._gauss({f: max(lean.get(g, 0.0) for g in range(f - 3, f + 4)) for f in lean}, frames, 2.0)
            turn = self._gauss({f: max(-0.6, min(0.6, 0.8 * e)) for f, e in self._yaw_err.items()}, frames, 1.5)
            for f, dy in turn.items():  # short of reach sideways: turn the trunk further toward the work
                self.extra_yaw[f] = max(-1.2, min(1.2, self.extra_yaw.get(f, 0.0) + dy))
            shift = self._gauss(shift, frames, 2.0)
            for f in frames:
                if f in lean:
                    self.extra_flex[f] = self.extra_flex.get(f, 0.0) + lean[f]
                if f in shift:
                    old = self.shift.get(f, Vector())
                    hx, hy, hz = shift[f]
                    nv = old + Vector((hx, hy, hz))
                    hh = Vector((nv.x, nv.y, 0))
                    if hh.length > 0.12:
                        hh *= 0.12 / hh.length
                    self.shift[f] = Vector((hh.x, hh.y, max(nv.z, -0.3) if f not in self.walking else nv.z))
            self.adapt.append(moved)
            if not moved:
                break
            self._key_trunk(frames)
        act = self._bake(frames)
        for t_ in list(ad.nla_tracks):
            ad.nla_tracks.remove(t_)
        ad.action = act
        if hasattr(ad, "action_slot") and getattr(act, "slots", None):
            ad.action_slot = act.slots[0]
        bpy.data.actions.remove(self.add_act)
        self.act = act
        self._solve(frames)

    def _ground_walk(self, frames):
        """The walk clip's soles sit at their own height (not the idle's): measure the stride's lowest point per
        walk frame (toes / heels vs. the standing pose) and drop or raise the pelvis so a planted sole is on the
        floor. Stored in the pelvis shift (z) before the arms are solved, so hands stay on what they hold."""
        arm = self.arm
        pbs = arm.pose.bones
        self.sc.frame_set(frames[0])
        mw = arm.matrix_world
        low0 = self._lowest()
        toe0 = min((mw @ pbs[f"Bip01 {sd} Toe0"].head).z for sd in ("L", "R")) - low0
        heel0 = min((mw @ pbs[f"Bip01 {sd} Foot"].head).z for sd in ("L", "R")) - low0
        raw = {}
        for f in frames:
            if f not in self.walking and not any(g in self.walking for g in (f - 2, f - 1, f + 1, f + 2)):
                continue
            self.sc.frame_set(f)
            mw = arm.matrix_world
            toe = min((mw @ pbs[f"Bip01 {sd} Toe0"].head).z for sd in ("L", "R")) - toe0
            heel = min((mw @ pbs[f"Bip01 {sd} Foot"].head).z for sd in ("L", "R")) - heel0
            raw[f] = min(toe, heel) - self.floor_z
        sm = {f: sorted(raw.get(g, raw[f]) for g in (f - 1, f, f + 1))[1] for f in raw}
        for f, dz in sm.items():
            v = self.shift.get(f, Vector())
            self.shift[f] = Vector((v.x, v.y, v.z - dz))
        self.walk_ground = (round(min(sm.values()) * 100, 1), round(max(sm.values()) * 100, 1)) if sm else None
        self._key_trunk(frames)

    def _key_trunk(self, frames):
        """(Re)write the additive trunk keys: pelvis hinge / drop / reach shift, Spine1-2 twist + flex."""
        arm = self.arm
        bones = arm.data.bones
        ad = arm.animation_data
        keep = ad.action
        for bag, fcs in P._channelbag_fcurves(self.add_act):
            for fc in fcs:
                bag.fcurves.remove(fc)
        ad.action = self.add_act
        split = {"Bip01 Pelvis": (0.3, 0.55), "Bip01 Spine1": (0.35, 0.25), "Bip01 Spine2": (0.35, 0.2)}
        fys = getattr(self, "fy", {})
        # body axes in armature space, from the measured facing (never assume the import's axis convention)
        Ar0 = self.A(frames[0]).to_3x3().normalized().inverted()
        fwd_a = (Ar0 @ yaw_vec(self.heading_at(frames[0]))).normalized()  # constant in armature space
        flex_axis = Vector((0, 0, 1)).cross(fwd_a).normalized()  # rotating about it tips the top toward fwd_a
        for f in frames:
            yaw, flex, drop = self.trunk.get(f, (0.0, 0.0, 0.0))
            flex += self.extra_flex.get(f, 0.0)
            yaw += self.extra_yaw.get(f, 0.0)
            fy = fys.get(f, 0.0)  # the pelvis follows the feet; the spine takes the rest of the twist
            walking = f in self.walking
            for bn, (ky, kf) in split.items():
                if walking:
                    kf = {"Bip01 Pelvis": 0.0, "Bip01 Spine1": 0.55, "Bip01 Spine2": 0.45}[bn]
                M3 = bones[bn].matrix_local.to_3x3().normalized()
                yb = fy + (yaw - fy) * ky + self.pyaw.get(f, 0.0) if bn == "Bip01 Pelvis" else (yaw - fy) * ky
                # bend about the rest lateral axis, then turn: the bend goes where the bone now faces
                R = Matrix.Rotation(yb, 3, "Z") @ Matrix.Rotation(flex * kf, 3, flex_axis)  # armature space
                pb = arm.pose.bones[bn]
                pb.rotation_mode = "QUATERNION"
                pb.rotation_quaternion = (M3.inverted() @ R @ M3).to_quaternion()
                pb.keyframe_insert("rotation_quaternion", frame=f, group=bn)
            pb = arm.pose.bones["Bip01 Pelvis"]
            M3 = bones["Bip01 Pelvis"].matrix_local.to_3x3().normalized()
            back = 0.0 if walking else 0.12 * math.sin(flex * 0.55)  # hips go back as the trunk hinges forward
            d_arm = Matrix.Rotation(fy + (yaw - fy) * 0.3, 3, "Z") @ (-fwd_a * back / S + Vector((0, 0, -drop / S)))
            d_arm += Ar0 @ self.shift.get(f, Vector()) / S
            pb.location = M3.inverted() @ d_arm
            pb.keyframe_insert("location", frame=f, group="Bip01 Pelvis")
        ad.action = keep

    def _bake(self, frames):
        act = bpy.data.actions.new(f"{self.name}_baked")
        if self.motion_act is not None:
            self.arm.animation_data.action = self.motion_act
        opts = anim_utils.BakeOptions(only_selected=False, do_pose=True, do_object=True, do_visual_keying=True,
                                      do_constraint_clear=False, do_parents_clear=False, do_clean=False,
                                      do_location=True, do_rotation=True, do_scale=False, do_bbone=False,
                                      do_custom_props=False)
        anim_utils.bake_action_objects([(self.arm, act)], frames=frames, bake_options=opts)
        return act

    def _reach_need(self, frames, margin=0.95, win=6):
        """Per frame: how far (world vector) the shoulders must move so both wrists are within margin x reach."""
        arm = self.arm
        bones = arm.data.bones
        raw = {}
        self._yaw_err = {}
        for f in frames:
            if f not in self.hands:
                continue
            self.sc.frame_set(f)
            mw = arm.matrix_world
            c = Vector()
            for sd in ("L", "R"):
                Sh = mw @ arm.pose.bones[f"Bip01 {sd} UpperArm"].head
                El = mw @ arm.pose.bones[f"Bip01 {sd} Forearm"].head
                Wr = mw @ arm.pose.bones[f"Bip01 {sd} Hand"].head
                reach = ((El - Sh).length + (Wr - El).length) * margin
                T = self.hands[f][sd][0].translation
                d = T - Sh
                if d.length > reach:
                    c += d.normalized() * (d.length - reach)
            raw[f] = c
            mid = (self.hands[f]["L"][0].translation + self.hands[f]["R"][0].translation) / 2
            pel = mw @ arm.pose.bones["Bip01 Pelvis"].head
            want = math.atan2(mid.y - pel.y, mid.x - pel.x)
            have = self.heading_at(f) + self.trunk.get(f, (0.0, 0.0, 0.0))[0] + self.extra_yaw.get(f, 0.0)
            err = (want - have + math.pi) % (2 * math.pi) - math.pi
            self._yaw_err[f] = err if (c.length > 0.005 and (mid - pel).xy.length > 0.25) else 0.0
        out = {}
        fs = sorted(raw)
        for f in fs:  # smooth (a body doesn't jump): the max over a window, eased
            acc, wsum = Vector(), 0.0
            for g in range(f - win, f + win + 1):
                if g in raw:
                    wgt = math.exp(-((g - f) / (win * 0.5)) ** 2)
                    acc += raw[g] * wgt
                    wsum += wgt
            peak = max((raw[g] for g in range(f - 2, f + 3) if g in raw), key=lambda v: v.length)
            sm = acc / wsum if wsum else Vector()
            out[f] = sm if sm.length >= peak.length * 0.8 else peak * 1.0
        return out

    def _solve(self, frames):
        arm = self.arm
        bones = arm.data.bones
        act = self.act
        # 3. per frame: solve arms, legs, head on top of the baked base pose
        prev_q = {}
        pbs = arm.pose.bones
        self._measure_hinges(frames)
        fingers = [b.name for b in bones if " Finger" in b.name]
        for f in frames:
            self._f = f
            self.sc.frame_set(f)
            Aw = arm.matrix_world
            Ai = Aw.inverted()
            Ari = Aw.to_3x3().normalized().inverted()
            base = {pb.name: pb.matrix.copy() for pb in pbs}
            new = {}
            if f in self.hands:
                for sd in ("L", "R"):
                    Mw, pole_dir, _ = self.hands[f][sd]
                    names = [f"Bip01 {sd} {n}" for n in ARM_CHAIN]
                    S_w = Aw @ base[names[1]].translation
                    self._chain(base, new, names, Ai @ Mw.translation, Ari @ Mw.to_3x3(), Ai @ (S_w + pole_dir * 0.5),
                                weight=self.hand_w.get(f, 1.0))
            if f in self.feet:
                for sd in ("L", "R"):
                    Mw, pole_w = self.feet[f][sd]
                    names = [f"Bip01 Spine"] + [f"Bip01 {sd} {n}" for n in LEG_CHAIN]
                    self._chain(base, new, names, Ai @ Mw.translation, Ari @ Mw.to_3x3().normalized(),
                                Ai @ pole_w, weight=getattr(self, "feet_w", {}).get(f, 1.0))
            if f in self.look:
                self._head(base, new, Ai @ self.look[f])
            flat = self.flat.get(f, 0.0)
            if flat or any(self.flat.get(g, 0.0) for g in (f - 2, f - 1, f + 1, f + 2)):
                u = sum(self.flat.get(g, 0.0) for g in range(f - 2, f + 3)) / 5.0  # ease in / out over 5 frames
                for bn in fingers:
                    pb = pbs[bn]
                    pb.rotation_mode = "QUATERNION"
                    pb.rotation_quaternion = pb.rotation_quaternion.slerp(Quaternion(), u)
                    pb.keyframe_insert("rotation_quaternion", frame=f, group=bn)
            for bn, M in new.items():
                parent = bones[bn].parent
                pM = new.get(parent.name, base[parent.name])
                rel = parent.matrix_local.inverted() @ bones[bn].matrix_local
                basis = (pM @ rel).inverted() @ M
                q = basis.to_quaternion().normalized()
                if bn in prev_q and prev_q[bn].dot(q) < 0:
                    q.negate()
                prev_q[bn] = q
                pb = pbs[bn]
                pb.rotation_mode = "QUATERNION"
                pb.rotation_quaternion = q
                pb.keyframe_insert("rotation_quaternion", frame=f, group=bn)
        _linear_action(act)

    def _measure_hinges(self, frames):
        """Elbow / knee hinge axis of each limb, in the upper and lower bones' own frames, from the baked base
        pose frame where the limb is most bent (Biped hinges are a fixed local axis: snapped to it)."""
        arm = self.arm
        pbs = arm.pose.bones
        self.hinge = {}
        chains = [(f"Bip01 {sd} UpperArm", f"Bip01 {sd} Forearm", f"Bip01 {sd} Hand") for sd in ("L", "R")] + \
                 [(f"Bip01 {sd} Thigh", f"Bip01 {sd} Calf", f"Bip01 {sd} Foot") for sd in ("L", "R")]
        best = {c: (0.0, None) for c in chains}
        for f in frames[::5]:
            self.sc.frame_set(f)
            for c in chains:
                S_, E_, H_ = (pbs[n].matrix.translation for n in c)
                u, w = (E_ - S_).normalized(), (H_ - E_).normalized()
                bend = u.cross(w).length
                if bend > best[c][0]:
                    best[c] = (bend, (pbs[c[0]].matrix.to_3x3().normalized(), pbs[c[1]].matrix.to_3x3().normalized(),
                                      u, w, u.cross(w).normalized()))
        for c, (bend, data) in best.items():
            Ru, Rl, u, w, h = data
            hu, hl = Ru.inverted() @ h, Rl.inverted() @ h

            def snap(v):
                k = max(range(3), key=lambda i: abs(v[i]))
                out = Vector((0, 0, 0))
                out[k] = math.copysign(1.0, v[k])
                return out if bend > 0.05 else v.normalized()
            self.hinge[c[0]] = dict(u=(Ru.inverted() @ u).normalized(), hu=snap(hu), w=(Rl.inverted() @ w).normalized(),
                                    hl=snap(hl), bend=round(bend, 3))

    @staticmethod
    def _frame(a, h):
        a = a.normalized()
        h = (h - a * h.dot(a)).normalized()
        return Matrix((a, h, a.cross(h))).transposed()

    def _chain(self, base, new, names, T, R_end, pole, weight=1.0):
        """Two-bone solve in armature space. names = (parent, upper, lower, end). Each bone is oriented by its own
        direction AND the limb's hinge axis (the bend plane through the pole), so the twist is fully determined
        every frame: no flips, whatever the reach."""
        par, up, lo, end = names
        S_ = base[up].translation
        Eb = base[lo].translation
        Hb = base[end].translation
        a, b = (Eb - S_).length, (Hb - Eb).length
        E, T2, clamped = two_bone(S_, a, b, T, pole)
        self.clamped += int(clamped)
        if clamped:
            self.deficits.append((self._f, end, round(((T - S_).length - (a + b)) * S * 100, 1)))
        hg = self.hinge[up]
        axis = (T2 - S_).normalized()
        n = pole - S_
        n = n - axis * n.dot(axis)
        prev = self.last_n.get(up)
        if prev is not None and (n.length < 0.2 * (pole - S_).length or n.normalized().dot(prev) < 0.0):
            pn = prev - axis * prev.dot(axis)  # near-degenerate: keep the previous bend plane (no flip)
            n = pn if pn.length > 1e-6 else n
        n = n.normalized() if n.length > 1e-6 else axis.orthogonal().normalized()
        self.last_n[up] = n.copy()
        h_w = n.cross(axis).normalized()  # = direction of (upper x lower) for a limb bent toward the pole
        u_w, w_w = (E - S_).normalized(), (T2 - E).normalized()
        Ru = self._frame(u_w, h_w) @ self._frame(hg["u"], hg["hu"]).inverted()
        Rl = self._frame(w_w, h_w) @ self._frame(hg["w"], hg["hl"]).inverted()
        if weight < 1.0:  # ramp from the clip's own pose to the contact pose (no jump when a grip starts)
            def mix(Rb, Rn):
                return Rb.to_quaternion().slerp(Rn.to_quaternion(), weight).to_matrix()
            Ru = mix(base[up].to_3x3().normalized(), Ru)
            E = S_ + Ru @ (base[up].to_3x3().normalized().inverted() @ (Eb - S_))  # elbow carried by the upper arm
            Rl = mix(base[lo].to_3x3().normalized(), Rl)
            T2 = E + Rl @ (base[lo].to_3x3().normalized().inverted() @ (Hb - Eb))
            R_end = mix(base[end].to_3x3().normalized(), R_end.normalized())
        new[up] = Matrix.Translation(S_) @ Ru.to_4x4()
        new[lo] = Matrix.Translation(E) @ Rl.to_4x4()
        new[end] = Matrix.Translation(T2) @ R_end.normalized().to_4x4()

    def _head(self, base, new, look):
        """Look-at that keeps the head upright (no roll): forward toward the target, the head's up axis toward
        armature up; 75 % over the clip's own head, never more than 70 deg from it."""
        Mh = base["Bip01 Head"]
        R0 = Mh.to_3x3().normalized()
        ax, sg = self.head_fwd
        bones = self.arm.data.bones
        if not hasattr(self, "_head_up"):
            hm = bones["Bip01 Head"].matrix_local.to_3x3().normalized()
            cands = [(i, g) for i in range(3) for g in (1, -1) if i != ax]
            self._head_up = max(cands, key=lambda c: c[1] * Vector(hm.col[c[0]]).dot(Vector((0, 0, 1))))
        ui, us = self._head_up
        want = (look - Mh.translation).normalized()
        up = Vector((0, 0, 1))
        up_t = (up - want * up.dot(want))
        if up_t.length < 1e-4:
            return
        up_t.normalize()
        # target rotation: maps the head's local forward / up axes onto (want, up_t)
        lf, lu = Vector((0, 0, 0)), Vector((0, 0, 0))
        lf[ax], lu[ui] = sg, us
        Rt = self._frame(want, up_t) @ self._frame(lf, lu).inverted()
        q0, qt = R0.to_quaternion(), Rt.to_quaternion()
        if q0.dot(qt) < 0:
            qt.negate()
        ang = q0.rotation_difference(qt).angle
        w = 0.75 * min(1.0, math.radians(70) / ang) if ang > 1e-6 else 0.0
        new["Bip01 Head"] = Matrix.Translation(Mh.translation) @ q0.slerp(qt, w).to_matrix().to_4x4()

    # ------------------------------------------------------------------------------------------------ checks
    def palm_world(self, sd):
        arm = self.arm
        pb = arm.pose.bones[f"Bip01 {sd} Hand"]
        return arm.matrix_world @ (pb.matrix @ self.palm[sd]["offset"])

    def bake(self, frames):
        """(apply() already wrote plain keys; kept for the call order)"""
        return self.act


def _linear_action(act):
    for bag, fcs in P._channelbag_fcurves(act):
        for fc in fcs:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"


def box_sockets(dims, toward, up_frac=0.15, front_frac=0.2, inset=0.01):
    """Two palm contact points + palm frames on a box's lateral faces, in the BOX's local frame.
    dims = (w along local x, d along local y, h along local z; origin at the bottom centre).
    toward = local unit vector (x/y plane) pointing from the box to the worker. The hands grip the faces
    perpendicular to the lateral axis, palms facing in (1 cm inside the face: slightly inside reads better than
    floating off), fingers pointing away from the worker and a little down. Returns {'L'|'R': (point, R3)}."""
    w, d, h = dims
    lat = UP.cross(toward).normalized()
    half = abs(lat.x) * w / 2 + abs(lat.y) * d / 2
    depth = abs(toward.x) * w / 2 + abs(toward.y) * d / 2
    out = {}
    if h < 0.08:  # flat mailer: both palms on top near the lateral ends (a side grip would put hands in the belt)
        for sd, side in (("L", -lat), ("R", lat)):
            p = side * max(half - 0.06, 0.03) + toward * depth * 0.1 + UP * (h - 0.004)
            along = (-toward * 0.9 + side * 0.25)
            out[sd] = (p, frame_from(along, -UP))
        return out
    # the worker faces F = -toward, so his left = UP x F = -lat: left hand on the -lat face
    for sd, side in (("L", -lat), ("R", lat)):
        p = side * (half - inset) + toward * depth * front_frac + UP * h * (0.5 + up_frac)
        along = (-toward * 0.94 - UP * 0.34)
        out[sd] = (p, frame_from(along, -side))
    return out
