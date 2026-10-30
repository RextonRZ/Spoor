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
CLIPS = HERE.parents[1] / "mocap" / "clips.json"
_takes = {}


def take(name):
    """BVH of an AndyData take (cached) with the participant's measured leg length."""
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


def candidates(min_pick_h=0.9, max_pick_dur=2.0):
    """Pick / place clips usable for a planted right-turning inductor, scored from the data."""
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
                if -95 <= turn <= -30 and trav < 0.45 and t1 - t0 <= max_pick_dur:
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


def plan_cycles(rig, station, n_frames, fps, rnd, picks, places, parcel_ready=None, busy=(), pick_pool=None):
    """Lay pick/place clips back to back over the frames. station: dict(belt_yaw rad (facing the belt), table_pt xyz
    of the waiting parcel's centre, place_y (the belt's near-half centre line), clear_y (min root y: body off the belt
    frame), sign (+1: belt at -Y of the worker)). Returns per-frame arrays (Dw, src positions) + events."""
    segs = []
    t = 0.0
    k = 0
    T = n_frames / fps
    last_pick = last_place = None
    last_lift = None
    recent = []  # (pick, place) pairs of the last 3 cartons: never repeated (review 015 #1)
    while t < T + 1.0:
        for _ in range(40):
            pool = pick_pool(k) if pick_pool else picks  # per carton (e.g. by wall tier height)
            pk = pool[rnd.randrange(len(pool))]
            pl = places[rnd.randrange(len(places))]
            if (len(picks) == 1 or pk is not last_pick) and (len(places) == 1 or pl is not last_place)                     and (id(pk), id(pl)) not in recent:
                break
        last_pick, last_place = pk, pl
        recent = (recent + [(id(pk), id(pl))])[-3:]
        rlo, rhi = station.get("ratio", (0.92, 1.12))  # review 015 #1 (a dock unloader runs slower: 014_GO)
        r1 = rnd.uniform(rlo, rhi)
        r2 = rnd.uniform(rlo, rhi)
        if segs and rnd.random() < 1 / 6:  # an extra beat: a pause with a glance up the line before the next pick
            beat = rnd.uniform(0.6, 1.1)
            segs.append(dict(kind="hold", out0=t, out1=t + beat, beat=True))
            t += beat
        d1 = (pk["t1"] - pk["t0"]) / r1
        d2 = (pl["t1"] - pl["t0"]) / r2
        ready = parcel_ready(k) if callable(parcel_ready) else (
            last_lift + station["refill_s"] if (station.get("refill_s") and last_lift is not None) else None)
        if ready is not None:  # wait (hold) until the next parcel sits at the stop
            g_out = t + (pk["anchor"] - pk["t0"]) / r1
            wait = max(0.0, ready + 0.2 - g_out)
            if wait > 0 and segs:
                segs.append(dict(kind="hold", out0=t, out1=t + wait))
                t += wait
        segs.append(dict(kind="pick", clip=pk, ratio=r1, out0=t, out1=t + d1, n=k))
        last_lift = t + (pk["events"]["lift"] - pk["t0"]) / r1
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
        t += d1 + wait + d2
        k += 1
    return segs


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
        if sg["kind"] == "place":
            want_yaw = belt_yaw  # facing the belt at the release
            Y = R.rz(want_yaw - ya[0])[0]
            v = Y @ (s_ * (pa - hip_a))
            px, py = station.get("place_xy", (station["x"], station.get("place_y", 0.0)))
            root = np.array([px - v[0], max(station["clear_y"], py - v[1])])  # palms over the place spot, body clear
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
    return Dw, Pw, PL, sorted(events, key=lambda e: e["t"]), J


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


def _smooth(u):
    u = np.clip(u, 0, 1)
    return u * u * (3 - 2 * u)


