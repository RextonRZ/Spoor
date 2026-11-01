"""Measure the sorter clock (WCS / PLC) against the cameras from shared events, then record it as a fitted clock sync.

The scan tunnel logs "read at T" on the WCS clock; CAM_05 watches the tunnel exit. Every parcel SAM follows past the
tunnel's read point (the plan's SP-TUNNEL, placed in CAM_05's picture by its calibrated pose) gives the camera's time of
that passage. Each tunnel read in the clip is paired with the passage nearest to it after the overall offset (the most
common read-to-passage difference); the backend's robust fit (spatial/clock.py) then drops mismatched pairs and keeps
the anchors and residuals, so the case file can show how time was aligned. Nothing is assumed from NTP or the OSD.

  cd backend; DATA_DIR=... USERS_FILE=... URL_SIGNING_SECRET=... uv run python ../frontend/scripts/fit_wcs_clock.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

import httpx
import numpy as np

from spoor.api.services import Services
from spoor.config import Settings
from spoor.contracts import CameraCoverage, ClockDomain, MediaAsset, ScanEvent
from spoor.forensics.journey import latest_plan
from spoor.perception.anchor import anchor_for

FRONT = Path(__file__).resolve().parents[1]
SITE, CAM, POINT, DOMAIN_NAME = "site_contoh_hub", "cam_CAM_05", "SP-TUNNEL", "clkd_wcs"
NEAR_PX = 45  # a track passes the read point if its centre comes this close (1920 px frame)
PAIR_S = 1.0  # a read and a passage pair if within this of the overall offset

env = {k.strip(): v.strip() for k, v in (line.split("=", 1) for line in (FRONT / ".env.local").read_text(encoding="utf-8")
                                         .splitlines() if "=" in line and not line.startswith("#"))}
svc = Services.from_settings(Settings())
DOMAIN = next(d.clock_domain_id for d in svc.store.find(ClockDomain, site_id=SITE) if d.name == DOMAIN_NAME)
media = next(m for m in svc.store.find(MediaAsset, camera_id=CAM) if m.kind.value == "original")
plan = latest_plan(svc.store, SITE)
anchor = anchor_for(plan.read_point(POINT), svc.valid_calibration(CAM))
print("read point in", CAM, anchor.point_px)

r = svc.run_perception(media.media_id, concept="box")
passes = []
for t in r.tracks:
    obs = sorted((o for o in r.observations if o.track_id == t.track_id), key=lambda o: o.source_frame.frame_index)
    c = np.array([((o.bbox_xyxy_px[0] + o.bbox_xyxy_px[2]) / 2, (o.bbox_xyxy_px[1] + o.bbox_xyxy_px[3]) / 2) for o in obs])
    d = np.linalg.norm(c - np.asarray(anchor.point_px), axis=1)
    i = int(np.argmin(d))
    if d[i] <= NEAR_PX:
        passes.append((obs[i].source_frame.normalized_utc, obs[i].observation_id))
print(f"SAM: {len(r.tracks)} tracks, {len(passes)} pass the tunnel read point")

cov = svc.store.find(CameraCoverage, media_id=media.media_id)[-1]
# raw WCS device times on purpose: this is the clock being measured
reads = [s for s in svc.store.find(ScanEvent, site_id=SITE) if (s.station_id or s.device_id) == POINT
         and s.event_kind.value == "tunnel_read" and s.clock_domain_id == DOMAIN]
lo, hi = cov.start_utc.timestamp() - 30, cov.end_utc.timestamp() + 30
reads = [s for s in reads if lo <= s.device_time_utc.timestamp() <= hi]
print(f"{len(reads)} tunnel reads within the clip")

diffs = [round((p.timestamp() - s.device_time_utc.timestamp()) * 5) / 5 for s in reads for p, _ in passes
         if abs(p.timestamp() - s.device_time_utc.timestamp()) <= 10]
if not diffs:
    sys.exit("no read/passage pairs within 10 s: cannot estimate the offset")
offset = Counter(diffs).most_common(1)[0][0]
print(f"most common read-to-passage difference: {offset:+.1f} s")
anchors = []
for s in reads:
    best = min(passes, key=lambda p: abs(p[0].timestamp() - s.device_time_utc.timestamp() - offset))
    if abs(best[0].timestamp() - s.device_time_utc.timestamp() - offset) <= PAIR_S:
        anchors.append({"device_time": s.device_time_utc.isoformat(), "reference_time": best[0].isoformat(),
                        "anchor_id": f"{s.scan_event_id}~{best[1]}"})
print(f"{len(anchors)} anchors")
api = httpx.Client(base_url="http://127.0.0.1:8000", headers={"Authorization": f"Bearer {env['SPOOR_TOKEN_SITE_ADMIN']}"},
                   timeout=60)
res = api.post(f"/v1/clock-domains/{DOMAIN}/fit", json={
    "anchors": anchors, "base_uncertainty_ms": 100.0,
    "description": f"tunnel reads ({POINT}, {DOMAIN_NAME}) paired with SAM-tracked passages of its read point on {CAM}"})
print(res.status_code, json.dumps(res.json())[:600])
