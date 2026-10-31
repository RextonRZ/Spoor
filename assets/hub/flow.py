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
import os
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
ap.add_argument("--scenario", default="S0")  # S0 control; S2 removal into the blind spot; ...
ap.add_argument("--seconds", type=float, default=0.0)  # scenario length override (default: render_plan, 30 s)
ap.add_argument("--spec", default="")  # spec variant (default hub_spec.json; e.g. hub_spec_lineAb.json for line A (b))
ap.add_argument("--mocap-docks", action="store_true")  # stations.MocapDocks instead of Docks (M5, in progress)
ap.add_argument("--lookalike-t", type=float, default=-20.0)  # S2: when the look-alike carton enters the collector (-20: tunnel 4.7 s, on the loop 10-33 s, C08)
ap.add_argument("--scan-extend", type=float, default=0.0)
# stations left unstaffed in this run (comma list; "opener"): a station whose old motion is not convincing is not
# filmed (021d question, owner rule "remove what can't be made convincing"); its heap / wall stays, nobody works it
ap.add_argument("--unstaff", default="")  # "opener", "lineB"  # with --sim-only: run on this long past the window and
# write its scan log (parcel numbers, not ids: splice_scan_log.py takes the window from the full run, builder note 0445)
ap.add_argument("--sim-only", default="")  # write the simulation's QA trace (json) here and stop: no workers, no bake
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
rnd = random.Random(args.seed)

BUILD = Path(bpy.path.abspath("//")).resolve()
HUB = BUILD.parent
SPEC = json.loads(((HUB / args.spec) if args.spec and not Path(args.spec).is_absolute() else Path(args.spec)
                   if args.spec else HUB / "hub_spec.json").read_text(encoding="utf-8"))
LABELS = json.loads((BUILD / "labels" / "labels.json").read_text(encoding="utf-8"))
REG = json.loads((BUILD / "truth" / "parcels_registry.json").read_text(encoding="utf-8"))
sc = bpy.context.scene
FPS = 10
F0, F1 = 1, int(round((args.seconds or SPEC["render_plan"]["seconds_per_scenario"]) * FPS))
SCEN = args.scenario.upper()
SUFFIX = "" if SCEN == "S0" else f"_{SCEN}"  # S0 keeps the default file names (the frontend's seed reads them)
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


def loop_ride_s(chute):
    """Line A carrier load (SP-INDUCT, at the merge) to the divert at `chute`, first time round: the carrier rides the
    loop at V_LOOP and tips as it reaches the chute. Scenario histories time their divert from it (builder note 1040:
    S2's hard-coded 21.7 s was shorter than the 25.9 s the loop takes, a false 'records disagree')."""
    return ((CHUTE_S[chute] - S_MERGE) % L_LOOP) / V_LOOP

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
        self.sloped = max(q.z for q in self.pts) - min(q.z for q in self.pts) > 0.005
        self.items = []  # parcels on it, ordered from the end (index 0 = furthest along)
        self.entry = entry or {}  # name of feeding belt -> arc length where it joins this one

    def at(self, s):
        if s < 0.0:  # before the start (a boom ending short of the belt it feeds): along the first segment
            p0, yaw0 = self.at(0.0)
            return p0 + Vector((math.cos(yaw0), math.sin(yaw0), 0.0)) * s, yaw0
        s = min(s, self.length)
        lo, hi = 0, len(self.cum) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            lo, hi = (mid, hi) if self.cum[mid] <= s else (lo, mid)
        seg = self.cum[hi] - self.cum[lo] or 1.0
        t = (s - self.cum[lo]) / seg
        p = self.pts[lo].lerp(self.pts[hi], t)
        d = self.pts[hi] - self.pts[lo]
        return p, math.atan2(d.y, d.x)

    def rest(self, s, half_len, n=9):
        """(z, pitch) of a rigid flat-bottomed parcel centred at s on a sloped belt: it rests on the edge of the
        surface's upper convex hull under its centre of mass (yaw alone left the downhill end 4-5 cm inside the
        ramp: collision check)."""
        pts = [(u, self.at(s + u)[0].z) for u in (half_len * (2 * i / (n - 1) - 1) for i in range(n))]
        hull = []
        for q in pts:  # upper hull, left to right
            while len(hull) >= 2 and ((hull[-1][0] - hull[-2][0]) * (q[1] - hull[-2][1])
                                      - (hull[-1][1] - hull[-2][1]) * (q[0] - hull[-2][0])) >= 0:
                hull.pop()
            hull.append(q)
        for a, b in zip(hull, hull[1:]):
            if a[0] <= 0.0 <= b[0]:
                k = (b[1] - a[1]) / max(b[0] - a[0], 1e-9)
                return a[1] - k * a[0], math.atan(k)
        return self.at(s)[0].z, 0.0

    def free_at(self, s, half):
        return all(abs(q.s - s) > half + q.half + 0.1 for q in self.items)


B = {}
BOOM_END_X = 4.55  # booms end at the collector's west side frame (build_hub.BOOM_END_X)
B["merge"] = Belt("merge", [(23.0, 9.5, 1.5), (27.6, 9.5, 1.5), (30.0, 11.0, 1.5)], 1.8)
B["tunnel"] = Belt("tunnel", [(17.5, 9.5, 1.5), (23.0, 9.5, 1.5)], 1.5, "merge")
B["induction"] = Belt("induction", [(5.6, 9.5, 1.0), (15.0, 9.5, 1.0), (17.5, 9.5, 1.5)], 1.5, "tunnel")  # ramps up
# to the tunnel deck like the conveyor mesh (flat at 1.0 m the parcels ran through the ramp)
# the collector turns east into a slow accumulation belt that stops at its end plate; the inductors take parcels off
# that queue (stations.Inductors) - nothing passes from feed to induction by itself
sys.path.insert(0, str(HUB))
import line_a_geom  # noqa: E402

LINE_A_B = SPEC.get("line_a", {}).get("layout") == "b"
LA, LA_MOUTHS, LA_INDUCT, LA_MERGES = line_a_geom.derive(SPEC.get("line_a"))
LA_LINE = []  # line A (b) belts, downstream first (ORDER)
if not LINE_A_B:
    B["feed"] = Belt("feed", [(5.0, 10.85, 1.0), (9.2, 10.85, 1.0)], 0.5, None,
                     entry={"boom_D02": BOOM_END_X - 5.0})
    B["collector"] = Belt("collector", [(5.0, 28.0, 1.0), (5.0, 10.85, 1.0)], 1.2, "feed",
                          entry={"boom_D05": 28.0 - 23.0})
else:  # line A (b): the feed line runs north of the inductors (y 12.25) and stops at the last table's mouth (a zone
    # stop just past it: parcels further on could never be diverted); diverters push parcels onto 4 gravity roller tables; each
    # inductor sets down on his own induct belt, which merges onto belt A when the gap is there (the side-merge rule
    # below). D02's boom (south of the feed line now) hands over to a stub belt running north into the feed corner.
    FY = LA["feed_y"]
    _y0t, _y1t = line_a_geom.table_ys(LA)
    B["feed"] = Belt("feed", [(5.0, FY, 1.0), (LA_MOUTHS[-1] + 0.3, FY, 1.0)], 0.8, None)  # end stop: the queue's
    # head parcel stops inside the last mouth. 0.8 m/s (sim-only QA, seeds 7 / 11): at 0.5 the 7.8 m feed could not
    # bring parcels past tables 1-2, the collector backed up to 20 and I4 never worked; at 1.0 two set-downs met a
    # parcel still on the induct belt
    B["collector"] = Belt("collector", [(5.0, 28.0, 1.0), (5.0, FY, 1.0)], 1.2, "feed",
                          entry={"boom_D05": 28.0 - 23.0})
    B["d02_stub"] = Belt("d02_stub", [(5.0, 10.6, 1.0), (5.0, FY - LA["feed_half"] - 0.05, 1.0)], 0.8, "feed",
                         entry={"boom_D02": 11.0 - 10.6})
    for _k, (_mx, ((_sx, _sy), (_ex, _ey)), _gx) in enumerate(zip(LA_MOUTHS, LA_INDUCT, LA_MERGES)):
        # the real surfaces under a parcel crossing over: the feed belt flat at 1.0 m to its south edge, the 5 cm step
        # down onto the table head (0.95 m), the rollers falling to the stop (0.88 m); one straight slope from the feed's
        # centre line left a parcel still half on the feed 2-4 cm inside its belt (hub collision run, 31 Oct)
        B[f"table_{_k}"] = Belt(f"table_{_k}", [(_mx, FY, 1.0), (_mx, FY - LA["feed_half"], 1.0),
                                                (_mx, _y1t, LA["table_top"][0]), (_mx, _y0t - 0.03, LA["table_top"][1])],
                                0.4)
        B[f"induct_{_k}"] = Belt(f"induct_{_k}", [(_sx, _sy, 1.0), (_ex, _ey, 1.0)], 1.5, "induction")
        B["induction"].entry[f"induct_{_k}"] = _gx - 5.6
    LA_LINE = [f"induct_{k}" for k in reversed(range(len(LA_MOUTHS)))] + ["feed"] + \
        [f"table_{k}" for k in range(len(LA_MOUTHS))]
B["boom_D05"] = Belt("boom_D05", [(-1.15, 23.0, 1.0), (BOOM_END_X, 23.0, 1.0)], 0.8, "collector")  # from the nose
# the D02 boom (y 11.0) lines up with the start of the feed: it hands over there, taking turns with the collector
# (it used to join the collector 15 cm before the collector's own corner, and the two queues ran through each other)
B["boom_D02"] = Belt("boom_D02", [(-1.15, 11.0, 1.0), (BOOM_END_X, 11.0, 1.0)], 0.8,
                     "d02_stub" if LINE_A_B else "feed")
