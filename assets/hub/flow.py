"""Parcel flow: the hub's material handling, simulated and baked to keyframes (frames 1-300 = 30 s at 10 fps).

  blender -b --factory-startup assets/hub/build/hub_dressed.blend -P assets/hub/flow.py -- \
      --save assets/hub/build/hub_dressed.blend [--seed 7] [--preroll 60]

What moves (one cross-belt hub; the systems in the owner's list that this hub has):
  telescopic booms D02 / D05 (out of the docked lorries)  ->  collector belt  ->  induction belt (singulation gaps)
  ->  DWS + camera tunnel (read / no-read, dims, weight)  ->  merge  ->  cross-belt loop: 99 carriers at 2.0 m/s
  ->  divert at the sort-plan chute (carrier belt fires the parcel sideways)  ->  chute slide  ->  into the bag.
  No-reads go to the REJECT chute and its rework bin.
Belts queue (a parcel never closes within 10 cm of the one ahead), the merge waits for an empty carrier, and the
simulation starts --preroll seconds before frame 1, so at frame 1 the belts and loop are already busy.

Writes
  build/truth/flow_truth.json          render-side truth: every parcel, its label / chute / read status and its
                                       position at every frame (Spoor never reads this)
  build/sim/events_scan_simulated.jsonl  what the hub's systems record (label: scan_simulated): tunnel reads with
                                       measured dims / weight (+ noise), no-reads, divert confirms, bag drops
Each parcel is its own object with a unique CONTOH label (atlas tile not used by any static parcel).
"""

import argparse
import json
import math
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

ap = argparse.ArgumentParser()
ap.add_argument("--save", default="")
ap.add_argument("--seed", type=int, default=7)
ap.add_argument("--preroll", type=float, default=240.0)
ap.add_argument("--rate", type=float, default=1.4)  # parcels / s released at each boom tip
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
rnd = random.Random(args.seed)

BUILD = Path(bpy.path.abspath("//")).resolve()
HUB = BUILD.parent
SPEC = json.loads((HUB / "hub_spec.json").read_text(encoding="utf-8"))
LABELS = json.loads((BUILD / "labels" / "labels.json").read_text(encoding="utf-8"))
REG = json.loads((BUILD / "truth" / "parcels_registry.json").read_text(encoding="utf-8"))
sc = bpy.context.scene
FPS = 10
F0, F1 = 1, SPEC["render_plan"]["seconds_per_scenario"] * FPS
DT = 1.0 / FPS
T_START = datetime(2026, 10, 28, 14, 32, 7, tzinfo=timezone(timedelta(hours=8)))  # frame 1 (matches the OSD)
LOOP = SPEC["machines"]["loop"]
V_LOOP = LOOP["speed_mps"]
DECK = LOOP["deck_height"]
CHUTES = {c["id"]: c for c in SPEC["machines"]["chutes"]}
SORT = SPEC["sort_plans"][0]["chutes"]
NO_READ = 0.04

# ------------------------------------------------------------------------------------------------ loop geometry
WCX, ECX, SY, NY, CY, R = (LOOP[k] for k in ("west_cx", "east_cx", "south_y", "north_y", "cy", "radius"))
L_STR = ECX - WCX
L_ARC = math.pi * R
L_LOOP = 2 * L_STR + 2 * L_ARC


def loop_at(s):
    """(x, y, heading) at arc length s; s = 0 at the west end of the south straight, counter-clockwise."""
    s %= L_LOOP
    if s < L_STR:
        return WCX + s, SY, 0.0
    s -= L_STR
    if s < L_ARC:
        a = -math.pi / 2 + s / R
        return ECX + R * math.cos(a), CY + R * math.sin(a), a + math.pi / 2
    s -= L_ARC
    if s < L_STR:
        return ECX - s, NY, math.pi
    s -= L_STR
    a = math.pi / 2 + s / R
    return WCX + R * math.cos(a), CY + R * math.sin(a), a + math.pi / 2


