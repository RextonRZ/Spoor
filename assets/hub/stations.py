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
Y_HALF = 1.02  # the wall's end columns 10 cm in from the body's side walls (+-1.12): at 1.07 his fingers on an end
# carton touched the side wall, run 17
# 0.35 m from the face (reachable: 0.6 m put the cartons out of reach), 0.5 m off the boom's centre line; a carton
# cleared from the wall is held toward the boom, over it, where there is room (between him and the face it pressed
# into his chest: owner rule, review 009d)
WORKER_X, WORKER_DY = -1.05, 0.62  # (0.55 at x -1.05: his arm by the boom's nose, run 17)  # (x -1.25: 0.35 m from the carton face, a 0.26 m carton held between them
# touched the wall or his chest - pushed off one it went into the other, runs 12-16)  # (0.50: his hanging hand lay on the boom's side frame between cartons, run 13)
BELT_START_X = -1.15
PLACE_X = -0.98  # carton centre on the nose when set down
# side +1 (north of the boom): feet face 205 deg (mostly at the wall, a little toward the boom), mirrored for -1
FEET = {+1: math.radians(207), -1: math.radians(153)}
AVATARS = [  # (avatar, vest, hat) per worker slot: D02 north / south, D05 north / south
    ("Male_Adult_05", "orange", None), ("Male_Adult_09", None, None),
    ("Male_Adult_12", "lime", None), ("Female_Adult_07", "yellow", None)]


def follow_turn(yaw_end, box_yaw, worker_pos, pick_pos, place_pos):
    """Of yaw_end and yaw_end + pi (same look on the belt), the one whose change from box_yaw matches the turn of
    the carrier's body from pick to place (the gripped faces stay at his sides; arms never cross)."""
    a0 = math.atan2(pick_pos.y - worker_pos.y, pick_pos.x - worker_pos.x)
    a1 = math.atan2(place_pos.y - worker_pos.y, place_pos.x - worker_pos.x)
    turn = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
    want = box_yaw + turn

    def err(y):
        return abs((y - want + math.pi) % (2 * math.pi) - math.pi)
    return min((yaw_end, yaw_end + math.pi), key=err)


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

    def y_ext(self):
        w, d, h = self.dims
        return w if abs(math.cos(self.yaw)) < 0.5 else d

    def footprint(self, margin=0.0):
        """World xy corners of the base rectangle (grown by margin)."""
        w, d, h = self.dims
        c, s_ = math.cos(self.yaw), math.sin(self.yaw)
        ax, ay = Vector((c, s_)), Vector((-s_, c))
        hw, hd = w / 2 + margin, d / 2 + margin
        o = self.pos.xy
        return [o + ax * sx * hw + ay * sy * hd for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]

    def overlaps_xy(self, other, margin=0.01):
        """2-D separating-axis test of the two base rectangles."""
        pa, pb = self.footprint(margin), other.footprint(margin)
        for poly in (pa, pb):
            for i in range(4):
                e = poly[(i + 1) % 4] - poly[i]
                n = Vector((-e.y, e.x))
                a_ = [n.dot(q) for q in pa]
                b_ = [n.dot(q) for q in pb]
                if max(a_) < min(b_) or max(b_) < min(a_):
                    return False
        return True


def build_wall(rnd, cy, box_dims):
    """Columns of cartons across the body, front face at X_FACE, back rows to X_BACK. Returns (front, back)."""
    usable = [d for d in box_dims if 0.2 <= d[0] <= 0.45 and d[2] >= 0.1]
    # the face (the cartons he takes): at most 0.36 m deep, so a carton cleared from the wall fits between him and
    # the face without touching either (owner rule)
    face = [d for d in usable if d[1] <= 0.36] or usable
    front, back = [], []
    y = cy - Y_HALF
    while True:
        dims0 = rnd.choice(face)
        colw = dims0[0]
        if y + colw > cy + Y_HALF:
            break
        yc = y + colw / 2
        top = rnd.uniform(1.15, 1.55)  # a partly unloaded lorry: every face carton is taken by the top (palms on
        # top, nothing beside the hands - side grips between tight columns went into the neighbours)
        z = 0.0
        while z < top - 0.08:
            fits = [d for d in face if colw - 0.07 <= d[0] <= colw] or [dims0]
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
    READY = "ready"  # empty-hands pose (contact.neutral_hands kind)
    MAX_HIP_SHIFT = 0.12  # reach adaptation: hips toward the work at most this far (m)
    READY_KEEP = None  # lines the empty hands wait behind (None: KEEP_OUT)
    # (world matrix, dims) boxes the arms keep clear of (elbow swivel, contact.Worker._chain): for the unloaders the
    # boom's nose sections beside them, x -1.2..1.4, +-0.33 m, up to the belt (forearms rested on its side frame)
    STATIC_OBST = [(Matrix.Translation((-0.15, d["cy"], 0.0)), (3.1, 0.7, 1.02)) for d in DOCKS]  # (from x -1.7: the
    # boom runs on into the lorry - from -1.2 their forearms lay on it there, 3-4 cm, run 11)
    TOP_GRIP = True  # wall cartons: taken by the top out of the slot, hands slide to the sides once it is clear
    # carried cartons keep their far edge on the open side of these lines (n . p >= off + half): the carton face
    # he unloads (QA: the turn swung cartons into the wall)
    KEEP_OUT = [(Vector((1.0, 0.0)), X_FACE + 0.05)]
    PULL_OUT, PULL_LIFT = 0.2, 0.035  # a wall carton slides straight out of its slot
    TURN_LIFT = 0.05  # carried a little higher mid-turn
    RELEASE_UP = 0.08  # let go 8 cm over the belt (lowered onto it, the forearms under it went 3-4 cm into the boom,
    # runs 9-12)
    HOLD_LIFTED = False
    STRAIGHT_PULL = True

    def __init__(self, ctx):
        self.ctx = ctx
        self.rnd = random.Random(ctx["seed"] + 101)
        self.DT, self.F0, self.F1 = ctx["DT"], ctx["F0"], ctx["F1"]
        self.T_END = (self.F1 - self.F0) * self.DT
        self.T_STOP = ctx.get("T_STOP", self.T_END)  # (sim-only --scan-extend: work on past the window)
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
        # the lorry's side walls (1.1 m each side of the dock's centre line): a carton turned out of the north column
        # swept 5-8 cm into the wall, run 11
        self.KEEP_OUT = list(self.KEEP_OUT) + [ln for d in DOCKS for ln in ((Vector((0.0, -1.0)), -(d["cy"] + 1.08)),
                                                                             (Vector((0.0, 1.0)), d["cy"] - 1.08))]
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
        # the face comes down in layers (real unloading): always the highest carton left on his columns, the
        # nearer column first when tops are within ~10 cm. Digging one column to the floor left a slot between
        # full-height neighbours that he had to bend into, head first into the next column (QA 30 Oct).
        cand = []
        for dist, bs in mine:
            for b in bs:
                if b.pos.z + b.dims[2] * 0.5 < 0.32:  # last one or two on the floor: left for later (sweep)
                    break
                cand.append((-(b.pos.z + b.dims[2]) + 0.15 * dist, b))
        cand.sort(key=lambda c: c[0])
        return [b for _, b in cand]

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

    def _ready_clamp(self, w, p):
        """Empty hands stay on his own side of the boom beside him (they rested on its side frame: collision
        check); other stations: as is."""
        if self.STRAIGHT_PULL and "cy" in w.dock and p.x > -1.3:
            side = 1.0 if w.pos.y >= w.dock["cy"] else -1.0
            if side * (p.y - w.dock["cy"]) < 0.36:
                p = Vector((p.x, w.dock["cy"] + side * 0.36, p.z))
        return p

    def _hold_if_busy(self, w, pk, t, belt, half):
        """Just before the set-down: if the belt stalled since he committed and a parcel is now where this one goes,
        hold it above a frame longer (it was set down on top of the stalled one: QA parcel_overlap 8-18 cm)."""
        snap = self.__dict__.setdefault("_snap", {})  # belt positions per simulation step: (t, now, previous)
        st = snap.get(id(belt))
        if st is None or st[0] != t:
            st = (t, {id(q): q.s for q in belt.items}, st[1] if st else {})
            snap[id(belt)] = st
        last = st[2]
        if not (pk.t["place"] - self.DT - 1e-6 <= t < pk.t["release"] - 1e-6):
            return
        busy = False
        for q in belt.items:
            if q is pk.parcel or getattr(q, "state", "") == "ghost":
                continue
            stopped = id(q) in last and abs(last[id(q)] - q.s) < 1e-6  # (a running belt's parcels are judged
            at = q.s if stopped else q.s + belt.speed * max(pk.t["release"] - t, 0.0)  # where they will be)
            if abs(at - pk.s) < q.half + half + 0.05:
                busy = True
                break
        if busy:
            for k_ in ("place", "release", "end"):
                pk.t[k_] += self.DT
            pk.t_rel, pk.f_rel = pk.t["release"], pk.f_rel + 1

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
                if t < w.free_at or not w.slots or t > getattr(self, 'T_STOP', self.T_END) + 1.0:
                    continue
                box = w.slots.pop(0)
                pk = Pick(box, w)
                w_, d_, h_ = box.dims
                pk.below_top = max([b.pos.z + b.dims[2] for b in w.slots  # the carton under it in its column
                                    if b.pos.z < box.pos.z - 0.01 and abs(b.pos.y - box.pos.y) < 0.5 * (
                                        b.y_ext() + box.y_ext()) - 0.01], default=None)
                low = box.pos.z + h_ * 0.65 < 0.8
                # weight (review 009d): a full carton moves slower than an empty-feeling one - volume as the proxy
                heavy = 1.0 + 0.35 * min(w_ * d_ * h_ / 0.03, 1.0)
                T_reach = rnd.uniform(1.0, 1.35) + (0.4 if low else 0.0)  # real unload: 4-6 s per carton
                T_settle = rnd.uniform(0.25, 0.35)  # grip, and the small knee dip before the lift (anticipation)
                T_pull = (rnd.uniform(0.35, 0.5) + (0.2 if low else 0.0)) * heavy
                pk.T_turn = (rnd.uniform(0.9, 1.2) + (0.2 if low else 0.0)) * heavy * 1.7  # (wall to boom, ~180 deg: at
                # 0.9-1.2 s the carton swung 30-35 deg and 0.25 m in a frame, held-object gate run 9)
                pk.T_place = rnd.uniform(0.3, 0.4) * heavy
                pk.T_ret = rnd.uniform(0.45, 0.6)
                pk.t = dict(reach=t, settle=t + T_reach, pull=t + T_reach + T_settle,
                            hold=t + T_reach + T_settle + T_pull)
                yaw_end = box.yaw + self._turn_angle(w, box)
                hx = abs(math.cos(yaw_end)) * w_ / 2 + abs(math.sin(yaw_end)) * d_ / 2
                x_c = max(PLACE_X + rnd.uniform(-0.04, 0.04), BELT_START_X + hx + 0.05)  # (clear of the nose's end
                # frame: 1 cm from it, set-downs went 3-4 cm into it, run 12)
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
            if (w.state == "reach" and pk.t["settle"] <= t < pk.t["pull"] - 1e-6
                    and (t + (pk.t["hold"] - pk.t["pull"]) < self.lock[bn] or not self._nose_clear(bn, pk.s, pk.half))):
                # the nose is busy (the mate is setting one down): wait with the hands on the carton in the wall
                # instead of pulling it out and holding it at the chest (the hold put it into his chest and arms:
                # collision check, phase attribution)
                for k_ in ("pull", "hold"):
                    pk.t[k_] += self.DT
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
            if (w.state == "turn" and pk.t["place"] - self.DT - 1e-6 <= t < pk.t["release"] - 1e-6
                    and not self._nose_clear(bn, pk.s, pk.half)):
                # the boom stalled since he committed (its queue backed up to the nose): hold it over the nose a
                # frame longer instead of setting it down on the last one (QA parcel_overlap 9-19 cm)
                for k_ in ("place", "release", "end"):
                    pk.t[k_] += self.DT
                pk.t_rel, pk.f_rel = pk.t["release"], pk.f_rel + 1
                self.lock[bn] = max(self.lock[bn], pk.t["release"] + 0.25)
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
        if self.STRAIGHT_PULL:
            # a wall carton comes straight out of its slot (a diagonal pull swept it through the next column),
            # then is held against the chest with its far face at the wall line (0.32 m from face to worker)
            high = box.pos.z + box.dims[2] > 1.6  # a top-row carton comes out only a little at face height,
            # then is lowered to the chest (slid 20 cm out up there it went into his face: QA held_clip_head)
            low = box.pos.z < 0.45  # a bottom-row carton comes up out of its slot first (the column above is gone by
            # then): pulled 20 cm out at shin height it went 6 cm into his legs, run 9
            p1 = box.pos + Vector((0.12 if high else (0.06 if low else self.PULL_OUT), 0.0, 0.3 if low else self.PULL_LIFT))
            # (low: up 0.3 m before it comes out - at 0.15 it still met his forearm and thigh, 8 cm, run 15)
            hold = self._dock_hold(w, box, p1)
            hold.x = max(hold.x, X_FACE + 0.01 + box.depth_x() / 2)
            ye_ = box.y_ext() / 2  # clear of the lorry's side walls (KEEP_OUT's side lines; at the chest a carton from
            for n_, off in self.KEEP_OUT:  # the end column stood 4 cm into the wall, run 12)
                if abs(n_.y) > 0.5:
                    short = off + ye_ - n_.dot(hold.xy)
                    if short > 0:
                        hold += Vector((n_.x, n_.y, 0.0)) * short
        else:
            p1 = box.pos + Vector((out_dir.x, out_dir.y, 0)) * self.PULL_OUT + UP * self.PULL_LIFT
            p1.z = max(p1.z, getattr(pk, "lift_z", 0.0))
            hold = p1 + Vector((out_dir.x, out_dir.y, 0)) * 0.08
            p1 = self._hold_point(w, box, p1)  # the pull ends clear of the body too (13 cm into the opener)
            c_, s_ = math.cos(box.yaw), math.sin(box.yaw)
            for n_, off in self.KEEP_OUT:  # held while waiting: clear of the queue beside him too
                ext = abs(n_.x * c_ + n_.y * s_) * box.dims[0] / 2 + abs(-n_.x * s_ + n_.y * c_) * box.dims[1] / 2
                short = off + ext - n_.dot(hold.xy)
                if short > 0:
                    hold += Vector((n_.x, n_.y, 0.0)) * short
        hold = self._hold_point(w, box, hold)
        if self.STRAIGHT_PULL:  # never into the wall it came out of (last: the push off his body went into it)
            hold.x = max(hold.x, X_FACE + 0.01 + box.depth_x() / 2)
        hold = self._side_clear(box, hold)  # (after the push off his body: it pushed a carton back into the lorry's
        # side wall, 4-11 cm, run 14)
        if getattr(self, "HEAP_PULL", False):  # held beside the heap, turned toward where it goes (over the heap the
            # chin-height cap put it back down inside the parcels it came out of: collision check)
            d0 = (box.pos - w.pos).xy
            a_ = math.atan2(d0.y, d0.x) + self.HOLD_TURN
            r_ = 0.3 + max(box.dims[0], box.dims[1]) / 2  # (0.24: his belly against it while he waited)
            hold = Vector((w.pos.x + math.cos(a_) * r_, w.pos.y + math.sin(a_) * r_, hold.z))
        hold.z = max(0.78, min(p1.z, 1.05)) - box.dims[2] * 0.4
        if self.HOLD_LIFTED:  # waiting over the heap: kept up where it was lifted (lowered, it sat in the heap)
            hold.z = max(hold.z, p1.z)
        hold.z = min(hold.z, 1.22 - box.dims[2])  # top of the carton at most sternum high (chin on it: review 009c)
        if self.STRAIGHT_PULL:  # held over the boom: clear of its belt and side frames
            hold.z = max(hold.z, 1.03)
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
            if getattr(self, "HEAP_PULL", False):  # up first, then out
                uz, uxy = C.smooth(min(1.0, u * 1.8)), C.smooth(max(0.0, (u - 0.56) / 0.44))  # fully up first
                return Vector((lerp(box.pos.x, p1.x, uxy), lerp(box.pos.y, p1.y, uxy), lerp(box.pos.z, p1.z, uz))), box.yaw
            return box.pos.lerp(p1, u), box.yaw
        if t < T["turn"]:  # waiting with it at the chest (p1 -> hold over <= 0.45 s)
            return self._to_hold(p1, hold, (t - T["hold"]) / self._hold_s(p1, hold), pk), box.yaw
        start = self._to_hold(p1, hold, (T["turn"] - T["hold"]) / self._hold_s(p1, hold), pk)
        place, yaw_end = pk.place
        above = place + UP * (0.075 + self.RELEASE_UP)  # (down 7.5 cm to the let-go point, wherever that is: from
        # 7.5 to 8 cm it hovered still in his hands, run 13)
        if t < T["place"]:
            u = C.smooth((t - T["turn"]) / (T["place"] - T["turn"]))
            piv = w.pos
            a0 = math.atan2(start.y - piv.y, start.x - piv.x)
            a1 = math.atan2(above.y - piv.y, above.x - piv.x)
            r0, r1 = (start - piv).xy.length, (above - piv).xy.length
            da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
            ty0, ty1 = self._trunk_for(w, start, 1.0)[0], self._trunk_for(w, above, 1.0)[0]
            # (the short way to the boom: "the way the body turns" sent cartons round behind him, through his
            # forearms and back, 4-9 cm, runs 13-17 - an unloader turns the short way)
            if self.KEEP_OUT:  # ...unless that sweeps the carton through the wall he faces: then round the other side
                hb = max(box.dims[0], box.dims[1]) / 2

                def worst(d_a):
                    m = 9.0
                    for i in range(1, 12):
                        uu = i / 12
                        aa = a0 + d_a * uu
                        q = piv.xy + Vector((math.cos(aa), math.sin(aa))) * lerp(r0, r1, uu)
                        m = min([m] + [n_.dot(q) - off - hb for n_, off in self.KEEP_OUT
                                       if abs(n_.x) > 0.5])  # (the wall face: the lorry's side lines are for the hold
                        # - counted here they sent a carton the long way round, through his back, run 13)
                    return m
                alt = da - math.copysign(2 * math.pi, da)
                if worst(da) < -0.02 and worst(alt) > worst(da):
                    da = alt
            a = a0 + da * u
            r_lin = lerp(r0, r1, u)
            # carried out in front mid-turn - only as far as the body needs (its near edge 0.22 m from his feet:
            # a fixed 0.5 m left big cartons beyond reach, hands 10-19 cm off them through the turn)
            dd = Vector((math.cos(a0 + da * u), math.sin(a0 + da * u)))
            cy_, sy_ = math.cos(box.yaw), math.sin(box.yaw)
            ext = abs(dd.x * cy_ + dd.y * sy_) * box.dims[0] / 2 + abs(-dd.x * sy_ + dd.y * cy_) * box.dims[1] / 2
            r = r_lin + max(0.0, 0.42 + ext - r_lin) * math.sin(math.pi * u)  # (0.22: chest into it; 0.28: his
            # back / spine 9 cm into it going round behind him, run 13)
            d_ = Vector((math.cos(a), math.sin(a)))
            for n_, off in self.KEEP_OUT:  # ...but never out into the wall / the queue beside him
                nd = n_.dot(d_)
                if nd < -1e-3:
                    r = max(r_lin, min(r, (n_.dot(piv.xy) - off - max(box.dims[0], box.dims[1]) / 2) / -nd))
            z = lerp(start.z, above.z, u) + self.TURN_LIFT * math.sin(math.pi * u)
            dy = (yaw_end - box.yaw + math.pi) % (2 * math.pi) - math.pi
            if abs(da) > math.pi and dy * da < 0:
                dy += math.copysign(2 * math.pi, da)
            return self._side_clear(box, Vector((piv.x + r * math.cos(a), piv.y + r * math.sin(a), z))), box.yaw + dy * u
        u = C.smooth((t - T["place"]) / (T["release"] - T["place"]))
        return above.lerp(place + UP * self.RELEASE_UP, u), yaw_end

    def _hold_point(self, w, box, hold):
        """The carton's centre at least 0.2 m + its half size (toward him) from his root: never into his body (the
        opener held parcels 31 cm into herself: collision check)."""
        d = Vector((hold.x - w.pos.x, hold.y - w.pos.y))
        if d.length < 1e-6:
            d = Vector((math.cos(w.heading), math.sin(w.heading)))
        u = d.normalized()
        c_, s_ = math.cos(box.yaw), math.sin(box.yaw)
        ext = abs(u.x * c_ + u.y * s_) * box.dims[0] / 2 + abs(-u.x * s_ + u.y * c_) * box.dims[1] / 2
        need = 0.34 + ext  # (0.2: belly / chest 2-6 cm into the carton, collision check; 0.26 / 0.32: leaning over
        # it, his chest 3-9 cm into it, runs 12-15; he stands 0.2 m further from the wall since run 17)
        if d.length < need:
            hold = Vector((w.pos.x + u.x * need, w.pos.y + u.y * need, hold.z))
        return hold

    def _dock_hold(self, w, box, hold):
        """Toward the boom (mostly sideways, a little into the hall), clear of his body."""
        d = Vector((0.35, w.dock["cy"] - w.pos.y)).normalized()
        c_, s_ = math.cos(box.yaw), math.sin(box.yaw)
        ext = abs(d.x * c_ + d.y * s_) * box.dims[0] / 2 + abs(-d.x * s_ + d.y * c_) * box.dims[1] / 2
        q = Vector((w.pos.x, w.pos.y)) + d * (0.2 + ext)
        # ...but on his own side of the boom: held over the nose it sat where his mate was setting a carton down
        # (QA parcel_overlap 9-19 cm). The boom's belt is +-0.3 m round its centre line.
        ext_y = abs(c_) * box.dims[1] / 2 + abs(s_) * box.dims[0] / 2
        side = 1.0 if w.pos.y >= w.dock["cy"] else -1.0
        q.y = w.dock["cy"] + side * max(side * (q.y - w.dock["cy"]), 0.33 + ext_y)
        return Vector((q.x, q.y, hold.z))

    def _side_clear(self, box, q):
        """A carton's centre moved in off the lorry's side walls (the KEEP_OUT side lines, y only)."""
        ye_ = max(box.dims[0], box.dims[1]) / 2  # (any yaw it turns through)
        for n_, off in self.KEEP_OUT:
            if abs(n_.y) > 0.5:
                short = off + ye_ - n_.dot(q.xy)
                if short > 0:
                    q = q + Vector((n_.x, n_.y, 0.0)) * short
        return q

    @staticmethod
    def _hold_s(p1, hold):
        """Pull point -> chest: 0.45 s, longer for a big rise (a low carton came up 0.4 m in under 3 frames: 0.26 m in
        one, held-object gate run 9), at most 0.6 m/s up."""
        return max(0.45, abs(hold.z - p1.z) / 0.6 + 0.15)

    def _to_hold(self, p1, hold, u, pk=None):
        """Pull point -> chest. A wall carton goes DOWN first, still out at the wall, then in at chest height (on
        the straight diagonal a top-row carton crossed his face: 0.32 m from the face to him) - never down into the
        carton under it in its column while it is still within 2 cm of the wall face (a top-row carton pulled only
        12 cm out went 5 cm into the one below, D05 run 7)."""
        u = min(max(u, 0.0), 1.0)
        floor_z = getattr(pk, "below_top", None) if pk is not None else None
        if getattr(self, "HEAP_PULL", False):  # across at the lifted height first (clear of the heap), then down
            uxy, uz = C.smooth(min(1.0, u * 1.6)), C.smooth(max(0.0, (u - 0.4) / 0.6))
            return Vector((lerp(p1.x, hold.x, uxy), lerp(p1.y, hold.y, uxy), lerp(p1.z, hold.z, uz)))
        if not self.STRAIGHT_PULL:
            return p1.lerp(hold, C.smooth(u))
        uz, uxy = C.smooth(min(1.0, u * 1.6)), C.smooth(max(0.0, (u - 0.35) / 0.65))
        q = Vector((lerp(p1.x, hold.x, uxy), lerp(p1.y, hold.y, uxy), lerp(p1.z, hold.z, uz)))
        if pk is not None and q.x + pk.box.depth_x() / 2 > BELT_START_X - 0.07 and \
                abs(q.y - pk.worker.dock["cy"]) < 0.33 + pk.box.y_ext() / 2:
            q.z = max(q.z, 1.03)  # over the boom's nose: above its belt (rising from a low slot it went 3 cm in, run 14)
        if floor_z is not None:  # eased off the floor over the last 3 cm out (no step down)
            out_ = q.x - pk.box.depth_x() / 2 - (X_FACE + 0.02)
            q.z = max(q.z, (floor_z + 0.01) * (1.0 - C.smooth(min(1.0, max(0.0, out_ / 0.03)))) +
                      q.z * C.smooth(min(1.0, max(0.0, out_ / 0.03))))
        return q

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
        socks = self._grip_socks(w, pk, t)
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
            if getattr(self, "HEAP_PULL", False):  # off a heap: up out of the bend as it comes up (the lifted
                pulled = (slot_trunk[0], min(slot_trunk[1], 0.14), 0.0)  # parcel met his bent-over face)
            if t < T["hold"]:
                u = C.smooth((t - T["pull"]) / (T["hold"] - T["pull"])) if t > T["pull"] else 0.0
                trunk = tuple(lerp(a, b, u) for a, b in zip(slot_trunk, pulled))
                if t < T["pull"]:  # anticipation: a small dip in the knees, then the lift
                    dip = 0.03 * math.sin(math.pi * min(1.0, (t - T["settle"]) / max(T["pull"] - T["settle"], 1e-3)))
                    trunk = (trunk[0], trunk[1], trunk[2] + dip)
                return trunk, ("grip", self._socket_world(M, socks), (M, box.dims)), box.pos + UP * box.dims[2] * 0.5
            if t < T["turn"]:  # holding it at the chest, eyes on the nose
                u = C.smooth((t - T["hold"]) / 0.45)
                trunk = tuple(lerp(a, b, u) for a, b in zip(pulled, carry_trunk))
                return trunk, ("grip", self._socket_world(M, socks), (M, box.dims)), place + UP * 0.1
            u = C.smooth((T["turn"] - T["hold"]) / 0.45)
            start_trunk = tuple(lerp(a, b, u) for a, b in zip(pulled, carry_trunk))
            if t < T["place"]:
                u = C.smooth((t - T["turn"]) / (T["place"] - T["turn"]))
                # turn upright with the carton low in front; bend for the set-down only in the last 40 % (bent
                # through the whole turn, the head came down into a tall carton: review 006 P0 #1)
                ub = C.smooth(max(0.0, (u - 0.6) / 0.4))
                upright = min(start_trunk[1], carry_trunk[1], 0.12)
                flex = lerp(lerp(start_trunk[1], upright, min(1.0, u * 3)), place_trunk[1], ub)
                trunk = (lerp(start_trunk[0], place_trunk[0], u), flex, lerp(start_trunk[2], place_trunk[2], ub))
                return trunk, ("grip", self._socket_world(M, socks), (M, box.dims)), place + UP * 0.1
            return place_trunk, ("grip", self._socket_world(M, socks), (M, box.dims)), place + UP * 0.05
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
        """A longer pause: a look at the colleague on the other side of the boom now and then (review 009d: nobody
        glanced at a neighbour), otherwise into the lorry."""
        mate = next((o for o in self.workers if o is not w and o.dock is w.dock), None)
        if mate is not None and len(w.picks) % 2 == 0:
            return Vector((mate.pos.x, mate.pos.y, 1.6))
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

    def _grip_socks(self, w, pk, t):
        """Palm sockets (box frame) at time t. Side grip; for a carton in a packed wall (TOP_GRIP) the palms are
        on its top while it comes out of the slot (side faces 4-8 cm from the next column: the hands went into
        it), then slide round to the sides during the first 0.45 s at the chest."""
        box = pk.box
        tl = self._toward_local(w, box)
        high = box.pos.z + box.dims[2] > 1.6  # above the shoulders palms can't go flat on top: grip the sides
        # high instead (the layer order keeps that carton's neighbours lower than it)
        side = C.box_sockets(box.dims, tl, up_frac=0.25 if (self.TOP_GRIP and high) else 0.45, front_frac=0.8,
                             inset=-0.035)  # (0.72 / -0.022: at the chest the forearms crossed its near edges 3-7 cm,
        # run 14)
        if not self.TOP_GRIP or high or t >= pk.t["hold"] + 0.45:
            return side
        top = C.box_sockets(box.dims, tl, top=True)
        if t < pk.t["hold"]:
            return top
        u = C.smooth((t - pk.t["hold"]) / 0.45)
        lat = UP.cross(tl).normalized()
        out = {}
        for sd, sgn in (("L", -1.0), ("R", 1.0)):
            (p0, R0), (p1, R1) = top[sd], side[sd]
            p = p0.lerp(p1, u) + lat * sgn * 0.04 * math.sin(math.pi * u)  # round the top edge, not through it
            q0, q1 = R0.to_quaternion(), R1.to_quaternion()
            if q0.dot(q1) < 0:
                q1.negate()
            out[sd] = (p, q0.slerp(q1, u).to_matrix())
        return out

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
            wk.max_shift = self.MAX_HIP_SHIFT
            wk.rig()
            for f in frames:
                t = (f - self.F0) * self.DT
                trunk, hands, look = self._worker_state(w, wk, t)
                wk.set_trunk(f, *trunk)
                ready = wk.neutral_hands(f, self.READY)
                # between picks the arms hang (held out at the chest for seconds they read as "zombie arms": review
                # 009e) - down over 0.6 s after a set-down, up again over the 0.6 s before the next reach
                ends = [q.t["end"] for q in w.picks if q.t["end"] <= t]
                nxts = [q.t["reach"] for q in w.picks if q.t["reach"] > t]
                k_rest = C.smooth(max(0.0, min(1.0, (t - max(ends)) / 0.6 if ends else 1.0,
                                              (min(nxts) - t) / 0.6 if nxts else 1.0)))
                if any(q.t["reach"] <= t <= q.t["end"] for q in w.picks):
                    k_rest = 0.0  # in a cycle the blends start / end at ready
                if k_rest > 0.0:
                    rest = wk.neutral_hands(f, "relaxed")
                    for sd in ("L", "R"):
                        q0, q1 = ready[sd][1].to_quaternion(), rest[sd][1].to_quaternion()
                        if q0.dot(q1) < 0:
                            q1.negate()
                        ready[sd] = (ready[sd][0].lerp(rest[sd][0], k_rest), q0.slerp(q1, k_rest).to_matrix())
                for sd in ("L", "R"):  # empty hands wait clear of the wall face / the queue (they rested in the
                    p_, R_ = ready[sd]   # bottom-row cartons and on the feed frame: collision check)
                    for n_, off in (self.KEEP_OUT if self.READY_KEEP is None else self.READY_KEEP):
                        short = off + 0.08 - n_.dot(p_.xy)
                        if short > 0:
                            p_ = p_ + Vector((n_.x, n_.y, 0.0)) * short
                    ready[sd] = (self._ready_clamp(w, p_), R_)
                fingers, obst = None, list(self.STATIC_OBST)
                if hands is None:
                    tgt = ready
                elif hands[0] == "grip":
                    tgt = hands[1]
                    fingers = "flat"
                    if len(hands) > 2:  # the carton: elbows swivel clear of it (and of the station's frames)
                        obst.append(hands[2])
                else:
                    kind, u, sock = hands
                    if kind == "unblend":
                        u = 1 - u
                    tgt = {}
                    for sd in ("L", "R"):
                        p0, R0 = ready[sd]
                        p1, R1 = sock[sd]
                        back_ = Vector((p0.x - p1.x, p0.y - p1.y, 0.0))  # in from his side and over the top, not
                        back_ = back_.normalized() * 0.06 if back_.length > 1e-6 else Vector()  # through its edge
                        mid_lift = (UP * 0.09 + back_) * math.sin(math.pi * u)
                        q = R0.to_quaternion().slerp(R1.to_quaternion(), u)
                        tgt[sd] = (p0.lerp(p1, u) + mid_lift, q.to_matrix())
                    fingers = "flat" if u > 0.2 else None  # flat before the hand nears the face
                wk.set_hands(f, tgt, fingers=fingers, obstacle=obst)
                wk.set_look(f, look)
            wk.auto_steps(frames, step_s=0.8)  # (0.55 s pivots on top of the trunk turn: 23.8 deg/frame, run 11)
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
                    socks = self._grip_socks(w, pk, t)
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
            rep.setdefault("phases", {})[w.name] = [  # per pick: phase start times (s), for collision attribution
                [round(pk.t.get(k, -99.0), 2) for k in ("reach", "settle", "pull", "hold", "turn", "place", "release",
                                                         "end")] for pk in w.picks]
            rep["workers"][w.name] = dict(avatar=av, picks_in_window=sum(1 for pk in w.picks if pk.parcel is not None),
                                          contact_err_cm_max=round(max(err) * 100, 2) if err else None,
                                          contact_err_cm_p95=round(sorted(err)[int(len(err) * 0.95)] * 100, 2)
                                          if err else None,
                                          heading_deg=round(math.degrees(w.heading)), at=[round(w.pos.x, 2),
                                                                                         round(w.pos.y, 2)],
                                          pivot_steps=len(wk.steps))


