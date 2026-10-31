"""Scenario S2's removal actor on mocap (scenarios_v2 S2 #2): walk in, take a small box off a roll-cage shelf with
both hands, turn away with it and walk it through the exception store's entrance - every frame from real capture.

Timeline (one take each, joined by inertialization):
  1. walk in: 100STYLE Neutral_FW (CC BY 4.0), path-warped onto a route that ends where clip 2 starts;
  2. the pick: one AndyData take (CC BY 4.0) from ~2 s before the grasp (he walks up to the shelf) to ~1.6 s after
     the lift (he has turned away and walks off carrying), anchored so his palms meet the box at the grasp;
  3. walk out: 100STYLE Neutral_FW path-warped onto the route to the store, with the carry arms of clip 2's last
     frame held relative to the chest (the walk's own arms swing; a carried box doesn't).
Path warp (Gleicher 2001): the source's smoothed hip path is mapped by arc length onto the route; every frame is
turned by (route tangent - source tangent), so the step-by-step sway and the body's yaw relative to its own travel
stay as captured. The walk ends / starts are chosen by matching the legs (ankles relative to the hips, and their
velocities, in the heading frame) to clip 2's first / last frame, so a stride is never cut against the wrong foot.
Then: retarget solve, floor, foot lock in stance, the box rigid with the (mocap) palms from the grasp, a two-bone IK
onto its end faces (palms flat, fingers along the face), elbows down.
"""
import math

import importlib.util
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import retarget as R  # noqa: E402

# the engine by file (Blender's path has another top-level "inductor" module: stations.MocapInductors does the same)
if "mocap_inductor" not in sys.modules:
    _spec = importlib.util.spec_from_file_location("mocap_inductor", Path(__file__).resolve().parent / "inductor.py")
    sys.modules["mocap_inductor"] = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(sys.modules["mocap_inductor"])
I = sys.modules["mocap_inductor"]

FW_TAKE, FW_CLEAN = "100STYLE/Neutral/Neutral_FW", (327 / 60.0, 7445 / 60.0)
LEGS = ("LeftAnkle", "RightAnkle", "LeftKnee", "RightKnee")


# ------------------------------------------------------------------------------------------------ route
def route(pts, r=0.8, step=0.02):
    """Polyline with filleted corners (radius <= r, at most half of each leg), densified: (P (N,2), S (N,), TH (N,))."""
    pts = [np.asarray(p, float) for p in pts]
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        u, v = (b - a) / np.linalg.norm(b - a), (c - b) / np.linalg.norm(c - b)
        ang = math.acos(float(np.clip(np.dot(u, v), -1, 1)))
        if ang < 1e-3:
            out.append(b)
            continue
        cut = min(r * math.tan(ang / 2), np.linalg.norm(b - a) / 2, np.linalg.norm(c - b) / 2)
        p0, p1 = b - u * cut, b + v * cut
        for k in range(17):  # quadratic Bezier p0 -> b -> p1 (tangent-continuous)
            s = k / 16
            out.append((1 - s) ** 2 * p0 + 2 * s * (1 - s) * b + s * s * p1)
    out.append(pts[-1])
    P = [out[0]]
    for q in out[1:]:
        d = np.linalg.norm(q - P[-1])
        if d < 1e-6:
            continue
        n = max(1, int(math.ceil(d / step)))
        p0 = P[-1]
        for k in range(1, n + 1):
            P.append(p0 + (q - p0) * k / n)
    P = np.array(P)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    S = np.r_[0, np.cumsum(seg)]
    d = np.gradient(P, axis=0)
    TH = np.unwrap(np.arctan2(d[:, 1], d[:, 0]))
    return P, S, TH


def at(rt, s):
    P, S, TH = rt
    s = np.clip(s, 0, S[-1])
    return np.stack([np.interp(s, S, P[:, 0]), np.interp(s, S, P[:, 1])], -1), np.interp(s, S, TH)