# induction line B (B2 pre-review #4): belt B from the gaylord station (stations.GaylordInductors) ramps up through DWS
# arch B and merges onto the south straight; its end waits for a booked empty carrier like the main merge belt
_CB = next(c for c in SPEC["machines"]["conveyors"] if c["id"] == "induction_B")
B["induction_B"] = Belt("induction_B", [(x, y, z) for (x, y), z in zip(_CB["path"], _CB["heights"])], 1.5)  # as
# line A (at 1.2 m/s the third, downstream inductor seldom found a gap)
ORDER = (["induction_B", "merge", "tunnel", "induction", "feed", "collector", "boom_D05", "boom_D02"] if not LINE_A_B
         else ["induction_B", "merge", "tunnel", "induction"] + LA_LINE
         + ["collector", "d02_stub", "boom_D05", "boom_D02"])  # downstream first


def _s_near(belt, xy):
    return min(zip(belt.cum, belt.pts), key=lambda cp: (cp[1].xy - Vector(xy)).length)[0]


_SPB = {sp["id"]: sp["position_m"] for sp in SPEC["scan_points"]}
# (loop s, scan point, wait margin: how far short of the loop the head parcel waits - clear of the parcels riding
# the carriers; belt B comes in at 61 deg, so 0.45 m short was still inside their band: QA parcel_overlap)
MERGES = {"merge": (S_MERGE, "SP-INDUCT", 1.37), "induction_B": (_CB["path"][-1][0] - WCX, "SP-INDUCT-B", 0.83)}
# (waiting fully outside the carriers' band: 0.45 m short, line A's head parcel sat over the passing carriers - the
# merge belts now end at the band's edge, build_hub. Line A's merge timing moves by a fraction of a second)
READS = {"tunnel": (22.2 - 17.5, "SP-TUNNEL"),  # exit read at x 22.2
         "induction_B": (_s_near(B["induction_B"], _SPB["SP-TUNNEL-B"][:2]), "SP-TUNNEL-B")}

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
        self.lat = 0.0  # across the belt (+ = left of travel)
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
        tile = getattr(self, "forced_tile", None)  # scenario parcels: a reserved label (e.g. the look-alike pair)
        if tile is None:
            tile = FREE_BY_CHUTE[self.dest].pop() if FREE_BY_CHUTE.get(self.dest) else None
        if tile is None:
            return False
        self.ob, meta = make_parcel(self.k, tile, self.kind, self.dims, self.body)
        self.meta.update(meta)
        return True


parcels, events = [], []


def ev(t, kind, parcel=None, history=False, **kw):
    """parcel: the Parcel (its waybill is only known once its label is assigned at bake; no-reads stay None).
    history=True: an event from earlier in the shift (before the window) that the log does contain."""
    if t < 0 and not history and not (args.sim_only and args.scan_extend):  # (--scan-extend: the pre-roll's too)
        return
    events.append(dict(label="scan_simulated", t_s=round(t, 2), time=(T_START + timedelta(seconds=t)).isoformat(
        timespec="milliseconds"), event=kind, _p=parcel, **kw))


# ------------------------------------------------------------------------------------------------ station workers
sys.path.insert(0, str(HUB))
import people  # noqa: E402
import stations  # noqa: E402

people.RB = BUILD / "third_party" / "rocketbox"
stations.SCENARIO = SCEN
_k_station = [5000]


def _next_k():
    _k_station[0] += 1
    return _k_station[0]


T_STOP = (F1 - F0) * DT + (args.scan_extend if args.sim_only else 0.0)  # the stations work on through a
# --scan-extend at their window pace (sim-only: else the feed stopped at the window's end and the long scan log
# went quiet; a longer window would also have slowed line B's pace inside it)
UNSTAFF = {x.strip() for x in args.unstaff.split(",") if x.strip()}
if "dock_D02" in UNSTAFF:  # D02's lorry is unloaded (empty, waiting to leave), its boom pulled back to the door:
    stations.DOCKS[:] = [d for d in stations.DOCKS if d["door"] != "D02"]  # no wall, no unloaders, nothing arriving
ST = (stations.MocapDocks if args.mocap_docks else stations.Docks)(  # M5: the unloaders on mocap (in progress:
    # first hub runs had the hands 0.4-0.76 m off the wall cartons, being debugged - off by default)
    dict(seed=args.seed, DT=DT, F0=F0, F1=F1, T_STOP=T_STOP, B=B, BOX_DIMS=BOX_DIMS, Parcel=Parcel, next_k=_next_k, parcels=parcels))
IND = (stations.Inductors(dict(seed=args.seed, DT=DT, F0=F0, F1=F1, T_STOP=T_STOP, B=B)) if not LINE_A_B else
       stations.MocapInductors(dict(seed=args.seed, DT=DT, F0=F0, F1=F1, T_STOP=T_STOP, B=B, line_a=SPEC.get("line_a"))))
BAG = stations.BagChange(dict(seed=args.seed, DT=DT, F0=F0, F1=F1, T_STOP=T_STOP))
OPEN = stations.BagOpener(dict(seed=args.seed, DT=DT, F0=F0, F1=F1, T_STOP=T_STOP, B=B, Parcel=Parcel, next_k=_next_k,
                               parcels=parcels))  # C07's full bag is changed in the window
if "opener" in UNSTAFF:  # 021d review: plausibly idle = full bags waiting on the bench, none opened, no heap
    OPEN.workers, OPEN.pile, OPEN.unstaffed = [], [], True
if "dock_D02" in UNSTAFF:  # the boom's extended section (into the lorry) taken out of the merged conveyors mesh
    _cv = sc.objects.get("conveyors")
    if _cv is not None:
        _bm = bmesh.new()
        _bm.from_mesh(_cv.data)
        _mw = _cv.matrix_world
        _dead = [f for f in _bm.faces if (lambda c: -6.0 <= c.x <= 0.58 and 10.4 <= c.y <= 11.6 and 0.3 <= c.z <= 1.3)(
            _mw @ f.calc_center_median())]
        bmesh.ops.delete(_bm, geom=_dead, context="FACES_ONLY")
        bmesh.ops.delete(_bm, geom=[v for v in _bm.verts if not v.link_faces], context="VERTS")
        _bm.to_mesh(_cv.data)
        _bm.free()
        print("UNSTAFF dock_D02: boom extension faces cut", len(_dead), flush=True)
_rnd_A, rnd = rnd, random.Random(args.seed + 4242)  # Parcel() draws from the global rnd: line B gets its own
_k_lb = [7000]  # ...and its own parcel numbers (flow_parcel_7xxx)


def _next_k_lb():
    _k_lb[0] += 1
    return _k_lb[0]


LB = stations.GaylordInductors(dict(seed=args.seed, DT=DT, F0=F0, F1=F1, T_STOP=T_STOP, B=B, Parcel=Parcel, next_k=_next_k_lb,
                                    parcels=parcels, preroll=args.preroll))
if "lineB" in UNSTAFF:  # line B's gaylords wait full; nobody inducts there (no line B traffic)
    LB.workers = []
rnd_B, rnd = rnd, _rnd_A
occ = []  # loop occupancy per frame in the window (B2 pre-review #4 target 30-35 %)
_bag_reset = [False]
S5 = []
if SCEN == "S5":  # look-alike pair: same blue mailer, same size; only the labels differ (tiles 30 -> C12, 31 -> C03)
    for tile, t_in in ((30, -9.0), (31, -7.4)):
        lab = LABELS["labels"][tile]
        p5 = Parcel(_next_k())
        p5.kind, p5.dims, p5.body = "mailer", (0.32, 0.24, 0.04), "mailer_blue"
        p5.dest, p5.read = lab["chute"], True
        p5.target = p5.dest
        p5.forced_tile = tile
        p5.half = max(p5.dims[:2]) / 2
        p5.yaw_off = 0.05 * (1 if tile == 30 else -1)
        p5.meta.update(kind="mailer", dims_m=list(p5.dims), body=p5.body, chute=p5.dest, scenario="S5", story=True)
        p5.t_in = t_in
        p5.state = "pending"
        # scenarios_v2 pass 2: they swap order through line A - the subject (first on the feed) rides on to the last
        # table (I4), its twin is taken at the first (I1) and reaches belt A, the tunnel and the loop ahead of it: an
        # appearance tracker swaps them there, the tunnel read / carrier / divert confirm do not
        if LINE_A_B and tile == 30:  # (its twin takes the first free table: always one upstream of I4)
            p5.only_table = len(LA_MOUTHS) - 1
        S5.append(p5)
S1 = stations.NoReadRework(dict(seed=args.seed, DT=DT, F0=F0, F1=F1)) if SCEN == "S1" else None
S3 = None
if SCEN == "S3":  # phantom containment: the dropped parcel at C04 is scanned into the bag and left beside it
    S3 = stations.PhantomContainment(dict(seed=args.seed, DT=DT, F0=F0, F1=F1, Parcel=Parcel, next_k=_next_k))
    _reg = next((r for r in REG.get("parcels", REG) if r.get("object") == "floor_spill_000"), None)
    if _reg:  # the same registered identity as the static parcel it replaces
        S3.parcel.forced_tile = _reg["tile"]
    S3.history_events(ev, rnd, ride=loop_ride_s)
    S3.scan_event(ev)
