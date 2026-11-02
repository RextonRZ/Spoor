"""Evaluation only (never at runtime): were the handshakes' outlined cartons the scanned parcels?

For each handshake that outlined a carton, the render truth gives every parcel's 3-D centre at the scan's frame. Each
centre goes into the camera through Spoor's validated calibration (pose + lens, held-out error 1-2 cm), and the
handshake is right when the scanned parcel's projection is the one nearest the outlined box's centre and falls inside
the box (with a margin); its number on the outline is right when the scanned parcel is the one nearest it. Reports,
per kind of scan, how many outlines carry a label (labelled) and how many of those are right (target: all), how many
were withheld ("can't tell which carton"), and the story parcel's own checkpoints. Writes
docs/open_weights_proof/handshake_eval.json.

    uv run --project ../backend python scripts/eval_handshakes.py --data .local/backend-data-s2r18c
"""

import argparse
import json
import math
from datetime import timedelta, timezone
from pathlib import Path

from spoor.api.services import Services
from spoor.config import Settings
from spoor.contracts import CameraCoverage
from spoor.spatial.homography import site_to_image
from spoor.store import ScanHandshake

ROOT = Path(__file__).resolve().parents[2]
TRUTH = ROOT / "assets" / "hub" / "build" / "truth"
WINDOWS = {"S2": "flow_truth_S2.json", "W1": "flow_truth_W1.json", "W2": "flow_truth_W2.json"}
MARGIN = 0.25  # of the box size, each side
# rendered windows: the first render frame of each delivered clip (the Modal render ranges); S2's wide clips start at 1
# W1 as re-rendered with the quiet unload door (2 Nov, start re-pinned 7.9 s earlier: every range +79 frames)
W1_FIRST = {"CHK_UNLOAD": 255, "CAM_02": 255, "CHK_TUNNEL": 664, "CAM_05": 664, "CAM_01": 764, "CHK_CHUTE": 990,
            "CAM_11": 1024}
S2_FIRST = {"CHK_DOCK": 780, "CHK_STORE": 200}
W2_FIRST = {"CHK_CHUTE": 30, "CHK_CAGE_W": 220}


def first_frame(store, media_id, camera):
    """(truth window, first render frame) of a clip, from when it was recorded (W1 14:09-14:12, W2 14:21, S2 14:32)."""
    local = store.find(CameraCoverage, media_id=media_id)[-1].start_utc.astimezone(timezone(timedelta(hours=8)))
    if local.minute < 20:
        return "W1", W1_FIRST[camera]
    if local.minute < 30:
        return "W2", W2_FIRST[camera]
    return "S2", S2_FIRST.get(camera, 1)