def build(rig, segs, station, parcels, n_frames, fps, frame0=1, name="inductor", ramp_s=0.3):
    """Solve + feet + hands + parcel bake. parcels[n] = dict(dims=(w along the hands, d, h)). Writes the action and
    returns dict(events, parcel tracks {n: (F,3) loc, (F,) yaw, (F,) pitch, state per frame}, sol, src)."""
    Dw, Pw, PL, events, J = assemble(rig, segs, station, n_frames, fps, frame0)
    want = (Pw[:, J["LeftHip"]] + Pw[:, J["RightHip"]]) / 2
    if "root_min_y" in station:  # hips never closer to the belt frame than this, every frame (soft max, 3 cm)
        lo_, k_ = station["root_min_y"], 0.03
        dy_ = want[:, 1] - lo_
        want[:, 1] = lo_ + np.where(dy_ > 4 * k_, dy_, k_ * np.log1p(np.exp(np.clip(dy_ / k_, -50, 50))))
    sol = R.solve(rig, Dw, J, want)
    dz = R.floor_dz(rig, sol, station.get("lift", 0.0))
    Pw[:, :, 2] += dz
    for sd, sj in (("L", "LeftAnkle"), ("R", "RightAnkle")):
        R._foot_lock(sol["A"], sol["Hw"], sol["L"], rig["rest"], rig["par"], rig["bi"], sd,
                     R.contacts(Pw[:, J[sj]], fps), rig["MR"], fps)
    F = n_frames
    pm0 = palm_pts(sol, rig)  # mocap palms (after the solve, before hand IK)
    tf = lambda t: int(np.clip(round(t * fps), 0, F - 1))  # noqa: E731
    grasp = {e["n"]: tf(e["t"]) for e in events if e["kind"] == "grasp"}
    lift = {e["n"]: tf(e["t"]) for e in events if e["kind"] == "lift"}
    rel = {e["n"]: tf(e["t"]) for e in events if e["kind"] == "release"}
    tracks = {}
    tgt = {x: pm0[:, i].copy() for i, x in enumerate(("L", "R"))}
    wgt = np.zeros(F)
    rf = max(1, int(round(ramp_s * fps)))
    slope = station.get("table_slope", 0.0)
    for n in sorted(grasp):
        if n not in rel or n not in parcels:
            continue
        g, r_, lf = grasp[n], rel[n], lift.get(n, grasp[n])
        w_, d_, h_ = parcels[n]["dims"]
        tp = np.array(station.get("pick_pts", {}).get(n, station["table_pt"])) + np.array([0, 0, h_ / 2])
        mid = pm0.mean(1)
        ax = pm0[:, 1] - pm0[:, 0]
        yaw = np.arctan2(ax[:, 1], ax[:, 0])
        yaw = np.unwrap(yaw)
        # the carton sits square on the table (yaw snapped to the table's axes); in the hands it turns rigidly with
        # the hand axis, keeping that offset
        if "grip_axis_yaw" in station:  # snap to the table's axes, preferring the hands across this one (30 deg bias)
            cands = [station["grip_axis_yaw"] + k_ * math.pi / 2 for k_ in range(-8, 9)
                     if not station.get("grip_axis_strict") or k_ % 2 == 0]  # strict: only the faces across it
            tyaw = min(cands, key=lambda c_: abs(yaw[g] - c_) + (0 if (round((c_ - station["grip_axis_yaw"]) /
                                                                             (math.pi / 2)) % 2 == 0) else math.radians(30)))
        else:
            tyaw = station.get("table_yaw", 0.0) + round((yaw[g] - station.get("table_yaw", 0.0)) / (math.pi / 2)) * math.pi / 2
        yoff = tyaw - yaw[g]
        yaw = yaw + yoff
        if "table_align_x" in station:  # skewed rollers run every carton against the operator-side rail
            ex = 0.5 * (abs(w_ * math.cos(tyaw)) + abs(d_ * math.sin(tyaw)))
            tp[0] = station["table_align_x"] + ex + 0.005
        pl_ = mid[r_].copy()
        if "induct_start" in station:  # on the induct belt's placement zone: 0.15-0.6 m along, inside its width
            S_, d2 = np.array(station["induct_start"]), np.array(station["induct_dir"])
            n2 = np.array([-d2[1], d2[0]])
            ang = yaw[r_] - math.atan2(d2[1], d2[0])
            ea = 0.5 * (abs(w_ * math.cos(ang)) + abs(d_ * math.sin(ang)))
            el = 0.5 * (abs(w_ * math.sin(ang)) + abs(d_ * math.cos(ang)))
            hw = station.get("induct_half_w", 0.25) - 0.02
            rv = pl_[:2] - S_
            al = np.clip(rv @ d2, 0.05 + ea, max(0.05 + ea, 0.5))
            lt = np.clip(rv @ n2, -max(0.0, hw - el), max(0.0, hw - el))
            pl_[:2] = S_ + d2 * al + n2 * lt
        else:
            pl_[0] = np.clip(pl_[0], station["place_x"][0], station["place_x"][1])
            ext = 0.5 * (abs(w_ * math.sin(yaw[r_])) + abs(d_ * math.cos(yaw[r_])))  # half extent across the belt
            pl_[1] = np.clip(pl_[1], station["place_y_range"][0] + ext, station["place_y_range"][1] - ext)
        pl_[2] = station["belt_top"] + h_ / 2
        loc = np.zeros((F, 3))
        yw = np.zeros(F)
        pitch = np.zeros(F)
        state = np.array(["table"] * F, dtype=object)
        gi = min(station.get("grip_in", 0.05), d_ / 2)  # grip near the body-side edge (forearms clear the box)
        fwd = np.stack([-np.sin(yaw), np.cos(yaw), np.zeros(F)], 1)  # parcel local +Y: away from the body
        fwd = -fwd if station.get("flip_fwd") else fwd
        tp_g = tp - fwd[g] * (d_ / 2 - gi)
        pl_g = pl_ - fwd[r_] * (d_ / 2 - gi)
        zmin_g = station.get("pick_grip_min_z", 0.0)
        zmin_r = station["belt_top"] + 0.05
        # grip high on the side face (5.5 cm under the top edge: the forearms come over less of the carton), never
        # lower than the support allows
        gz = lambda c, zm: max(0.0, max(zm - c[2], h_ / 2 - 0.055))  # noqa: E731  grip height above the centre
        lift_g, lift_r = gz(tp, zmin_g), gz(pl_, zmin_r)
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
        pl_ = loc[r_].copy()  # set down where it was released (on the belt, clear of the body)
        pl_[2] = station["belt_top"] + h_ / 2
        tracks[n] = dict(loc=loc, yaw=yw, pitch=pitch, state=state, grasp=g, release=r_, dims=(w_, d_, h_))
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
            return {"L": gp - X * (w_ / 2 + so), "R": gp + X * (w_ / 2 + so)}, {"L": -X, "R": X}
        sg_, og_ = sockets(g)
        sr_, or_ = sockets(r_)
        bk = sol["Hw"][r_, rig["bi"]["Bip01 Pelvis"]] - pl_  # retract towards the pelvis (horizontal) but never
        bk[2] = 0  # along the grip axis: that would sweep one hand across the carton
        Xr = np.array([math.cos(yw[r_]), math.sin(yw[r_]), 0.0])
        bk -= np.dot(bk, Xr) * Xr
        bk /= np.linalg.norm(bk) + 1e-9
        for f in range(max(0, g - n_in), min(F, r_ + n_out1 + n_keep + n_out2 + 1)):
            for i, x in enumerate(("L", "R")):
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
                elif f <= r_ + n_out1:  # off the face: out 3 cm, up 8 cm, back 10 cm (the carton leaves along the belt)
                    u = _smooth((f - r_) / n_out1)
                    w = 1.0
                    tgt[x][f] = sr_[x] + (or_[x] * 0.06 + bk * 0.18 + np.array([0, 0, 0.10])) * u
                elif f <= r_ + n_out1 + n_keep:
                    w = 1.0
                    tgt[x][f] = sr_[x] + or_[x] * 0.06 + bk * 0.18 + np.array([0, 0, 0.10])
                else:  # back to the mocap path
                    w = 1 - _smooth((f - r_ - n_out1 - n_keep) / n_out2)
                    off = sr_[x] + or_[x] * 0.06 + bk * 0.18 + np.array([0, 0, 0.10])
                    tgt[x][f] = pm0[f, i] + w * (off - pm0[f, i])
            wgt[f] = max(wgt[f], w)
        # light curtain: the placement belt starts at the first delay (0.3-1.5 s) for which the moving carton keeps
        # >= 9 cm (hand + fingers) from both hand targets over the next 1.2 s
        Rz = np.array([[math.cos(yw[r_]), -math.sin(yw[r_]), 0], [math.sin(yw[r_]), math.cos(yw[r_]), 0], [0, 0, 1]])
        hb = np.array([w_, d_, h_]) / 2 + 0.10
        bdir = np.array([station.get("belt_dir", 1.0), 0, 0])
        best = 1.5
        for d0 in np.arange(0.3, 1.51, 0.1):
            ok = True
            for f in range(r_ + 1, min(F, r_ + int(1.2 * fps) + 1)):
                tb = (f - r_) / fps - d0
                if tb <= 0:
                    continue  # still standing: the hands only have to be clear of its path once it moves
                xx = station["belt_speed"] * (tb - 0.125) if tb > 0.25 else station["belt_speed"] * tb * tb / 0.5
                c_ = belt_path(station, pl_, xx)
                for x in ("L", "R"):
                    q_ = Rz.T @ (tgt[x][f] - c_)
                    if np.all(np.abs(q_) < hb):
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                best = float(d0)
                break
        for f in range(r_ + 1, F):
            tb = (f - r_) / fps - best
            xx = 0.0 if tb <= 0 else (station["belt_speed"] * (tb - 0.125) if tb > 0.25 else
                                      station["belt_speed"] * tb * tb / 0.5)
            loc[f] = belt_path(station, pl_, xx)
        tracks[n]["belt_wait_s"] = round(best, 2)
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
    for tr in tracks.values():
        holding[tr["grasp"]:tr["release"] + 1] = True
    for x_i, x in enumerate(("L", "R")):
        for f in range(F):
            if holding[f]:
                continue  # on the carton: the sockets decide
            p_ = tgt[x][f]
            for (x0, y0, x1, y1, zt) in station.get("surfaces", ()):
                if x0 - 0.04 <= p_[0] <= x1 + 0.04 and y0 - 0.04 <= p_[1] <= y1 + 0.04 and p_[2] < zt + 0.10:
                    p_[2] = zt + 0.10  # a hand's length above the surface (the fingers may point down)
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
        dzn = 0.5 * ((tgt["L"][f][2] - pmc[f, 0, 2]) + (tgt["R"][f][2] - pmc[f, 1, 2]))
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
            for f in range(max(0, g - int(round(0.5 * fps))), min(F, r_ + int(round(0.6 * fps)) + 1)):
                ff = min(max(f, g), r_)
                X = np.array([math.cos(tr["yaw"][ff]), math.sin(tr["yaw"][ff]), 0.0])
                Yf = np.array([-X[1], X[0], 0.0])
                nd[f] = sgn * X
                dn = 0.0  # level: tilted down, the little finger reached under the end stop / belt top
                fdd[f] = Yf * math.cos(dn) - np.array([0, 0, math.sin(dn)])
        k = wgt > 1e-6
        if not k.any():
            continue
        Fc = np.stack([fd, n_, np.cross(fd, n_)], 2)  # current frame (columns)
        fdd_o = fdd - np.sum(fdd * nd, 1)[:, None] * nd
        fdd_o /= np.linalg.norm(fdd_o, axis=1, keepdims=True) + 1e-12
        Fd = np.stack([fdd_o, nd, np.cross(fdd_o, nd)], 2)
        Rw = np.einsum("fij,fkj->fik", Fd[k], Fc[k])  # world rotation current -> desired
        Rw = I._rotexp(I._rotlog(Rw) * np.clip(wgt[k], 0, 1)[:, None]) if False else             _rotexp(_rotlog(Rw) * np.clip(wgt[k], 0, 1)[:, None])
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
    fl = np.clip(wgt, 0, 1)[:, None]
    for nm_, i in bi.items():
        if "Finger" in nm_ and nm_.split()[1] in ("L", "R"):
            sol["L"][:, i] = _rotexp((1 - fl) * I_log(rig["LT"][i])[None])
            sol.setdefault("keyed", set()).add(i)
    for x in ("L", "R"):
        fk_desc(sol, rig, bi[f"Bip01 {x} Hand"])
    # the bind pose still curls the fingers (up to ~5 cm at the tips, more on the female hands): turn each finger at
    # its knuckle so its tip comes back into the palm plane, so the palm itself can lie on the carton face
    k = wgt > 1e-6
    if k.any():
        Hw = sol["Hw"]
        MRm = rig["MR"]
        for x in ("L", "R"):
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
                Rw = _rotexp(_rotlog(Rw) * np.clip(wgt[k], 0, 1)[:, None])
                Ra = np.einsum("ji,fjk,kl->fil", MRm, Rw, MRm)
                piv = Hw[k, b_].copy()
                for i in [b_] + [i for i in range(len(rig["par"])) if _is_desc(rig["par"], i, b_)]:
                    sol["A"][k, i] = Ra @ sol["A"][k, i]
                    Hw[k, i] = piv + np.einsum("fij,fj->fi", Rw, Hw[k, i] - piv)
                p_ = rig["par"][b_]
                sol["L"][k, b_] = np.einsum("ij,fjk,fkl->fil", rig["rest"][b_].T @ rig["rest"][p_],
                                            np.transpose(sol["A"][k, p_], (0, 2, 1)), sol["A"][k, b_])
    if k.any():
        Hw = sol["Hw"]
        MR = rig["MR"]
        for x in ("L", "R"):
            h = Hw[k, bi[f"Bip01 {x} Hand"]]
            n_ = np.cross(Hw[k, bi[f"Bip01 {x} Finger1"]] - h, Hw[k, bi[f"Bip01 {x} Finger4"]] - h)
            t0_, tt = Hw[k, bi[f"Bip01 {x} Finger0"]], Hw[k, bi[f"Bip01 {x} Finger02"]]
            n_ *= np.sign(np.sum(n_ * (tt - h), 1))[:, None]
            n_ /= np.linalg.norm(n_, axis=1, keepdims=True)
            d0 = tt - t0_
            dd = d0 - np.sum(d0 * n_, 1)[:, None] * n_ - 0.25 * np.linalg.norm(d0, axis=1)[:, None] * n_ * 0.0
            Rw = R._swing_np(d0, dd)
            Rw = _rotexp(_rotlog(Rw) * np.clip(wgt[k], 0, 1)[:, None])
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
            pole["L"][f], pole["R"][f] = (-X * eo + dn_) * wgt[f], (X * eo + dn_) * wgt[f]
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
        for f in range(g, min(F, r_ + 1)):
            dl = 0.5 * ((pc[f, 0] - tgt["L"][f]) + (pc[f, 1] - tgt["R"][f])) * _smooth((f - g) / 2.0)
            tr["loc"][f] = tr["loc"][f] + dl
        if dl is not None and r_ + 1 < F:
            tr["loc"][r_ + 1:] = tr["loc"][r_ + 1:] + dl * np.array([1.0, 1.0, 0.0])
        tr["reach_fix_max_mm"] = round(float(max(np.linalg.norm(0.5 * ((pc[f, 0] - tgt["L"][f]) + (pc[f, 1] - tgt["R"][f])))
                                                for f in range(g, min(F, r_ + 1)))) * 1000, 1) if r_ >= g else 0.0
    frames = frame0 + np.arange(F)
    act = R.write(rig, sol, frames, name)
    return dict(events=events, tracks=tracks, sol=sol, src=Pw, J=J, frames=frames, action=act, targets=tgt,
                wgt=wgt, dz=dz, src_palms=PL + np.array([0, 0, dz]))
