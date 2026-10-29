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
        for w in self.workers:
            w.slots = self._slots(w)
            w.state, w.cur, w.start = "idle", None, -self.rnd.uniform(0.4, 2.3)  # mid-cycle at frame 1
            w.free_at = w.start
        self.start_t = min(w.start for w in self.workers)
        self.lock = {d["belt"]: -1e9 for d in DOCKS}  # one unloader over the nose at a time

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

    def _nose_clear(self, bn, s_place, half):
        """Nothing on the boom from its start to just past where this carton goes (a stalled boom keeps it busy)."""
        return all(q.s - q.half > s_place + half + 0.12 for q in self.B[bn].items)

    def step(self, t):
        """One simulation step (called after the belts moved). The unloaders as agents: a carton is only set down
        when the nose is clear and the other unloader isn't over it; otherwise it is held at the chest."""
        rnd = self.rnd
        for w in self.workers:
            bn = w.dock["belt"]
            belt = self.B[bn]
            pk = w.cur
            if w.state == "idle":
                if t < w.free_at or not w.slots or t > self.T_END + 1.0:
                    continue
                box = w.slots.pop(0)
                pk = Pick(box, w)
                w_, d_, h_ = box.dims
                low = box.pos.z + h_ * 0.65 < 0.8
                T_reach = rnd.uniform(1.0, 1.35) + (0.4 if low else 0.0)  # real unload: 4-6 s per carton
                T_settle = rnd.uniform(0.14, 0.22)
                T_pull = rnd.uniform(0.35, 0.5) + (0.2 if low else 0.0)
                pk.T_turn = rnd.uniform(0.9, 1.2) + (0.2 if low else 0.0)
                pk.T_place = rnd.uniform(0.3, 0.4)
                pk.T_ret = rnd.uniform(0.45, 0.6)
                pk.t = dict(reach=t, settle=t + T_reach, pull=t + T_reach + T_settle,
                            hold=t + T_reach + T_settle + T_pull)
                yaw_end = box.yaw + self._turn_angle(w, box)
                hx = abs(math.cos(yaw_end)) * w_ / 2 + abs(math.sin(yaw_end)) * d_ / 2
                x_c = max(PLACE_X + rnd.uniform(-0.04, 0.04), BELT_START_X + hx + 0.01)
                pk.s = x_c - BELT_START_X
                pos = belt.at(pk.s)[0]
                pk.place = (Vector((pos.x, w.dock["cy"], pos.z)), yaw_end)
                pk.half = max(w_, d_) / 2
                Parcel = self.ctx["Parcel"]
                prc = Parcel(self.ctx["next_k"]())
                prc.kind, prc.dims, prc.body = "box", tuple(box.dims), ("box_white" if rnd.random() < 0.12 else "box")
                prc.meta.update(kind="box", dims_m=list(prc.dims), body=prc.body)
                prc.half = pk.half
                prc.yaw_off = yaw_end
                prc.station = pk
                prc.state = "held"
                pk.parcel = prc
                box.pick = pk
                w.cur, w.state = pk, "reach"
                continue
            if w.state == "reach" and t >= pk.t["hold"]:
                w.state = "hold"
            if w.state == "hold" and t >= self.lock[bn] and self._nose_clear(bn, pk.s, pk.half):
                rel = t + pk.T_turn + pk.T_place
                f_rel = self.F0 + math.ceil(rel / self.DT - 1e-6)
                rel = (f_rel - self.F0) * self.DT
                ts = rel - pk.T_turn - pk.T_place
                pk.t.update(turn=ts, place=ts + pk.T_turn, release=rel, end=rel + pk.T_ret)
                pk.t_rel, pk.f_rel = rel, f_rel
                self.lock[bn] = rel + 0.25
                w.state = "turn"
            if w.state == "turn" and t >= pk.t["release"] - 1e-6:
                prc = pk.parcel
                prc.belt, prc.s, prc.state = bn, pk.s, "belt"  # exactly where the hands set it down
                belt.items.append(prc)
                self.ctx["parcels"].append(prc)
                pk.pause = min(rnd.expovariate(1 / 0.8), 2.2)
                if rnd.random() < 0.12:
                    pause_extra = rnd.uniform(1.2, 2.4)  # look down the boom / straighten up / wipe hands
                    pk.pause += pause_extra
                w.picks.append(pk)
                self.picks.append(pk)
                w.free_at = pk.t["end"] + pk.pause
                w.cur, w.state = None, "idle"

    def finish(self):
        """End of the simulation: a carton still being reached for / held keeps its pose (set-down after F1)."""
        for w in self.workers:
            pk = w.cur
            if pk is None:
                continue
            T = pk.t
            if "turn" not in T:
                base = max(self.T_END + 3.0, T["hold"] + 0.5)
                T.update(turn=base, place=base + 1.0, release=base + 1.3, end=base + 1.8)
                pk.t_rel, pk.f_rel = T["release"], self.F0 + int(T["release"] / self.DT) + 1
            pk.pause = 0.0
            w.picks.append(pk)
            self.picks.append(pk)
            pk.parcel.state = "held"
        for w in self.workers:
            w.picks.sort(key=lambda q: q.t["reach"])

    def _turn_angle(self, w, box):
        """How far the carton turns about the vertical while carried (= trunk turn from wall to boom)."""
        a0 = math.atan2(box.pos.y - w.pos.y, box.pos.x - w.pos.x)
        a1 = math.atan2(w.dock["cy"] - w.pos.y, PLACE_X - w.pos.x)
        return (a1 - a0 + math.pi) % (2 * math.pi) - math.pi

    def preroll_rate(self, bn):
        """Expected cartons/s at this boom from its unloaders (pre-roll spawns: the same steady state)."""
        n = sum(1 for w in self.workers if w.dock["belt"] == bn)
        return n / 5.0

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
            r = lerp(r0, r1, u)
            r += (0.42 - r) * 0.8 * math.sin(math.pi * u)  # carried in close to the body mid-turn
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
                fingers = None
                if hands is None:
                    tgt = ready
                elif hands[0] == "grip":
                    tgt = hands[1]
                    fingers = "flat"
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
                    fingers = "flat" if u > 0.6 else None
                wk.set_hands(f, tgt, fingers=fingers)
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
FEED_END_X, IND_Y, FEED_Y = 9.2, 9.5, 10.85
OP_Y = 10.17  # the operators' aisle between the belts: 0.55 m (belt edges at 9.9 and 10.45)
FEED_LAT, IND_LAT = -0.15, 0.15  # parcels ride the operator-side half: side guide on the feed; set down near side
INDUCTORS = [  # (x, (avatar, vest, hat), pick band in x on the feed queue, place x on the induction belt)
    (8.65, ("Male_Adult_04", "orange", None), (8.2, 9.25), 8.8),
    (7.55, ("Female_Adult_04", None, "cap"), (7.1, 8.2), 7.7),
    (6.45, ("Male_Adult_09", "lime", None), (6.0, 7.1), 6.6)]


class IndWorker:
    def __init__(self, k, x, avatar, band, place_x):
        self.k, self.avatar, self.band, self.place_x = k, avatar, band, place_x
        self.pos = Vector((x, OP_Y, 0.0))
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
        return Vector((w.pos.x + 0.3, FEED_Y + FEED_LAT, 1.05))

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
                pos = pos + Vector((-math.sin(byaw), math.cos(byaw), 0.0)) * getattr(p, "lat", 0.0)
                box = Box(pos.x, pos.y, pos.z, tuple(p.dims), byaw + p.yaw_off)
                pk = Pick(box, w)
                pk.parcel = p
                box.pick = pk
                T_reach = rnd.uniform(0.55, 0.85)
                T_settle = rnd.uniform(0.1, 0.16)
                T_pull = rnd.uniform(0.25, 0.35)
                pk.T_label = rnd.uniform(0.3, 0.5)
                pk.T_turn = rnd.uniform(0.9, 1.15)  # a half turn with a step, ~1 s
                pk.T_place = rnd.uniform(0.22, 0.3)
                pk.T_ret = rnd.uniform(0.3, 0.45)
                pk.t = dict(reach=t, settle=t + T_reach, pull=t + T_reach + T_settle,
                            hold=t + T_reach + T_settle + T_pull)
                yaw_end = (0.0 if p.dims[0] >= p.dims[1] else math.pi / 2) + rnd.uniform(-0.12, 0.12)
                s_place = w.place_x - ind.pts[0].x
                ppos = ind.at(s_place)[0]
                lat = min(0.21, 0.37 - max(p.dims[:2]) / 2)  # as near the operator as the belt edge allows
                pk.lat = lat
                pk.place = (Vector((ppos.x, IND_Y + lat, ppos.z)), yaw_end)
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
                p.belt, p.s, p.state, p.frozen = "induction", pk.s, "belt", False  # exactly where it was set down
                p.lat = pk.lat
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