S2 = None
LOOK = []  # look-alikes that come down the collector like the S5 pair (agent_showcase_0925 #5)
if SCEN == "S2":  # removal into the blind spot: the story parcel + its earlier shift history
    S2 = stations.BlindRemoval(dict(seed=args.seed, DT=DT, F0=F0, F1=F1, Parcel=Parcel, next_k=_next_k))
    S2.history_events(ev, rnd, ride=loop_ride_s)
    # a look-alike of the story carton (same size, kraft with a white label: another customer's parcel) riding line A,
    # the tunnel and the sorter in the window while the real one is in a person's hands by cage S11: the agent's
    # verifier must reject it (it would have had to cross the hub faster than anything can)
    pl = Parcel(_next_k())
    pl.kind, pl.dims, pl.body = "box", tuple(stations.S2_PARCEL_DIMS), "box"
    pl.read, pl.target = True, pl.dest
    pl.half = max(pl.dims[:2]) / 2
    pl.meta.update(kind="box", dims_m=list(pl.dims), body="box", chute=pl.dest, scenario="S2", lookalike=True)
    pl.t_in, pl.state = args.lookalike_t, "pending"
    LOOK.append(pl)

# ------------------------------------------------------------------------------------------------ simulate
car_s0 = [k * PITCH for k in range(N_CAR)]
car_booked = {}  # carrier -> the merge parcel on its way to it
car_load = [None] * N_CAR
next_spawn = {"boom_D05": -args.preroll, "boom_D02": -args.preroll + 0.6}
bag_fill = {cid: 0 for cid in CHUTES}
landed = {cid: [] for cid in CHUTES}
_dg_static = None


def support_z(box, top=1.6):
    """Highest static surface under a footprint (the bag's built-in contents / sack bottom): a dropped parcel rests ON
    it (it landed inside the static bag contents: collision check)."""
    global _dg_static
    if _dg_static is None:
        _dg_static = bpy.context.evaluated_depsgraph_get()
    zs = []
    for q in box.footprint(-0.01) + [box.pos.xy]:
        z0 = top
        while z0 > 0.0:  # through the chute / bag frame / clips over the bag: down to the contents
            hit, loc, _n, _i, ob, _m = sc.ray_cast(_dg_static, Vector((q.x, q.y, z0)), Vector((0, 0, -1)), distance=z0)
            if not hit:
                break
            if not any(k in ob.name for k in ("chute", "frame", "clip", "light", "loop", "crossover", "sign")):
                zs.append(loc.z)
                break
            z0 = loc.z - 0.002
    return max(zs) if zs else 0.0
sliding = {}  # chute -> (time the parcel on it lands, its lateral offset)  # resting footprints in each bag: a drop lands ON what is there, not inside it
t = -args.preroll
steps = int(round((args.preroll + (F1 - F0) * DT + (args.scan_extend if args.sim_only else 0.0)) / DT))
SIM_TRACE = []


def _pp(q):
    """(x, y, world yaw) of a parcel on a belt (sim-only trace)."""
    pos_, yaw_ = B[q.belt].at(q.s)
    pos_ = pos_ + Vector((-math.sin(yaw_), math.cos(yaw_), 0.0)) * q.lat
    return pos_.x, pos_.y, yaw_ + q.yaw_off
