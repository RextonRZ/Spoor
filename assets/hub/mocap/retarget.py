"""M2 (014_GO): retarget Xsens-skeleton BVH (AndyData, 100STYLE: same 22 joints) onto a Rocketbox Bip01 rig.

World-space, at a shared T-pose:
  1. the BVH rest IS a T-pose (offsets only, zero rotations). The avatar is put in the SAME pose: every mapped bone is
     swung (shortest arc about its head, no twist) so its head->child direction equals the BVH rest segment direction;
     unmapped bones (fingers, face) keep the relaxed static pose of rb_tpose (M1).
  2. per frame, each source joint's world rotation relative to its rest, D(t) = C G(t) C^T (C: Y-up cm -> Z-up m),
     is applied to the matching bone's T-pose world rotation: A(t) = D(t) A_T. Local pose rotations follow from the
     rest matrices, so hierarchy differences (Biped thighs hang off Bip01 Spine, clavicles off Neck) don't matter.
  3. root: Bip01 Pelvis (the FBX importer turns the Biped's Bip01 node into the armature object). Its location is
     solved per frame so the midpoint of the thigh heads sits on the source hip midpoint scaled by the leg-length
     ratio (spine flexion would otherwise swing the hips: they hang 12 cm below the spine head); one vertical
     constant puts the ankles' low percentile on their rest height (no floor assumption about the source).
  4. quaternions, hemisphere-continuous, written in bulk (foreach_set) into one action.

  blender -b --factory-startup -P assets/hub/mocap/retarget.py -- --bvh <file> --avatar Male_Adult_04
          --t0 30.5 --t1 40.5 --out qa/review/m2 [--fps 30] [--render]
"""
import math
import re
import sys
from pathlib import Path

import numpy as np

# ------------------------------------------------------------------------------------------------ BVH (numpy)
C = np.array([[1.0, 0, 0], [0, 0, -1.0], [0, 1.0, 0]])  # BVH (x, y up, z fwd) cm -> Blender (x, -z, y)
MAP = {  # source joint -> target bone, and the source child that defines its direction
    "Hips": ("Bip01 Pelvis", "Chest"), "Chest": ("Bip01 Spine", "Chest2"), "Chest2": ("Bip01 Spine1", "Chest3"),
    "Chest4": ("Bip01 Spine2", "Neck"), "Neck": ("Bip01 Neck", "Head"), "Head": ("Bip01 Head", None),
}
for _s, _S in (("Left", "L"), ("Right", "R")):
    MAP.update({f"{_s}Collar": (f"Bip01 {_S} Clavicle", f"{_s}Shoulder"),
                f"{_s}Shoulder": (f"Bip01 {_S} UpperArm", f"{_s}Elbow"),
                f"{_s}Elbow": (f"Bip01 {_S} Forearm", f"{_s}Wrist"),
                f"{_s}Wrist": (f"Bip01 {_S} Hand", "_end"),
                f"{_s}Hip": (f"Bip01 {_S} Thigh", f"{_s}Knee"), f"{_s}Knee": (f"Bip01 {_S} Calf", f"{_s}Ankle"),
                f"{_s}Ankle": (f"Bip01 {_S} Foot", f"{_s}Toe"), f"{_s}Toe": (f"Bip01 {_S} Toe0", None)})
ALONG = {"Bip01 Pelvis": "Bip01 Spine", "Bip01 Spine": "Bip01 Spine1", "Bip01 Spine1": "Bip01 Spine2",
         "Bip01 Spine2": "Bip01 Neck", "Bip01 Neck": "Bip01 Head"}
for _S in ("L", "R"):
    ALONG.update({f"Bip01 {_S} Clavicle": f"Bip01 {_S} UpperArm", f"Bip01 {_S} UpperArm": f"Bip01 {_S} Forearm",
                  f"Bip01 {_S} Forearm": f"Bip01 {_S} Hand", f"Bip01 {_S} Hand": f"Bip01 {_S} Finger2",
                  f"Bip01 {_S} Thigh": f"Bip01 {_S} Calf", f"Bip01 {_S} Calf": f"Bip01 {_S} Foot",
                  f"Bip01 {_S} Foot": f"Bip01 {_S} Toe0"})


def read_bvh(path):
    txt = Path(path).read_text(encoding="utf-8", errors="replace")
    head, motion = txt.split("MOTION", 1)
    names, parents, offs, chans, ends = [], [], [], [], {}
    stack, cur = [], None
    for tok in re.finditer(r"(ROOT|JOINT)\s+(\S+)|End Site|OFFSET\s+(\S+)\s+(\S+)\s+(\S+)|CHANNELS\s+\d+\s+([^\n]+)|\{|\}",
                           head):
        t = tok.group(0)
        if tok.group(1):
            names.append(tok.group(2))
            parents.append(stack[-1] if stack else -1)
            offs.append(None)
            chans.append([])
            cur = ("j", len(names) - 1)
        elif t == "End Site":
            cur = ("e", stack[-1])
        elif t.startswith("OFFSET"):
            v = [float(tok.group(k)) for k in (3, 4, 5)]
            if cur[0] == "j":
                offs[cur[1]] = v
            else:
                ends[cur[1]] = v
        elif t.startswith("CHANNELS"):
            chans[cur[1]] = tok.group(6).split()
        elif t == "{":
            stack.append(cur[1] if cur[0] == "j" else -2)
        elif t == "}":
            stack.pop()
    m = re.search(r"Frames:\s*(\d+)\s*Frame Time:\s*([\d.eE+-]+)", motion)
    data = np.loadtxt(motion[m.end():].strip().splitlines(), dtype=np.float64, ndmin=2)
    return dict(names=names, parents=parents, offs=np.array(offs), chans=chans, ends=ends, data=data,
                dt=float(m.group(2)))


