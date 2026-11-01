"""Add more footage to a seeded store (six checkpoints step 5): extra recording windows of the same hub (W1 / W2 on
existing cameras) and the checkpoint cameras' clips, through the API like seed_nokey.py: cameras and the site plan
re-synced from the hub spec (the checkpoint cameras and their visible_by), a clock domain per new camera, each clip
uploaded with its recorder's own start time (clip_starts.json, a recorder export's metadata; the app fits the clocks
itself with fit_camera_clocks.py). Scans are not imported here: a window's other traffic has label ids that repeat
the S2 window's, so only records already in the log (the story parcel's) describe those windows.

  uv run --project ../backend python scripts/ingest_windows.py ../assets/hub/build/renders/W1 [more dirs] [--hosted]
"""
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from seed_nokey import REPO, SITE_ID, guard, load_env, sync_geometry  # noqa: E402

HOSTED = "--hosted" in sys.argv  # synthetic renders only: hosted models may process them (as seed_nokey --hosted)
DIRS = [a for a in sys.argv[1:] if not a.startswith("--")]

env = load_env()
admin = httpx.Client(base_url="http://127.0.0.1:8000", headers={"Authorization": f"Bearer {env['SPOOR_TOKEN_SITE_ADMIN']}"},
                     timeout=600)
spec = json.loads((REPO / "assets/hub/hub_spec.json").read_text(encoding="utf-8"))
sync_geometry(admin, spec)
have = {d["domain"]["name"] for d in admin.get(f"/v1/sites/{SITE_ID}/clock-domains").json()}
for d in spec["clock_domains"]:
    if d["id"] not in have:
        cams = [f"cam_{c['id']}" for c in spec["cameras"] if c["clock_domain"] == d["id"]]
        admin.post(f"/v1/sites/{SITE_ID}/clock-domains", json={"kind": d["kind"], "name": d["id"], "camera_ids": cams}).raise_for_status()
        print("clock domain", d["id"], cams)
for folder in DIRS:
    folder = guard(Path(folder))
    starts = json.loads((folder / "clip_starts.json").read_text(encoding="utf-8"))
    for clip in sorted(folder.glob("*.mp4")):
        cam_id = f"cam_{clip.stem}"
        cams = {c["camera"]["camera_id"]: c for c in admin.get(f"/v1/sites/{SITE_ID}/cameras").json()}
        mine = cams.get(cam_id)
        if mine is None:
            print("skip clip without camera", clip.name)
            continue
        if mine["clock_sync"] is None:
            admin.post(f"/v1/cameras/{cam_id}/clock-syncs", json={
                "offset_ms": 0, "uncertainty_ms": 5000,
                "method": "UNVERIFIED: uploader-declared recording start; no anchor event matched yet",
                "anchor_description": "none yet"}).raise_for_status()
        meta = {"site_id": SITE_ID, "camera_id": cam_id,
                "rights_statement": "Synthetic footage rendered from a fictional hub model; no real people",
                "purpose": "Spoor demonstration", "consent_confirmed": True, "hosted_processing_allowed": HOSTED,
                "retention_days": 30, "recording_start_camera_time": starts[clip.stem],
                "recording_kind": "synthetic_test"}  # fmt: skip
        with clip.open("rb") as fh:
            r = admin.post("/v1/media/uploads", data={"meta": json.dumps(meta)}, files={"file": (clip.name, fh, "video/mp4")})
        r.raise_for_status()
        print("clip", folder.name, clip.name, r.json()["media_id"], r.json()["frames"], "frames")
