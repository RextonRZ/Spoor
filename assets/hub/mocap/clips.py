"""M3 step 1 (014_GO): cut AndyData takes on their labels into stationary PICK and PLACE clips + sidecar JSON.

AndyData carries walk ~2 m between tables, so a whole Re-Pi-Ca-Pl cycle never fits a planted inductor. What does fit
are the two stationary pieces: the end of the reach + the pick at one table, and the place + start of the release at
the other. Each boundary is snapped to the nearest wrist-speed minimum within +-0.15 s; clips are padded for blends.

  py -X utf8 assets/hub/mocap/clips.py            -> assets/mocap/clips.json (+ printout)
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import retarget as R  # noqa: E402

RAW = HERE.parents[1] / "mocap" / "raw" / "andydata"
FPS = 30.0


def majority(row, key):
    v = [row[f"{key}_Annotator{i}"] for i in (1, 2, 3)]
    return max(set(v), key=v.count)


def segments(labels_csv):
    rows = list(csv.DictReader(open(labels_csv, encoding="utf-8")))
    segs, cur, t0 = [], None, 0.0
    for r in rows:
        a = majority(r, "current_action")
        if a != cur:
            if cur:
                segs.append([cur, t0, float(r["t_video"])])
            cur, t0 = a, float(r["t_video"])
    segs.append([cur, t0, float(rows[-1]["t_video"])])
    return segs, rows


def analyse(bvh_path, labels_csv):
    b = R.read_bvh(bvh_path)
    J = {n: i for i, n in enumerate(b["names"])}
    rows_all = np.arange(0, len(b["data"]), int(round(1 / (FPS * b["dt"]))))
    G, P = R.fk(b, rows_all)
    P = P / 100.0
    hips = P[:, J["Hips"], [0, 2]]
    fwd = np.einsum("fij,j->fi", G[:, J["Hips"]], [0, 0, 1.0])
    yaw = np.degrees(np.unwrap(np.arctan2(fwd[:, 0], fwd[:, 2])))
    wr = {s: P[:, J[f"{s}Wrist"]] for s in ("Left", "Right")}
    wspeed = sum(np.r_[0, np.linalg.norm(np.diff(w, axis=0), axis=1)] * FPS for w in wr.values()) / 2
    ankles = [P[:, J[f"{s}Ankle"]] for s in ("Left", "Right")]
    n = len(rows_all)

    def fi(t):
        return int(np.clip(round(t * FPS), 0, n - 1))

    def snap(t):
        a, b_ = fi(t - 0.15), fi(t + 0.15)
        return (a + int(np.argmin(wspeed[a:b_ + 1]))) / FPS

    def still(t0, t1):  # root travel and foot travel inside [t0, t1]
        a, b_ = fi(t0), fi(t1)
        root = float(np.max(np.linalg.norm(hips[a:b_ + 1] - hips[a], axis=1)))
        foot = max(float(np.max(np.linalg.norm(an[a:b_ + 1, [0, 2]] - an[a, [0, 2]], axis=1))) for an in ankles)
        return root, foot

    segs, rows = segments(labels_csv)
    post = lambda t: majority(rows[min(len(rows) - 1, int(t * 24))], "detailed_posture")  # noqa: E731
    out = []
    name = Path(bvh_path).name.replace(".xsens.bvh", "")
    for i, (a, s0, s1) in enumerate(segs):
        prev = segs[i - 1] if i else None
        nxt = segs[i + 1] if i + 1 < len(segs) else None
        if a == "Pi":
            g = snap(s0)
            lift = snap(s1)
            t0 = max(prev[1] if prev and prev[0] == "Re" else s0 - 0.6, g - 0.9)
            t1 = lift + 0.4
            kind, ev = "pick", {"grasp": g, "lift": lift}
        elif a == "Pl":
            rel = snap(s1)
            t0 = max(s0 - 0.3, (prev[1] if prev else s0 - 0.3))
            t1 = rel + (min(0.6, nxt[2] - nxt[1]) if nxt and nxt[0] == "Rl" else 0.3)
            kind, ev = "place", {"place_start": snap(s0), "release": rel}
        else:
            continue
        root, foot = still(t0, t1)
        k = fi(ev.get("grasp", ev.get("release")))
        hands = {s: [round(float(x), 3) for x in wr[s][k]] for s in wr}
        two = float(np.linalg.norm(wr["Left"][k] - wr["Right"][k]))
        out.append(dict(take=name, kind=kind, t0=round(t0, 3), t1=round(t1, 3), dur=round(t1 - t0, 3),
                        events={k_: round(v, 3) for k_, v in ev.items()}, root_travel_m=round(root, 3),
                        foot_travel_m=round(foot, 3), yaw_change_deg=round(float(yaw[fi(t1)] - yaw[fi(t0)]), 1),
                        hand_height_m=round(float(min(wr["Left"][k][1], wr["Right"][k][1])), 3),
                        wrist_gap_m=round(two, 3), two_hand=two < 0.55, posture=post(ev.get("grasp",
                                                                                              ev.get("release"))),
                        wrists=hands))
    return out


if __name__ == "__main__":
    allc = []
    for f in sorted((RAW / "xsens_bvh").glob("*/*.bvh")):
        name = f.name.replace(".xsens.bvh", "")
        pid = name.split("_")[1]
        allc += analyse(f, RAW / "labels" / "labels_csv" / f"Participant_{pid}" / f"{name}.labels.csv")
    for c in allc:
        c["usable"] = c["root_travel_m"] < 0.25 and c["foot_travel_m"] < 0.2 and c["two_hand"] and \
            0.75 <= c["hand_height_m"] <= 1.2
        print(f"{c['take'][12:]:28s} {c['kind']:5s} {c['t0']:6.1f}-{c['t1']:6.1f} ({c['dur']:.2f}s) root {c['root_travel_m']:.2f} "
              f"foot {c['foot_travel_m']:.2f} yaw {c['yaw_change_deg']:5.0f} hands {c['hand_height_m']:.2f} m "
              f"gap {c['wrist_gap_m']:.2f} {c['posture']:6s} {'USE' if c['usable'] else ''}")
    out = HERE.parents[1] / "mocap" / "clips.json"
    out.write_text(json.dumps(allc, indent=1), encoding="utf-8")
    print(sum(c["usable"] for c in allc), "usable of", len(allc), "->", out)