for step in range(steps + 1):
    t = -args.preroll + step * DT
    if S1 is not None and S1.T is not None:
        sp = S1.story
        if sp.state == "bag" and t >= S1.T["lift"]:  # picked out of the bin: in her hands
            sp.state = "held"
        if sp.state == "held" and t >= S1.T["put_feed"] and not getattr(sp, "reinducted", False):
            fd = B["feed"]
            s_ = S1.feed_spot(fd)
            while s_ > 0.5 and not fd.free_at(s_, sp.half):
                s_ -= 0.1
            sp.belt, sp.s, sp.state, sp.read, sp.target = "feed", s_, "belt", True, sp.dest
            sp.lat = -min(0.21, 0.37 - sp.half)
            sp.yaw_off = 0.1
            sp.meta["scanned"] = None  # it goes through the tunnel again
            sp.reinducted = True
            fd.items.append(sp)
            pos_, yaw_ = fd.at(s_)
            S1.feed_pos = pos_ + Vector((-math.sin(yaw_), math.cos(yaw_), 0.0)) * sp.lat
            S1.feed_yaw = yaw_ + sp.yaw_off
            ev(S1.T["encoded"], "manual_encoded", parcel=sp, scan_point="SP-REWORK", device="handheld",
               note="waybill keyed by hand at the exception bench (tunnel no-read)")
    for p5 in S5 + LOOK:  # the look-alike pair comes down the collector from the bag-opening benches
        if p5.state == "pending" and t >= p5.t_in and B["collector"].free_at(B["collector"].length - 3.0, p5.half):
            p5.state, p5.belt, p5.s = "belt", "collector", B["collector"].length - 3.0
            B["collector"].items.append(p5)
            parcels.append(p5)
    # 1. spawn at the boom tips (inside the lorries)
    for bn in ("boom_D05", "boom_D02"):
        if bn in ST.belts and t >= ST.start_t:  # from here on the unloaders put every carton on the boom
            continue
        if bn == "boom_D02" and "dock_D02" in UNSTAFF:  # nothing arrives at an unmanned point
            continue
        rate = ST.preroll_rate(bn) if bn in ST.belts else args.rate
        if t >= next_spawn[bn] and B[bn].free_at(0.15, 0.3):
            p = Parcel(len(parcels))
            p.belt, p.s = bn, 0.15
            B[bn].items.append(p)
            parcels.append(p)
            next_spawn[bn] = t + rnd.expovariate(rate) + 0.25
    if os.environ.get("FLOW_DEBUG_K") and step % 5 == 0:  # trace parcels (debugging only): FLOW_DEBUG_K=12,13
        for q in parcels:
            if q.k in {int(x) for x in os.environ["FLOW_DEBUG_K"].split(",")}:
                print("DBG", q.k, round(t, 1), q.belt, round(getattr(q, "s", -1), 3), q.state, getattr(q, "frozen", None),
                      [round(x.s, 2) for x in B["collector"].items][:4], [round(x.s, 2) for x in B["feed"].items][:6],
                      flush=True)
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
            elif LINE_A_B and bn == "feed":  # zone stop: the head parcel stops centred on the last table's mouth
                want = min(want, LA_MOUTHS[-1] - 5.0)
            elif bn in MERGES and getattr(p, "res_car", None) is None:
                # it waits 0.45 m short of the loop (it waited ON the carriers' track and loaded carriers ran
                # through it) and goes on only with an empty carrier booked that reaches the merge point just as
                # it does
                margin = MERGES[bn][2]
                edge = belt.length - margin
                want = min(want, edge)
                if p.s >= edge - 1e-6:
                    n_ = math.ceil(margin / (belt.speed * DT) - 1e-9)
                    for k in range(N_CAR):
                        s_k = (car_s0[k] + V_LOOP * (t + n_ * DT)) % L_LOOP
                        if (car_load[k] is None and k not in car_booked
                                and 0.0 <= (s_k - MERGES[bn][0]) % L_LOOP < V_LOOP * DT):
                            p.res_car = k
                            car_booked[k] = p
                            want = p.s + belt.speed * DT
                            break
            elif belt.nxt is not None:  # the corner onto the next belt: its first parcel must leave room (the two
                nb = B[belt.nxt]        # belts' queues were spaced separately and met inside each other)
                s_in = nb.entry.get(bn, 0.0)
                backs = [q.s - q.half for q in nb.items if q.s >= s_in and q.s - q.half < s_in + p.half + 0.6]
                # (only parcels at / past the entry: ones still approaching it are handled by the hand-over test)
                if backs:
                    want = min(want, belt.length + (min(backs) - s_in - 0.1) - p.half - abs(p.lat))
                # the last 35 cm + half a parcel is the hand-over zone. A side merge waits OUTSIDE it (on the
                # collector's centre line its parcels ran through the waiting one) until the gap there is long
                # enough to cross in; belts handing over to the same spot take turns (one leader in the zone)
                cross_t = (0.35 + p.half) / max(belt.speed, 0.1)
                crossing = p.s > belt.length - 0.35 - p.half + 0.005  # already in: it finishes
                rivals = [B[o] for o in ORDER if o != bn and B[o].nxt == belt.nxt
                          and abs(nb.entry.get(o, 0.0) - s_in) < 0.6 and B[o].items]
                rival_in = any(max(r.items, key=lambda q: q.s).s > r.length - 0.35
                               - max(r.items, key=lambda q: q.s).half + 0.005 for r in rivals)
                if not crossing and ((s_in > 0.01 and not nb.free_at(s_in, p.half + nb.speed * cross_t))
                                     or rival_in):
                    want = min(want, belt.length - 0.35 - p.half)
            p.s = max(p.s, min(want, belt.length - (p.half + 0.02 if belt.nxt is None and bn not in MERGES else 0.0)))
        done = [p for p in belt.items if p.s >= belt.length - 1e-6]
        for p in done:
            if bn in MERGES:
                p.state = "merge_wait"
                continue
            if belt.nxt is None:
                continue
            nxt = B[belt.nxt]
            s_in = nxt.entry.get(bn, 0.0)
            if nxt.free_at(s_in, p.half):
                belt.items.remove(p)
                pos0, yaw0 = belt.at(p.s)
                pos0 = pos0 + Vector((-math.sin(yaw0), math.cos(yaw0), 0.0)) * p.lat
                p.belt, p.s = belt.nxt, s_in
                pn, yn = nxt.at(s_in)  # keep its place across the belt (no sideways jump at the hand-over) ...
                p.lat = (pos0 - pn).dot(Vector((-math.sin(yn), math.cos(yn), 0.0)))
                if LINE_A_B and bn.startswith("induct_"):  # onto belt A at 45 deg: it keeps its world yaw (no snap)
                    p.yaw_off += yaw0 - yn
                if belt.nxt == "feed":  # ... then the feed's side guide eases it to the operator-side edge
                    p.lat_to = -min(0.21, 0.37 - p.half)
                elif belt.nxt in ("collector", "d02_stub"):  # off a boom: it slides across to the middle
                    p.lat_to = 0.0
                nxt.items.append(p)
                if belt.nxt == "merge":
                    pass
                if bn == "tunnel" or (belt.nxt == "merge"):
                    pass
            # else it waits at the end (belt stalls behind it)
        # DWS read points (line A tunnel exit, line B arch)
        if bn in READS:
            s_read, sp_id = READS[bn]
            rr = rnd if bn == "tunnel" else rnd_B  # line B draws apart: line A's stream (story timings) unchanged
            for p in belt.items:
                if not p.meta.get("scanned") and p.s >= s_read:
                    p.meta["scanned"] = round(t, 2)
                    if bn == "tunnel" and S1 is not None and S1.choose(p, t):  # S1: label crumpled under the tape
                        p.read, p.target = False, "REJECT"
                    w, d, h = p.meta["dims_m"]
                    vol = w * d * h
                    kg = max(0.08, vol * rr.uniform(90, 260)) if p.meta["kind"] == "box" else rr.uniform(0.1, 1.2)
                    p.meta["weight_g"] = int(kg * 1000)
                    if p.read:
                        ev(t, "tunnel_read", parcel=p, scan_point=sp_id,
                           dims_mm=[int(x * 1000 + rr.gauss(0, 4)) for x in (w, d, h)],
                           weight_g=int(kg * 1000 * rr.uniform(0.98, 1.02)), photo=f"tunnel_{p.k:03d}.png")
                    else:
                        ev(t, "tunnel_no_read", scan_point=sp_id,
                           dims_mm=[int(x * 1000 + rr.gauss(0, 4)) for x in (w, d, h)],
                           weight_g=int(kg * 1000 * rr.uniform(0.98, 1.02)), photo=f"tunnel_{p.k:03d}.png")
    for p in B["induction"].items + B["induction_B"].items:  # set down on the near half, centred by the guides
        p.lat *= 0.9
        if LINE_A_B and p in B["induction"].items:  # line A (b): in at 45 deg off an induct belt, squared by the guides
            p.yaw_off += ((p.yaw_off + math.pi / 4) % (math.pi / 2) - math.pi / 4) * -0.15
    for p in B["feed"].items + B["collector"].items + [q for k_ in LA_LINE + (["d02_stub"] if LINE_A_B else [])
                                                         if k_.startswith(("table", "d02")) for q in B[k_].items]:
        if getattr(p, "lat_to", None) is not None and not getattr(p, "frozen", False):
            p.lat += (p.lat_to - p.lat) * 0.25
            if p.belt.startswith("table") or (LINE_A_B and p.belt == "feed"):  # the side guides square it up (the
                # grip wants it square; yawed, it did not fit between the tables' guides: collision check)
                p.yaw_off += (round(p.yaw_off / (math.pi / 2)) * (math.pi / 2) - p.yaw_off) * 0.3
    for p in B["tunnel"].items:
        p.lat = 0.0
    # 2b. unloaders (docks) and inductors (feed queue, stopped parcels only)
    ST.step(t)
    OPEN.step(t)
    LB.step(t)
    if LINE_A_B:
        IND.step(t)
        if args.sim_only and step % 5 == 0:
            SIM_TRACE.append(dict(t=round(t, 1), feed=len(B["feed"].items),
                                  tables=[len(B[f"table_{k}"].items) for k in range(len(LA_MOUTHS))],
                                  induct=[len(B[f"induct_{k}"].items) for k in range(len(LA_MOUTHS))],
                                  collector=len(B["collector"].items), booms=[len(B["boom_D02"].items),
                                                                              len(B["boom_D05"].items)],
                                  pos=[[round(v, 3) for v in (*_pp(q), *q.dims[:2])] + [q.kind[0]]
                                       for bn_ in LA_LINE + ["collector", "d02_stub", "induction"]
                                       for q in B[bn_].items if q.state in ("belt", "merge_wait")
                                       and B[bn_].at(q.s)[0].x < 15.5],
                                  held=[st_["k"] for st_ in IND.st for c_ in st_["active"] if c_["state"] == "held"]))
    else:
        IND.step(t, [p for p in B["feed"].items if abs(p.s - feed_before.get(id(p), -9.0)) < 1e-6])
    # 3. merge onto the first empty carrier passing the merge point (line A, then line B 16.6 m downstream)
    for mb, (s_m, sp_m, _mg) in MERGES.items():
        for p in [q for q in B[mb].items if q.state == "merge_wait"]:
            for k in range(N_CAR):
                s_k = (car_s0[k] + V_LOOP * t) % L_LOOP
                if car_booked.get(k, p) is not p:  # booked by another parcel
                    continue
                if car_load[k] is None and 0.0 <= (s_k - s_m) % L_LOOP < V_LOOP * DT:
                    for kk in [kk for kk, q in car_booked.items() if q is p]:  # (a missed booking never blocks)
                        car_booked.pop(kk)
                    car_load[k] = p
                    p.car, p.state = k, "carrier"
                    B[mb].items.remove(p)
                    ev(t, "induct_to_carrier", parcel=p if p.read else None, scan_point=sp_m, carrier=k + 1)
                    break
    if t >= -1e-6:
        occ.append(sum(c is not None for c in car_load) / N_CAR)
    if not _bag_reset[0] and not BAG.chute_closed(t):  # new empty bag hung: fill starts again from the bottom
        bag_fill[stations.BAG_CHUTE] = 0
        landed[stations.BAG_CHUTE] = []
        _bag_reset[0] = True
    # 4. carriers: divert at the target chute (north straight, moving west)
    for k in range(N_CAR):
        p = car_load[k]
        if p is None:
            continue
        s_prev = (car_s0[k] + V_LOOP * (t - DT)) % L_LOOP
        s_k = (car_s0[k] + V_LOOP * t) % L_LOOP
        cs = CHUTE_S[p.target]
        passing = (s_prev < cs <= s_k) or (s_prev > s_k and (cs > s_prev or cs <= s_k))
        if passing and p.target == stations.BAG_CHUTE and BAG.chute_closed(t):
            # the chute's bag is full (stack light red): the sorter does not divert, the parcel goes round again
            ev(t, "recirculate_chute_full", parcel=p if p.read else None, scan_point=f"SP-DIV-{p.target}",
               carrier=k + 1, chute=p.target)
            continue
        if passing:
            car_load[k] = None
            p.state, p.car = "divert", None
            c = CHUTES[p.target]
            x0, y0, _ = loop_at(cs)
            n = bag_fill[p.target]
            bag_fill[p.target] += 1
            rr = rnd_B if p.k >= 7000 else rnd  # line B parcels: their own stream (line A landings unchanged)
            yaw_l = math.pi + rr.uniform(-0.3, 0.3)  # long side across the bag: it fits between the chute end and
            # the sack's front wall (at +-1 rad the big ones fitted nowhere and rested against the chute)
            if p.target == "REJECT":
                by0, by1 = c["bin"]["y"]  # anywhere in the rework bin (a narrow patch stacked them up to the lip),
                bw_ = c["bin"]["size_m"][0]  # a parcel radius + 2 cm inside its walls (13.9 cm into the wall: collision check)
                rp_ = math.hypot(p.dims[0], p.dims[1]) / 2 + 0.02
                mx_, my_ = max(0.0, bw_ / 2 - rp_), max(0.0, (by1 - by0) / 2 - rp_)
                spot = lambda: (c["x"] + rr.uniform(-mx_, mx_), (by0 + by1) / 2 + rr.uniform(-my_, my_))
                base = 0.42
            else:
                # anywhere over the open bag (frame 1.0 x 0.8 m; a 0.4 x 0.24 m patch stacked them to the lip)
                spot = lambda: (c["x"] + rr.uniform(-0.2, 0.2), c["bag_frame_y"] + 0.525 + rr.uniform(-0.05, 0.05))
                # (the sack's interior, not the whole frame: wider put parcels into the sack walls)
                base = 0.55
            best = None
            for _ in range(16):  # where it comes to rest lowest, on top of the parcels already in (QA parcel_overlap)
                cand = stations.Box(*spot(), base, tuple(p.dims), yaw_l)
                fp_ = cand.footprint()
                under = c.get("end_y") and min(q.y for q in fp_) < c["end_y"] + 0.03
                wall = p.target != "REJECT" and (max(q.y for q in fp_) > c["bag_frame_y"] + 0.72
                                                  or max(abs(q.x - c["x"]) for q in fp_) > 0.42)  # into the
                # sack's front / side wall (1 cm into it: collision check)
                z = max([b_.pos.z + b_.dims[2] for b_ in landed[p.target] if b_.overlaps_xy(cand, 0.0)]
                        + [support_z(cand, 1.4)], default=base)  # from above any heap (it started at the
                # rim, inside heaped static contents: 10 cm deep); chutes / frames over the bag are seen through
                lim_ = c["lip_z"] - (0.02 if p.target == "REJECT" else 0.06)
                if wall or (under and z + p.dims[2] > lim_):  # into the sack wall / against the
                    z += 10.0  # chute's end over the bag (collision check) - only if nothing else is free
                if best is None or z < best[0] - 1e-6:
                    best = (z, cand)
            best[1].pos.z = best[0] if best[0] < 5.0 else best[0] - 10.0
            # a full bag (its heap at the lip): the parcel lands at the lip and settles into the sack (sinks its own
            # height over 0.6 s, then hidden) - only C07 has a bag change, so every other chute's heap grew 2-3.2 m
            # high over the 90 s + preroll (51 parcels in the air over C01 / C12 / ...: motion gate, 31 Oct)
            settle = p.target != "REJECT" and best[1].pos.z + p.dims[2] > c["lip_z"] - 0.02
            if settle:  # onto the opening, gone as it lands (sinking through the heap it crossed the bag's static
                best[1].pos.z = c["lip_z"] + 0.02  # contents and the chute end: +370 collision rows, 31 Oct)
            else:
                landed[p.target].append(best[1])
            land = best[1].pos.copy()
            # two parcels on one chute at once slide down different halves of it (they ran through each other)
            prev = sliding.get(p.target)
            if prev is not None and prev[0] > t:
                side = -math.copysign(1.0, prev[1]) if abs(prev[1]) > 1e-6 else rr.choice((-1.0, 1.0))
                lat_c = side * rr.uniform(0.22, 0.28)
            else:
                lat_c = rr.uniform(-0.15, 0.15)
            lat_c = math.copysign(min(abs(lat_c), 0.45 - p.half), lat_c)  # clear of the chute's side walls
            # 2 cm above the chute surface: the parcel slides flat on a ~22 deg slope, its corners dug 1.2-1.4 cm in
            top = Vector((c["x"] + lat_c * 0.8, c["mouth_y"] + 0.15, DECK - 0.03))
            end = Vector((c["x"] + lat_c, c["end_y"] - 0.05, c["lip_z"] + 0.04))
            # it slides on, pitched with the slope, until its back edge is past the chute's end; only then flat and
            # down into the bag (flattened on the chute it dug its corners into the end lip, 1-2.5 cm; going down
            # diagonally from the end its back edge cut the lip, 8.8 cm: hub run 4)
            sl_ = end - top
            dy_e = p.half * 0.9 + 0.05
            end = end + Vector((sl_.x / sl_.y * dy_e, dy_e, sl_.z / sl_.y * dy_e))
            sliding[p.target] = (t + 0.3 + (end - top).length / 1.4 + 0.35, lat_c)
            p.anim = [(t, Vector((x0, y0, DECK)), math.pi), (t + 0.3, top, math.pi + 0.3),
                      (t + 0.3 + (end - top).length / 1.4, end, math.pi + 0.5),
                      (t + 0.3 + (end - top).length / 1.4 + 0.35, land, yaw_l)]
            # run off the carrier flat at deck height (a cross-belt carrier's belt drives it off sideways), down only
            # once its back edge is past the carrier's (850 mm across: north_y + 0.425); dropping from the start put
            # its bottom 1.7 cm into the carrier edge for a frame (hub run 4: ~25 rows)
            y_off = LOOP["north_y"] + 0.425 + p.half + 0.01
            if y0 < y_off < top.y:
                u_ = (y_off - y0) / (top.y - y0)
                p.anim.insert(1, (t + 0.3 * u_, Vector((x0 + (top.x - x0) * u_, y_off, DECK)), math.pi + 0.3 * u_))
            ev(t, "divert_confirm", parcel=p if p.read else None, scan_point=f"SP-DIV-{p.target}", carrier=k + 1,
               chute=p.target)
            if S1 is not None and p is S1.story and S1.T is None:  # it lands in the rework bin: plan the rework
                S1.landed(p.anim[-1][0], p.anim[-1][1], p.anim[-1][2])
            ev(p.anim[-1][0], "bag_drop" if p.target != "REJECT" else "reject_bin", chute=p.target)  # photo-eye only
            p.t_land = p.anim[-1][0]
            if settle:  # (after the drop events: they are at the landing) gone into the bag's mouth as it leaves the
                # chute's end (hidden only on landing, its last 0.35 s ran level under the chute end: ~177 rows, run 3)
                p.gone_at = F0 + int(round(p.anim[-2][0] / DT)) + 1
    # 5. record positions (frames 1..300 only)
    if -1e-6 <= t <= (F1 - F0) * DT + 1e-6:  # (not past the window: --scan-extend)
        f = F0 + int(round(t / DT))
        for p in parcels:
            if p.state in ("belt", "merge_wait"):
                bel = B[p.belt]
                if LINE_A_B:
                    p.__dict__.setdefault("where", {})[f] = p.belt
                pos, yaw = bel.at(p.s)
                if p.lat:
                    pos = pos + Vector((-math.sin(yaw), math.cos(yaw), 0.0)) * p.lat
                if bel.sloped:
                    hl = (p.dims[0] * abs(math.cos(p.yaw_off)) + p.dims[1] * abs(math.sin(p.yaw_off))) / 2
                    z_, pitch = bel.rest(p.s, hl)
                    pos.z = z_
                    p.track[f] = (pos.copy(), yaw + p.yaw_off, (pitch, yaw))
                else:
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
                    for i_, ((ta, pa, ya), (tb, pb, yb)) in enumerate(zip(kf, kf[1:])):
                        if ta <= t <= tb:
                            u = (t - ta) / max(tb - ta, 1e-6)
                            if i_ == len(kf) - 3:  # sliding down the chute (top -> end): flat on its slope (yaw
                                # only dug its corners in); the segment before it may be the run-off the carrier
                                pitch = math.atan2(pb.z - pa.z, (pb - pa).xy.length)
                                p.track[f] = (pa.lerp(pb, u), ya + (yb - ya) * u,
                                              (pitch, math.atan2(pb.y - pa.y, pb.x - pa.x)))
                            else:
                                p.track[f] = (pa.lerp(pb, u), ya + (yb - ya) * u)
                            break
            elif p.state == "bag":
                p.track[f] = p.rest
    elif any(p.state == "divert" and t >= p.anim[-1][0] for p in parcels):
        for p in parcels:
            if p.state == "divert" and t >= p.anim[-1][0]:
                p.state = "bag"
                p.rest = (p.anim[-1][1].copy(), p.anim[-1][2])