CARRIERS = sorted([o for o in sc.objects if o.name.startswith("carrier_") and o.type == "MESH"], key=lambda o: o.name)
N_CAR = len(CARRIERS)
PITCH = L_LOOP / N_CAR
S_MERGE = 2.0  # merge belt joins the south straight 2 m east of its west end (30, 11)
CHUTE_S = {cid: 2 * L_STR + L_ARC - (c["x"] - WCX) - L_STR + L_STR for cid, c in CHUTES.items()}
for cid, c in CHUTES.items():  # north straight runs west: s = L_STR + L_ARC + (ECX - x)
    CHUTE_S[cid] = L_STR + L_ARC + (ECX - c["x"])

# ------------------------------------------------------------------------------------------------ belts (surface by ray)
dg = bpy.context.evaluated_depsgraph_get()
BELT_OBJS = ("conveyors", "telescopic", "booms", "induction", "collector")  # never the tunnel housing roof
GAPS = {}


def belt_z(x, y, default):
    """Top of the belt at (x, y): the first surface below 2.4 m that belongs to a conveyor (tunnel roofs skipped)."""
    o = Vector((x, y, 2.4))
    for _ in range(6):
        hit, loc, nrm, idx, ob, _ = sc.ray_cast(dg, o, Vector((0, 0, -1)), distance=3.0)
        if not hit:
            GAPS[_belt_now[0]] = GAPS.get(_belt_now[0], 0) + 1
            return default
        if any(k in ob.name.lower() for k in BELT_OBJS) and nrm.z > 0.7 and loc.z > 0.5:
            return loc.z
        o = loc + Vector((0, 0, -0.01))
    GAPS[_belt_now[0]] = GAPS.get(_belt_now[0], 0) + 1
    return default


_belt_now = [""]


class Belt:
    def __init__(self, name, pts, speed, nxt=None, entry=None):
        self.name, self.speed, self.nxt = name, speed, nxt
        _belt_now[0] = name
        self.pts = []
        for (x0, y0, z0), (x1, y1, z1) in zip(pts, pts[1:]):
            n = max(1, int(math.dist((x0, y0), (x1, y1)) / 0.1))
            for k in range(n):
                t = k / n
                x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
                self.pts.append(Vector((x, y, belt_z(x, y, z0 + (z1 - z0) * t))))
        self.pts.append(Vector((pts[-1][0], pts[-1][1], belt_z(pts[-1][0], pts[-1][1], pts[-1][2]))))
        self.cum = [0.0]
        for a, b in zip(self.pts, self.pts[1:]):
            self.cum.append(self.cum[-1] + (b - a).xy.length)
        self.length = self.cum[-1]
        self.items = []  # parcels on it, ordered from the end (index 0 = furthest along)
        self.entry = entry or {}  # name of feeding belt -> arc length where it joins this one

    def at(self, s):
        s = min(max(s, 0.0), self.length)
        lo, hi = 0, len(self.cum) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            lo, hi = (mid, hi) if self.cum[mid] <= s else (lo, mid)
        seg = self.cum[hi] - self.cum[lo] or 1.0
        t = (s - self.cum[lo]) / seg
        p = self.pts[lo].lerp(self.pts[hi], t)
        d = self.pts[hi] - self.pts[lo]
        return p, math.atan2(d.y, d.x)

    def free_at(self, s, half):
        return all(abs(q.s - s) > half + q.half + 0.1 for q in self.items)