# ==================================================================================================== induction
FEED_END_X, IND_Y, FEED_Y = 9.2, 9.5, 10.85
OP_Y = 10.17  # the operators' aisle between the belts: 0.55 m (belt edges at 9.9 and 10.45) - both belts in
# reach; the carton is held in front, along the aisle, never between the belts (an 0.85 m aisle put them out of reach)
FEED_LAT, IND_LAT = -0.15, 0.15  # parcels ride the operator-side half: side guide on the feed; set down near side
# four inductors 1.0 m apart in the 0.85 m aisle: induction keeps up with the docks + opener (three let the feed fill
# and the D02 unloaders stood holding cartons for 25 s: review 009e), and nobody works in a neighbour's space
INDUCTORS = [  # (x, (avatar, vest, hat), pick band in x on the feed queue, place x on the induction belt)
    (9.0, ("Male_Adult_04", "orange", None), (8.5, 9.25), 9.15),
    (8.0, ("Female_Adult_04", "lime", None), (7.5, 8.5), 8.15),  # no cap: her bun came through its crown (review 013)
    (7.0, ("Male_Adult_09", "lime", None), (6.5, 7.5), 7.15),
    (6.0, ("Female_Adult_06", "yellow", None), (5.5, 6.5), 6.15)]


class _Ghost:
    """A queue place still taken by a parcel being lifted off the belt (stopped, never drawn or recorded)."""

    def __init__(self, s, half, until):
        self.s, self.half, self.until = s, half, until
        self.frozen, self.lat, self.state, self.k = True, 0.0, "ghost", -1


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
    TOP_GRIP = False  # loose parcels: side grip from the start
    KEEP_OUT = [(Vector((0.0, -1.0)), -(FEED_Y - 0.21 - 0.16 - 0.03))]  # the queue on the feed beside him
    STRAIGHT_PULL = False
    # lifted clear of the queue and out of its lane: the parcel behind moves up as soon as this one is taken (it
    # slid through the picked one at 3.5 cm lift: QA parcel_overlap)
    PULL_OUT, PULL_LIFT = 0.24, 0.12
    # 0.55 m between the feed and induction belt frames: hands wait close in, arms keep clear of both frames (their
    # left hands rested in the feed frame at 0.97 m: collision check)
    READY = "narrow"
    MAX_HIP_SHIFT = 0.03  # 0.45 m between the belt frames: shifted 12 cm the belly went into the induction frame
    # (the side frames stand 0.41-0.45 m off the centre line and 4 cm above the belt; the feed's end plate at
    # x 9.2-9.26 to 1.14 m: build_hub)
    STATIC_OBST = [(Matrix.Translation((7.1, FEED_Y, 0.0)), (4.4, 0.92, 1.05)),
                   (Matrix.Translation((9.24, FEED_Y, 0.0)), (0.08, 0.92, 1.15)),
                   (Matrix.Translation((10.3, 9.5, 0.0)), (9.4, 0.92, 1.05))]

    def __init__(self, ctx):
        self.ctx = ctx
        self.rnd = random.Random(ctx["seed"] + 303)
        self.DT, self.F0, self.F1 = ctx["DT"], ctx["F0"], ctx["F1"]
        self.T_END = (self.F1 - self.F0) * self.DT
        self.T_STOP = ctx.get("T_STOP", self.T_END)  # (sim-only --scan-extend: work on past the window)
        self.B = ctx["B"]
        self.workers = [IndWorker(k, x, av, band, px) for k, (x, av, band, px) in enumerate(INDUCTORS)]
        self.picks = []
        self.planned = []  # (t_release, s_place, half) on the induction belt
        self.now = 0.0

    def _hold_point(self, w, box, hold):
        """In front of him along the aisle (between the belts there is no room for a carton and a body), a little
        toward the feed, clear of his body (base rule)."""
        fwd = Vector((math.cos(w.heading), math.sin(w.heading)))
        left = Vector((-fwd.y, fwd.x))
        c_, s_ = math.cos(box.yaw), math.sin(box.yaw)
        ext = abs(fwd.x * c_ + fwd.y * s_) * box.dims[0] / 2 + abs(-fwd.x * s_ + fwd.y * c_) * box.dims[1] / 2
        q = Vector((w.pos.x, w.pos.y)) + fwd * (0.22 + ext) + left * 0.06
        return Vector((q.x, q.y, hold.z))

    def _idle_target(self, w):
        return Vector((w.pos.x + 0.3, FEED_Y + FEED_LAT, 1.05))

    def _glance_target(self, w):
        """Every other longer pause: a look at the next inductor along (a nod, a word), else down the line."""
        mates = sorted((o for o in self.workers if o is not w), key=lambda o: abs(o.pos.x - w.pos.x))
        if mates and len(w.picks) % 2 == 0:
            return Vector((mates[0].pos.x, mates[0].pos.y, 1.6))
        return Vector((w.pos.x + 4.0, IND_Y, 1.1))

    def _gap_clear(self, t_rel, s_place, half, gap=0.3):
        ind = self.B["induction"]
        for q in ind.items:  # parcels already on the belt: anywhere from where they are (belt stalled behind the
            # tunnel / merge) to where they will be if it runs (assuming it runs placed parcels onto queued ones)
            pred = q.s + ind.speed * max(t_rel - self.now, 0.0)
            if q.s - (q.half + half + gap) < s_place < pred + (q.half + half + gap):
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
        for g in [g for g in getattr(self, "ghosts", []) if t >= g.until]:  # the lifted parcel is clear now
            if g in feed.items:
                feed.items.remove(g)
            self.ghosts.remove(g)
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
                T_settle = rnd.uniform(0.2, 0.28)  # grip + anticipation dip
                T_pull = rnd.uniform(0.25, 0.35)
                pk.T_label = rnd.uniform(0.3, 0.5)
                pk.T_turn = rnd.uniform(0.9, 1.15)  # a half turn with a step, ~1 s
                pk.T_place = rnd.uniform(0.22, 0.3)
                pk.T_ret = rnd.uniform(0.3, 0.45)
                pk.t = dict(reach=t, settle=t + T_reach, pull=t + T_reach + T_settle,
                            hold=t + T_reach + T_settle + T_pull)
                yaw_end = (0.0 if p.dims[0] >= p.dims[1] else math.pi / 2) + rnd.uniform(-0.12, 0.12)
                yaw_end = follow_turn(yaw_end, box.yaw, w.pos, box.pos, Vector((w.place_x, IND_Y, 1.0)))
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
                    # its place in the queue stays taken until it is lifted clear (the next parcel rolled into it)
                    g = _Ghost(pk.parcel.s, pk.parcel.half, pk.t["hold"] + 0.5)
                    feed.items.append(g)
                    self.ghosts = getattr(self, "ghosts", []) + [g]
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
            if w.state == "turn":
                self._hold_if_busy(w, pk, t, ind, max(pk.parcel.dims[:2]) / 2)
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
BEHIND = CAGE_D / 2 + 0.52  # worker's root behind the cage centre while pushing: chest ~0.3 m clear of the back
# face with the push lean (0.42 put the torso into the cage at the start lean: review 006 P0 #2)
PUSH_RATE = 0.9  # ~0.9 m/s: walking pace (HSE); the walk clip is slowed with it (no foot sliding)
# plan steps: ("push", cage_name, bay_to_clear, cage centre path, earliest start s, loaded) | ("walk", path) | ("stand",)
SCENARIO = "S0"  # set by flow.py
# S4 (mis-load): the first pusher takes the cage meant for D08 into D09's lorry (crosses at ZX5, then along the dock
# face clear of the queued cages); the D09 portal reads it and D08's portal cross-reads it
S4_PLAN = [("push", "out_D08", "S14", [(34.2, 30.6), (34.2, 32.4), (33.05, 33.0), (33.05, 36.98), (37.05, 37.0),
                                         (37.05, 38.4)], True),
           ("walk", [(37.05, 37.58), (39.3, 36.95), (41.05, 36.6), (41.05, 33.0), (38.6, 32.6)]),
           ("stand",)]
