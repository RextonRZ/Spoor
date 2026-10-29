"""Station workers driven by the parcel flow (one timeline: footage, scan_simulated log and truth all come from it).

Dock unload (D02 / D05, two Rocketbox workers per lorry, one each side of the telescopic boom's nose):
  the lorry holds a loose-loaded wall of cartons (columns, small gaps, front face ~0.4 m past the boom nose).
  Each worker cycles: reach to the top carton of a column (hip hinge + knee bend for low ones) -> grip both
  lateral faces -> pull it out -> turn (trunk twist ~60-90 deg, feet planted) -> hold if the boom nose isn't
  clear -> set it on the boom -> retract -> short pause. 4-6 s per carton (real: 600-900 parcels/h/person).
  THAT carton becomes a flow parcel at the release frame: it rides the boom, collector, induction, tunnel, loop,
  chute and bag like any other.

Used by flow.py:
    st = stations.Docks(ctx)        before the simulation (plans the walls, the picks and their release times)
    st.spawns(bn, t)                 picks released on boom bn by time t (flow puts them on the belt)
    st.preroll_rate(bn)              parcels/s for the pre-roll spawns at that boom (same steady state)
    st.pre_tracks()                  {Parcel: {frame: (pos, yaw)}} wall + carry, for frames before release
    st.build(frames)                 after the bake: walls, workers, IK, bake, numeric checks -> report
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

import contact as C
import people as P

UP = Vector((0, 0, 1))
DOCKS = [dict(door="D02", cy=11.0, belt="boom_D02", seed=21), dict(door="D05", cy=23.0, belt="boom_D05", seed=55)]
X_BACK, X_FACE, X_NOSE = -7.08, -1.60, -1.20  # lorry front wall (inside), wall face, boom nose (early unload)
Y_HALF = 1.07  # inside half width of the body (walls at +-1.12)
WORKER_X, WORKER_DY = -1.28, 0.50  # 0.32 m from the face, shoulder to the boom's side guard (QA: 0.46/0.64 too far)
BELT_START_X = -1.15
PLACE_X = -0.98  # carton centre on the nose when set down
# side +1 (north of the boom): feet face 205 deg (mostly at the wall, a little toward the boom), mirrored for -1
FEET = {+1: math.radians(207), -1: math.radians(153)}
AVATARS = [  # (avatar, vest, hat) per worker slot: D02 north / south, D05 north / south
    ("Male_Adult_05", "orange", "cap"), ("Male_Adult_09", None, None),
    ("Male_Adult_12", "lime", "hard"), ("Female_Adult_07", "yellow", None)]


def lerp(a, b, u):
    return a + (b - a) * u


def ang_lerp(a, b, u):
    d = (b - a + math.pi) % (2 * math.pi) - math.pi
    return a + d * u


class Box:
    """A carton in the wall (bottom centre, yaw, dims w x d x h with w along local x)."""

    def __init__(self, x, y, z, dims, yaw):
        self.pos, self.dims, self.yaw = Vector((x, y, z)), dims, yaw
        self.pick = None

    def matrix(self, pos=None, yaw=None):
        return Matrix.Translation(pos if pos is not None else self.pos) @ Matrix.Rotation(
            self.yaw if yaw is None else yaw, 4, "Z")

    def span_y(self):
        w, d, h = self.dims
        return w if abs(math.cos(self.yaw)) < 0.5 else d

    def depth_x(self):
        w, d, h = self.dims
        return d if abs(math.cos(self.yaw)) < 0.5 else w


def build_wall(rnd, cy, box_dims):
    """Columns of cartons across the body, front face at X_FACE, back rows to X_BACK. Returns (front, back)."""
    usable = [d for d in box_dims if 0.2 <= d[0] <= 0.45 and d[2] >= 0.1]
    front, back = [], []
    y = cy - Y_HALF
    while True:
        dims0 = rnd.choice(usable)
        colw = dims0[0]
        if y + colw > cy + Y_HALF:
            break
        yc = y + colw / 2
        top = rnd.uniform(1.35, 1.95)
        z = 0.0
        while z < top - 0.08:
            fits = [d for d in usable if colw - 0.07 <= d[0] <= colw] or [dims0]
            dims = rnd.choice(fits)
            if z + dims[2] > 2.3:
                break
            yaw = math.pi / 2 + rnd.uniform(-0.04, 0.04)  # w along world y (faces the worker)
            xf = X_FACE - rnd.uniform(0.0, 0.035)
            b = Box(xf - dims[1] / 2, yc + rnd.uniform(-0.015, 0.015), z, dims, yaw)
            front.append(b)
            z += dims[2]
        # back rows: up to the lorry's front wall, a little taller
        xb = X_FACE - max(d.depth_x() for d in front[-6:] if abs(d.pos.y - yc) < 0.05) - 0.03
        while xb - 0.2 > X_BACK:
            z = 0.0
            tb = rnd.uniform(1.6, 2.25)
            dep = 0.0
            while z < tb - 0.08:
                dims = rnd.choice(usable)
                if dims[1] > xb - X_BACK:
                    break
                back.append(Box(xb - dims[1] / 2, yc + rnd.uniform(-0.03, 0.03), z,
                                (min(dims[0], colw), dims[1], dims[2]), math.pi / 2 + rnd.uniform(-0.05, 0.05)))
                z += dims[2]
                dep = max(dep, dims[1])
            if dep == 0:
                break
            xb -= dep + 0.02
        y += colw + rnd.uniform(0.045, 0.085)
    return front, back


def fill_mesh(name, boxes, coll):
    """The load behind the face: one mesh of plain cartons (kraft / white board), no labels (never visible)."""
    bm = bmesh.new()
    for b in boxes:
        w, d, h = b.dims
        M = b.matrix() @ Matrix.Translation((0, 0, h / 2)) @ Matrix.Diagonal((w * 0.995, d * 0.995, h, 1))
        r = bmesh.ops.create_cube(bm, size=1.0, matrix=M)
        mi = 1 if random.Random(hash((round(b.pos.x, 3), round(b.pos.y, 3), round(b.pos.z, 3)))).random() < 0.1 else 0
        for f in {f for v in r["verts"] for f in v.link_faces}:
            f.material_index = mi
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for mn in ("cardboard", "cardboard_white"):
        me.materials.append(bpy.data.materials.get(mn))
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return len(boxes)


class Pick:
    def __init__(self, box, worker):
        self.box, self.worker = box, worker
        self.parcel = None
        self.t = {}  # phase start times
        self.t_rel = None
        self.place = None  # (pos, yaw) on the belt at release
        self.s = None


class DockWorker:
    def __init__(self, dock, side, avatar, k):
        self.dock, self.side, self.avatar, self.k = dock, side, avatar, k
        self.pos = Vector((WORKER_X, dock["cy"] + side * WORKER_DY, 0.0))
        self.heading = FEET[side]
        self.picks = []
        self.segs = []  # (t0, t1, kind, data)
        self.name = f"worker_dock_{dock['door']}_{'n' if side > 0 else 's'}"


class Docks:
    def __init__(self, ctx):
        self.ctx = ctx
        self.rnd = random.Random(ctx["seed"] + 101)
        self.DT, self.F0, self.F1 = ctx["DT"], ctx["F0"], ctx["F1"]
        self.T_END = (self.F1 - self.F0) * self.DT
        self.B = ctx["B"]
        self.belts = {d["belt"] for d in DOCKS}
        self.walls, self.workers, self.picks = {}, [], []
        for i, dock in enumerate(DOCKS):
            r = random.Random(dock["seed"])
            front, back = build_wall(r, dock["cy"], ctx["BOX_DIMS"])
            self.walls[dock["door"]] = (front, back)
            for j, side in enumerate((+1, -1)):
                w = DockWorker(dock, side, AVATARS[i * 2 + j], i * 2 + j)
                self.workers.append(w)
        for dock in DOCKS:
            ws = [w for w in self.workers if w.dock is dock]
            self._schedule(dock, ws)

    # ------------------------------------------------------------------------------------------------ planning
    def _slots(self, w):
        """The carton order for one worker: columns on his side, nearest first, each top-down."""
        front, _ = self.walls[w.dock["door"]]
        cy = w.dock["cy"]
        cols = {}
        for b in front:
            cols.setdefault(round(b.pos.y, 2), []).append(b)
        mine = []
        for yc, bs in cols.items():
            rel = (yc - w.pos.y) * w.side  # >0: further out (toward the lorry wall)
            if (yc - cy) * w.side < 0.1 or not (-0.62 <= rel <= 0.42):  # own half of the face only (QA: arms crossed)
                continue
            mine.append((abs(yc - (w.pos.y - w.side * 0.2)), sorted(bs, key=lambda b: -b.pos.z)))
        mine.sort(key=lambda m: m[0])
        order = []
        for _, bs in mine:
            for b in bs:
                if b.pos.z + b.dims[2] * 0.5 < 0.32:  # last one or two on the floor: left for later (sweep)
                    break
                order.append(b)
        return order

    def _trunk_for(self, w, target, hand_h):
        """(yaw rel. to the feet, flex, drop) to work at a target point at hand height hand_h."""
        d = target - w.pos
        yaw = (math.atan2(d.y, d.x) - w.heading + math.pi) % (2 * math.pi) - math.pi
        if hand_h >= 1.15:
            flex, drop = 0.06, 0.0
        elif hand_h >= 0.75:
            u = (1.15 - hand_h) / 0.4
            flex, drop = 0.06 + 0.44 * u, 0.05 * u
        else:
            u = min((0.75 - hand_h) / 0.4, 1.0)
            flex, drop = 0.5 + 0.32 * u, 0.05 + 0.25 * u
        reach = d.xy.length
        if reach > 0.55:
            flex += 0.6 * (reach - 0.55)
        return yaw * 0.92, flex, drop  # head and arms take the rest of the turn

    def _schedule(self, dock, ws):
        rnd = self.rnd
        bn = dock["belt"]
        belt = self.B[bn]
        busy = []  # (turn start, release, half length) of every carton set on this boom
        for w in ws:
            slots = self._slots(w)
            t = -rnd.uniform(0.4, 2.3)  # mid-cycle at frame 1 (the first carton is released after frame 1)
            ready = (0.0, 0.08, 0.0)
            last_place_yaw = 0.0
            for box in slots:
                if t > self.T_END + 1.0:
                    break
                pk = Pick(box, w)
                w_, d_, h_ = box.dims
                grip_h = box.pos.z + h_ * 0.65
                low = grip_h < 0.8
                T_reach = rnd.uniform(0.85, 1.15) + (0.35 if low else 0.0)
                T_settle = rnd.uniform(0.12, 0.2)
                T_pull = rnd.uniform(0.3, 0.42) + (0.15 if low else 0.0)
                T_turn = rnd.uniform(0.8, 1.05) + (0.2 if low else 0.0)
                T_place = rnd.uniform(0.28, 0.36)
                T_ret = rnd.uniform(0.4, 0.55)
                # place spot: centre on the belt, rear edge on the nose
                yaw_end = box.yaw + self._turn_angle(w, box)
                hx = abs(math.cos(yaw_end)) * w_ / 2 + abs(math.sin(yaw_end)) * d_ / 2
                x_c = max(PLACE_X + rnd.uniform(-0.04, 0.04), BELT_START_X + hx + 0.01)
                s = x_c - BELT_START_X
                hm = max(w_, d_) / 2  # the flow's clearance rule uses the longest side (any orientation)
                t_hold = t + T_reach + T_settle + T_pull  # carton out of the wall, at the chest
                ts = t_hold  # turn start: wait (holding it at the chest) until the nose and the other worker are clear
                for _ in range(8):
                    moved = False
                    for (ta_turn, ta_rel, hh) in sorted(busy):
                        sep = (hh + hm + 0.12) / belt.speed + self.DT
                        rel = ts + T_turn + T_place
                        if ts < ta_rel + 0.25 and ta_turn < rel + 0.25:  # both over the nose at once
                            ts, moved = ta_rel + 0.25, True
                        rel = ts + T_turn + T_place
                        if ta_rel - sep < rel < ta_rel + sep:  # the nose not clear yet
                            ts, moved = ta_rel + sep - T_turn - T_place, True
                    if not moved:
                        break
                rel = ts + T_turn + T_place
                f_rel = self.F0 + math.ceil(rel / self.DT - 1e-6)  # release on a frame
                ts += (f_rel - self.F0) * self.DT - rel
                pk.t = dict(reach=t, settle=t + T_reach, pull=t + T_reach + T_settle, hold=t_hold, turn=ts,
                            place=ts + T_turn, release=ts + T_turn + T_place, end=ts + T_turn + T_place + T_ret)
                pk.f_rel = f_rel
                pk.t_rel = pk.t["release"]
                pos = belt.at(s)[0]
                pk.s = s
                pk.place = (Vector((pos.x, dock["cy"], pos.z)), yaw_end)
                busy.append((pk.t["turn"], pk.t_rel, hm))
                box.pick = pk
                w.picks.append(pk)
                self.picks.append(pk)
                pause = min(rnd.expovariate(1 / 0.55), 1.8)
                if rnd.random() < 0.12:
                    pause += rnd.uniform(1.2, 2.4)  # look down the boom / straighten up / wipe hands
                pk.pause = pause
                t = pk.t["end"] + pause
        # carton look -> flow Parcel (fixed dims, cardboard)
        Parcel = self.ctx["Parcel"]
        for pk in [p for p in self.picks if p.worker in ws]:
            pk.gone = pk.t_rel < 0  # released before frame 1: carton gone, its parcel came from the pre-roll
            if pk.gone:
                continue
            if pk.t["reach"] > self.T_END:  # not touched in the window: stays in the wall
                pk.box.pick = None
                pk.parcel = None
                continue
            p = Parcel(self.ctx["next_k"]())
            p.kind, p.dims, p.body = "box", tuple(pk.box.dims), ("box_white" if self.rnd.random() < 0.12 else "box")
            p.meta.update(kind="box", dims_m=list(p.dims), body=p.body)
            p.half = max(p.dims[:2]) / 2
            p.yaw_off = pk.place[1]
            p.station = pk
            pk.parcel = p
        for w in ws:
            w.picks = [pk for pk in w.picks if pk.box.pick is pk and (not pk.gone or pk.t["end"] + pk.pause > 0)]
        self.picks = [pk for pk in self.picks if pk.box.pick is pk]

    def _turn_angle(self, w, box):
        """How far the carton turns about the vertical while carried (= trunk turn from wall to boom)."""
        a0 = math.atan2(box.pos.y - w.pos.y, box.pos.x - w.pos.x)
        a1 = math.atan2(w.dock["cy"] - w.pos.y, PLACE_X - w.pos.x)
        return (a1 - a0 + math.pi) % (2 * math.pi) - math.pi

    # ------------------------------------------------------------------------------------------------ flow hooks
    def spawns(self, bn, t):
        out = []
        for pk in self.picks:
            if pk.worker.dock["belt"] == bn and pk.parcel is not None and not getattr(pk, "spawned", False) \
                    and pk.t_rel <= t + 1e-6:
                pk.spawned = True
                out.append(pk)
        return out

    def preroll_rate(self, bn):
        ws = [w for w in self.workers if w.dock["belt"] == bn]
        per = []
        for w in ws:
            cyc = [pk.t["end"] + pk.pause - pk.t["reach"] for pk in w.picks]
            per.append(len(cyc) / max(sum(cyc), 1e-6) if cyc else 0.2)
        return sum(per)

    # ------------------------------------------------------------------------------------------------ carry path
    def _chest_point(self, pk):
        """Where the carton is held while waiting: pulled in toward the body, at about belly height."""
        box, w = pk.box, pk.worker
        out_dir = (w.pos - box.pos).xy.normalized()
        p1 = box.pos + Vector((out_dir.x, out_dir.y, 0)) * 0.2 + UP * 0.035
        hold = p1 + Vector((out_dir.x, out_dir.y, 0)) * 0.08
        hold.z = max(0.78, min(p1.z, 1.05)) - box.dims[2] * 0.4
        return p1, hold

    def carton_pose(self, pk, t):
        """(bottom-centre position, yaw) of the carton at time t (None after release)."""
        box, w, T = pk.box, pk.worker, pk.t
        if t < T["pull"]:
            return box.pos.copy(), box.yaw
        if t >= T["release"]:
            return None
        p1, hold = self._chest_point(pk)
        if t < T["hold"]:
            u = C.smooth((t - T["pull"]) / (T["hold"] - T["pull"]))
            return box.pos.lerp(p1, u), box.yaw
        if t < T["turn"]:  # waiting with it at the chest (p1 -> hold over <= 0.45 s)
            u = C.smooth((t - T["hold"]) / 0.45)
            return p1.lerp(hold, u), box.yaw
        start = p1.lerp(hold, C.smooth((T["turn"] - T["hold"]) / 0.45))
        place, yaw_end = pk.place
        above = place + UP * 0.075
        if t < T["place"]:
            u = C.smooth((t - T["turn"]) / (T["place"] - T["turn"]))
            piv = w.pos
            a0 = math.atan2(start.y - piv.y, start.x - piv.x)
            a1 = math.atan2(above.y - piv.y, above.x - piv.x)
            r0, r1 = (start - piv).xy.length, (above - piv).xy.length
            da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
            ty0, ty1 = self._trunk_for(w, start, 1.0)[0], self._trunk_for(w, above, 1.0)[0]
            if abs(ty1 - ty0) > 0.1 and da * (ty1 - ty0) < 0:  # turn the way the body turns (through the front)
                da -= math.copysign(2 * math.pi, da)
            a = a0 + da * u
            r = lerp(r0, r1, u) + 0.05 * math.sin(math.pi * u)  # swing a little wide of the body
            z = lerp(start.z, above.z, u) + 0.05 * math.sin(math.pi * u)
            dy = (yaw_end - box.yaw + math.pi) % (2 * math.pi) - math.pi
            if abs(da) > math.pi and dy * da < 0:
                dy += math.copysign(2 * math.pi, da)
            return Vector((piv.x + r * math.cos(a), piv.y + r * math.sin(a), z)), box.yaw + dy * u
        u = C.smooth((t - T["place"]) / (T["release"] - T["place"]))
        return above.lerp(place, u), yaw_end

    def pre_tracks(self):
        out = {}
        for pk in self.picks:
            if pk.parcel is None:
                continue
            tr = {}
            for f in range(self.F0, min(pk.f_rel, self.F1 + 1)):
                pose = self.carton_pose(pk, (f - self.F0) * self.DT)
                if pose is not None:
                    tr[f] = pose
            out[pk.parcel] = tr
        return out

    # ------------------------------------------------------------------------------------------------ worker motion
    def _worker_state(self, w, wk, t):
        """Trunk (yaw, flex, drop), hands {sd: (point, R)} or None for neutral, look point, at time t."""
        for pk in w.picks:
            T = pk.t
            if t < T["reach"]:
                break
            if t <= T["end"] + pk.pause:
                return self._in_cycle(w, wk, pk, t)
        # before the first cycle / in a pause: ready, looking at the wall
        nxt = next((pk for pk in w.picks if pk.t["reach"] > t), None)
        tgt = nxt.box.pos + UP * 0.2 if nxt else self._idle_target(w)
        tr = self._trunk_for(w, tgt, 1.2)
        return (tr[0] * 0.5, 0.06, 0.0), None, tgt

    def _in_cycle(self, w, wk, pk, t):
        T = pk.t
        box = pk.box
        grip_h = box.pos.z + box.dims[2] * 0.65
        slot_trunk = self._trunk_for(w, box.pos + UP * box.dims[2] * 0.5, grip_h)
        place, yaw_end = pk.place
        place_trunk = self._trunk_for(w, place, place.z + box.dims[2] * 0.65)
        place_trunk = (place_trunk[0], place_trunk[1] + 0.05, place_trunk[2])
        ready = (slot_trunk[0] * 0.45, 0.08, 0.0)
        socks = C.box_sockets(box.dims, self._toward_local(w, box))
        if t < T["settle"]:  # reach
            u = C.smooth((t - T["reach"]) / (T["settle"] - T["reach"]))
            trunk = tuple(lerp(a, b, u) for a, b in zip(self._prev_trunk(w, pk), slot_trunk))
            return trunk, ("blend", u, self._socket_world(box.matrix(), socks)), box.pos + UP * box.dims[2] * 0.5
        pose = self.carton_pose(pk, t)
        if pose is not None:
            M = box.matrix(*pose)
            p1, hold = self._chest_point(pk)
            carry_trunk = self._trunk_for(w, hold + UP * 0.1, hold.z + box.dims[2] * 0.65)
            pulled = (slot_trunk[0], slot_trunk[1] - 0.08, slot_trunk[2] * 0.7)
            if t < T["hold"]:
                u = C.smooth((t - T["pull"]) / (T["hold"] - T["pull"])) if t > T["pull"] else 0.0
                trunk = tuple(lerp(a, b, u) for a, b in zip(slot_trunk, pulled))
                return trunk, ("grip", self._socket_world(M, socks)), box.pos + UP * box.dims[2] * 0.5
            if t < T["turn"]:  # holding it at the chest, eyes on the nose
                u = C.smooth((t - T["hold"]) / 0.45)
                trunk = tuple(lerp(a, b, u) for a, b in zip(pulled, carry_trunk))
                return trunk, ("grip", self._socket_world(M, socks)), place + UP * 0.1
            u = C.smooth((T["turn"] - T["hold"]) / 0.45)
            start_trunk = tuple(lerp(a, b, u) for a, b in zip(pulled, carry_trunk))
            if t < T["place"]:
                u = C.smooth((t - T["turn"]) / (T["place"] - T["turn"]))
                trunk = tuple(lerp(x, y, u) for x, y in zip(start_trunk, place_trunk))
                return trunk, ("grip", self._socket_world(M, socks)), place + UP * 0.1
            return place_trunk, ("grip", self._socket_world(M, socks)), place + UP * 0.05
        # released: hands come off where they let go, trunk back to ready
        Mr = box.matrix(place, yaw_end)
        rel = self._socket_world(Mr, socks)
        if t < T["end"]:
            u = C.smooth((t - T["release"]) / (T["end"] - T["release"]))
            trunk = tuple(lerp(a, b, u) for a, b in zip(place_trunk, ready))
            lifted = {sd: (p + UP * 0.06 * min(u * 3, 1), R) for sd, (p, R) in rel.items()}
            return trunk, ("unblend", u, lifted), place + UP * 0.05
        nxt = next((q for q in w.picks if q.t["reach"] > t), None)
        tgt = nxt.box.pos + UP * 0.2 if nxt else self._idle_target(w)
        if pk.pause > 1.0 and t > T["end"] + 0.3:  # a longer pause: glance down the line
            tgt = self._glance_target(w)
        return ready, None, tgt

    def _idle_target(self, w):
        return Vector((X_FACE, w.pos.y, 1.2))

    def _glance_target(self, w):
        return Vector((-2.0, w.dock["cy"], 1.0))

    def _prev_trunk(self, w, pk):
        i = w.picks.index(pk)
        if i == 0:
            return (0.0, 0.08, 0.0)
        q = w.picks[i - 1]
        box = q.box
        grip_h = box.pos.z + box.dims[2] * 0.65
        st = self._trunk_for(w, box.pos, grip_h)
        return (st[0] * 0.45, 0.08, 0.0)

    def _toward_local(self, w, box):
        d = (w.pos - box.pos)
        d.z = 0
        d.normalize()
        Rinv = Matrix.Rotation(-box.yaw, 3, "Z")
        v = Rinv @ d
        return Vector((v.x, v.y, 0)).normalized()

    @staticmethod
    def _socket_world(M, socks):
        R3 = M.to_3x3()
        return {sd: (M @ p, R3 @ R) for sd, (p, R) in socks.items()}

    # ------------------------------------------------------------------------------------------------ build
    def build(self, scene, coll, frames, make_parcel_mesh):
        rep = {"walls": {}, "workers": {}, "schedule": {}}
        for pk in self.picks:
            if pk.parcel is not None:
                rep["schedule"].setdefault(pk.worker.dock.get("belt", "-"), []).append(
                    (pk.worker.name[-1], pk.parcel.k, round(pk.t_rel, 2), round(pk.s, 2), round(max(pk.box.dims[:2]) / 2, 2)))
        # 1. walls: every carton not picked during the window (and not gone) is static
        wall_coll = bpy.data.collections.get("TruckWalls") or bpy.data.collections.new("TruckWalls")
        if wall_coll.name not in scene.collection.children:
            scene.collection.children.link(wall_coll)
        for door, (front, back) in self.walls.items():
            static = [b for b in front if b.pick is None]  # picked cartons are flow parcels (or gone)
            n = make_parcel_mesh(f"truck_wall_{door}", static, wall_coll)  # face: each uniquely labelled
            nb = fill_mesh(f"truck_fill_{door}", back, wall_coll)  # behind the face: plain cartons, never seen
            rep["walls"][door] = {"face_cartons": n, "fill_cartons": nb,
                                  "picked_in_window": sum(1 for b in front if b.pick and b.pick.parcel is not None)}
        self.animate(scene, coll, frames, rep)
        return rep

    def animate(self, scene, coll, frames, rep, role="dock"):
        """Every worker of this station: per-frame trunk / hands / look from the cycle, pivot steps, solve, bake,
        contact check against the parcel it holds."""
        for w in self.workers:
            av, vest, hat = w.avatar
            st = dict(role=role, avatar=av, vest=vest, hat=hat)
            wk = C.Worker(scene, coll, st, w.name, w.pos, w.heading, floor_z=0.0, hat_colour=w.k % 4,
                          clip_offset=w.k * 23)
            wk.rig()
            for f in frames:
                t = (f - self.F0) * self.DT
                trunk, hands, look = self._worker_state(w, wk, t)
                wk.set_trunk(f, *trunk)
                ready = wk.neutral_hands(f, "ready")
                if hands is None:
                    tgt = ready
                elif hands[0] == "grip":
                    tgt = hands[1]
                else:
                    kind, u, sock = hands
                    if kind == "unblend":
                        u = 1 - u
                    tgt = {}
                    for sd in ("L", "R"):
                        p0, R0 = ready[sd]
                        p1, R1 = sock[sd]
                        mid_lift = UP * 0.06 * math.sin(math.pi * u)
                        q = R0.to_quaternion().slerp(R1.to_quaternion(), u)
                        tgt[sd] = (p0.lerp(p1, u) + mid_lift, q.to_matrix())
                wk.set_hands(f, tgt)
                wk.set_look(f, look)
            wk.auto_steps(frames)
            wk.apply(frames)
            # hats / devices: fitted in rest pose and bone-bound (pose independent)
            if P._pending_props.get(w.name):
                scene.frame_set(1)
                P._fit_props(scene, wk.arm, wk.body, P._templates[av], w.heading, P._pending_props.pop(w.name))
            # contact error while gripping (before bake: with live constraints)
            err = []
            for pk in w.picks:
                if pk.parcel is None:
                    continue
                for f in range(max(self.F0, int(pk.t["settle"] / self.DT) + self.F0 + 1),
                               min(self.F1, pk.f_rel - 1) + 1, 3):
                    t = (f - self.F0) * self.DT
                    scene.frame_set(f)
                    pose = self.carton_pose(pk, t)
                    if pose is None:
                        continue
                    socks = C.box_sockets(pk.box.dims, self._toward_local(w, pk.box))
                    sw = self._socket_world(pk.box.matrix(*pose), socks)
                    for sd in ("L", "R"):
                        err.append((wk.palm_world(sd) - sw[sd][0]).length)
            wk.bake(frames)
            phase_def = {}
            for f, bone, cm in wk.deficits:
                t = (f - self.F0) * self.DT
                ph = "idle"
                for pk in w.picks:
                    if pk.t["reach"] <= t <= pk.t["end"]:
                        ph = next(k for k in ("end", "release", "place", "turn", "hold", "pull", "settle", "reach")
                                  if t >= pk.t[k])
                        ph += f"@{pk.box.pos.z + pk.box.dims[2] * 0.65:.2f}m"
                        break
                key = ("leg " if "Foot" in bone else "arm ") + ph.split("@")[0]
                d = phase_def.setdefault(key, [0, 0.0, set()])
                d[0] += 1
                d[1] = max(d[1], cm)
                if "@" in ph:
                    d[2].add(ph.split("@")[1])
            rep.setdefault("deficits", {})[w.name] = {k: [v[0], v[1], sorted(v[2])] for k, v in phase_def.items()}
            rep.setdefault("adapt", {})[w.name] = wk.adapt
            rep["workers"][w.name] = dict(avatar=av, picks_in_window=sum(1 for pk in w.picks if pk.parcel is not None),
                                          contact_err_cm_max=round(max(err) * 100, 2) if err else None,
                                          contact_err_cm_p95=round(sorted(err)[int(len(err) * 0.95)] * 100, 2)
                                          if err else None,
                                          heading_deg=round(math.degrees(w.heading)), at=[round(w.pos.x, 2),
                                                                                         round(w.pos.y, 2)],
                                          pivot_steps=len(wk.steps))


# ==================================================================================================== induction
FEED_END_X, IND_Y, FEED_Y = 9.2, 9.5, 11.1
INDUCTORS = [  # (x, (avatar, vest, hat), pick band in x on the feed queue, place x on the induction belt)
    (8.55, ("Male_Adult_04", "orange", None), (8.05, 9.25), 8.75),
    (7.25, ("Female_Adult_04", None, "cap"), (6.7, 8.05), 7.45)]


class IndWorker:
    def __init__(self, k, x, avatar, band, place_x):
        self.k, self.avatar, self.band, self.place_x = k, avatar, band, place_x
        self.pos = Vector((x, (IND_Y + FEED_Y) / 2, 0.0))
        self.heading = 0.0  # faces down the line: feed queue on the left, induction belt on the right
        self.picks = []
        self.dock = {"cy": IND_Y, "belt": "induction"}
        self.name = f"worker_induct_{k + 1}"
        self.state, self.cur, self.free_at = "idle", None, -1e9


class Inductors(Docks):
    """Two inductors between the accumulation (feed) belt and the induction belt, run as agents INSIDE the flow
    simulation (pre-roll included, so the hub's steady state is the workers' real throughput). Each: picks the
    most downstream STOPPED parcel in its band of the feed queue (it then acts as a zone stop), lifts it, checks
    the label (0.3-0.5 s, label up: the tunnel reads from above), waits at the chest for a singulation gap
    (>= 0.3 m) on the induction belt, turns through the front and sets it down. ~3-4 s per parcel."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.rnd = random.Random(ctx["seed"] + 303)
        self.DT, self.F0, self.F1 = ctx["DT"], ctx["F0"], ctx["F1"]
        self.T_END = (self.F1 - self.F0) * self.DT
        self.B = ctx["B"]
        self.workers = [IndWorker(k, x, av, band, px) for k, (x, av, band, px) in enumerate(INDUCTORS)]
        self.picks = []
        self.planned = []  # (t_release, s_place, half) on the induction belt
        self.now = 0.0

    def _idle_target(self, w):
        return Vector((w.pos.x + 0.3, FEED_Y, 1.05))

    def _glance_target(self, w):
        return Vector((w.pos.x + 4.0, IND_Y, 1.1))

    def _gap_clear(self, t_rel, s_place, half, gap=0.3):
        ind = self.B["induction"]
        for q in ind.items:  # parcels already on the belt, where they will be at t_rel (it runs freely here)
            pred = q.s + ind.speed * max(t_rel - self.now, 0.0)
            if abs(pred - s_place) < q.half + half + gap:
                return False
        for (tr, sp, hh) in self.planned:  # the other inductor's parcel, set down before or after ours
            pred = sp + ind.speed * (t_rel - tr)
            if abs(pred - s_place) < hh + half + gap:
                return False
        return True

    def step(self, t, stopped):
        """One simulation step (after the belts moved). stopped = parcels on the feed belt that did not move."""
        self.now = t
        feed, ind = self.B["feed"], self.B["induction"]
        rnd = self.rnd
        for w in self.workers:
            pk = w.cur
            if w.state == "idle" and t >= w.free_at:
                cands = [p for p in stopped if not getattr(p, "frozen", False)
                         and w.band[0] <= feed.at(p.s)[0].x <= w.band[1]]
                if not cands:
                    continue
                p = max(cands, key=lambda q: q.s)
                p.frozen = True
                pos, byaw = feed.at(p.s)
                box = Box(pos.x, pos.y, pos.z, tuple(p.dims), byaw + p.yaw_off)
                pk = Pick(box, w)
                pk.parcel = p
                box.pick = pk
                T_reach = rnd.uniform(0.55, 0.85)
                T_settle = rnd.uniform(0.1, 0.16)
                T_pull = rnd.uniform(0.25, 0.35)
                pk.T_label = rnd.uniform(0.3, 0.5)
                pk.T_turn = rnd.uniform(0.6, 0.85)
                pk.T_place = rnd.uniform(0.22, 0.3)
                pk.T_ret = rnd.uniform(0.3, 0.45)
                pk.t = dict(reach=t, settle=t + T_reach, pull=t + T_reach + T_settle,
                            hold=t + T_reach + T_settle + T_pull)
                yaw_end = (0.0 if p.dims[0] >= p.dims[1] else math.pi / 2) + rnd.uniform(-0.12, 0.12)
                s_place = w.place_x - ind.pts[0].x
                ppos = ind.at(s_place)[0]
                pk.place = (Vector((ppos.x, IND_Y, ppos.z)), yaw_end)
                pk.s = s_place
                w.cur, w.state = pk, "reach"
                continue
            if pk is None:
                continue
            if w.state == "reach" and t >= pk.t["pull"]:  # grabbed: off the feed belt, in the hands
                if pk.parcel in feed.items:
                    feed.items.remove(pk.parcel)
                pk.parcel.state, pk.parcel.belt = "held", None
                w.state = "hold"
            if w.state == "hold" and t >= pk.t["hold"] + pk.T_label:
                t_rel = t + pk.T_turn + pk.T_place
                f_rel = self.F0 + math.ceil(t_rel / self.DT - 1e-6)
                t_rel = (f_rel - self.F0) * self.DT
                half = max(pk.parcel.dims[:2]) / 2
                if self._gap_clear(t_rel, pk.s, half):
                    pk.t.update(turn=t_rel - pk.T_turn - pk.T_place, place=t_rel - pk.T_place, release=t_rel,
                                end=t_rel + pk.T_ret)
                    pk.t_rel, pk.f_rel = t_rel, f_rel
                    self.planned.append((t_rel, pk.s, half))
                    w.state = "turn"
            if w.state == "turn" and t >= pk.t["release"] - 1e-6:
                p = pk.parcel
                p.yaw_off = pk.place[1]
                p.belt, p.s, p.state, p.frozen = "induction", max(pk.s - ind.speed * self.DT, 0.0), "belt", False
                ind.items.append(p)
                pk.pause = min(rnd.expovariate(1 / 0.35), 1.2) + (rnd.uniform(1.0, 2.2) if rnd.random() < 0.1 else 0)
                w.picks.append(pk)
                self.picks.append(pk)
                w.free_at = pk.t["end"] + pk.pause
                w.cur, w.state = None, "idle"
        self.planned = [x for x in self.planned if x[0] > t - 5.0]

    def finish(self):
        """End of the simulation: a parcel still in the hands at frame F1 is kept as a held pick."""
        for w in self.workers:
            pk = w.cur
            if pk is not None and w.state in ("hold", "turn"):
                T = pk.t
                if "turn" not in T:  # still holding / label check: its set-down falls after the window
                    T.update(turn=self.T_END + 5, place=self.T_END + 6, release=self.T_END + 6.3,
                             end=self.T_END + 6.6)
                    pk.t_rel, pk.f_rel = T["release"], self.F1 + 70
                pk.pause = 0.0
                w.picks.append(pk)
                self.picks.append(pk)
                pk.parcel.state = "held"
            elif pk is not None and w.state == "reach":  # reaching at the end: the parcel stays on the queue
                pk.parcel.frozen = False
        for w in self.workers:  # cycles that ended before frame 1 don't need animating
            w.picks = [pk for pk in w.picks if pk.t["end"] + pk.pause > -0.5]
        self.picks = [pk for pk in self.picks if pk.t["end"] + pk.pause > -0.5]

    def held_tracks(self):
        """{Parcel: {frame: (pos, yaw)}} for the frames each parcel is in an inductor's hands."""
        out = {}
        for pk in self.picks:
            tr = {}
            for f in range(self.F0, self.F1 + 1):
                t = (f - self.F0) * self.DT
                if pk.t["pull"] <= t < pk.t["release"]:
                    pose = self.carton_pose(pk, t)
                    if pose is not None:
                        tr[f] = pose
            out[pk.parcel] = tr
        return out

    def build(self, scene, coll, frames):
        rep = {"workers": {}, "cycles_in_window": sum(1 for pk in self.picks if pk.t["release"] >= 0)}
        self.animate(scene, coll, frames, rep, role="induction")
        return rep
