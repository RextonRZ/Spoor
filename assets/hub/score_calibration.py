"""Score Spoor's calibrated projection against where Blender says each test point truly lands (qa_calibration.py), in
pixels of the delivered 1920x1086 frame. Two methods: the camera pose (3D, height included) and the floor homography
(x, y only), so the height error of the floor-only method on raised scanners is visible.

  uv run --project backend python assets/hub/score_calibration.py <spoor.db> <qa_truth.json> [--per-point CAM_13 ...]
"""
import argparse
import json
import sqlite3

import numpy as np

from spoor.contracts import FloorCalibration
from spoor.spatial.homography import floor_to_image, site_to_image

ap = argparse.ArgumentParser()
ap.add_argument("db")
ap.add_argument("truth")
ap.add_argument("--per-point", nargs="*", default=[])
a = ap.parse_args()
db = sqlite3.connect(a.db)
truth = json.load(open(a.truth, encoding="utf-8"))


def kind(pid: str) -> str:
    return "floor grid" if pid.startswith("floor_") else "store door" if pid.startswith("store_door") \
        else "story cage" if pid.startswith("cage_") else "scanner"


def stats(e) -> str:
    e = np.asarray(e)
    return f"n={len(e):3d}  median {np.median(e):5.2f}  p95 {np.percentile(e, 95):6.2f}  max {e.max():6.2f} px" if len(e) else "n=  0"


every = {"pose": {}, "floor": {}}
print(f"{'camera':7s} {'points':10s}  pose (3D)                                        | floor-only (x, y)")
for cam, rows in truth["cameras"].items():
    r = db.execute("select payload from calibrations where camera_id=? order by seq desc", (f"cam_{cam}",)).fetchone()
    if not r:
        print(f"{cam:7s} not calibrated ({len(rows)} test points in frame)")
        continue
    cal = FloorCalibration.model_validate_json(r[0])
    xyz = np.array([p["xyz"] for p in rows], float)
    true = np.array([p["uv"] for p in rows], float)
    pose_uv, front = site_to_image(cal, xyz)
    flat_uv, flat_ok = floor_to_image(cal, xyz[:, :2])
    e_pose = np.where(front, np.linalg.norm(pose_uv - true, axis=1), np.inf)
    e_flat = np.where(flat_ok, np.linalg.norm(flat_uv - true, axis=1), np.inf)
    for k in ("scanner", "store door", "story cage", "floor grid"):
        idx = [i for i, p in enumerate(rows) if kind(p["id"]) == k]
        if not idx:
            continue
        every["pose"].setdefault(k, []).extend(e_pose[idx])
        every["floor"].setdefault(k, []).extend(e_flat[idx])
        print(f"{cam:7s} {k:10s}  {stats(e_pose[idx]):48s} | {stats(e_flat[idx])}")
    if cam in a.per_point:
        for i, p in enumerate(rows):
            if kind(p["id"]) != "floor grid":
                print(f"    {p['id']:20s} z={p['xyz'][2]:.2f}  true ({p['uv'][0]:7.1f},{p['uv'][1]:6.1f})  pose err {e_pose[i]:6.2f} px"
                      f"  floor-only err {e_flat[i]:7.2f} px  {'seen' if p['seen'] else 'hidden behind something'}")
print("\nALL CAMERAS")
for k in ("scanner", "store door", "story cage", "floor grid"):
    print(f"  {k:10s}  pose {stats(every['pose'].get(k, []))}   | floor-only {stats(every['floor'].get(k, []))}")
