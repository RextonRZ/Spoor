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
                 clip_offset=0):
        self.sc, self.coll, self.name = scene, coll, name
        self.heading, self.floor_z = heading, floor_z
        self.st = st
        self.arm = P._instance(scene, coll, st, name, hat_colour)
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

    def rig(self):
        """(kept for the call order; the solver needs no helper objects)"""
        self.add_act = bpy.data.actions.new(f"{self.name}_trunk")

    # ------------------------------------------------------------------------------------------------ body model
    def torso_frame(self, f):
        """World frame of the chest from the authored trunk values (for neutral hands, elbow poles, look)."""
        yaw, flex, drop = self.trunk.get(f, (0.0, 0.0, 0.0))
        h = self.heading + yaw
        fwd, left = yaw_vec(h), yaw_vec(h + math.pi / 2)
        base = Vector((self.pelvis0.x, self.pelvis0.y, self.pelvis0.z - drop))
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

    def set_hands(self, f, targets):
        """targets: {sd: (palm_point, R_contact)} in world."""
        chest, fwd, left, h = self.torso_frame(f)
        out = {}
        for sd, sg in (("L", 1), ("R", -1)):
            p, R = targets[sd]
            pole = chest + left * sg * 0.55 - fwd * 0.30 - UP * 0.45
            out[sd] = (self.hand_target(sd, p, R), pole, (p, R))
        self.hands[f] = out

    def set_feet(self, f, feet=None, fy=0.0):
        """feet: explicit world foot matrices (else the pinned frame-1 pose); fy: their yaw (rel. to heading)."""
        fwd = yaw_vec(self.heading + fy)
        out = {}
        for sd in ("L", "R"):
            M = feet[sd] if feet else self.foot0[sd]
            out[sd] = (M, M.translation + fwd * 0.8 + UP * 0.45)
        self.feet[f] = out

    def auto_steps(self, frames, max_twist=0.95, rest_twist=0.45, step_s=0.55, fps=10):
        """Pivot steps: when the trunk would twist more than max_twist from the feet, the feet step round (the foot
        on the turning side first, a 5 cm lift each, ~0.55 s for both) to leave rest_twist; the pelvis follows the
        feet. Fills self.fy and the feet keys for every frame."""
        frames = list(frames)
        n = max(2, int(round(step_s * fps)))
        yaw = {f: self.trunk.get(f, (0.0, 0.0, 0.0))[0] for f in frames}
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
        c = (self.foot0["L"].translation + self.foot0["R"].translation) / 2
        c.z = 0.0

        def placed(sd, a):
            return Matrix.Translation(c) @ Matrix.Rotation(a, 4, "Z") @ Matrix.Translation(-c) @ self.foot0[sd]

        for f in frames:
            a = fy.get(f, cur)
            feet = {sd: placed(sd, a) for sd in ("L", "R")}
            for (f0, f1, a0, a1) in steps:
                if f0 <= f <= f1:
                    first = "L" if a1 > a0 else "R"  # turning left: left foot leads
                    for sd in ("L", "R"):
                        u0, u1 = (0.0, 0.55) if sd == first else (0.45, 1.0)
                        u = min(max(((f - f0) / (f1 - f0) - u0) / (u1 - u0), 0.0), 1.0)
                        M = placed(sd, a0 + (a1 - a0) * smooth(u))
                        feet[sd] = Matrix.Translation(UP * 0.05 * math.sin(math.pi * u)) @ M
            self.set_feet(f, feet, fy=a)

    def set_trunk(self, f, yaw, flex, drop):
        self.trunk[f] = (yaw, flex, drop)

    def set_look(self, f, point):
        self.look[f] = point.copy()

    # ------------------------------------------------------------------------------------------------ solve + keys
    def apply(self, frames):
        frames = list(frames)
        arm = self.arm
        ad = arm.animation_data
        self.shift = {}
        tr = ad.nla_tracks.new()
        tr.name = "trunk_add"
        self._key_trunk(frames)
        st = tr.strips.new("trunk", int(frames[0]), self.add_act)
        if hasattr(st, "action_slot") and getattr(self.add_act, "slots", None):
            st.action_slot = self.add_act.slots[0]
        st.blend_type = "COMBINE"
        st.extrapolation = "HOLD"
        # reach adaptation: bake, measure how far each wrist target is beyond the arm's reach, move the hips
        # toward the work (and lower them for low work), smoothed over time; feet stay pinned. Twice.
        self.adapt = []
        for _ in range(2):
            act = self._bake(frames)
            need = self._reach_need(frames)
            ad.action = None
            bpy.data.actions.remove(act)
            moved = 0
            for f, c in need.items():
                old = self.shift.get(f, Vector())
                cand = old + c
                h = Vector((cand.x, cand.y, 0))
                if h.length > 0.2:
                    h *= 0.2 / h.length
                z = min(0.0, max(cand.z, -0.3)) - h.length_squared / (2 * 0.85)  # keep the legs' length
                self.shift[f] = Vector((h.x, h.y, z))
                moved += int(c.length > 0.005)
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
        Ar0 = arm.matrix_world.to_3x3().normalized().inverted()
        fwd_a = (Ar0 @ yaw_vec(self.heading)).normalized()
        flex_axis = Vector((0, 0, 1)).cross(fwd_a).normalized()  # rotating about it tips the top toward fwd_a
        for f in frames:
            yaw, flex, drop = self.trunk.get(f, (0.0, 0.0, 0.0))
            fy = fys.get(f, 0.0)  # the pelvis follows the feet; the spine takes the rest of the twist
            for bn, (ky, kf) in split.items():
                M3 = bones[bn].matrix_local.to_3x3().normalized()
                yb = fy + (yaw - fy) * ky if bn == "Bip01 Pelvis" else (yaw - fy) * ky
                # bend about the rest lateral axis, then turn: the bend goes where the bone now faces
                R = Matrix.Rotation(yb, 3, "Z") @ Matrix.Rotation(flex * kf, 3, flex_axis)  # armature space
                pb = arm.pose.bones[bn]
                pb.rotation_mode = "QUATERNION"
                pb.rotation_quaternion = (M3.inverted() @ R @ M3).to_quaternion()
                pb.keyframe_insert("rotation_quaternion", frame=f, group=bn)
            pb = arm.pose.bones["Bip01 Pelvis"]
            M3 = bones["Bip01 Pelvis"].matrix_local.to_3x3().normalized()
            back = 0.12 * math.sin(flex * 0.55)  # hips go back as the trunk hinges forward
            d_arm = Matrix.Rotation(fy + (yaw - fy) * 0.3, 3, "Z") @ (-fwd_a * back / S + Vector((0, 0, -drop / S)))
            d_arm += Ar0 @ self.shift.get(f, Vector()) / S
            pb.location = M3.inverted() @ d_arm
            pb.keyframe_insert("location", frame=f, group="Bip01 Pelvis")
        ad.action = keep

    def _bake(self, frames):
        act = bpy.data.actions.new(f"{self.name}_baked")
        opts = anim_utils.BakeOptions(only_selected=False, do_pose=True, do_object=False, do_visual_keying=True,
                                      do_constraint_clear=False, do_parents_clear=False, do_clean=False,
                                      do_location=True, do_rotation=True, do_scale=False, do_bbone=False,
                                      do_custom_props=False)
        anim_utils.bake_action_objects([(self.arm, act)], frames=frames, bake_options=opts)
        return act

    def _reach_need(self, frames, margin=0.95, win=6):
        """Per frame: how far (world vector) the shoulders must move so both wrists are within margin x reach."""
        arm = self.arm
        mw = arm.matrix_world
        bones = arm.data.bones
        raw = {}
        for f in frames:
            if f not in self.hands:
                continue
            self.sc.frame_set(f)
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
        Aw = arm.matrix_world
        Ai = Aw.inverted()
        Ar = Aw.to_3x3().normalized()
        Ari = Ar.inverted()
        prev_q = {}
        pbs = arm.pose.bones
        for f in frames:
            self._f = f
            self.sc.frame_set(f)
            base = {pb.name: pb.matrix.copy() for pb in pbs}
            new = {}
            if f in self.hands:
                for sd in ("L", "R"):
                    Mw, pole_w, _ = self.hands[f][sd]
                    names = [f"Bip01 {sd} {n}" for n in ARM_CHAIN]
                    self._chain(base, new, names, Ai @ Mw.translation, Ari @ Mw.to_3x3(), Ai @ pole_w)
            if f in self.feet:
                for sd in ("L", "R"):
                    Mw, pole_w = self.feet[f][sd]
                    names = [f"Bip01 Spine"] + [f"Bip01 {sd} {n}" for n in LEG_CHAIN]
                    self._chain(base, new, names, Ai @ Mw.translation, Ari @ Mw.to_3x3().normalized(),
                                Ai @ pole_w)
            if f in self.look:
                self._head(base, new, Ai @ self.look[f])
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

    def _chain(self, base, new, names, T, R_end, pole):
        """Two-bone solve in armature space. names = (parent, upper, lower, end)."""
        par, up, lo, end = names
        S_ = base[up].translation
        Eb = base[lo].translation
        Hb = base[end].translation
        a, b = (Eb - S_).length, (Hb - Eb).length
        E, T2, clamped = two_bone(S_, a, b, T, pole)
        self.clamped += int(clamped)
        if clamped:
            self.deficits.append((self._f, end, round(((T - S_).length - (a + b)) * S * 100, 1)))
        R1 = (Eb - S_).rotation_difference(E - S_).to_matrix()
        Ru = R1 @ base[up].to_3x3()
        fdir = R1 @ (Hb - Eb)
        R2 = fdir.rotation_difference(T2 - E).to_matrix()
        Rl = R2 @ R1 @ base[lo].to_3x3()
        new[up] = Matrix.Translation(S_) @ Ru.to_4x4()
        new[lo] = Matrix.Translation(E) @ Rl.to_4x4()
        new[end] = Matrix.Translation(T2) @ R_end.normalized().to_4x4()

    def _head(self, base, new, look):
        Mh = base["Bip01 Head"]
        ax, sg = self.head_fwd
        cur = Vector(Mh.to_3x3().col[ax]).normalized() * sg
        want = (look - Mh.translation).normalized()
        q = cur.rotation_difference(want)
        ang = min(q.angle, math.radians(70)) * 0.75
        q = Quaternion(q.axis, ang) if q.angle > 1e-6 else Quaternion()
        new["Bip01 Head"] = Matrix.Translation(Mh.translation) @ (q.to_matrix() @ Mh.to_3x3()).to_4x4()

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