def _rot(axis, deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    R = np.zeros(a.shape + (3, 3))
    i = "XYZ".index(axis)
    j, k = (i + 1) % 3, (i + 2) % 3
    R[..., i, i] = 1
    R[..., j, j] = c
    R[..., k, k] = c
    R[..., j, k] = -s
    R[..., k, j] = s
    return R


def fk(b, rows):
    """Global rotations (F,J,3,3) and positions (F,J,3) in BVH space (cm) for the given motion rows."""
    D = b["data"][rows]
    F, J = len(rows), len(b["names"])
    G = np.zeros((F, J, 3, 3))
    P = np.zeros((F, J, 3))
    col = 0
    for j in range(J):
        R = np.broadcast_to(np.eye(3), (F, 3, 3)).copy()
        pos = None
        for ch in b["chans"][j]:
            if ch.endswith("position"):
                pos = D[:, col] if pos is None else pos
                if ch[0] == "X":
                    px = D[:, col]
                elif ch[0] == "Y":
                    py = D[:, col]
                else:
                    pz = D[:, col]
            else:
                R = R @ _rot(ch[0], D[:, col])
            col += 1
        p = b["parents"][j]
        if p < 0:
            G[:, j] = R
            P[:, j] = np.stack([px, py, pz], 1) + b["offs"][j]
        else:
            G[:, j] = G[:, p] @ R
            P[:, j] = P[:, p] + np.einsum("fij,j->fi", G[:, p], b["offs"][j])
    return G, P


def sample(b, times, fps, sigma=None):
    """Low-pass + resample in one step (review 014c #2: never drop source frames): every output time takes a Gaussian
    (sigma = 0.5 / fps) over ALL source frames within 3 sigma; positions are averaged, rotations take the weighted
    chordal mean projected back onto SO(3) (SVD), i.e. the rotation low-pass, evaluated at fractional times."""
    sigma = sigma or 0.5 / fps
    rate, n = 1.0 / b["dt"], len(b["data"])
    a = max(0, int((np.min(times) - 3 * sigma) * rate))  # times need not be sorted
    z = min(n - 1, int((np.max(times) + 3 * sigma) * rate) + 1)
    rows = np.arange(a, z + 1)
    G, P = fk(b, rows)
    tr = rows * b["dt"]
    Go = np.zeros((len(times),) + G.shape[1:])
    Po = np.zeros((len(times),) + P.shape[1:])
    for k, t in enumerate(times):
        m = np.abs(tr - t) <= 3 * sigma
        if not m.any():
            m = np.abs(tr - t) == np.abs(tr - t).min()
        w = np.exp(-0.5 * ((tr[m] - t) / sigma) ** 2)
        w /= w.sum()
        Po[k] = np.einsum("f,fjk->jk", w, P[m])
        U, _, Vt = np.linalg.svd(np.einsum("f,fjab->jab", w, G[m]))
        d = np.sign(np.linalg.det(U @ Vt))
        U[:, :, 2] *= d[:, None]
        Go[k] = U @ Vt
    return Go, Po


def quat(M):
    """(N,3,3) rotation matrices -> (N,4) quaternions w,x,y,z (Shepperd)."""
    N = M.shape[0]
    q = np.zeros((N, 4))
    tr = M[:, 0, 0] + M[:, 1, 1] + M[:, 2, 2]
    for i in range(N):
        m = M[i]
        if tr[i] > 0:
            s = math.sqrt(tr[i] + 1.0) * 2
            q[i] = [0.25 * s, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s]
        elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
            s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
            q[i] = [(m[2, 1] - m[1, 2]) / s, 0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s]
        elif m[1, 1] > m[2, 2]:
            s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
            q[i] = [(m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s]
        else:
            s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
            q[i] = [(m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s]
    q /= np.linalg.norm(q, axis=1, keepdims=True)
    for i in range(1, N):  # hemisphere: keep the path continuous
        if np.dot(q[i], q[i - 1]) < 0:
            q[i] = -q[i]
    return q


def yaw_fix(G0hips):
    """Rotation about Blender Z that turns the source's facing at t0 to -Y (the avatars' rest facing)."""
    f = C @ G0hips @ np.array([0, 0, 1.0])  # BVH forward +Z
    yaw = math.atan2(f[0], -f[1])  # angle from -Y
    c, s = math.cos(-yaw), math.sin(-yaw)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


# ------------------------------------------------------------------------------------------------ retarget (Blender)
MIRROR = np.diag([-1.0, 1.0, 1.0])  # BVH sagittal mirror (x -> -x), with Left/Right joints swapped


def clip_world(b, times, fps, sigma=None, mirror=False):
    """Source joints over `times` (s, any spacing, fractional), low-passed: world rotations relative to the T-pose
    (Blender axes, unturned) Dw (F,J,3,3) and positions Pw (F,J,3) in metres."""
    G, P = sample(b, np.asarray(times, float), fps, sigma)
    if mirror:
        names = b["names"]
        perm = [names.index(n.replace("Left", "#").replace("Right", "Left").replace("#", "Right"))
                if n.replace("Left", "#").replace("Right", "Left").replace("#", "Right") in names else j
                for j, n in enumerate(names)]
        G = np.einsum("ij,fkjl,lm->fkim", MIRROR, G[:, perm], MIRROR)
        P = np.einsum("ij,fkj->fki", MIRROR, P[:, perm])
    Dw = np.einsum("ij,fkjl,ml->fkim", C, G, C)
    Pw = np.einsum("ij,fkj->fki", C, P) * 0.01
    return Dw, Pw


def yaw_of(Dw_hips):
    """Heading (rad, about +Z, 0 = facing -Y like the avatars at rest) of the source hips, per frame."""
    f = np.einsum("fij,j->fi", Dw_hips, [0, -1.0, 0])  # the rest facing (-Y) carried by the hips' rotation
    return np.arctan2(f[:, 0], -f[:, 1])


def rz(a):
    a = np.atleast_1d(a)
    c, s = np.cos(a), np.sin(a)
    R = np.zeros(a.shape + (3, 3))
    R[..., 0, 0], R[..., 0, 1], R[..., 1, 0], R[..., 1, 1], R[..., 2, 2] = c, -s, s, c, 1
    return R


def setup(arm, b):
    """Shared T-pose (every mapped bone swung onto the BVH rest direction; fingers relaxed) + rig arrays."""
    import bpy
    from mathutils import Matrix, Vector

    J = {n: i for i, n in enumerate(b["names"])}
    pb = arm.pose.bones
    for p in pb:
        p.rotation_mode = "QUATERNION"
        p.rotation_quaternion = (1, 0, 0, 0)
        p.location = (0, 0, 0)
    bpy.context.view_layer.update()
    MW = arm.matrix_world.copy()
    MR = np.array(MW.to_3x3().normalized())  # armature object rotation (scale 0.01 removed)
    Mi = MW.inverted()

    def src_dir(j):
        tgt, ch = MAP[b["names"][j]]
        v = b["ends"][j] if ch == "_end" else b["offs"][J[ch]]
        return C @ np.array(v)

    depth = lambda n: 0 if pb[n].parent is None else 1 + depth(pb[n].parent.name)  # noqa: E731
    order = sorted([(depth(MAP[s][0]), s) for s in MAP if MAP[s][1] and MAP[s][0] in pb and s in J])
    for _, s in order:
        bn = MAP[s][0]
        bpy.context.view_layer.update()
        h = MW @ pb[bn].matrix.translation
        d = (MW @ pb[ALONG[bn]].matrix.translation - h).normalized()
        q = d.rotation_difference(Vector(src_dir(J[s])).normalized())
        R = Mi.to_3x3() @ q.to_matrix() @ MW.to_3x3()
        hl = pb[bn].matrix.translation.copy()
        pb[bn].matrix = Matrix.Translation(hl) @ R.to_4x4() @ Matrix.Translation(-hl) @ pb[bn].matrix
    _relax_fingers(arm)
    bpy.context.view_layer.update()
    bones = sorted(arm.data.bones, key=lambda bn: depth(bn.name))  # parents before children
    bi = {bn.name: i for i, bn in enumerate(bones)}
    rest = np.array([np.array(bn.matrix_local.to_3x3().normalized()) for bn in bones])  # armature space
    rhead = np.array([np.array(bn.head_local) for bn in bones])
    AT = np.array([np.array(pb[bn.name].matrix.to_3x3().normalized()) for bn in bones])  # T-pose, armature space
    LT = np.array([np.array(pb[bn.name].rotation_quaternion.to_matrix()) for bn in bones])  # T-pose local
    par = [bi[bn.parent.name] if bn.parent else -1 for bn in bones]
    tdir = {}  # twist axes (review 014c #4): the forearm's direction, in the forearm's and the hand's T-pose frames
    for x in ("L", "R"):
        fa, hd_ = bi[f"Bip01 {x} Forearm"], bi[f"Bip01 {x} Hand"]
        d_ = np.array((pb[f"Bip01 {x} Hand"].matrix.translation - pb[f"Bip01 {x} Forearm"].matrix.translation)
                      .normalized())
        tdir[x] = (AT[fa].T @ d_, AT[hd_].T @ d_)
    sc_ = arm.scale.x
    # hip-to-ankle, both sides (review 014c #3): the avatar from its rest heads (vertical legs)
    leg_t = float(np.mean([(MR @ (rhead[bi[f"Bip01 {x} Thigh"]] - rhead[bi[f"Bip01 {x} Foot"]]))[2]
                           for x in ("L", "R")]) * sc_)
    root = bi["Bip01 Pelvis"] if "Bip01 Pelvis" in bi else [i for i in range(len(bones)) if par[i] < 0][0]
    src_of = {MAP[s][0]: s for s in MAP if s in J and MAP[s][0] in bi}  # target bone -> source joint name
    pairs = [(MAP[sj][0], ALONG[MAP[sj][0]], sj, MAP[sj][1]) for sj in MAP if MAP[sj][1] not in (None, "_end")
             and MAP[sj][0] in ALONG and sj in J]
    return dict(arm=arm, pb=pb, bones=bones, bi=bi, rest=rest, rhead=rhead, AT=AT, LT=LT, par=par, tdir=tdir,
                MW=MW, MR=MR, scale=sc_, base=np.array(MW.translation), leg_t=leg_t, root=root, src_of=src_of,
                pairs=pairs, ank_rest=float(rhead[bi["Bip01 L Foot"]][2] * sc_ + MW.translation.z))


def leg_ratio(rig, b):
    J = {n: i for i, n in enumerate(b["names"])}
    leg_bvh = (np.linalg.norm(b["offs"][J["LeftKnee"]]) + np.linalg.norm(b["offs"][J["LeftAnkle"]])
               + np.linalg.norm(b["offs"][J["RightKnee"]]) + np.linalg.norm(b["offs"][J["RightAnkle"]])) / 2 * 0.01
    leg_s = b.get("spec_leg_m") or leg_bvh
    return rig["leg_t"] / leg_s, leg_s, leg_bvh


def solve(rig, Dw, J, want):
    """Dw (F,Jsrc,3,3): per-frame WORLD rotation of every source joint vs the T-pose (any yaw already applied);
    want (F,3): world target of the thigh-head midpoint. Returns armature-space rotations A, locals L, world heads Hw
    and the per-frame world shift of the root."""
    bones, bi, rest, rhead, AT, LT, par, MR = (rig[k] for k in ("bones", "bi", "rest", "rhead", "AT", "LT", "par", "MR"))
    F, NB = len(Dw), len(bones)
    Darm = np.einsum("ji,fkjl,lm->fkim", MR, Dw, MR)  # world delta -> armature space (MR^T D MR)
    A = np.zeros((F, NB, 3, 3))
    L = np.zeros((F, NB, 3, 3))
    for i, bn in enumerate(bones):
        p = par[i]
        if bn.name in rig["src_of"]:
            A[:, i] = Darm[:, J[rig["src_of"][bn.name]]] @ AT[i]
            if p < 0:
                L[:, i] = rest[i].T @ A[:, i]
            else:
                L[:, i] = np.einsum("ij,fjk,fkl->fil", rest[i].T @ rest[p], np.transpose(A[:, p], (0, 2, 1)), A[:, i])
        else:
            L[:, i] = LT[i]
            A[:, i] = (A[:, p] @ rest[p].T @ rest[i] @ LT[i]) if p >= 0 else rest[i] @ LT[i]
    H = np.zeros((F, NB, 3))
    for i in range(NB):
        p = par[i]
        H[:, i] = rhead[i] if p < 0 else H[:, p] + np.einsum("fij,j->fi", A[:, p] @ rest[p].T[None], rhead[i] - rhead[p])
    Hw = np.einsum("ij,fkj->fki", MR, H) * rig["scale"] + rig["base"]  # world, root unmoved
    th = (Hw[:, bi["Bip01 L Thigh"]] + Hw[:, bi["Bip01 R Thigh"]]) / 2
    shift = want - th
    return dict(A=A, L=L, Hw=Hw + shift[:, None], shift=shift)


def floor_dz(rig, sol, lift=0.0):
    """Vertical constant putting the ankles' 2nd-percentile height on their rest height (+ a mesh-measured lift)."""
    bi = rig["bi"]
    ank = np.minimum(sol["Hw"][:, bi["Bip01 L Foot"], 2], sol["Hw"][:, bi["Bip01 R Foot"], 2])
    dz = rig["ank_rest"] - np.percentile(ank, 2) + lift
    sol["shift"][:, 2] += dz
    sol["Hw"][:, :, 2] += dz
    return dz


def write(rig, sol, frames, name):
    """Bulk-write rotations (mapped bones; the others static at the T-pose locals) + the root location."""
    import bpy
    arm, bones, pb, rest, root, MR = (rig[k] for k in ("arm", "bones", "pb", "rest", "root", "MR"))
    loc_arm = (MR.T @ sol["shift"].T).T / rig["scale"]  # armature-space translation of the root head
    loc_basis = (rest[root].T @ loc_arm.T).T  # pose location is in the bone's rest frame
    act = bpy.data.actions.new(name)
    arm.animation_data_create()
    arm.animation_data.action = act
    frames = np.asarray(frames, float)
    for i, bn in enumerate(bones):
        if bn.name not in rig["src_of"] and i not in sol.get("keyed", ()):
            pb[bn.name].rotation_quaternion = list(quat(rig["LT"][i:i + 1])[0])
            continue
        Q = quat(sol["L"][:, i])
        for k in range(4):
            _bulk(act, arm, f'pose.bones["{bn.name}"].rotation_quaternion', k, frames, Q[:, k], bn.name)
    for k in range(3):
        _bulk(act, arm, f'pose.bones["{bones[root].name}"].location', k, frames, loc_basis[:, k], bones[root].name)
    return act


def retarget(arm, b, t0, t1, fps, frame0=1, name=None, align_yaw=True, lift=0.0, foot_lock=True, sigma=None):
    """Key arm (Rocketbox, imported, rest) with BVH b between t0 and t1 s at fps (M2). Returns arrays for QA."""
    J = {n: i for i, n in enumerate(b["names"])}
    times = np.arange(t0, t1 - 1e-9, 1.0 / fps)
    rows = np.clip(np.round(times / b["dt"]).astype(int), 0, len(b["data"]) - 1)  # nearest source rows (labels)
    Dw, Pw = clip_world(b, times, fps, sigma)
    Y = rz(-yaw_of(Dw[:1, J["Hips"]])[0])[0] if align_yaw else np.eye(3)  # start facing -Y
    Dw = np.einsum("ij,fkjl->fkil", Y, Dw)
    Pw = np.einsum("ij,fkj->fki", Y, Pw)
    rig = setup(arm, b)
    s, leg_s, leg_bvh = leg_ratio(rig, b)
    hips_src = (Pw[:, J["LeftHip"]] + Pw[:, J["RightHip"]]) / 2
    base = rig["base"]
    sol = solve(rig, Dw, J, base + s * (hips_src - hips_src[0] * np.array([1, 1, 0])))
    dz = floor_dz(rig, sol, lift)
    pw_t = base + s * (Pw - hips_src[0] * np.array([1, 1, 0])) + np.array([0, 0, dz])  # source, scaled + placed
    locks = {}
    if foot_lock:
        for sd, sj in (("L", "LeftAnkle"), ("R", "RightAnkle")):
            locks[sd] = _foot_lock(sol["A"], sol["Hw"], sol["L"], rig["rest"], rig["par"], rig["bi"], sd,
                                   contacts(pw_t[:, J[sj]], fps), rig["MR"], fps)
    frames = frame0 + np.arange(len(times), dtype=float)
    act = write(rig, sol, frames, name or f"{Path(str(b.get('path', 'bvh'))).stem}@{arm.name}")
    return dict(action=act, frames=frames, Hw=sol["Hw"], bi=rig["bi"], src=pw_t, J=J, pairs=rig["pairs"], scale=s,
                rows=rows, fps=fps, locks=locks, leg_t=rig["leg_t"], leg_s=leg_s, leg_bvh=leg_bvh,
                leg_src="participant spec" if b.get("spec_leg_m") else "BVH offsets", AT=rig["AT"], tdir=rig["tdir"],
                times=times)


def contacts(sp, fps, dz=0.03, vmax=0.15):
    """Stance frames of one ankle from the (scaled, placed) source: near its low height and nearly still."""
    z = sp[:, 2]
    v = np.r_[0, np.linalg.norm(np.diff(sp[:, :2], axis=0), axis=1) * fps]
    c = (z < np.percentile(z, 5) + dz) & (v < vmax)
    iv, i = [], 0
    while i < len(c):
        if c[i]:
            j = i
            while j + 1 < len(c) and c[j + 1]:
                j += 1
            if j - i >= 2:
                iv.append((i, j))
            i = j + 1
        else:
            i += 1
    return iv


def _swing_np(a, b):
    """(F,3),(F,3) -> (F,3,3) shortest-arc rotations taking a onto b."""
    a = a / np.linalg.norm(a, axis=1, keepdims=True)
    b = b / np.linalg.norm(b, axis=1, keepdims=True)
    v = np.cross(a, b)
    c = np.sum(a * b, 1)
    K = np.zeros((len(a), 3, 3))
    K[:, 0, 1], K[:, 0, 2], K[:, 1, 0] = -v[:, 2], v[:, 1], v[:, 2]
    K[:, 1, 2], K[:, 2, 0], K[:, 2, 1] = -v[:, 0], -v[:, 1], v[:, 0]
    return np.eye(3)[None] + K + K @ K * (1.0 / (1.0 + np.maximum(c, -0.999999)))[:, None, None]


def _foot_lock(A, Hw, L, rest, par, bi, sd, iv, MR, fps, ramp_s=0.1):
    """Pin the ankle (Bip01 <sd> Foot head) horizontally to its median stance position over each stance interval,
    ramping in/out over ramp_s; two-bone thigh/calf solve in the mocap knee plane; the foot keeps its world rotation.
    Updates A, L and Hw (that leg's knee/ankle/toe heads) in place. Returns the intervals."""
    F = A.shape[0]
    th, ca, fo = bi[f"Bip01 {sd} Thigh"], bi[f"Bip01 {sd} Calf"], bi[f"Bip01 {sd} Foot"]
    w = np.zeros(F)
    tgt = Hw[:, fo].copy()
    rf = max(1, int(round(ramp_s * fps)))
    for i, j in iv:
        pin = np.median(Hw[i:j + 1, fo, :2], axis=0)
        for f in range(max(0, i - rf), min(F, j + rf + 1)):
            wf = 1.0 if i <= f <= j else (1.0 - (i - f) / (rf + 1) if f < i else 1.0 - (f - j) / (rf + 1))
            if wf > w[f]:
                w[f] = wf
                tgt[f, :2] = pin
    k = w > 0
    if not k.any():
        return iv
    T, K, Aa = Hw[k, th], Hw[k, ca], Hw[k, fo]
    P = Aa.copy()
    P[:, :2] = Aa[:, :2] + (tgt[k, :2] - Aa[:, :2]) * w[k, None]
    l1 = np.linalg.norm(K - T, axis=1)
    l2 = np.linalg.norm(Aa - K, axis=1)
    d_ = np.linalg.norm(P - T, axis=1)
    d = np.clip(d_, np.abs(l1 - l2) + 1e-4, l1 + l2 - 1e-4)
    u = (P - T) / d_[:, None]
    P = T + u * d[:, None]
    kp = (K - T) - np.sum((K - T) * u, 1)[:, None] * u
    kp /= np.linalg.norm(kp, axis=1, keepdims=True) + 1e-12
    a_ = (l1 ** 2 - l2 ** 2 + d ** 2) / (2 * d)
    h_ = np.sqrt(np.maximum(l1 ** 2 - a_ ** 2, 0))
    K2 = T + u * a_[:, None] + kp * h_[:, None]
    R1 = _swing_np(K - T, K2 - T)  # world
    R2 = _swing_np(np.einsum("fij,fj->fi", R1, Aa - K), P - K2)
    toArm = lambda R: np.einsum("ji,fjk,kl->fil", MR, R, MR)  # noqa: E731  (MR^T R MR)
    A1, A2 = toArm(R1), toArm(R2)
    A[k, th] = A1 @ A[k, th]
    A[k, ca] = A2 @ A1 @ A[k, ca]
    for i_ in (th, ca, fo):  # locals of the changed bones (the foot's world rotation is unchanged)
        p = par[i_]
        L[k, i_] = np.einsum("ij,fjk,fkl->fil", rest[i_].T @ rest[p], np.transpose(A[k, p], (0, 2, 1)), A[k, i_])
    toe = bi.get(f"Bip01 {sd} Toe0")
    dP = P - Aa
    Hw[k, ca] = K2
    Hw[k, fo] = P
    if toe is not None:
        Hw[k, toe] = Hw[k, toe] + dP
    return iv


def _bulk(act, arm, path, idx, frames, vals, group):
    fc = act.fcurve_ensure_for_datablock(arm, path, index=idx, group_name=group)
    fc.keyframe_points.clear()
    fc.keyframe_points.add(len(frames))
    co = np.empty(2 * len(frames))
    co[0::2], co[1::2] = frames, vals
    fc.keyframe_points.foreach_set("co", co)
    fc.update()


CURL = {0: (8, 12, 10), 1: (10, 18, 12), 2: (12, 20, 14), 3: (14, 22, 15), 4: (16, 24, 16)}  # as rb_tpose (M1)


def _relax_fingers(arm):
    import bpy
    from mathutils import Matrix
    pb, MW = arm.pose.bones, arm.matrix_world
    Mi = MW.inverted()
    hd = lambda n: MW @ pb[n].matrix.translation  # noqa: E731
    for sd in ("L", "R"):
        def segs(f):
            base = f"Bip01 {sd} Finger{f}"
            return [n for n in (base, base + "1", base + "2") if n in pb]
        bpy.context.view_layer.update()
        h = hd(f"Bip01 {sd} Hand")
        n_ = (hd(segs(1)[0]) - h).cross(hd((segs(4) or segs(3))[0]) - h)
        if n_.dot(hd(segs(0)[-1]) - h) < 0:
            n_ = -n_
        n_.normalize()
        for f in range(5):
            ch = segs(f)
            for k, nm in enumerate(ch):
                bpy.context.view_layer.update()
                hh = hd(nm)
                d = ((hd(ch[k + 1]) - hh) if k + 1 < len(ch) else (MW @ pb[nm].tail - hh)).normalized()
                ax = d.cross(n_)
                if ax.length < 1e-4:
                    continue
                R = Mi.to_3x3() @ Matrix.Rotation(math.radians(CURL[f][min(k, 2)] * (0.5 if f == 0 else 1.0)), 3,
                                                  ax.normalized()) @ MW.to_3x3()
                hl = pb[nm].matrix.translation.copy()
                pb[nm].matrix = Matrix.Translation(hl) @ R.to_4x4() @ Matrix.Translation(-hl) @ pb[nm].matrix


# ------------------------------------------------------------------------------------------------ QA
def _twist(Rp, Rc, RpT, RcT, axis_c):
    """Twist (deg) of child vs parent about axis_c (unit, child's T-pose frame), relative to the T-pose."""
    D = np.einsum("ij,fjk->fik", (RpT.T @ RcT).T, np.einsum("fji,fjk->fik", Rp, Rc))  # (Rrel_T)^T Rrel(t)
    q = quat(D)
    return np.degrees(2 * np.arctan2(q[:, 1:] @ axis_c, q[:, 0]))


def qa(r, body=None, scene=None, mesh_step=3, hold=None):
    """Review 014c #4 table. Foot skate PER CONTACT (mm, contacts from the source: ankle within 3 cm of its low and
    < 0.15 m/s), ground-penetration FRAMES (deformed mesh below z 0 by > 0.5 mm), limb-direction error vs source per
    limb (mean / max deg), forearm and wrist twist vs the T-pose (max deg; > 90 = candy-wrap flag), palms facing each
    other on hold frames. With body/scene everything is measured on Blender's EVALUATED pose, not the numpy model."""
    Hw, bi, src, J, fps = r["Hw"], r["bi"], r["src"], r["J"], r["fps"]
    out = {}
    names = list(bi)
    Arot = None
    if body is not None:
        arm = body.find_armature() or next(o for o in scene.objects if o.type == "ARMATURE")
        ev = np.zeros_like(Hw)
        Arot = np.zeros((len(r["frames"]), len(names), 3, 3))
        for k, f in enumerate(r["frames"]):
            scene.frame_set(int(f))
            M = arm.matrix_world
            ev[k] = [tuple(M @ arm.pose.bones[n].head) for n in names]
            Arot[k] = [np.array(arm.pose.bones[n].matrix.to_3x3().normalized()) for n in names]
        out["model_vs_blender_mm"] = round(float(np.abs(ev - Hw).max()) * 1000, 2)
        Hw = ev
    per = []
    for sd, sj in (("L", "LeftAnkle"), ("R", "RightAnkle")):
        tp = Hw[:, bi[f"Bip01 {sd} Foot"], :2]
        for i, j in contacts(src[:, J[sj]], fps):
            per.append(dict(foot=sd, f0=int(r["frames"][i]), frames=j - i + 1,
                            skate_mm=round(float(np.max(np.linalg.norm(tp[i:j + 1] - tp[i], axis=1))) * 1000, 1)))
    out["contacts"] = per
    out["foot_skate_max_mm"] = max((c["skate_mm"] for c in per), default=0.0)
    limbs = {}
    for tb, tc, sj, sc_ in r["pairs"]:
        dt = Hw[:, bi[tc]] - Hw[:, bi[tb]]
        ds = src[:, J[sc_]] - src[:, J[sj]]
        cosv = np.sum(dt * ds, 1) / (np.linalg.norm(dt, axis=1) * np.linalg.norm(ds, axis=1) + 1e-9)
        e = np.degrees(np.arccos(np.clip(cosv, -1, 1)))
        limbs[tb.replace("Bip01 ", "")] = (round(float(e.mean()), 2), round(float(e.max()), 2))
    out["limb_dir_err_deg_mean_max"] = limbs
    out["limb_dir_err_max_deg"] = max(v[1] for v in limbs.values())
    if Arot is not None:
        AT = r["AT"]
        tw = {}
        for x in ("L", "R"):
            ua, fa, hd = (bi[f"Bip01 {x} {n}"] for n in ("UpperArm", "Forearm", "Hand"))
            ax_f, ax_h = (v / np.linalg.norm(v) for v in r["tdir"][x])
            t1 = _twist(Arot[:, ua], Arot[:, fa], AT[ua], AT[fa], ax_f)
            t2 = _twist(Arot[:, fa], Arot[:, hd], AT[fa], AT[hd], ax_h)
            tw[f"{x}_forearm"] = round(float(np.abs(t1).max()), 1)
            tw[f"{x}_wrist"] = round(float(np.abs(t2).max()), 1)
        out["twist_max_deg"] = tw
        out["candy_wrap_flag"] = any(v > 90 for v in tw.values())
        if hold is not None and hold.any():  # palms facing each other while the two hands hold a load
            def palm(x):
                h = Hw[:, bi[f"Bip01 {x} Hand"]]
                n_ = np.cross(Hw[:, bi[f"Bip01 {x} Finger1"]] - h, Hw[:, bi[f"Bip01 {x} Finger4"]] - h)
                s_ = np.sign(np.sum(n_ * (Hw[:, bi[f"Bip01 {x} Finger02"]] - h), 1))
                n_ = n_ * s_[:, None]
                c_ = (h + Hw[:, bi[f"Bip01 {x} Finger2"]]) / 2
                return n_ / np.linalg.norm(n_, axis=1, keepdims=True), c_
            nl, cl = palm("L")
            nr, cr = palm("R")
            u = (cr - cl) / np.linalg.norm(cr - cl, axis=1, keepdims=True)
            cosl, cosr = np.sum(nl * u, 1)[hold], -np.sum(nr * u, 1)[hold]
            out["palms_inward_on_hold"] = dict(frames=int(hold.sum()), L_median_cos=round(float(np.median(cosl)), 2),
                                               R_median_cos=round(float(np.median(cosr)), 2),
                                               share_facing=round(float(np.mean((cosl > 0.3) & (cosr > 0.3))), 2))
    if body is not None:
        import bpy
        lows = []
        for f in r["frames"][::mesh_step]:
            scene.frame_set(int(f))
            dg = bpy.context.evaluated_depsgraph_get()
            ob = body.evaluated_get(dg)
            me = ob.to_mesh()
            co = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3)
            M = np.array(ob.matrix_world)
            lows.append(float((co @ M[:3, :3].T + M[:3, 3])[:, 2].min()))
            ob.to_mesh_clear()
        lows = np.array(lows)
        out["ground_pen_frames"] = int((lows < -0.0005).sum())
        out["ground_pen_max_mm"] = round(max(0.0, -float(lows.min())) * 1000, 1)
        out["float_p50_mm"] = round(float(np.median(lows)) * 1000, 1)
    return out


# ------------------------------------------------------------------------------------------------ CLI (M2 proof)
if __name__ == "__main__":
    import argparse
    import json

    import bpy
    ap = argparse.ArgumentParser()
    ap.add_argument("--bvh", required=True)
    ap.add_argument("--avatar", default="Male_Adult_04")
    ap.add_argument("--t0", type=float, default=0.0)
    ap.add_argument("--t1", type=float, default=10.0)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--sigma", type=float, default=None)  # 1e-6 = raw rows (reference-pose proof)
    ap.add_argument("--rb", default=str(Path(__file__).resolve().parents[1] / "build" / "third_party" / "rocketbox"))
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    OUT = Path(a.out).resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import people  # noqa: E402

    sc = bpy.context.scene
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.import_scene.fbx(filepath=str(Path(a.rb) / a.avatar / f"{a.avatar}.fbx"))
    arm = next(o for o in sc.objects if o.type == "ARMATURE")
    body = max((o for o in sc.objects if o.type == "MESH"), key=lambda o: len(o.data.vertices))
    for o in sc.objects:
        if o.type == "MESH":
            people._fix_materials(o, Path(a.rb) / a.avatar)
        if o.animation_data:
            o.animation_data.action = None
    for act in list(bpy.data.actions):
        bpy.data.actions.remove(act)
    b = read_bvh(a.bvh)
    b["path"] = a.bvh
    bp = Path(a.bvh).resolve()
    pid = re.search(r"Participant_(\d+)", bp.name)
    hold = None
    if pid:  # AndyData: measured leg (hip - ankle height) and the labels (hold frames for the palm check)
        import csv as _csv
        spec = bp.parents[2] / "participant_specifications.csv"
        for row in _csv.DictReader(open(spec, encoding="utf-8")):
            if row["ID"] == pid.group(1):
                b["spec_leg_m"] = (float(row["hip_height"]) - float(row["ankle_height"])) / 100.0
                b["spec_height_m"] = float(row["body_height"]) / 100.0
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import clips  # noqa: E402
        segs, _ = clips.segments(bp.parents[2] / "labels" / "labels_csv" / f"Participant_{pid.group(1)}" /
                                 bp.name.replace(".xsens.bvh", ".labels.csv"))
    r = retarget(arm, b, a.t0, a.t1, a.fps, sigma=a.sigma)
    if pid:
        hold = np.array([any(s_[0] in ("Pi", "Ca") and s_[1] <= t < s_[2] for s_ in segs) for t in r["times"]])
    sc.render.fps = int(a.fps)
    sc.frame_start, sc.frame_end = 1, len(r["frames"])
    low = -qa(r, body, sc, mesh_step=1)["ground_pen_max_mm"] / 1000.0
    for act in list(bpy.data.actions):
        bpy.data.actions.remove(act)
    r = retarget(arm, b, a.t0, a.t1, a.fps, lift=-low, sigma=a.sigma)  # the lowest sole point over the clip exactly on the floor
    res = qa(r, body, sc, mesh_step=1, hold=hold)
    res.update(bvh=Path(a.bvh).name, avatar=a.avatar, t0=a.t0, t1=a.t1, fps=a.fps, leg_scale=round(r["scale"], 4),
               leg_avatar_hip_to_ankle_m=round(r["leg_t"], 3), leg_source_hip_to_ankle_m=round(r["leg_s"], 3),
               leg_source_from=r["leg_src"], leg_source_bvh_offsets_m=round(r["leg_bvh"], 3),
               source_height_m=b.get("spec_height_m"), resample="Gaussian low-pass sigma=0.5/fps over all 240 Hz "
               "frames + SO(3) chordal mean (no frame dropped)", frames=len(r["frames"]))
    print("M2 QA", json.dumps(res), flush=True)
    (OUT / "m2_qa.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    np.savez(OUT / "m2_src.npz", src=r["src"], Hw=r["Hw"], names=np.array(b["names"]),
             parents=np.array(b["parents"]), bones=np.array(list(r["bi"])))
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "m2_retarget.blend"))
    if a.render:
        sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in {
            e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items} else "BLENDER_EEVEE"
        if hasattr(sc.eevee, "taa_render_samples"):
            sc.eevee.taa_render_samples = 8
        sc.render.resolution_x = sc.render.resolution_y = 540
        sc.render.image_settings.file_format = "PNG"
        w = bpy.data.worlds.new("w")
        w.use_nodes = True
        w.node_tree.nodes["Background"].inputs[0].default_value = (0.35, 0.36, 0.38, 1)
        sc.world = w
        ld = bpy.data.lights.new("key", "SUN")
        ld.energy = 3.0
        lo = bpy.data.objects.new("key", ld)
        sc.collection.objects.link(lo)
        lo.rotation_euler = (math.radians(50), 0, math.radians(30))
        bpy.ops.mesh.primitive_plane_add(size=12)
        fl = bpy.context.active_object
        fm = bpy.data.materials.new("floor")
        fm.use_nodes = True
        fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.5, 0.5, 0.5, 1)
        fl.data.materials.append(fm)
        hw = r["Hw"][:, r["bi"]["Bip01 Pelvis"]]
        cx, cy = float(hw[:, 0].mean()), float(hw[:, 1].mean())
        ext = max(float(np.ptp(hw[:, 0])), float(np.ptp(hw[:, 1])))
        ortho = max(2.4, ext + 1.4)
        cams = {}
        for tag, d in (("front", (0, -1, 0)), ("side", (1, 0, 0))):
            cd = bpy.data.cameras.new(tag)
            cd.type, cd.ortho_scale = "ORTHO", ortho
            cam = bpy.data.objects.new(tag, cd)
            sc.collection.objects.link(cam)
            cam.location = (cx + 8 * d[0], cy + 8 * d[1], ortho / 2 - 0.1)
            from mathutils import Vector
            cam.rotation_euler = Vector((-d[0], -d[1], 0)).to_track_quat("-Z", "Y").to_euler()
            cams[tag] = cam
        (OUT / "frames").mkdir(exist_ok=True)
        json.dump(dict(cx=cx, cy=cy, cz=ortho / 2 - 0.1, ortho=ortho, res=540), open(OUT / "m2_cams.json", "w"))
        for tag, cam in cams.items():
            sc.camera = cam
            sc.render.filepath = str(OUT / "frames" / f"{tag}_####")
            bpy.ops.render.render(animation=True)
        print("M2 rendered", flush=True)