PUSHERS = [
    dict(name="worker_cage_1", avatar=("Male_Adult_12", "yellow", None), start=1.0,
         plan=[("push", "out_D08", "S14", [(34.2, 30.6), (34.2, 32.4), (33.05, 33.0), (33.05, 38.4)], True),
               ("walk", [(33.05, 37.58), (33.05, 34.0), (33.3, 32.75), (36.95, 32.6)]),
               # back to staging for the next cage: through the bay he emptied (S14) to behind S15's cage
               ("walk", [(36.95, 32.6), (34.6, 32.0), (34.6, 29.65), (36.9, 29.6)]),
               ("stand",)]),
    dict(name="worker_cage_2", avatar=("Male_Adult_04", None, None), start=-5.0,
         plan=[("push", "out_D11", "S17", [(42.3, 30.6), (42.3, 32.4), (45.05, 33.0), (45.05, 38.4)], True),
               # round the south of the D11 queue cage (42.45, 37.9), then up the gap between it and the empty one
               ("walk", [(45.05, 37.58), (44.1, 36.95), (41.78, 36.95), (41.78, 37.88), (41.05, 37.82)]),
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


def _static_clear(box, top=2.5):
    """True if nothing static rises above the box's base inside its footprint (rays from `top` down): a heap parcel
    placed by a flat reference height sat 7-10 cm inside the opener's / line B's sloped chute meshes (021c hub rows).
    Called while the stations are set up: only the static hub is in the scene then."""
    from mathutils import Vector as V_
    sc_ = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    for q in box.footprint(-0.01) + [box.pos.xy]:
        hit, loc, _n, _i, ob, _m = sc_.ray_cast(dg, V_((q.x, q.y, top)), V_((0.0, 0.0, -1.0)), distance=top)
        if hit and loc.z > box.pos.z + 0.01 and not ob.name.startswith(("flow_parcel_", "worker_")):
            return False
    return True


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
            # palm centre 4.5 cm behind the 32 mm post's centre: at 3 cm one avatar's thicker hand sat 1.2 cm in the
            # post for the whole push (hub run 4, pusher 1 at D08: 109 rows)
            p = Vector((post.x, post.y, HANDLE_Z)) - fwd * 0.045
            inward = c - post
            inward.z = 0
            inward.normalize()
            # fingers OUT round the post's outer side (021c hub: pointed in, the curl took them through the back mesh
            # into the cage, ~4.1 cm for the whole push - 377 rows once hands stopped being skipped)
            out[sd] = (p, C.frame_from(-inward * 0.8 + fwd * 0.3 - UP * 0.2, fwd))
        return out

    def build(self, scene, coll, frames, spec):
        frames = list(frames)
        rep = {}
        fps = int(round(1 / self.DT))
        rep["pushes"] = []
        for k, ps in enumerate(PUSHERS):
            av, vest, hat = ps["avatar"]
            plan = S4_PLAN if (SCENARIO == "S4" and k == 0) else ps["plan"]
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
                    if legs and seq[-1][0] == "walk":  # the walk ends exactly where this push takes hold, the
                        # last 0.35 m along the push direction: he arrives facing the way he pushes (arriving side-on,
                        # the cage was placed ahead of his walking heading - inside the queue cage beside it)
                        d0 = Vector((wpts[1][0] - wpts[0][0], wpts[1][1] - wpts[0][1])).normalized()
                        appr = (wpts[0][0] - d0.x * 0.35, wpts[0][1] - d0.y * 0.35)
                        legs[-1] = (legs[-1][0], list(legs[-1][1][:-1]) + [appr, wpts[0]], legs[-1][2])
                    f_grab = f
                    f += fps  # 1 s to take hold
                    n = frames_for(wpts, PUSH_RATE)
                    legs.append((f, wpts, PUSH_RATE))
                    seq.append(("push", cname, f_grab, f, f + n))
                    end = pts[-1]
                    door = min((29.0, 33.0, 37.0, 41.0, 45.0, 49.0), key=lambda x: abs(x - end[0])) \
                        if end[1] > 38.0 else None
                    rep["pushes"].append(dict(cage=f"cage_rolling_{cname}", door=f"D{int((door - 29) / 4) + 7:02d}"
                                              if door else None, t_end_s=round((f + n - self.F0) * self.DT, 2),
                                              intended="D08" if cname == "out_D08" else (
                                                  "D11" if cname == "out_D11" else None),
                                              worker=ps["name"]))
                    f += n + int(1.3 * fps)  # park, let go, straighten
                elif step[0] == "walk":
                    pts = step[1]
                    if legs:  # starts exactly where the last leg left the worker (plans give the nominal point)
                        pts = [legs[-1][1][-1]] + list(pts[1:])
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
                loc1, h1 = wk.obj.get(f1, (wk.loc0, wk.heading0))
                at_door = (Vector((loc1.x, loc1.y, 0.0)) + yaw_vec3(h1) * BEHIND).y > 38.0
                for g in frames:
                    gg = min(max(g, f0), f1)
                    loc, h = wk.obj.get(gg, (wk.loc0, wk.heading0))
                    c = Vector((loc.x, loc.y, 0.0)) + yaw_vec3(h) * BEHIND
                    if at_door and g > f1 + 2:  # let go at the door, it rolls on ~0.22 m and stops (as a cage does):
                        # parked at arm's length, his turn-away step put a toe 10-11 cm into its base (run 7)
                        u_ = min(1.0, (g - f1 - 2) / 8)
                        c = c + yaw_vec3(h) * 0.22 * (1 - (1 - u_) ** 2)
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
                        flex = 0.1 + 0.08 * max(0.0, 1 - (g - f0) / 10) + 0.04 * max(0.0, 1 - (f1 - g) / 6)
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
    dict(name="worker_walk_2", avatar=("Male_Adult_05", None, None), start=2.0,
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
NEXT_BAG_X = 36.8  # C08, the next chute west
BAG_CAGE = Vector((39.6, 27.0, 0.0))  # its open front faces the aisle (south)
BAGGER = dict(name="worker_bag_1", avatar=("Male_Adult_09", "orange", None), start=-1.2,
              approach=[(34.7, 22.25), (37.2, 21.95), (38.3, 21.72)])  # 0.32 m off the frame's aisle rail
# (at 0.24 m his thigh went into the bulging full bag on the reach: collision check)
BAG_STAND_Y = 21.72
BAG_READY_T = 23.38  # the new bag hangs (chute open again) at this time, as before the drag-out choreography: the
# chute's closed window decides which parcels go round again, and those decide line A's merges (story timings)
SACK_TILT = math.radians(15)  # dragged: leaning toward the puller, its far bottom edge on the floor
DRAG_RATE = 0.75  # backwards with a full sack: slower than a walk (review 013: drag it with both hands on the neck,
# walking backwards; then a two-hand squat lift into the cage)


def _hanging_bag(name, full=True, rnd=None):
    """Woven sack clipped open on the frame rim: rectangular mouth at the rim, body bulging to the floor (full) or
    hanging slack (new / empty). Origin at the frame centre on the floor."""
    rnd = rnd or random.Random(7)
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    hx, hy = 0.47, 0.37
    rings = [(RIM + 0.02, 1.0), (RIM - 0.08, 1.03), (0.62, 1.06 if full else 1.0), (0.32, 1.06 if full else 1.0),
             (0.08, 0.96 if full else 0.99), (0.01 if full else 0.03, 0.8 if full else 0.96)]  # (empty: straight down
    # from the rim's rectangle - narrower below, a parcel landed 12 cm off centre went 8 cm into its wall, run 13)  # (empty: open down to
    # a flat bottom on the floor - tapered to a 0.2 m cap at 0.3 m, a parcel dropped in stuck 8 cm through its walls,
    # run 12)
    n = 24
    loops = []
    for k, (z, sc_) in enumerate(rings):
        loop = []
        for i in range(n):
            a = 2 * math.pi * i / n
            cx, cy = math.cos(a), math.sin(a)
            r = 1.0 / max(abs(cx), abs(cy)) ** 0.85  # rounded rectangle
            lump = 1.0 + (0.03 * math.sin(5 * a + k) if 0 < k < len(rings) - 1 else 0.0)
            sy_ = 1.0 if full or k < 2 else 0.8  # (empty: slack front to back - its calf met it, run 14)
            loop.append(bm.verts.new((cx * r * hx * sc_ * lump, cy * r * hy * sc_ * sy_ * lump,
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
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16, radius=0.5)
    seed = rnd.random() * 10
    # parcel corners pushing the weave out: a few random directions get a sharp bump (a smooth ball read as a
    # snowman in the QA videos)
    corners = [Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.8, 0.5))).normalized() for _ in range(7)]
    for v in bm.verts:
        x, y, z = v.co
        dn = v.co.normalized()
        lump = 1.0 + 0.06 * math.sin(6 * x + seed) * math.sin(4 * z + seed) + 0.04 * math.sin(11 * y + 2 * seed)
        lump += sum(max(0.0, dn.dot(c) - 0.86) * 1.1 for c in corners)
        top = max(0.0, z)  # narrows to the neck at the top
        bot = max(0.0, -z)  # slumps: wider low down, flat where it sits
        w = (1.0 - 0.75 * top ** 2) * (1.0 + 0.3 * bot) * lump
        zz = max(z, -0.36)
        v.co = Vector((x * 0.6 * w, y * 0.5 * w, -0.72 + (zz + 0.5) * 0.7))
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


def _table_items(coll, tx, ty, top):
    """Everyday things on the break table, clear of the seated worker's forearms (x tx-0.42..tx-0.08)."""
    me = bpy.data.meshes.new("break_table_items")
    bm = bmesh.new()
    items = [((tx + 0.42, ty + 0.12), 0.034, 0.22, 0), ((tx + 0.55, ty - 0.04), 0.034, 0.22, 0),  # water bottles
             ((tx + 0.18, ty + 0.2), 0.04, 0.09, 1)]  # a mug
    for (x, y), r, h, mi in items:
        res = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=r, radius2=r * (0.85 if mi == 0 else 1.0),
                                    depth=h, matrix=Matrix.Translation((x, y, top + h / 2)))
        for f in {f for v in res["verts"] for f in v.link_faces}:
            f.material_index = mi
    res = bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((tx - 0.6, ty + 0.18, top + 0.04))
                                @ Matrix.Diagonal((0.22, 0.15, 0.08, 1)))  # lunch box
    for f in {f for v in res["verts"] for f in v.link_faces}:
        f.material_index = 2
    bm.to_mesh(me)
    bm.free()
    for mt in (P._mat("bottle_blue", (0.35, 0.55, 0.75), 0.15), P._mat("mug_white", (0.85, 0.85, 0.82), 0.3),
               P._mat("lunchbox_red", (0.62, 0.12, 0.1), 0.4)):
        me.materials.append(mt)
    coll.objects.link(bpy.data.objects.new("break_table_items", me))


def _hmi_ui_image(name="hmi_ui", W=320, H=200):
    """The sorter HMI's screen, drawn in code: header bar, the loop with its induction, 12 chute tiles (green =
    open, amber = nearly full, red = full / bag change) and status rows. Packed into the .blend."""
    import numpy as np
    img = np.zeros((H, W, 4), dtype=np.float32)
    img[...] = (0.03, 0.05, 0.08, 1.0)

    def rect(x0, y0, x1, y1, rgb):  # top-left origin, like a screen
        img[H - y1:H - y0, x0:x1, :3] = rgb

    rect(0, 0, W, 18, (0.09, 0.27, 0.5))  # header
    for k in range(5):
        rect(8 + k * 26, 6, 26 + k * 26, 12, (0.75, 0.85, 0.95))  # header text blocks
    rect(W - 60, 5, W - 10, 13, (0.2, 0.75, 0.3))  # "RUNNING"
    x0, y0, x1, y1 = 24, 46, 230, 150  # the loop, 3 px outline
    for (a0, b0, a1, b1) in ((x0, y0, x1, y0 + 3), (x0, y1 - 3, x1, y1), (x0, y0, x0 + 3, y1), (x1 - 3, y0, x1, y1)):
        rect(a0, b0, a1, b1, (0.6, 0.65, 0.7))
    rect(x0 + 30, y1, x0 + 34, y1 + 26, (0.6, 0.65, 0.7))  # induction into the loop
    states = ["g"] * 12
    states[6] = "r"  # C07: bag change
    states[3] = states[9] = "a"
    col = {"g": (0.15, 0.7, 0.25), "a": (0.95, 0.65, 0.1), "r": (0.9, 0.15, 0.1)}
    for k, st in enumerate(states):  # chute tiles along the loop's top side
        cx = x0 + 10 + k * 17
        rect(cx, y0 - 16, cx + 12, y0 - 4, col[st])
    for r_ in range(6):  # status rows
        rect(244, 40 + r_ * 18, 244 + 30 + (r_ * 13) % 40, 46 + r_ * 18, (0.55, 0.6, 0.65))
        rect(290, 40 + r_ * 18, 312, 46 + r_ * 18, (0.15, 0.7, 0.25) if r_ != 2 else (0.95, 0.65, 0.1))
    im = bpy.data.images.new(name, W, H, alpha=False)
    im.pixels = img.ravel().tolist()
    im.pack()
    return im


def _hmi_screen_ui(ob, mat_name):
    """Map the UI image onto the screen faces of the HMI (planar UV in the screen's own plane)."""
    me = ob.data
    idx = next((i for i, m in enumerate(me.materials) if m and m.name.startswith(mat_name)), None)
    if idx is None:
        return
    polys = [pl for pl in me.polygons if pl.material_index == idx]
    if not polys:
        return
    nrm = sum((pl.normal for pl in polys), Vector()).normalized()
    u_ax = Vector((0, 0, 1)).cross(nrm).normalized()
    v_ax = nrm.cross(u_ax).normalized()
    vs = {i for pl in polys for i in pl.vertices}
    us = [me.vertices[i].co.dot(u_ax) for i in vs]
    vv = [me.vertices[i].co.dot(v_ax) for i in vs]
    uv = me.uv_layers.get("ui") or me.uv_layers.new(name="ui")
    for pl in polys:
        for li in pl.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = ((co.dot(u_ax) - min(us)) / max(max(us) - min(us), 1e-6),
                              (co.dot(v_ax) - min(vv)) / max(max(vv) - min(vv), 1e-6))
    m = bpy.data.materials.new("hmi_screen_ui")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = _hmi_ui_image()
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = "ui"
    nt.links.new(uvn.outputs["UV"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 1.6
    bsdf.inputs["Roughness"].default_value = 0.25
    me.materials[idx] = m


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
        t += 0.8  # down to the tied neck (the sack stands on the floor); then he walks back dragging it out under the
        # front rail (standing at the frame and pulling it to him, its belly went 6.5 cm into his calves: run 7-9)
        # west of the XO-1 stair (its stringer stands at x 39.1 from y 19.6 to 23.2): out, up the aisle, to the cage,
        # dragging the sack behind (lifting a full sack over the 0.9 m rim needs it at 1.6 m; carried in front or at
        # the side it went through his legs: collision check)
        self.carry_path = [(BAG_X, BAG_STAND_Y), (BAG_X + 0.2, 22.25), (38.75, 23.5), (BAG_CAGE.x, 26.15)]
        # the tied sack's neck when it sits on the sacks already in the cage, well in from the open front
        self.rest_neck = Vector((BAG_CAGE.x, BAG_CAGE.y + 0.05, 0.17 + 0.48 + 0.8))  # ON the lumpy sacks already
        # in the cage (0.7 sank it 9 cm into them: collision check)
        T["walk_cage"] = t
        t += L(self.carry_path) / (v * DRAG_RATE)  # walking backwards, dragging it
        T["at_cage"] = t
        t += 0.3
        T["place"] = t
        t += 0.9  # stood upright in front of its cage (staged for loading) and let go
        T["released"] = t
        t += 0.3
        # (the spare is taken 8 cm further back from the frame: turning there his stepping foot went 3.6 cm into
        # C08's sacks, run 7)
        self.staged = None  # (neck, yaw) of the full sack stood at its cage
        self.back_path = [(BAG_CAGE.x, 26.15), (BAG_CAGE.x + 0.65, 25.75), (BAG_CAGE.x + 0.4, 24.85), (38.75, 23.5),
                          (BAG_X - 0.45, 22.15), (BAG_X - 0.62, 21.80)]  # (round the sack he left in front of him)
        self.center_path = [(BAG_X - 0.62, 21.80), (BAG_X - 0.3, 21.77), (BAG_X - 0.02, BAG_STAND_Y)]
        T["walk_back"] = t
        t += L(self.back_path) / v
        T["at_spare"] = t
        t += 0.5
        T["take_spare"] = t
        t += 0.6
        T["step_in"] = t  # spare in hand, a step along to the middle of the frame
        t += L(self.center_path) / (v * 0.8) + 0.1
        T["to_rim"] = t
        t += 0.9
        T["clip_new"] = t
        t = max(BAG_READY_T, t + 1.0)
        T["ready"] = t  # light green, the sorter may divert here again
        t += 0.8
        T["done"] = t
        t += 0.4
        # then on to the next chute along (C08) to check how full its bag is: no 6 s of standing idle (review 006)
        # (he stands there to the window's end: at 21.72 his idle arm swing put the left forearm into C08's frame
        # rim, 30 rows in hub run 4; 12 cm further back)
        # a step back from the frame first, turning as he goes (turning on the spot his first step went 8.1 cm into
        # the new bag, run 7)
        self.next_path = [(BAG_X - 0.02, BAG_STAND_Y), (BAG_X - 0.15, BAG_STAND_Y + 0.4), (NEXT_BAG_X, 21.95)]
        T["walk_next"] = t
        T["at_next"] = t + L(self.next_path) / v
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
        hook = Vector((BAG_X - 0.72, FRAME_Y1 - 0.08, 0.98))  # folded spare on the front-west post, chest high (at -0.62
        # his right arm went through it while he worked the rim clips, run 9)
        # (outside the post: 9 cm further in it touched his right arm at the frame - collision check):
        # taken from where the bagger stands, without bending over the frame
        hook_o = hook - Vector((0.4, 0.0, 0.0))  # the folded bag hangs west of the hook (its mesh runs 0.4 m +x from
        # its origin: from the hook point it hung back over the frame, where his right hand works the clips, run 12)
        spare.location, spare.rotation_euler = hook_o, (math.pi / 2, 0, math.pi / 2)
        f_lift, f_new = F(T["lift"]), F(T["to_rim"])  # (the folded spare becomes the hung bag as he reaches the rim:
        # left floating in front of him for 0.3 s his hands went through it, run 9)
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
        legs = [(F(T["walk_in"]), BAGGER["approach"], 1.0), (F(T["walk_cage"]), self.carry_path, DRAG_RATE, 0.9, True),
                (F(T["walk_back"]), self.back_path, 1.0, 0.7), (F(T["step_in"]), self.center_path, 0.8, 0.5),
                (F(T["walk_next"]), self.next_path, 1.0, 0.8)]
        spans = wk.walk(legs, frames)
        rep["legs"] = spans
        # carried / held objects: the tied sack follows the hands' authored pose (object first, hands on it)
        rim_L = Vector((BAG_X - 0.17, FRAME_Y1 + 0.05, RIM + 0.12))  # either side of the front clip, palms ON the
        rim_R = Vector((BAG_X + 0.17, FRAME_Y1 + 0.05, RIM + 0.12))  # rim tube's outer side, past the bag's lip
        # folded over it (on top they went 2 cm into the lip, runs 7-9; at
        # +4.5 cm the fingers were 1.8-2.4 cm into the full bag's lip and the frame, run 7)
        neck_rest = frame_c + Vector((0, 0.05, RIM + 0.15))  # neck of the full bag at the rim, centre
        tv = [v.co.copy() for v in tied.data.vertices]

        def neck_z(th):  # neck height with the sack leaning th toward the puller, its lowest point on the floor
            return 0.01 - min(-v.x * math.sin(th) + v.z * math.cos(th) for v in tv)
        neck_floor = Vector((BAG_X, (FRAME_Y0 + FRAME_Y1) / 2, neck_z(0.0)))  # tied, standing in the frame
        pull_end = Vector((BAG_X, FRAME_Y1 - 0.06, neck_z(SACK_TILT)))  # under the front rail
        pull_r = BAG_STAND_Y - pull_end.y
        # dragged in FRONT of him while he walks backwards (review 013: a one-handed carry of a full sack at the
        # side is not believable), both hands on the neck, the sack leaning toward him on its far bottom edge
        DRAG_ANG, DRAG_R = 0.0, 0.75  # (0.55: the sack stood against his toes and calf at the cage, run 15)
        rail = [(Matrix.Translation((BAG_X, FRAME_Y1, RIM - 0.03)), (1.04, 0.06, 0.06))]  # the frame's front rail
        dropped, trail = None, None
        for f in frames:
            t = (f - self.F0) * self.DT
            loc, h = wk.obj.get(f, (wk.loc0, wk.heading0))
            fwd = yaw_vec3(h)
            hands, fingers, flex, yaw, look = None, None, 0.03, 0.0, Vector((loc.x, loc.y, 1.5)) + fwd * 3 - UP * 0.3
            neck, sack, obst, drop_ = None, None, None, 0.0
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
                else:  # the sack (tied: a cut) slumps to the floor; down to its neck, then pull it under the rail
                    obst = rail
                    u = (t - T["lift"]) / 0.8
                    if u < 1.0:
                        k_ = C.smooth(u)
                        nh = self._neck_hold(neck_floor, h)
                        rh = self._rim_hold(rim_L, rim_R)
                        hold = {}
                        for sd in ("L", "R"):
                            q0, q1 = rh[sd][1].to_quaternion(), nh[sd][1].to_quaternion()
                            if q0.dot(q1) < 0:
                                q1.negate()
                            hold[sd] = (rh[sd][0].lerp(nh[sd][0], k_) + UP * 0.08 * math.sin(math.pi * k_),
                                        q0.slerp(q1, k_).to_matrix())
                        sack = (neck_floor, 0.0, math.pi / 2)
                        flex = 0.45 + 0.25 * k_
                    else:
                        k_ = C.smooth(min(1.0, u - 1.0))
                        tl = SACK_TILT * k_
                        nk = neck_floor.lerp(pull_end, k_)
                        nk.z = neck_z(tl)
                        hold = self._neck_hold(nk, h)
                        sack = (nk, tl, math.pi / 2)
                        flex = 0.7 - 0.2 * k_
                    hands, fingers = ("grip", hold), "flat"
                    look = neck_floor
            elif T["walk_cage"] <= t < T["released"]:  # drag it behind, then swing it up into the cage
                side_r = Vector((math.sin(h), -math.cos(h), 0.0))  # his right

                def local(ang, r):  # angle from his front toward his right
                    return Vector((loc.x, loc.y, 0.0)) + (fwd * math.cos(ang) + side_r * math.sin(ang)) * r
                if t < T["at_cage"]:
                    u = C.smooth(min(1.0, (t - T["walk_cage"]) / 1.0))
                    nk = neck_floor.lerp(local(DRAG_ANG, DRAG_R), u)  # out from the frame as he backs away
                    tl_ = SACK_TILT * u  # (leaning toward him as it comes, not snapped to it)
                    nk.z = neck_z(tl_)
                    to_him = Vector((loc.x - nk.x, loc.y - nk.y, 0.0))
                    yaw_s = math.atan2(to_him.y, to_him.x)  # its top leans toward him
                    sack = (nk, tl_, yaw_s)
                    hands, fingers = ("grip", self._neck_hold(nk, h)), "flat"
                    flex = 0.45  # bent over the sack, both hands on its neck
                    look = nk + UP * 0.2 if (t - T["walk_cage"]) % 3.0 < 2.2 else Vector((loc.x, loc.y, 1.4)) - fwd
                    trail = (nk.copy(), yaw_s)
                else:  # at its cage: stood upright where it is, in front of the cage, staged for loading (lifted
                    # over him into the cage - swung 180 deg round him, the cage behind - it touched his head, went
                    # 7 cm into the cage's side bars and jumped 0.27-0.48 m a frame: runs 7-11)
                    u = C.smooth((t - T["place"]) / (T["released"] - T["place"])) if t > T["place"] else 0.0
                    if self.staged is None:
                        self.staged = (Vector((trail[0].x, trail[0].y, neck_z(0.0))), trail[1])
                    nk = self.staged[0].copy()
                    nk.z = neck_z(SACK_TILT * (1 - u))
                    sack = (nk, SACK_TILT * (1 - u), self.staged[1])
                    hands, fingers = ("grip", self._neck_hold(nk, h)), "flat"
                    flex = 0.45 - 0.2 * u
                    look = nk
                neck = sack[0]
                dropped = neck.copy()
            elif T["released"] <= t < T["walk_back"]:
                u = C.smooth((t - T["released"]) / (T["walk_back"] - T["released"]))
                hands = ("unblend", u, self._neck_hold(dropped, h))
                flex = 0.2 * (1 - u)
                look = Vector((BAG_CAGE.x, BAG_CAGE.y, 0.6))
            elif t >= T["walk_next"]:  # on to C08: a look at its bag on the way, then at it
                look = Vector((NEXT_BAG_X, 21.0, 0.75)) if t > T["walk_next"] + 0.6 else look
            elif T["at_spare"] <= t < T["done"]:  # spare off the hook, clip it open on the rim
                yaw = (-math.pi / 2 - h + math.pi) % (2 * math.pi) - math.pi
                if t < T["take_spare"]:
                    look = hook
                elif t < T["step_in"]:
                    u = C.smooth((t - T["take_spare"]) / (T["step_in"] - T["take_spare"]))
                    sp_c = hook_o + Vector((0.2, 0.0, 0.1))  # (its middle: it hangs west of the hook point; palms
                    # 7 cm over its top - at 3 cm the fingertips went into it, run 15)
                    hands = ("blend", u, self._rim_hold(sp_c + Vector((-0.06, 0.0, 0.0)), sp_c + Vector((0.06, 0.0, 0.0))))
                    flex = 0.15 * u
                    look = hook
                elif t < T["to_rim"]:  # carrying the folded bag to the middle of the frame
                    held = Vector((loc.x, loc.y, 1.1)) + yaw_vec3(-math.pi / 2) * 0.42
                    # the folded bag lies flat (0.4 x 0.5 x 0.06, its origin at a corner): centred on his hands, its top
                    # just under the palms, 0.42 m out - chest high over the frame's rail (0.92) and clear of his thighs
                    # and belly (it hung 13 cm under his hands at 0.75-0.81 m, over the rail and into his thigh: run 7);
                    # off the hook over 0.3 s (it jumped 0.2 m)
                    u_sp = C.smooth(min(1.0, (t - T["step_in"]) / 0.6))  # (0.3 s: 2.5 m/s off the hook, run 13)
                    spare.location = hook_o.lerp(held + Vector((-0.2, 0.0, -0.06)), u_sp)
                    spare.keyframe_insert("location", frame=f)
                    sp_c = spare.location + Vector((0.2, 0.0, 0.1))  # his palms on it where it is (on the hook's
                    # east end they met it as it came off, run 14)
                    hands = ("grip", self._rim_hold(sp_c + Vector((-0.06, 0, 0)), sp_c + Vector((0.06, 0, 0))))
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
                    spare.location = hook_o
                    spare.keyframe_insert("location", frame=f)
            if sack is not None:  # (location = neck, lean toward the puller about its own y, yaw)
                tied.location, tied.rotation_euler = sack[0], (0.0, sack[1], sack[2])
                tied.keyframe_insert("location", frame=f)
                tied.keyframe_insert("rotation_euler", frame=f)
            elif dropped is not None and t >= T["released"]:
                tied.location = self.staged[0]
                tied.keyframe_insert("location", frame=f)
            elif t < T["lift"]:
                tied.location = neck_floor  # (hidden till the lift; at the rim it showed there for a frame and
                # jumped 0.42 m to the floor, run 11)
                tied.keyframe_insert("location", frame=f)
            wk.set_trunk(f, yaw, flex, drop_)
            if hands is not None:  # the clip's own arms ramp onto the hold (no jump)
                if hands[0] == "grip":
                    wk.set_hands(f, hands[1], fingers=fingers, obstacle=obst)
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
        """Both palms on the tied neck, one a little above the other, facing each other across it, fingers up
        along the tie (fists 3.5 cm from its axis were inside the 4-5 cm neck: collision check)."""
        fwd = yaw_vec3(h)
        left = Vector((-fwd.y, fwd.x, 0))
        # fingers forward and a little down round the neck, so the forearm rises back toward him (fingers up put
        # the forearm down into the sack's shoulders: collision check)
        # (3 cm higher, on the tie above the shoulders: the lower right fist was in the sack up to 7.2 cm at the lift
        # and the swing into the cage, hub run 4)
        return {"L": (neck + left * 0.072 + UP * 0.04, C.frame_from(fwd * 0.9 - UP * 0.25, -left)),
                "R": (neck - left * 0.072 + UP * 0.02, C.frame_from(fwd * 0.9 - UP * 0.25, left))}

    def _stack_lights(self, coll, frames, f_green):
        """A 3-lamp stack light (green / amber / red) on the right side wall of every chute, near the lip."""
        mats = {k: bpy.data.materials.get(f"dock_lamp_{k}") for k in ("red", "green", "off")}
        amber_off = mats["off"]
        made = []
        for k in range(12):
            cid = f"C{k + 1:02d}"
            x = 48.6 - 1.5 * k
            base = Vector((x + 0.58, 20.55, 1.32))  # (0.52: a carton sliding down the chute's outer half
            # hit C08's mast, 9.4 cm, hub run 4)
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
OPENER = dict(name="worker_open_1", avatar=("Female_Adult_07", "lime", None), at=(5.8, 20.55), start=-0.6)
BENCH_X0, BENCH_Y0, BENCH_Y1, BENCH_Z = 6.2, 19.0, 22.0, 0.9


class BagOpener(Docks):
    TOP_GRIP = True  # in the heap its neighbours touch its sides: palms on top until it is lifted clear, then round
    # to the sides (a side grip put the hands into the next parcels: collision check)
    KEEP_OUT = []
    STRAIGHT_PULL = False
    PULL_OUT, PULL_LIFT = 0.2, 0.15  # lifted off the heap (it slid through the parcels around it)
    TURN_LIFT = 0.22  # ...and carried over the rest of the heap on the turn to the collector
    HOLD_LIFTED = True
    HEAP_PULL = True  # straight up until clear of the parcels round it, then out (diagonal: through them)
    HOLD_TURN = 1.0  # held ~57 deg round toward the collector / belt (to his left), beside the heap
    # empty hands wait west of the heap (overhanging parcels reach 7 cm past the bench edge; at the belly they rested
    # in the heap: collision check)
    READY_KEEP = [(Vector((-1.0, 0.0)), -(BENCH_X0 - 0.12))]

    @staticmethod
    def _heap_clear(box, rest, reach, toward):
        """Height the carton's bottom must reach before it moves sideways: 3 cm over every heap parcel in its way
        toward the worker (a diagonal pull slid it through its neighbours: QA parcel_overlap up to 24 cm; clearing
        every neighbour all round lifted it to his face: held_clip_head)."""
        top = box.pos.z
        u = toward.normalized()
        for b, _ in rest:
            d = b.pos.xy - box.pos.xy
            ra = max(b.dims[:2]) / 2 + max(box.dims[:2]) / 2
            along, across = d.dot(u), abs(d.x * u.y - d.y * u.x)
            if -ra * 0.5 < along < reach + ra and across < ra + 0.03:
                top = max(top, b.pos.z + b.dims[2] + 0.03)
        return top
    def __init__(self, ctx):
        self.ctx = ctx
        self.rnd = random.Random(ctx["seed"] + 909)
        self.DT, self.F0, self.F1 = ctx["DT"], ctx["F0"], ctx["F1"]
        self.T_END = (self.F1 - self.F0) * self.DT
        self.T_STOP = ctx.get("T_STOP", self.T_END)  # (sim-only --scan-extend: work on past the window)
        self.B = ctx["B"]
        w = IndWorker(0, OPENER["at"][0], OPENER["avatar"], (0, 0), 0)
        w.pos = Vector((OPENER["at"][0], OPENER["at"][1], 0.0))
        w.heading = math.radians(25)  # mostly at the bench, turned a little up the line: the turn to the collector
        # (behind-left) then always goes through the front-left, never flips side
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
            p.state = "held"
            # a spilled heap: each parcel lands where it rests lowest, on top of whatever it overlaps (the old
            # 12 x 33 cm grid put parcels inside each other: QA parcel_overlap)
            best = None
            for _ in range(40):
                x = BENCH_X0 + rnd.uniform(0.15, 0.6)  # spilled toward the aisle edge
                y = OPENER["at"][1] + rnd.uniform(-0.55, 0.45)
                cand = Box(x, y, BENCH_Z, tuple(p.dims), rnd.uniform(-0.6, 0.6) + math.pi / 2)
                z = max([b.pos.z + b.dims[2] for b, _ in self.pile if b.overlaps_xy(cand)], default=BENCH_Z)
                cand.pos.z = z
                if not _static_clear(cand):
                    continue
                if best is None or z < best[0] - 1e-6:
                    best = (z, cand)
            if best is None:  # (nowhere clear in 40 tries: the last one, as before)
                best = (z, cand)
            box = best[1]
            box.pos.z = best[0]
            self.pile.append((box, p))
        # top of the heap first (a parcel is never taken from under another), then nearest
        self.pile.sort(key=lambda bp: (-round(bp[0].pos.z, 3), (bp[0].pos - w.pos).xy.length))
        self.sack_pos = Vector((BENCH_X0 + 0.95, OPENER["at"][1] + 0.1, BENCH_Z))

    def _idle_target(self, w):
        return Vector((BENCH_X0 + 0.4, w.pos.y, 0.95))

    def _glance_target(self, w):
        return Vector((5.0, w.pos.y - 3.0, 1.0))  # down the collector

    def _gap_clear(self, t_rel, s_place, half, gap=0.35):
        col = self.B["collector"]
        for q in col.items:  # from where they are (stalled) to where they will be (running): see Inductors
            pred = q.s + col.speed * max(t_rel - self.now, 0.0)
            if q.s - (q.half + half + gap) < s_place < pred + (q.half + half + gap):
                return False
        for (tr, sp, hh) in self.planned:
            if abs(sp + col.speed * (t_rel - tr) - s_place) < hh + half + gap:
                return False
        return True

    def step(self, t):
        self.now = t
        if not self.workers:  # unstaffed (flow --unstaff opener): the heap waits
            return
        col = self.B["collector"]
        rnd = self.rnd
        w = self.workers[0]
        pk = w.cur
        if w.state == "idle":
            if t < w.free_at or not self.pile or t > getattr(self, 'T_STOP', self.T_END) + 1.0:
                return
            box, p = self.pile.pop(0)
            pk = Pick(box, w)
            pk.parcel = p
            box.pick = pk
            pk.lift_z = self._heap_clear(box, self.pile, self.PULL_OUT + 0.05, (w.pos - box.pos).xy)
            T_reach = rnd.uniform(0.7, 1.0)
            T_settle = rnd.uniform(0.2, 0.28)  # grip + anticipation dip
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
            yaw_end = follow_turn(yaw_end, box.yaw, w.pos, box.pos, ppos)
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
        if w.state == "turn":
            self._hold_if_busy(w, pk, t, col, max(pk.parcel.dims[:2]) / 2)
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
        if not self.workers:
            return
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
        if getattr(self, "unstaffed", False):  # flow --unstaff opener (021d review): nobody on the bench, two full
            # tied bags lying on it waiting to be opened (not an opened sack and a spilled heap: abandoned mid-task)
            for k_, (dx, dy, rz) in enumerate(((0.45, -0.4, 1.5), (0.6, 0.45, 1.75))):
                nm = f"waiting_sack_bench1_{k_}"
                sk = bpy.data.objects.new(nm, _tied_sack(nm, self.rnd))
                coll.objects.link(sk)
                sk.rotation_euler = (math.pi / 2, 0.0, rz)  # on its side
                sk.location = Vector((BENCH_X0 + dx, OPENER["at"][1] + dy, 0.0))
                bpy.context.view_layer.update()
                lo = min((sk.matrix_world @ v.co).z for v in sk.data.vertices)
                sk.location.z += BENCH_Z + 0.002 - lo  # resting on the bench top
            rep["unstaffed"] = "bag opener: two full bags waiting on the bench (S2 render, 021d review)"
            return rep
        sk = bpy.data.objects.new("opened_sack_bench1", sack_mesh(self.rnd, 0.7, 0.5, 0.18))
        coll.objects.link(sk)
        sk.location, sk.rotation_euler = self.sack_pos, (0, 0, math.pi / 2 + 0.2)
        self.animate(scene, coll, frames, rep, role="bag_opening")
        return rep


# ==================================================================================================== line A (b), mocap
class MocapInductors:
    """Line A option (b) (reviews 015 / 016, M5): per inductor a gravity roller table on his left, fed by a diverter
    paddle off the feed line, and his own induct belt into belt A. In the flow simulation this station only TIMES the
    work: the mocap engine's Planner (mocap/inductor.py) lays the pick / place clips one carton at a time as parcels
    reach the table's end stop, so grasp, lift and release fall where the clips put them. The flow owns the parcel
    on the feed, on the table and from the release on the induct belt; the engine owns it in the hands (its bake
    lands with the workers at M5 step 3)."""
    DIVERT_S = 0.6  # the next parcel is diverted 0.6 s after the lift (the bench: hands clear of the table head)
    CURTAIN_S = 0.3  # the induct belt starts once the hands are out of the light curtain: the engine found 0.3 s
    # clear in 36 of 37 bench set-downs; at step 3 it is handed this value (station curtain_s) and reports the rest
    PLACE_S = 0.34  # set down 0.34 m along the induct belt (the engine's set-down, 12 cm further along since run 13:
    # at 0.22 the release eased each carton back onto the belt's start frame, 4 cm, run 15)
    LOOK_S = 0.7  # the hands are over the belt from 0.7 s before the release (inductor.Planner gap control)
    MAX_WAIT_S = 1.5  # review 017 #3: nobody stands holding a box waiting; at most 1.5 s extra over the belt
    MOUTH_HALF = 0.30  # the mouth cut in the feed's frame: table 0.5 m + 5 cm each side. A parcel whose footprint
    # (along the feed) lies inside it can be pushed in from where it is - queued parcels never stop centred on it

    def __init__(self, ctx):
        import importlib.util
        import sys
        from pathlib import Path
        import line_a_geom
        mdir = Path(__file__).resolve().parent / "mocap"
        sys.path.insert(0, str(mdir))  # (retarget, its import)
        # by file: another top-level "inductor" module shadows it on Blender's path
        spec_ = importlib.util.spec_from_file_location("mocap_inductor", mdir / "inductor.py")
        I = importlib.util.module_from_spec(spec_)
        spec_.loader.exec_module(I)
        self.I = I
        self.F0, self.F1 = ctx["F0"], ctx["F1"]
        self.T_END = (self.F1 - self.F0) * ctx["DT"]
        self.T_STOP = ctx.get("T_STOP", self.T_END)  # (sim-only --scan-extend: work on past the window)
        self.ctx, self.B, self.DT = ctx, ctx["B"], ctx["DT"]
        self.la, self.mouths, self.induct, self.merges = line_a_geom.derive(ctx.get("line_a"))
        picks, places = I.candidates()
        self.st = []
        for k, x in enumerate(self.la["stations_x"]):
            pk_k = picks[k % len(picks):] + picks[:k % len(picks)]  # neighbours never start on the same take
            P_ = I.Planner(dict(ratio=(0.92, 1.12)), random.Random(ctx["seed"] * 100 + k), pk_k, places)
            self.st.append(dict(k=k, x=x, P=P_, table=self.B[f"table_{k}"], ind=self.B[f"induct_{k}"],
                                free_at=-1e9, active=[], cycles=[]))
        self.diverts = []
        self.conflicts = []
        self.overflows = []
        self.ghosts = []

    def step(self, t):
        """One simulation step (after the belts moved)."""
        feed = self.B["feed"]
        for g_ in [g_ for g_ in self.ghosts if t >= g_.until]:
            if g_ in feed.items:
                feed.items.remove(g_)
            self.ghosts.remove(g_)
        for st in self.st:
            tb, P_ = st["table"], st["P"]
            # 1. diverter: an empty table takes the parcel passing (or queued at) its mouth; world pose kept
            if not tb.items and t >= st["free_at"]:
                mx = self.mouths[st["k"]]
                for q in sorted(feed.items, key=lambda q_: -q_.s):
                    if getattr(q, "frozen", False) or getattr(q, "state", "belt") != "belt":
                        continue
                    ot_ = getattr(q, "only_table", None)
                    if ot_ is not None and feed.at(q.s)[0].x > self.mouths[ot_] + 0.35:
                        q.only_table = ot_ = None  # it missed its table: any one takes it (never stuck at the head)
                    if ot_ not in (None, st["k"]):
                        continue  # meant for another inductor (S5: the twins swap order through line A)
                    pos, yaw = feed.at(q.s)
                    ya_ = yaw + q.yaw_off  # its footprint along the feed, as it lies (yawed), 3 cm clear of the frame ends
                    ext_ = 0.5 * (q.dims[0] * abs(math.cos(ya_)) + q.dims[1] * abs(math.sin(ya_)))
                    x_prev = feed.at(getattr(q, "prev_s", q.s))[0].x
                    crossed = x_prev < mx - 1e-6 <= pos.x  # the photo-eye at the mouth: the paddle fires as it passes
                    lim_ = min(self.MOUTH_HALF - 0.03, self.la["table_w"] / 2 - 0.02)  # the table's side guides
                    if not crossed and abs(pos.x - mx) + ext_ > lim_:
                        continue
                    if ext_ > lim_:
                        continue  # wider than the table as it lies: rides on (the feed's guide squares it)
                    # (crossed: kept where it is - snapped back onto the mouth it jumped up to 0.32 m in a frame,
                    # run 12; the table's guides centre it, lat_to)
                    pos = pos + Vector((-math.sin(yaw), math.cos(yaw), 0.0)) * q.lat
                    feed.items.remove(q)
                    # its place in the queue stays taken while the paddle pushes it across (the next parcel moved up
                    # into it: collision check, 5-7 cm)
                    g_ = _Ghost(q.s, q.half, t + 0.6)
                    feed.items.append(g_)
                    self.ghosts.append(g_)
                    p0, tyaw = tb.at(0.0)
                    q.belt, q.s = tb.name, max(0.0, p0.y - pos.y)
                    q.lat, q.lat_to = pos.x - mx, 0.0  # (the table runs -y: its left is +x - with -x the parcel was
                    # mirrored across the mouth, up to 0.32 m in a frame, run 13) side guides centre it
                    q.yaw_off += yaw - tyaw
                    tb.items.append(q)
                    self.diverts.append((round(t, 2), st["k"], q.k))
                    break
            # 2. a parcel resting at the end stop: the next pick / place cycle (one at a time, after the last)
            for q in tb.items:
                if not getattr(q, "planned", False) and q.s >= tb.length - q.half - 0.02 - 1e-6:
                    if not P_.segs:
                        P_.t = t
                    c = P_.cycle(ready=t)
                    c.update(parcel=q, ready=t, state="table", stop=self._pose(tb, q))
                    q.planned, q.frozen = True, True
                    st["active"].append(c)
                    st["cycles"].append(c)
            for c in list(st["active"]):
                q = c["parcel"]
                if c["state"] == "table" and t >= c["lift"] - 1e-6:  # lifted: off the table, in the hands
                    if q in tb.items:
                        tb.items.remove(q)
                    q.state, q.belt = "held", None
                    st["free_at"] = c["lift"] + self.DIVERT_S
                    c["state"] = "held"
                if c["state"] == "held" and t >= c["release"] - self.LOOK_S - 1e-6:
                    # the spot on his induct belt still taken (the belt backs up while belt A has no gap): he holds
                    # the carton over the belt a step longer (the planner shifts his place clip and what follows)
                    ind = st["ind"]
                    if not ind.free_at(self.PLACE_S, q.half):
                        if c.get("held_extra", 0.0) < self.MAX_WAIT_S - 1e-6:
                            P_.delay(c["n"], self.DT, st["cycles"])
                            c["held_extra"] = round(c.get("held_extra", 0.0) + self.DT, 2)
                        elif not c.get("overflow"):  # 017 #3: he would put it back at the table's stop and wait
                            c["overflow"] = True  # hands off (not built yet: counted, must stay 0)
                            self.overflows.append((round(t, 2), st["k"], q.k))
                if c["state"] == "held" and t >= c["release"] - 1e-6:  # set down on his induct belt
                    ind = st["ind"]
                    if not ind.free_at(self.PLACE_S, q.half):
                        self.conflicts.append((round(t, 2), st["k"], q.k))
                    q.belt, q.s, q.state, q.lat, q.lat_to = ind.name, self.PLACE_S, "belt", 0.0, None
                    q.frozen, q.unfreeze_at = True, c["release"] + self.CURTAIN_S
                    q.yaw_off = 0.0
                    ind.items.append(q)
                    c["state"] = "placed"
                    st["active"].remove(c)
            for q in st["ind"].items:
                if getattr(q, "unfreeze_at", None) is not None and t >= q.unfreeze_at:
                    q.frozen, q.unfreeze_at = False, None
        for q in feed.items:
            if not isinstance(q, _Ghost):
                q.prev_s = q.s

    @staticmethod
    def _pose(belt, q):
        """(bottom centre, 3x3 rotation) of a parcel on a belt, as flow.py keys it."""
        pos, yaw = belt.at(q.s)
        pos = pos + Vector((-math.sin(yaw), math.cos(yaw), 0.0)) * q.lat
        R_ = Matrix.Rotation(yaw + q.yaw_off, 3, "Z")
        if belt.sloped:
            hl = (q.dims[0] * abs(math.cos(q.yaw_off)) + q.dims[1] * abs(math.sin(q.yaw_off))) / 2
            z_, pitch = belt.rest(q.s, hl)
            pos.z = z_
            R_ = Matrix.Rotation(-pitch, 3, Vector((-math.sin(yaw), math.cos(yaw), 0.0))) @ R_
        return pos.copy(), R_, yaw + q.yaw_off

    AVATARS = [("Male_Adult_04", "yellow"), ("Male_Adult_12", "orange"), ("Male_Adult_09", "lime"),
               ("Male_Adult_05", "yellow")]  # flat shoes (014c #5); the women fail the grip / hips still (016 #6)

    def build(self, scene, coll, rb, fps, lead_s=3.0):
        """M5 step 3: each inductor on mocap. His timeline is his Planner's, cut at the last pick starting >= lead_s
        before frame F0 (rounded up to a frame, so that pick covers the first frame); the engine solves it with the
        parcels' own sizes and stop poses and the flow's belt-start delay. Returns {parcel: {frame: track entry}}
        for the frames each parcel is in his hands (grasp .. release) + per-worker QA rows."""
        import copy
        import line_a_worker as LW
        import retarget as R_
        I = self.I
        held, rep_ = {}, {}
        for st in self.st:
            k, x0 = st["k"], st["x"]
            P_ = st["P"]
            if not P_.segs:
                continue
            av, vest = self.AVATARS[k]
            arm, body = LW.import_avatar(scene, rb, av, vest, f"worker_induct_{k + 1}", x0, LW.OP_Y)
            for o in [arm] + list(arm.children):
                for c_ in list(o.users_collection):
                    c_.objects.unlink(o)
                coll.objects.link(o)
            tc = LW.trunk_clearance(arm, body)
            rig = R_.setup(arm, I.take(P_.picks[0]["take"]))
            sd = LW.station(x0, tc)
            sd["curtain_s"] = self.CURTAIN_S
            picks_ = [i for i, sg in enumerate(P_.segs) if sg["kind"] == "pick" and sg["out0"] <= -lead_s]
            i0 = picks_[-1] if picks_ else 0
            tb = math.ceil(P_.segs[i0]["out0"] * fps - 1e-6) / fps
            segs = copy.deepcopy(P_.segs[i0:])
            for sg in segs:
                sg["out0"] -= tb
                sg["out1"] -= tb
            nF = int(round((self.T_END - tb) * fps)) + 1
            frame0 = self.F0 + int(round(tb * fps))
            parcels, byn = {}, {}
            for c in st["cycles"]:
                q = c["parcel"]
                pos, R3, yaw = c["stop"]
                ctr = pos + R3 @ Vector((0.0, 0.0, q.dims[2] / 2))
                parcels[c["n"]] = dict(dims=tuple(q.dims), at=tuple(ctr), yaw=yaw,
                                       grip="one_hand" if q.kind == "mailer" else None)
                byn[c["n"]] = c
            res = I.build(rig, segs, sd, parcels, nF, fps, frame0=frame0, name=f"inductor@{av}#{k}")
            rows = dict(avatar=av, frame0=frame0, cycles_in_window=0, reach_fix_max_mm=0.0, curtain_not_clear=[])
            for n, tr in res["tracks"].items():
                c = byn.get(n)
                if c is None:
                    continue
                q = c["parcel"]
                g, r_ = tr["grasp"], tr["release"]
                h_ = tr["dims"][2]
                tr_f = {}
                for i in range(g, r_ + 1):
                    f = frame0 + i
                    if not (self.F0 <= f <= self.F1):
                        continue
                    yw = float(tr["yaw"][i]) + tr["obj_yaw_off"]
                    M = Matrix.Rotation(float(tr["pitch"][i]), 3, "X") @ Matrix.Rotation(float(tr["yaw"][i]), 3, "Z")                         @ Matrix.Rotation(float(tr["droop"][i]) if "droop" in tr else 0.0, 3, "X")                         @ Matrix.Rotation(tr["obj_yaw_off"], 3, "Z")  # (droop: a mailer held by its far edge)
                    ctr = Vector(tuple(tr["loc"][i]))
                    tr_f[f] = (ctr - M @ Vector((0.0, 0.0, h_ / 2)), yw, ("R", M))
                if tr_f:
                    held[q] = dict(track=tr_f, release_frame=frame0 + r_, belt=f"induct_{k}")
                    rows["cycles_in_window"] += int(self.F0 <= frame0 + r_ <= self.F1)
                rows["reach_fix_max_mm"] = max(rows["reach_fix_max_mm"], tr.get("reach_fix_max_mm", 0.0))
                rows["zone_corr_max_m"] = max(rows.get("zone_corr_max_m", 0.0), tr.get("zone_corr_m", 0.0))
                if tr.get("reach_fix_max_mm", 0.0) > 30 and self.F0 - 20 <= frame0 + r_ <= self.F1 + 20:
                    rows.setdefault("reach_fix_rows", []).append(dict(
                        n=n, release_frame=frame0 + r_, kind=q.kind, dims=[round(v, 2) for v in tr["dims"]],
                        reach_fix_mm=tr["reach_fix_max_mm"], zone_corr_m=tr.get("zone_corr_m", 0.0)))
                if not tr.get("curtain_clear", True):
                    rows["curtain_not_clear"].append(frame0 + r_)
            st.update(arm=arm, body=body, res=res, frame0=frame0)
            rep_[f"I{k + 1}"] = rows
        return held, rep_

    def report(self, t0=0.0, t1=1e9):
        """Cycle stats for the window (QA, --sim-only)."""
        out = {}
        for st in self.st:
            cs = [c for c in st["cycles"] if t0 <= c.get("release", -1e9) <= t1]
            rel = [c["release"] for c in cs]
            gaps = [round(b_ - a_, 2) for a_, b_ in zip(rel, rel[1:])]
            out[f"I{st['k'] + 1}"] = dict(
                cycles=len(cs), release_gaps_s=gaps, release_s=[round(c["release"], 2) for c in cs],
                grasp_s=[round(c["grasp"], 2) for c in cs], ready_s=[round(c["ready"], 2) for c in cs],
                held_extra_s=[c.get("held_extra", 0.0) for c in cs],
                segs=[(sg["kind"], round(sg["out0"], 2), round(sg["out1"], 2)) for sg in st["P"].segs
                      if sg["out1"] >= t0 and sg["out0"] <= t1],
                stop_wait_s=[round(c["grasp"] - c["ready"], 2) for c in cs],
                kinds=[c["parcel"].kind for c in cs], dims=[[round(v, 2) for v in c["parcel"].dims] for c in cs])
        return dict(stations=out, diverts_in_window=sum(1 for d in self.diverts if t0 <= d[0] <= t1),
                    diverts_total=len(self.diverts), first_diverts=self.diverts[:6],
                    cycles_total=[len(st["cycles"]) for st in self.st],
                    conflicts=self.conflicts, hold_overflows=self.overflows)


# ==================================================================================================== docks on mocap
class MocapDocks(Docks):
    """The dock unloaders on real capture (014_GO M4; bench mocap/m4_dock.py, review 016b): AndyData picks off the
    carton wall and places on the boom nose through the mocap engine (inductor.Planner / build), in each worker's
    own frame (the bench's: the wall in front at local +x, the boom beside him; world = local turned 180 deg about his
    feet). North of the boom the belt is on his left: left-turning takes, belt_side +1. The wall, its column order and
    the boom hand-over stay Docks'; the carry and the hands are the engine's. Two unloaders share one nose: a carton is
    held over it until the mate's is set down and the nose is clear (Planner.delay)."""
    AVATARS_M = {("D02", 1): ("Male_Adult_09", "orange"), ("D02", -1): ("Male_Adult_12", "lime"),
                 ("D05", 1): ("Male_Adult_04", "yellow"), ("D05", -1): ("Male_Adult_05", "orange")}  # (016 #6: men)
    LOOK_S = 0.7
    MAX_WAIT_S = 2.5

    def __init__(self, ctx):
        import importlib.util
        import sys
        from pathlib import Path
        mdir = Path(__file__).resolve().parent / "mocap"
        sys.path.insert(0, str(mdir))
        spec_ = importlib.util.spec_from_file_location("mocap_inductor_dock", mdir / "inductor.py")
        I = importlib.util.module_from_spec(spec_)
        spec_.loader.exec_module(I)
        self.I = I
        super().__init__(ctx)  # (build_wall already leaves 4.5-8.5 cm between columns: room for a hand, 016b #4)
        self.conflicts, self.waits = [], []
        for i, w in enumerate(self.workers):
            w.belt_side = -1 if w.side < 0 else 1  # local frame: south of the boom -> the boom at local -y
            picks, places = I.candidates(min_pick_h=0.6, max_pick_dur=2.3, turn_sign=w.belt_side * -1)
            w.order = []

            def pool(k, w=w, picks=picks):
                if k >= len(w.order):
                    return picks
                b = w.order[k]
                gz = b.pos.z + b.dims[2] - 0.055  # grip height (top of the carton less a hand)
                key = lambda p_: abs(p_["hand_height_m"] * 0.84 - min(gz, 0.95))  # noqa: E731
                ranked = sorted(picks, key=key)
                return [p_ for p_ in ranked if key(p_) < key(ranked[0]) + 0.08]
            w.P = I.Planner(dict(ratio=(0.85, 0.95), idle=True), random.Random(ctx["seed"] * 31 + i), picks, places,
                            pick_pool=pool)
            w.cycles, w.cur = [], None

    # ------------------------------------------------------------------------------------------------ frames
    @staticmethod
    def to_local(w, p):
        """World point -> the worker's frame (turned 180 deg about his feet)."""
        return (-(p[0] - w.pos.x), -(p[1] - w.pos.y), p[2])

    @staticmethod
    def to_world(w, p):
        return Vector((w.pos.x - p[0], w.pos.y - p[1], p[2]))

    def station(self, w, trunk_clear, lift=0.0):
        """The engine's station dict for worker w (local frame; m4_dock.py's, mirrored in y north of the boom)."""
        sd_ = w.belt_side
        wall_x = -(X_FACE - w.pos.x)  # 0.35
        by = sorted((-(w.dock["cy"] - 0.25 - w.pos.y), -(w.dock["cy"] + 0.25 - w.pos.y)))  # boom across (local y)
        boom = dict(x0=-2.65, x1=0.0, y0=by[0], y1=by[1], top=1.0)
        pts = {n: (*self.to_local(w, (b.pos.x, b.pos.y, 0.0))[:2], b.pos.z) for n, b in enumerate(w.order)}
        st = dict(x=0.0, belt_yaw=(0.0 if sd_ < 0 else math.pi), belt_side=sd_,
                  table_pt=tuple(pts[0]) if pts else (wall_x, 0.0, 1.0), pick_pts=pts,
                  place_xy=(-(PLACE_X - w.pos.x), (by[0] + by[1]) / 2),
                  clear_y=0.06 * sd_, root_min_y=0.08 * sd_, grip_axis_yaw=-math.pi / 2, trunk_clear=trunk_clear,
                  pick_root_max=(wall_x - max(0.34, trunk_clear - 0.035 + 0.10), 1e9), pick_grip_min_z=0.0,
                  ratio=(0.85, 0.95), surfaces=[(boom["x0"], boom["y0"], boom["x1"], boom["y1"], boom["top"])],
                  place_x=(-0.75, -0.15), place_y_range=(boom["y0"] + 0.03, boom["y1"] - 0.03),
                  belt_top=boom["top"], belt_speed=0.8, belt_dir=-1.0, table_slope=0.0, lift_rule=False,
                  grip_axis_strict=True, elbow_out=0.3, elbow_down=0.3, lean_at_pick=False, flex_cap_pick=45.0,
                  hold_min_bottom=1.03, lift=lift, slot_pull=dict(n=(-1.0, 0.0)))  # out of the face, towards him
        st["pick_root_max_n"] = {n: (st["pick_root_max"][0] - 0.25 * max(0.0, 1.0 - (b.pos.z + b.dims[2]) / 1.2), 1e9)
                                 for n, b in enumerate(w.order)}
        return st

    # ------------------------------------------------------------------------------------------------ simulation
    def step(self, t):
        rnd = self.rnd
        for w in self.workers:
            bn = w.dock["belt"]
            belt = self.B[bn]
            P_ = w.P
            if w.cur is None:  # plan the next carton as soon as the last one is down (the planner runs ahead)
                if t < w.free_at or not w.slots or t > getattr(self, 'T_STOP', self.T_END) + 1.0:
                    continue
                box = w.slots.pop(0)
                if not P_.segs:
                    P_.t = t
                w.order.append(box)
                c = P_.cycle(ready=max(t, P_.t))
                pk = Pick(box, w)
                w_, d_, h_ = box.dims
                yaw_end = box.yaw + self._turn_angle(w, box)
                hx = abs(math.cos(yaw_end)) * w_ / 2 + abs(math.sin(yaw_end)) * d_ / 2
                pk.s = max(PLACE_X + rnd.uniform(-0.04, 0.04), BELT_START_X + hx + 0.01) - BELT_START_X
                pos = belt.at(pk.s)[0]
                pk.place = (Vector((pos.x, w.dock["cy"], pos.z)), yaw_end)
                pk.half = max(w_, d_) / 2
                Parcel = self.ctx["Parcel"]
                prc = Parcel(self.ctx["next_k"]())
                prc.kind, prc.dims, prc.body = "box", tuple(box.dims), ("box_white" if rnd.random() < 0.12 else "box")
                prc.meta.update(kind="box", dims_m=list(prc.dims), body=prc.body)
                prc.half, prc.yaw_off, prc.station, prc.state = pk.half, yaw_end, pk, "held"
                pk.parcel, box.pick = prc, pk
                pk.c = c
                pk.t = dict(reach=c["pick0"], grasp=c["grasp"], lift=c["lift"], release=c["release"], end=c["end"])
                c["pick"] = pk
                w.cycles.append(c)
                w.cur = pk
                continue
            pk, c = w.cur, w.cur.c
            if t >= c["release"] - self.LOOK_S - 1e-6 and t < c["release"] - 1e-6:
                mate_busy = t + (c["release"] - t) < self.lock[bn]
                if (mate_busy or not self._nose_clear(bn, pk.s, pk.half)):
                    if c.get("held_extra", 0.0) < self.MAX_WAIT_S - 1e-6:
                        P_.delay(c["n"], self.DT, w.cycles)
                        c["held_extra"] = round(c.get("held_extra", 0.0) + self.DT, 2)
                    elif not c.get("overflow"):
                        c["overflow"] = True
                        self.waits.append((round(t, 2), w.name, pk.parcel.k))
            if t >= c["release"] - 1e-6:
                if not self._nose_clear(bn, pk.s, pk.half):
                    self.conflicts.append((round(t, 2), w.name, pk.parcel.k))
                prc = pk.parcel
                prc.belt, prc.s, prc.state = bn, pk.s, "belt"
                belt.items.append(prc)
                self.ctx["parcels"].append(prc)
                self.lock[bn] = c["release"] + 0.25
                pk.t.update(release=c["release"], end=c["end"])
                pk.t_rel = c["release"]
                pk.f_rel = self.F0 + int(round(c["release"] / self.DT))
                pk.pause = 0.0
                w.picks.append(pk)
                self.picks.append(pk)
                w.free_at = c["release"]  # the planner already holds his timeline to the cycle's end
                w.cur = None

    def finish(self):
        """A carton still in a cycle at the end: kept (in the wall until its grasp, then in his hands)."""
        for w in self.workers:
            pk = w.cur
            if pk is None:
                continue
            pk.t_rel = pk.c["release"]
            pk.f_rel = self.F0 + int(round(pk.c["release"] / self.DT))
            pk.pause = 0.0
            w.picks.append(pk)
            self.picks.append(pk)
            pk.parcel.state = "held"

    def pre_tracks(self):
        return {}  # the engine's tracks come from build_motion (before the bake)

    # ------------------------------------------------------------------------------------------------ motion
    def build_motion(self, scene, coll, rb, fps):
        """Each unloader on mocap: his whole planned timeline through the engine (two passes: the second lifted by
        his mesh's lowest point), in his frame under a root turned 180 deg about his feet. Returns {parcel: dict(track
        {frame: (bottom centre, yaw, ("R", M))}, release_frame, belt)} for the frames each carton is in the wall
        (static, from the window start) or in his hands, + per-worker QA rows."""
        import copy
        import numpy as np
        import line_a_worker as LW
        import retarget as R_
        I = self.I
        held, rep_ = {}, {}
        for w in self.workers:
            P_ = w.P
            if not P_.segs:
                continue
            av, vest = self.AVATARS_M[(w.dock["door"], 1 if w.side > 0 else -1)]
            before_ = set(scene.objects)
            arm, body = LW.import_avatar(scene, rb, av, vest, w.name, 0.0, 0.0)
            new_ = [o for o in scene.objects if o not in before_]
            for o in new_:
                for c_ in list(o.users_collection):
                    c_.objects.unlink(o)
                coll.objects.link(o)
            vest_ob = next((o for o in new_ if o.type == "MESH" and o is not body), None)
            tc = LW.trunk_clearance(arm, body)
            tb = math.floor(P_.segs[0]["out0"] * fps + 1e-6) / fps
            segs0 = copy.deepcopy(P_.segs)
            for sg in segs0:
                sg["out0"] -= tb
                sg["out1"] -= tb
            nF = int(round((self.T_END - tb) * fps)) + 1
            frame0 = self.F0 + int(round(tb * fps))
            parcels = {}
            for n, c in enumerate(w.cycles):
                b = c["pick"].box
                ctr = self.to_local(w, (b.pos.x, b.pos.y, b.pos.z + b.dims[2] / 2))
                parcels[c["n"]] = dict(dims=tuple(b.dims), at=tuple(ctr), yaw=b.yaw - math.pi)
            lift = 0.0
            for it in range(2):
                rig = R_.setup(arm, I.take(P_.picks[0]["take"]))
                st = self.station(w, tc, lift)
                res = I.build(rig, copy.deepcopy(segs0), st, parcels, nF, fps, frame0=frame0, name=f"dock@{av}#{w.k}")
                if it == 1:
                    break
                low = []
                for f in range(frame0, frame0 + nF, 3):
                    scene.frame_set(f)
                    ob_ = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
                    me_ = ob_.to_mesh()
                    co_ = np.empty(len(me_.vertices) * 3)
                    me_.vertices.foreach_get("co", co_)
                    M_ = np.array(ob_.matrix_world)
                    low.append(float((co_.reshape(-1, 3) @ M_[:3, :3].T + M_[:3, 3])[:, 2].min()))
                    ob_.to_mesh_clear()
                lift = -min(low)
                bpy.data.actions.remove(res["action"])
            root = bpy.data.objects.new(f"{w.name}_root", None)
            coll.objects.link(root)
            root.location = (w.pos.x, w.pos.y, 0.0)
            root.rotation_euler = (0.0, 0.0, math.pi)
            arm.parent = root
            if vest_ob is not None and vest_ob.parent is None:
                vest_ob.parent = arm
            rows = dict(avatar=av, frame0=frame0, cycles_in_window=0, lift_m=round(lift, 3), reach_fix_max_mm=0.0,
                        belt_side=w.belt_side)
            byn = {c["n"]: c for c in w.cycles}
            for n, tr in res["tracks"].items():
                c = byn.get(n)
                if c is None:
                    continue
                pk = c["pick"]
                q = pk.parcel
                g, r_ = tr["grasp"], tr["release"]
                h_ = tr["dims"][2]
                tr_f = {}
                for i in range(0, min(r_ + 1, nF)):
                    f = frame0 + i
                    if not (self.F0 <= f <= self.F1):
                        continue
                    yw = float(tr["yaw"][i]) + tr["obj_yaw_off"] + math.pi
                    M = Matrix.Rotation(yw, 3, "Z")
                    ctr = self.to_world(w, tuple(tr["loc"][i]))
                    tr_f[f] = (ctr - M @ Vector((0.0, 0.0, h_ / 2)), yw, ("R", M))
                if tr_f:
                    held[q] = dict(track=tr_f, release_frame=frame0 + r_, belt=w.dock["belt"])
                    rows["cycles_in_window"] += int(self.F0 <= frame0 + r_ <= self.F1)
                rows["reach_fix_max_mm"] = max(rows["reach_fix_max_mm"], tr.get("reach_fix_max_mm", 0.0))
            w.arm, w.body, w.res, w.frame0 = arm, body, res, frame0
            rep_[w.name] = rows
        return held, rep_

    def build(self, scene, coll, frames, make_parcel_mesh):
        """Walls (as Docks) + the report; the people were built by build_motion before the bake."""
        rep = {"walls": {}, "workers": getattr(self, "motion_rows", {}), "schedule": {},
               "conflicts": self.conflicts, "hold_overflows": self.waits,
               "held_extra_s": {w.name: [c.get("held_extra", 0.0) for c in w.cycles] for w in self.workers}}
        for pk in self.picks:
            if pk.parcel is not None:
                rep["schedule"].setdefault(pk.worker.dock.get("belt", "-"), []).append(
                    (pk.worker.name[-1], pk.parcel.k, round(pk.t_rel, 2), round(pk.s, 2)))
        wall_coll = bpy.data.collections.get("TruckWalls") or bpy.data.collections.new("TruckWalls")
        if wall_coll.name not in scene.collection.children:
            scene.collection.children.link(wall_coll)
        for door, (front, back) in self.walls.items():
            static = [b for b in front if b.pick is None]
            n = make_parcel_mesh(f"truck_wall_{door}", static, wall_coll)
            nb = fill_mesh(f"truck_fill_{door}", back, wall_coll)
            rep["walls"][door] = {"face_cartons": n, "fill_cartons": nb,
                                  "picked_in_window": sum(1 for b in front if b.pick and b.pick.parcel is not None)}
        return rep


# ==================================================================================================== induction line B
# A manual induction workstation (B2 pre-review #4: a 2nd induction line, 30-35 % loop occupancy): two inductors take
# parcels off the top of over-full gaylords (bulk boxes the forklifts bring from the lane) and set them into gaps on
# belt B, which ramps up through DWS arch B and merges onto the loop (flow.py). Belt B runs east along y 7.6 from
# x 40.8 (clear of the XO-1 stair); each inductor faces east with the belt on the left and the gaylord on the right
# (a 90 deg turn each way, through the front, as on line A). Three on the 3.2 m flat section, 1.1 m apart (>= 0.6 m
# personal space, review 009d), half-size gaylords side by side (forklift access from the lane to the south); two
# inductors gave 26.9-28.5 % loop occupancy, the target is 30-35 % (B2 pre-review #4).
LINE_B_Y, LINE_B_X0 = 7.6, 40.8
GAYLORD = (1.0, 0.8, 0.75)  # w x d x rim height (m): heaped above the rim on the near half, taken from the top
GAYLORD_GAP = 0.33  # body centre -> gaylord's near wall (0.25-0.3: pivot steps put toes into its pallet; 0.35:
# the heap out of reach)
LINE_B_LEAD, LINE_B_HEAP = 20.0, 18  # working since 20 s before frame 1; parcels per gaylord (a low heap near him:
# 26 over the whole gaylord stood 6 layers high and half of it out of reach). Longer windows (S1, 90 s) are worked at
# a slower pace (longer pauses) so the heap lasts: no worker stands idle at an empty gaylord
LINE_B = [dict(name="worker_inductB_1", at=(41.2, 6.85), avatar=("Male_Adult_12", "lime", None), start=0.3),
          dict(name="worker_inductB_2", at=(42.3, 6.85), avatar=("Female_Adult_04", "orange", None), start=1.4),
          dict(name="worker_inductB_3", at=(43.4, 6.85), avatar=("Male_Adult_09", "yellow", None), start=2.2)]
# (inductB_3 was Female_Adult_06: the shortest arms of the set, 11-19 cm short of the far heap)
# (y 6.85: 0.35 m from belt B's frame - at 6.95 hips and spine went into it on the set-down)


class GaylordInductors(BagOpener):
    """Line B inductors: the bag opener's heap picking, each worker with their own gaylord, onto belt B."""
    READY_KEEP = []  # (not the opener's bench line)
    HOLD_LIFTED = False  # held beside the heap at chest height (kept lifted it came up to his face)
    PULL_OUT = 0.1  # only out of its place, then up and round (0.2 toward him at lift height met his face)
    HOLD_TURN = 1.4  # held in front of him, clear of the gaylord's near wall (at 1.0 rad it was still over it)
    KEEP_OUT = []
    STRAIGHT_PULL = False

    def __init__(self, ctx):
        self.ctx = ctx
        self.rnd = random.Random(ctx["seed"] + 1313)
        self.DT, self.F0, self.F1 = ctx["DT"], ctx["F0"], ctx["F1"]
        self.T_END = (self.F1 - self.F0) * self.DT
        self.T_STOP = ctx.get("T_STOP", self.T_END)  # (sim-only --scan-extend: work on past the window)
        self.B = ctx["B"]
        self.workers, self.picks, self.planned, self.now = [], [], [], 0.0
        self.piles, self.gaylords = {}, []
        rnd = self.rnd
        Parcel = ctx["Parcel"]
        gw, gd, gh = GAYLORD
        for k, cfg in enumerate(LINE_B):
            w = IndWorker(k, cfg["at"][0], cfg["avatar"], (0, 0), 0)
            w.pos, w.heading, w.name = Vector((cfg["at"][0], cfg["at"][1], 0.0)), 0.0, cfg["name"]
            w.dock = {"cy": LINE_B_Y, "belt": "induction_B"}
            w.free_at = cfg["start"] - min(LINE_B_LEAD, ctx.get("preroll", 0.0))
            self.workers.append(w)
            gc = Vector((cfg["at"][0] + 0.1, cfg["at"][1] - GAYLORD_GAP - gd / 2, 0.0))  # on the right (south)
            self.gaylords.append(gc)
            pile = []
            for _ in range(LINE_B_HEAP):
                p = Parcel(ctx["next_k"]())
                if p.kind == "box" and max(p.dims) > 0.36:  # bulk small-parcel flow: mailers and small cartons
                    p.kind, p.dims, p.body = "mailer", (0.32, 0.24, 0.04), "mailer_grey"
                    p.meta.update(kind=p.kind, dims_m=list(p.dims), body=p.body)
                    p.half = max(p.dims[:2]) / 2
                p.state = "held"
                r = math.hypot(p.dims[0], p.dims[1]) / 2 + 0.03  # any yaw stays inside the 2 cm walls
                best = None
                for _ in range(40):  # on the fill / what is already there, near half only (reach)
                    cand = Box(gc.x - 0.1 + rnd.uniform(-min(0.4, gw / 2 - r - 0.1), min(0.4, gw / 2 - r + 0.1)),
                               gc.y + rnd.uniform(max(0.0, gd / 2 - r - 0.35), gd / 2 - r), gh, tuple(p.dims),
                               rnd.uniform(0, math.pi))
                    z = max([b.pos.z + b.dims[2] for b, _ in pile if b.overlaps_xy(cand)], default=gh)
                    cand.pos.z = z
                    if not _static_clear(cand):
                        continue
                    if best is None or z < best[0] - 1e-6:
                        best = (z, cand)
                if best is None:  # (nowhere clear in 40 tries: the last one, as before)
                    best = (z, cand)
                best[1].pos.z = best[0]
                pile.append((best[1], p))
            pile.sort(key=lambda bp: (-round(bp[0].pos.z, 3), (bp[0].pos - w.pos).xy.length))
            self.piles[w.name] = pile
        # arms keep clear of belt B's frames (flat run) and the gaylord walls (elbow swivel)
        self.STATIC_OBST = [(Matrix.Translation((LINE_B_X0 + 1.6, LINE_B_Y, 0.0)), (3.2, 0.92, 1.05))] +             [(Matrix.Translation((g.x, g.y, 0.0)), (gw, gd, gh)) for g in self.gaylords]
        lead = min(LINE_B_LEAD, ctx.get("preroll", 0.0))
        self.extra_pause = max(0.0, (lead + self.T_END) / (LINE_B_HEAP - 2) - 3.0)  # s per pick, mean

    @property
    def pile(self):
        return [bp for pl in self.piles.values() for bp in pl]

    def _idle_target(self, w):
        return Vector((w.pos.x + 0.4, LINE_B_Y, 1.0))

    def _glance_target(self, w):
        mate = next((o for o in self.workers if o is not w), None)
        if mate is not None and len(w.picks) % 2 == 0:
            return Vector((mate.pos.x, mate.pos.y, 1.6))
        return Vector((46.0, 10.0, 1.6))  # up the ramp to the arch

    def _gap_clear(self, t_rel, s_place, half, gap=0.35):
        bel = self.B["induction_B"]
        for q in bel.items:
            pred = q.s + bel.speed * max(t_rel - self.now, 0.0)
            if q.s - (q.half + half + gap) < s_place < pred + (q.half + half + gap):
                return False
        for (tr, sp, hh) in self.planned:
            if abs(sp + bel.speed * (t_rel - tr) - s_place) < hh + half + gap:
                return False
        return True

    def step(self, t):
        self.now = t
        bel = self.B["induction_B"]
        rnd = self.rnd
        for w in self.workers:
            pk = w.cur
            pile = self.piles[w.name]
            if w.state == "idle":
                if t < w.free_at or not pile or t > getattr(self, 'T_STOP', self.T_END) + 1.0:
                    continue
                # start only if belt B will have a gap at his spot by the set-down (~2.1 s): the downstream inductor
                # held a parcel at his chest for 16 s waiting for one (held_clip_head)
                if not self._gap_clear(t + 2.1, w.pos.x - LINE_B_X0 + 0.15, 0.2):
                    w.free_at = t + 0.3
                    continue
                box, p = pile.pop(0)
                pk = Pick(box, w)
                pk.parcel = p
                box.pick = pk
                pk.lift_z = self._heap_clear(box, pile, self.PULL_OUT + 0.05, (w.pos - box.pos).xy)
                # ~3.0 s a parcel (~1,200/h each, inside the 800-2,250/h manual-induction range): no queue wait
                T_reach, T_settle, T_pull = rnd.uniform(0.55, 0.8), rnd.uniform(0.18, 0.25), rnd.uniform(0.22, 0.3)
                pk.T_label, pk.T_turn = rnd.uniform(0.2, 0.35), rnd.uniform(0.7, 0.9)
                pk.T_place, pk.T_ret = rnd.uniform(0.2, 0.26), rnd.uniform(0.25, 0.35)
                pk.t = dict(reach=t, settle=t + T_reach, pull=t + T_reach + T_settle,
                            hold=t + T_reach + T_settle + T_pull)
                pk.s = w.pos.x - LINE_B_X0 + 0.15  # just downstream of him
                lat = -min(0.21, 0.37 - max(p.dims[:2]) / 2)  # the near (south) half
                pk.lat = lat
                ppos, byaw = bel.at(pk.s)
                ppos = ppos + Vector((-math.sin(byaw), math.cos(byaw), 0.0)) * lat
                yaw_end = byaw + (0.0 if p.dims[0] >= p.dims[1] else math.pi / 2) + rnd.uniform(-0.12, 0.12)
                yaw_end = follow_turn(yaw_end, box.yaw, w.pos, box.pos, ppos)
                pk.place = (Vector((ppos.x, ppos.y, ppos.z)), yaw_end)
                w.cur, w.state = pk, "reach"
                continue
            if pk is None:
                continue
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
            if w.state == "turn":
                self._hold_if_busy(w, pk, t, bel, max(pk.parcel.dims[:2]) / 2)
            if w.state == "turn" and t >= pk.t["release"] - 1e-6:
                p = pk.parcel
                p.yaw_off = pk.place[1] - bel.at(pk.s)[1]
                p.belt, p.s, p.state, p.lat = "induction_B", pk.s, "belt", pk.lat
                bel.items.append(p)
                self.ctx["parcels"].append(p)
                pk.pause = min(rnd.expovariate(1 / 0.25), 0.9) + (rnd.uniform(0.8, 1.6) if rnd.random() < 0.06 else 0)
                if self.extra_pause > 0:
                    pk.pause += min(rnd.expovariate(1 / self.extra_pause), 3 * self.extra_pause)
                w.picks.append(pk)
                self.picks.append(pk)
                w.free_at = pk.t["end"] + pk.pause
                w.cur, w.state = None, "idle"
        self.planned = [x for x in self.planned if x[0] > t - 5.0]

    def finish(self):
        for w in self.workers:
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
            w.picks = [q for q in w.picks if q.t["end"] + q.pause > -0.5]
        self.picks = [q for q in self.picks if q.t["end"] + q.pause > -0.5]

    def build(self, scene, coll, frames):
        rep = {"workers": {}, "cycles_in_window": sum(1 for pk in self.picks if pk.t["release"] >= 0)}
        gw, gd, gh = GAYLORD
        bm = bmesh.new()  # gaylords: board walls 2 cm, open top, on a pallet; filled below the heap
        walls = ((-gw / 2, -gd / 2, gw / 2, -gd / 2 + 0.02), (-gw / 2, gd / 2 - 0.02, gw / 2, gd / 2),
                 (-gw / 2, -gd / 2, -gw / 2 + 0.02, gd / 2), (gw / 2 - 0.02, -gd / 2, gw / 2, gd / 2))
        for gc in self.gaylords:
            for (x0, y0, x1, y1) in walls:
                M = Matrix.Translation((gc.x + (x0 + x1) / 2, gc.y + (y0 + y1) / 2, 0.12 + (gh - 0.12) / 2))
                bmesh.ops.create_cube(bm, size=1.0, matrix=M @ Matrix.Diagonal((x1 - x0, y1 - y0, gh - 0.12, 1)))
            bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((gc.x, gc.y, 0.06))
                                  @ Matrix.Diagonal((gw, gd, 0.12, 1)))  # pallet
            fill_top = gh  # over-full: the heap starts at the rim, so a pull never drags through a wall
            bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((gc.x, gc.y, (0.12 + fill_top) / 2))
                                  @ Matrix.Diagonal((gw - 0.05, gd - 0.05, fill_top - 0.12, 1)))  # the fill
        me = bpy.data.meshes.new("gaylords_lineB")
        bm.to_mesh(me)
        bm.free()
        me.materials.append(bpy.data.materials.get("cardboard"))
        coll.objects.link(bpy.data.objects.new("gaylords_lineB", me))
        self.animate(scene, coll, frames, rep, role="induction")
        return rep


# ==================================================================================================== ambient roles
# Roles without parcel flow: technician at the HMI (taps the touchscreen), supervisor on the phone, the cage
# checker with a clipboard at a cage's destination tag, a break table (one seated on a real chair, one standing
# texting). Their props (HMI stand, table, chair, phone, clipboard) are real objects at the right height.
HMI_AT, TECH_AT = (21.2, 13.65), (21.2, 13.14)  # 0.45 m from the screen (at 0.53 he was short of the taps by up
# to 14 cm and the clamped hand met the cabinet: collision check)
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
        hmi = scene.objects.get("tech_hmi")
        if hmi is not None:
            _hmi_screen_ui(hmi, "hmi_screen")
        sc_c = Vector((HMI_AT[0], HMI_AT[1] - 0.062, 1.334))  # screen centre (faces south, tilted back 20 deg)
        n = Vector((0, -math.cos(math.radians(20)), math.sin(math.radians(20))))  # out of the screen
        upv = Vector((0, math.sin(math.radians(20)), math.cos(math.radians(20))))  # up the screen
        wk = C.Worker(scene, coll, dict(role="technician", avatar="Male_Adult_05", vest="yellow", hat=None),
                      "worker_tech_1", Vector((*TECH_AT, 0)), math.pi / 2, hat_colour=0, clip_offset=71)
        wk.rig()
        taps, t = [], -0.5
        while t < self.F1 * self.DT + 2:
            n_t = rnd.randint(2, 4)  # a few taps on the screen, then hands down, read, again
            # (taps in the lower two thirds: on the top third his palm went over the housing's top edge, 1-1.3 cm,
            # hub run 4)
            spots = [sc_c + Vector((rnd.uniform(-0.14, 0.14), 0, 0)) + upv * rnd.uniform(-0.08, 0.03) for _ in range(n_t)]
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
                    p = spots[max(k, 0)] + n * (0.045 + 0.035 * poke)  # fingers flat, tip ON the glass at the tap
                    # (0.025 put the fingertip 2 cm into the screen: owner rule)
                    # fingers to his left along the glass (pointing up the screen they reached past its top edge)
                    tg["R"] = (p, C.frame_from(Vector((-1.0, 0.0, 0.0)) * 0.9 + upv * 0.35, -n))
                    w_ = min(1.0, (tt - a) / 0.4, max(0.0, (b + 0.5 - tt) / 0.5))
            wk.set_trunk(f, 0.0, 0.06, 0.0)
            wk.set_hands(f, tg, fingers="flat", weight=w_)
            wk.set_look(f, sc_c)
        wk.auto_steps(frames)
        wk.apply(frames)
        self._props(scene, wk, "worker_tech_1", "Male_Adult_05", math.pi / 2)
        rep["worker_tech_1"] = dict(taps=len(taps), deficits=Ambient._defs(wk))
        # ---------------------------------------------------------------- supervisor on the phone (bagging aisle)
        wk = C.Worker(scene, coll, dict(role="supervisor", avatar="Male_Adult_12", vest="orange", hat=None,
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
                                                    [P._mat("table_top", (0.40, 0.31, 0.22), 0.5), grey]), (tx, ty), 0.0, 90)
        _table_items(coll, tx, ty, 0.74)  # bottles, a cup, a lunch box (a bare top read as a white plane: B2 #10)
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
            edge = Vector((seat_at[0], ty - 0.22, 0.80))  # forearms ON the table (lower sank them in), 15 cm in
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
                      "worker_break_2", Vector((tx + 0.95, ty - 0.35, 0)),
                      math.atan2(seat_at[1] - (ty - 0.35), seat_at[0] - (tx + 0.95)),  # faces her seated colleague
                      hat_colour=0, base_clip="cell_phone_textmessage", clip_offset=47)  # (not the camera: 006b)
        wk.rig()
        for f in frames:
            tt = (f - self.F0) * self.DT
            wk.set_trunk(f, 0.0, 0.03, 0.0)
            if (tt % 8.0) > 5.0:  # looks up to talk to the seated colleague
                wk.set_look(f, Vector((seat_at[0], seat_at[1], 1.15)))
        wk.auto_steps(frames)
        wk.apply(frames)
        self._props(scene, wk, "worker_break_2", "Female_Adult_13",
                    math.atan2(seat_at[1] - (ty - 0.35), seat_at[0] - (tx + 0.95)))
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