# ==================================================================================================== roll cages
CAGE_W, CAGE_D = 0.72, 0.80
HANDLE_Z = 1.0  # HSE: roll-cage handles ~1 m; pushed (never pulled), at walking pace
BEHIND = CAGE_D / 2 + 0.42  # worker's root behind the cage centre while pushing
PUSH_RATE = 0.9  # ~0.9 m/s: walking pace (HSE); the walk clip is slowed with it (no foot sliding)
# plan steps: ("push", cage_name, bay_to_clear, cage centre path, earliest start s, loaded) | ("walk", path) | ("stand",)
PUSHERS = [
    dict(name="worker_cage_1", avatar=("Male_Adult_12", "yellow", "cap"), start=1.0,
         plan=[("push", "out_D08", "S14", [(34.2, 30.6), (34.2, 32.4), (33.05, 33.0), (33.05, 38.4)], True),
               ("walk", [(33.05, 37.58), (33.05, 34.0), (33.3, 32.75), (36.95, 32.6)]),
               ("stand",)]),
    dict(name="worker_cage_2", avatar=("Male_Adult_04", None, None), start=-5.0,
         plan=[("push", "out_D11", "S17", [(42.3, 30.6), (42.3, 32.4), (45.05, 33.0), (45.05, 38.4)], True),
               ("walk", [(45.05, 37.58), (43.0, 38.15), (41.05, 37.82)]),
               ("push", "empty_back", "S19", [(41.05, 37.0), (41.05, 32.75), (47.7, 32.75), (47.7, 30.8)], False),
               ("stand",)])]


def yaw_vec3(h):
    return Vector((math.cos(h), math.sin(h), 0.0))


def _lin(ob):
    ad = ob.animation_data
    if ad and ad.action:
        for bag, fcs in P._channelbag_fcurves(ad.action):
            for fc in fcs:
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"


def sack_mesh(rnd, length=0.62, width=0.42, height=0.24, tied=False):
    """A full woven sack lying flat (or standing tied): a squashed, lumpy pillow with a gathered neck at one end.
    Material: the hub's woven sack (white / blue / grey)."""
    me = bpy.data.meshes.new("sack_lying")
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=0.5)
    seed = rnd.random() * 100
    for v in bm.verts:
        x, y, z = v.co
        lump = 1.0 + 0.07 * math.sin(7 * x + seed) * math.sin(5 * y + seed * 0.7)
        neck = 1.0 - 0.55 * max(0.0, x - 0.3) / 0.2  # the gathered (tied) end narrows
        v.co = Vector((x * length, y * width * neck * lump, (z + 0.5) * height * (0.85 + 0.15 * neck) * lump))
        if v.co.z < 0.02:
            v.co.z *= 0.3  # sits flat
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    me.materials.append(bpy.data.materials.get(rnd.choice(["woven_sack", "woven_sack", "woven_sack_blue",
                                                             "woven_sack_grey"])))
    return me


def _cage_parts(name, coll, rnd, loaded):
    """A roll cage that can roll: the shared cage mesh without its castor wheels + 4 wheel objects (+ 2 sacks)."""
    src = bpy.data.meshes.get("roll_cage")
    me = src.copy()
    me.name = f"{name}_body"
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index == 1], context="FACES")
    bm.to_mesh(me)
    bm.free()
    cage = bpy.data.objects.new(name, me)
    coll.objects.link(cage)
    coat = rnd.choice([None, "cage_red", "cage_yellow"])
    if coat and bpy.data.materials.get(coat):
        cage.material_slots[0].link = "OBJECT"
        cage.material_slots[0].material = bpy.data.materials[coat]
    wm = bpy.data.meshes.new(f"{name}_wheel")
    wb = bmesh.new()
    bmesh.ops.create_cone(wb, cap_ends=True, segments=12, radius1=0.055, radius2=0.055, depth=0.035,
                          matrix=Matrix.Rotation(math.pi / 2, 4, "Y"))
    wb.to_mesh(wm)
    wb.free()
    blk = me.materials[1] if len(me.materials) > 1 else None
    wm.materials.append(blk)
    wheels = []
    for x, y in ((-0.30, -0.34), (0.30, -0.34), (0.30, 0.34), (-0.30, 0.34)):
        w = bpy.data.objects.new(f"{name}_wheel", wm)
        coll.objects.link(w)
        w.parent = cage
        w.location = (x, y, 0.055)
        wheels.append(w)
    z = 0.17
    for k in range(2 if loaded else 0):
        sk = bpy.data.objects.new(f"{name}_sack{k}", sack_mesh(rnd))
        coll.objects.link(sk)
        sk.parent = cage
        sk.location = (rnd.uniform(-0.04, 0.04), rnd.uniform(-0.04, 0.04), z)
        sk.rotation_euler = (rnd.uniform(-0.12, 0.12), rnd.uniform(-0.12, 0.12), math.pi / 2 + rnd.uniform(-0.1, 0.1))
        z += rnd.uniform(0.2, 0.25)
    return cage, wheels


def _clear_bay(scene, spec, bay_id):
    """Empty a staging bay for a rolling cage: remove its parked cage (gate / sacks / tag) and any loose parcels of
    that cage from the merged cage-load mesh."""
    gone = []
    for o in list(scene.objects):
        if o.name == f"cage_{bay_id}" or o.name.startswith(f"cage_{bay_id}_"):
            gone.append(o.name)
            bpy.data.objects.remove(o, do_unlink=True)
    bay = next((b for b in spec["fixtures"]["cage_bays"] if b["id"] == bay_id), None)
    for mname in ("cage_loads_merged", "parcels_static_merged"):
        ml = scene.objects.get(mname)
        if not (bay and ml):
            continue
        x0, y0 = bay["sw_corner_m"]
        x1, y1 = x0 + bay["size_m"], y0 + bay["size_m"]
        bm = bmesh.new()
        bm.from_mesh(ml.data)
        mw = ml.matrix_world
        dead = [v for v in bm.verts if x0 <= (mw @ v.co).x <= x1 and y0 <= (mw @ v.co).y <= y1
                and (mw @ v.co).z > 0.12]  # above the floor marks: the cage's contents only
        if dead:
            bmesh.ops.delete(bm, geom=dead, context="VERTS")
            bm.to_mesh(ml.data)
            gone.append(f"{mname}:{len(dead)} verts")
        bm.free()
    return gone