if args.sim_only:  # QA of the simulation alone (line A (b) wiring, M5 step 2): no workers, nothing baked
    T_W = (F1 - F0) * DT
    _w = [x for x in SIM_TRACE if x["t"] >= 0]
    out_ = dict(spec=args.spec or "hub_spec.json", line_a_layout="b" if LINE_A_B else "a", seed=args.seed,
                preroll_s=args.preroll, window_s=T_W,
                tunnel_reads_in_window=sum(1 for e in events if e["event"] in ("tunnel_read", "tunnel_no_read")),
                inducted_to_carriers_in_window=sum(1 for e in events if e["event"] == "induct_to_carrier"),
                feed_queue_max=max((x["feed"] for x in _w), default=0),
                feed_queue_mean=round(sum(x["feed"] for x in _w) / max(len(_w), 1), 2),
                collector_max=max((x["collector"] for x in _w), default=0),
                booms_max=[max((x["booms"][i] for x in _w), default=0) for i in (0, 1)],
                line_a=IND.report(0.0, T_W) if LINE_A_B else None,
                feed_items=[(round(B["feed"].at(q.s)[0].x, 2), round(q.half, 2), q.state, getattr(q, "frozen", None)) for q in B["feed"].items] if LINE_A_B else None,
                feed_len=B["feed"].length,
                story_events=[dict(event=e["event"], t_s=e["t_s"], scan_point=e.get("scan_point"),
                                   tile=getattr(e.get("_p"), "forced_tile", None))
                              for e in events if getattr(e.get("_p"), "meta", {}).get("story")],
                lookalike_events=[dict(event=e["event"], t_s=e["t_s"], scan_point=e.get("scan_point"), chute=e.get("chute"))
                                  for e in events if getattr(e.get("_p"), "meta", {}).get("lookalike")],
                trace=SIM_TRACE[-int(T_W / (5 * DT)) - 1:])
    Path(args.sim_only).write_text(json.dumps(out_, indent=1), encoding="utf-8")
    print("SIM_ONLY written", args.sim_only, flush=True)
    if args.scan_extend:  # every event of the run (window + extension), parcel numbers for the splice
        _RT0 = json.loads((HUB / "render_truth.json").read_text(encoding="utf-8"))
        ext = Path(args.sim_only).with_name(Path(args.sim_only).stem + "_scan_ext.jsonl")
        with open(ext, "w", encoding="utf-8") as fh:
            for e in sorted(events, key=lambda e: e["t_s"]):
                q = e.pop("_p")
                e["parcel_k"] = q.k if q is not None else None
                e["story"] = bool(q is not None and q.meta.get("story"))  # (the splice keeps the full run's story)
                e.pop("device", None)
                fh.write(json.dumps(e, default=str) + "\n")
        print("SCAN_EXT written", ext, len(events), flush=True)
    sys.exit(0)

# bag change at C07 (handheld scans, simulated): bag closed + its ID, bag into a roll cage, new bag opened on the chute
_bt = BAG.T
_bag_full_id = f"BAG-{stations.BAG_CHUTE}-{rnd.randint(1000, 9999)}"
_bag_new_id = f"BAG-{stations.BAG_CHUTE}-{rnd.randint(1000, 9999)}"
_cage_id = f"RC-{rnd.randint(100, 999)}"
ev(_bt["lift"], "bag_close", scan_point=f"SP-BAG-{stations.BAG_CHUTE}", chute=stations.BAG_CHUTE, bag_id=_bag_full_id,
   device="handheld")
ev(_bt["released"], "container_add", scan_point="SP-CAGE-E", container_id=_cage_id, item_id=_bag_full_id,
   item_kind="bag", device="handheld")
