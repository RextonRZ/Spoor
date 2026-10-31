"""M3 (014_GO): the line-A inductor on real mocap (AndyData, CC BY 4.0), steps 7-9 of the build plan.

Per parcel: a PICK clip (end of the reach, the two-hand pick and the turn that follows it in the source) then a PLACE
clip (the set-down and the start of the release), cut on the AndyData labels (clips.py). Each clip is
  * retimed at a constant ratio 0.85-1.15 (no slow motion; waits are holds of the last pose),
  * anchored at its event: the pick so the palms meet the parcel on the roller table at the grasp, the place so the
    worker faces belt A at the release with the body clear of the belt frame; the pick's END heading is chained to
    the place's START heading, so no join ever spins the worker,
  * joined to the next clip by inertialization (the pose / root offset at the cut decays over ~0.3 s, no crossfade),
then the whole timeline is solved on the avatar (retarget.solve), feet are locked during stance, the hands are pulled
onto the parcel's side faces by a ramped two-bone IK (pole = the mocap elbow), and the parcel's world matrix is baked
from the palms (table -> hands -> belt). Left-turning source takes are mirrored so every inductor turns right
(buffer table on the left, belt in front).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import retarget as R  # noqa: E402

RAW = HERE.parents[1] / "mocap" / "raw" / "andydata"
RAW100 = HERE.parents[1] / "mocap" / "raw" / "100style"
# review 017 #1: a wait for a parcel of >= IDLE_MIN_S is stood out in a real idle (100STYLE Neutral_ID, CC BY 4.0:
# weight shifts, arms down, small looks), not the last pose of the place clip held with empty hands
IDLE_TAKE, IDLE_RANGE, IDLE_MIN_S = "100STYLE/Neutral/Neutral_ID", (655 / 60.0, 1555 / 60.0), 0.6
IDLE_CHUNK_S = 6.0  # longer waits: chained cuts (alternately mirrored), never past the take's clean range


def _idle_segs(t, wait, k, x):
    """Idle segments filling [t, t + wait): deterministic cuts of the idle take (no draw from the planner's rnd)."""
    out, j = [], 0
    n = max(1, int(math.ceil(wait / IDLE_CHUNK_S - 1e-9)))
    for j in range(n):
        d = wait / n
        span = IDLE_RANGE[1] - IDLE_RANGE[0] - d - 0.2
        t0 = IDLE_RANGE[0] + ((k * 7.31 + x * 3.7 + j * 4.13) % max(span, 0.1))
        out.append(dict(kind="idle", clip=dict(take=IDLE_TAKE, t0=t0, t1=t0 + d, anchor=t0, mirror=bool((k + j) % 2)),
                        ratio=1.0, out0=t + j * d, out1=t + (j + 1) * d))
    return out
CLIPS = HERE.parents[1] / "mocap" / "clips.json"
_takes = {}


def take(name):
    """BVH of an AndyData take (cached) with the participant's measured leg length."""
    if name not in _takes and name.startswith("100STYLE/"):  # 100STYLE: same Xsens skeleton, rest = T-pose
        b = R.read_bvh(RAW100 / f"{name}.bvh")
        b["J"] = {n: i for i, n in enumerate(b["names"])}
        _takes[name] = b
    if name not in _takes:
        pid = name.split("_")[1]
        b = R.read_bvh(RAW / "xsens_bvh" / f"Participant_{pid}" / f"{name}.xsens.bvh")
        import csv
        for row in csv.DictReader(open(RAW / "participant_specifications.csv", encoding="utf-8")):
            if row["ID"] == pid:
                b["spec_leg_m"] = (float(row["hip_height"]) - float(row["ankle_height"])) / 100.0
        b["J"] = {n: i for i, n in enumerate(b["names"])}
        _takes[name] = b
    return _takes[name]


def palms(b, Dw, Pw):
    """Source palm centres (F,2,3): wrist + 40 % of the wrist->fingertip segment (Blender axes, metres)."""
    J = b["J"]
    out = []
    for s in ("Left", "Right"):
        e = R.C @ (0.4 * np.array(b["ends"][J[f"{s}Wrist"]]) * 0.01)
        out.append(Pw[:, J[f"{s}Wrist"]] + np.einsum("fij,j->fi", Dw[:, J[f"{s}Wrist"]], e))
    return np.stack(out, 1)


def candidates(min_pick_h=0.9, max_pick_dur=2.0, turn_sign=-1):
    """Pick / place clips usable for a planted right-turning inductor (turn_sign -1; +1: left-turning, the belt on
    his left: the dock unloader north of the boom), scored from the data."""
    picks, places = [], []
    for c in json.loads(CLIPS.read_text(encoding="utf-8")):
        if not c["two_hand"] or not (min_pick_h if c["kind"] == "pick" else 0.7) <= c["hand_height_m"] <=                 (1.25 if c["kind"] == "pick" else 1.15):  # places: release at belt height, not a high shelf
            continue
        b = take(c["take"])
        J = b["J"]
        for mirror in (False, True):
            if c["kind"] == "pick":
                g, lift = c["events"]["grasp"], c["events"]["lift"]
                t0, t1 = g - 0.6, lift + 0.45
                Dw, Pw = R.clip_world(b, [t0, g, t1], 30, mirror=mirror)
                yw = np.unwrap(R.yaw_of(Dw[:, J["Hips"]]))
                turn = math.degrees(yw[2] - yw[1])
                hips = (Pw[:, J["LeftHip"]] + Pw[:, J["RightHip"]]) / 2
                trav = float(np.linalg.norm(hips[2, :2] - hips[0, :2]))
                if -95 <= turn * -turn_sign <= -30 and trav < 0.45 and t1 - t0 <= max_pick_dur:
                    picks.append(dict(c, mirror=mirror, t0=t0, t1=t1, anchor=g, turn=turn, travel=trav))
            else:
                rel = c["events"]["release"]
                t0, t1 = max(c["events"]["place_start"] - 0.25, rel - 0.9), rel + 0.45
                Dw, Pw = R.clip_world(b, np.linspace(t0, t1, 12), 30, mirror=mirror)
                yw = np.unwrap(R.yaw_of(Dw[:, J["Hips"]]))
                hips = (Pw[:, J["LeftHip"]] + Pw[:, J["RightHip"]]) / 2
                trav = float(np.max(np.linalg.norm(hips[:, :2] - hips[0, :2], axis=1)))
                turn = math.degrees(yw[-1] - yw[0])
                if abs(turn) < 35 and trav < 0.35:
                    places.append(dict(c, mirror=mirror, t0=t0, t1=t1, anchor=rel, turn=turn, travel=trav))
    return picks, places


def _rotlog(R_):
    """(N,3,3) -> (N,3) axis*angle, via quaternions (stable near 180 deg, where the trace formula loses the axis)."""
    q = R.quat(np.asarray(R_).reshape(-1, 3, 3))
    q = q * np.where(q[:, :1] < 0, -1.0, 1.0)  # shortest rotation per element
    vn = np.linalg.norm(q[:, 1:], axis=1)
    ang = 2 * np.arctan2(vn, q[:, 0])
    return np.where(vn[:, None] > 1e-9, q[:, 1:] / (vn[:, None] + 1e-12), 0.0) * ang[:, None]


def _rotexp(w):
    a = np.linalg.norm(w, axis=-1, keepdims=True)
    k = np.where(a > 1e-9, w / (a + 1e-12), 0.0)
    K = np.zeros(w.shape[:-1] + (3, 3))
    K[..., 0, 1], K[..., 0, 2], K[..., 1, 0] = -k[..., 2], k[..., 1], k[..., 2]
    K[..., 1, 2], K[..., 2, 0], K[..., 2, 1] = -k[..., 0], -k[..., 1], k[..., 0]
    a = a[..., None]
    return np.eye(3) + np.sin(a) * K + (1 - np.cos(a)) * (K @ K)


class Planner:
    """Lays pick/place clips back to back, one carton per cycle() call, so a simulation (flow.py) can drive it as
    parcels arrive. station: dict(belt_yaw rad (facing the belt), table_pt xyz of the waiting parcel's centre,
    place_y (the belt's near-half centre line), clear_y (min root y: body off the belt frame), sign (+1: belt at -Y of
    the worker)). segs (the timeline for assemble / build) grows with every cycle."""

    def __init__(self, station, rnd, picks, places, busy=(), pick_pool=None):
        self.station, self.rnd, self.picks, self.places = station, rnd, picks, places
        self.busy, self.pick_pool = busy, pick_pool
        self.segs = []
        self.t = 0.0  # end of the planned timeline (s)
        self.k = 0
        self.last_pick = self.last_place = self.last_lift = None
        self.recent = []  # (pick, place) pairs of the last 3 cartons: never repeated (review 015 #1)

    def cycle(self, ready=None, busy=None):
        """Plan carton k. ready: time (s) the parcel sits at the stop (None: no wait). busy: (t0, t1) windows when the
        place spot is taken (default: the planner's own). Returns dict(n, pick0, grasp, lift, release, end) in s."""
        rnd, station, picks, places, segs = self.rnd, self.station, self.picks, self.places, self.segs
        busy = self.busy if busy is None else busy
        t, k = self.t, self.k
        for _ in range(40):
            pool = self.pick_pool(k) if self.pick_pool else picks  # per carton (e.g. by wall tier height)
            pk = pool[rnd.randrange(len(pool))]
            pl = places[rnd.randrange(len(places))]
            if (len(picks) == 1 or pk is not self.last_pick) and (len(places) == 1 or pl is not self.last_place) \
                    and (id(pk), id(pl)) not in self.recent:
                break
        self.last_pick, self.last_place = pk, pl
        self.recent = (self.recent + [(id(pk), id(pl))])[-3:]
        rlo, rhi = station.get("ratio", (0.92, 1.12))  # review 015 #1 (a dock unloader runs slower: 014_GO)
        r1 = rnd.uniform(rlo, rhi)
        r2 = rnd.uniform(rlo, rhi)
        if segs and rnd.random() < 1 / 6:  # an extra beat: a pause with a glance up the line before the next pick
            beat = rnd.uniform(0.6, 1.1)
            if station.get("idle", True):  # stood out relaxed (017 #1), not the place clip's end pose held
                segs.extend(_idle_segs(t, beat, k, station.get("x", 0.0)))
            else:
                segs.append(dict(kind="hold", out0=t, out1=t + beat, beat=True))
            t += beat
        d1 = (pk["t1"] - pk["t0"]) / r1
        d2 = (pl["t1"] - pl["t0"]) / r2
        if ready is not None:  # wait (hold) until the next parcel sits at the stop
            g_out = t + (pk["anchor"] - pk["t0"]) / r1
            wait = max(0.0, ready + 0.2 - g_out)
            if wait >= IDLE_MIN_S and segs and station.get("idle", True):
                segs.extend(_idle_segs(t, wait, k, station.get("x", 0.0)))  # (no rnd draw: plans unchanged)
                t += wait
            elif wait > 0 and segs:
                segs.append(dict(kind="hold", out0=t, out1=t + wait))
                t += wait
        pick0 = t
        segs.append(dict(kind="pick", clip=pk, ratio=r1, out0=t, out1=t + d1, n=k))
        self.last_lift = t + (pk["events"]["lift"] - pk["t0"]) / r1
        # gap control: the hands are over the belt from 0.7 s before the release to 0.6 s after it; if an upstream
        # carton passes then, hold the carton (turned to the belt) until the gap comes (max 2.5 s)
        wait = 0.0
        for _ in range(8):
            rel_t = t + d1 + wait + (pl["anchor"] - pl["t0"]) / r2
            hit = [b1 for (b0, b1) in busy if b0 < rel_t + 0.5 and b1 > rel_t - 0.6]
            if not hit:
                break
            wait = min(6.0, wait + max(hit) - (rel_t - 0.6) + 0.05)
        if wait > 0:
            segs.append(dict(kind="hold", out0=t + d1, out1=t + d1 + wait, n=k))
        segs.append(dict(kind="place", clip=pl, ratio=r2, out0=t + d1 + wait, out1=t + d1 + wait + d2, n=k,
                         gap_wait=round(wait, 2)))
        out = dict(n=k, pick0=pick0, grasp=pick0 + (pk["anchor"] - pk["t0"]) / r1, lift=self.last_lift,
                   release=t + d1 + wait + (pl["anchor"] - pl["t0"]) / r2, end=t + d1 + wait + d2)
        self.t = t + d1 + wait + d2
        self.k = k + 1
        return out

    def delay(self, n, dt, cycles=()):
        """Hold carton n (turned to the belt) dt seconds longer before its place clip: the spot on the belt is still
        taken (a simulation finds out late). Its place and everything planned after it shift by dt; the cycle dicts
        in `cycles` (as returned by cycle()) are shifted with them."""
        i = next(j for j, sg in enumerate(self.segs) if sg["kind"] == "place" and sg.get("n") == n)
        t0 = self.segs[i]["out0"]
        for sg in self.segs[i:]:
            sg["out0"] += dt
            sg["out1"] += dt
        place = self.segs[i]
        prev = self.segs[i - 1]
        if prev["kind"] == "hold" and prev.get("n") == n and abs(prev["out1"] - t0) < 1e-9:  # extend the gap hold
            prev["out1"] += dt
        else:
            self.segs.insert(i, dict(kind="hold", out0=t0, out1=t0 + dt, n=n))
        place["gap_wait"] = round(place.get("gap_wait", 0.0) + dt, 2)
        self.t += dt
        for c in cycles:
            if c["n"] == n:
                c["release"] += dt
                c["end"] += dt
            elif c["n"] > n:
                for k_ in ("pick0", "grasp", "lift", "release", "end"):
                    c[k_] += dt

    def idle_until(self, t):
        """Nothing to pick: stand (hold) until t."""
        if t > self.t and self.segs:
            self.segs.append(dict(kind="hold", out0=self.t, out1=t))
        self.t = max(self.t, t)


def plan_cycles(rig, station, n_frames, fps, rnd, picks, places, parcel_ready=None, busy=(), pick_pool=None):
    """The whole timeline at once (the benches): Planner cycles until the frames are covered. Returns the segs."""
    P = Planner(station, rnd, picks, places, busy, pick_pool)
    T = n_frames / fps
    while P.t < T + 1.0:
        k = P.k
        ready = parcel_ready(k) if callable(parcel_ready) else (
            P.last_lift + station["refill_s"] if (station.get("refill_s") and P.last_lift is not None) else None)
        P.cycle(ready)
    return P.segs


def assemble(rig, segs, station, n_frames, fps, frame0=1, join_s=0.3):
    """Per-frame world rotations (F,J,3,3) and source joint positions (F,J,3) for the whole timeline + events."""
    b0 = take(segs[0]["clip"]["take"])
    J = b0["J"]
    F = n_frames
    times = np.arange(F) / fps
    Dw = np.zeros((F, len(J), 3, 3))
    Pw = np.zeros((F, len(J), 3))
    PL = np.zeros((F, 2, 3))
    owner = np.full(F, -1)
    events = []
    belt_yaw = station["belt_yaw"]
    prev_end_yaw = None
    # place first: its start heading fixes the preceding pick's end heading
    for i, sg in enumerate(segs):
        if sg["kind"] == "hold":
            continue
        c, r = sg["clip"], sg["ratio"]
        b = take(c["take"])
        s_, _, _ = R.leg_ratio(rig, b)
        m = (times >= sg["out0"] - 1e-9) & (times < sg["out1"] - 1e-9)
        if not m.any():
            continue
        tt = c["t0"] + (times[m] - sg["out0"]) * r
        Dc, Pc = R.clip_world(b, tt, fps / r, mirror=c["mirror"])
        Da, Pa = R.clip_world(b, [c["anchor"], c["t0"], c["t1"]], fps / r, mirror=c["mirror"])
        ya = np.unwrap(R.yaw_of(Da[:, J["Hips"]]))
        hip_a = (Pa[0, J["LeftHip"]] + Pa[0, J["RightHip"]]) / 2
        pa = palms(b, Da[:1], Pa[:1])[0].mean(0)
        if sg["kind"] == "idle":  # stood where the last clip ended, facing the way it faced
            fp = max(0, int(math.floor(sg["out0"] * fps)) - 1)
            if owner[fp] >= 0:
                y_prev = float(R.yaw_of(Dw[fp:fp + 1, J["Hips"]])[0])
                r_prev = (Pw[fp, J["LeftHip"]] + Pw[fp, J["RightHip"]])[:2] / 2
            else:
                y_prev, r_prev = belt_yaw, np.array([station["x"], station.get("clear_y", 0.0)
                                                     - 0.1 * station.get("belt_side", -1)])
            Y = R.rz(y_prev - ya[0])[0]
            sg.update(Y=Y, root=r_prev)
            root = r_prev
        elif sg["kind"] == "place":
            want_yaw = belt_yaw  # facing the belt at the release
            Y = R.rz(want_yaw - ya[0])[0]
            v = Y @ (s_ * (pa - hip_a))
            px, py = station.get("place_xy", (station["x"], station.get("place_y", 0.0)))
            ry_ = py - v[1]  # palms over the place spot, body clear of the belt frame (belt_side: which side it is)
            ry_ = max(station["clear_y"], ry_) if station.get("belt_side", -1) < 0 else min(station["clear_y"], ry_)
            root = np.array([px - v[0], ry_])
            start_yaw = want_yaw + (ya[1] - ya[0])
            sg.update(Y=Y, root=root, start_yaw=start_yaw)
        else:
            nxt = next(x for x in segs[i + 1:] if x["kind"] == "place")  # (a gap hold may sit between)
            # chain: the pick ends with the heading the place starts with
            cpl = nxt["clip"]
            bpl = take(cpl["take"])
            Dpl, _ = R.clip_world(bpl, [cpl["anchor"], cpl["t0"]], fps, mirror=cpl["mirror"])
            ypl = np.unwrap(R.yaw_of(Dpl[:, J["Hips"]]))
            end_yaw = belt_yaw + (ypl[1] - ypl[0])
            grasp_yaw = end_yaw - (ya[2] - ya[0])
            Y = R.rz(grasp_yaw - ya[0])[0]
            v = Y @ (s_ * (pa - hip_a))
            tp = station.get("pick_pts", {}).get(sg["n"], station["table_pt"])  # per carton (wall columns)
            root = np.array([tp[0] - v[0], tp[1] - v[1]])
            lo = station.get("pick_root_min", (-1e9, -1e9))
            hi = station.get("pick_root_max_n", {}).get(sg["n"], station.get("pick_root_max", (1e9, 1e9)))
            root = np.clip(root, lo, hi)  # body clear of the table rail / stop: IK takes the rest of the reach
            sg.update(Y=Y, root=root)
        Dseg = np.einsum("ij,fkjl->fkil", Y, Dc)
        Pseg = np.einsum("ij,fkj->fki", Y, s_ * (Pc - hip_a * np.array([1, 1, 0])))
        Pseg[:, :, :2] += root
        Dw[m], Pw[m] = Dseg, Pseg
        PL[m] = palms(b, Dseg, Pseg)
        owner[m] = i
        if sg["kind"] == "idle":
            continue
        ev_t = sg["out0"] + (c["anchor"] - c["t0"]) / r
        events.append(dict(kind="grasp" if sg["kind"] == "pick" else "release", t=ev_t, n=sg["n"],
                           frame=frame0 + int(round(ev_t * fps)), seg=i))
        if sg["kind"] == "pick":
            lift_t = sg["out0"] + (c["events"]["lift"] - c["t0"]) / r
            events.append(dict(kind="lift", t=lift_t, n=sg["n"], frame=frame0 + int(round(lift_t * fps)), seg=i))
    # holds: repeat the last pose before them, with a breathing sway (chest +-1.2 deg, ~3.5 s) and, on holds over
    # 0.6 s, the head turned ~25 deg upstream (watching for a gap on the belt)
    for f in range(F):
        if owner[f] < 0 and f > 0:
            Dw[f], Pw[f], PL[f], owner[f] = Dw[f - 1].copy(), Pw[f - 1], PL[f - 1], owner[f - 1]
    # 018b: idle variety without new sources: on ~1 in 3 idles (>= 1.2 s) an additive glance up the feed, head + neck
    # 20-30 deg for 0.8-1.2 s, eased in and out (deterministic per segment: plans unchanged)
    for i_s, sg in enumerate(segs):
        if sg["kind"] != "idle" or sg["out1"] - sg["out0"] < 1.2 or (int(sg["out0"] * 7.0) % 3):
            continue
        dur = sg["out1"] - sg["out0"]
        amp = math.radians(20 + (int(sg["out0"] * 13.0) % 11))
        gd = min(dur - 0.2, 0.8 + (int(sg["out0"] * 17.0) % 5) * 0.1)
        g0 = sg["out0"] + (dur - gd) / 2
        up_dir = station.get("upstream_turn", -1.0)
        for f in range(max(0, int(math.ceil(g0 * fps))), min(F, int((g0 + gd) * fps) + 1)):
            w = _smooth(min(f / fps - g0, g0 + gd - f / fps) / 0.3)
            for jn, share in (("Neck", 0.4), ("Head", 0.6)):
                Dw[f, J[jn]] = R.rz(up_dir * amp * share * w)[0] @ Dw[f, J[jn]]
    # 018b: and on ~1 in 6 idles (>= 1.4 s, not those with the glance) a shoulder roll: both collars back and round,
    # one cycle of ~1.1 s about the body's left-right axis (+-9 deg), eased in and out
    for sg in segs:
        dur = sg["out1"] - sg["out0"]
        if sg["kind"] != "idle" or dur < 1.4 or not (int(sg["out0"] * 7.0) % 3) or int(sg["out0"] * 11.0) % 2:
            continue
        r0 = sg["out0"] + (dur - 1.1) / 2
        for f in range(max(0, int(math.ceil(r0 * fps))), min(F, int((r0 + 1.1) * fps) + 1)):
            u = (f / fps - r0) / 1.1
            ang = math.radians(9.0) * math.sin(2 * math.pi * u) * _smooth(min(u, 1 - u) / 0.25)
            lat = Dw[f, J["Hips"]] @ np.array([1.0, 0, 0])
            for jn in ("LeftCollar", "RightCollar"):
                Dw[f, J[jn]] = _rotexp(lat * ang) @ Dw[f, J[jn]]
    for sg in segs:
        if sg["kind"] != "hold":
            continue
        dur = sg["out1"] - sg["out0"]
        for f in range(max(0, int(math.ceil(sg["out0"] * fps))), min(F, int(sg["out1"] * fps) + 1)):
            tt = f / fps - sg["out0"]
            lat = Dw[f, J["Hips"]] @ np.array([1.0, 0, 0])
            br = _rotexp(lat * math.radians(1.2) * math.sin(2 * math.pi * tt / 3.5))
            for jn in ("Chest", "Chest2"):
                Dw[f, J[jn]] = br @ Dw[f, J[jn]]
            if dur > 0.6:
                w = _smooth(min(tt, dur - tt) / 0.4)
                up_dir = station.get("upstream_turn", -1.0)  # belt A runs +x: upstream is the worker's right
                for jn, share in (("Neck", 0.4), ("Head", 0.6)):
                    Dw[f, J[jn]] = R.rz(up_dir * math.radians(25) * share * w)[0] @ Dw[f, J[jn]]
    # inertialized joins: at each segment change, the previous pose (extrapolated one frame) minus the new pose,
    # decaying with a smootherstep over join_s
    nj = max(2, int(round(join_s * fps)))
    for f in range(1, F):
        if owner[f] != owner[f - 1]:
            prevD = Dw[f - 1]
            prevP = Pw[f - 1] + (Pw[f - 1] - Pw[f - 2]) if f > 1 else Pw[f - 1]
            off_r = _rotlog(np.einsum("kij,klj->kil", prevD, Dw[f]))  # prev * new^T
            off_p = prevP - Pw[f]
            for i_ in range(nj):
                if f + i_ >= F or owner[f + i_] != owner[f]:
                    break
                u = i_ / nj
                w = 1 - u ** 3 * (u * (u * 6 - 15) + 10)
                Dw[f + i_] = np.einsum("kij,kjl->kil", _rotexp(off_r * w), Dw[f + i_])
                Pw[f + i_] = Pw[f + i_] + off_p * w
                PL[f + i_] = PL[f + i_] + off_p[[J["LeftWrist"], J["RightWrist"]]] * w
    # whole-body turn rate (builder note 0650 #1: <= 25 deg / frame): the retimed takes swung the hips ~90 deg from
    # the table to the belt in 2 frames (47 deg / frame, hub run 4). The heading is held to 220 deg/s (forward and
    # backward passes averaged: the turn spreads round the corner), each frame's pose turned about its hip centre;
    # the hands' IK works to the carton path, so they still meet it
    # measured on the hip-joint line, as the motion gate does (the hips joint's own yaw held to 220 deg/s still gave
    # 27.9 deg / frame on that line: the pelvis pitches and rolls in the reach); the feet locks and the solve on the
    # avatar add ~25 % (200 deg/s here measured 24.8 deg / frame, run 8): 160 deg/s for the 22 deg / frame limit
    # (Rexton 31 Oct)
    hl_ = Pw[:, J["RightHip"]] - Pw[:, J["LeftHip"]]
    yaw_h = np.unwrap(np.arctan2(hl_[:, 1], hl_[:, 0]))
    d_y = _rate_limit(yaw_h, times, math.radians(station.get("turn_max_dps", 140.0))) - yaw_h
    hc = (Pw[:, J["LeftHip"]] + Pw[:, J["RightHip"]]) / 2
    for f in np.nonzero(np.abs(d_y) > 1e-6)[0]:
        Rz = R.rz(d_y[f])[0]
        c_ = hc[f] * np.array([1.0, 1.0, 0.0])
        Dw[f] = np.einsum("ij,kjl->kil", Rz, Dw[f])
        Pw[f] = (Pw[f] - c_) @ Rz.T + c_
        PL[f] = (PL[f] - c_) @ Rz.T + c_
    return Dw, Pw, PL, sorted(events, key=lambda e: e["t"]), J


def _rate_limit(th, times, w_max):
    """Heading th(t) (rad, unwrapped) with its rate held to w_max (rad/s): a forward and a backward pass, averaged
    (as remover._rate_limit)."""
    if len(th) < 3:
        return th
    dt = np.r_[np.diff(times), np.diff(times)[-1:]]
    fw_, bw_ = th.copy(), th.copy()
    for i in range(1, len(th)):
        lim = w_max * dt[i - 1]
        fw_[i] = fw_[i - 1] + np.clip(th[i] - fw_[i - 1], -lim, lim)
    for i in range(len(th) - 2, -1, -1):
        lim = w_max * dt[i]
        bw_[i] = bw_[i + 1] + np.clip(th[i] - bw_[i + 1], -lim, lim)
    return 0.5 * (fw_ + bw_)


def two_bone(sol, rig, chain, P, wgt, pole_bias=None):
    """Pull the end of `chain` (3 bone names) to P (F,3) with weight wgt (F,), pole = current middle joint; the end
    bone keeps its world rotation. Updates A, L, Hw (chain + the end bone's descendants)."""
    A, L, Hw = sol["A"], sol["L"], sol["Hw"]
    rest, par, bi, MR = rig["rest"], rig["par"], rig["bi"], rig["MR"]
    b1, b2, b3 = (bi[n] for n in chain)
    k = wgt > 1e-6
    if not k.any():
        return
    T, K, E = Hw[k, b1], Hw[k, b2], Hw[k, b3]
    Pt = E + (P[k] - E) * wgt[k, None]
    l1 = np.linalg.norm(K - T, axis=1)
    l2 = np.linalg.norm(E - K, axis=1)
    d_ = np.linalg.norm(Pt - T, axis=1)
    d = np.clip(d_, np.abs(l1 - l2) + 1e-4, l1 + l2 - 1e-4)
    fr = np.nonzero(k)[0]
    sol.setdefault("ik_short", {})[chain[2]] = (int((d_ > l1 + l2).sum()), float(np.max(d_ - (l1 + l2))),
                                                 int(k.sum()), float(np.median(l1 + l2)),
                                                 [(int(fr[i]) + 1, round(float(d_[i] - l1[i] - l2[i]), 3))
                                                  for i in np.nonzero(d_ > l1 + l2)[0]])
    u = (Pt - T) / d_[:, None]
    Pt = T + u * d[:, None]
    kv = K - T
    if pole_bias is not None:  # push the pole (the elbow) this way (e.g. outward, clear of a held carton)
        kv = kv + pole_bias[k] * np.linalg.norm(kv, axis=1, keepdims=True)
    kp = kv - np.sum(kv * u, 1)[:, None] * u
    kp /= np.linalg.norm(kp, axis=1, keepdims=True) + 1e-12
    a_ = (l1 ** 2 - l2 ** 2 + d ** 2) / (2 * d)
    h_ = np.sqrt(np.maximum(l1 ** 2 - a_ ** 2, 0))
    K2 = T + u * a_[:, None] + kp * h_[:, None]
    R1 = R._swing_np(K - T, K2 - T)
    R2 = R._swing_np(np.einsum("fij,fj->fi", R1, E - K), Pt - K2)
    toArm = lambda R_: np.einsum("ji,fjk,kl->fil", MR, R_, MR)  # noqa: E731
    A1, A2 = toArm(R1), toArm(R2)
    A[k, b1] = A1 @ A[k, b1]
    A[k, b2] = A2 @ A1 @ A[k, b2]
    for i_ in (b1, b2, b3):
        p = par[i_]
        L[k, i_] = np.einsum("ij,fjk,fkl->fil", rest[i_].T @ rest[p], np.transpose(A[k, p], (0, 2, 1)), A[k, i_])
    dE = Pt - E
    Hw[k, b2] = K2
    desc = [b3] + [i for i in range(len(par)) if _is_desc(par, i, b3)]
    for i in desc:
        Hw[k, i] = Hw[k, i] + dE
    sol.setdefault("keyed", set()).update((b1, b2, b3))


def _is_desc(par, i, a):
    p = par[i]
    while p >= 0:
        if p == a:
            return True
        p = par[p]
    return False


def _pivot(sol, rig, bone, ang, backward=False):
    """Rotate `bone` and everything below it about its head by ang[f] (rad) about the body's lateral axis (the hip
    line): forward flexion, or extension with backward=True. Updates A, L (of `bone`) and Hw."""
    k = ang > 1e-5
    if not k.any():
        return
    bi, Hw, MR = rig["bi"], sol["Hw"], rig["MR"]
    lv = Hw[:, bi["Bip01 L Thigh"]] - Hw[:, bi["Bip01 R Thigh"]]
    lv[:, 2] = 0
    lv /= np.linalg.norm(lv, axis=1, keepdims=True)
    Rw = _rotexp(lv[k] * (ang[k] * (-1.0 if backward else 1.0))[:, None])
    Ra = np.einsum("ji,fjk,kl->fil", MR, Rw, MR)
    b = bi[bone]
    piv = Hw[k, b].copy()
    for i in [b] + [i for i in range(len(rig["par"])) if _is_desc(rig["par"], i, b)]:
        sol["A"][k, i] = Ra @ sol["A"][k, i]
        Hw[k, i] = piv + np.einsum("fij,fj->fi", Rw, Hw[k, i] - piv)
    p_ = rig["par"][b]
    sol["L"][k, b] = np.einsum("ij,fjk,fkl->fil", rig["rest"][b].T @ rig["rest"][p_],
                               np.transpose(sol["A"][k, p_], (0, 2, 1)), sol["A"][k, b])


def fk_desc(sol, rig, root):
    """Recompute A and world heads of every descendant of `root` from their locals (parents first)."""
    A, L, Hw = sol["A"], sol["L"], sol["Hw"]
    rest, rhead, par, MR, sc_ = rig["rest"], rig["rhead"], rig["par"], rig["MR"], rig["scale"]
    for i in range(len(par)):  # bones are sorted parents-first
        if not _is_desc(par, i, root):
            continue
        p = par[i]
        A[:, i] = A[:, p] @ rest[p].T @ rest[i] @ L[:, i]
        Hw[:, i] = Hw[:, p] + np.einsum("ij,fj->fi", MR, np.einsum("fij,j->fi", A[:, p] @ rest[p].T[None],
                                                                     rhead[i] - rhead[p])) * sc_


def palm_pts(sol, rig):
    """Avatar palm centres (F,2,3): hand head + 55 % towards the middle finger base."""
    bi, Hw = rig["bi"], sol["Hw"]
    return np.stack([Hw[:, bi[f"Bip01 {x} Hand"]] + 0.55 * (Hw[:, bi[f"Bip01 {x} Finger2"]] - Hw[:, bi[f"Bip01 {x} Hand"]])
                     for x in ("L", "R")], 1)


def I_log(Rm):
    return _rotlog(Rm[None])[0]


def belt_path(station, p0, s):
    """Where a carton set down at p0 is after s metres of belt travel: along station['induct_dir'] (an induct belt)
    until belt A's centre line (station['main_y']), then along +x (station['belt_dir']); plain +x without an induct."""
    p0 = np.asarray(p0, float)
    if "induct_dir" not in station:
        return p0 + np.array([station.get("belt_dir", 1.0), 0, 0]) * s
    d = np.array([*station["induct_dir"], 0.0])
    s1 = max(0.0, (p0[1] - station["main_y"]) / max(1e-6, -d[1]))
    if s <= s1:
        return p0 + d * s
    return p0 + d * s1 + np.array([station.get("belt_dir", 1.0), 0, 0]) * (s - s1)


def _cut_start(station, c_xy, w_, d_, yaw_):
    """Shift along the induct belt so the carton's footprint keeps 3 cm inside its near end, which is cut parallel to
    belt A (a world-x line through the start): the square-cut zone let back corners hang over it (collision check)."""
    S_, d2 = np.array(station["induct_start"]), np.array(station["induct_dir"])
    c_, s_ = math.cos(yaw_), math.sin(yaw_)
    ymax = c_xy[1] + abs(s_) * w_ / 2 + abs(c_) * d_ / 2
    over = ymax - (S_[1] - 0.03)
    if over > 0 and d2[1] < -1e-6:
        return c_xy + d2 * (over / -d2[1])
    return c_xy


def _smooth(u):
    u = np.clip(u, 0, 1)
    return u * u * (3 - 2 * u)


def _induct_zone(rv, S_, d2, n2, ea, el, hw, yaw_w, w_, d_, edge=0.03):
    """(along, across) of a parcel centre at rv (from the induct start) clamped to the belt's placement zone: 0.05 m +
    its half extent past the start .. 0.5 m along, inside the width, and its footprint `edge` inside the near end (the
    line y = S_y; the belt runs to -y)."""
    al = float(np.clip(rv @ d2, 0.05 + ea, max(0.05 + ea, 0.5)))
    lt = float(np.clip(rv @ n2, -max(0.0, hw - el), max(0.0, hw - el)))
    ey = 0.5 * (abs(w_ * math.sin(yaw_w)) + abs(d_ * math.cos(yaw_w)))  # its half extent in world y
    if d2[1] < -1e-6:
        cap = max(0.05 + ea, 0.5)
        lt = min(lt, (-d2[1] * cap - edge - ey) / max(n2[1], 1e-6)) if n2[1] > 1e-6 else lt
        lt = max(lt, -max(0.0, hw - el))
        al = max(al, (edge + ey + n2[1] * lt) / -d2[1])
    return al, lt


def finger_wrap(sol, rig, k, x, fingers, mode, z_ref, toward, w, rf=0.009):
    """Curl fingers of hand x round an edge, on frames k (bool mask); z_ref, toward (n,3) horizontal unit, w (n,).
    mode "under": the first joint below z_ref - rf flexes so the rest of the finger runs in under (towards `toward`),
    tip up to z_ref - rf; "over": the knuckle flexes so the finger lies on a top at z_ref + rf, towards `toward`.
    Flexion only (in the plane of the finger and the palm normal, towards the palm), <= 100 deg per joint; joints after
    the bent one go straight on. Returns {finger: frames it bent}."""
    bi = rig["bi"]
    MRm = rig["MR"]
    hd = bi[f"Bip01 {x} Hand"]
    up = np.array([0.0, 0.0, 1.0])
    out = {}
    for f_ in fingers:
        ch = [bi[f"Bip01 {x} Finger{f_}{s_}"] for s_ in ("", "1", "2")]
        done = np.zeros(int(k.sum()), bool)
        for j, b_ in enumerate(ch):
            Hw = sol["Hw"]
            n_loc = rig["AT"][hd].T @ (MRm.T @ np.array([0.0, 0.0, -1.0]))
            npm = np.einsum("ij,fjk,k->fi", MRm, sol["A"][k, hd], n_loc)
            npm /= np.linalg.norm(npm, axis=1, keepdims=True)
            hd_ = Hw[k, b_]
            nxt = Hw[k, ch[j + 1]] if j < 2 else Hw[k, b_] + (Hw[k, b_] - Hw[k, ch[1]]) * 0.9
            v = nxt - hd_
            tip = Hw[k, ch[2]] + (Hw[k, ch[2]] - Hw[k, ch[1]]) * 0.9
            lrem = np.linalg.norm(tip - hd_, axis=1)
            if mode == "under":  # (the last joint also when only its tip is below: a straight 2.5 cm tip went
                # into the belt at the set-down when the joint sat 1 mm short of the line - bench 31 Oct)
                here = (~done) & ((hd_[:, 2] < z_ref - rf) | ((j == 2) & (tip[:, 2] < z_ref - rf)))
                d = toward * lrem[:, None] + up * np.clip(z_ref - rf - hd_[:, 2], 0, None)[:, None]
            else:
                here = (~done) & np.full(len(done), j == 0)
                d = toward * lrem[:, None] + up * (z_ref + rf - hd_[:, 2])[:, None]
            if j > 0:
                d = np.where(done[:, None], hd_ - Hw[k, ch[j - 1]], d)
            vn = v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-12)
            nn = npm - np.sum(npm * vn, 1)[:, None] * vn
            nn /= np.linalg.norm(nn, axis=1, keepdims=True) + 1e-12
            dp = np.sum(d * vn, 1)[:, None] * vn + np.maximum(np.sum(d * nn, 1), 0.0)[:, None] * nn
            ang = np.clip(np.arctan2(np.sum(dp * nn, 1), np.sum(dp * vn, 1)), 0.0, math.radians(100))
            act = here | done
            if act.any():
                ax = np.cross(vn, nn)
                Rw = _rotexp(ax * (np.where(act, ang, 0.0) * w)[:, None])
                Ra = np.einsum("ji,fjk,kl->fil", MRm, Rw, MRm)
                piv = Hw[k, b_].copy()
                for i in [b_] + [i for i in range(len(rig["par"])) if _is_desc(rig["par"], i, b_)]:
                    sol["A"][k, i] = Ra @ sol["A"][k, i]
                    Hw[k, i] = piv + np.einsum("fij,fj->fi", Rw, Hw[k, i] - piv)
                p_ = rig["par"][b_]
                sol["L"][k, b_] = np.einsum("ij,fjk,fkl->fil", rig["rest"][b_].T @ rig["rest"][p_],
                                            np.transpose(sol["A"][k, p_], (0, 2, 1)), sol["A"][k, b_])
            out[f_] = out.get(f_, 0) + int(here.sum())
            done |= here
    return out