# ==================================================================================================== scenario S2
# Removal into the blind spot (the core of the pitch). A worker takes a parcel off the load of the staging cage in
# bay S11, carries it west along the staging edge and walks through the gap in the sack racks into the BLIND_NW
# store corner, where no camera sees. CAM_13 (and CAM_01 / CAM_06 at range) film the approach. The parcel's earlier
# shift history is in the scan log; nothing scans it in the window. Expected answer: last seen entering Z11 with a
# person, then no coverage - unknown, never "left the hub".
S2_CAGE_BAY = "S11"
S2_CAGE = Vector((26.1, 30.6, 0.0))
S2_SHELF_Z = 0.9  # removable wire mid shelf hooked into the cage's side frames (half its 1.8 m height)
S2_PARCEL_DIMS = (0.25, 0.18, 0.10)  # a COD carton, kraft + white label (review 021 #1: an 18x10x6 phone box was
# unreadable on CAM_19; a phone usually travels in a carton like this anyway); w across the hands
# perimeter proof (scenarios_v2 S2 #1; raycast in the real hub geometry incl. the lens crop: mocap/s2_perimeter.py,
# qa/review/s2_perimeter/perimeter.json): the racks run flush to the west / north walls, which have no doors there
S2_EXITS = [dict(exit="entrance gap x 13.4-15.2, y 33.0-33.6 (the only walk-in)", watched_by=["CAM_19", "CAM_01", "CAM_06"],
                 seen_fraction=dict(south_face=1.0, person_column=1.0),
                 note="CAM_19 sees all of the gap's south face; unseen only a 0.25 m strip behind the south rack's end "
                      "upright above 0.6 m, reachable only through that face"),
            dict(exit="over the 3 m racks (a throw, not a way out for a person)", watched_by=["CAM_19"],
                 seen_fraction=dict(air_over_racks=0.49, landing_band=0.83),
                 note="CAM_19 (yaw 65, tilt 30) sees 49 % of the air 0.3 m over the racks; 83 % of the 1.5 m floor "
                      "band where a thrown parcel would land outside the racks is seen")]