class CagePushers:
    """Roll-cage pushers: take hold of a cage's back posts (~1 s), push it along the walkway path at walking pace
    (leaning into the start, upright once rolling, bracing to stop), park it, let go, walk on."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.DT, self.F0, self.F1 = ctx["DT"], ctx["F0"], ctx["F1"]
        self.rnd = random.Random(ctx["seed"] + 505)

    @staticmethod
    def _handles(c, r):
        """Palm contact + palm frame on the two back posts (local (+-0.36, +0.4)) at handle height."""
        out = {}
        R = Matrix.Rotation(r, 3, "Z")
        fwd = R @ Vector((0, -1, 0))
        for sd, lx in (("L", 0.36), ("R", -0.36)):  # pushing toward local -y: local +x is the pusher's LEFT
            post = c + R @ Vector((lx, 0.40, 0.0))
            p = Vector((post.x, post.y, HANDLE_Z)) - fwd * 0.03
            inward = c - post
            inward.z = 0
            inward.normalize()
            out[sd] = (p, C.frame_from(inward * 0.8 + fwd * 0.3 - UP * 0.2, fwd))
        return out

    def build(self, scene, coll, frames, spec):
        frames = list(frames)
        rep = {}
        fps = int(round(1 / self.DT))
        for k, ps in enumerate(PUSHERS):
            av, vest, hat = ps["avatar"]
            plan = ps["plan"]
            first = plan[0]
            p0, p1 = Vector((*first[3][0], 0)), Vector((*first[3][1], 0))
            h0 = math.atan2(p1.y - p0.y, p1.x - p0.x)
            start = p0 - yaw_vec3(h0) * BEHIND
            st = dict(role="cages", avatar=av, vest=vest, hat=hat)
            wk = C.Worker(scene, coll, st, ps["name"], start, h0, hat_colour=(k + 2) % 4, clip_offset=17 + k * 31)
            wk.rig()
            gender = "f" if av.startswith("Female") else "m"
            wact = P._retarget(f"{gender}_walk_neutral_01", P._clip(scene, gender, "walk_neutral_01"), av)
            v = float(wact.get("speed", -1.0))
            v = v if v > 0.5 else 1.25

            def frames_for(pts, rate):
                tot = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
                return max(2, int(round(tot / (v * rate) * fps)))

            # timeline (frames): grab 1 s -> push leg -> let go 1.3 s -> walk leg -> ...
            f = self.F0 + int(round(ps["start"] * fps))
            legs, seq, cages = [], [], {}
            for step in plan:
                if step[0] == "push":
                    _, cname, bay, pts, loaded = step
                    cage, wheels = _cage_parts(f"cage_rolling_{cname}", coll, self.rnd, loaded)
                    cages[cname] = (cage, wheels, _clear_bay(scene, spec, bay))
                    wpts = []
                    for i, q in enumerate(pts):  # the worker's path: BEHIND the cage centre along each segment
                        a, b = (pts[i], pts[i + 1]) if i + 1 < len(pts) else (pts[i - 1], pts[i])
                        wpts.append(tuple((Vector((*q, 0)) - yaw_vec3(math.atan2(b[1] - a[1], b[0] - a[0])) * BEHIND).xy))
                    f_grab = f
                    f += fps  # 1 s to take hold
                    n = frames_for(wpts, PUSH_RATE)
                    legs.append((f, wpts, PUSH_RATE))
                    seq.append(("push", cname, f_grab, f, f + n))
                    f += n + int(1.3 * fps)  # park, let go, straighten
                elif step[0] == "walk":
                    pts = step[1]
                    n = frames_for(pts, 1.0)
                    legs.append((f, pts, 1.0))
                    seq.append(("walk", None, f, f, f + n))
                    f += n + int(0.4 * fps)
            spans = wk.walk(legs, frames)
            # cage poses: still before its push, carried by the worker during it, parked after
            cage_pose = {}
            for kind, cname, fg, f0, f1 in seq:
                if kind != "push":
                    continue
                cage, wheels, _ = cages[cname]
                dist, prev = 0.0, None
                for g in frames:
                    gg = min(max(g, f0), f1)
                    loc, h = wk.obj.get(gg, (wk.loc0, wk.heading0))
                    c = Vector((loc.x, loc.y, 0.0)) + yaw_vec3(h) * BEHIND
                    r = h + math.pi / 2  # cage local -y (open front) leads
                    if prev is not None:
                        dist += (c - prev).length
                    prev = c
                    cage.location, cage.rotation_euler = c, (0, 0, r)
                    cage.keyframe_insert("location", frame=g)
                    cage.keyframe_insert("rotation_euler", frame=g)
                    for wobj in wheels:
                        wobj.rotation_euler = (dist / 0.055, 0, 0)
                        wobj.keyframe_insert("rotation_euler", index=0, frame=g)
                    cage_pose[(cname, g)] = (c, r)
                for o in [cage] + wheels:
                    _lin(o)
            attached = {}
            for g in frames:
                hands, flex, look = None, 0.04, None
                for kind, cname, fg, f0, f1 in seq:
                    if kind != "push" or not (fg <= g <= f1 + 10):
                        continue
                    c, r = cage_pose[(cname, g)]
                    hd = self._handles(c, r)
                    if g < f0:  # reaching for the handles
                        u = C.smooth((g - fg) / max(f0 - fg, 1))
                        hands, flex = ("blend", u, hd), 0.04 + 0.12 * u
                    elif g <= f1:  # lean into the start, upright once rolling, brace to stop
                        hands = ("grip", hd)
                        attached[g] = cname
                        flex = 0.12 + 0.14 * max(0.0, 1 - (g - f0) / 10) + 0.06 * max(0.0, 1 - (f1 - g) / 6)
                    else:  # let go, straighten
                        u = C.smooth((g - f1) / 10)
                        hands, flex = ("unblend", u, hd), 0.12 * (1 - u)
                    look = c + yaw_vec3(r - math.pi / 2) * 2.5 + UP * 1.0
                wk.set_trunk(g, 0.0, flex, 0.0)
                if hands is not None:  # the clip's own arms ramp onto the handles (no jump at take-hold / let-go)
                    if hands[0] == "grip":
                        wk.set_hands(g, hands[1], fingers="wrap")
                    else:
                        kind, u, sock = hands
                        wk.set_hands(g, sock, fingers="wrap", weight=(1 - u) if kind == "unblend" else u)
                if look is None:
                    loc, h = wk.obj.get(g, (wk.loc0, wk.heading0))
                    look = Vector((loc.x, loc.y, 1.5)) + yaw_vec3(h) * 3.0
                wk.set_look(g, look)
            wk.auto_steps(frames)
            wk.apply(frames)
            if P._pending_props.get(ps["name"]):
                scene.frame_set(1)
                P._fit_props(scene, wk.arm, wk.body, P._templates[av], h0, P._pending_props.pop(ps["name"]))
            err = []
            for g in frames[::3]:
                if attached.get(g):
                    scene.frame_set(g)
                    hd = self._handles(*cage_pose[(attached[g], g)])
                    err += [(wk.palm_world(sd) - hd[sd][0]).length for sd in ("L", "R")]
            rep[ps["name"]] = dict(avatar=av, legs=spans, walk_speed=round(v, 2),
                                   walk_yaw_fix_deg=round(math.degrees(getattr(wk, "walk_yaw_fix", 0.0)), 1),
                                   handle_err_cm_max=round(max(err) * 100, 2) if err else None,
                                   handle_err_cm_p95=round(sorted(err)[int(len(err) * 0.95)] * 100, 2) if err else None,
                                   cleared=[g for (_, _, cl) in cages.values() for g in cl], pivot_steps=len(wk.steps))
        return rep


# ==================================================================================================== walkers
# people crossing the hall on the painted walkways (centre lines), at the walk clip's own stride speed, now and
# then stopping to look at something; empty hands swing with the clip
WALKERS = [
    dict(name="worker_walk_1", avatar=("Female_Adult_13", "lime", None), start=-3.0,
         legs=[[(48.0, 23.8), (30.0, 23.8)], [(30.0, 23.8), (15.0, 23.8), (14.4, 24.6)]],
         stops=[(4.0, (29.3, 21.0, 0.9))]),  # W3 bagging aisle westward; a look at the reject chute
    dict(name="worker_walk_2", avatar=("Male_Adult_05", None, "cap"), start=2.0,
         legs=[[(20.0, 1.0), (44.0, 1.0)]],
         stops=[]),  # W1 south aisle eastward (toward the office)
]


class Walkers:
    def __init__(self, ctx):
        self.DT, self.F0, self.F1 = ctx["DT"], ctx["F0"], ctx["F1"]

    def build(self, scene, coll, frames):
        frames = list(frames)
        fps = int(round(1 / self.DT))
        rep = {}
        for k, ws in enumerate(WALKERS):
            av, vest, hat = ws["avatar"]
            p0, p1 = ws["legs"][0][0], ws["legs"][0][1]
            h0 = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
            wk = C.Worker(scene, coll, dict(role="walk", avatar=av, vest=vest, hat=hat), ws["name"], Vector((*p0, 0)),
                          h0, hat_colour=(k + 1) % 4, clip_offset=40 + 13 * k)
            wk.rig()
            gender = "f" if av.startswith("Female") else "m"
            wact = P._retarget(f"{gender}_walk_neutral_01", P._clip(scene, gender, "walk_neutral_01"), av)
            v = float(wact.get("speed", -1.0))
            v = v if v > 0.5 else 1.25
            f = self.F0 + int(round(ws["start"] * fps))
            legs, stops = [], []
            for i, pts in enumerate(ws["legs"]):
                legs.append((f, pts, 1.0))
                tot = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
                f += max(2, int(round(tot / v * fps)))
                if i < len(ws["stops"]):
                    dur, look = ws["stops"][i]
                    stops.append((f, f + int(dur * fps), Vector(look)))
                    f += int(dur * fps) + 1
            spans = wk.walk(legs, frames)
            for g in frames:
                wk.set_trunk(g, 0.0, 0.02, 0.0)
                loc, h = wk.obj.get(g, (wk.loc0, wk.heading0))
                look = Vector((loc.x, loc.y, 1.55)) + yaw_vec3(h) * 4.0 - UP * 0.25
                for (s0, s1, lk) in stops:
                    if s0 <= g <= s1:
                        look = lk
                wk.set_look(g, look)
            wk.auto_steps(frames)
            wk.apply(frames)
            if P._pending_props.get(ws["name"]):
                scene.frame_set(1)
                P._fit_props(scene, wk.arm, wk.body, P._templates[av], h0, P._pending_props.pop(ws["name"]))
            rep[ws["name"]] = dict(avatar=av, legs=spans, walk_speed=round(v, 2), pivot_steps=len(wk.steps))
        return rep


# ==================================================================================================== chute bagging
# Bag change (owner decision 2026-10-30: never animate tying; the full bag comes out already tied). The chute's
# stack light shows red while its bag is full; the sorter stops diverting to it (parcels recirculate) until the
# new bag hangs and the light turns green. Sequence: walk to the frame -> unclip the full bag at the rim -> lift
# it out (tied) -> carry it by the neck to the bag cage in the staging bay -> set it in -> walk back -> take the
# spare folded bag off the frame-side hook -> clip it open on the rim -> light green.
BAG_CHUTE = "C07"
BAG_X, FRAME_Y0, FRAME_Y1, RIM = 38.3, 20.6, 21.4, 0.9
BAG_CAGE_BAY = "S06"
BAG_CAGE = Vector((39.6, 27.0, 0.0))  # its open front faces the aisle (south)
BAGGER = dict(name="worker_bag_1", avatar=("Male_Adult_09", "orange", "hard"), start=-1.2,
              approach=[(34.7, 22.25), (37.2, 21.95), (38.3, 21.64)])  # 0.24 m off the frame's aisle rail


def _hanging_bag(name, full=True, rnd=None):
    """Woven sack clipped open on the frame rim: rectangular mouth at the rim, body bulging to the floor (full) or
    hanging slack (new / empty). Origin at the frame centre on the floor."""
    rnd = rnd or random.Random(7)
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    hx, hy = 0.47, 0.37
    rings = [(RIM + 0.02, 1.0), (RIM - 0.08, 1.03), (0.62, 1.06 if full else 0.92), (0.32, 1.06 if full else 0.8),
             (0.08, 0.96 if full else 0.62), (0.01 if full else 0.3, 0.8 if full else 0.45)]
    n = 24
    loops = []
    for k, (z, sc_) in enumerate(rings):
        loop = []
        for i in range(n):
            a = 2 * math.pi * i / n
            cx, cy = math.cos(a), math.sin(a)
            r = 1.0 / max(abs(cx), abs(cy)) ** 0.85  # rounded rectangle
            lump = 1.0 + (0.03 * math.sin(5 * a + k) if 0 < k < len(rings) - 1 else 0.0)
            loop.append(bm.verts.new((cx * r * hx * sc_ * lump, cy * r * hy * sc_ * lump,
                                      z + (rnd.uniform(-0.015, 0.015) if 0 < k < len(rings) - 1 else 0.0))))
        loops.append(loop)
    for la, lb in zip(loops, loops[1:]):
        for i in range(n):
            bm.faces.new((la[i], la[(i + 1) % n], lb[(i + 1) % n], lb[i]))
    bm.faces.new(list(reversed(loops[-1])))
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    me.materials.append(bpy.data.materials.get("woven_sack"))
    return me


def _tied_sack(name, rnd):
    """A full sack lifted out by its tied neck: a lumpy bag body (0.6 x 0.5 x 0.7 m) hanging from a gathered neck.
    Origin = the neck (where the hands hold it)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=18, v_segments=12, radius=0.5)
    seed = rnd.random() * 10
    for v in bm.verts:
        x, y, z = v.co
        lump = 1.0 + 0.05 * math.sin(6 * x + seed) * math.sin(4 * z + seed)
        top = max(0.0, z)  # narrows to the neck at the top
        w = (1.0 - 0.75 * top ** 2) * lump
        v.co = Vector((x * 0.6 * w, y * 0.5 * w, -0.72 + (z + 0.5) * 0.7))
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.05, radius2=0.035, depth=0.1,
                              matrix=Matrix.Translation((0, 0, -0.03)))  # gathered neck + tie
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    me.materials.append(bpy.data.materials.get("woven_sack"))
    return me