B = {}
B["merge"] = Belt("merge", [(23.0, 9.5, 1.5), (27.6, 9.5, 1.5), (30.0, 11.0, 1.5)], 1.8)
B["tunnel"] = Belt("tunnel", [(17.5, 9.5, 1.5), (23.0, 9.5, 1.5)], 1.5, "merge")
B["induction"] = Belt("induction", [(5.6, 9.5, 1.0), (17.5, 9.5, 1.0)], 1.5, "tunnel")
# the collector turns east into a slow accumulation belt that stops at its end plate; the inductors take parcels off
# that queue (stations.Inductors) - nothing passes from feed to induction by itself
B["feed"] = Belt("feed", [(5.0, 11.1, 1.0), (9.2, 11.1, 1.0)], 0.5, None)
B["collector"] = Belt("collector", [(5.0, 28.0, 1.0), (5.0, 11.1, 1.0)], 1.2, "feed",
                      entry={"boom_D05": 28.0 - 23.0, "boom_D02": 28.0 - 11.0})
B["boom_D05"] = Belt("boom_D05", [(-1.15, 23.0, 0.97), (5.0, 23.0, 1.0)], 0.8, "collector")  # from the boom nose
B["boom_D02"] = Belt("boom_D02", [(-1.15, 11.0, 0.97), (5.0, 11.0, 1.0)], 0.8, "collector")
ORDER = ["merge", "tunnel", "induction", "feed", "collector", "boom_D05", "boom_D02"]  # downstream first

# ------------------------------------------------------------------------------------------------ parcels
used_tiles = {p["tile"] for p in REG.get("parcels", REG) if "tile" in p}
free_tiles = [lb["tile"] for lb in LABELS["labels"] if not lb.get("reserved_for_scenarios") and lb["tile"] not in used_tiles]
rnd.shuffle(free_tiles)
COLS, ROWS = LABELS["cols"], LABELS["rows"]
atlas = bpy.data.images.load(str(BUILD / "labels" / "label_atlas.png"), check_existing=True)


def mat_simple(name, rgb, rough=0.5):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    return m


label_mat = bpy.data.materials.get("flow_label")
if label_mat is None:
    label_mat = bpy.data.materials.new("flow_label")
    label_mat.use_nodes = True
    nt = label_mat.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = atlas
    nt.links.new(tex.outputs["Color"], nt.nodes.get("Principled BSDF").inputs["Base Color"])
BODY = {"box": bpy.data.materials.get("cardboard") or mat_simple("flow_card", (0.42, 0.29, 0.17), 0.8),
        "box_white": bpy.data.materials.get("cardboard_white") or mat_simple("flow_card_w", (0.8, 0.79, 0.75), 0.8)}
for nm, rgb in (("grey", (0.26, 0.27, 0.28)), ("black", (0.012, 0.012, 0.013)), ("white", (0.81, 0.81, 0.82)),
                ("red", (0.55, 0.02, 0.015)), ("blue", (0.015, 0.08, 0.43)), ("purple", (0.14, 0.03, 0.26))):
    BODY[f"mailer_{nm}"] = bpy.data.materials.get(f"flyer_{nm}") or mat_simple(f"flow_flyer_{nm}", rgb, 0.4)
TAPE = mat_simple("flow_tape", (0.42, 0.33, 0.2), 0.3)
coll = bpy.data.collections.get("Flow") or bpy.data.collections.new("Flow")
if coll.name not in sc.collection.children:
    sc.collection.children.link(coll)

BOX_DIMS = [(0.2, 0.15, 0.1), (0.25, 0.18, 0.12), (0.3, 0.2, 0.15), (0.3, 0.3, 0.25), (0.35, 0.25, 0.2),
            (0.4, 0.3, 0.25), (0.45, 0.35, 0.3), (0.25, 0.25, 0.25), (0.4, 0.25, 0.1)]
MAILER_DIMS = [(0.24, 0.17, 0.035), (0.32, 0.24, 0.04), (0.37, 0.27, 0.045), (0.44, 0.31, 0.05)]


def pick_look():
    kind = rnd.choices(["mailer", "box"], weights=[60, 40])[0]
    if kind == "box":
        return kind, rnd.choice(BOX_DIMS), ("box_white" if rnd.random() < 0.15 else "box")
    return kind, rnd.choice(MAILER_DIMS), "mailer_" + rnd.choices(["grey", "black", "white", "red", "blue", "purple"],
                                                                  weights=[30, 24, 14, 11, 11, 10])[0]