S2_AVATAR = "Male_Adult_05"
S2_STORE_SHELF = (10.5, 33.87, 1.145)  # dress_hub's steel shelving inside the store (x 9.95-11.05), the top of its
# 3rd board (ray-measured 31 Oct: 1.145; 1.13 put the carton 15 mm into it, review 021b #3)
S2_STORE_SHELF_TOP = (9.951, 33.619, 11.049, 34.121, 1.145)  # that board: x0, y0, x1, y1, top z
S2_BOX_DX = 0.03  # the carton 3 cm right of the opening's centre (review 021b #2): he turns left with it as his
# head backs out of the 0.68 m opening; 7 cm left of centre put the head 1 mm off the front-left post, centred 3.6 cm;
# 4 cm right put his right fingers 1.1 cm into the front-right post at the lift
S2_BOX_LEAN_CAP = 20.0  # deg: the reach into the cage leans at most this (review 021b #2)
S2_BOX_IN = 0.01  # its front face 1 cm in from the shelf's front edge (3 cm: at the 20 deg cap his hands fell 17 mm
# short at the lift and the right fingers touched the front-right post)


S2_CARRY = dict(palm_up=-0.03, finger_down_deg=55.0, finger_flat=0.35, arm_keep=0.25,  # review 021 #2
                above_pelvis=0.14,  # carton centre ~1.05 m: against the lower chest / belly
                hook=True)  # fingertips hooked under the bottom edge, thumb flat on the end face (review 021b #1)