def _key_vis(ob, frames_on, frames):
    """Show the object only on frames_on (constant keys on hide_render / hide_viewport)."""
    for f in frames:
        hid = f not in frames_on
        ob.hide_render = ob.hide_viewport = hid
        ob.keyframe_insert("hide_render", frame=f)
        ob.keyframe_insert("hide_viewport", frame=f)
    ad = ob.animation_data
    if ad and ad.action:
        for bag, fcs in P._channelbag_fcurves(ad.action):
            for fc in fcs:
                for kp in fc.keyframe_points:
                    kp.interpolation = "CONSTANT"


def _cut_region(scene, names, x0, x1, y0, y1, z0=-1.0, z1=9.0):
    """Delete the vertices of merged static meshes inside a box (the bag + contents being replaced)."""
    out = {}
    for mname in names:
        ml = scene.objects.get(mname)
        if ml is None:
            continue
        bm = bmesh.new()
        bm.from_mesh(ml.data)
        mw = ml.matrix_world
        dead = [v for v in bm.verts if x0 <= (mw @ v.co).x <= x1 and y0 <= (mw @ v.co).y <= y1
                and z0 <= (mw @ v.co).z <= z1]
        if dead:
            bmesh.ops.delete(bm, geom=dead, context="VERTS")
            bm.to_mesh(ml.data)
            out[mname] = len(dead)
        bm.free()
    return out