ev(_bt["clip_new"], "bag_open", scan_point=f"SP-BAG-{stations.BAG_CHUTE}", chute=stations.BAG_CHUTE,
   bag_id=_bag_new_id, device="handheld")
BAG_TRUTH = dict(chute=stations.BAG_CHUTE, full_bag_id=_bag_full_id, new_bag_id=_bag_new_id, cage_id=_cage_id,
                 cage_bay=stations.BAG_CAGE_BAY, times_s={k: round(v, 2) for k, v in _bt.items()},
                 contents_note="parcels sorted to C07 before t=-40 s (pre-roll, not individually tracked) + the "
                               "static bag contents of the build; no flow parcel entered this bag in the window")
# parcels that landed in the C07 bag before it was lifted out: inside the tied sack from then on (they stood in
# its mesh: collision check)
_f_lift = F0 + math.ceil(BAG.T["lift"] / DT - 1e-9)
for p in parcels:
    if p.target == stations.BAG_CHUTE and p.state == "bag" and p.anim and p.anim[-1][0] < BAG.T["lift"]:
        p.gone_at = min(getattr(p, "gone_at", None) or _f_lift, _f_lift)  # (or earlier: settled into it)
# inductors: parcels in the hands at the end; tracks while held
if not LINE_A_B:
    IND.finish()
ST.finish()
OPEN.finish()
LB.finish()
if S3 is not None:
    for f_ in range(F0, F1 + 1):
        S3.parcel.track[f_] = (S3.box.pos.copy(), S3.box.yaw)
    parcels.append(S3.parcel)
if S2 is not None:  # static on the S11 cage load until the S2 build keys the carry
    for f_ in range(F0, F1 + 1):
        S2.parcel.track[f_] = (S2.box.pos.copy(), S2.box.yaw)
    parcels.append(S2.parcel)
for p, tr in list(OPEN.pile_tracks().items()) + list(LB.pile_tracks().items()):  # bench / gaylord parcels: on
    for f_, pose in tr.items():                                                   # the heap, in the hands, on a belt
        p.track.setdefault(f_, (pose[0].copy(), pose[1]))
    if p not in parcels:
        parcels.append(p)
IND_REP = None
if not LINE_A_B:
    for p, tr in IND.held_tracks().items():
        for f, (pos, yaw) in tr.items():
            p.track[f] = (pos.copy(), yaw)
else:  # M5 step 3: the inductors on mocap; the engine owns each parcel from the grasp to the release
    people_coll = bpy.data.collections.get("People") or bpy.data.collections.new("People")
    if people_coll.name not in sc.collection.children:
        sc.collection.children.link(people_coll)
    _held, IND_REP = IND.build(sc, people_coll, people.RB, FPS)
    if isinstance(ST, stations.MocapDocks):  # the dock unloaders too (the boom takes the engine's release offset)
        _held_d, ST.motion_rows = ST.build_motion(sc, people_coll, people.RB, FPS)
        _held.update(_held_d)
    _off_max = 0.0
    _off_rows = []
    for p, info in _held.items():
        for f, e in info["track"].items():
            p.track[f] = e
        if p not in parcels:
            parcels.append(p)
        # the flow set it down at its belt's place point; the engine's hands put it a few cm off that: the run on
        # the induct belt carries the engine's offset (position + yaw), easing out over 5 frames on belt A
        rf = info["release_frame"]
        if rf not in info["track"] or rf + 1 not in p.track:
            continue
        e_pos, e_yaw = info["track"][rf][0], info["track"][rf][1]
        off, dyaw = e_pos - p.track[rf + 1][0], e_yaw - p.track[rf + 1][1]
        dyaw = (dyaw + math.pi) % (2 * math.pi) - math.pi
        dyaw_k = round(dyaw / (math.pi / 2)) * (math.pi / 2)  # the induct belt's guides square it (to the nearest
        dres = dyaw - dyaw_k  # quarter turn) and centre it once it runs: 6 frames after the belt starts
        if info["belt"].startswith("boom"):  # a boom has no guides: the engine's yaw is kept while on it (eased
            dyaw_k, dres = 0.0, dyaw  # out with the offset after it)
        off.z = 0.0
        _off_max = max(_off_max, off.length)
        _bd = B[info["belt"]].pts[-1] - B[info["belt"]].pts[0]
        _bd = Vector((_bd.x, _bd.y, 0.0)).normalized()
        _rel = e_pos - B[info["belt"]].pts[0]
        _off_rows.append(dict(parcel=p.k, belt=info["belt"], release_frame=rf,
                              engine_along=round(_rel.dot(_bd), 3), engine_lat=round(_rel.cross(_bd).z * -1, 3),
                              off_along=round(off.dot(_bd), 3), off_lat=round(off.cross(_bd).z * -1, 3),
                              dyaw_deg=round(math.degrees(dyaw), 1)))
        n0 = int(math.ceil(IND.CURTAIN_S * FPS))
        if info["belt"].startswith("boom"):  # kept while on the boom, eased out once past its end (x 4.3)
            n0 = next((f_ - rf for f_ in sorted(fr for fr in p.track if fr > rf) if p.track[f_][0].x > 4.3), 10 ** 6)
        for f in sorted(fr for fr in p.track if fr > rf):
            w_ = 1.0 if f - rf <= n0 else max(0.0, 1.0 - (f - rf - n0) / 6)
            p.track[f] = (p.track[f][0] + off * w_, p.track[f][1] + dyaw_k + dres * w_) + tuple(p.track[f][2:])
    IND_REP["release_offset_max_m"] = round(_off_max, 3)
    IND_REP["release_offsets"] = _off_rows
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
LATE = []  # parcels whose track starts after frame 1 (reported: each should have a reason to appear)
for p in sorted(parcels, key=lambda q: q.k >= 7000):  # line B last: line A keeps its labels (tiles)
    if not p.track:
        continue
    frames_ = sorted(p.track)
    if p.state == "bag" and all((p.track[f][0] - p.track[frames_[0]][0]).length < 1e-4 for f in frames_):
        continue  # bagged before frame 1: part of the bag's static contents
    rnd = rnd_B if p.k >= 7000 else _rnd_A  # make_parcel draws label placement: line B from its own stream
    ok = p.materialise()
    rnd = _rnd_A
    if not ok:
        continue
    kept += 1
    frames = sorted(p.track)
    static = all((p.track[f][0] - p.track[frames[0]][0]).length < 1e-4 for f in frames)
    eul = None
    for f in (frames[:1] if static else frames):
        pos, yaw, *tilt = p.track[f]
        p.ob.location = pos
        if tilt and tilt[0][0] == "R":  # a full rotation (mocap engine: in the hands)
            eul = tilt[0][1].to_euler("XYZ", eul) if eul is not None else tilt[0][1].to_euler("XYZ")
            p.ob.rotation_euler = eul
        elif tilt:  # on a ramp: pitched about the belt's lateral axis (uphill = nose up)
            pitch, byaw = tilt[0]
            M = Matrix.Rotation(-pitch, 3, Vector((-math.sin(byaw), math.cos(byaw), 0.0))) @ Matrix.Rotation(yaw, 3, "Z")
            eul = M.to_euler("XYZ", eul) if eul is not None else M.to_euler("XYZ")
            p.ob.rotation_euler = eul
        else:
            eul = Euler((0, 0, yaw)) if eul is None else Matrix.Rotation(yaw, 3, "Z").to_euler("XYZ", eul)
            p.ob.rotation_euler = eul
        if not static:
            p.ob.keyframe_insert("location", frame=f)
            p.ob.keyframe_insert("rotation_euler", frame=f)
    linear(p.ob)
    if getattr(p, "gone_at", None) and p.gone_at <= F0:  # into a full bag before the window: not seen at all
        p.ob.hide_render = p.ob.hide_viewport = True
    elif getattr(p, "gone_at", None) and F0 < p.gone_at <= frames[-1]:  # leaves with the tied sack / into the bag
        for f, hid in ((F0, False), (p.gone_at, True)):
            p.ob.hide_render = p.ob.hide_viewport = hid
            p.ob.keyframe_insert("hide_render", frame=f)
            p.ob.keyframe_insert("hide_viewport", frame=f)
        for fc in [fc for b_, fcs in people._channelbag_fcurves(p.ob.animation_data.action) for fc in fcs
                   if fc.data_path.startswith("hide")]:
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"
    if frames[0] > F0:  # it enters mid-window: not there before (it stood as a ghost at its first pose from frame 1,
        # with belt parcels running through it: QA parcel_overlap S5)
        for f, hid in ((F0, True), (frames[0], False)):
            p.ob.hide_render = p.ob.hide_viewport = hid
            p.ob.keyframe_insert("hide_render", frame=f)
            p.ob.keyframe_insert("hide_viewport", frame=f)
        for fc in [fc for b_, fcs in people._channelbag_fcurves(p.ob.animation_data.action) for fc in fcs
                   if fc.data_path.startswith("hide")]:
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"
        LATE.append((p.ob.name, frames[0], [round(c, 2) for c in p.track[frames[0]][0]]))
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
station_report["induction"] = IND.build(sc, people_coll, range(F0, F1 + 1)) if not LINE_A_B else IND_REP
station_report["cages"] = stations.CagePushers(dict(seed=args.seed, DT=DT, F0=F0, F1=F1)).build(
    sc, people_coll, range(F0, F1 + 1), SPEC)