def s2_legs(box_c):
    """worker_s2_1's chain (mocap/remover.py; bench mocap/s2_bench.py; scenarios_v2 pass 2: in carrying, out
    empty-handed). pick: AndyData 541 A3/2 at 27.07 s walks up from the front, stops, picks with both hands, turns and
    walks off carrying (mirrored: from the south-west, off to the west); place: 541 A3/2 at 60.9 s walks up to a shelf,
    sets the box down, stands ~1.5 s, turns ~130 deg and walks off (towards the store's exit: the shelf faces north);
    100STYLE forward walks between them, path-warped onto these routes. 90 s: in at ~23 s, out at ~40 s, then away
    east along the staging aisle."""
    sx, sy, sz = S2_STORE_SHELF
    place_at = (sx, sy + 0.25 - 0.02 - S2_PARCEL_DIMS[1] / 2, sz + S2_PARCEL_DIMS[2] / 2)  # front of the shelf
    pick = dict(kind="clip", role="pick", take="Participant_541_Setup_A_Seq_3_Trial_2", grasp=27.067, lift=27.633,
                pre_s=(3.6, 4.3), post_s=(1.3, 2.1), mirror=True, at=tuple(box_c), yaw=0.0, behind=0.42, t=6.0)
    place = dict(kind="clip", role="place", take="Participant_541_Setup_A_Seq_3_Trial_2", release=60.9,
                 pre_s=(1.6, 3.0), post_s=(2.4, 3.2), mirror=False, at=place_at, yaw=math.pi, behind=0.36,
                 lead_in=0.5, lead_out=0.6, rest_s=2.6)  # arms hang until he walks: the take's own arms after the
    # release came up in front of the belly (bench f340-343), the walk's swing doesn't
    # pass 2 #3 (review 021 P1 #5): then he takes the same cage (RC-864, where the scan still has the parcel) by its
    # two front posts - the pick take again, cut at the lift before it turns - pushes it to door D07 (its RFID portal
    # reads the tag there: the scan story becomes "left on the truck") and lets go with the place take (stands, turns,
    # walks off)
    grab = dict(kind="clip", role="grab", obj="cage", take="Participant_541_Setup_A_Seq_3_Trial_2", grasp=27.067,
                lift=27.633, pre_s=(2.0, 2.8), post_s=(0.0, 0.3), mirror=True, at=S2_CAGE_GRIP, yaw=0.0, behind=0.57,
                lead_in=0.8)  # (cut later, in 0.8 m: the take's own walk-in and a 1.2 m lead-in brought him up past
    # parked cage S01's north face, a thumb 1.3 cm into it - bench 18 f575)
    release = dict(kind="clip", role="release", obj="cage", take="Participant_541_Setup_A_Seq_3_Trial_2", release=60.9,
                   pre_s=(1.6, 3.0), post_s=(2.4, 3.2), mirror=False, at=S2_CAGE_DOOR_GRIP, yaw=0.0, behind=0.57,
                   lead_in=0.6, lead_out=0.6, rest_s=2.6)
    return [dict(kind="walk", route=[(19.0, 27.6), (22.5, 28.4)]), pick,
            dict(kind="walk", route=[(22.0, 30.4), (19.5, 32.0), (15.9, 32.35), (14.3, 32.75), (14.3, 33.8),
                                     (13.0, 34.75), (11.6, 35.6)]), place,
            dict(kind="walk", route=[(12.0, 35.0), (13.3, 34.6), (14.3, 33.8), (14.3, 32.75), (16.0, 32.2), (21.0, 30.6),
                                     (22.0, 28.6), (23.0, 28.4)]), grab,
            dict(kind="walk", route=[(26.1, 31.3), (27.2, 32.5), (29.05, 33.5)]), release,  # (a waypoint past where
            # the release take starts doubled the path back: he spun with the cage, arms crossed - bench f778)
            dict(kind="walk", route=[(27.6, 36.6), (27.0, 33.4), (24.0, 32.0), (20.0, 31.4), (16.5, 31.2), (12.5, 31.0)])]