class BagChange:
    def __init__(self, ctx):
        self.DT, self.F0, self.F1 = ctx["DT"], ctx["F0"], ctx["F1"]
        self.rnd = random.Random(ctx["seed"] + 707)
        self.fps = int(round(1 / self.DT))
        self.v = 1.01  # Rocketbox walk clip speed (measured: walk_neutral_01)
        self._plan()

    def _plan(self):
        """Times (s) of every step: fixed before the simulation, so the sorter knows when the chute is back."""
        v = self.v
        t = BAGGER["start"]
        L = lambda pts: sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
        T = {"walk_in": t}
        t += L(BAGGER["approach"]) / v
        T["arrive"] = t
        t += 0.5
        T["reach"] = t
        t += 1.2
        T["unclip"] = t
        t += 0.6
        T["lift"] = t
        t += 1.0
        # west of the XO-1 stair (its stringer stands at x 39.1 from y 19.6 to 23.2): out, up the aisle, to the cage
        self.carry_path = [(BAG_X, 21.64), (BAG_X + 0.2, 22.25), (38.75, 23.5), (BAG_CAGE.x, 26.12)]
        T["walk_cage"] = t
        t += L(self.carry_path) / (v * 0.85)
        T["at_cage"] = t
        t += 0.4
        T["place"] = t
        t += 1.4
        T["released"] = t
        t += 0.6
        self.back_path = [(BAG_CAGE.x, 26.12), (38.75, 23.5), (BAG_X - 0.45, 22.15), (BAG_X - 0.62, 21.72)]
        self.center_path = [(BAG_X - 0.62, 21.72), (BAG_X - 0.3, 21.68), (BAG_X - 0.02, 21.64)]
        T["walk_back"] = t
        t += L(self.back_path) / v
        T["at_spare"] = t
        t += 0.5
        T["take_spare"] = t
        t += 0.8
        T["step_in"] = t  # spare in hand, a step along to the middle of the frame
        t += L(self.center_path) / (v * 0.8) + 0.3
        T["to_rim"] = t
        t += 0.9
        T["clip_new"] = t
        t += 1.4
        T["ready"] = t  # light green, the sorter may divert here again
        t += 0.8
        T["done"] = t
        self.T = T

    def chute_closed(self, t):
        """Full (red) from ~40 s before the window until the new bag hangs: the sorter recirculates its parcels."""
        return -40.0 <= t < self.T["ready"]

    def build(self, scene, coll, frames, spec):
        frames = list(frames)
        self.spec = spec
        T, fps, rnd = self.T, self.fps, self.rnd
        F = lambda t: self.F0 + int(round(t * fps))
        rep = {"times": {k: round(v, 2) for k, v in T.items()}}
        # --- the chute's bag: cut the merged static one (and its contents), add our own
        rep["cut"] = _cut_region(scene, ["sacks_merged", "parcels_static_merged", "bag_contents_merged"],
                                 BAG_X - 0.56, BAG_X + 0.56, FRAME_Y0 - 0.05, FRAME_Y1 + 0.12, z1=RIM + 0.15)
        bc = bpy.data.collections.get("Bagging") or bpy.data.collections.new("Bagging")
        if bc.name not in scene.collection.children:
            scene.collection.children.link(bc)
        frame_c = Vector((BAG_X, (FRAME_Y0 + FRAME_Y1) / 2, 0.0))
        full = bpy.data.objects.new(f"bag_{BAG_CHUTE}_full", _hanging_bag(f"bag_{BAG_CHUTE}_full", True, rnd))
        new = bpy.data.objects.new(f"bag_{BAG_CHUTE}_new", _hanging_bag(f"bag_{BAG_CHUTE}_new", False, rnd))
        tied = bpy.data.objects.new(f"bag_{BAG_CHUTE}_tied", _tied_sack(f"bag_{BAG_CHUTE}_tied", rnd))
        spare = bpy.data.objects.new(f"bag_{BAG_CHUTE}_spare", sack_mesh(rnd, 0.5, 0.06, 0.4))
        for o in (full, new, tied, spare):
            bc.objects.link(o)
        full.location = new.location = frame_c
        hook = Vector((BAG_X - 0.53, FRAME_Y0 + 0.4, 0.62))  # the folded spare hangs on the frame's west side
        spare.location, spare.rotation_euler = hook, (math.pi / 2, 0, math.pi / 2)
        f_lift, f_new = F(T["lift"]), F(T["to_rim"] + 0.3)
        _key_vis(full, {f for f in frames if f < f_lift}, frames)
        _key_vis(tied, {f for f in frames if f_lift <= f}, frames)
        _key_vis(new, {f for f in frames if f >= f_new}, frames)
        _key_vis(spare, {f for f in frames if f < F(T["take_spare"]) or (F(T["take_spare"]) <= f < f_new)}, frames)
        # --- stack lights on every chute (green / amber / red); this chute red until the new bag hangs
        lights = self._stack_lights(bc, frames, F(T["ready"]))
        rep["stack_lights"] = lights
        # --- the bag cage (gate open toward the aisle), replacing the bay's parked cage
        rep["cleared"] = _clear_bay(scene, self.spec, BAG_CAGE_BAY)
        cage, wheels = _cage_parts("cage_bags_S06", bc, rnd, loaded=True)
        cage.location, cage.rotation_euler = BAG_CAGE, (0, 0, 0.0)  # local -y (open front) faces south
        # --- the bagger
        av, vest, hat = BAGGER["avatar"]
        p0, p1 = BAGGER["approach"][0], BAGGER["approach"][1]
        h0 = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        wk = C.Worker(scene, coll, dict(role="chutes", avatar=av, vest=vest, hat=hat), BAGGER["name"], Vector((*p0, 0)),
                      h0, hat_colour=1, clip_offset=55)
        wk.rig()
        legs = [(F(T["walk_in"]), BAGGER["approach"], 1.0), (F(T["walk_cage"]), self.carry_path, 0.85, 0.9),
                (F(T["walk_back"]), self.back_path, 1.0, 0.7), (F(T["step_in"]), self.center_path, 0.8, 0.5)]
        spans = wk.walk(legs, frames)
        rep["legs"] = spans
        # carried / held objects: the tied sack follows the hands' authored pose (object first, hands on it)
        rim_L = Vector((BAG_X - 0.17, FRAME_Y1 - 0.02, RIM + 0.02))  # either side of the front clip
        rim_R = Vector((BAG_X + 0.17, FRAME_Y1 - 0.02, RIM + 0.02))
        neck_rest = frame_c + Vector((0, 0.05, RIM + 0.15))  # neck of the full bag at the rim, centre
        dropped = None
        for f in frames:
            t = (f - self.F0) * self.DT
            loc, h = wk.obj.get(f, (wk.loc0, wk.heading0))
            fwd = yaw_vec3(h)
            hands, fingers, flex, yaw, look = None, None, 0.03, 0.0, Vector((loc.x, loc.y, 1.5)) + fwd * 3 - UP * 0.3
            neck = None
            if T["arrive"] <= t < T["walk_cage"]:  # at the frame, facing the bag (south)
                yaw = (-math.pi / 2 - h + math.pi) % (2 * math.pi) - math.pi
                look = neck_rest + UP * 0.1
                if t < T["unclip"]:  # reach down to the rim clips
                    u = C.smooth((t - T["reach"]) / (T["unclip"] - T["reach"])) if t > T["reach"] else 0.0
                    hands = ("blend", u, self._rim_hold(rim_L, rim_R))
                    flex = 0.1 + 0.35 * u
                elif t < T["lift"]:  # unclip
                    hands = ("grip", self._rim_hold(rim_L + UP * 0.02 * math.sin(20 * t), rim_R))
                    flex = 0.45
                else:  # lift it out by the neck (it comes out tied)
                    u = C.smooth((t - T["lift"]) / (T["walk_cage"] - T["lift"]))
                    neck = neck_rest.lerp(Vector((BAG_X, 21.55, 1.02)), u)
                    hands = ("grip", self._neck_hold(neck, -math.pi / 2))
                    fingers = None
                    flex = 0.45 - 0.33 * u
            elif T["walk_cage"] <= t < T["released"]:  # carry it, set it in the cage
                if t < T["at_cage"]:
                    neck = Vector((loc.x, loc.y, 0.98)) + fwd * 0.36
                    hands = ("grip", self._neck_hold(neck, h))
                    flex = -0.04  # leaning back a little against the load
                    look = Vector((BAG_CAGE.x, BAG_CAGE.y, 0.8))
                else:
                    u = C.smooth((t - T["place"]) / (T["released"] - T["place"])) if t > T["place"] else 0.0
                    start = Vector((loc.x, loc.y, 0.98)) + fwd * 0.36
                    into = Vector((BAG_CAGE.x, BAG_CAGE.y - 0.3, 1.05))
                    neck = start.lerp(into, u) + UP * 0.12 * math.sin(math.pi * u)
                    hands = ("grip", self._neck_hold(neck, h))
                    flex = 0.1 + 0.25 * u
                    look = into
                dropped = neck.copy()
            elif T["released"] <= t < T["walk_back"]:
                u = C.smooth((t - T["released"]) / (T["walk_back"] - T["released"]))
                hands = ("unblend", u, self._neck_hold(dropped, h))
                flex = 0.35 * (1 - u)
                look = Vector((BAG_CAGE.x, BAG_CAGE.y, 0.6))
            elif T["at_spare"] <= t < T["done"]:  # spare off the hook, clip it open on the rim
                yaw = (-math.pi / 2 - h + math.pi) % (2 * math.pi) - math.pi
                if t < T["take_spare"]:
                    look = hook
                elif t < T["step_in"]:
                    u = C.smooth((t - T["take_spare"]) / (T["step_in"] - T["take_spare"]))
                    hands = ("blend", u, self._rim_hold(hook + Vector((0.0, 0.08, 0.2)),
                                                        hook + Vector((0.12, -0.05, 0.2))))
                    flex = 0.15 * u
                    look = hook
                elif t < T["to_rim"]:  # carrying the folded bag to the middle of the frame
                    held = Vector((loc.x, loc.y, 0.98)) + yaw_vec3(-math.pi / 2) * 0.32
                    spare.location = held - UP * 0.2
                    spare.keyframe_insert("location", frame=f)
                    hands = ("grip", self._rim_hold(held + Vector((-0.06, 0, 0)), held + Vector((0.06, 0, 0))))
                    flex = 0.12
                    look = neck_rest
                elif t < T["ready"]:
                    u = C.smooth((t - T["to_rim"]) / (T["clip_new"] - T["to_rim"]))
                    hands = ("grip", self._rim_hold(rim_L.lerp(rim_L + Vector((0.1, -0.3, 0)), u * 0.0),
                                                    rim_R))
                    flex = 0.4
                    look = neck_rest
                else:
                    u = C.smooth((t - T["ready"]) / (T["done"] - T["ready"]))
                    hands = ("unblend", u, self._rim_hold(rim_L, rim_R))
                    flex = 0.4 * (1 - u)
                    look = frame_c + UP * 1.6 + Vector((0, -0.6, 0))  # a glance up at the stack light
            if t < T["step_in"] or t >= T["to_rim"]:  # the spare hangs on its hook until it is carried
                if t < T["step_in"]:
                    spare.location = hook
                    spare.keyframe_insert("location", frame=f)
            if neck is not None:
                tied.location, tied.rotation_euler = neck, (0, 0, h if t >= T["walk_cage"] else -math.pi / 2)
                tied.keyframe_insert("location", frame=f)
                tied.keyframe_insert("rotation_euler", frame=f)
            elif dropped is not None and t >= T["released"]:
                into = Vector((BAG_CAGE.x, BAG_CAGE.y - 0.08, 0.17 + 0.48 + 0.7))  # resting on the sacks inside
                tied.location = into
                tied.keyframe_insert("location", frame=f)
            elif t < T["lift"]:
                tied.location = neck_rest
                tied.keyframe_insert("location", frame=f)
            wk.set_trunk(f, yaw, flex, 0.0)
            if hands is not None:  # the clip's own arms ramp onto the hold (no jump)
                if hands[0] == "grip":
                    wk.set_hands(f, hands[1], fingers=fingers)
                else:
                    kind, u, sock = hands
                    wk.set_hands(f, sock, weight=(1 - u) if kind == "unblend" else u)
            wk.set_look(f, look)
        _lin(tied)
        wk.auto_steps(frames)
        wk.apply(frames)
        if P._pending_props.get(BAGGER["name"]):
            scene.frame_set(1)
            P._fit_props(scene, wk.arm, wk.body, P._templates[av], h0, P._pending_props.pop(BAGGER["name"]))
        rep["deficits"] = len(wk.deficits)
        ph = {}
        for f, bone, cm in wk.deficits:
            tt = (f - self.F0) * self.DT
            name = max((k for k, v in T.items() if v <= tt), key=lambda k: T[k], default="start")
            key = ("leg " if "Foot" in bone else "arm ") + name
            n_, mx = ph.get(key, (0, 0.0))
            ph[key] = (n_ + 1, max(mx, cm))
        rep["deficit_phases"] = ph
        rep["pivot_steps"] = len(wk.steps)
        return rep

    @staticmethod
    def _rim_hold(pl, pr):
        """Both hands on the rim / bag edge: palms down on it, fingers pointing away from the worker (south)."""
        Rl = C.frame_from(Vector((0, -1, -0.4)), -UP)
        return {"L": (pl, Rl), "R": (pr, Rl)}

    @staticmethod
    def _neck_hold(neck, h):
        """Both fists round the tied neck, one above the other, palms facing each other across it."""
        fwd = yaw_vec3(h)
        left = Vector((-fwd.y, fwd.x, 0))
        return {"L": (neck + left * 0.035 + UP * 0.03, C.frame_from(-UP * 0.3 + fwd, -left)),
                "R": (neck - left * 0.035 - UP * 0.02, C.frame_from(-UP * 0.3 + fwd, left))}

    def _stack_lights(self, coll, frames, f_green):
        """A 3-lamp stack light (green / amber / red) on the right side wall of every chute, near the lip."""
        mats = {k: bpy.data.materials.get(f"dock_lamp_{k}") for k in ("red", "green", "off")}
        amber_off = mats["off"]
        made = []
        for k in range(12):
            cid = f"C{k + 1:02d}"
            x = 48.6 - 1.5 * k
            base = Vector((x + 0.52, 20.55, 1.32))
            me = bpy.data.meshes.new(f"stacklight_{cid}")
            bm = bmesh.new()
            bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.012, radius2=0.012, depth=0.25,
                                  matrix=Matrix.Translation((0, 0, 0.125)))  # mast
            for i, z in enumerate((0.27, 0.35, 0.43)):  # green, amber, red lenses
                r = bmesh.ops.create_cone(bm, cap_ends=True, segments=14, radius1=0.035, radius2=0.035, depth=0.075,
                                          matrix=Matrix.Translation((0, 0, z)))
                for f in {f for v in r["verts"] for f in v.link_faces}:
                    f.material_index = i + 1
            bm.to_mesh(me)
            bm.free()
            me.materials.append(bpy.data.materials.get("steel"))
            me.materials.append(mats["green"])  # slot 1: green lens
            me.materials.append(amber_off)  # slot 2: amber lens
            me.materials.append(mats["off"])  # slot 3: red lens
            ob = bpy.data.objects.new(f"stacklight_{cid}", me)
            coll.objects.link(ob)
            ob.location = base
            if cid == BAG_CHUTE:  # red while full: a red-lit twin shown until the new bag hangs
                me2 = me.copy()
                me2.materials[1] = mats["off"]
                me2.materials[3] = mats["red"]
                ob2 = bpy.data.objects.new(f"stacklight_{cid}_full", me2)
                coll.objects.link(ob2)
                ob2.location = base
                _key_vis(ob2, {f for f in frames if f < f_green}, frames)
                _key_vis(ob, {f for f in frames if f >= f_green}, frames)
            made.append(cid)
        return made


