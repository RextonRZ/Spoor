"""Evaluation only (never at runtime): were the handshakes' outlined cartons the scanned parcels?

For each handshake that outlined a carton, the render truth gives every parcel's 3-D centre at the scan's frame. Each
centre goes into the camera through Spoor's validated calibration (pose + lens, held-out error 1-2 cm), and the
handshake is right when the scanned parcel's projection is the one nearest the outlined box's centre and falls inside
the box (with a margin). Also replays the parcel-size rule offline over the stored tracks (no SAM call), so the stored
rows can be judged before and after it. Writes docs/open_weights_proof/handshake_eval.json.

    uv run --project ../backend python scripts/eval_handshakes.py --data .local/backend-data-s2r18c
"""

import argparse
import json
import math
from collections import Counter
from datetime import timedelta, timezone
from pathlib import Path

from spoor.api.services import Services
from spoor.config import Settings
from spoor.contracts import CameraCoverage
from spoor.forensics.journey import latest_plan
from spoor.perception.anchor import parcel_extent_px
from spoor.spatial.homography import site_to_image
from spoor.store import ScanHandshake

ROOT = Path(__file__).resolve().parents[2]
TRUTH = ROOT / "assets" / "hub" / "build" / "truth"
WINDOWS = {"S2": "flow_truth_S2.json", "W1": "flow_truth_W1.json"}
MARGIN = 0.25  # of the box size, each side
# rendered windows: the first render frame of each delivered clip (the Modal render ranges); S2's wide clips start at 1
W1_FIRST = {"CHK_UNLOAD": 170, "CAM_02": 170, "CHK_TUNNEL": 585, "CAM_05": 585, "CAM_01": 685, "CHK_CHUTE": 945,
            "CAM_11": 945}
S2_FIRST = {"CHK_DOCK": 780, "CHK_STORE": 200}


def first_frame(store, media_id, camera):
    """(truth window, first render frame) of a clip: W1's clips were recorded before 14:20 on any camera's clock."""
    start = store.find(CameraCoverage, media_id=media_id)[-1].start_utc
    if start.astimezone(timezone(timedelta(hours=8))).hour == 14 and start.astimezone(timezone(timedelta(hours=8))).minute < 20:
        return "W1", W1_FIRST[camera]
    return "S2", S2_FIRST.get(camera, 1)


def judge(box, own, pts, waybill):
    if own is None:
        return "not_in_truth_view"
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    nearest = min(pts, key=lambda k: math.dist(pts[k], ((x1 + x2) / 2, (y1 + y2) / 2)))
    inside = x1 - MARGIN * bw <= own[0] <= x2 + MARGIN * bw and y1 - MARGIN * bh <= own[1] <= y2 + MARGIN * bh
    return "right" if nearest == waybill and inside else ("near_miss" if nearest == waybill else "other_parcel")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    a = ap.parse_args()
    svc = Services.from_settings(Settings(data_dir=Path(a.data)))
    store = svc.store
    truths = {k: json.loads((TRUTH / f).read_text(encoding="utf-8")) for k, f in WINDOWS.items()}
    hs = [h for h in store.find(ScanHandshake) if h.track_id or h.outcome == "cant_tell"]
    plan = latest_plan(store, hs[0].site_id) if hs else None
    out = []
    for h in hs:
        win, first = first_frame(store, h.media_id, h.camera_id.removeprefix("cam_"))
        cal = svc.valid_calibration(h.camera_id)
        if cal is None or not h.box_px or h.frame_index is None:
            continue
        t = truths[win]
        frame = str(first + h.frame_index)  # the TRUE moment of the frame the box is on (not the logged scan time)
        ids, xyz = zip(*[(p["parcel_id"], p["track"][frame]) for p in t["parcels"] if frame in p["track"]], strict=True)
        uv, front = site_to_image(cal, list(xyz))
        w, hh = cal.image_wh_px
        pts = {i: (float(u), float(v)) for i, (u, v), f in zip(ids, uv, front, strict=True) if f and 0 <= u < w and 0 <= v < hh}
        before = judge(h.box_px, pts.get(h.waybill), pts, h.waybill)
        pw, ph = parcel_extent_px(plan.read_point(h.scan_point_id), cal)
        x1, y1, x2, y2 = h.box_px
        too_big = x2 - x1 > 2 * pw or y2 - y1 > 2 * ph
        out.append({"window": win, "waybill": h.waybill, "camera": h.camera_id.removeprefix("cam_"),
                    "scan_point": h.scan_point_id, "rule": h.rule, "at": h.at_utc.isoformat(), "media": h.media_id, "box": h.box_px,
                    "parcel_px": [round(pw), round(ph)], "truth_px": (o := pts.get(h.waybill)) and [round(o[0]), round(o[1])],
                    "verdict": before, "after_size_rule": "dropped_too_big" if too_big else before})
    def summ(key):
        c = Counter(o[key] for o in out)
        judged = c["right"] + c["near_miss"] + c["other_parcel"]
        return {"verdicts": dict(c), "precision": round(c["right"] / judged, 3) if judged else None,
                "by_rule": {r: dict(Counter(o[key] for o in out if o["rule"] == r)) for r in sorted({o["rule"] for o in out})}}
    summary = {"outlined": len(out), "as_stored": summ("verdict"), "with_size_rule": summ("after_size_rule")}
    dest = ROOT / "docs" / "open_weights_proof" / "handshake_eval.json"
    dest.write_text(json.dumps({"summary": summary, "rows": out}, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