S2_CAGE_GRIP = (S2_CAGE.x, S2_CAGE.y - 0.40, 1.05)  # its open front: the two corner posts at 1.05 m
S2_CAGE_DOOR = (29.05, 38.3)  # the cage's centre where it is left at door D07 (portal SP-RFID-D07 at y 39.4)
S2_CAGE_DOOR_GRIP = (S2_CAGE_DOOR[0], S2_CAGE_DOOR[1] - 0.40, 1.05)


def s2_objects():
    """remover.compose's held objects other than the carton: the roll cage, each hand round one of its front corner
    posts from behind (palm forward 6 cm behind the post's axis, fingers up round it - 3.5 cm put the palm and the
    curled fingers 1.0-1.4 cm into the 32 mm post once hands stopped being skipped by the cage check, builder note
    0415; from outside the posts the hands were
    0.83 m apart, out of reach), rolling on the floor (its grip height fixed, no 180 deg symmetry), never drawn in."""
    return {"cage": dict(dims=(0.72, 0.04, 0.10), c=S2_CAGE_GRIP, yaw=0.0, draw_in=False, trunk=False, fix_z=True,
                         symmetric=False, grip="posts", palm_off=0.06, palm_up=0.0, finger_flat=0.3, elbow_out=0.35,
                         # pushed with the posts 0.57 m ahead of his spine line - his toes clear of its deck (0.30 / 0.50:
                         # they hit its front edge), leaning in up to 32 deg for the reach (riding on the
                         # captured end-of-reach arms they were out of reach the whole push: bench, up to 12 cm)
                         carry=dict(above_pelvis=0.1, snug_clear=0.55), carry_to_give=True, follow_body=True,
                         lean_cap=32.0)}


def s2_cage_pose(grip, yaw):
    """The cage's origin (centre on the floor) from its grip frame (front face centre at 1.0 m) and yaw."""
    c, s_ = math.cos(yaw), math.sin(yaw)
    return Vector((grip[0] - s_ * 0.40, grip[1] + c * 0.40, 0.0))  # (floor: whatever the grip height)


def _remover_module():
    import importlib.util
    import sys
    from pathlib import Path
    mdir = Path(__file__).resolve().parent / "mocap"
    if str(mdir) not in sys.path:
        sys.path.insert(0, str(mdir))
    if "mocap_remover" not in sys.modules:
        spec_ = importlib.util.spec_from_file_location("mocap_remover", mdir / "remover.py")
        m = importlib.util.module_from_spec(spec_)
        sys.modules["mocap_remover"] = m
        spec_.loader.exec_module(m)
    return sys.modules["mocap_remover"]


class BlindRemoval:
    """worker_s2_1 on mocap: walks over to the S11 cage, takes the small COD box off its mid shelf with both hands,
    turns away and carries it through the exception store's entrance (mocap/remover.py: real capture every frame,
    the box rigid with the hands from the grasp)."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.DT, self.F0, self.F1 = ctx["DT"], ctx["F0"], ctx["F1"]
        self.rnd = random.Random(ctx["seed"] + 2002)
        Parcel = ctx["Parcel"]
        p = Parcel(ctx["next_k"]())
        p.kind, p.dims, p.body = "box", S2_PARCEL_DIMS, "box"
        p.meta.update(kind="box", dims_m=list(p.dims), body="box", scenario="S2", story=True)
        p.half = max(p.dims[:2]) / 2
        p.state = "held"
        self.parcel = p
        # on the shelf, 3 cm in from its front edge, 7 cm left of the cage's centre line (the mirrored take stands
        # ~7 cm right of his hands: centred in the 0.72 m opening; bench: his shoulder touched the front post)
        self.box = Box(S2_CAGE.x + S2_BOX_DX, S2_CAGE.y - 0.40 + S2_BOX_IN + S2_PARCEL_DIMS[1] / 2, S2_SHELF_Z, S2_PARCEL_DIMS,
                       0.0)
        self.T = {}

    def history_events(self, ev, rnd, ride=None, door=None):
        """The story parcel's earlier shift (before the window): unloaded at the north door with a handheld scan, read
        at the tunnel, sorted, then loose into the S11 cage with a handheld container scan (a mis-sort put aside by the
        bagger). `ride(chute)`: flow's loop time from the carrier load to the divert (the divert follows the load by
        exactly that). `door()`: flow's door-to-tunnel trip (a parcel cannot reach the tunnel without its unload scan:
        checkpoint 1, Rexton 31 Oct)."""
        p, t0 = self.parcel, -1310.0 + rnd.uniform(-30, 30)
        ev(t0 - (door() if door else 37.0), "unload_scan", parcel=p, scan_point="SP-IN-N", device="handheld", history=True)
        w, d, h = p.dims
        ev(t0, "tunnel_read", parcel=p, scan_point="SP-TUNNEL", dims_mm=[int(x * 1000 + rnd.gauss(0, 4)) for x in (w, d, h)],
           weight_g=int(rnd.uniform(800, 2600)), photo=f"tunnel_s2.png", history=True)
        ev(t0 + 9.8, "induct_to_carrier", parcel=p, scan_point="SP-INDUCT", carrier=rnd.randint(1, 99), history=True)
        ev(t0 + 9.8 + (ride("C12") if ride else 21.7), "divert_confirm", parcel=p, scan_point="SP-DIV-C12", chute="C12",
           history=True)
        self.cage_id = f"RC-{rnd.randint(100, 999)}"
        ev(-640.0 + rnd.uniform(-20, 20), "container_add", parcel=p, scan_point="SP-CAGE-W", container_id=self.cage_id,
           item_kind="parcel", device="handheld", history=True)

    def _cage(self, scene, coll, spec):
        cleared = _clear_bay(scene, spec, S2_CAGE_BAY)
        cage, _ = _cage_parts("cage_s2_S11", coll, self.rnd, loaded=True)
        cage.location = S2_CAGE
        me = bpy.data.meshes.new("cage_s2_shelf")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=(0.68, 0.76, 0.02), verts=bm.verts)
        bmesh.ops.translate(bm, vec=(0, 0, S2_SHELF_Z - 0.01), verts=bm.verts)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(cage.material_slots[0].material if cage.material_slots else None)
        shelf = bpy.data.objects.new("cage_s2_S11_shelf", me)
        coll.objects.link(shelf)
        shelf.parent = cage
        return cleared

    def _avatar(self, scene, coll):
        from pathlib import Path
        rb = Path(__file__).resolve().parent / "build" / "third_party" / "rocketbox"
        before_o, before_a = set(scene.objects), set(bpy.data.actions)
        bpy.ops.import_scene.fbx(filepath=str(rb / S2_AVATAR / f"{S2_AVATAR}.fbx"))
        new_o = [o for o in scene.objects if o not in before_o]
        arm = next(o for o in new_o if o.type == "ARMATURE")
        body = next(o for o in new_o if o.type == "MESH" and o.parent == arm)
        P._fix_materials(body, rb / S2_AVATAR)
        for o in new_o:
            if o.animation_data:
                o.animation_data.action = None
            for c_ in list(o.users_collection):
                c_.objects.unlink(o)
            coll.objects.link(o)
        for act in [x for x in bpy.data.actions if x not in before_a]:
            bpy.data.actions.remove(act)
        arm.name, body.name = "worker_s2_1", "worker_s2_1_body"
        bpy.context.view_layer.update()
        return arm, body

    def build(self, scene, coll, frames, spec):
        import numpy as np
        RM = _remover_module()
        I, R = RM.I, RM.R
        import line_a_worker as LW
        frames = list(frames)
        F = len(frames)
        fps = 1.0 / self.DT
        rep = {"cleared": self._cage(scene, coll, spec)}
        arm, body = self._avatar(scene, coll)
        c0 = self.box.pos + Vector((0, 0, S2_PARCEL_DIMS[2] / 2))
        trunk = LW.trunk_clearance(arm, body) - 0.035 + 0.01  # his own torso + 1 cm (no vest)
        ap_ = S2_CARRY["above_pelvis"]  # snug: his torso front in the band the carton sits in, + 8 mm
        carry = dict(S2_CARRY, snug_clear=LW.torso_front(arm, body, ap_ - 0.06, ap_ + 0.06) + 0.008)
        cfg = dict(fps=fps, F=F, frame0=self.F0, legs=s2_legs(c0), objects=s2_objects(), palm_off=0.05,
                   trunk_clear=trunk, finger_flat=0.6,
                   elbow_out=0.45,  # 25 cm carton: the forearms came in over its near top edge (bench f66)
                   carry=carry,
                   box=dict(c=tuple(c0), yaw=0.0, dims=S2_PARCEL_DIMS, support_z=S2_SHELF_Z,
                            cage=(S2_CAGE.x - 0.34, S2_CAGE.y - 0.40, S2_CAGE.x + 0.34, S2_CAGE.y + 0.38),
                            supports=[S2_STORE_SHELF_TOP], lean_cap=S2_BOX_LEAN_CAP, give_s=1.2, give_rise=0.6),
                   name="worker_s2_1@remover")

        def mesh_low():
            out = []
            for f in frames:
                scene.frame_set(f)
                ob_ = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
                me_ = ob_.to_mesh()
                co_ = np.empty(len(me_.vertices) * 3)
                me_.vertices.foreach_get("co", co_)
                M_ = np.array(ob_.matrix_world)
                out.append(float((co_.reshape(-1, 3) @ M_[:3, :3].T + M_[:3, 3])[:, 2].min()))
                ob_.to_mesh_clear()
            return np.array(out)

        res = None
        for it in range(3):  # 1: as captured, 2: lifted so the soles sit on the floor, 3: dips at the joins lifted
            if res is not None:
                bpy.data.actions.remove(res["action"])
            rig = R.setup(arm, I.take(cfg["legs"][1]["take"]))
            res = RM.compose(rig, cfg)
            if it == 2:
                break
            lows = mesh_low()
            if it == 0:
                cfg["lift"] = -float(np.percentile(lows, 5))
            else:
                dip = np.where(lows < -0.004, -lows + 0.002, 0.0)
                if not dip.any():
                    break
                k_ = np.exp(-0.5 * (np.arange(-3, 4) / 1.2) ** 2)
                cfg["lift_f"] = np.maximum(np.convolve(dip, k_ / k_.max(), mode="same"), dip)
        rep.update(res["report"])
        loc, yaw = res["loc"], res["yaw"]
        h = S2_PARCEL_DIMS[2]
        p = self.parcel
        if p.ob is not None:  # the flow baked it static on the shelf: re-key it (mesh origin = bottom centre)
            if p.ob.animation_data:
                p.ob.animation_data_clear()
            for i, f in enumerate(frames):
                p.ob.location = Vector((loc[i][0], loc[i][1], loc[i][2] - h / 2))
                p.ob.rotation_euler = (0.0, 0.0, float(yaw[i]))
                p.ob.keyframe_insert("location", frame=f)
                p.ob.keyframe_insert("rotation_euler", frame=f)
            _lin(p.ob)
        self.track_out = {f: [round(float(c), 3) for c in (loc[i][0], loc[i][1], loc[i][2] - h / 2)]
                          for i, f in enumerate(frames)}
        cage = scene.objects.get("cage_s2_S11")
        if cage is not None and "cage" in res["objects"]:  # pushed to D07 (pass 2 #3)
            cl, cy_ = res["objects"]["cage"]
            if cage.animation_data:
                cage.animation_data_clear()
            for i, f in enumerate(frames):
                cage.location = s2_cage_pose(cl[i], float(cy_[i]))
                cage.rotation_euler = (0.0, 0.0, float(cy_[i]))
                cage.keyframe_insert("location", frame=f)
                cage.keyframe_insert("rotation_euler", frame=f)
            _lin(cage)
            fo = res["report"]["frames"]["objects"]["cage"]
            self.cage_push = dict(grab_t=(fo["take"] - self.F0) * self.DT,
                                  at_door_t=((fo["give"] - self.F0) * self.DT if fo["give"] is not None else None),
                                  door="D07", where=[round(float(v), 2) for v in s2_cage_pose(cl[-1], float(cy_[-1]))])
        # into the store carrying it (box crosses the gap's south face), out empty-handed (his pelvis crosses it back)
        gap = next((i for i in range(F) if loc[i][1] > 33.0 and 13.4 < loc[i][0] < 15.2), None)
        gone = next((i for i in range(F) if loc[i][1] > 33.6 and loc[i][0] < 13.0), None)
        bi_ = rig["bi"]
        pv = res["sol"]["Hw"][:, bi_["Bip01 Pelvis"]]
        inside = [i for i in range(F) if pv[i][1] > 33.3 and pv[i][0] < 15.4]  # in the store (x < its gap's east
        # side: the cage push later takes him to D07 at y ~38 - by y alone the exit was never found, 021c hub run)
        out_ = next((i for i in range(inside[-1] + 1, F) if pv[i][1] < 32.95), None) if inside else None
        rel = res["report"]["frames"].get("release")
        self.T = dict(grip=float(res["report"]["clips"][0]["event_t"]), gap=(gap * self.DT if gap is not None else None),
                      behind_rack=(gone * self.DT if gone is not None else None),
                      placed=((rel - self.F0) * self.DT if rel is not None else None),
                      out_empty=(out_ * self.DT if out_ is not None else None))
        self.rest_xyz = [round(float(c), 3) for c in (loc[-1][0], loc[-1][1], loc[-1][2] - h / 2)]
        rep["times"] = {k: (round(v, 2) if v is not None else None) for k, v in self.T.items()}
        return rep


# ==================================================================================================== scenario S3
# Phantom containment: the parcel that missed the C04 bag lies on the floor at the frame. A bagger picks it up,
# scans it INTO the C04 bag (handheld container_add, bag ID) - and sets it back down on the floor against the front
# of the frame instead of in the bag, then walks off. The log says "in bag"; the video says "beside it".
S3_PICK = Vector((44.82, 21.62, 0.0))
S3_DROP = Vector((43.95, 21.56, 0.0))
S3_STAND = (44.38, 22.02)
S3_DIMS = (0.3, 0.22, 0.14)


class PhantomContainment(Docks):
    TOP_GRIP = False  # loose parcels: side grip from the start
    KEEP_OUT = []
    STRAIGHT_PULL = False
    def __init__(self, ctx):
        self.ctx = ctx
        self.DT, self.F0, self.F1 = ctx["DT"], ctx["F0"], ctx["F1"]
        self.rnd = random.Random(ctx["seed"] + 3003)
        Parcel = ctx["Parcel"]
        p = Parcel(ctx["next_k"]())
        p.kind, p.dims, p.body = "box", S3_DIMS, "box"
        p.dest, p.target, p.read = "C04", "C04", True
        p.half = max(S3_DIMS[:2]) / 2
        p.meta.update(kind="box", dims_m=list(S3_DIMS), body="box", chute="C04", scenario="S3", story=True)
        p.state = "held"
        self.parcel = p
        self.box = Box(S3_PICK.x, S3_PICK.y, 0.0, S3_DIMS, 0.4)
        w = IndWorker(0, 0, ("Male_Adult_09", "lime", None), (0, 0), 0)
        w.name = "worker_s3_1"
        w.pos = Vector((S3_STAND[0], S3_STAND[1], 0.0))
        w.heading = -math.pi / 2
        self.w = w
        d = Vector((S3_STAND[0], S3_STAND[1], 0)) - self.box.pos
        d.z = 0
        tl = Matrix.Rotation(-self.box.yaw, 3, "Z") @ d.normalized()
        self.tl = Vector((tl.x, tl.y, 0)).normalized()
        self.approach = [(47.6, 22.3), (45.5, 22.25), S3_STAND]
        self.leave = [S3_STAND, (45.4, 22.4), (49.0, 22.6)]
        v = 1.01
        L = lambda pts: sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
        T = {"walk_in": 0.3}
        T["arrive"] = T["walk_in"] + L(self.approach) / v
        T["reach"] = T["arrive"] + 0.5
        T["grip"] = T["reach"] + 1.3  # squats to the floor
        T["lift"] = T["grip"] + 0.25
        T["scan"] = T["lift"] + 0.9  # label toward the ring scanner on his hand
        T["turn"] = T["scan"] + 0.6
        T["lower"] = T["turn"] + 0.9
        T["release"] = T["lower"] + 1.2  # sets it on the floor against the frame
        T["stand"] = T["release"] + 0.7
        T["walk_out"] = T["stand"] + 1.4
        self.T = T

    def history_events(self, ev, rnd, ride=None, door=None):
        p, t0 = self.parcel, -415.0 + rnd.uniform(-20, 20)
        ev(t0 - (door() if door else 37.0), "unload_scan", parcel=p, scan_point="SP-IN-N", device="handheld", history=True)
        w, d, h = p.dims
        ev(t0, "tunnel_read", parcel=p, scan_point="SP-TUNNEL", dims_mm=[int(x * 1000 + rnd.gauss(0, 4)) for x in (w, d, h)],
           weight_g=int(rnd.uniform(600, 2000)), photo="tunnel_s3.png", history=True)
        ev(t0 + 10.1, "induct_to_carrier", parcel=p, scan_point="SP-INDUCT", carrier=rnd.randint(1, 99), history=True)
        t_dv = t0 + 10.1 + (ride("C04") if ride else 16.7)
        ev(t_dv, "divert_confirm", parcel=p, scan_point="SP-DIV-C04", chute="C04", history=True)
        ev(t_dv + 1.2, "bag_drop", chute="C04", history=True)  # the photo-eye counted it; it bounced off the rim

    def scan_event(self, ev):
        self.bag_id = f"BAG-C04-{self.rnd.randint(1000, 9999)}"
        ev(self.T["scan"] + 0.3, "container_add", parcel=self.parcel, scan_point="SP-BAG-C04", container_id=self.bag_id,
           item_kind="parcel", device="handheld")

    def track(self):
        T = self.T
        out = {}
        hold = Vector((S3_STAND[0], S3_STAND[1] - 0.36, 1.0 - S3_DIMS[2] / 2))
        for f in range(self.F0, self.F1 + 1):
            t = (f - self.F0) * self.DT
            if t < T["lift"]:
                out[f] = (self.box.pos.copy(), self.box.yaw)
            elif t < T["scan"]:
                u = C.smooth((t - T["lift"]) / (T["scan"] - T["lift"]))
                out[f] = (self.box.pos.lerp(hold, u), self.box.yaw + 0.5 * u)
            elif t < T["turn"]:
                out[f] = (hold + Vector((0.06, 0.0, 0.08)), self.box.yaw + 0.5 + 0.3)  # label up toward his hand
            elif t < T["release"]:
                a = hold + Vector((0.06, 0.0, 0.08))
                u = C.smooth((t - T["turn"]) / (T["release"] - T["turn"]))
                drop = S3_DROP.copy()
                mid = a.lerp(drop, 0.5) + UP * 0.05
                pos = a.lerp(mid, min(u * 2, 1.0)) if u < 0.5 else mid.lerp(drop, (u - 0.5) * 2)
                out[f] = (pos, self.box.yaw + 0.8 - 0.6 * u)
            else:
                out[f] = (S3_DROP.copy(), self.box.yaw + 0.2)
        return out

    def build(self, scene, coll, frames):
        frames = list(frames)
        T = self.T
        fps = int(round(1 / self.DT))
        F = lambda t: self.F0 + int(round(t * fps))
        rep = {"times": {k: round(v, 2) for k, v in T.items()}}
        w = self.w
        wk = C.Worker(scene, coll, dict(role="chutes", avatar=w.avatar[0], vest=w.avatar[1], hat=w.avatar[2]), w.name,
                      Vector((*self.approach[0], 0)), math.pi, hat_colour=2, clip_offset=61)
        wk.rig()
        rep["legs"] = wk.walk([(F(T["walk_in"]), self.approach, 1.0, 0.6), (F(T["walk_out"]), self.leave, 1.0, 0.7)],
                              frames)
        tr = self.track()
        for f in frames:
            t = (f - self.F0) * self.DT
            loc, h = wk.obj.get(f, (wk.loc0, wk.heading0))
            yaw, flex, drop = 0.0, 0.03, 0.0
            look = Vector((loc.x, loc.y, 1.5)) + yaw_vec3(h) * 3.0
            hands = None
            if T["arrive"] <= t < T["walk_out"]:
                pos, pyaw = tr[f]
                yaw = (math.atan2(pos.y - loc.y, pos.x - loc.x) - h + math.pi) % (2 * math.pi) - math.pi
                yaw *= 0.85
                look = pos + UP * 0.1
                socks = self._socket_world(self.box.matrix(pos, pyaw), C.box_sockets(S3_DIMS, self._tl_at(pyaw, pos, loc)))
                if t < T["reach"]:
                    pass
                elif t < T["grip"]:
                    u = C.smooth((t - T["reach"]) / (T["grip"] - T["reach"]))
                    hands, flex, drop = (socks, u), 0.85 * u, 0.42 * u
                elif t < T["lift"] + 0.6:
                    u = C.smooth((t - T["lift"]) / 0.6) if t > T["lift"] else 0.0
                    hands, flex, drop = (socks, 1.0), 0.85 * (1 - u) + 0.08 * u, 0.42 * (1 - u)
                elif t < T["turn"]:
                    hands, flex = (socks, 1.0), 0.08
                    if t < T["scan"] + 0.5:
                        look = pos + UP * 0.12  # reads the label as the ring scanner beeps
                elif t < T["release"]:
                    u = C.smooth((t - T["turn"]) / (T["release"] - T["turn"]))
                    hands, flex, drop = (socks, 1.0), 0.08 + 0.77 * u, 0.42 * u
                elif t < T["stand"]:
                    u = C.smooth((t - T["release"]) / (T["stand"] - T["release"]))
                    hands, flex, drop = (socks, 1.0 - u), 0.85 * (1 - u), 0.42 * (1 - u)
                else:  # straightens, glances down the aisle (someone calls him), leaves
                    look = Vector((49.0, 22.6, 1.5))
            wk.set_trunk(f, yaw, flex, drop)
            if hands is not None:
                wk.set_hands(f, hands[0], fingers="flat", weight=hands[1])
            wk.set_look(f, look)
        wk.auto_steps(frames)
        wk.apply(frames)
        if P._pending_props.get(w.name):
            scene.frame_set(1)
            P._fit_props(scene, wk.arm, wk.body, P._templates[w.avatar[0]], w.heading, P._pending_props.pop(w.name))
        p = self.parcel
        if p.ob is not None:
            if p.ob.animation_data:
                p.ob.animation_data_clear()
            for f in frames:
                pos, pyaw = tr[f]
                p.ob.location, p.ob.rotation_euler = pos, (0, 0, pyaw)
                p.ob.keyframe_insert("location", frame=f)
                p.ob.keyframe_insert("rotation_euler", frame=f)
            _lin(p.ob)
            self.track_out = {f: [round(c, 3) for c in tr[f][0]] for f in frames}
        rep["deficits"] = len(wk.deficits)
        return rep

    def _tl_at(self, pyaw, pos, loc):
        """Grip faces fixed in the box frame from the grab (self.tl): the box's yaw carries them round."""
        return self.tl