# ==================================================================================================== bag opening
# Bench 1 (x 6.2-8.0, y 19-22, 0.9 m): an opened inbound sack lies on the bench with its parcels spilled toward
# the aisle edge. The opener stands between the bench and the collector belt (0.3 m off the belt), takes one
# parcel at a time, turns and sets it on the collector's near half into a gap. Those parcels then ride the
# collector -> feed -> induction like the docks' cartons. (Bench 2 holds the scenario-5 look-alike pair: untouched.)
OPENER = dict(name="worker_open_1", avatar=("Female_Adult_07", "lime", None), at=(5.72, 20.55), start=-0.6)
BENCH_X0, BENCH_Y0, BENCH_Y1, BENCH_Z = 6.2, 19.0, 22.0, 0.9


class BagOpener(Docks):
    def __init__(self, ctx):
        self.ctx = ctx
        self.rnd = random.Random(ctx["seed"] + 909)
        self.DT, self.F0, self.F1 = ctx["DT"], ctx["F0"], ctx["F1"]
        self.T_END = (self.F1 - self.F0) * self.DT
        self.B = ctx["B"]
        w = IndWorker(0, OPENER["at"][0], OPENER["avatar"], (0, 0), 0)
        w.pos = Vector((OPENER["at"][0], OPENER["at"][1], 0.0))
        w.heading = math.pi / 2  # faces up the line (north): bench on the right, collector on the left
        w.name = OPENER["name"]
        w.dock = {"cy": OPENER["at"][1], "belt": "collector"}
        w.free_at = OPENER["start"]
        self.workers = [w]
        self.picks = []
        self.planned = []
        self.now = 0.0
        # the spilled parcels: near the bench's aisle edge, nearest first (mailers and small boxes from a sack)
        rnd = self.rnd
        Parcel = ctx["Parcel"]
        self.pile = []
        for k in range(12):
            p = Parcel(ctx["next_k"]())
            if p.kind == "box" and max(p.dims) > 0.36:  # sack contents are small: mailers and small cartons
                p.kind, p.dims, p.body = "mailer", (0.32, 0.24, 0.04), "mailer_grey"
                p.meta.update(kind=p.kind, dims_m=list(p.dims), body=p.body)
                p.half = max(p.dims[:2]) / 2
            row, col = divmod(k, 4)
            x = BENCH_X0 + 0.16 + 0.17 * row + rnd.uniform(-0.03, 0.03)
            y = OPENER["at"][1] - 0.5 + 0.33 * col + rnd.uniform(-0.04, 0.04)
            z = BENCH_Z + (0.0 if row == 0 else 0.02 * row)
            p.state = "held"
            box = Box(x, y, z, tuple(p.dims), rnd.uniform(-0.6, 0.6) + math.pi / 2)
            self.pile.append((box, p))
        self.pile.sort(key=lambda bp: (bp[0].pos - w.pos).xy.length)
        self.sack_pos = Vector((BENCH_X0 + 0.95, OPENER["at"][1] + 0.1, BENCH_Z))

    def _idle_target(self, w):
        return Vector((BENCH_X0 + 0.4, w.pos.y, 0.95))

    def _glance_target(self, w):
        return Vector((5.0, w.pos.y - 3.0, 1.0))  # down the collector

    def _gap_clear(self, t_rel, s_place, half, gap=0.35):
        col = self.B["collector"]
        for q in col.items:  # upstream parcels arrive at the collector's speed (it runs freely here)
            pred = q.s + col.speed * max(t_rel - self.now, 0.0)
            if abs(pred - s_place) < q.half + half + gap:
                return False
        for (tr, sp, hh) in self.planned:
            if abs(sp + col.speed * (t_rel - tr) - s_place) < hh + half + gap:
                return False
        return True

    def step(self, t):
        self.now = t
        col = self.B["collector"]
        rnd = self.rnd
        w = self.workers[0]
        pk = w.cur
        if w.state == "idle":
            if t < w.free_at or not self.pile or t > self.T_END + 1.0:
                return
            box, p = self.pile.pop(0)
            pk = Pick(box, w)
            pk.parcel = p
            box.pick = pk
            T_reach = rnd.uniform(0.7, 1.0)
            T_settle = rnd.uniform(0.1, 0.16)
            T_pull = rnd.uniform(0.25, 0.35)
            pk.T_label = rnd.uniform(0.25, 0.45)  # label up for the tunnel
            pk.T_turn = rnd.uniform(0.85, 1.1)
            pk.T_place = rnd.uniform(0.22, 0.3)
            pk.T_ret = rnd.uniform(0.3, 0.45)
            pk.t = dict(reach=t, settle=t + T_reach, pull=t + T_reach + T_settle, hold=t + T_reach + T_settle + T_pull)
            pk.s = 28.0 - (w.pos.y - 0.15)  # collector runs south from y 28: set down just downstream
            lat = min(0.21, 0.37 - max(p.dims[:2]) / 2)
            pk.lat = lat
            ppos, byaw = col.at(pk.s)
            ppos = ppos + Vector((-math.sin(byaw), math.cos(byaw), 0.0)) * lat
            yaw_end = byaw + (0.0 if p.dims[0] >= p.dims[1] else math.pi / 2) + rnd.uniform(-0.12, 0.12)
            pk.place = (Vector((ppos.x, ppos.y, ppos.z)), yaw_end)
            w.cur, w.state = pk, "reach"
            return
        if w.state == "reach" and t >= pk.t["pull"]:
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
            p.yaw_off = pk.place[1] - col.at(pk.s)[1]
            p.belt, p.s, p.state, p.lat = "collector", pk.s, "belt", pk.lat
            col.items.append(p)
            self.ctx["parcels"].append(p)
            pk.pause = min(rnd.expovariate(1 / 0.45), 1.4) + (rnd.uniform(1.0, 2.0) if rnd.random() < 0.1 else 0)
            w.picks.append(pk)
            self.picks.append(pk)
            w.free_at = pk.t["end"] + pk.pause
            w.cur, w.state = None, "idle"
        self.planned = [x for x in self.planned if x[0] > t - 5.0]

    def finish(self):
        w = self.workers[0]
        pk = w.cur
        if pk is not None:
            if "turn" not in pk.t:
                base = max(self.T_END + 3.0, pk.t["hold"] + 0.5)
                pk.t.update(turn=base, place=base + 1.0, release=base + 1.3, end=base + 1.6)
                pk.t_rel, pk.f_rel = pk.t["release"], self.F0 + int(pk.t["release"] / self.DT) + 1
            pk.pause = 0.0
            w.picks.append(pk)
            self.picks.append(pk)
        w.picks.sort(key=lambda q: q.t["reach"])
        self.picks = [q for q in self.picks if q.t["end"] + q.pause > -0.5]
        w.picks = [q for q in w.picks if q.t["end"] + q.pause > -0.5]

    def pile_tracks(self):
        """{Parcel: {frame: (pos, yaw)}}: on the bench until picked, in the hands until set down."""
        out = {}
        for box, p in [(pk.box, pk.parcel) for pk in self.picks] + list(self.pile):
            pk = box.pick
            tr = {}
            for f in range(self.F0, self.F1 + 1):
                t = (f - self.F0) * self.DT
                if pk is None or t < pk.t["pull"]:
                    tr[f] = (box.pos.copy(), box.yaw)
                elif t < pk.t["release"]:
                    pose = self.carton_pose(pk, t)
                    if pose is not None:
                        tr[f] = pose
            out[p] = tr
        return out

    def build(self, scene, coll, frames):
        rep = {"workers": {}, "cycles_in_window": sum(1 for pk in self.picks if pk.t["release"] >= 0)}
        sk = bpy.data.objects.new("opened_sack_bench1", sack_mesh(self.rnd, 0.7, 0.5, 0.18))
        coll.objects.link(sk)
        sk.location, sk.rotation_euler = self.sack_pos, (0, 0, math.pi / 2 + 0.2)
        self.animate(scene, coll, frames, rep, role="bag_opening")
        return rep