def make_parcel(k, tile, kind, dims, body):
    """One parcel mesh: body (material 0), tape (1) on boxes, label quad (2) UV'd to its atlas tile on top."""
    w, d, h = dims
    me = bpy.data.meshes.new(f"flow_parcel_{k:03d}")
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.verify()
    r = bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, 0, h / 2)) @ Matrix.Diagonal((w, d, h, 1)))
    for f in {f for v in r["verts"] for f in v.link_faces}:
        f.material_index = 0
    if kind == "mailer":  # pillow: puff the top
        for v in r["verts"]:
            pass
    if kind == "box":
        r2 = bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, 0, h + 0.0008))
                                   @ Matrix.Diagonal((w + 0.002, 0.05, 0.0016, 1)))
        for f in {f for v in r2["verts"] for f in v.link_faces}:
            f.material_index = 1
    lw, lh = min(0.10, w * 0.7), min(0.15, d * 0.7)
    col, row = tile % COLS, tile // COLS
    u0, v0 = col / COLS, (ROWS - 1 - row) / ROWS
    ang = rnd.uniform(-0.4, 0.4)
    ca, sa = math.cos(ang), math.sin(ang)
    cx, cy = rnd.uniform(-0.15, 0.15) * w, rnd.uniform(-0.15, 0.15) * d
    corners = [(-lw / 2, -lh / 2, 0, 0), (lw / 2, -lh / 2, 1, 0), (lw / 2, lh / 2, 1, 1), (-lw / 2, lh / 2, 0, 1)]
    vs = [bm.verts.new((cx + x * ca - y * sa, cy + x * sa + y * ca, h + 0.0025)) for x, y, _, _ in corners]
    f = bm.faces.new(vs)
    f.material_index = 2
    for loop, (_, _, uu, vv) in zip(f.loops, corners):
        loop[uvl].uv = (u0 + uu / COLS, v0 + vv / ROWS)
    bm.to_mesh(me)
    bm.free()
    for m in (BODY[body], TAPE, label_mat):
        me.materials.append(m)
    ob = bpy.data.objects.new(f"flow_parcel_{k:03d}", me)
    coll.objects.link(ob)
    lab = LABELS["labels"][tile]
    return ob, dict(kind=kind, dims_m=[w, d, h], body=body, tile=tile, parcel_id=lab["parcel_id"],
                    chute=lab.get("chute"), destination=lab.get("destination"))


FREE_BY_CHUTE = {}
for _t in free_tiles:
    FREE_BY_CHUTE.setdefault(LABELS["labels"][_t].get("chute"), []).append(_t)
DESTS = [c for c in FREE_BY_CHUTE if c in CHUTES and c != "REJECT"]


class Parcel:
    """Simulated from spawn; its object + unique label are only made if it is still visible at frame 1 or later
    (parcels bagged during the pre-roll are part of the bags' static contents)."""
    def __init__(self, k):
        self.k = k
        self.kind, self.dims, self.body = pick_look()
        self.dest = rnd.choice(DESTS)
        self.ob = None
        self.meta = dict(kind=self.kind, dims_m=list(self.dims), body=self.body, chute=self.dest)
        self.half = max(self.dims[:2]) / 2
        self.belt, self.s = None, 0.0
        self.state = "belt"  # belt | merge_wait | carrier | divert | chute | bag
        self.car = None
        self.read = rnd.random() > NO_READ
        self.target = self.dest if self.read else "REJECT"
        self.yaw_off = rnd.uniform(-0.25, 0.25)
        self.track = {}
        self.anim = None  # (t0, list of (t, pos, yaw)) for scripted moves
        self.rest = None

    def materialise(self):
        tile = FREE_BY_CHUTE[self.dest].pop() if FREE_BY_CHUTE.get(self.dest) else None
        if tile is None:
            return False
        self.ob, meta = make_parcel(self.k, tile, self.kind, self.dims, self.body)
        self.meta.update(meta)
        return True