# ------------------------------------------------------------------------------------------------ sources
def _gauss(x, sig):
    k = np.exp(-0.5 * (np.arange(-3 * sig, 3 * sig + 1) / sig) ** 2)
    k /= k.sum()
    xp = np.pad(x, ((len(k) // 2, len(k) // 2),) + ((0, 0),) * (x.ndim - 1), mode="edge")
    return np.stack([np.convolve(xp[:, j], k, "valid") for j in range(x.shape[1])], 1) if x.ndim > 1 else \
        np.convolve(xp, k, "valid")


_FW_CACHE = {}


def fw_world(mirror, rate=60.0, v_min=0.35, total_s=300.0):
    """The clean forward walk at `rate` Hz as a VIRTUAL timeline: only the stretches between the capture's
    turnarounds, chained (motion gate 31 Oct: the actor slows down and turns round every 13-28 s - at 26.05 / 81.53 s
    the smoothed path's heading flips 150-170 deg in one sample, at 54.2 s a slow U-turn - and the path warp spun the
    walker 144-360 deg in a few output frames; a long route needs more straight source than any one stretch has).
    Each stretch is continued from the frame of another stretch whose legs match best (the same gait phase); per
    virtual sample: the real source time t, Dw, Pw, the real smoothed hip path cs and heading th (the warp works per
    frame relative to them), a continuous arc, and the stretch-run id seg (joins are inertialized)."""
    key = (mirror, rate)
    if key in _FW_CACHE:
        return _FW_CACHE[key]
    b = I.take(FW_TAKE)
    J = b["J"]
    t = np.arange(FW_CLEAN[0], FW_CLEAN[1], 1 / rate)
    Dw, Pw = R.clip_world(b, t, rate, mirror=mirror)
    hip = (Pw[:, J["LeftHip"]] + Pw[:, J["RightHip"]])[:, :2] / 2
    cs = _gauss(hip, int(0.45 * rate))  # one stride: the sway averages out
    d = np.gradient(cs, axis=0)
    th = np.unwrap(np.arctan2(d[:, 1], d[:, 0]))
    n = len(t)
    bad = (np.linalg.norm(d, axis=1) * rate < v_min) | (np.abs(np.r_[np.diff(th), 0]) > math.radians(20))
    pad = int(0.5 * rate)
    badd = np.convolve(bad.astype(float), np.ones(2 * pad + 1), "same") > 0
    runs, i0 = [], None
    for i in range(n):
        if not badd[i] and i0 is None:
            i0 = i
        if (badd[i] or i == n - 1) and i0 is not None:
            i1 = i - 1 if badd[i] else i
            if i1 - i0 > 2 * rate:
                runs.append((i0, i1))
            i0 = None
    fp, fv = fw_feats(dict(Dw=Dw, Pw=Pw, J=J, rate=rate))
    feat = np.concatenate([fp, fv * 0.25], 2).reshape(n, -1)
    idx, seg = [], []
    r_, a, sid = 0, runs[0][0], 0
    while len(idx) < total_s * rate:
        a1 = runs[r_][1]
        idx += list(range(a, a1 + 1))
        seg += [sid] * (a1 - a + 1)
        r_ = (r_ + 1) % len(runs)  # on into the next stretch (wrapping round): its frame matching the legs at a1
        b0, b1 = runs[r_][0], runs[r_][1] - int(3 * rate)
        if b1 <= b0:
            b1 = runs[r_][1]
        cand = np.arange(b0, b1)
        a = int(cand[np.argmin(np.linalg.norm(feat[cand] - feat[a1], axis=1))]) + 1
        sid += 1
    idx = np.array(idx)
    seg = np.array(seg)
    step = np.linalg.norm(np.diff(cs[idx], axis=0), axis=1)
    same = seg[1:] == seg[:-1]
    step = np.where(same, step, np.median(step[same]))  # across a join: one ordinary step
    arc = np.r_[0, np.cumsum(step)]
    out = dict(b=b, J=J, t=t[idx], Dw=Dw[idx], Pw=Pw[idx], hip=hip[idx], cs=cs[idx], th=th[idx], arc=arc, rate=rate,
               mirror=mirror, seg=seg, runs=runs)
    _FW_CACHE[key] = out
    return out


def leg_feat(Dw, Pw, J, i, dt):
    """Legs at frame i in the hips' heading frame: knee / ankle offsets from the hip midpoint and their velocities."""
    yaw = float(R.yaw_of(Dw[i:i + 1, J["Hips"]])[0])
    Rz = R.rz(-yaw)[0]
    hip = (Pw[i, J["LeftHip"]] + Pw[i, J["RightHip"]]) / 2
    hip1 = (Pw[i + 1, J["LeftHip"]] + Pw[i + 1, J["RightHip"]]) / 2
    f = []
    for n in LEGS:
        p0, p1 = Pw[i, J[n]] - hip, Pw[i + 1, J[n]] - hip1
        f += list(Rz @ p0) + list(Rz @ (p1 - p0) / dt * 0.25)
    return np.array(f)


def fw_feats(fw):
    """leg_feat for every FW frame, split into the position part and the per-source-second velocity part."""
    if "fpos" in fw:
        return fw["fpos"], fw["fvel"]
    Dw, Pw, J = fw["Dw"], fw["Pw"], fw["J"]
    Rz = R.rz(-R.yaw_of(Dw[:, J["Hips"]]))
    hip = (Pw[:, J["LeftHip"]] + Pw[:, J["RightHip"]]) / 2
    pos, vel = [], []
    for nm in LEGS:
        p = Pw[:, J[nm]] - hip
        pos.append(np.einsum("fij,fj->fi", Rz, p))
        dp = np.r_[np.diff(p, axis=0), np.zeros((1, 3))] * fw["rate"]
        vel.append(np.einsum("fij,fj->fi", Rz, dp))
    fw["fpos"], fw["fvel"] = np.stack(pos, 1), np.stack(vel, 1)  # (n, 4, 3)
    return fw["fpos"], fw["fvel"]


def match_fw(fw, feat, ratio, s_, need_s, end=True, min_curv_w=0.15):
    """FW frame whose legs best match `feat` (a clip's first frame: the walk ENDS there; else its last frame: the walk
    STARTS there), with need_s seconds of source before / after it inside the clean range; mild preference for a
    straight source (less to warp)."""
    rate, n = fw["rate"], len(fw["t"])
    span = int(need_s * ratio * rate) + 2
    fp, fv = fw_feats(fw)
    ff = np.concatenate([fp, fv * ratio * 0.25], 2).reshape(n, -1) * s_  # as leg_feat, at this ratio and scale
    d = np.linalg.norm(ff - feat.reshape(1, -1), axis=1)
    dth = np.abs(np.r_[np.diff(fw["th"]), 0])
    dth[np.r_[fw["seg"][1:] != fw["seg"][:-1], False]] = 0.0  # (a join of the virtual timeline: not a turn)
    cum = np.r_[0, np.cumsum(dth * rate)]
    i = np.arange(n)
    lo, hi = (i - span, i) if end else (i, i + span)
    ok = (lo >= 0) & (hi <= n - 2) & (i >= 1) & (i <= n - 3)
    curv = np.where(ok, (cum[np.clip(hi, 0, n)] - cum[np.clip(lo, 0, n)]) / max(1, span), 1e9)
    sc = np.where(ok, d + min_curv_w * curv, 1e9)
    k = int(np.argmin(sc))
    return (float(sc[k]), k, float(d[k]), float(curv[k]))


def walk_seg(fw, i_anchor, ratio, s_, rt, times, t_anchor, end=True):
    """Source frames for output `times` (s), path-warped onto route rt: the source frame i_anchor (at output time
    t_anchor) sits at the route's end (end=True) or start. Returns Dw, Pw (scaled, placed)."""
    rate = fw["rate"]
    fi = i_anchor + (np.asarray(times) - t_anchor) * ratio * rate
    fi = np.clip(fi, 1, len(fw["t"]) - 1.001)
    k = np.floor(fi).astype(int)
    fr = fi - k
    same = fw["seg"][k] == fw["seg"][k + 1]  # (a virtual timeline: k and k+1 may be either side of a join)
    tt = fw["t"][k] + fr / rate  # real source time: on from sample k
    Dc, Pc = R.clip_world(fw["b"], tt, rate / ratio, mirror=fw["mirror"])
    nxt = np.where(same[:, None], fw["cs"][k + 1], 2 * fw["cs"][k] - fw["cs"][k - 1])
    cs = fw["cs"][k] + (nxt - fw["cs"][k]) * fr[:, None]
    thn = np.where(same, fw["th"][k + 1], 2 * fw["th"][k] - fw["th"][k - 1])
    thc = fw["th"][k] + (thn - fw["th"][k]) * fr
    arc = np.interp(fi, np.arange(len(fw["t"])), fw["arc"])
    L = rt[1][-1]
    s_out = (L - (fw["arc"][i_anchor] - arc) * s_) if end else (arc - fw["arc"][i_anchor]) * s_
    base, th = at(rt, s_out)
    over = np.maximum(0, -s_out) if end else np.maximum(0, s_out - L)  # past the route: straight on along its end
    if over.any():
        ends = (0 if end else -1)
        tan = np.array([math.cos(rt[2][ends]), math.sin(rt[2][ends])])
        base = base + (-1 if end else 1) * over[:, None] * tan
    th = _rate_limit(th, np.asarray(times, float), math.radians(220.0))
    Y = R.rz(th - thc)
    Dseg = np.einsum("fij,fkjl->fkil", Y, Dc)
    rel = s_ * (Pc - np.concatenate([cs, np.zeros((len(cs), 1))], 1)[:, None, :] * np.array([1, 1, 0]))
    Pseg = np.einsum("fij,fkj->fki", Y, rel)
    Pseg[:, :, :2] += base[:, None, :]
    return Dseg, Pseg, dict(s_out=s_out, route_len=L, seg=fw["seg"][k])


def _rate_limit(th, times, w_max):
    """Heading th(t) (rad, unwrapped) with its rate held to w_max (rad/s): a forward and a backward pass, averaged
    (the turn is spread over both sides of a tight corner, not lagged after it)."""
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


def clip_seg(b, t0, t1, g, mirror, s_, box_yaw, grip_xy, times, t_out0, behind=0.0):
    """AndyData window [t0, t1] at output time t_out0 (no retime), turned so the source palm axis (left -> right) at
    the grasp g runs along the box's +X (box_yaw), placed so the source palm midpoint at g sits over grip_xy - and the
    hips at least `behind` m behind it along the box's -Y (the body clear of the cage front: the IK reaches the rest)."""
    J = b["J"]
    tt = t0 + (np.asarray(times) - t_out0)
    Dc, Pc = R.clip_world(b, tt, 30, mirror=mirror)
    Da, Pa = R.clip_world(b, [g], 30, mirror=mirror)
    pl = I.palms(b, Da, Pa)[0]
    ax = pl[1] - pl[0]
    hip_a = (Pa[0, J["LeftHip"]] + Pa[0, J["RightHip"]]) / 2
    pa = pl.mean(0)
    Y = R.rz(box_yaw - math.atan2(ax[1], ax[0]))[0]
    v = Y @ (s_ * (pa - hip_a))
    root = np.asarray(grip_xy) - v[:2]
    yb = np.array([-math.sin(box_yaw), math.cos(box_yaw)])
    ahead = float(np.dot(v[:2], yb))  # palms ahead of the hips along the box's +Y
    if ahead < behind:
        root = root - yb * (behind - ahead)
    Dseg = np.einsum("ij,fkjl->fkil", Y, Dc)
    Pseg = np.einsum("ij,fkj->fki", Y, s_ * (Pc - hip_a * np.array([1, 1, 0])))
    Pseg[:, :, :2] += root
    return Dseg, Pseg, dict(Y=Y, root=root)


def inertialize(Dw, Pw, owner, fps, join_s=0.4):
    """As inductor.assemble: at each owner change the previous pose's offset decays (smootherstep) over join_s."""
    F = len(Dw)
    nj = max(2, int(round(join_s * fps)))
    for f in range(1, F):
        if owner[f] == owner[f - 1]:
            continue
        prevD = Dw[f - 1]
        prevP = Pw[f - 1] + (Pw[f - 1] - Pw[f - 2]) if f > 1 else Pw[f - 1]
        off_r = I._rotlog(np.einsum("kij,klj->kil", prevD, Dw[f]))
        off_p = prevP - Pw[f]
        for i_ in range(nj):
            if f + i_ >= F or owner[f + i_] != owner[f]:
                break
            u = i_ / nj
            w = 1 - u ** 3 * (u * (u * 6 - 15) + 10)
            Dw[f + i_] = np.einsum("kij,kjl->kil", I._rotexp(off_r * w), Dw[f + i_])
            Pw[f + i_] = Pw[f + i_] + off_p * w


ARMS = ("LeftCollar", "LeftShoulder", "LeftElbow", "LeftWrist", "RightCollar", "RightShoulder", "RightElbow",
        "RightWrist")


def hold_arms(Dw, J, D_ref, frames, keep=0.0):
    """The arms' orientation relative to the chest (Chest4) as in D_ref (one frame), on `frames`, with `keep` of the
    walk's own arm motion layered on (relative to that pose): the elbows and shoulders still move with the gait."""
    c = J["Chest4"]
    frames = np.asarray(frames)
    for a in ARMS:
        rel = D_ref[c].T @ D_ref[J[a]]
        if keep > 0:
            rel_w = np.einsum("fji,fjk->fik", Dw[frames, c], Dw[frames, J[a]])  # the walk's, chest-relative
            dl = I._rotlog(np.einsum("ji,fjk->fik", rel, rel_w)) * keep
            rel_f = np.einsum("ij,fjk->fik", rel, I._rotexp(dl))
            Dw[frames, J[a]] = np.einsum("fij,fjk->fik", Dw[frames, c], rel_f)
        else:
            Dw[frames, J[a]] = np.einsum("fij,jk->fik", Dw[frames, c], rel)


def _turn(sol, rig, k, bone, Rw):
    """World rotation Rw (n,3,3) of `bone` and everything below it about its head, on frames k (bool mask)."""
    MRm, Hw = rig["MR"], sol["Hw"]
    b = rig["bi"][bone] if isinstance(bone, str) else bone
    Ra = np.einsum("ji,fjk,kl->fil", MRm, Rw, MRm)
    piv = Hw[k, b].copy()
    for i in [b] + [i for i in range(len(rig["par"])) if I._is_desc(rig["par"], i, b)]:
        sol["A"][k, i] = Ra @ sol["A"][k, i]
        Hw[k, i] = piv + np.einsum("fij,fj->fi", Rw, Hw[k, i] - piv)
    p_ = rig["par"][b]
    sol["L"][k, b] = np.einsum("ij,fjk,fkl->fil", rig["rest"][b].T @ rig["rest"][p_],
                               np.transpose(sol["A"][k, p_], (0, 2, 1)), sol["A"][k, b])


def _palm_n(sol, rig, x, k):
    """Palm normals (n,3) of hand x on frames k: the T-pose palm-down direction carried by the hand's rotation."""
    MRm = rig["MR"]
    hd = rig["bi"][f"Bip01 {x} Hand"]
    n_loc = rig["AT"][hd].T @ (MRm.T @ np.array([0.0, 0.0, -1.0]))
    n_ = np.einsum("ij,fjk,k->fi", MRm, sol["A"][k, hd], n_loc)
    return n_ / np.linalg.norm(n_, axis=1, keepdims=True)


# ------------------------------------------------------------------------------------------------ the whole actor
def _rng(v):
    return np.arange(v[0], v[1] + 1e-6, 1 / 30.0) if np.ndim(v) else [float(v)]


def _fw_ratio(rig, fw, v):
    s_f = R.leg_ratio(rig, fw["b"])[0]
    v_fw = float(np.median(np.linalg.norm(np.diff(fw["cs"], axis=0), axis=1))) * fw["rate"] * s_f
    return s_f, float(np.clip(v / v_fw, 0.9, 1.25))


def _fw_feat_at(fw, i, ratio, s_f):
    fp, fv = fw_feats(fw)
    return np.concatenate([fp[i], fv[i] * ratio * 0.25], 1).reshape(-1) * s_f


def compose(rig, cfg):
    """The whole actor as a chain of legs: walk, clip, walk, clip, ..., walk (cfg["legs"]).
      walk: dict(kind="walk", route=[(x, y) ...]) - the waypoints between the clips (the clips' own start / end and
            their walking directions are added); the first walk is anchored at its end, the others at their start.
      clip: dict(kind="clip", role="pick" | "place", take, mirror, grasp + lift (pick) | release (place),
            pre_s / post_s (s, or a (lo, hi) range searched against the walks), at (xyz the box centre at the event),
            yaw (the box's yaw then: its +X runs across the hands), behind (min hips-behind-palms along the box -Y),
            lead_in / lead_out (m of straight route into / out of the clip along its walking direction: 1.2 / 1.0),
            [t (output s of the event): the first clip only; later clips follow from the walk before them]).
    cfg: fps, F, frame0, box=dict(c, yaw, dims (w across the hands, d, h), support_z, cage (x0, y0, x1, y1)),
    palm_off, palm_up, trunk_clear, finger_flat, lift, lift_f, join_s, name.
    Returns dict(action, loc (F,3), yaw (F,), report, sol, Pw, J, frames, targets, wgt)."""
    fps, F = cfg["fps"], cfg["F"]
    times = np.arange(F) / fps
    legs = cfg["legs"]
    clips = [lg for lg in legs if lg["kind"] == "clip"]
    walks = [lg for lg in legs if lg["kind"] == "walk"]
    assert legs[0]["kind"] == "walk" and legs[-1]["kind"] == "walk" and len(walks) == len(clips) + 1
    box = cfg["box"]
    pu = cfg.get("palm_up", 0.02)
    fws = [fw_world(mir) for mir in (False, True)]
    for c in clips:
        c["_b"] = I.take(c["take"])
        c["_s"] = R.leg_ratio(rig, c["_b"])[0]
        takes_ = c["role"] in ("pick", "grab")  # takes hold (grasp .. lift) / lets go (release)
        c["_ev"] = c["grasp"] if takes_ else c["release"]
        c["_after"] = (c["lift"] if takes_ else c["release"]) - c["_ev"]  # event -> its post reference
    J = clips[0]["_b"]["J"]

    def hip(P_, i):
        return (P_[i, J["LeftHip"]] + P_[i, J["RightHip"]]) / 2

    def seg(c, T, t_ev):
        """Clip c placed in space (anchored at its event) for output times T, its event at output time t_ev."""
        grip = np.asarray(c["at"], float) + np.array([0, 0, pu])
        return clip_seg(c["_b"], c["_ev"] - 99, c["_ev"] + 99, c["_ev"], c["mirror"], c["_s"], c["yaw"], grip[:2],
                        np.asarray(T, float), t_ev - 99, c.get("behind", 0.0))

    def edge(c, pre=None, post=None):
        """(D, P, speed, dir, feat) of clip c's first frame (cut pre_s before its event) or last (post_s after)."""
        if pre is not None:
            D_, P_, _ = seg(c, [0.0, 1 / 60.0], pre)
            i0 = 0
        else:
            t_end = c["_after"] + post
            D_, P_, _ = seg(c, [t_end - 1 / 60.0, t_end], 0.0)
            i0 = 0
        dv = (hip(P_, 1) - hip(P_, 0))[:2]
        v_ = float(np.linalg.norm(dv)) * 60
        # the way on: its motion when it moves, the way the body faces when it (nearly) stands - a grab cut at the grab
        # gave a noise direction from 1/60 s of hip sway, the lead-out went sideways / back and the walk span him
        # 130 deg round and back with the cage (S2 bench f632-651, 31 Oct)
        yw_ = float(R.yaw_of(D_[1:2, J["Hips"]])[0])
        face = np.array([math.sin(yw_), -math.cos(yw_)])
        wv = float(I._smooth((v_ - 0.2) / 0.4))
        dd = dv / max(1e-9, np.linalg.norm(dv)) * wv + face * (1 - wv)
        return D_, P_, v_, dd / max(1e-9, np.linalg.norm(dd)), leg_feat(D_, P_, J, i0, 1 / 60.0)

    rep = dict(clips=[], walks=[])
    plan = []  # [(kind, t0, t1, payload)]
    # ---- clip 0: its event time is given; its cut before is matched against the first walk (anchored at its end)
    c0 = clips[0]
    best = None
    for pre in _rng(c0["pre_s"]):
        D_, P_, v_, d_, feat = edge(c0, pre=pre)
        for fw in fws:
            s_f, r_ = _fw_ratio(rig, fw, v_)
            m_ = match_fw(fw, feat, r_, s_f, c0["t"] - pre + 0.5, end=True)
            if best is None or m_[0] < best[0][0]:
                best = (m_, fw, r_, s_f, pre, P_, d_)
    m_, fw, r_, s_f, pre, P_, d_ = best
    c0["_pre"], c0["_t"] = pre, c0["t"]
    rt = route(list(walks[0]["route"]) + [hip(P_, 0)[:2] - d_ * c0.get("lead_in", 1.2), hip(P_, 0)[:2]])
    plan.append(("walk", 0.0, c0["t"] - pre, dict(fw=fw, i=m_[1], ratio=r_, s=s_f, rt=rt, t_anchor=c0["t"] - pre,
                                                   end=True, match=m_, carry=None)))
    # ---- each clip's cut after, the walk after it; that walk's arrival fixes the next clip's cut before and time
    for k, c in enumerate(clips):
        nxt = clips[k + 1] if k + 1 < len(clips) else None
        nxt_edges = {pre_n: edge(nxt, pre=pre_n) for pre_n in _rng(nxt["pre_s"])} if nxt is not None else {}
        best = None
        for post in _rng(c["post_s"]):
            D1, P1, v1, d1, feat1 = edge(c, post=post)
            t_end = c["_t"] + c["_after"] + post
            for fw in fws:
                s_f, r_ = _fw_ratio(rig, fw, v1)
                need = (times[-1] - t_end + 0.5) if nxt is None else 30.0
                m_ = match_fw(fw, feat1, r_, s_f, need, end=False)
                if m_[1] is None:
                    continue
                if nxt is None:
                    sc_ = m_[0]
                    cand = None
                else:  # the next clip's cut: the one whose first frame best matches the walk's arrival frame
                    fp, _ = fw_feats(fw)
                    arc = fw["arc"]
                    cand = None
                    for pre_n, (D2, P2, v2, d2, feat2) in nxt_edges.items():
                        rt_ = route([hip(P1, 1)[:2], hip(P1, 1)[:2] + d1 * c.get("lead_out", 1.0)]
                                    + list(walks[k + 1]["route"])
                                    + [hip(P2, 0)[:2] - d2 * nxt.get("lead_in", 1.2), hip(P2, 0)[:2]])
                        L = rt_[1][-1]
                        j = int(np.searchsorted(arc, arc[m_[1]] + L / s_f))
                        if j >= len(arc) - 3:
                            continue
                        d_arr = float(np.linalg.norm(_fw_feat_at(fw, j, r_, s_f) - feat2))
                        if cand is None or d_arr < cand[0]:
                            cand = (d_arr, pre_n, j, rt_, (j - m_[1]) / (r_ * fw["rate"]))
                    if cand is None:
                        continue
                    sc_ = m_[0] + cand[0]
                if best is None or sc_ < best[0]:
                    best = (sc_, m_, fw, r_, s_f, post, P1, d1, cand)
        _, m_, fw, r_, s_f, post, P1, d1, cand = best
        c["_post"] = post
        t_end = c["_t"] + c["_after"] + post
        plan.append(("clip", c["_t"] - c["_pre"], t_end, dict(c=c)))
        if nxt is None:
            rt = route([hip(P1, 1)[:2], hip(P1, 1)[:2] + d1 * c.get("lead_out", 1.0)] + list(walks[k + 1]["route"]))
            plan.append(("walk", t_end, times[-1] + 1.0, dict(fw=fw, i=m_[1], ratio=r_, s=s_f, rt=rt, t_anchor=t_end,
                                                                end=False, match=m_, carry=c if c["role"] in ("pick", "grab") else None)))
        else:
            d_arr, pre_n, j, rt, t_walk = cand
            nxt["_pre"] = pre_n
            nxt["_t"] = t_end + t_walk + pre_n
            plan.append(("walk", t_end, t_end + t_walk, dict(fw=fw, i=m_[1], ratio=r_, s=s_f, rt=rt, t_anchor=t_end,
                                                              end=False, match=m_, arrive_match=d_arr,
                                                              carry=c if c["role"] in ("pick", "grab") else None)))
        rep["clips"].append(dict(role=c["role"], take=c["take"], event_t=round(c["_t"], 2), pre_s=round(c["_pre"], 3),
                                 post_s=round(post, 3), mirror=c["mirror"]))
    # ---- assemble
    Dw = np.zeros((F, len(J), 3, 3))
    Pw = np.zeros((F, len(J), 3))
    owner = np.full(F, -1)
    for n_, (kind, ta, tb, pl) in enumerate(plan):
        m = (times >= ta - 1e-9) & (times < tb - 1e-9) if n_ < len(plan) - 1 else (times >= ta - 1e-9)
        if not m.any():
            continue
        sub = 0
        if kind == "walk":
            Dw[m], Pw[m], info_ = walk_seg(pl["fw"], pl["i"], pl["ratio"], pl["s"], pl["rt"], times[m], pl["t_anchor"],
                                           end=pl["end"])
            sub = info_["seg"] - info_["seg"].min()
            rep.setdefault("walk_joins", []).append(int(len(np.unique(info_["seg"])) - 1))
            if pl["carry"] is not None:  # the carry arms of the pick's last frame, held relative to the chest
                c = pl["carry"]
                Dl, _, _ = seg(c, [c["_t"] + c["_after"] + c["_post"]], c["_t"])
                hold_arms(Dw, J, Dl[0], np.nonzero(m)[0], keep=cfg.get("carry", {}).get("arm_keep", 0.0))
            rep["walks"].append(dict(t=[round(ta, 2), round(min(tb, times[-1]), 2)], mirror=pl["fw"]["mirror"],
                                     src_t=round(float(pl["fw"]["t"][pl["i"]]), 3), ratio=round(pl["ratio"], 3),
                                     leg_match=round(float(pl["match"][2]), 3),
                                     arrive_match=round(pl.get("arrive_match", 0.0), 3),
                                     route_m=round(float(pl["rt"][1][-1]), 2)))
        else:
            c = pl["c"]
            Dw[m], Pw[m], _ = seg(c, times[m], c["_t"])
        owner[m] = n_ * 1000 + sub
    inertialize(Dw, Pw, owner, fps, cfg.get("join_s", 0.4))
    # ---------------------------------------------------------------- avatar
    want = (Pw[:, J["LeftHip"]] + Pw[:, J["RightHip"]]) / 2
    sol = R.solve(rig, Dw, J, want)
    dz = R.floor_dz(rig, sol, cfg.get("lift", 0.0))
    Pw[:, :, 2] += dz
    lf_ = cfg.get("lift_f")  # (F,) extra lift where the mesh still dipped under the floor (joins), smoothed
    if lf_ is not None:
        sol["shift"][:, 2] += lf_
        sol["Hw"][:, :, 2] += lf_[:, None]
        Pw[:, :, 2] += lf_[:, None]
    for sd, sj in (("L", "LeftAnkle"), ("R", "RightAnkle")):
        R._foot_lock(sol["A"], sol["Hw"], sol["L"], rig["rest"], rig["par"], rig["bi"], sd,
                     R.contacts(Pw[:, J[sj]], fps), rig["MR"], fps)
    bi = rig["bi"]
    pm0 = I.palm_pts(sol, rig)
    # ---------------------------------------------------------------- held objects: each pick / grab clip takes one,
    # the next place / release clip lets it go (the carton; S2's roll cage pushed by its front posts)
    objs = []
    for c in clips:
        if c["role"] in ("pick", "grab"):
            spec = cfg.get("objects", {}).get(c.get("obj", "box"), cfg.get("box")) if c.get("obj") else cfg["box"]
            objs.append(dict(name=c.get("obj", "box"), spec=spec, take=c, give=None))
        elif objs and objs[-1]["give"] is None:
            objs[-1]["give"] = c
    mid = pm0.mean(1)
    Hw0 = sol["Hw"]
    # what a held object turns with: his shoulder line (the upper-arm heads, ~30 cm apart), not the palm-to-palm axis -
    # at the pick take's lift the source hands end up one in front of the other, 4 cm apart sideways, and that axis
    # flipped 137 deg in one frame: the carton jumped 0.46 m and the hands swapped sides round it (S2 bench f66-67,
    # found 31 Oct). Not the clavicle heads either: ~1-2 cm apart at the neck, ill-conditioned the same way (the
    # carton turned 145 deg in one frame on a corner, motion gate 05:45); not smoothed (a smoothed line lagged a
    # corner: carton 4 cm into a forearm)
    ax_ = Hw0[:, bi["Bip01 R UpperArm"]] - Hw0[:, bi["Bip01 L UpperArm"]]
    yh = np.unwrap(np.arctan2(ax_[:, 1], ax_[:, 0]))
    pel, sp2 = Hw0[:, bi["Bip01 Pelvis"]], Hw0[:, bi["Bip01 Spine2"]]
    tc = cfg.get("trunk_clear", 0.21)
    up = np.array([0, 0, 1.0])
    n_in, n_mid, n_fin = int(round(0.9 * fps)), int(round(0.5 * fps)), max(2, int(round(0.25 * fps)))
    n_off, n_back = max(2, int(round(0.25 * fps))), max(3, int(round(0.6 * fps)))
    n_down = max(2, int(round(0.4 * fps)))
    n_r = max(2, int(round(0.5 * fps)))
    # per frame, whichever object the hands are on (windows never overlap)
    tgt = {x: pm0[:, i].copy() for i, x in enumerate(("L", "R"))}
    wgt = np.zeros(F)
    Xv = np.tile(np.array([1.0, 0, 0]), (F, 1))
    Yv = np.tile(np.array([0.0, 1, 0]), (F, 1))
    cw = np.zeros(F)
    dn_f = np.zeros(F)
    ff_f = np.full(F, cfg.get("finger_flat", 1.0))
    eo_f = np.full(F, cfg.get("elbow_out", 0.25))
    pf_f = np.zeros(F)  # 1: palm forward round a post (fingers up), 0: palm on a side face
    rw_f = np.zeros(F)  # 1: let go and hanging - palm to the thigh, fingers down (review 021c P2: the palms kept
    # facing the carton's old faces as he turned away, out / forward at the hip)
    lean_cap = np.full(F, 28.0)  # deg (pushing a loaded cage: more)
    held = np.zeros(F, bool)
    lean_win = np.zeros(F, bool)
    ub_wins = []
    Hr = sol["Hw"]
    arm_len = {}
    for i_, x in enumerate(("L", "R")):
        ua, fa, hd = (bi[f"Bip01 {x} {n}"] for n in ("UpperArm", "Forearm", "Hand"))
        arm_len[x] = float(np.linalg.norm(Hr[0, fa] - Hr[0, ua]) + np.linalg.norm(Hr[0, hd] - Hr[0, fa])
                           + np.linalg.norm(pm0[0, i_] - Hr[0, hd]))

    def rest_pt(f, x):
        """Hanging beside the thigh after a release (inductor.build 018b): under the shoulder, elbow nearly straight."""
        lv = Hr[f, bi["Bip01 L Thigh"]] - Hr[f, bi["Bip01 R Thigh"]]
        lv[2] = 0
        lv /= np.linalg.norm(lv) + 1e-9
        fw_ = np.array([lv[1], -lv[0], 0.0])
        return Hr[f, bi[f"Bip01 {x} UpperArm"]] + lv * (0.02 if x == "L" else -0.02) + fw_ * 0.01 \
            + np.array([0, 0, -0.93 * arm_len[x]])  # (0.66 m: beyond this avatar's arm - the reach lean bent him over)

    for ob in objs:
        sp_o, tk, gv = ob["spec"], ob["take"], ob["give"]
        w_, d_, h_ = sp_o["dims"]
        g = int(round(tk["_t"] * fps))
        lf = int(round((tk["_t"] + tk["lift"] - tk["grasp"]) * fps))
        r_ = min(F - 1, int(round(gv["_t"] * fps))) if gv is not None else F - 1
        cr = sp_o.get("carry", cfg.get("carry", {})) if ob["name"] == "box" else sp_o.get("carry", {})
        pu_o = sp_o.get("palm_up", cfg.get("palm_up", 0.02))
        po = sp_o.get("palm_off", cfg.get("palm_off", 0.035))
        c0b = np.array(sp_o["c"], float)
        loc = np.tile(c0b, (F, 1))
        yaw = np.full(F, float(sp_o["yaw"]))
        # rigid with the palms from the grasp; the grasp offset drawn in to the palm midpoint by 0.6 s after the lift
        lf2 = min(F - 1, lf + int(round(0.6 * fps)))
        r_pl = r_ if gv is not None else F + 10 ** 6
        lead_ = 0.0 if sp_o.get("carry_to_give") else 1.6  # (a pushed cage stays where it is pushed from till let go)
        cw_o = np.array([float(I._smooth(min((f - lf2) / n_r, (r_pl - int(round(lead_ * fps)) - f) / n_r, 1.0)))
                         if lf2 <= f <= r_ else 0.0 for f in range(F)])
        if sp_o.get("carry_to_give"):  # from the grasp on (riding on the take's end-of-reach arms it was out of reach)
            cw_o = np.array([float(I._smooth((f - g) / n_r)) if g <= f <= r_ else 0.0 for f in range(F)])
        cw_l = cw_o.copy()  # where it is: snug till the give-up blend takes it (review 021b #3: from 1.6 s before
        # the release it followed the place take's own hands, captured at a lower table, under the store shelf)
        cw_h = cw_o.copy()  # the hands' carry shape (palm low, fingers hooked under): let go over the last 0.4 s only
        # (021b #3: from 1.6 s before the release the fingers opened palms-up beside it: "presenting a tray" again)
        if gv is not None and not sp_o.get("carry_to_give") and (cw_o >= 1.0 - 1e-6).any():
            f1_ = int(np.argmax(cw_o >= 1.0 - 1e-6))
            cw_l[f1_:r_ + 1] = 1.0
            n_h = max(2, int(round(0.4 * fps)))
            cw_h[f1_:r_ + 1] = [float(I._smooth(min(1.0, (r_ - f) / n_h))) for f in range(f1_, r_ + 1)]
        pu_f = pu_o + (cr.get("palm_up", pu_o) - pu_o) * cw_h
        off0 = c0b - mid[g]
        for f in range(g, F):
            u = float(I._smooth((f - g) / max(1, lf2 - g))) if sp_o.get("draw_in", True) else 0.0
            loc[f] = mid[f] + R.rz(yh[f] - yh[g])[0] @ (off0 * (1 - u) + np.array([0, 0, -pu_f[f]]) * u)
            yaw[f] = sp_o["yaw"] + yh[f] - yh[g]
        if sp_o.get("trunk", True):  # trunk clearance (the avatar's own mesh), ramped in from the grasp to the lift
            for f in range(g, F):
                fv = np.array([-math.sin(yaw[f]), math.cos(yaw[f]), 0.0])
                u = np.clip((loc[f][2] - pel[f][2]) / max(1e-3, sp2[f][2] - pel[f][2]), 0, 1)
                need = tc - float(np.dot((loc[f] - fv * (d_ / 2) - (pel[f] + (sp2[f] - pel[f]) * u))[:2], fv[:2]))
                if need > 0:
                    loc[f] = loc[f] + fv * need * float(I._smooth((f - g) / max(1, lf - g)))
        if sp_o.get("follow_body"):  # pushed: squared to his body (hip line, averaged over ~1 s: no gait wobble)
            lv_ = Hw0[:, bi["Bip01 L Thigh"]] - Hw0[:, bi["Bip01 R Thigh"]]
            by_ = np.unwrap(np.arctan2(-lv_[:, 1], -lv_[:, 0]))  # object +Y = his forward (the hip line lv points left)
            kk_ = np.exp(-0.5 * (np.arange(-int(fps), int(fps) + 1) / (0.25 * fps)) ** 2)
            by_ = np.convolve(np.pad(by_, len(kk_) // 2, mode="edge"), kk_ / kk_.sum(), mode="valid")
            for f in range(g, F):
                if cw_o[f] > 0:
                    dy_ = (by_[f] - yaw[f] + math.pi) % (2 * math.pi) - math.pi
                    yaw[f] = yaw[f] + dy_ * cw_o[f]
        if cr.get("above_pelvis") is not None:  # review 021 #2: carried snug against his torso, bobbing with him
            for f in range(g, F):
                if cw_l[f] <= 0:
                    continue
                fv = np.array([-math.sin(yaw[f]), math.cos(yaw[f]), 0.0])
                zt = pel[f][2] + cr["above_pelvis"]
                u = np.clip((zt - pel[f][2]) / max(1e-3, sp2[f][2] - pel[f][2]), 0, 1)
                sp_ = pel[f] + (sp2[f] - pel[f]) * u
                snug = np.array([sp_[0], sp_[1], zt]) + fv * (cr.get("snug_clear", tc + 0.01) + d_ / 2)
                loc[f] = loc[f] + (snug - loc[f]) * cw_l[f]
        if gv is not None:  # into the give-up pose over the last give_s (0.8 s; the hands follow), then it stays
            n_pl = int(round(sp_o.get("give_s", 0.8) * fps))
            pc_ = np.asarray(gv["at"], float)
            lz_ = sp_o.get("give_rise", 1.0)  # < 1: up to the shelf's height in that part of the blend, in over it
            for f in range(max(g, r_ - n_pl), r_ + 1):  # after (021b #3: a straight line crossed its front edge low)
                u = float(I._smooth((f - (r_ - n_pl)) / n_pl))
                uz = float(I._smooth(min(1.0, (f - (r_ - n_pl)) / max(1.0, lz_ * n_pl))))
                dy = (gv["yaw"] - yaw[f] + math.pi) % (2 * math.pi) - math.pi
                if sp_o.get("symmetric", True):
                    dy = dy if abs(dy) <= math.pi / 2 else dy - math.copysign(math.pi, dy)  # same turned 180
                loc[f] = loc[f] + (pc_ - loc[f]) * np.array([u, u, uz])
                yaw[f] = yaw[f] + dy * u
            loc[r_ + 1:] = loc[r_]
            yaw[r_ + 1:] = yaw[r_]
        if sp_o.get("fix_z", False):  # rolls on the floor: the grip stays at its height (no gait bob)
            loc[:, 2] = c0b[2]
        if sp_o.get("cage") is not None:  # never down into the pick shelf while over it
            x0, y0, x1, y1 = sp_o["cage"]
            for f in range(g, F):
                if x0 <= loc[f][0] <= x1 and y0 - 0.05 <= loc[f][1] <= y1:
                    loc[f][2] = max(loc[f][2], sp_o["support_z"] + h_ / 2)
        if sp_o.get("supports"):  # never into a shelf it is set down on (review 021b #3: the place dipped 7 cm into
            # the store shelf before the release): where its footprint is over one, its bottom stays on or above the
            # top; the lift spread over +-0.3 s so it comes up smoothly, never jumps
            need = np.zeros(F)
            for f in range(g, F):
                ex = 0.5 * (abs(w_ * math.cos(yaw[f])) + abs(d_ * math.sin(yaw[f])))
                ey = 0.5 * (abs(w_ * math.sin(yaw[f])) + abs(d_ * math.cos(yaw[f])))
                for x0, y0, x1, y1, zt in sp_o["supports"]:
                    if loc[f][0] + ex > x0 and loc[f][0] - ex < x1 and loc[f][1] + ey > y0 and loc[f][1] - ey < y1:
                        need[f] = max(need[f], zt + h_ / 2 - loc[f][2])
            need = np.clip(need, 0.0, None)
            if need.any():
                k_ = np.exp(-0.5 * (np.arange(-3, 4) / 1.5) ** 2)
                raw = need.copy()
                pad_ = np.pad(need, 3)  # weighted max over the next 3 frames: it rises before it gets over the edge,
                # never stays up after (a convolution summed them; +-3 frames left a 13 mm bump over the board)
                need = np.max([pad_[3 + j:3 + j + F] * k_[3 + j] for j in range(0, 4)], axis=0)
                need[:g] = 0.0
                if gv is not None:  # set down exactly on the top: no smoothing lift left at the release
                    need[max(g, r_ - 2):r_ + 1] = raw[max(g, r_ - 2):r_ + 1]
                if gv is not None:
                    need[r_ + 1:] = need[r_]
                loc[:, 2] = loc[:, 2] + need
            rep.setdefault("support_lift_mm_max", {})[ob["name"]] = round(float(need.max()) * 1000, 1)
            rep.setdefault("support_lift_frames", {})[ob["name"]] = [
                [int(f) + cfg.get("frame0", 1), round(float(need[f]) * 1000, 1)] for f in np.nonzero(need > 0.002)[0]][:40]
        Xo = np.stack([np.cos(yaw), np.sin(yaw), np.zeros(F)], 1)
        Yo = np.stack([-np.sin(yaw), np.cos(yaw), np.zeros(F)], 1)
        posts = sp_o.get("grip") == "posts"  # a cage: each hand round a front post from behind, palm forward
        if posts:
            sock = {"L": loc - Xo * (w_ / 2) - Yo * po + up[None] * pu_f[:, None],
                    "R": loc + Xo * (w_ / 2) - Yo * po + up[None] * pu_f[:, None]}
            nrm = {"L": -Yo, "R": -Yo}  # approached from behind (his side)
        else:
            sock = {"L": loc - Xo * (w_ / 2 + po) + up[None] * pu_f[:, None],
                    "R": loc + Xo * (w_ / 2 + po) + up[None] * pu_f[:, None]}
            nrm = {"L": -Xo, "R": Xo}  # outward face normals
        n_rest = int(round((gv.get("rest_s", 1.6) if gv is not None else 0.0) * fps))
        end_ = (r_ + n_off + n_down + n_rest + n_back) if gv is not None else F - 1
        for f in range(max(0, g - n_in), min(F, end_ + 1)):
            for x in ("L", "R"):
                P2 = sock[x][g] + nrm[x][g] * 0.06
                P1 = P2 - Yo[g] * 0.14 if not posts else P2 + nrm[x][g] * 0.08
                if f < g - n_mid:  # approach: beside-and-in-front of the end face, along it, then in along the normal
                    w = float(I._smooth((f - (g - n_in)) / max(1, n_in - n_mid)))
                    tgt[x][f] = tgt[x][f] + w * (P1 - tgt[x][f])
                elif f < g - n_fin:
                    w = 1.0
                    tgt[x][f] = P1 + (P2 - P1) * float(I._smooth((f - (g - n_mid)) / max(1, n_mid - n_fin)))
                elif f < g:
                    w = 1.0
                    tgt[x][f] = sock[x][g] + nrm[x][g] * 0.06 * (g - f) / n_fin
                elif f <= r_:
                    w = 1.0
                    tgt[x][f] = sock[x][f]
                elif f <= r_ + n_off:  # release: off the faces (out 6 cm, up 3 cm)
                    w = 1.0
                    u = float(I._smooth((f - r_) / n_off))
                    tgt[x][f] = sock[x][r_] + (nrm[x][r_] * 0.06 + up * 0.03) * u
                elif f <= r_ + n_off + n_down:  # back towards the body, then down beside the thighs
                    w = 1.0
                    u = float(I._smooth((f - r_ - n_off) / n_down))
                    off_ = sock[x][r_] + nrm[x][r_] * 0.06 + up * 0.03 - Yo[r_] * 0.12 * min(1.0, u * 2)
                    tgt[x][f] = off_ + (rest_pt(f, x) - off_) * float(I._smooth((u - 0.3) / 0.7))
                elif f <= r_ + n_off + n_down + n_rest:  # hanging while he stands and turns away
                    w = 1.0
                    tgt[x][f] = rest_pt(f, x)
                else:  # back to the captured arms
                    w = 1.0 - float(I._smooth((f - r_ - n_off - n_down - n_rest) / n_back))
                    i_ = 0 if x == "L" else 1
                    tgt[x][f] = pm0[f, i_] + w * (rest_pt(f, x) - pm0[f, i_])
                wgt[f] = max(wgt[f], w)
        win = slice(max(0, g - n_in), min(F, end_ + 1))
        if gv is not None:
            for f in range(r_ + n_off, min(F, end_ + 1)):
                rw_f[f] = max(rw_f[f], min(float(I._smooth((f - r_ - n_off) / max(1, n_down))),
                                           1.0 - float(I._smooth((f - (end_ - n_back)) / max(1, n_back)))))
        Xv[win], Yv[win], cw[win] = Xo[win], Yo[win], cw_h[win]
        dn_f[win] = np.radians(cr.get("finger_down_deg", 0.0)) * cw_h[win]
        ff_f[win] = sp_o.get("finger_flat", cfg.get("finger_flat", 1.0)) + (
            cr.get("finger_flat", sp_o.get("finger_flat", cfg.get("finger_flat", 1.0)))
            - sp_o.get("finger_flat", cfg.get("finger_flat", 1.0))) * cw_h[win]
        eo_f[win] = sp_o.get("elbow_out", cfg.get("elbow_out", 0.25))
        pf_f[win] = 1.0 if posts else 0.0
        lean_cap[win] = sp_o.get("lean_cap", 28.0)
        held[g:r_ + 1] = True
        lean_win[max(0, g - n_in):min(F, r_ + n_off + 1)] = True
        ub_wins += [(g - n_in, lf + int(0.5 * fps))] + ([(r_ - int(1.0 * fps), r_ + n_off)] if gv is not None else [])
        ob.update(loc=loc, yaw=yaw, g=g, lf=lf, r=r_, given=gv is not None, cw=cw_h, posts=posts,
                  hook=cr.get("hook", False))
    # ---------------------------------------------------------------- upper body: straighten up where the hold is higher
    # than the captured hands (take and give windows), lean in where the arms can't reach (inductor.build's rules)
    Hw = sol["Hw"]
    sp1 = bi["Bip01 Spine1"]
    ub = np.zeros(F)
    for a_, b_ in ub_wins:
        for f in range(max(0, a_), min(F, b_)):
            dzn = 0.5 * ((tgt["L"][f][2] - pm0[f, 0, 2]) + (tgt["R"][f][2] - pm0[f, 1, 2]))
            if dzn > 0.03 and wgt[f] > 0:
                lever = max(0.2, Hw[f, bi["Bip01 L UpperArm"], 2] - Hw[f, sp1, 2])
                ub[f] = min(math.radians(25), (dzn - 0.03) / lever) * wgt[f]
    if ub.any():
        k_ = np.exp(-0.5 * (np.arange(-5, 6) / 2.0) ** 2)
        ub = np.convolve(ub, k_ / k_.sum(), mode="same")
        I._pivot(sol, rig, "Bip01 Spine1", ub, backward=True)
    rep["unstoop_deg_max"] = round(float(np.degrees(ub.max())), 1)
    Hw = sol["Hw"]
    reach = {}
    pc0 = I.palm_pts(sol, rig)
    for i_, x in enumerate(("L", "R")):
        ua, fa, hd = (bi[f"Bip01 {x} {n}"] for n in ("UpperArm", "Forearm", "Hand"))
        reach[x] = float(np.linalg.norm(Hw[0, fa] - Hw[0, ua]) + np.linalg.norm(Hw[0, hd] - Hw[0, fa])
                         + np.linalg.norm(pc0[0, i_] - Hw[0, hd]))
    th = np.zeros(F)
    for f in range(F):
        if wgt[f] <= 0 or not lean_win[f]:  # only for what he holds (never for the hands' rest)
            continue
        need = max(np.linalg.norm(tgt[x][f] - Hw[f, bi[f"Bip01 {x} UpperArm"]]) - 0.96 * reach[x] for x in ("L", "R"))
        if need > 0:
            lever = max(0.2, Hw[f, bi["Bip01 L UpperArm"], 2] - Hw[f, sp1, 2])
            th[f] = min(math.radians(lean_cap[f]), need / lever * 1.15)
    if th.any():
        k_ = np.exp(-0.5 * (np.arange(-4, 5) / 1.5) ** 2)
        th = np.maximum(np.convolve(th, k_ / k_.sum(), mode="same"), th)
        I._pivot(sol, rig, "Bip01 Spine1", th)
    rep["lean_deg_max"] = round(float(np.degrees(th.max())), 1)
    rep["lean_deg_by_obj"] = {}  # which reach it was (review 021b #2): [max deg, frames over 20 deg as runs]
    for ob in objs:
        w_ = slice(max(0, ob["g"] - n_in), min(F, ob["r"] + n_off + 1))
        thd = np.degrees(th[w_])
        over = np.nonzero(thd > 20.0)[0] + w_.start + cfg.get("frame0", 1)
        rep["lean_deg_by_obj"][ob["name"]] = [round(float(thd.max()), 1) if thd.size else 0.0,
                                             [int(over[0]), int(over[-1])] if over.size else None]
    # ---------------------------------------------------------------- palms flat on the faces, fingers along them
    k = wgt > 1e-6
    for x, sgn in (("L", 1.0), ("R", -1.0)):
        Hw = sol["Hw"]
        hd = bi[f"Bip01 {x} Hand"]
        n_ = _palm_n(sol, rig, x, np.ones(F, bool))
        fd = Hw[:, bi[f"Bip01 {x} Finger2"]] - Hw[:, hd]
        fd /= np.linalg.norm(fd, axis=1, keepdims=True)
        nd, fdd = sgn * Xv, Yv * np.cos(dn_f)[:, None] - up[None] * np.sin(dn_f)[:, None]  # carried: fingers turned down
        nd = nd * (1 - pf_f)[:, None] + Yv * pf_f[:, None]  # round a post: palm forward, fingers up
        fdd = fdd * (1 - pf_f)[:, None] + up[None] * pf_f[:, None]
        lat_ = Hw[:, bi["Bip01 L Thigh"]] - Hw[:, bi["Bip01 R Thigh"]]  # let go: palm to the thigh, fingers down
        lat_[:, 2] = 0.0
        lat_ /= np.linalg.norm(lat_, axis=1, keepdims=True) + 1e-12
        nd = nd * (1 - rw_f)[:, None] - sgn * lat_ * rw_f[:, None]
        fdd = fdd * (1 - rw_f)[:, None] - up[None] * rw_f[:, None]
        nd /= np.linalg.norm(nd, axis=1, keepdims=True) + 1e-12
        Fc = np.stack([fd, n_, np.cross(fd, n_)], 2)
        fdd_o = fdd - np.sum(fdd * nd, 1)[:, None] * nd
        fdd_o /= np.linalg.norm(fdd_o, axis=1, keepdims=True) + 1e-12
        Fd = np.stack([fdd_o, nd, np.cross(fdd_o, nd)], 2)
        Rw = np.einsum("fij,fkj->fik", Fd[k], Fc[k])
        _turn(sol, rig, k, hd, I._rotexp(I._rotlog(Rw) * np.clip(wgt[k], 0, 1)[:, None]))
    # fingers: the bind curl relaxed towards straight while on it (finger_flat < 1 keeps some curl: they wrap round its
    # edge / round a post), tips towards the palm plane by the same weight, thumb into it
    wf = np.clip(wgt, 0, 1) * ff_f
    for nm_, i in bi.items():
        if "Finger" in nm_ and nm_.split()[1] in ("L", "R"):
            w_f = np.clip(wgt, 0, 1) if nm_.split()[2].startswith("Finger0") else wf
            sol["L"][:, i] = I._rotexp((1 - w_f[:, None]) * I.I_log(rig["LT"][i])[None])
            sol.setdefault("keyed", set()).add(i)
    for x in ("L", "R"):
        I.fk_desc(sol, rig, bi[f"Bip01 {x} Hand"])
    for x in ("L", "R"):
        Hw = sol["Hw"]
        nf = _palm_n(sol, rig, x, k)
        for f_ in (1, 2, 3, 4):
            b_, m_, l_ = (bi[f"Bip01 {x} Finger{f_}{s_}"] for s_ in ("", "1", "2"))
            v = Hw[k, l_] + (Hw[k, l_] - Hw[k, m_]) * 0.9 - Hw[k, b_]
            Rw = R._swing_np(v, v - nf * np.maximum(np.sum(v * nf, 1), 0.0)[:, None])
            _turn(sol, rig, k, b_, I._rotexp(I._rotlog(Rw) * wf[k][:, None]))
        d0 = Hw[k, bi[f"Bip01 {x} Finger02"]] - Hw[k, bi[f"Bip01 {x} Finger0"]]
        Rw = R._swing_np(d0, d0 - np.maximum(np.sum(d0 * nf, 1), 0.0)[:, None] * nf)
        _turn(sol, rig, k, f"Bip01 {x} Finger0", I._rotexp(I._rotlog(Rw) * np.clip(wgt[k], 0, 1)[:, None]))
    # ---------------------------------------------------------------- arm IK (elbows down and out)
    for i, x in enumerate(("L", "R")):
        sg = -1.0 if x == "L" else 1.0
        pole = (Xv * sg * eo_f[:, None] + np.array([0, 0, -cfg.get("elbow_down", 0.5)])) * wgt[:, None]
        pc = I.palm_pts(sol, rig)[:, i]
        P = sol["Hw"][:, bi[f"Bip01 {x} Hand"]] + (tgt[x] - pc)
        I.two_bone(sol, rig, (f"Bip01 {x} UpperArm", f"Bip01 {x} Forearm", f"Bip01 {x} Hand"), P, wgt, pole)
    pc = I.palm_pts(sol, rig)
    # safety net (inductor.build): where an arm fell short while holding, the object follows by the two hands' mean
    # shortfall (a rolling one only sideways); after the release it stays where it was let go
    sh = 0.5 * ((pc[:, 0] - tgt["L"]) + (pc[:, 1] - tgt["R"]))
    sh[~held] = 0.0
    rep["reach_fix_mm_max"] = round(float(np.linalg.norm(sh, axis=1).max()) * 1000, 1)
    for ob in objs:
        s_o = sh.copy()
        s_o[np.arange(F) < ob["g"]] = 0.0
        s_o[np.arange(F) > ob["r"]] = 0.0
        if ob["spec"].get("fix_z", False):
            s_o[:, 2] = 0.0
        ob["loc"] = ob["loc"] + s_o
        if ob["spec"].get("grip") == "posts":  # held round its posts: it goes where both hands are (midpoint + the
            # palm offset, square to the line through them) - a mean shift left one hand 3-4 cm off its post
            po_ = ob["spec"].get("palm_off", 0.035)
            for f in range(ob["g"] + 1, ob["r"] + 1):
                a_, b_ = pc[f, 0], pc[f, 1]
                xa = (b_ - a_)
                xa[2] = 0.0
                xa /= np.linalg.norm(xa) + 1e-9
                ya = np.array([-xa[1], xa[0], 0.0])
                m_ = 0.5 * (a_ + b_) + ya * po_
                if ob["spec"].get("fix_z", False):
                    m_[2] = ob["loc"][f][2]
                ob["loc"][f] = m_
                ob["yaw"][f] = math.atan2(xa[1], xa[0])
            ob["yaw"] = np.unwrap(ob["yaw"])
        if ob["given"]:
            ob["loc"][ob["r"] + 1:] = ob["loc"][ob["r"]]
            ob["yaw"][ob["r"] + 1:] = ob["yaw"][ob["r"]]
    for x in ("L", "R"):
        tgt[x] = np.where(held[:, None], tgt[x] + sh, tgt[x])
    def runs_(lst):  # contiguous runs of short frames: [first, last, worst m]
        out_, cur_ = [], None
        for f_, d_ in lst:
            if cur_ and f_ == cur_[1] + 1:
                cur_[1], cur_[2] = f_, max(cur_[2], d_)
            else:
                cur_ = [f_, f_, d_]
                out_.append(cur_)
        return out_
    for ob in objs:  # held round posts: the target is where the refitted posts are
        if ob["spec"].get("grip") == "posts":
            w_o = ob["spec"]["dims"][0]
            po_ = ob["spec"].get("palm_off", 0.035)
            for f in range(ob["g"], ob["r"] + 1):
                X_ = np.array([math.cos(ob["yaw"][f]), math.sin(ob["yaw"][f]), 0.0])
                Y_ = np.array([-X_[1], X_[0], 0.0])
                tgt["L"][f] = ob["loc"][f] - X_ * w_o / 2 - Y_ * po_
                tgt["R"][f] = ob["loc"][f] + X_ * w_o / 2 - Y_ * po_
                tgt["L"][f][2] = pc[f, 0, 2]
                tgt["R"][f][2] = pc[f, 1, 2]
    # ---------------------------------------------------------------- carried: fingers hooked under the bottom edge
    # (review 021b #1: no "presenting a tray"). On the final arms and the final object pose, per finger the first
    # joint below the bottom edge (minus the finger's radius) flexes towards the palm (into the plane of the finger
    # and the palm normal) so the rest of the finger runs in under the carton, its tip up to touch the bottom; the
    # joints after it go straight on. The thumb lies flat on the end face (palm plane), never out to the side.
    rf = cfg.get("finger_r", 0.009)
    hook_rep = {}
    for ob in objs:
        if ob["posts"] or not ob["hook"]:
            continue
        hw = np.where(held, ob["cw"], 0.0)
        k = hw > 1e-3
        if not k.any():
            continue
        h_ = ob["spec"]["dims"][2]
        zb = ob["loc"][k, 2] - h_ / 2
        Xo = np.stack([np.cos(ob["yaw"][k]), np.sin(ob["yaw"][k]), np.zeros(int(k.sum()))], 1)
        nh = {}
        for x in ("L", "R"):
            n_in = Xo if x == "L" else -Xo
            npm = _palm_n(sol, rig, x, k)
            for f_ in (1, 2, 3, 4):
                ch = [bi[f"Bip01 {x} Finger{f_}{s_}"] for s_ in ("", "1", "2")]
                done = np.zeros(int(k.sum()), bool)  # hooked at an earlier joint: this one goes straight on
                for j, b_ in enumerate(ch):
                    Hw = sol["Hw"]
                    hd_ = Hw[k, b_]
                    nxt = Hw[k, ch[j + 1]] if j < 2 else Hw[k, b_] + (Hw[k, b_] - Hw[k, ch[1]]) * 0.9
                    v = nxt - hd_
                    tip = Hw[k, ch[2]] + (Hw[k, ch[2]] - Hw[k, ch[1]]) * 0.9
                    lrem = np.linalg.norm(tip - hd_, axis=1)
                    if j > 0:
                        par_d = hd_ - Hw[k, ch[j - 1]]
                    here = (~done) & (hd_[:, 2] < zb - rf)
                    d = n_in * lrem[:, None] + np.array([0, 0, 1.0]) * np.clip(zb - rf - hd_[:, 2], 0, None)[:, None]
                    if j > 0:
                        d = np.where(done[:, None], par_d, d)
                    # flexion only: d in the plane of the finger and the palm normal, towards the palm
                    vn = v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-12)
                    nn = npm - np.sum(npm * vn, 1)[:, None] * vn
                    nn /= np.linalg.norm(nn, axis=1, keepdims=True) + 1e-12
                    dp = np.sum(d * vn, 1)[:, None] * vn + np.maximum(np.sum(d * nn, 1), 0.0)[:, None] * nn
                    ang = np.arctan2(np.sum(dp * nn, 1), np.sum(dp * vn, 1))
                    ang = np.clip(ang, 0.0, math.radians(100))
                    act = here | done
                    a_w = np.where(act, ang, 0.0) * hw[k]
                    if not act.any():
                        continue
                    ax = np.cross(vn, nn)
                    Rw = I._rotexp(ax * a_w[:, None])
                    _turn(sol, rig, k, b_, Rw)
                    nh[(x, f_)] = nh.get((x, f_), 0) + int(here.sum())
                    done |= here
            # thumb flat on the face: its whole n component removed (in or out)
            Hw = sol["Hw"]
            t0, t2 = bi[f"Bip01 {x} Finger0"], bi[f"Bip01 {x} Finger02"]
            d0 = Hw[k, t2] - Hw[k, t0]
            npm = _palm_n(sol, rig, x, k)
            Rw = R._swing_np(d0, d0 - np.sum(d0 * npm, 1)[:, None] * npm)
            _turn(sol, rig, k, t0, I._rotexp(I._rotlog(Rw) * hw[k][:, None]))
        # how far each fingertip is from the bottom face (signed, + below) and in from the end face, while carried
        Hw = sol["Hw"]
        full = hw[k] > 0.99
        tips = []
        for x in ("L", "R"):
            n_in = Xo if x == "L" else -Xo
            for f_ in (1, 2, 3, 4):
                b1, b2 = bi[f"Bip01 {x} Finger{f_}1"], bi[f"Bip01 {x} Finger{f_}2"]
                tip = Hw[k, b2] + (Hw[k, b2] - Hw[k, b1]) * 0.9
                face = ob["loc"][k] - n_in * ob["spec"]["dims"][0] / 2
                tips.append(np.stack([zb - tip[:, 2], np.sum((tip - face) * n_in, 1)], 1))
        tips = np.stack(tips, 1)[full]
        hook_rep[ob["name"]] = dict(frames=int(full.sum()),
                                    tip_below_bottom_mm_min_max=[round(float(tips[..., 0].min()) * 1000, 1),
                                                                  round(float(tips[..., 0].max()) * 1000, 1)],
                                    tip_in_from_face_mm_min_max=[round(float(tips[..., 1].min()) * 1000, 1),
                                                                  round(float(tips[..., 1].max()) * 1000, 1)],
                                    hooked_frames_per_finger={f"{a}{b}": c for (a, b), c in sorted(nh.items())})
    rep["hook"] = hook_rep
    err = np.maximum(np.linalg.norm(pc[:, 0] - tgt["L"], axis=1), np.linalg.norm(pc[:, 1] - tgt["R"], axis=1))
    rep["palm_err_mm_max_held"] = round(float(err[held].max()) * 1000, 1) if held.any() else None
    rep["palm_err_mm_p95_held"] = round(float(np.percentile(err[held], 95)) * 1000, 1) if held.any() else None
    bad_ = [(int(f), float(err[f])) for f in range(F) if held[f] and err[f] > 0.01]
    rep["palm_err_runs_over_10mm"] = [[a_ + cfg.get("frame0", 1), b_ + cfg.get("frame0", 1), round(m_ * 1000, 1)]
                                      for a_, b_, m_ in runs_(bad_)][:30]
    rep["ik_short"] = {k_: [v_[0], round(v_[1], 4), runs_(v_[4])[:20]] for k_, v_ in sol.get("ik_short", {}).items()}
    frames = cfg.get("frame0", 1) + np.arange(F)
    act = R.write(rig, sol, frames, cfg.get("name", "remover"))
    o0 = objs[0]
    rep["frames"] = dict(grasp=int(frames[o0["g"]]), lift=int(frames[min(F - 1, o0["lf"])]),
                         release=(int(frames[o0["r"]]) if o0["given"] else None),
                         objects={ob["name"]: dict(take=int(frames[ob["g"]]),
                                                   give=(int(frames[ob["r"]]) if ob["given"] else None)) for ob in objs},
                         segments=[(kind, int(frames[0] + round(ta * fps)), int(frames[0] + round(min(tb, times[-1]) * fps)))
                                   for kind, ta, tb, _ in plan])
    return dict(action=act, loc=o0["loc"], yaw=o0["yaw"], objects={ob["name"]: (ob["loc"], ob["yaw"]) for ob in objs},
                report=rep, sol=sol, Pw=Pw, J=J, frames=frames, targets=tgt, wgt=wgt)