# ==================================================================================================== ambient roles
# Roles without parcel flow: technician at the HMI (taps the touchscreen), supervisor on the phone, the cage
# checker with a clipboard at a cage's destination tag, a break table (one seated on a real chair, one standing
# texting). Their props (HMI stand, table, chair, phone, clipboard) are real objects at the right height.
HMI_AT, TECH_AT = (21.2, 13.65), (21.2, 13.06)
BREAK_TABLE = (4.55, 31.35)


def _copy_prop(prefix, at, rot_z):
    """Duplicate a dressed Poly Haven prop (root empty + child meshes, shared mesh data) at a new spot."""
    root = next((o for o in bpy.data.objects if o.name.startswith(prefix) and o.type == "EMPTY"
                 and not o.name.startswith("src_") and o.children), None)
    if root is None:
        return None
    new_root = root.copy()
    for c in root.users_collection:
        c.objects.link(new_root)
        break
    new_root.location, new_root.rotation_euler = (at[0], at[1], 0.0), (0, 0, rot_z)
    for ch in root.children:
        c2 = ch.copy()
        for c in ch.users_collection:
            c.objects.link(c2)
            break
        c2.parent = new_root
    return new_root


class Ambient:
    def __init__(self, ctx):
        self.DT, self.F0, self.F1 = ctx["DT"], ctx["F0"], ctx["F1"]
        self.rnd = random.Random(ctx["seed"] + 1101)

    def build(self, scene, coll, frames):
        import mixamo_workers as MW  # prop meshes only (HMI stand, break table)
        frames = list(frames)
        rnd = self.rnd
        rep = {}
        grey = P._mat("steel_grey", (0.32, 0.33, 0.34), 0.45, metal=0.8)
        dark = P._mat("hmi_case", (0.06, 0.065, 0.07), 0.5)
        screen = P._mat("hmi_screen", (0.08, 0.22, 0.42), 0.2, emit=2.2)
        # ---------------------------------------------------------------- technician at the HMI
        MW._place(coll, "tech_hmi", P._prop_mesh("hmi_stand", MW._hmi_mesh, [grey, dark, screen]), HMI_AT, 0.0, 270)
        sc_c = Vector((HMI_AT[0], HMI_AT[1] - 0.062, 1.334))  # screen centre (faces south, tilted back 20 deg)
        n = Vector((0, -math.cos(math.radians(20)), math.sin(math.radians(20))))  # out of the screen
        upv = Vector((0, math.sin(math.radians(20)), math.cos(math.radians(20))))  # up the screen
        wk = C.Worker(scene, coll, dict(role="technician", avatar="Male_Adult_05", vest="yellow", hat="cap"),
                      "worker_tech_1", Vector((*TECH_AT, 0)), math.pi / 2, hat_colour=0, clip_offset=71)
        wk.rig()
        taps, t = [], -0.5
        while t < self.F1 * self.DT + 2:
            n_t = rnd.randint(2, 4)  # a few taps on the screen, then hands down, read, again
            spots = [sc_c + Vector((rnd.uniform(-0.14, 0.14), 0, 0)) + upv * rnd.uniform(-0.08, 0.08) for _ in range(n_t)]
            taps.append((t, t + 0.5 + 0.7 * n_t, spots))
            t += 0.5 + 0.7 * n_t + rnd.uniform(1.6, 3.4)
        for f in frames:
            tt = (f - self.F0) * self.DT
            rest = wk.neutral_hands(f, "rest")
            tg, w_ = dict(rest), 0.0
            for (a, b, spots) in taps:
                if a <= tt <= b + 0.5:
                    k = min(int((tt - a - 0.4) / 0.7), len(spots) - 1) if tt > a + 0.4 else 0
                    poke = 0.5 + 0.5 * math.cos(2 * math.pi * ((tt - a - 0.4) % 0.7) / 0.7) if tt > a + 0.4 else 1.0
                    p = spots[max(k, 0)] + n * (0.025 + 0.035 * poke)  # fingers flat, tip on the glass at the tap
                    tg["R"] = (p, C.frame_from(upv * 0.9 - n * 0.4, -n))
                    w_ = min(1.0, (tt - a) / 0.4, max(0.0, (b + 0.5 - tt) / 0.5))
            wk.set_trunk(f, 0.0, 0.06, 0.0)
            wk.set_hands(f, tg, fingers="flat", weight=w_)
            wk.set_look(f, sc_c)
        wk.auto_steps(frames)
        wk.apply(frames)
        self._props(scene, wk, "worker_tech_1", "Male_Adult_05", math.pi / 2)
        rep["worker_tech_1"] = dict(taps=len(taps), deficits=Ambient._defs(wk))
        # ---------------------------------------------------------------- supervisor on the phone (bagging aisle)
        wk = C.Worker(scene, coll, dict(role="supervisor", avatar="Male_Adult_12", vest="orange", hat="hard",
                                        device="phone"), "worker_sup_1", Vector((51.7, 22.45, 0)),
                      math.radians(215), hat_colour=1, base_clip="cell_phone_textmessage", clip_offset=12)
        wk.rig()
        for f in frames:
            tt = (f - self.F0) * self.DT
            look = None
            if (tt % 9.0) > 6.5:  # looks up from the phone at the chute row now and then
                look = Vector((44.0 - 2.0 * math.sin(tt), 21.0, 1.1))
            wk.set_trunk(f, 0.0, 0.03, 0.0)
            if look is not None:
                wk.set_look(f, look)
        wk.auto_steps(frames)
        wk.apply(frames)
        self._props(scene, wk, "worker_sup_1", "Male_Adult_12", math.radians(215))
        rep["worker_sup_1"] = dict(deficits=Ambient._defs(wk))
        # ---------------------------------------------------------------- cage checker at S08's tag (clipboard)
        cage = bpy.data.objects.get("cage_S08")
        if cage is not None:
            r = cage.rotation_euler[2]
            ca, sa = math.cos(r), math.sin(r)
            tag = Vector((cage.location.x + 0.36 * ca + 0.42 * sa, cage.location.y + 0.36 * sa - 0.42 * ca, 1.2))
            at = Vector((cage.location.x + 0.5 * ca + 0.95 * sa, cage.location.y + 0.5 * sa - 0.95 * ca, 0.0))
            face = math.atan2(tag.y - at.y, tag.x - at.x)
            wk = C.Worker(scene, coll, dict(role="cages", avatar="Female_Adult_06", vest="orange", device="clipboard",
                                            open=True), "worker_check_1", at, face, hat_colour=2,
                          base_clip="documents_check", clip_offset=33)
            wk.rig()
            for f in frames:
                tt = (f - self.F0) * self.DT
                wk.set_trunk(f, 0.0, 0.05, 0.0)
                if (tt % 6.0) < 1.6:  # compares the tag with the manifest on her clipboard
                    wk.set_look(f, tag)
            wk.auto_steps(frames)
            wk.apply(frames)
            self._props(scene, wk, "worker_check_1", "Female_Adult_06", face)
            rep["worker_check_1"] = dict(at=[round(at.x, 2), round(at.y, 2)], deficits=Ambient._defs(wk))
        # ---------------------------------------------------------------- break table: seated + standing
        tx, ty = BREAK_TABLE
        MW._place(coll, "break_table", P._prop_mesh("break_table", MW._table_mesh,
                                                    [P._mat("table_top", (0.55, 0.53, 0.5), 0.6), grey]), (tx, ty), 0.0, 90)
        seat_at = (tx - 0.25, ty - 0.66)  # at the table's south long side, facing north across it
        chair = _copy_prop("plastic_monobloc_chair_01", seat_at, math.radians(180))
        wk = C.Worker(scene, coll, dict(role="break", avatar="Male_Adult_04", vest="lime"), "worker_break_1",
                      Vector((seat_at[0], seat_at[1] - 0.05, 0)), math.pi / 2, hat_colour=3, clip_offset=5)
        wk.rig()
        seat_drop = 0.36  # pelvis from standing (~0.9 m) onto the seat (0.44 m + soft tissue)
        for f in frames:
            tt = (f - self.F0) * self.DT
            wk.set_trunk(f, 0.0, -0.05, seat_drop)
            chest = wk.torso_frame(f)[0]
            edge = Vector((seat_at[0], ty - 0.22, 0.745))  # forearms on the table, 15 cm in from its edge
            tg = {"L": (edge + Vector((-0.17, 0.02, 0)), C.frame_from(Vector((0.2, 1, 0)), Vector((0, 0, -1)))),
                  "R": (edge + Vector((0.15, 0.0, 0)) + Vector((0, 0.03 * math.sin(tt * 0.7), 0)),
                        C.frame_from(Vector((-0.2, 1, 0)), Vector((0, 0, -1))))}
            wk.set_hands(f, tg, fingers="flat")
            wk.set_look(f, Vector((tx + 0.95, ty - 0.35, 1.55)) if (tt % 7.0) < 4.5 else Vector((tx - 0.2, ty, 0.8)))
        feet = {}
        A0 = wk.A(frames[0])
        for sd in ("L", "R"):
            M = A0 @ wk.foot_local[sd]
            feet[sd] = Matrix.Translation(Vector((0.0, 0.34, 0.0))) @ M  # forward (north), under the table edge
        for f in frames:
            wk.set_feet(f, feet)
        wk.apply(frames)
        self._props(scene, wk, "worker_break_1", "Male_Adult_04", 0.0)
        rep["worker_break_1"] = dict(chair=bool(chair), deficits=Ambient._defs(wk))
        wk = C.Worker(scene, coll, dict(role="break", avatar="Female_Adult_13", vest=None, device="phone"),
                      "worker_break_2", Vector((tx + 0.95, ty - 0.35, 0)), math.radians(160), hat_colour=0,
                      base_clip="cell_phone_textmessage", clip_offset=47)
        wk.rig()
        for f in frames:
            tt = (f - self.F0) * self.DT
            wk.set_trunk(f, 0.0, 0.03, 0.0)
            if (tt % 8.0) > 5.0:  # looks up to talk to the seated colleague
                wk.set_look(f, Vector((seat_at[0], seat_at[1], 1.15)))
        wk.auto_steps(frames)
        wk.apply(frames)
        self._props(scene, wk, "worker_break_2", "Female_Adult_13", math.radians(160))
        rep["worker_break_2"] = dict(deficits=Ambient._defs(wk))
        return rep

    @staticmethod
    def _defs(wk):
        out = {}
        for f, bone, cm in wk.deficits:
            k = "leg" if "Foot" in bone else "arm"
            n, mx = out.get(k, (0, 0.0))
            out[k] = (n + 1, max(mx, cm))
        return out

    @staticmethod
    def _props(scene, wk, name, avatar, heading):
        if P._pending_props.get(name):
            scene.frame_set(1)
            P._fit_props(scene, wk.arm, wk.body, P._templates[avatar], heading, P._pending_props.pop(name))