parcels, events = [], []


def ev(t, kind, parcel=None, **kw):
    """parcel: the Parcel (its waybill is only known once its label is assigned at bake; no-reads stay None)."""
    if t < 0:
        return
    events.append(dict(label="scan_simulated", t_s=round(t, 2), time=(T_START + timedelta(seconds=t)).isoformat(
        timespec="milliseconds"), event=kind, _p=parcel, **kw))


# ------------------------------------------------------------------------------------------------ station workers
sys.path.insert(0, str(HUB))
import people  # noqa: E402
import stations  # noqa: E402

people.RB = BUILD / "third_party" / "rocketbox"
_k_station = [5000]


def _next_k():
    _k_station[0] += 1
    return _k_station[0]


ST = stations.Docks(dict(seed=args.seed, DT=DT, F0=F0, F1=F1, B=B, BOX_DIMS=BOX_DIMS, Parcel=Parcel, next_k=_next_k))
IND = stations.Inductors(dict(seed=args.seed, DT=DT, F0=F0, F1=F1, B=B))

# ------------------------------------------------------------------------------------------------ simulate
car_s0 = [k * PITCH for k in range(N_CAR)]
car_load = [None] * N_CAR
next_spawn = {"boom_D05": -args.preroll, "boom_D02": -args.preroll + 0.6}
bag_fill = {cid: 0 for cid in CHUTES}
t = -args.preroll
steps = int(round((args.preroll + (F1 - F0) * DT) / DT))
for step in range(steps + 1):
    t = -args.preroll + step * DT
    # 1. spawn at the boom tips (inside the lorries)
    for bn in ("boom_D05", "boom_D02"):
        if bn in ST.belts and t >= -1e-6:  # the unloaders' cartons, at their release frames
            for pk in ST.spawns(bn, t):
                p = pk.parcel
                p.belt, p.s = bn, max(pk.s - B[bn].speed * DT, 0.0)  # the belt step below moves it onto pk.s
                if not B[bn].free_at(p.s, p.half):  # (checked where it is put: the belt step follows)
                    print(f"WARN station release onto an occupied nose: {bn} t={t:.1f} at s={pk.s:.2f} "
                          f"items={[(round(q.s, 2), q.k, getattr(q, 'station', None) is not None) for q in B[bn].items if q.s < 1.5]}",
                          flush=True)
                B[bn].items.append(p)
                parcels.append(p)
            continue
        rate = ST.preroll_rate(bn) if bn in ST.belts else args.rate
        if t >= next_spawn[bn] and B[bn].free_at(0.15, 0.3):
            p = Parcel(len(parcels))
            p.belt, p.s = bn, 0.15
            B[bn].items.append(p)
            parcels.append(p)
            next_spawn[bn] = t + rnd.expovariate(rate) + 0.25
    # 2. belts, downstream first
    feed_before = {id(p): p.s for p in B["feed"].items}
    for bn in ORDER:
        belt = B[bn]
        belt.items.sort(key=lambda q: -q.s)
        lead_s = None
        for i, p in enumerate(belt.items):
            if getattr(p, "frozen", False):  # reserved by an inductor: held on its zone of the queue
                continue
            want = p.s + belt.speed * DT
            if i > 0:
                ahead = belt.items[i - 1]
                want = min(want, ahead.s - ahead.half - p.half - 0.1)
            p.s = max(p.s, min(want, belt.length - (p.half + 0.02 if belt.nxt is None and bn != "merge" else 0.0)))
        done = [p for p in belt.items if p.s >= belt.length - 1e-6]
        for p in done:
            if bn == "merge":
                p.state = "merge_wait"
                continue
            if belt.nxt is None:
                continue
            nxt = B[belt.nxt]
            s_in = nxt.entry.get(bn, 0.0)
            if nxt.free_at(s_in, p.half):
                belt.items.remove(p)
                p.belt, p.s = belt.nxt, s_in
                nxt.items.append(p)
                if belt.nxt == "merge":
                    pass
                if bn == "tunnel" or (belt.nxt == "merge"):
                    pass
            # else it waits at the end (belt stalls behind it)
        # tunnel read point (exit read at x 22.2)
        if bn == "tunnel":
            for p in belt.items:
                if not p.meta.get("scanned") and belt.at(p.s)[0].x >= 22.2:
                    p.meta["scanned"] = round(t, 2)
                    w, d, h = p.meta["dims_m"]
                    vol = w * d * h
                    kg = max(0.08, vol * rnd.uniform(90, 260)) if p.meta["kind"] == "box" else rnd.uniform(0.1, 1.2)
                    p.meta["weight_g"] = int(kg * 1000)
                    if p.read:
                        ev(t, "tunnel_read", parcel=p, scan_point="SP-TUNNEL",
                           dims_mm=[int(x * 1000 + rnd.gauss(0, 4)) for x in (w, d, h)],
                           weight_g=int(kg * 1000 * rnd.uniform(0.98, 1.02)), photo=f"tunnel_{p.k:03d}.png")
                    else:
                        ev(t, "tunnel_no_read", scan_point="SP-TUNNEL",
                           dims_mm=[int(x * 1000 + rnd.gauss(0, 4)) for x in (w, d, h)],
                           weight_g=int(kg * 1000 * rnd.uniform(0.98, 1.02)), photo=f"tunnel_{p.k:03d}.png")
    # 2b. inductors work the feed queue (stopped parcels only)
    IND.step(t, [p for p in B["feed"].items if abs(p.s - feed_before.get(id(p), -9.0)) < 1e-6])
    # 3. merge onto the first empty carrier passing the merge point
    for p in [q for q in B["merge"].items if q.state == "merge_wait"]:
        for k in range(N_CAR):
            s_k = (car_s0[k] + V_LOOP * t) % L_LOOP
            if car_load[k] is None and 0.0 <= (s_k - S_MERGE) % L_LOOP < V_LOOP * DT:
                car_load[k] = p
                p.car, p.state = k, "carrier"
                B["merge"].items.remove(p)
                ev(t, "induct_to_carrier", parcel=p if p.read else None, scan_point="SP-INDUCT", carrier=k + 1)
                break
    # 4. carriers: divert at the target chute (north straight, moving west)
    for k in range(N_CAR):
        p = car_load[k]
        if p is None:
            continue
        s_prev = (car_s0[k] + V_LOOP * (t - DT)) % L_LOOP
        s_k = (car_s0[k] + V_LOOP * t) % L_LOOP
        cs = CHUTE_S[p.target]
        if (s_prev < cs <= s_k) or (s_prev > s_k and (cs > s_prev or cs <= s_k)):
            car_load[k] = None
            p.state, p.car = "divert", None
            c = CHUTES[p.target]
            x0, y0, _ = loop_at(cs)
            n = bag_fill[p.target]
            bag_fill[p.target] += 1
            if p.target == "REJECT":
                land = Vector((c["x"] + rnd.uniform(-0.25, 0.25), 20.9 + rnd.uniform(-0.15, 0.15), 0.42 + 0.05 * min(n, 4)))
            else:
                land = Vector((c["x"] + rnd.uniform(-0.2, 0.2), c["bag_frame_y"] + rnd.uniform(-0.12, 0.12),
                               0.55 + 0.035 * min(n, 8)))
            top = Vector((c["x"], c["mouth_y"] + 0.15, DECK - 0.05))
            end = Vector((c["x"] + rnd.uniform(-0.15, 0.15), c["end_y"] - 0.05, c["lip_z"] + 0.02))
            p.anim = [(t, Vector((x0, y0, DECK)), math.pi), (t + 0.3, top, math.pi + 0.3),
                      (t + 0.3 + (end - top).length / 1.4, end, math.pi + 0.5),
                      (t + 0.3 + (end - top).length / 1.4 + 0.35, land, math.pi + rnd.uniform(-1, 1))]
            ev(t, "divert_confirm", parcel=p if p.read else None, scan_point=f"SP-DIV-{p.target}", carrier=k + 1,
               chute=p.target)
            ev(p.anim[-1][0], "bag_drop" if p.target != "REJECT" else "reject_bin", chute=p.target)  # photo-eye only
    # 5. record positions (frames 1..300 only)
    if t >= -1e-6:
        f = F0 + int(round(t / DT))
        for p in parcels:
            if p.state in ("belt", "merge_wait"):
                pos, yaw = B[p.belt].at(p.s)
                p.track[f] = (pos.copy(), yaw + p.yaw_off)
            elif p.state == "carrier":
                x, y, hd = loop_at(car_s0[p.car] + V_LOOP * t)
                p.track[f] = (Vector((x, y, DECK)), hd + math.pi / 2 + p.yaw_off * 0.5)
            elif p.state == "divert":
                kf = p.anim
                if t >= kf[-1][0]:
                    p.state = "bag"
                    p.rest = (kf[-1][1].copy(), kf[-1][2])
                    p.track[f] = p.rest
                else:
                    for (ta, pa, ya), (tb, pb, yb) in zip(kf, kf[1:]):
                        if ta <= t <= tb:
                            u = (t - ta) / max(tb - ta, 1e-6)
                            p.track[f] = (pa.lerp(pb, u), ya + (yb - ya) * u)
                            break
            elif p.state == "bag":
                p.track[f] = p.rest
    elif any(p.state == "divert" and t >= p.anim[-1][0] for p in parcels):
        for p in parcels:
            if p.state == "divert" and t >= p.anim[-1][0]:
                p.state = "bag"
                p.rest = (p.anim[-1][1].copy(), p.anim[-1][2])

