"""Install-time floor calibration for every CCTV camera, through the backend's own API (POST /v1/cameras/{id}/calibrations).

A real hub does this once per camera: floor marks measured on the plan and clicked in the camera's picture, plus the
lens measured once. The marks come from assets/hub/floor_survey.py (rays through the scene onto open floor, through the
CCTV lens, at the delivered frame size). Like a person would, we use about 24 well-spread marks per camera and keep 8
back to measure the error, each with click noise (1.5 px), all within 20 m of the camera (its working area). The pass thresholds are fixed here, before the results:
median 0.25 m and p95 0.50 m, enough to say which zone and which door.

  uv run --project ../backend python scripts/seed_calibrations.py [--api http://127.0.0.1:8000] [--survey <json>]
"""
import argparse
import json
import random
from pathlib import Path

import httpx

FRONT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--api", default="http://127.0.0.1:8000")
ap.add_argument("--survey", default=str(FRONT.parent / "assets/hub/build/survey/floor_survey_S2.json"))
ap.add_argument("--fit", type=int, default=24)
ap.add_argument("--holdout", type=int, default=8)
ap.add_argument("--click-px", type=float, default=1.5)
ap.add_argument("--only", nargs="*", help="camera names (default: all)")
ap.add_argument("--site", default="site_contoh_hub")
ap.add_argument("--max-range-m", type=float, default=20.0, help="marks within this floor distance of the camera")
a = ap.parse_args()


def load_env() -> dict:
    env = {}
    for line in (FRONT / ".env.local").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def spread(pts: list, n: int, rnd: random.Random) -> list:
    """Farthest-point picks in the picture: marks across the whole view, not a clump."""
    pick = [pts[rnd.randrange(len(pts))]]
    while len(pick) < min(n, len(pts)):
        pick.append(max(pts, key=lambda p: min((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 for q in pick)))
    return pick


env = load_env()
api = httpx.Client(base_url=a.api, headers={"Authorization": f"Bearer {env['SPOOR_TOKEN_SITE_ADMIN']}"}, timeout=30)
survey = json.loads(Path(a.survey).read_text(encoding="utf-8"))
cams = {c["camera"]["camera_id"]: c["camera"] for c in api.get(f"/v1/sites/{a.site}/cameras").raise_for_status().json()}
for name, s in sorted(survey.items()):
    if a.only and name not in a.only:
        continue
    cx, cy = cams[f"cam_{name}"]["position_m"][:2]
    # a surveyor marks the camera's working area; far marks near the horizon turn a pixel of click into metres
    pts = [q for q in s["fit"] + s["holdout"] if (q[2] - cx) ** 2 + (q[3] - cy) ** 2 <= a.max_range_m ** 2]
    if len(pts) < a.fit + a.holdout:
        print(f"{name}: {len(pts)} floor marks in view, not calibrated (the yard's ground is not the hall floor)")
        continue
    rnd = random.Random(f"calib-{name}")
    marks = spread(pts, a.fit + a.holdout, rnd)
    rnd.shuffle(marks)
    click = [[u + rnd.gauss(0, a.click_px), v + rnd.gauss(0, a.click_px), x, y] for u, v, x, y in marks]
    fit, hold = click[:a.fit], click[a.fit:]
    r = api.post(f"/v1/cameras/cam_{name}/calibrations", json={
        "image_points_px": [p[:2] for p in fit], "floor_points_m": [p[2:] for p in fit],
        "holdout_image_points_px": [p[:2] for p in hold], "holdout_floor_points_m": [p[2:] for p in hold],
        "image_wh_px": s["image_wh_px"], "max_median_m": 0.25, "max_p95_m": 0.5,
        "radial_k1": s["lens_k1"], "lens_hfov_deg": s["lens_hfov_deg"],
        "notes": f"install survey: {a.fit} marks + {a.holdout} held out, {a.click_px} px click noise"})
    if r.status_code != 201:
        print(f"{name}: {r.status_code} {r.text[:200]}")
        continue
    c = r.json()
    m, p = c["holdout_error_median_m"], c["holdout_error_p95_m"]
    print(f"{name}: {c['rig_state']}  " + (f"held-out error median {m:.3f} m, p95 {p:.3f} m" if p is not None else c["notes"]))