for push in station_report["cages"].get("pushes", []):  # RFID portals at the doors (the cage tag is read)
    if push["door"] is None:
        continue
    cid = f"RC-{rnd.randint(100, 999)}"
    push["cage_id"] = cid
    portal = f"SP-RFID-{push['door']}"
    ev(push["t_end_s"] - 0.6, "rfid_read", scan_point=portal, container_id=cid, rssi_dbm=round(rnd.uniform(-58, -51), 1))
    nb = {"D08": "D09", "D09": "D08", "D11": "D10", "D10": "D11"}.get(push["door"])
    if nb and (SCEN == "S4" or rnd.random() < 0.25):  # neighbouring portal cross-reads the tag (weaker)
        ev(push["t_end_s"] - 0.3, "rfid_read", scan_point=f"SP-RFID-{nb}", container_id=cid,
           rssi_dbm=round(rnd.uniform(-74, -67), 1))
station_report["walkers"] = stations.Walkers(dict(DT=DT, F0=F0, F1=F1)).build(sc, people_coll, range(F0, F1 + 1))
station_report["bagging"] = BAG.build(sc, people_coll, range(F0, F1 + 1), SPEC)
station_report["bag_opening_cut"] = stations._cut_region(sc, ["parcels_static_merged"], 6.2, 8.0, 19.0, 22.0, 0.85, 1.6)
station_report["bag_opening"] = OPEN.build(sc, people_coll, range(F0, F1 + 1))
station_report["induction_B"] = LB.build(sc, people_coll, range(F0, F1 + 1))
station_report["loop_occupancy"] = dict(mean=round(sum(occ) / max(len(occ), 1), 3), min=round(min(occ, default=0), 3),
                                       max=round(max(occ, default=0), 3), target="0.30-0.35 (B2 pre-review #4)")
print("FLOW loop occupancy", station_report["loop_occupancy"], flush=True)
station_report["ambient"] = stations.Ambient(dict(seed=args.seed, DT=DT, F0=F0, F1=F1)).build(sc, people_coll,
                                                                                             range(F0, F1 + 1))
SCEN_TRUTH = {"scenario": SCEN, "seconds": (F1 - F0 + 1) / FPS, "t0": T_START.isoformat()}
if S2 is not None:
    station_report["S2"] = S2.build(sc, people_coll, range(F0, F1 + 1), SPEC)
    for e_ in truth:
        if e_["object"] == S2.parcel.ob.name:
            e_["track"] = S2.track_out
            e_["scenario_note"] = ("carried from the S11 cage into the exception store (BLIND_NW) by worker_s2_1 and "
                                   "set down on its shelving; he came back out without it")
    T2 = S2.T
    _hm = lambda t_: (T_START + timedelta(seconds=t_)).strftime("%H:%M:%S")  # noqa: E731
    _cp = getattr(S2, "cage_push", None)
    if _cp and _cp.get("at_door_t") is not None:  # the cage's tag read at D07's portal as it gets there
        ev(_cp["at_door_t"] - 0.4, "rfid_read", scan_point="SP-RFID-D07", container_id=S2.cage_id,
           rssi_dbm=round(rnd.uniform(-58, -51), 1))
    SCEN_TRUTH.update(story_parcel=S2.parcel.meta.get("parcel_id"), story_object=S2.parcel.ob.name,
                      what="taken off cage S11's shelf by a person, carried into the exception store (BLIND_NW) and "
                           "left there: he came back out empty-handed",
                      picked_t_s=round(T2["grip"], 2), enters_blind_t_s=round(T2["gap"], 2),
                      placed_t_s=(round(T2["placed"], 2) if T2.get("placed") is not None else None),
                      exits_empty_t_s=(round(T2["out_empty"], 2) if T2.get("out_empty") is not None else None),
                      final_location=dict(zone="Z11", where="exception store shelving (unseen by every camera)",
                                          xyz=S2.rest_xyz),
                      cage_id=getattr(S2, "cage_id", None), person="worker_s2_1", cage_push=_cp,
                      expected_answer=("went into Z11 carrying it at ~%s (t=%.0f s) through its only entrance; came "
                                       "out empty-handed at ~%s (t=%.0f s); no camera sees inside Z11 but every way out "
                                       "is watched (CAM_19) and nothing came out with it before the window ended -> "
                                       "the parcel is in Z11. Neutral: moved by a person into the exception store; "
                                       "the cage scan (container_add) is out of date after t=%.1f s, so the cage's RFID "
                                       "read at D07 (t=%.0f s) does not mean the parcel left on that truck")
                      % (_hm(T2["gap"]), T2["gap"], _hm(T2["out_empty"] or 0), T2["out_empty"] or 0, T2["grip"],
                         (_cp or {}).get("at_door_t") or 0),
                      expected_one_liner="Went in carrying it, came out empty-handed: it is in the exception store (Z11).",
                      must_not=["say 'left the hub'", "say 'left on the D07 truck' (the cage's RFID read)",
                                "say 'stolen' or name / describe a person beyond a token",
                                "trust the cage scan after t=%.1f s" % T2["grip"]],
                      cameras=["CAM_13", "CAM_19", "CAM_01", "CAM_06"],
                      lookalike=([dict(parcel_id=q.meta.get("parcel_id"), object=(q.ob.name if q.ob else None),
                                       what="same size kraft carton with a white label, another customer's parcel",
                                       scans=[dict(event=e_["event"], t_s=e_["t_s"], scan_point=e_.get("scan_point"))
                                              for e_ in events if e_.get("_p") is q],
                                       why_not_the_subject=("while it rides line A / the tunnel / the sorter the story "
                                                            "carton is in a person's hands by cage S11 or in Z11: it "
                                                            "would have had to cross the hub in seconds; and its label "
                                                            "reads another waybill at the tunnel"))
                                  for q in LOOK]),
                      exits_covered=True, exits=stations.S2_EXITS,
                      limitations=["unseen: a 0.25 m strip behind the south rack's end upright (x 13.45-13.55, z >= "
                                   "0.7 m), reachable only through the gap's fully seen south face (review 019 #3)",
                                   "a throw over the 3 m racks: 49 % of the air over them and 83 % of the floor band where "
                                   "it would land are seen (review 019 #4); not a way out for a person"]
                      + [{"opener": "rendered with the bag-opening bench unstaffed (two full bags waiting on it): its "
                                    "old motion is not convincing yet; fixed before any scenario that films it (021d review)",
                          "dock_D02": "rendered with dock D02 idle (its lorry unloaded, the boom pulled back to the door, "
                                      "nobody unloading): its old motion is not convincing yet; fixed before any scenario "
                                      "that films it (021d review)",
                          "lineB": "rendered with line B unstaffed (gaylords waiting, no line B inductions)"}[u_]
                         for u_ in sorted(UNSTAFF)],
                      unstaffed_for_render=sorted(UNSTAFF))
elif SCEN == "S1" and S1 is not None and S1.T is not None:
    station_report["S1"] = S1.build(sc, people_coll, range(F0, F1 + 1))
    sp = S1.story
    if sp.ob is not None:  # re-key: in the bin until picked, her carry, then the flow again from the feed
        full = dict(sp.track)
        for f_, pose in S1.track_world.items():
            full[f_] = (pose[0], pose[1])
        if sp.ob.animation_data:
            sp.ob.animation_data_clear()
        for f_ in sorted(full):
            pos, yaw = full[f_]
            sp.ob.location, sp.ob.rotation_euler = pos, (0, 0, yaw)
            sp.ob.keyframe_insert("location", frame=f_)
            sp.ob.keyframe_insert("rotation_euler", frame=f_)
        linear(sp.ob)
        for e_ in truth:
            if e_["object"] == sp.ob.name:
                e_["track"] = {f_: [round(c, 3) for c in full[f_][0]] for f_ in sorted(full)}
    T1 = S1.T
    SCEN_TRUTH.update(story_parcel=sp.meta.get("parcel_id"), story_object=sp.ob.name if sp.ob else None,
                      times_s={k: round(v, 2) for k, v in T1.items()},
                      what="tunnel no-read -> REJECT chute -> rework bin -> exception bench (manual encode) -> "
                           "carried back to the induction feed -> inducted again, read, sorted",
                      expected_answer=("first pass: no read at the tunnel, reject bin at t~%.0f s; reworked at the "
                                       "bench (manual_encoded at t~%.0f s); re-inducted from the feed at t~%.0f s")
                                      % (T1["land"], T1["encoded"], T1["put_feed"]),
                      cameras=["CAM_04", "CAM_05", "CAM_06", "CAM_07", "CAM_08", "CAM_09", "CAM_12", "CAM_10", "CAM_11"])
elif SCEN == "S3" and S3 is not None:
    station_report["S3_cut"] = stations._cut_region(sc, ["parcels_static_merged"], 44.55, 45.1, 21.35, 21.9, -0.1, 0.4)
    station_report["S3"] = S3.build(sc, people_coll, range(F0, F1 + 1))
    for e_ in truth:
        if e_["object"] == S3.parcel.ob.name:
            e_["track"] = S3.track_out
    SCEN_TRUTH.update(story_parcel=S3.parcel.meta.get("parcel_id"), story_object=S3.parcel.ob.name,
                      bag_id=S3.bag_id, scanned_t_s=round(S3.T["scan"] + 0.3, 2),
                      set_down_t_s=round(S3.T["release"], 2), set_down_at=[round(c, 2) for c in stations.S3_DROP],
                      what="scanned INTO the C04 bag (handheld container_add), then set down on the floor against "
                           "the front of the C04 frame and left there",
                      expected_answer="the scan says it is in " + S3.bag_id + ", but the video shows it set down "
                                      "beside the C04 bag frame at t~%.0f s and still there at the end: physical "
                                      "location = floor beside chute C04, not in the bag" % S3.T["release"],
                      cameras=["CAM_10", "CAM_11", "CAM_13", "CAM_14"])