# inductors: parcels in the hands at the end; tracks while held
IND.finish()
for p, tr in IND.held_tracks().items():
    for f, (pos, yaw) in tr.items():
        p.track[f] = (pos.copy(), yaw)
# station cartons: still in the hands at the end of the window -> parcels with their carry track only
for pk in ST.picks:
    if pk.parcel is not None and pk.parcel not in parcels:
        pk.parcel.state = "held"
        parcels.append(pk.parcel)
for p, tr in ST.pre_tracks().items():
    for f, (pos, yaw) in tr.items():
        p.track.setdefault(f, (pos.copy(), yaw))


# ------------------------------------------------------------------------------------------------ bake
def linear(ob):
    act = ob.animation_data.action if ob.animation_data else None
    if act is None:
        return
    bags = [cb for layer in getattr(act, "layers", []) for st in layer.strips for cb in st.channelbags]
    for fc in [fc for cb in bags for fc in cb.fcurves] or list(getattr(act, "fcurves", [])):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"



for k in range(N_CAR):  # carriers
    ob = CARRIERS[k]
    for f in range(F0, F1 + 1):
        x, y, hd = loop_at(car_s0[k] + V_LOOP * (f - F0) * DT)
        ob.location = (x, y, DECK)
        ob.rotation_euler = (0, 0, hd)
        ob.keyframe_insert("location", frame=f)
        ob.keyframe_insert("rotation_euler", frame=f)
    linear(ob)