def carton_fit(cal, xyz, dims, box):
    """(IoU, SAM area / true area) of SAM's box against the true carton's projected box, best of the two yaws; the
    true box is clipped to the picture (a carton cut by the frame edge is outlined only where it is seen)."""
    if xyz is None or not dims:
        return None, None
    L, W, H = dims
    best = (0.0, 99.0)
    for lx, wy in ((L, W), (W, L)):
        corners = [(xyz[0] + dx, xyz[1] + dy, xyz[2] + dz) for dx in (-lx / 2, lx / 2) for dy in (-wy / 2, wy / 2) for dz in (0.0, H)]
        uv, front = site_to_image(cal, corners)
        if not front.all():
            continue
        w, h = cal.image_wh_px
        tb = (max(0.0, uv[:, 0].min()), max(0.0, uv[:, 1].min()), min(w, uv[:, 0].max()), min(h, uv[:, 1].max()))
        if tb[2] <= tb[0] or tb[3] <= tb[1]:
            continue
        ix = max(0.0, min(tb[2], box[2]) - max(tb[0], box[0])) * max(0.0, min(tb[3], box[3]) - max(tb[1], box[1]))
        a_t, a_s = (tb[2] - tb[0]) * (tb[3] - tb[1]), (box[2] - box[0]) * (box[3] - box[1])
        iou = ix / (a_t + a_s - ix) if a_t + a_s - ix > 0 else 0.0
        if iou > best[0]:
            best = (round(float(iou), 3), round(float(a_s / a_t), 2) if a_t > 0 else 99.0)
    return best


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
    gone = store.invalid_ids()  # purged clips (superseded renders): their rows are not the current evidence
    hs = [h for h in store.find(ScanHandshake) if (h.track_id or h.outcome == "cant_tell") and h.media_id not in gone]
    out = []
    for h in hs:
        win, first = first_frame(store, h.media_id, h.camera_id.removeprefix("cam_"))
        cal = svc.valid_calibration(h.camera_id)
        if cal is None or not h.box_px or h.frame_index is None:
            continue
        t = truths[win]
        frame = str(first + h.frame_index)  # the TRUE moment of the frame the box is on (not the logged scan time)
        ids, xyz = zip(*[(p["parcel_id"], p["track"][frame]) for p in t["parcels"] if frame in p["track"]], strict=True)
        dims = {p["parcel_id"]: p.get("dims_m") for p in t["parcels"]}
        uv, front = site_to_image(cal, list(xyz))
        w, hh = cal.image_wh_px
        pts = {i: (float(u), float(v)) for i, (u, v), f in zip(ids, uv, front, strict=True) if f and 0 <= u < w and 0 <= v < hh}
        before = judge(h.box_px, pts.get(h.waybill), pts, h.waybill)
        # carton-sized? the true carton's projected box (both orientations; yaw is not in the truth) vs SAM's box
        iou, ratio = carton_fit(cal, xyz[ids.index(h.waybill)] if h.waybill in ids else None, dims.get(h.waybill), h.box_px)
        out.append({"window": win, "waybill": h.waybill, "camera": h.camera_id.removeprefix("cam_"),
                    "scan_point": h.scan_point_id, "event": h.event_kind, "rule": h.rule, "at": h.at_utc.isoformat(),
                    "media": h.media_id, "box": h.box_px, "outcome": h.outcome, "labelled": h.labelled,
                    "truth_px": (o := pts.get(h.waybill)) and [round(o[0]), round(o[1])], "verdict": before,
                    # the scanned parcel is the one nearest the outline: a label with its number on it is right
                    "identity_right": before in ("right", "near_miss"), "iou": iou, "size_ratio": ratio,
                    # a label is right only on the scanned parcel AND carton-sized (not its tray, bag or carrier)
                    "carton_right": before in ("right", "near_miss") and iou is not None and iou >= 0.3 and ratio <= 2.5})

    def kind(o):
        return ("cage" if o["scan_point"].startswith("SP-CAGE") else "handheld") if o["rule"] == "work_area" else             {"point": "divert", "tunnel_exit": "tunnel exit"}[o["rule"]]

    def summ(rows):
        shown = [o for o in rows if o["outcome"] == "outlined" and o["labelled"]]
        wrong = [o for o in shown if not o["identity_right"]]
        tray = [o for o in shown if o["identity_right"] and not o["carton_right"]]
        return {"outlines": len(rows), "labelled": len(shown), "withheld": len(rows) - len(shown),
                "labelled_right": len(shown) - len(wrong),
                "label_precision": round((len(shown) - len(wrong)) / len(shown), 3) if shown else None,
                "strict_right": sum(o["verdict"] == "right" for o in shown),
                "coverage_of_right": round(len(shown) / max(1, sum(o["identity_right"] for o in rows)), 3),
                "wrong_labels": [f"{o['waybill']} {o['camera']} {o['at'][11:19]}" for o in wrong],
                "not_carton_sized": [f"{o['waybill']} {o['camera']} {o['at'][11:19]} iou {o['iou']} x{o['size_ratio']}" for o in tray]}

    story = json.loads((TRUTH / "scenario_S2.json").read_text(encoding="utf-8"))["story_parcel"]
    summary = {"all": summ(out), "by_type": {k: summ([o for o in out if kind(o) == k]) for k in sorted({kind(o) for o in out})},
               "story": [{"at": o["at"][11:22], "event": o["event"], "camera": o["camera"], "outcome": o["outcome"],
                          "labelled": o["labelled"], "verdict": o["verdict"], "iou": o["iou"], "x": o["size_ratio"]} for o in sorted(out, key=lambda o: o["at"])
                         if o["waybill"] == story]}
    dest = ROOT / "docs" / "open_weights_proof" / "handshake_eval.json"
    dest.write_text(json.dumps({"summary": summary, "rows": out}, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