elif SCEN == "S4":
    mis = next((q for q in station_report["cages"]["pushes"] if q["intended"] == "D08"), None)
    SCEN_TRUTH.update(story_container=mis and mis.get("cage_id"), story_object=mis and mis["cage"],
                      intended_door="D08", actual_door=mis and mis["door"], loaded_t_s=mis and mis["t_end_s"],
                      what="roll cage meant for D08 pushed onto the D09 lorry; the D08 portal cross-reads its tag",
                      expected_answer="the cage went into the D09 lorry (video), despite the RFID read at D08's "
                                      "portal: a cross-read (weaker RSSI, 0.3 s after the D09 read)",
                      cameras=["CAM_13", "CAM_14", "CAM_15", "CAM_16", "CAM_17"])
elif SCEN == "S5":
    rd = {e["_p"]: e["t_s"] for e in events if e["event"] == "tunnel_read" and e.get("_p") in S5}
    dv = {e["_p"]: e["t_s"] for e in events if e["event"] == "divert_confirm" and e.get("_p") in S5}
    pair = []
    for p5 in S5:
        pair.append(dict(parcel_id=p5.meta.get("parcel_id"), object=p5.ob.name if p5.ob else None, chute=p5.target,
                         tunnel_read_t_s=round(rd[p5], 2) if p5 in rd else None,
                         divert_t_s=round(dv[p5], 2) if p5 in dv else None,
                         in_bag_t_s=round(getattr(p5, "t_land", p5.anim[-1][0]), 2) if p5.anim else None))
    SCEN_TRUTH.update(pair=pair, story_parcel=pair[0]["parcel_id"],
                      what="two look-alike blue mailers (same size, colour); only the labels differ",
                      expected_answer=f"{pair[0]['parcel_id']} -> chute {pair[0]['chute']} (not {pair[1]['chute']}): "
                                      "follow the tunnel read and the carrier, not the appearance",
                      swapped=(pair[0]["tunnel_read_t_s"] is not None and pair[1]["tunnel_read_t_s"] is not None
                               and pair[1]["tunnel_read_t_s"] < pair[0]["tunnel_read_t_s"]),
                      expected_one_liner=(f"They swapped places through line A: appearance would send you to chute "
                                          f"{pair[1]['chute']}; the tunnel read, carrier and divert confirm say "
                                          f"{pair[0]['chute']}."),
                      must_not=["identify the parcel by its appearance (same size, same colour)",
                                f"pick chute {pair[1]['chute']}"],
                      cameras=["CAM_04", "CAM_05", "CAM_06", "CAM_07", "CAM_09", "CAM_11"])
elif SCEN == "S0":  # control: a parcel read at the tunnel early in the window and bagged before its end
    reads = {e["_p"]: e["t_s"] for e in events if e["event"] == "tunnel_read" and e.get("_p") is not None}
    drops = {}
    for p in parcels:
        if p.ob is not None and p.read and p.target != "REJECT" and p.anim and p in reads:
            drops[p] = getattr(p, "t_land", p.anim[-1][0])
    T_END = (F1 - F0) * DT
    cands = [(p, reads[p], drops[p]) for p in drops if 0.5 < reads[p] < 18.0 and drops[p] < T_END - 0.5]
    late = [(p, t_) for p, t_ in reads.items() if 0.5 < t_ < T_END - 4.0 and p.ob is not None and p.read]
    if not cands and late:  # nothing both read and bagged inside the window: one read early, still on the loop
        p, tr_ = min(late, key=lambda c: c[1])
        SCEN_TRUTH.update(story_parcel=p.meta.get("parcel_id"), story_object=p.ob.name, chute=p.target,
                          tunnel_read_t_s=round(tr_, 2), in_bag_t_s=None,
                          what="normal path: tunnel -> merge -> loop (still riding the loop at the window's end)",
                          expected_answer=f"read at the tunnel (t~{tr_:.0f} s), last seen on the sorter loop heading "
                                          f"for chute {p.target}")
    if cands:
        p, tr_, td = min(cands, key=lambda c: c[1])
        SCEN_TRUTH.update(story_parcel=p.meta.get("parcel_id"), story_object=p.ob.name, chute=p.target,
                          tunnel_read_t_s=round(tr_, 2), in_bag_t_s=round(td, 2),
                          what="normal path: tunnel -> merge -> loop -> divert -> chute -> bag",
                          expected_answer=f"last seen dropping into the bag at chute {p.target} (t~{td:.0f} s)")
sc.frame_set(F0)
print("STATIONS " + json.dumps(station_report), flush=True)

(BUILD / "truth").mkdir(exist_ok=True)
# scenarios_v2 pass 2: every card gets its sharp line and what the answer must not say (scored by the evaluator)
SHARP = {
    "S0": ("Normal path: read, sorted, bagged - no incident.",
           ["raise an incident", "bridge a gap in the video without evidence"]),
    "S1": ("A no-read is not a loss: it went round to the reject chute, was keyed by hand and re-inducted.",
           ["call the no-read a loss", "order events before aligning the handheld clock"]),
    "S3": ("The scan says it is in the bag; the video says it is on the floor beside chute C04 - the bag left "
           "without it.", ["trust the bag scan", "say 'dispatched'"]),
    "S4": ("The cage went onto the D09 lorry; the D08 read is a cross-read (weaker RSSI, 0.3 s later).",
           ["trust the D08 read"]),
}
if SCEN in SHARP:
    SCEN_TRUTH.setdefault("expected_one_liner", SHARP[SCEN][0])
    SCEN_TRUTH.setdefault("must_not", SHARP[SCEN][1])
(BUILD / "truth" / f"scenario{SUFFIX or '_S0'}.json").write_text(json.dumps(SCEN_TRUTH, indent=1), encoding="utf-8")
(BUILD / "truth" / f"flow_truth{SUFFIX}.json").write_text(json.dumps(
    {"note": "render-side truth; Spoor never reads this", "fps": FPS, "frames": [F0, F1], "t0": T_START.isoformat(),
     "loop_speed_mps": V_LOOP, "parcels": truth, "truck_walls": WALL_TRUTH,
     "station_workers": station_report, "bag_change": BAG_TRUTH}), encoding="utf-8")
(BUILD / "sim").mkdir(exist_ok=True)
# device clocks (render side: render_truth.json, evaluator-only): every record carries the time ITS device wrote
# (sorter / tunnel PLC = the WCS reference clock; handhelds = the fleet clock, uploaded in batches). The true time
# goes to build/truth/events_truth.jsonl only - the log Spoor imports has no true time in it.
_RT = json.loads((HUB / "render_truth.json").read_text(encoding="utf-8"))
_HH, _WCS = _RT["handheld_fleet"], _RT["wcs"]


def _domain(e):
    sp = e.get("scan_point") or ""
    return "clkd_handheld" if sp.startswith(("SP-BAG", "SP-CAGE", "SP-IN-", "SP-REWORK", "SP-OVERSIZE", "SP-LOAD")) \
        else "clkd_wcs"


with open(BUILD / "sim" / f"events_scan_simulated{SUFFIX}.jsonl", "w", encoding="utf-8") as fh, \
        open(BUILD / "truth" / f"events_truth{SUFFIX}.jsonl", "w", encoding="utf-8") as ft:
    for e in sorted(events, key=lambda e: e["t_s"]):
        q = e.pop("_p")
        if q is not None and q.ob is None:
            continue  # its parcel was never materialised (pre-roll only)
        e["parcel_id"] = q.meta.get("parcel_id") if q is not None else None
        e.pop("device", None)
        t_true = e.pop("t_s")
        dom = _domain(e)
        off = (_HH if dom == "clkd_handheld" else _WCS).get("clock_offset_s", 0.0)
        e["time"] = (T_START + timedelta(seconds=t_true + off)).isoformat(timespec="milliseconds")
        e["clock_domain"] = dom
        if dom == "clkd_handheld":  # handhelds upload in batches: the hub system receives the record later
            e["received_time"] = (T_START + timedelta(seconds=t_true + off + 60 * _HH.get("batch_upload_delay_min", 0)
                                                      + rnd.uniform(5, 90))).isoformat(timespec="seconds")
        fh.write(json.dumps(e) + "\n")
        ft.write(json.dumps({"event": e["event"], "parcel_id": e["parcel_id"], "true_t_s": t_true,
                             "true_time": (T_START + timedelta(seconds=t_true)).isoformat(timespec="milliseconds"),
                             "logged_time": e["time"], "clock_domain": dom}) + "\n")
moving = sum(1 for p in parcels if p.ob is not None and any((p.track[f][0] - p.track[min(p.track)][0]).length > 0.01
                                                             for f in p.track))
on_loop_f1 = sum(1 for p in parcels if p.ob is not None and 1 in p.track and abs(p.track[1][0].z - DECK) < 0.05)
print("FLOW " + json.dumps({"late_parcels": LATE[:20], "n_late": len(LATE), "belt_points_without_surface": GAPS, "parcels": kept, "moving_in_window": moving, "on_loop_at_frame1": on_loop_f1,
                            "carriers": N_CAR, "events": len(events),
                            "events_by_kind": {k: sum(1 for e in events if e['event'] == k) for k in
                                               sorted({e['event'] for e in events})},
                            "bag_fill": {k: v for k, v in bag_fill.items() if v}}), flush=True)
sc.render.fps = FPS  # the station workers' FBX template imports reset it to 30
sc.frame_start, sc.frame_end = F0, F1
if args.save:
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(args.save).resolve()), compress=True)