kept = 0
truth = []
for p in parcels:
    if not p.track:
        continue
    frames_ = sorted(p.track)
    if p.state == "bag" and all((p.track[f][0] - p.track[frames_[0]][0]).length < 1e-4 for f in frames_):
        continue  # bagged before frame 1: part of the bag's static contents
    if not p.materialise():
        continue
    kept += 1
    frames = sorted(p.track)
    static = all((p.track[f][0] - p.track[frames[0]][0]).length < 1e-4 for f in frames)
    for f in (frames[:1] if static else frames):
        pos, yaw = p.track[f]
        p.ob.location = pos
        p.ob.rotation_euler = (0, 0, yaw)
        if not static:
            p.ob.keyframe_insert("location", frame=f)
            p.ob.keyframe_insert("rotation_euler", frame=f)
    linear(p.ob)
    truth.append(dict(object=p.ob.name, **{k: v for k, v in p.meta.items() if k != "scanned"},
                      read=p.read, target_chute=p.target, tunnel_t_s=p.meta.get("scanned"),
                      track={f: [round(c, 3) for c in p.track[f][0]] for f in frames[::1]}))


def wall_mesh(name, boxes, wcoll):
    """Static cartons (each uniquely labelled, label on top) joined into one object per truck."""
    obs = []
    for i, b in enumerate(boxes):
        dest = rnd.choice(DESTS)
        tile = FREE_BY_CHUTE[dest].pop() if FREE_BY_CHUTE.get(dest) else None
        if tile is None:
            continue
        ob, meta = make_parcel(9000 + len(WALL_TRUTH), tile, "box", tuple(b.dims),
                               "box_white" if rnd.random() < 0.1 else "box")
        ob.matrix_world = b.matrix()
        WALL_TRUTH.append(dict(object=name, parcel_id=meta["parcel_id"], tile=tile, dims_m=list(b.dims),
                               position_m=[round(c, 3) for c in b.pos], chute=meta["chute"]))
        obs.append(ob)
    if not obs:
        return 0
    for o in obs:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        wcoll.objects.link(o)
    with bpy.context.temp_override(active_object=obs[0], selected_editable_objects=obs, object=obs[0]):
        bpy.ops.object.join()
    obs[0].name = name
    return len(obs)