PINCH_DROOP = math.radians(10.0)  # a polybag held by one long edge: the free side hangs ~10 deg (review 017 #2 sag)


def build(rig, segs, station, parcels, n_frames, fps, frame0=1, name="inductor", ramp_s=0.3):
    """Solve + feet + hands + parcel bake. parcels[n] = dict(dims=(w along the hands, d, h)). Writes the action and
    returns dict(events, parcel tracks {n: (F,3) loc, (F,) yaw, (F,) pitch, state per frame}, sol, src)."""
    Dw, Pw, PL, events, J = assemble(rig, segs, station, n_frames, fps, frame0)
    want = (Pw[:, J["LeftHip"]] + Pw[:, J["RightHip"]]) / 2
    if "root_min_y" in station:  # hips never closer to the belt frame than this, every frame (soft max, 3 cm)
        lo_, k_ = station["root_min_y"], 0.03
        sg_ = -station.get("belt_side", -1)  # +1: hips stay above lo_ (belt at -y); -1: below it (belt at +y)
        dy_ = (want[:, 1] - lo_) * sg_
        want[:, 1] = lo_ + sg_ * np.where(dy_ > 4 * k_, dy_, k_ * np.log1p(np.exp(np.clip(dy_ / k_, -50, 50))))
    sol = R.solve(rig, Dw, J, want)
    dz = R.floor_dz(rig, sol, station.get("lift", 0.0))
    Pw[:, :, 2] += dz
    for sd, sj in (("L", "LeftAnkle"), ("R", "RightAnkle")):
        R._foot_lock(sol["A"], sol["Hw"], sol["L"], rig["rest"], rig["par"], rig["bi"], sd,
                     R.contacts(Pw[:, J[sj]], fps), rig["MR"], fps)
    F = n_frames
    pm0 = palm_pts(sol, rig)  # mocap palms (after the solve, before hand IK)
    pinch_grip = station.get("mailer_grip") == "far_pinch"
    if pinch_grip:  # review 018 #4: mailers by the far long edge - index + middle down a roller gap and hooked under,
        # ring + little finger and the thumb on the top. The knuckles' place relative to the palm centre in the hand's
        # own frame (fingers, palm normal, side), from frame 0 (the knuckles sit on the hand bone: curl-independent)
        bi0, Hw_ = rig["bi"], sol["Hw"]
        pinch_c = {}
        for x_ in ("L", "R"):
            h0, f20 = Hw_[0, bi0[f"Bip01 {x_} Hand"]], Hw_[0, bi0[f"Bip01 {x_} Finger2"]]
            fd0 = (f20 - h0) / np.linalg.norm(f20 - h0)
            n_l0 = rig["AT"][bi0[f"Bip01 {x_} Hand"]].T @ (rig["MR"].T @ np.array([0.0, 0.0, -1.0]))
            n0 = rig["MR"] @ sol["A"][0, bi0[f"Bip01 {x_} Hand"]] @ n_l0
            n0 = n0 - np.dot(n0, fd0) * fd0
            n0 /= np.linalg.norm(n0)
            sd0 = np.cross(fd0, n0)
            pc0 = h0 + 0.55 * (f20 - h0)
            o_im = 0.5 * (Hw_[0, bi0[f"Bip01 {x_} Finger1"]] + f20) - pc0
            pinch_c[x_] = (float(o_im @ fd0), float(o_im @ n0), float(o_im @ sd0))
            if x_ == "R":
                pinch_mcp = 0.45 * float(np.linalg.norm(f20 - h0))  # palm centre -> middle knuckle
    tf = lambda t: int(np.clip(round(t * fps), 0, F - 1))  # noqa: E731
    # a pick whose grasp is past the last frame gets no track (clipped to the last frame, its grasp, lift and release
    # collapsed there and its approach went through the end stop: bench / end of every hub window, 31 Oct)
    grasp = {e["n"]: tf(e["t"]) for e in events if e["kind"] == "grasp" and e["t"] * fps <= F - 1}
    lift = {e["n"]: tf(e["t"]) for e in events if e["kind"] == "lift"}
    rel = {e["n"]: tf(e["t"]) for e in events if e["kind"] == "release"}
    tracks = {}
    tgt = {x: pm0[:, i].copy() for i, x in enumerate(("L", "R"))}
    wgt = np.zeros(F)
    wori = np.zeros(F)  # hand orientation / flat fingers (fades after the release; the IK may still be on)
    wo_h = {"L": np.zeros(F), "R": np.zeros(F)}  # per hand: orientation weight
    flat_h = {"L": np.zeros(F), "R": np.zeros(F)}  # per hand: fingers flattened into the palm plane
    one_f = np.zeros(F, bool)  # frames around a one-hand carton (the left arm hangs relaxed)
    rest_b = {"L": np.zeros(F), "R": np.zeros(F)}  # after a release: palm turning to the thigh, fingers down
    brace_b = np.zeros(F)  # ... or, with the shoulder over the table's near rail, the left palm rests on the rail
    rf = max(1, int(round(ramp_s * fps)))
    slope = station.get("table_slope", 0.0)
    for n in sorted(grasp):
        if n not in rel or n not in parcels:
            continue
        g, r_, lf = grasp[n], rel[n], lift.get(n, grasp[n])
        w_, d_, h_ = parcels[n]["dims"]
        # one-hand pick (flat mailers, 3.5-5 cm: no side face to hold): the right hand comes down on the top near the
        # body-side edge, fingers forward over it, thumb along the near edge; the left arm hangs relaxed
        one = parcels[n].get("grip") == "one_hand"
        pinch_h = ()
        if one and pinch_grip:  # review 017 #2: a big polybag (> 40 cm) takes two hands, both on the far edge (one-
            # handed by an edge it hung across his body: the free forearm hit it; on its 5 cm side faces the palms
            # went 2 cm in, and its downhill end is against the end stop)
            pinch_h = ("L", "R") if max(w_, d_) > 0.40 else ("R",)
            one = len(pinch_h) == 1
        pinch = bool(pinch_h)
        tp = np.array(station.get("pick_pts", {}).get(n, station["table_pt"])) + np.array([0, 0, h_ / 2])
        at_ = parcels[n].get("at")  # a simulation's carton centre at the stop (flow.py): exactly there
        if at_ is not None:
            tp = np.array(at_, float)
        mid = pm0.mean(1)
        ax = pm0[:, 1] - pm0[:, 0]
        if one or pinch:  # one hand: the axis to the free (hanging) hand swings with the gait - the mailer spun in the hand
            # (bench 31 Oct); it turns with his shoulder line instead
            bi_ = rig["bi"]
            ax = sol["Hw"][:, bi_["Bip01 R UpperArm"]] - sol["Hw"][:, bi_["Bip01 L UpperArm"]]  # (the shoulder line:
            # the clavicle heads are 1-2 cm apart, ill-conditioned - remover.py, 31 Oct)
        yaw = np.arctan2(ax[:, 1], ax[:, 0])
        if not (one or pinch):  # two hands across it: the grip line has no sign (the palms crossed over at a clip
            yaw = np.unwrap(2 * yaw) / 2  # join and flipped it: the carton turned 136 deg in one frame, run 7)
        yaw = np.unwrap(yaw)
        # in the hands the carton turns / travels no faster than the body can carry it (Rexton 31 Oct, held-object
        # jumps: 0.46 m and 136 deg in one frame at the pick-to-place join); the hands are IK'd onto it, so they follow
        t_ = np.arange(F) / fps
        yaw = _rate_limit(yaw, t_, math.radians(station.get("carry_turn_max_dps", 60.0)))  # (200: the hands IK'd to
        # a carton turning 20 deg / frame lagged 5-7 cm, slips run 13)
        mid = np.stack([_rate_limit(mid[:, i_], t_, station.get("carry_axis_max_mps", 1.0)) for i_ in range(3)], 1)
        # the carton sits square on the table (yaw snapped to the table's axes); in the hands it turns rigidly with
        # the hand axis, keeping that offset
        if "grip_axis_yaw" in station:  # snap to the table's axes, preferring the hands across this one (30 deg bias)
            cands = [station["grip_axis_yaw"] + k_ * math.pi / 2 for k_ in range(-8, 9)
                     if not station.get("grip_axis_strict") or k_ % 2 == 0]  # strict: only the faces across it
            tyaw = min(cands, key=lambda c_: abs(yaw[g] - c_) + (0 if (round((c_ - station["grip_axis_yaw"]) /
                                                                             (math.pi / 2)) % 2 == 0) else math.radians(30)))
        else:
            tyaw = station.get("table_yaw", 0.0) + round((yaw[g] - station.get("table_yaw", 0.0)) / (math.pi / 2)) * math.pi / 2
        fy = parcels[n].get("yaw")  # the simulation's yaw on the table (object +X): the hands take the faces nearest
        obj_off = 0.0              # their own axis; across the other pair, the dims swap (same physical box)
        far_key = None
        if pinch:  # the far pinch takes the edge farthest from him (its +Y away from his pelvis): the
            # nearest-axis snap gave some bags the downhill edge, over the end stop (bench 31 Oct)
            u_ = tp[:2] - sol["Hw"][g, rig["bi"]["Bip01 Pelvis"]][:2]
            u_ /= np.linalg.norm(u_) + 1e-9
            fs_ = -1.0 if station.get("flip_fwd") else 1.0
            far_key = lambda c_: -(fs_ * (-math.sin(c_) * u_[0] + math.cos(c_) * u_[1])) + 0.01 * abs(yaw[g] - c_)  # noqa: E731
            tyaw = min((tyaw + k_ * math.pi / 2 for k_ in range(-8, 9)), key=far_key)
        if fy is not None:
            tyaw = min((fy + k_ * math.pi / 2 for k_ in range(-8, 9)), key=far_key or (lambda c_: abs(yaw[g] - c_)))
            if round((tyaw - fy) / (math.pi / 2)) % 2:
                w_, d_ = d_, w_
            obj_off = fy - tyaw  # object yaw = this yaw + obj_off
        yoff = tyaw - yaw[g]
        yaw = yaw + yoff
        if pinch and "table_stop_y" in station and at_ is None:  # (far pinch, bench: against the end stop by its own
            ey_ = 0.5 * (abs(w_ * math.sin(tyaw)) + abs(d_ * math.cos(tyaw)))  # length, not through it)
            y_new = station["table_stop_y"] + ey_ + 0.005
            tp[2] += math.tan(station.get("table_slope", 0.0)) * (y_new - tp[1])  # (on the sloped rollers)
            tp[1] = y_new
        if "table_align_x" in station and at_ is None:  # skewed rollers run every carton against the operator-side rail
            ex = 0.5 * (abs(w_ * math.cos(tyaw)) + abs(d_ * math.sin(tyaw)))
            tp[0] = station["table_align_x"] + ex + 0.005
        pl_ = mid[r_].copy()
        if "induct_start" in station:  # on the induct belt's placement zone: 0.15-0.6 m along, inside its width
            S_, d2 = np.array(station["induct_start"]), np.array(station["induct_dir"])
            n2 = np.array([-d2[1], d2[0]])
            ang = yaw[r_] - math.atan2(d2[1], d2[0])
            ea = 0.5 * (abs(w_ * math.cos(ang)) + abs(d_ * math.sin(ang)))
            el = 0.5 * (abs(w_ * math.sin(ang)) + abs(d_ * math.cos(ang)))
            hw = station.get("induct_half_w", 0.25) - 0.07  # (squared up by the guides after
            # the set-down, its corners swept into them at -0.02: run 14)
            al, lt = _induct_zone(pl_[:2] - S_, S_, d2, n2, ea, el, hw, yaw[r_], w_, d_)
            pl_[:2] = S_ + d2 * (al + 0.12) + n2 * lt  # (_cut_start here and below: hub run 8, induct rows 29 -> 44:
            # off; +5 cm along: at the zone's start its edge sat on the belt's end frame, run 11)
        else:
            pl_[0] = np.clip(pl_[0], station["place_x"][0], station["place_x"][1])
            ext = 0.5 * (abs(w_ * math.sin(yaw[r_])) + abs(d_ * math.cos(yaw[r_])))  # half extent across the belt
            pl_[1] = np.clip(pl_[1], station["place_y_range"][0] + ext, station["place_y_range"][1] - ext)
        pl_[2] = station["belt_top"] + h_ / 2 + (0.025 if pinch else 0.0)  # (far pinch: the hooked
        # fingertips stay over the belt; let go, the bag drops the last 2.5 cm flat)
        loc = np.zeros((F, 3))
        yw = np.zeros(F)
        pitch = np.zeros(F)
        state = np.array(["table"] * F, dtype=object)
        gi = min(station.get("grip_in", 0.05), d_ / 2)  # grip near the body-side edge (forearms clear the box)
        if one:
            gi = min(0.045, d_ / 2)  # the palm's centre 4.5 cm in from the near edge: the thumb goes under that edge
        fwd = np.stack([-np.sin(yaw), np.cos(yaw), np.zeros(F)], 1)  # parcel local +Y: away from the body
        fwd = -fwd if station.get("flip_fwd") else fwd
        tp_g = tp - fwd[g] * (d_ / 2 - gi)
        xo = min(0.04, max(0.0, w_ / 2 - 0.07))  # one-hand: the palm along the near edge (carton +X)
        xo_h = {}
        if pinch:  # palm facing him 1.2 cm past the far face, fingers down: knuckles 1.2 cm over the top; each
            # pinching hand's index + middle over a roller gap, clear of the end stop; two hands ~26 cm apart
            gi = d_ + 0.012
            tp_g = tp - fwd[g] * (d_ / 2 - gi)
            Xg = np.array([math.cos(yaw[g]), math.sin(yaw[g]), 0.0])
            fd_ = np.array([0.0, 0.0, -1.0])
            n_ = -fwd[g]
            cands_h = {}
            for x_ in pinch_h:
                c_vec = pinch_c[x_][0] * fd_ + pinch_c[x_][1] * n_ + pinch_c[x_][2] * np.cross(fd_, n_)
                cs_ = [0.0]
                if station.get("roller_gaps_y") and abs(Xg[1]) > 0.7:
                    cs_ = [(gy - tp_g[1] - c_vec[1]) / Xg[1] for gy in station["roller_gaps_y"]]
                    cs_ = [c_ for c_ in cs_ if abs(c_) <= w_ / 2 - 0.05
                           and tp_g[1] + Xg[1] * c_ + c_vec[1] >= station.get("pinch_y_min", -1e9)] or [0.0]
                cands_h[x_] = cs_
            if len(pinch_h) == 1:
                xo_h = {"R": min(cands_h["R"], key=abs)}
            else:
                xo_h = dict(zip(("L", "R"), min(((a_, b_) for a_ in cands_h["L"] for b_ in cands_h["R"] if b_ > a_ + 0.09),
                                                key=lambda ab: abs(ab[1] - ab[0] - 0.26) + abs(ab[0] + ab[1]),
                                                default=(-0.13, 0.13))))
            xo = xo_h.get("R", 0.0)
        if one and not pinch and station.get("roller_gaps_y"):  # review 017 #2: thumb under the near edge, a gap
            Xg = np.array([math.cos(yaw[g]), math.sin(yaw[g])])
            if abs(Xg[1]) > 0.7:  # the near edge runs along the fall line (across the rollers)
                cands = [(gy - tp_g[1]) / Xg[1] + 0.03 for gy in station["roller_gaps_y"]]  # thumb 3 cm to -X
                cands = [c_ for c_ in cands if abs(c_) <= w_ / 2 - 0.05]
                if cands:
                    xo = min(cands, key=lambda c_: abs(c_ - xo))
        pl_g = pl_ - fwd[r_] * (d_ / 2 - gi)
        zmin_g = station.get("pick_grip_min_z", 0.0)
        zmin_r = station["belt_top"] + 0.05
        # grip high on the side face (5.5 cm under the top edge: the forearms come over less of the carton), never
        # lower than the support allows
        gz = lambda c, zm: max(0.0, max(zm - c[2], h_ / 2 - 0.055))  # noqa: E731  (016 #3: mid-height grip measured 35 vs 16 collision rows)
        lift_g, lift_r = gz(tp, zmin_g), gz(pl_, zmin_r)
        if one:  # the palm on the top face
            lift_g = lift_r = h_ / 2 + station.get("palm_off_top", 0.042)
        if pinch:  # (the far pinch: the palm centre over the knuckles, those 1.2 cm over the top)
            lift_g = lift_r = h_ / 2 + 0.012 + pinch_mcp
        dg = tp_g + np.array([0, 0, lift_g]) - mid[g]
        dr = pl_g + np.array([0, 0, lift_r]) - mid[r_]
        for f in range(F):
            if f < g:
                loc[f], yw[f], pitch[f] = tp, yaw[g], slope
            elif f <= r_:
                u = (f - g) / max(1, r_ - g)
                loc[f] = mid[f] + dg + (dr - dg) * u + fwd[f] * (d_ / 2 - gi) - np.array([0, 0, lift_g + (lift_r - lift_g) * u])
                yw[f] = yaw[f]
                pitch[f] = slope * (1 - _smooth((f - g) / max(1, lf - g)))
                state[f] = "hands"
            else:
                tb = (f - r_) / fps - 0.3  # the placement belt starts once the hands are 6 cm off (light curtain)
                x = 0.0 if tb <= 0 else (station["belt_speed"] * (tb - 0.125) if tb > 0.25 else
                                         station["belt_speed"] * tb * tb / 0.5)
                loc[f] = belt_path(station, pl_, x)
                yw[f] = yaw[r_]
                state[f] = "belt"
        if pinch:  # straight up off the rollers first (the hooked fingertips are down a roller gap):
            # no sideways move until it has risen 3 cm (the take's lift slid it 5 cm down the slope at roller height)
            z0_, xy0_ = loc[g][2], loc[g][:2].copy()
            for f in range(g, r_ + 1):
                s_ = _smooth((loc[f][2] - z0_ - 0.005) / 0.03)
                loc[f][:2] = xy0_ + (loc[f][:2] - xy0_) * s_
        Hw0 = sol["Hw"]
        pel, sp2 = Hw0[:, rig["bi"]["Bip01 Pelvis"]], Hw0[:, rig["bi"]["Bip01 Spine2"]]
        for f in range(g, r_ + 1):
            u = np.clip((loc[f][2] - pel[f][2]) / max(1e-3, sp2[f][2] - pel[f][2]), 0, 1)
            spine = pel[f] + (sp2[f] - pel[f]) * u
            fv = fwd[f]
            rear = loc[f] - fv * (d_ / 2)
            need = station.get("trunk_clear", 0.21) - float(np.dot((rear - spine)[:2], fv[:2]))
            if need > 0:  # ramps in from the grasp to the lift (no jump off the table)
                loc[f] = loc[f] + fv * need * _smooth((f - g) / max(1, lf - g))
        # gap holds: the carried carton rises (bottom >= hold_min_bottom, ramped 0.3 s) over the cartons passing on the
        # belt below while the worker waits for a gap
        for sg in segs:
            if sg["kind"] != "hold" or sg.get("n") != n:
                continue
            h0, h1 = int(math.ceil(sg["out0"] * fps)), int(sg["out1"] * fps)
            for f in range(max(g, h0 - 3), min(r_, h1 + 4)):
                ramp = _smooth(min((f - (h0 - 3)) / 3.0, (h1 + 3 - f) / 3.0, 1.0))
                need = station.get("hold_min_bottom", 1.27) - (loc[f][2] - h_ / 2)
                if need > 0:
                    loc[f][2] += need * ramp
        if "induct_start" in station:  # the trunk clearance / gap holds may have carried it off the zone: back in,
            # ramped from the lift to the release (the hands follow: sockets come from loc). Hub run: 1 of 21 at 25 cm
            S_, d2 = np.array(station["induct_start"]), np.array(station["induct_dir"])
            n2 = np.array([-d2[1], d2[0]])
            ang = yaw[r_] - math.atan2(d2[1], d2[0])
            ea = 0.5 * (abs(w_ * math.cos(ang)) + abs(d_ * math.sin(ang)))
            el = 0.5 * (abs(w_ * math.sin(ang)) + abs(d_ * math.cos(ang)))
            hw = station.get("induct_half_w", 0.25) - 0.07
            al, lt = _induct_zone(loc[r_][:2] - S_, S_, d2, n2, ea, el, hw, yaw[r_], w_, d_)
            corr = np.zeros(3)
            corr[:2] = S_ + d2 * (al + 0.12) + n2 * lt - loc[r_][:2]
            if np.linalg.norm(corr) > 1e-4:
                for f in range(lf, r_ + 1):
                    loc[f] = loc[f] + corr * _smooth((f - lf) / max(1, r_ - lf))
            tracks_corr = float(np.linalg.norm(corr))
        else:
            tracks_corr = 0.0
        # held, its footprint never dips into a station surface (the table's end stop: lifted off the rollers it
        # was carried 1-3 cm through the 4 cm stop lip towards him; hub run 4, CAM_01): raised to the surface top,
        # ramped over 3 frames each side (the hands follow: sockets come from loc). At a set-down its bottom is at the
        # belt top already, so nothing changes there
        surfg = station.get("surfaces", ())
        surf_lift_m = 0.0  # (report: how far its carry path was raised)
        if surfg:
            needg = np.zeros(F)
            for f in range(g, r_ + 1):
                csg, sng = math.cos(yw[f]), math.sin(yw[f])
                axg = (np.array([csg, sng]), np.array([-sng, csg]))
                hxg = (w_ / 2, d_ / 2)
                botg = loc[f][2] - h_ / 2
                for (x0, y0, x1, y1, zt) in surfg:
                    if botg >= zt or botg < zt - 0.25:
                        continue
                    ctrg, extg = np.array([(x0 + x1) / 2, (y0 + y1) / 2]), np.array([(x1 - x0) / 2, (y1 - y0) / 2])
                    dvg = loc[f][:2] - ctrg
                    sepg = any(abs(dvg[i]) > extg[i] + abs(axg[0][i]) * hxg[0] + abs(axg[1][i]) * hxg[1] for i in (0, 1)) \
                        or any(abs(dvg @ axg[j]) > hxg[j] + abs(extg[0] * axg[j][0]) + abs(extg[1] * axg[j][1])
                               for j in (0, 1))  # (separating axis: the box's x / y, the parcel's own axes)
                    if not sepg:
                        needg[f] = max(needg[f], zt - botg)
            if needg.any():
                needg_r = needg.copy()
                for f in np.nonzero(needg)[0]:
                    for kg in range(1, 4):
                        for f2 in (f - kg, f + kg):
                            if g <= f2 <= r_:
                                needg_r[f2] = max(needg_r[f2], needg[f] * (1 - kg / 4))
                loc[g:r_ + 1, 2] += needg_r[g:r_ + 1]
                surf_lift_m = float(needg.max())
        # out of a wall slot (dock, review 016b #4): from the grasp until it is out of its slot by its own depth + 3 cm
        # it moves only straight out towards him - not sideways into the next column, not down into the carton below
        # (the captured hands swung it through both: hub collision run, 31 Oct); then it eases onto the hands' path
        sp_ = station.get("slot_pull")
        if sp_ is not None:
            n_o = np.array([*sp_["n"], 0.0])
            n_o /= np.linalg.norm(n_o)
            ax_x = np.array([math.cos(tyaw), math.sin(tyaw), 0.0])
            ax_y = np.array([-math.sin(tyaw), math.cos(tyaw), 0.0])
            dep = w_ * abs(float(ax_x @ n_o)) + d_ * abs(float(ax_y @ n_o))  # its extent along n
            need_out = dep + 0.03
            clear_f = None
            for f in range(g, r_ + 1):
                out_ = float(np.dot(loc[f] - tp, n_o))
                if out_ >= need_out:
                    clear_f = f
                    break
                q_ = tp + n_o * max(0.0, out_)
                q_[2] = max(loc[f][2], tp[2])
                loc[f] = q_
            if clear_f is not None:
                n_b = max(2, int(round(0.3 * fps)))
                for f in range(clear_f, min(r_ + 1, clear_f + n_b)):
                    u = float(_smooth((f - clear_f) / n_b))
                    out_ = float(np.dot(loc[f] - tp, n_o))
                    q_ = tp + n_o * max(0.0, out_)
                    q_[2] = max(loc[f][2], tp[2])
                    loc[f] = q_ + (loc[f] - q_) * u
        # held over a belt (belt A, the induct belt) the box never dips into it: the captured hands lowered it 2-4.5 cm
        # below the belt top in the last second before the set-down (hub collision run, 31 Oct). The raise each frame
        # needs (its footprint over a belt's rectangle, bottom >= top + 3 mm) is spread over +-3 frames, never below the
        # need; the sloped table (lower than the belt) is not a belt
        bt_ = station.get("belt_top", 1.0)
        belts_ = [sf for sf in station.get("surfaces", ()) if sf[4] >= bt_ - 0.005]
        need_ = np.zeros(F)
        ext_ = 0.5 * max(w_, d_)
        for f in range(g, r_ + 1):
            for (x0, y0, x1, y1, zt) in belts_:
                if x0 - ext_ <= loc[f][0] <= x1 + ext_ and y0 - ext_ <= loc[f][1] <= y1 + ext_:
                    need_[f] = max(need_[f], zt + (0.028 if pinch else 0.003) - (loc[f][2] - h_ / 2))
            for (gs, gd, a0, a1, o0, o1, gt) in station.get("guides", ()):  # over a side guide: clear of its top
                gd_ = np.array(gd, float)
                gn_ = np.array([-gd_[1], gd_[0]])
                gc_ = np.array(gs, float) + gd_ * (a0 + a1) / 2 + gn_ * (o0 + o1) / 2
                ga_, gh_ = (gd_, gn_), ((a1 - a0) / 2, abs(o1 - o0) / 2)
                pa_ = (np.array([math.cos(yw[f]), math.sin(yw[f])]), np.array([-math.sin(yw[f]), math.cos(yw[f])]))
                ph_ = (w_ / 2, d_ / 2)
                dv_ = loc[f][:2] - gc_
                sep_ = any(abs(dv_ @ ax_) > sum(h * abs(ax_ @ a) for h, a in zip(ph_, pa_)) + sum(h * abs(ax_ @ a) for h, a in zip(gh_, ga_))
                           for ax_ in pa_ + ga_)  # (separating axis: both rectangles' own axes)
                if not sep_:
                    need_[f] = max(need_[f], gt + 0.005 - (loc[f][2] - h_ / 2))
        need_ = np.maximum(need_, 0.0)  # (far pinch: + 2.5 cm, its hooked fingertips are under it)
        if need_.any():
            k_ = np.exp(-0.5 * (np.arange(-3, 4) / 1.2) ** 2)
            pad_ = np.pad(need_, 3)  # weighted max over +-3 frames (31 Oct: a convolution summed them, over-lifting)
            up_ = np.max([pad_[3 + j:3 + j + F] * k_[3 + j] for j in range(-3, 4)], axis=0)
            up_[r_] = need_[r_]
            for f in range(g, r_ + 1):
                loc[f][2] += up_[f]
            tracks_dip = float(need_.max())
        else:
            tracks_dip = 0.0
        # last: the corrections above (trunk clearance, gap holds, zone, the far pinch's straight-up rule, belt / guide
        # clearance) each ramp in, together they still made a carton (and the hands IK'd to it) jump 0.29 m in a
        # frame (a pinch, run 9): its held path, across, no faster than 1.2 m/s per axis
        tg_ = np.arange(g, r_ + 1) / fps
        for i_ in (0, 1):
            loc[g:r_ + 1, i_] = _rate_limit(loc[g:r_ + 1, i_], tg_, 1.2)
        pl_ = loc[r_].copy()  # set down where it was released (on the belt, clear of the body)
        pl_[2] = station["belt_top"] + h_ / 2
        tracks[n] = dict(loc=loc, yaw=yw, pitch=pitch, state=state, grasp=g, release=r_, dims=(w_, d_, h_), one=one,
                         pinch=pinch, pinch_hands=pinch_h, lift=lf, fwd_sign=(-1.0 if station.get("flip_fwd") else 1.0),
                         pinch_xo=xo_h, pinch_gi=gi, pinch_lift=lift_g,
                         obj_yaw_off=obj_off, zone_corr_m=round(tracks_corr, 3), surface_lift_m=round(surf_lift_m, 3), xo=xo, belt_dip_mm=round(tracks_dip * 1000, 1))
        # hand targets: side-face sockets while held. Approach: blend from the mocap path to a point 6 cm off each face,
        # then in along the face normal over the last 0.2 s. Release: out 6 cm along the normal + up 4 cm over 0.2 s
        # (the belt waits for that: light curtain), then back to the mocap path over 0.4 s.
        n_in, n_out1, n_out2 = max(2, int(round(0.8 * fps))), max(1, int(round(0.2 * fps))), max(2, int(round(0.4 * fps)))
        n_keep = max(1, int(round(0.3 * fps)))  # hold the retracted hands while the carton leaves
        n_fin = max(1, int(round(0.2 * fps)))

        def sockets(ff):
            X = np.array([math.cos(yw[ff]), math.sin(yw[ff]), 0.0])
            u_ = (ff - g) / max(1, r_ - g)
            gp = loc[ff] - fwd[ff] * (d_ / 2 - gi) + np.array([0, 0, lift_g + (lift_r - lift_g) * u_])
            if ff == g:
                gp = tp - fwd[g] * (d_ / 2 - gi) + np.array([0, 0, lift_g])
            so = station.get("palm_off", 0.04) + 0.012 * _smooth((ff - (r_ - 2)) / 2.0)  # opens before the release (fingers are un-curled flat)
            if pinch:  # each pinching hand past the far edge at its own place along it (from above, up after)
                up_ = np.array([0.0, 0.0, 1.0])
                return ({x_: gp + X * xo_h[x_] for x_ in pinch_h}, {x_: up_ for x_ in pinch_h})
            if one:  # the right palm on the top, right of the middle (it is set down off the hand's own side)
                up_ = np.array([0.0, 0.0, 1.0])
                return ({"R": gp + X * xo + up_ * 0.012 * _smooth((ff - (r_ - 2)) / 2.0)}, {"R": up_})
            return {"L": gp - X * (w_ / 2 + so), "R": gp + X * (w_ / 2 + so)}, {"L": -X, "R": X}
        sg_, og_ = sockets(g)
        sr_, or_ = sockets(r_)

        def rest_pt(f, x):
            """Relaxed after a release (review 018 #2: a hand held in front of the hips read as holding the stomach):
            hanging beside the thigh under its shoulder, elbow a little bent; slid in towards the pelvis if that is
            over / into a belt or table."""
            Hw_ = sol["Hw"]
            lv = Hw_[f, rig["bi"]["Bip01 L Thigh"]] - Hw_[f, rig["bi"]["Bip01 R Thigh"]]
            lv[2] = 0
            lv /= np.linalg.norm(lv) + 1e-9
            fw = np.array([lv[1], -lv[0], 0.0])
            # 018b: all the way down along the thigh, elbow nearly straight (not a hand at the hip)
            q_ = Hw_[f, rig["bi"][f"Bip01 {x} UpperArm"]] + lv * (0.02 if x == "L" else -0.02) + fw * 0.01                 + np.array([0, 0, -0.66])
            pel_ = Hw_[f, rig["bi"]["Bip01 Pelvis"]]
            for _ in range(30):
                if not [1 for (x0, y0, x1, y1, zt) in station.get("surfaces", ())  # (hand + fingers hang ~0.2 m)
                        if x0 - 0.08 <= q_[0] <= x1 + 0.08 and y0 - 0.08 <= q_[1] <= y1 + 0.08 and q_[2] > zt - 0.40]:
                    break
                v_ = pel_[:2] - q_[:2]
                q_[:2] += v_ / (np.linalg.norm(v_) + 1e-9) * 0.01
            return q_
        def side_pt(f):
            """The left hand hanging beside the thigh: under the shoulder, elbow a little bent."""
            Hw_ = sol["Hw"]
            lv = Hw_[f, rig["bi"]["Bip01 L Thigh"]] - Hw_[f, rig["bi"]["Bip01 R Thigh"]]
            lv[2] = 0
            lv /= np.linalg.norm(lv) + 1e-9
            fw = np.array([lv[1], -lv[0], 0.0])
            q_ = Hw_[f, rig["bi"]["Bip01 L UpperArm"]] + lv * 0.03 + fw * 0.03 + np.array([0, 0, -0.60])
            # with the shoulder over the table's near rail (leaning to the pick), the free hand rests on the rail
            # (hanging, the forearm went through it: QA); blended over 12 cm of distance
            b_, br_ = 0.0, None
            rl = station.get("brace_rail")
            if rl:
                yb = float(np.clip(q_[1], rl["y0"] + 0.08, rl["y1"] - 0.08))
                br_ = np.array([rl["x"], yb, (rl["z_a"] if yb < rl["ym"] else rl["z_b"]) + station.get("palm_off_top", 0.042)])
                b_ = 1.0 - _smooth((float(np.linalg.norm((q_ - br_)[:2])) - 0.06) / 0.12)
            # never over / into a table or belt (the roller table is on his left): slid in towards the pelvis
            pel_ = Hw_[f, rig["bi"]["Bip01 Pelvis"]]
            for _ in range(30):
                inside = [1 for (x0, y0, x1, y1, zt) in station.get("surfaces", ())
                          if x0 - 0.08 <= q_[0] <= x1 + 0.08 and y0 - 0.08 <= q_[1] <= y1 + 0.08 and q_[2] > zt - 0.25]
                if not inside:
                    break
                v_ = pel_[:2] - q_[:2]
                q_[:2] += v_ / (np.linalg.norm(v_) + 1e-9) * 0.01
            if br_ is None:
                return q_
            if station.get("free_hand", "back") == "back":  # the free arm swings back behind the hip (QA: 8 rows
                # over 1 cm vs 50 with the palm on the 4 cm rail, 42 hanging straight)
                return q_ - fw * 0.20 * b_ + np.array([0, 0, 0.04]) * b_
            brace_b[f] = max(brace_b[f], b_)
            return q_ + (br_ - q_) * b_
        bk = sol["Hw"][r_, rig["bi"]["Bip01 Pelvis"]] - pl_  # retract towards the pelvis (horizontal) but never
        bk[2] = 0  # along the grip axis: that would sweep one hand across the carton
        Xr = np.array([math.cos(yw[r_]), math.sin(yw[r_]), 0.0])
        bk -= np.dot(bk, Xr) * Xr
        bk /= np.linalg.norm(bk) + 1e-9
        for f in range(max(0, g - n_in), min(F, r_ + n_out1 + n_keep + n_out2 + 1)):
            if one:  # left hand: from the mocap path down beside the thigh, and back after the release
                w = min(_smooth((f - (g - n_in)) / max(1, n_in - n_fin)),
                        1.0 - _smooth((f - r_ - n_out1 - n_keep) / n_out2) if f > r_ + n_out1 + n_keep else 1.0)
                base = tgt["L"][f].copy()
                tgt["L"][f] = base + w * (side_pt(f) - base)
                wgt[f] = max(wgt[f], w)
                wo_h["L"][f] = max(wo_h["L"][f], w)
                flat_h["L"][f] = max(flat_h["L"][f], w * brace_b[f])  # flat on the rail, relaxed when hanging
                one_f[f] = True
            for i, x in enumerate(("L", "R")):
                if one and x == "L":
                    continue
                if f < g - n_fin:  # current target (mocap, or the last release's retract) -> 6 cm off the face
                    w = _smooth((f - (g - n_in)) / max(1, n_in - n_fin))
                    base = tgt[x][f].copy()
                    tgt[x][f] = base + w * (sg_[x] + og_[x] * 0.06 + np.array([0, 0, 0.12]) - base)
                elif f < g:  # in along the normal and down over the last 0.2 s
                    u = (g - f) / n_fin
                    w = 1.0
                    tgt[x][f] = sg_[x] + (og_[x] * 0.06 + np.array([0, 0, 0.12])) * u
                elif f <= r_:
                    w = 1.0
                    tgt[x][f] = sockets(f)[0][x]
                elif f <= r_ + n_out1:  # off the face: out 6 cm, back, up (the carton leaves along the belt)
                    u = _smooth((f - r_) / n_out1)
                    w, wo = 1.0, 1.0
                    tgt[x][f] = sr_[x] + (or_[x] * 0.06 + bk * 0.18 + np.array([0, 0, 0.10])) * u
                elif f <= r_ + n_out1 + n_keep:  # review 016 #1: to the body within 0.3 s, palms turning in
                    u = _smooth((f - r_ - n_out1) / n_keep)
                    w, wo = 1.0, 1.0
                    # back towards the body first, then down (straight down to the thigh, the fingers went through
                    # the induct belt's near end); the fingers turn down only once the hand is coming down
                    rest_b[x][f] = max(rest_b[x][f], _smooth((u - 0.5) / 0.5))
                    off = sr_[x] + or_[x] * 0.06 + bk * 0.18 + np.array([0, 0, 0.10])
                    rp_ = rest_pt(f, x)
                    uxy, uz = _smooth(u / 0.6), _smooth((u - 0.4) / 0.6)
                    tgt[x][f] = np.array([off[0] + (rp_[0] - off[0]) * uxy, off[1] + (rp_[1] - off[1]) * uxy,
                                          off[2] + (rp_[2] - off[2]) * uz])
                else:  # back to the mocap path
                    w = 1 - _smooth((f - r_ - n_out1 - n_keep) / n_out2)
                    wo = w
                    rest_b[x][f] = max(rest_b[x][f], 1.0)
                    tgt[x][f] = pm0[f, i] + w * (rest_pt(f, x) - pm0[f, i])
                if f < g or f <= r_:
                    wo = w
                wgt[f] = max(wgt[f], w)
                wori[f] = max(wori[f], wo)
                wo_h[x][f] = max(wo_h[x][f], wo)
                flat_h[x][f] = max(flat_h[x][f], wo * (1.0 - rest_b[x][f]))  # relaxed curl once at rest
        # light curtain: the placement belt starts at the first delay (0.3-1.5 s) for which the moving carton keeps
        # >= 9 cm (hand + fingers) from both hand targets over the next 1.2 s
        Rz = np.array([[math.cos(yw[r_]), -math.sin(yw[r_]), 0], [math.sin(yw[r_]), math.cos(yw[r_]), 0], [0, 0, 1]])
        hb = np.array([w_, d_, h_]) / 2 + station.get("curtain_clear", 0.10)  # hand + fingers (0.15 fails more checks: the 1.5 s fallback is worse)
        bdir = np.array([station.get("belt_dir", 1.0), 0, 0])
        best = 1.5
        # a simulation that already timed the belt start (flow.py: station "curtain_s") gets that delay; whether the
        # hands were clear then is recorded, not hidden (bench: 0.3 s in 36 of 37 set-downs)
        fixed = station.get("curtain_s")
        for d0 in ([fixed] if fixed is not None else np.arange(0.3, 1.51, 0.1)):
            ok = True
            for f in range(r_ + 1, min(F, r_ + int(1.2 * fps) + 1)):
                tb = (f - r_) / fps - d0
                if tb <= 0:
                    continue  # still standing: the hands only have to be clear of its path once it moves
                xx = station["belt_speed"] * (tb - 0.125) if tb > 0.25 else station["belt_speed"] * tb * tb / 0.5
                c_ = belt_path(station, pl_, xx)
                for x in (("R",) if one else ("L", "R")):
                    q_ = Rz.T @ (tgt[x][f] - c_)
                    if np.all(np.abs(q_) < hb):
                        ok = False
                        break
                if not ok:
                    break
            if ok or fixed is not None:
                best = float(d0)
                break
        for f in range(r_ + 1, F):
            tb = (f - r_) / fps - best
            xx = 0.0 if tb <= 0 else (station["belt_speed"] * (tb - 0.125) if tb > 0.25 else
                                      station["belt_speed"] * tb * tb / 0.5)
            loc[f] = belt_path(station, pl_, xx)
        tracks[n]["belt_wait_s"] = round(best, 2)
        tracks[n]["curtain_clear"] = bool(ok)
        tracks[n]["retract_end"] = r_ + n_out1 + n_keep
    wik = (wgt > 1e-6).astype(float)
    arrive = {}  # frame each carton reaches the end stop: the previous one's lift + the refill (diverter + roll)
    for n in tracks:
        if n - 1 in lift:
            arrive[n] = lift[n - 1] + int(round(station.get("divert_s", station.get("refill_s", 0.0)) * fps))
    # no hand path through a carton that is not in the hands (waiting on the table, standing / leaving on the belt)
    # (off for a stacked wall: the carton under the target would push the hands off it):
    # lifted 8 cm over it
    for n, tr in (tracks.items() if station.get("lift_rule", True) else ()):
        w_, d_, h_ = tr["dims"]
        hb = np.array([w_, d_, h_]) / 2 + 0.08
        for f in range(F):
            if tr["state"][f] == "hands" or tr["release"] < f <= tr.get("retract_end", -1):
                continue  # in the hands, or just let go (the retract moves the hands off it)
            if tr["state"][f] == "table" and f < arrive.get(n, 0):
                continue  # not at the stop yet (on the feed / rolling down the table)
            c_, yz = tr["loc"][f], tr["yaw"][f]
            Rz = np.array([[math.cos(yz), -math.sin(yz), 0], [math.sin(yz), math.cos(yz), 0], [0, 0, 1]])
            for x in ("L", "R"):
                q_ = Rz.T @ (tgt[x][f] - c_)
                if np.all(np.abs(q_) < hb):
                    tgt[x][f][2] = max(tgt[x][f][2], c_[2] + h_ / 2 + 0.08)
                    wik[f] = 1.0
    holding = np.zeros(F, bool)
    n_dn, n_up = max(1, int(round(0.2 * fps))) + 1, max(1, int(round(0.2 * fps)))
    for tr in tracks.values():  # (+ the last 0.2 s down onto it and the first 0.2 s off it: the sockets decide)
        holding[max(0, tr["grasp"] - n_dn):tr["release"] + n_up + 1] = True
    # palm targets over a table / belt (+ 8 cm round it: the hand and fingers, the end stop just past the table's low
    # end) stay 13 cm over it (a hanging hand's fingertips; 4 cm / 10 cm let the take's own approach and way-back paths
    # put fingers in the end stop and the induct belt: line A bench rows, 31 Oct)
    for x_i, x in enumerate(("L", "R")):
        for f in range(F):
            if holding[f] or (x == "L" and brace_b[f] > 0):
                continue  # on the carton: the sockets decide (the free hand on the rail: its own target)
            p_ = tgt[x][f]
            for (x0, y0, x1, y1, zt) in station.get("surfaces", ()):
                near = x0 - 0.08 <= p_[0] <= x1 + 0.08 and y0 - 0.08 <= p_[1] <= y1 + 0.08 and p_[2] > zt - 0.06
                if near and p_[2] < zt + 0.13:  # (well below its top: a hand hanging beside / under it, left -
                    # raised, it went up through the belt's edge)
                    p_[2] = zt + 0.13  # a hand's length above the surface (the fingers may point down)
                    wik[f] = 1.0
    bi = rig["bi"]
    # reach-driven forward lean: where a hand target is beyond the arm (+ palm), pivot the upper body forward about
    # Spine1's head (the thighs hang off Spine, so Spine itself stays), smoothed in time; the real worker leans in
    Hw = sol["Hw"]
    reach = {}
    for x in ("L", "R"):
        ua, fa, hd = (bi[f"Bip01 {x} {n}"] for n in ("UpperArm", "Forearm", "Hand"))
        reach[x] = float(np.linalg.norm(Hw[0, fa] - Hw[0, ua]) + np.linalg.norm(Hw[0, hd] - Hw[0, fa])
                         + np.linalg.norm(palm_pts(sol, rig)[0, 0 if x == "L" else 1] - Hw[0, hd]))
    sp1 = bi["Bip01 Spine1"]
    # 014d #3 un-stoop: the lab tables were lower than our 88 cm table end / 1.0 m belt; where the hand targets sit
    # above the mocap hands, straighten the upper body (pivot back about Spine1's head) instead of bending the arms
    # up out of a deep stoop; capped at 30 deg, smoothed in time
    pmc = palm_pts(sol, rig)
    ub = np.zeros(F)
    pick_win = np.zeros(F, bool)  # only around the pick (approach .. lift + 0.5 s): at the belt the reach-lean rules
    for n, tr in tracks.items():
        pick_win[max(0, tr["grasp"] - int(0.8 * fps)):min(F, lift.get(n, tr["grasp"]) + int(0.5 * fps))] = True
    for f in range(F):
        if wik[f] <= 0 or not pick_win[f]:
            continue
        dzn = (tgt["R"][f][2] - pmc[f, 1, 2]) if one_f[f] else \
            0.5 * ((tgt["L"][f][2] - pmc[f, 0, 2]) + (tgt["R"][f][2] - pmc[f, 1, 2]))
        if dzn > 0.03:
            lever = max(0.2, Hw[f, bi["Bip01 L UpperArm"], 2] - Hw[f, sp1, 2])
            ub[f] = min(math.radians(30), (dzn - 0.03) / lever)
    if ub.any():
        k_ = np.exp(-0.5 * (np.arange(-5, 6) / 2.0) ** 2)
        ub = np.convolve(ub, k_ / k_.sum(), mode="same")
        lv = Hw[:, bi["Bip01 L Thigh"]] - Hw[:, bi["Bip01 R Thigh"]]
        lv[:, 2] = 0
        lv /= np.linalg.norm(lv, axis=1, keepdims=True)
        k = ub > 1e-4
        Rw = _rotexp(-lv[k] * ub[k, None])  # backwards
        Ra = np.einsum("ji,fjk,kl->fil", rig["MR"], Rw, rig["MR"])
        piv = Hw[k, sp1].copy()
        ids = [sp1] + [i for i in range(len(rig["par"])) if _is_desc(rig["par"], i, sp1)]
        for i in ids:
            sol["A"][k, i] = Ra @ sol["A"][k, i]
            Hw[k, i] = piv + np.einsum("fij,fj->fi", Rw, Hw[k, i] - piv)
        p_ = rig["par"][sp1]
        sol["L"][k, sp1] = np.einsum("ij,fjk,fkl->fil", rig["rest"][sp1].T @ rig["rest"][p_],
                                     np.transpose(sol["A"][k, p_], (0, 2, 1)), sol["A"][k, sp1])
        sol["unstoop_deg_max"] = float(np.degrees(ub.max()))
    th = np.zeros(F)
    for f in range(F):
        if wik[f] <= 0 or (not station.get("lean_at_pick", True) and pick_win[f]):
            continue  # at a wall the keep-out sets the reach: leaning in there puts the head into the wall
        need = max(np.linalg.norm(tgt[x][f] - Hw[f, bi[f"Bip01 {x} UpperArm"]]) - 0.96 * reach[x] for x in ("L", "R"))
        if need > 0:
            lever = max(0.2, Hw[f, bi["Bip01 L UpperArm"], 2] - Hw[f, sp1, 2])
            th[f] = min(math.radians(28), need / lever * 1.15)
    if th.any():
        k_ = np.exp(-0.5 * (np.arange(-4, 5) / 1.5) ** 2)
        th = np.maximum(np.convolve(th, k_ / k_.sum(), mode="same"), th)  # spread in time, never below the need
        lv = Hw[:, bi["Bip01 L Thigh"]] - Hw[:, bi["Bip01 R Thigh"]]
        lv[:, 2] = 0
        lv /= np.linalg.norm(lv, axis=1, keepdims=True)
        k = th > 1e-4
        Rw = _rotexp(lv[k] * th[k, None])
        MR = rig["MR"]
        Ra = np.einsum("ji,fjk,kl->fil", MR, Rw, MR)
        piv = Hw[k, sp1].copy()
        ids = [sp1] + [i for i in range(len(rig["par"])) if _is_desc(rig["par"], i, sp1)]
        for i in ids:
            sol["A"][k, i] = Ra @ sol["A"][k, i]
            Hw[k, i] = piv + np.einsum("fij,fj->fi", Rw, Hw[k, i] - piv)
        p_ = rig["par"][sp1]
        sol["L"][k, sp1] = np.einsum("ij,fjk,fkl->fil", rig["rest"][sp1].T @ rig["rest"][p_],
                                     np.transpose(sol["A"][k, p_], (0, 2, 1)), sol["A"][k, sp1])
        sol["lean_deg_max"] = float(np.degrees(th.max()))
    # review 015 #2: at the set-down the trunk folds no more than 38 deg from vertical (pivot back about Spine1 by the
    # excess) and the head comes up to 12 deg (eyes on the belt, not the floor)
    place_win = np.zeros(F)
    for n, tr in tracks.items():
        a0, a1 = lift.get(n, tr["grasp"]) + int(0.5 * fps), tr["release"] + int(0.3 * fps)
        for f in range(max(0, a0 - 3), min(F, a1 + 4)):
            place_win[f] = max(place_win[f], _smooth(min((f - (a0 - 3)) / 3.0, (a1 + 3 - f) / 3.0, 1.0)))
    if place_win.any() or station.get("flex_cap_pick"):
        pel, s2 = Hw[:, bi["Bip01 Pelvis"]], Hw[:, bi["Bip01 Spine2"]]
        v = s2 - pel
        flex = np.degrees(np.arccos(np.clip(v[:, 2] / np.linalg.norm(v, axis=1), -1, 1)))
        back = np.radians(np.maximum(0.0, flex - 38.0)) * place_win
        if station.get("flex_cap_pick"):  # at a wall: no folding over the column into the rows behind
            pw_ = np.zeros(F)
            for n, tr in tracks.items():
                a0, a1 = tr["grasp"] - int(0.8 * fps), lift.get(n, tr["grasp"]) + int(0.5 * fps)
                for f in range(max(0, a0 - 3), min(F, a1 + 4)):
                    pw_[f] = max(pw_[f], _smooth(min((f - (a0 - 3)) / 3.0, (a1 + 3 - f) / 3.0, 1.0)))
            back = np.maximum(back, np.radians(np.maximum(0.0, flex - station["flex_cap_pick"])) * pw_)
        _pivot(sol, rig, "Bip01 Spine1", back, backward=True)
        neck_up = np.radians(12.0) * place_win
        if station.get("flex_cap_pick"):
            neck_up = np.maximum(neck_up, np.radians(station.get("neck_up_pick", 15.0)) * pw_)
        # review 016 #2: eyes >= 25 cm above the carton top while setting it down (the trunk cap alone let the neck drop)
        hb_ = bi["Bip01 Head"]
        for n, tr in tracks.items():
            h2 = tr["dims"][2]
            for f in range(max(0, tr["grasp"]), min(F, tr["release"] + 1)):
                if place_win[f] <= 0:
                    continue
                gap = Hw[f, hb_][2] + 0.08 - (tr["loc"][f][2] + h2 / 2)
                if gap < 0.25:
                    neck_up[f] = max(neck_up[f], min(math.radians(35), (0.25 - gap) / 0.12) * place_win[f])
        _pivot(sol, rig, "Bip01 Neck", neck_up, backward=True)
        sol["flex_set_down_deg_max"] = float(np.max(np.where(place_win > 0.5, np.degrees(np.arccos(np.clip(
            (Hw[:, bi["Bip01 Spine2"], 2] - Hw[:, bi["Bip01 Pelvis"], 2]) / np.linalg.norm(
                Hw[:, bi["Bip01 Spine2"]] - Hw[:, bi["Bip01 Pelvis"]], axis=1), -1, 1))), 0)))
    # hands flat on the side faces: palm normal -> the face normal (towards the carton), fingers along the face,
    # forward and 20 deg down (fingertips stay above the support); blended by the IK weight
    for x, sgn in (("L", 1.0), ("R", -1.0)):
        hd = bi[f"Bip01 {x} Hand"]
        Hw = sol["Hw"]
        h = Hw[:, hd]
        # palm normal: in the shared T-pose every avatar's palms face down (M1), so take that direction in the hand
        # bone's own frame and carry it through this frame's hand rotation (finger-base cross products flipped on
        # some avatars and laid the palms on the carton's top)
        MRm = rig["MR"]
        n_loc = rig["AT"][hd].T @ (MRm.T @ np.array([0.0, 0.0, -1.0]))
        n_ = np.einsum("ij,fjk,k->fi", MRm, sol["A"][:, hd], n_loc)
        n_ /= np.linalg.norm(n_, axis=1, keepdims=True)
        fd = Hw[:, bi[f"Bip01 {x} Finger2"]] - h
        fd /= np.linalg.norm(fd, axis=1, keepdims=True)
        nd = np.zeros_like(n_)
        fdd = np.zeros_like(fd)
        for n, tr in tracks.items():
            g, r_ = tr["grasp"], tr["release"]
            f0_, f1_ = max(0, g - int(round(0.5 * fps))), min(F, r_ + int(round(0.6 * fps)) + 1)
            if tr.get("one") and x == "L":  # hanging: palm to the thigh, fingers down (the whole blend window)
                f0_, f1_ = max(0, g - int(round(0.8 * fps))), min(F, r_ + int(round(0.9 * fps)) + 1)
            for f in range(f0_, f1_):
                ff = min(max(f, g), r_)
                X = np.array([math.cos(tr["yaw"][ff]), math.sin(tr["yaw"][ff]), 0.0])
                Yf = np.array([-X[1], X[0], 0.0])
                if tr.get("pinch") and x in tr["pinch_hands"]:  # far pinch: palm towards him past the far edge,
                    nd[f], fdd[f] = -Yf * tr["fwd_sign"], np.array([0.0, 0.0, -1.0])  # fingers down
                    continue
                if tr.get("one"):
                    if x == "R":  # palm down on the top, fingers forward over it
                        nd[f], fdd[f] = np.array([0.0, 0.0, -1.0]), Yf
                    else:
                        lv_ = Hw[f, bi["Bip01 L Thigh"]] - Hw[f, bi["Bip01 R Thigh"]]
                        lv_[2] = 0
                        lv_ /= np.linalg.norm(lv_) + 1e-9
                        b_ = brace_b[f]  # hanging (palm to the thigh, fingers down) .. on the rail (palm down, forward)
                        n2 = -lv_ * (1 - b_) + np.array([0.0, 0.0, -1.0]) * b_
                        d2 = np.array([0.0, 0.0, -1.0]) * (1 - b_) + np.array([lv_[1], -lv_[0], 0.0]) * b_
                        nd[f], fdd[f] = n2 / (np.linalg.norm(n2) + 1e-9), d2 / (np.linalg.norm(d2) + 1e-9)
                    continue
                nd[f] = sgn * X
                dn = 0.0  # level: tilted down, the little finger reached under the end stop / belt top
                fdd[f] = Yf * math.cos(dn) - np.array([0, 0, math.sin(dn)])
        for f in np.nonzero(rest_b[x] > 0)[0]:  # after a release: palm to the thigh, fingers down
            lv_ = Hw[f, bi["Bip01 L Thigh"]] - Hw[f, bi["Bip01 R Thigh"]]
            lv_[2] = 0
            lv_ /= np.linalg.norm(lv_) + 1e-9
            rb = rest_b[x][f]
            n2 = (nd[f] if np.linalg.norm(nd[f]) > 0.5 else 0.0) * (1 - rb) + (-lv_ if x == "L" else lv_) * rb
            d2 = (fdd[f] if np.linalg.norm(fdd[f]) > 0.5 else 0.0) * (1 - rb) + np.array([0.0, 0.0, -1.0]) * rb
            nd[f], fdd[f] = n2 / (np.linalg.norm(n2) + 1e-9), d2 / (np.linalg.norm(d2) + 1e-9)
        k = (wo_h[x] > 1e-6) & (np.linalg.norm(nd, axis=1) > 0.5)
        if not k.any():
            continue
        Fc = np.stack([fd, n_, np.cross(fd, n_)], 2)  # current frame (columns)
        fdd_o = fdd - np.sum(fdd * nd, 1)[:, None] * nd
        fdd_o /= np.linalg.norm(fdd_o, axis=1, keepdims=True) + 1e-12
        Fd = np.stack([fdd_o, nd, np.cross(fdd_o, nd)], 2)
        Rw = np.einsum("fij,fkj->fik", Fd[k], Fc[k])  # world rotation current -> desired
        Rw = _rotexp(_rotlog(Rw) * np.clip(wo_h[x][k], 0, 1)[:, None])
        MR = rig["MR"]
        Ra = np.einsum("ji,fjk,kl->fil", MR, Rw, MR)
        sol["A"][k, hd] = Ra @ sol["A"][k, hd]
        desc = [i for i in range(len(rig["par"])) if _is_desc(rig["par"], i, hd)]
        for i in desc:
            sol["A"][k, i] = Ra @ sol["A"][k, i]
            Hw[k, i] = h[k] + np.einsum("fij,fj->fi", Rw, Hw[k, i] - h[k])
        p = rig["par"][hd]
        sol["L"][k, hd] = np.einsum("ij,fjk,fkl->fil", rig["rest"][hd].T @ rig["rest"][p],
                                    np.transpose(sol["A"][k, p], (0, 2, 1)), sol["A"][k, hd])
    # fingers: from the relaxed curl towards the (straight) bind pose while the hands are on a parcel; then FK of
    # every finger chain, then the thumb swung into the palm plane (a flat thumb on the palm side crosses the face)
    for nm_, i in bi.items():
        if "Finger" in nm_ and nm_.split()[1] in ("L", "R"):
            fl = np.clip(flat_h[nm_.split()[1]], 0, 1)[:, None]
            sol["L"][:, i] = _rotexp((1 - fl) * I_log(rig["LT"][i])[None])
            sol.setdefault("keyed", set()).add(i)
    for x in ("L", "R"):
        fk_desc(sol, rig, bi[f"Bip01 {x} Hand"])
    # the bind pose still curls the fingers (up to ~5 cm at the tips, more on the female hands): turn each finger at
    # its knuckle so its tip comes back into the palm plane, so the palm itself can lie on the carton face
    k = wori > 1e-6
    if k.any():
        Hw = sol["Hw"]
        MRm = rig["MR"]
        for x in ("L", "R"):
            k = flat_h[x] > 1e-6
            if not k.any():
                continue
            hd_ = bi[f"Bip01 {x} Hand"]
            n_loc = rig["AT"][hd_].T @ (MRm.T @ np.array([0.0, 0.0, -1.0]))
            nf = np.einsum("ij,fjk,k->fi", MRm, sol["A"][k, hd_], n_loc)
            nf /= np.linalg.norm(nf, axis=1, keepdims=True)
            for f_ in (1, 2, 3, 4):
                b_, m_, l_ = (bi[f"Bip01 {x} Finger{f_}{s_}"] for s_ in ("", "1", "2"))
                tip = Hw[k, l_] + (Hw[k, l_] - Hw[k, m_]) * 0.9
                v = tip - Hw[k, b_]
                dep = np.sum(v * nf, 1)
                want = v - nf * np.maximum(dep, 0.0)[:, None]  # only remove the curl towards the palm side
                Rw = R._swing_np(v, want)
                Rw = _rotexp(_rotlog(Rw) * np.clip(flat_h[x][k], 0, 1)[:, None])
                Ra = np.einsum("ji,fjk,kl->fil", MRm, Rw, MRm)
                piv = Hw[k, b_].copy()
                for i in [b_] + [i for i in range(len(rig["par"])) if _is_desc(rig["par"], i, b_)]:
                    sol["A"][k, i] = Ra @ sol["A"][k, i]
                    Hw[k, i] = piv + np.einsum("fij,fj->fi", Rw, Hw[k, i] - piv)
                p_ = rig["par"][b_]
                sol["L"][k, b_] = np.einsum("ij,fjk,fkl->fil", rig["rest"][b_].T @ rig["rest"][p_],
                                            np.transpose(sol["A"][k, p_], (0, 2, 1)), sol["A"][k, b_])
    if (wori > 1e-6).any():
        Hw = sol["Hw"]
        MR = rig["MR"]
        for x in ("L", "R"):
            k = flat_h[x] > 1e-6
            if not k.any():
                continue
            hd_ = bi[f"Bip01 {x} Hand"]
            n_loc = rig["AT"][hd_].T @ (MR.T @ np.array([0.0, 0.0, -1.0]))  # palm normal from the T-pose (palms down)
            n_ = np.einsum("ij,fjk,k->fi", MR, sol["A"][k, hd_], n_loc)
            n_ /= np.linalg.norm(n_, axis=1, keepdims=True)
            t0_, tt = Hw[k, bi[f"Bip01 {x} Finger0"]], Hw[k, bi[f"Bip01 {x} Finger02"]]
            d0 = tt - t0_
            dd = d0 - np.maximum(np.sum(d0 * n_, 1), 0.0)[:, None] * n_  # out of the palm side, into the palm plane
            Rw = R._swing_np(d0, dd)
            Rw = _rotexp(_rotlog(Rw) * np.clip(flat_h[x][k], 0, 1)[:, None])
            Ra = np.einsum("ji,fjk,kl->fil", MR, Rw, MR)
            f0 = bi[f"Bip01 {x} Finger0"]
            ids = [f0] + [i for i in range(len(rig["par"])) if _is_desc(rig["par"], i, f0)]
            for i in ids:
                sol["A"][k, i] = Ra @ sol["A"][k, i]
                Hw[k, i] = t0_ + np.einsum("fij,fj->fi", Rw, Hw[k, i] - t0_)
            p_ = rig["par"][f0]
            sol["L"][k, f0] = np.einsum("ij,fjk,fkl->fil", rig["rest"][f0].T @ rig["rest"][p_],
                                        np.transpose(sol["A"][k, p_], (0, 2, 1)), sol["A"][k, f0])
    # elbows out while the hands are on / near a carton (people carry a box with the elbows wide)
    pole = {x: np.zeros((F, 3)) for x in ("L", "R")}
    for tr in tracks.values():
        for f in range(max(0, tr["grasp"] - 8), min(F, tr["release"] + 4)):
            ff = min(max(f, tr["grasp"]), tr["release"])
            X = np.array([math.cos(tr["yaw"][ff]), math.sin(tr["yaw"][ff]), 0.0])
            eo, ed = station.get("elbow_out", 0.6), station.get("elbow_down", 0.0)  # at a wall: down, not out
            dn_ = np.array([0, 0, -ed])
            pole["L"][f], pole["R"][f] = (-X * eo + dn_) * wgt[f] * (not tr.get("one")), (X * eo + dn_) * wgt[f]
    for i, x in enumerate(("L", "R")):
        pc = palm_pts(sol, rig)[:, i]
        P = sol["Hw"][:, bi[f"Bip01 {x} Hand"]] + (tgt[x] - pc)
        two_bone(sol, rig, (f"Bip01 {x} UpperArm", f"Bip01 {x} Forearm", f"Bip01 {x} Hand"), P, wik, pole[x])
    # safety net: where the arms could not reach their sockets, the carton follows the hands the IK did reach (mean
    # shortfall of the two hands, ramped in over 2 frames after the grasp); it is set down where it then is
    pc = palm_pts(sol, rig)
    for n, tr in tracks.items():
        g, r_ = tr["grasp"], tr["release"]
        dl = None
        sh = (lambda f: pc[f, 1] - tgt["R"][f]) if tr.get("one") else \
            (lambda f: 0.5 * ((pc[f, 0] - tgt["L"][f]) + (pc[f, 1] - tgt["R"][f])))  # noqa: E731
        for f in range(g, min(F, r_ + 1)):
            # (far pinch: from the grasp frame - the pinched edge slides the bag the last 1-2 cm to his fingers; ramped,
            # a short reach left the fingers 1.1 cm inside its edge at the grasp: bench 31 Oct)
            dl = sh(f) * (1.0 if tr.get("pinch") else _smooth((f - g) / 2.0))
            tr["loc"][f] = tr["loc"][f] + dl
        if dl is not None and r_ + 1 < F:
            tr["loc"][r_ + 1:] = tr["loc"][r_ + 1:] + dl * np.array([1.0, 1.0, 0.0])
        tr["reach_fix_max_mm"] = round(float(max(np.linalg.norm(sh(f)) for f in range(g, min(F, r_ + 1)))) * 1000, 1) \
            if r_ >= g else 0.0
        if tr.get("pinch") and len(tr["pinch_hands"]) == 2:  # two hands on its far edge: it goes where both are -
            # the edge through both palms, turned with the line between them (a mean shift left the downhill hand's
            # fingers 2.5 cm inside it, bench 31 Oct); ramped in over 2 frames after the grasp
            w_, d_, h_ = tr["dims"]
            xo_m = 0.5 * (tr["pinch_xo"]["L"] + tr["pinch_xo"]["R"])
            old_r = tr["loc"][min(r_, F - 1)].copy()
            for f in range(g, min(F, r_ + 1)):
                a_, b_ = pc[f, 0], pc[f, 1]
                X_ = b_ - a_
                X_[2] = 0.0
                X_ /= np.linalg.norm(X_) + 1e-9
                fw_ = np.array([-X_[1], X_[0], 0.0]) * tr["fwd_sign"]
                q_ = 0.5 * (a_ + b_) - X_ * xo_m + fw_ * (d_ / 2 - tr["pinch_gi"]) - np.array([0, 0, tr["pinch_lift"]])
                q_[2] = min(a_[2], b_[2]) - tr["pinch_lift"]  # (its top under the lower hand's knuckles: the mean put
                # the other hand's ring knuckle 2.3 cm into it)
                u_ = 1.0  # (from the grasp frame, as the one-hand net: ramped, the short hand was inside its edge)
                tr["loc"][f] = tr["loc"][f] + (q_ - tr["loc"][f]) * u_
                dy_ = (math.atan2(X_[1], X_[0]) - tr["yaw"][f] + math.pi) % (2 * math.pi) - math.pi
                tr["yaw"][f] = tr["yaw"][f] + dy_ * u_
            if r_ + 1 < F:  # (the belt takes it from where it was let go)
                tr["yaw"][r_ + 1:] = tr["yaw"][r_]
                tr["loc"][r_ + 1:] = tr["loc"][r_ + 1:] + (tr["loc"][r_] - old_r) * np.array([1.0, 1.0, 0.0])
    # far pinch (review 018 #4): on the final arm and the final mailer pose. Index + middle hooked under the far edge
    # (into the roller gap), ring + little finger and the thumb laid on the top towards him; then the free side hangs
    # (PINCH_DROOP about the held edge, ramped in after the lift, out again for the set-down)
    for n, tr in tracks.items():
        if not tr.get("pinch"):
            continue
        g, r_ = tr["grasp"], tr["release"]
        w_, d_, h_ = tr["dims"]
        rep_ = {}
        for xh in tr["pinch_hands"]:
            k = np.zeros(F, bool)
            k[max(0, g - int(round(0.5 * fps))):min(F, r_ + 2)] = True
            k &= wo_h[xh] > 1e-3
            if not k.any():
                continue
            ix = np.nonzero(k)[0]
            ff = np.clip(ix, g, r_)
            yz = tr["yaw"][ff]
            fwv = np.stack([-np.sin(yz), np.cos(yz), np.zeros(len(ff))], 1) * tr["fwd_sign"]
            ctr = tr["loc"][ff]
            wk = np.clip(wo_h[xh][k], 0, 1)
            Hw = sol["Hw"]  # index + middle drawn together (adducted, tips ~8 mm each towards the other): side by
            # side they are as wide as the 4.1 cm gap between two rollers (bench: the index tip in the next roller)
            b1_, b2_ = bi[f"Bip01 {xh} Finger1"], bi[f"Bip01 {xh} Finger2"]
            lat = Hw[k, b2_] - Hw[k, b1_]
            lat /= np.linalg.norm(lat, axis=1, keepdims=True) + 1e-9
            for fn_, sg_ in (("1", 1.0), ("2", -1.0)):
                b_ = bi[f"Bip01 {xh} Finger{fn_}"]
                l_ = bi[f"Bip01 {xh} Finger{fn_}2"]
                m_ = bi[f"Bip01 {xh} Finger{fn_}1"]
                v_ = Hw[k, l_] + (Hw[k, l_] - Hw[k, m_]) * 0.9 - Hw[k, b_]
                Rw = R._swing_np(v_, v_ + lat * (0.008 * sg_))
                Rw = _rotexp(_rotlog(Rw) * wk[:, None])
                Ra = np.einsum("ji,fjk,kl->fil", rig["MR"], Rw, rig["MR"])
                piv = Hw[k, b_].copy()
                for i in [b_] + [i for i in range(len(rig["par"])) if _is_desc(rig["par"], i, b_)]:
                    sol["A"][k, i] = Ra @ sol["A"][k, i]
                    Hw[k, i] = piv + np.einsum("fij,fj->fi", Rw, Hw[k, i] - piv)
                p_ = rig["par"][b_]
                sol["L"][k, b_] = np.einsum("ij,fjk,fkl->fil", rig["rest"][b_].T @ rig["rest"][p_],
                                            np.transpose(sol["A"][k, p_], (0, 2, 1)), sol["A"][k, b_])
            r1 = finger_wrap(sol, rig, k, xh, (1, 2), "under", ctr[:, 2] - h_ / 2, -fwv, wk, rf=0.012)
            # ring + little finger stay on the top (switched to under it for the carry, they swept through its top far
            # corner on the way round: 1.5-1.7 cm, bench 31 Oct)
            r1.update(finger_wrap(sol, rig, k, xh, (3, 4), "over", ctr[:, 2] + h_ / 2, -fwv, wk))
            rep_.update({f"{xh}{f_}": v for f_, v in r1.items()})
            Hw = sol["Hw"]  # thumb: from its base down onto the top, towards him
            t0, t2 = bi[f"Bip01 {xh} Finger0"], bi[f"Bip01 {xh} Finger02"]
            b0 = Hw[k, t0]
            L0 = np.linalg.norm(Hw[k, t2] - b0, axis=1) * 1.25
            dzt = np.clip(b0[:, 2] - (ctr[:, 2] + h_ / 2 + 0.009), 0.0, None)
            hz = np.sqrt(np.clip(L0 ** 2 - dzt ** 2, 1e-4, None))
            want = -fwv * hz[:, None] - np.array([0, 0, 1.0]) * dzt[:, None]
            Rw = R._swing_np(Hw[k, t2] - b0, want)
            Rw = _rotexp(_rotlog(Rw) * wk[:, None])
            Ra = np.einsum("ji,fjk,kl->fil", rig["MR"], Rw, rig["MR"])
            for i in [t0] + [i for i in range(len(rig["par"])) if _is_desc(rig["par"], i, t0)]:
                sol["A"][k, i] = Ra @ sol["A"][k, i]
                Hw[k, i] = b0 + np.einsum("fij,fj->fi", Rw, Hw[k, i] - b0)
            p_ = rig["par"][t0]
            sol["L"][k, t0] = np.einsum("ij,fjk,fkl->fil", rig["rest"][t0].T @ rig["rest"][p_],
                                        np.transpose(sol["A"][k, p_], (0, 2, 1)), sol["A"][k, t0])
        tr["pinch_fingers_bent_frames"] = rep_
        # the free side hangs from the held edge
        lf_ = tr.get("lift", g)
        n_u, n_d = max(2, int(round(0.4 * fps))), max(2, int(round(0.5 * fps)))
        dr = np.zeros(F)
        for f in range(g, r_ + 1):
            dr[f] = PINCH_DROOP * min(_smooth((f - lf_) / n_u) if f >= lf_ else 0.0, _smooth((r_ - f) / n_d))
        for f in range(g, r_ + 1):
            if dr[f] <= 0:
                continue
            yz_ = tr["yaw"][f]
            fv_ = np.array([-math.sin(yz_), math.cos(yz_), 0.0]) * tr["fwd_sign"]
            piv = tr["loc"][f] + fv_ * (d_ / 2) - np.array([0, 0, h_ / 2])  # on the hooked fingertips
            v_ = tr["loc"][f] - piv  # rotated about the held edge (axis fwd x up): the free side down
            ax_ = np.cross(fv_, np.array([0, 0, 1.0]))
            c_, s_ = math.cos(dr[f]), math.sin(dr[f])
            tr["loc"][f] = piv + v_ * c_ + np.cross(ax_, v_) * s_ + ax_ * np.dot(ax_, v_) * (1 - c_)
        tr["droop"] = dr * tr["fwd_sign"]
    # one-hand mailers (review 017 #2): the right thumb tip under the near edge, 1.2 cm in (in a roller gap on the
    # table), the palm and fingers on the top: a pinch, not a palm resting on it. After the arm IK and the safety net
    # (both move the hand and the carton)
    # OFF by default (30 Oct): a rigid swing of the thumb chain from a base over the mailer goes through its edge
    # (bench: 163 frames > 1 cm vs 8). Needs per-finger articulation (thumb curling round the edge, or index + middle
    # into a roller gap with the thumb on top: review 017 #2)
    if station.get("thumb_under") and any(tr.get("one") for tr in tracks.values()):
        Hw, MR = sol["Hw"], rig["MR"]
        f0, f01, f02 = (bi[f"Bip01 R Finger0{s_}"] for s_ in ("", "1", "2"))
        ids = [f0] + [i for i in range(len(rig["par"])) if _is_desc(rig["par"], i, f0)]
        p0_ = rig["par"][f0]
        for tr in tracks.values():
            if not tr.get("one"):
                continue
            g, r_ = tr["grasp"], tr["release"]
            w_, d_, h_ = tr["dims"]
            for f in range(max(0, g - 3), min(F, r_ + 2)):
                wt = float(np.clip(flat_h["R"][f], 0, 1)) * (1.0 if g <= f <= r_ else 0.5)
                if wt <= 0:
                    continue
                ff = min(max(f, g), r_)
                yz = tr["yaw"][ff]
                X = np.array([math.cos(yz), math.sin(yz), 0.0])
                Y = np.array([-math.sin(yz), math.cos(yz), 0.0])
                T = tr["loc"][ff] - Y * (d_ / 2 - 0.012) + X * (tr["xo"] - 0.03) - np.array([0, 0, h_ / 2 + 0.006])
                t0 = Hw[f, f0].copy()
                tip = Hw[f, f02] + (Hw[f, f02] - Hw[f, f01]) * 0.9
                Rw = R._swing_np((tip - t0)[None], (T - t0)[None])
                Rw = _rotexp(_rotlog(Rw) * wt)[0]
                Ra = MR.T @ Rw @ MR
                for i in ids:
                    sol["A"][f, i] = Ra @ sol["A"][f, i]
                    Hw[f, i] = t0 + Rw @ (Hw[f, i] - t0)
                sol["L"][f, f0] = rig["rest"][f0].T @ rig["rest"][p0_] @ sol["A"][f, p0_].T @ sol["A"][f, f0]
    frames = frame0 + np.arange(F)
    act = R.write(rig, sol, frames, name)
    return dict(events=events, tracks=tracks, sol=sol, src=Pw, J=J, frames=frames, action=act, targets=tgt,
                wgt=wgt, dz=dz, src_palms=PL + np.array([0, 0, dz]))