# ==================================================================================================== scenario S1
# No-read rework: a parcel goes through the tunnel unread (label crumpled under the tape), rides the loop to the
# REJECT chute and drops into the blue rework bin. The exception worker sees it, walks over, takes it out, brings it
# to the bench, reads the waybill by eye and keys it in (handheld manual_encoded at SP-REWORK), and walks it back to
# the induction feed (W3 -> W4 -> past the XO-2 stair foot) where it joins the queue and is inducted again - read
# at the tunnel this time, then sorted. Runs inside the flow simulation: its timing follows the real landing time.
S1_BENCH_STAND = (26.55, 22.92)  # between the exception bench (y 21.2-22.6) and walkway W3
S1_BIN_STAND = (29.3, 21.82)
S1_FEED_STAND = (8.95, 11.62)  # north of the feed belt's end, outside the inductors' aisle
S1_BENCH_SPOT = Vector((26.6, 22.18, 0.9))


class NoReadRework(Docks):
    TOP_GRIP = False  # loose parcels: side grip from the start
    KEEP_OUT = []
    STRAIGHT_PULL = False
    def __init__(self, ctx):
        self.ctx = ctx
        self.DT, self.F0, self.F1 = ctx["DT"], ctx["F0"], ctx["F1"]
        self.rnd = random.Random(ctx["seed"] + 1001)
        self.story = None
        self.T = None
        self.v = 1.01
        w = IndWorker(0, 0, ("Female_Adult_04", "yellow", None), (0, 0), 0)
        w.name = "worker_exc_1"
        w.pos = Vector((S1_BENCH_STAND[0], S1_BENCH_STAND[1], 0.0))
        w.heading = -math.pi / 2  # at the bench, facing it (south)
        self.w = w
        self.to_bin = [S1_BENCH_STAND, (28.2, 22.95), (29.05, 22.35), S1_BIN_STAND]
        self.to_bench = [S1_BIN_STAND, (29.0, 22.5), (27.7, 22.95), S1_BENCH_STAND]
        self.to_feed = [S1_BENCH_STAND, (25.0, 23.8), (16.5, 23.8), (16.5, 14.2), (15.4, 13.0), (11.2, 12.0),
                        S1_FEED_STAND]

    def choose(self, p, t):
        """Called at each tunnel read: the first carton after t = 1.5 s becomes the no-read."""
        if self.story is None and t >= 1.5 and p.kind == "box" and max(p.dims) <= 0.4:
            self.story = p
            p.meta.update(scenario="S1", story=True)
            return True
        return False

    def landed(self, t_land, bin_pos, bin_yaw=-math.pi / 2):
        """The parcel lies in the rework bin: plan the worker's whole rework from here."""
        L = lambda pts: sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
        v, rnd = self.v, self.rnd
        T = {"land": t_land, "notice": t_land + rnd.uniform(3.5, 5.0)}
        T["walk_bin"] = T["notice"] + 0.5
        T["at_bin"] = T["walk_bin"] + L(self.to_bin) / v
        T["reach"] = T["at_bin"] + 0.3
        T["grip"] = T["reach"] + 1.2
        T["lift"] = T["grip"] + 0.25
        T["walk_bench"] = T["lift"] + 1.0
        T["at_bench"] = T["walk_bench"] + L(self.to_bench) / (v * 0.95)
        T["put_bench"] = T["at_bench"] + 0.9
        T["read"] = T["put_bench"] + 0.5  # turns it, reads the waybill by eye
        T["key"] = T["read"] + 2.2  # keys it into the handheld
        T["encoded"] = T["key"] + 2.6
        T["pick_bench"] = T["encoded"] + 0.6
        T["walk_feed"] = T["pick_bench"] + 1.0
        T["at_feed"] = T["walk_feed"] + L(self.to_feed) / (v * 0.95)
        T["put_feed"] = T["at_feed"] + 0.9  # sets it on the feed queue
        T["done"] = T["put_feed"] + 0.8
        self.T = T
        self.bin_pos = bin_pos.copy()
        # she grips its long sides as it lies: the box's grip yaw = its rest yaw, folded toward her facing (south)
        d = (bin_yaw - (-math.pi / 2) + math.pi / 2) % math.pi - math.pi / 2
        self.bin_yaw_grip = -math.pi / 2 + d

    def feed_spot(self, feed):
        """Where it is set on the feed: near the end, operator side lane (the queue may be there: the flow puts it
        at the first free spot upstream)."""
        return feed.length - 0.9

    def track(self, wk, frames):
        """Bin -> hands -> bench -> hands -> feed (world poses), for frames between the pick and the put on the feed."""
        T, dims = self.T, self.story.dims
        out = {}
        for f in frames:
            t = (f - self.F0) * self.DT
            if t < T["lift"] or t >= T["put_feed"] + 0.05:
                continue
            loc, h = wk.obj.get(f, (wk.loc0, wk.heading0))
            carry = Vector((loc.x, loc.y, 1.0 - dims[2] / 2)) + yaw_vec3(h) * 0.34
            if t < T["walk_bench"]:
                u = C.smooth((t - T["lift"]) / (T["walk_bench"] - T["lift"]))
                dy = (h - self.bin_yaw_grip + math.pi) % (2 * math.pi) - math.pi
                out[f] = (self.bin_pos.lerp(carry, u), self.bin_yaw_grip + dy * u)
            elif t < T["at_bench"]:
                out[f] = (carry, h)
            elif t < T["put_bench"]:
                u = C.smooth((t - T["at_bench"]) / (T["put_bench"] - T["at_bench"]))
                out[f] = (carry.lerp(S1_BENCH_SPOT, u), h)
            elif t < T["pick_bench"]:
                spin = 0.6 * C.smooth((t - T["put_bench"]) / (T["read"] - T["put_bench"])) if t < T["read"] else 0.6
                out[f] = (S1_BENCH_SPOT.copy(), h + spin)
            elif t < T["walk_feed"]:
                u = C.smooth((t - T["pick_bench"]) / (T["walk_feed"] - T["pick_bench"]))
                out[f] = (S1_BENCH_SPOT.lerp(carry, u), h + 0.6 * (1 - u))
            elif t < T["at_feed"] or getattr(self, "feed_pos", None) is None:  # (the set-down may fall after
                out[f] = (carry, h)                                            # the simulated window)
            else:
                u = C.smooth((t - T["at_feed"]) / (T["put_feed"] - T["at_feed"]))
                out[f] = (carry.lerp(self.feed_pos, u), h + (self.feed_yaw - h) * u)
        return out

    def build(self, scene, coll, frames):
        frames = list(frames)
        T = self.T
        fps = int(round(1 / self.DT))
        F = lambda t: self.F0 + int(round(t * fps))
        rep = {"times": {k: round(v, 2) for k, v in T.items()}}
        w = self.w
        wk = C.Worker(scene, coll, dict(role="exception", avatar=w.avatar[0], vest=w.avatar[1]), w.name, w.pos,
                      w.heading, hat_colour=1, clip_offset=29)
        wk.rig()
        rep["legs"] = wk.walk([(F(T["walk_bin"]), self.to_bin, 1.0, 0.6), (F(T["walk_bench"]), self.to_bench, 0.95, 0.8),
                               (F(T["walk_feed"]), self.to_feed, 0.95, 0.9)], frames)
        tr = self.track(wk, frames)
        dims = self.story.dims
        tl = Vector((-1, 0, 0))  # box yaw = her facing: local -x points back at her, the side faces are gripped
        for f in frames:
            t = (f - self.F0) * self.DT
            loc, h = wk.obj.get(f, (wk.loc0, wk.heading0))
            yaw, flex, drop = 0.0, 0.04, 0.0
            look = Vector((loc.x, loc.y, 1.5)) + yaw_vec3(h) * 3.0
            hands = None
            if t < T["notice"]:  # at the bench, working on the monitor / parcels in front of her
                yaw = (-math.pi / 2 - h + math.pi) % (2 * math.pi) - math.pi
                look = Vector((26.2, 21.9, 1.0)) if (t % 6.0) < 4.5 else Vector((29.3, 21.0, 0.9))
            elif t < T["walk_bin"]:
                look = Vector((29.3, 20.9, 0.7))  # sees it land in the bin
            elif T["at_bin"] <= t < T["walk_bench"]:
                yaw = (-math.pi / 2 - h + math.pi) % (2 * math.pi) - math.pi
                look = self.bin_pos + UP * 0.1
                bpos = tr.get(f, (self.bin_pos, -math.pi / 2))[0] if t >= T["lift"] else self.bin_pos
                byaw = tr.get(f, (None, -math.pi / 2))[1] if t >= T["lift"] else self.bin_yaw_grip
                socks = self._socket_world(Box(0, 0, 0, dims, 0).matrix(bpos, byaw), C.box_sockets(dims, tl))
                if t >= T["reach"]:
                    u = C.smooth((t - T["reach"]) / (T["grip"] - T["reach"]))
                    hands = (socks, u if t < T["grip"] else 1.0)
                    sq = u if t < T["lift"] else 1 - C.smooth((t - T["lift"]) / (T["walk_bench"] - T["lift"]))
                    flex, drop = 0.75 * sq, 0.36 * sq
            elif T["walk_bench"] <= t < T["walk_feed"] + 0.0 or (T["walk_feed"] <= t < T["put_feed"] + 0.6):
                pose = tr.get(f)
                if pose is not None:
                    socks = self._socket_world(Box(0, 0, 0, dims, 0).matrix(pose[0], pose[1]), C.box_sockets(dims, tl))
                    hands = (socks, 1.0)
                    look = pose[0] + UP * 0.1
                if T["at_bench"] <= t < T["walk_feed"]:
                    yaw = (-math.pi / 2 - h + math.pi) % (2 * math.pi) - math.pi
                    flex = 0.18
                    if T["put_bench"] <= t < T["pick_bench"]:  # hands off the parcel: reads it, keys it in
                        hands = None
                        look = S1_BENCH_SPOT + UP * 0.1
                if t >= T["at_feed"]:
                    yaw = (-math.pi / 2 - h + math.pi) % (2 * math.pi) - math.pi
                    flex = 0.25
                if t >= T["put_feed"] and pose is None and getattr(self, "feed_pos", None) is not None:
                    u = C.smooth((t - T["put_feed"]) / 0.6)
                    socks = self._socket_world(Box(0, 0, 0, dims, 0).matrix(self.feed_pos, self.feed_yaw),
                                               C.box_sockets(dims, tl))
                    hands = (socks, 1.0 - u)
            wk.set_trunk(f, yaw, flex, drop)
            if hands is not None:
                wk.set_hands(f, hands[0], fingers="flat", weight=hands[1])
            wk.set_look(f, look)
        wk.auto_steps(frames)
        wk.apply(frames)
        if P._pending_props.get(w.name):
            scene.frame_set(1)
            P._fit_props(scene, wk.arm, wk.body, P._templates[w.avatar[0]], w.heading, P._pending_props.pop(w.name))
        self.track_world = tr
        rep["deficits"] = len(wk.deficits)
        return rep