WALL_TRUTH = []
people_coll = bpy.data.collections.get("People") or bpy.data.collections.new("People")
if people_coll.name not in sc.collection.children:
    sc.collection.children.link(people_coll)
station_report = ST.build(sc, people_coll, range(F0, F1 + 1), wall_mesh)
station_report["induction"] = IND.build(sc, people_coll, range(F0, F1 + 1))
sc.frame_set(F0)
print("STATIONS " + json.dumps(station_report), flush=True)

(BUILD / "truth").mkdir(exist_ok=True)
(BUILD / "truth" / "flow_truth.json").write_text(json.dumps(
    {"note": "render-side truth; Spoor never reads this", "fps": FPS, "frames": [F0, F1], "t0": T_START.isoformat(),
     "loop_speed_mps": V_LOOP, "parcels": truth, "truck_walls": WALL_TRUTH,
     "station_workers": station_report}), encoding="utf-8")
(BUILD / "sim").mkdir(exist_ok=True)
with open(BUILD / "sim" / "events_scan_simulated.jsonl", "w", encoding="utf-8") as fh:
    for e in sorted(events, key=lambda e: e["t_s"]):
        q = e.pop("_p")
        if q is not None and q.ob is None:
            continue  # its parcel was never materialised (pre-roll only)
        e["parcel_id"] = q.meta.get("parcel_id") if q is not None else None
        fh.write(json.dumps(e) + "\n")
moving = sum(1 for p in parcels if p.ob is not None and any((p.track[f][0] - p.track[min(p.track)][0]).length > 0.01
                                                             for f in p.track))
on_loop_f1 = sum(1 for p in parcels if p.ob is not None and 1 in p.track and abs(p.track[1][0].z - DECK) < 0.05)
print("FLOW " + json.dumps({"belt_points_without_surface": GAPS, "parcels": kept, "moving_in_window": moving, "on_loop_at_frame1": on_loop_f1,
                            "carriers": N_CAR, "events": len(events),
                            "events_by_kind": {k: sum(1 for e in events if e['event'] == k) for k in
                                               sorted({e['event'] for e in events})},
                            "bag_fill": {k: v for k, v in bag_fill.items() if v}}), flush=True)
if args.save:
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(args.save).resolve()), compress=True)
