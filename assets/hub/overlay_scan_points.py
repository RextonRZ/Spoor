"""Draw the site plan's scan points on one camera frame, through the camera's stored calibration (pose + lens), so
each marker says what it is and nothing can be misread (reviewer, 1 Nov):

  dot          a scan device on camera (tunnel, DWS arch, store scan-in)
  pair + bar   an RFID portal: its two antennas, joined across the read zone
  diamond      a sorter event (divert at a chute mouth): no device, the parcel is there at that second
  dashed area  a handheld scan: made somewhere in its measured work area (bag frame, bench, bay rows, door mouths)
Only points in the plan's visible_by for this camera are drawn; a point is named only where this camera sees it at
least half as well as its best camera (others show the mark alone).

Labels sit off the marker on a short leader line, placed so no two labels overlap; a legend explains the marks.

  uv run --project backend python assets/hub/overlay_scan_points.py <spoor.db> <plan.json> <CAM_xx> <frame.png> <out.png>
"""
import json
import sqlite3
import sys

import cv2
import numpy as np

from spoor.contracts import FloorCalibration
from spoor.spatial.homography import site_to_image

db_path, plan_path, cam, frame_path, out_path = sys.argv[1:6]
db = sqlite3.connect(db_path)
cals = {}
for cid, payload in db.execute("select camera_id, payload from calibrations order by seq"):
    cals[cid] = FloorCalibration.model_validate_json(payload)  # the latest version per camera wins
cal = cals[f"cam_{cam}"]


def detail(c: FloorCalibration, xyz) -> float:
    """Pixels per metre at a point (the lens's focal length over its depth): how well a camera sees it."""
    rot = cv2.Rodrigues(np.asarray(c.pose_rvec))[0]
    z = (rot @ np.asarray(xyz, float) + np.asarray(c.pose_tvec))[2]
    f = c.image_wh_px[0] / (2 * np.tan(np.radians(c.lens_hfov_deg / 2)))
    return f / z if z > 0 else 0.0
plan = json.load(open(plan_path, encoding="utf-8"))
img = cv2.imread(frame_path)
H, W = img.shape[:2]
s = W / cal.image_wh_px[0]
RED, BLUE, AMBER, WHITE, INK = (60, 60, 235), (235, 160, 40), (40, 190, 250), (245, 245, 245), (20, 20, 20)
FONT, FS = cv2.FONT_HERSHEY_SIMPLEX, 0.42


def px(xyz):
    uv, front = site_to_image(cal, np.asarray(xyz, float))
    return [(int(u * s), int(v * s)) if f and 0 <= u <= cal.image_wh_px[0] and 0 <= v <= cal.image_wh_px[1] else None
            for (u, v), f in zip(uv, front)]


marks, taken = [], []
for rp in plan["read_points"]:
    sid, kind = rp["scan_point_id"], rp["device_kind"]
    if f"cam_{cam}" not in rp["visible_by"]:
        continue  # only what this camera actually sees (the plan's check); far or hidden points stay off the picture
    seen = True
    probe = (rp.get("device_parts_m") or [rp["position_m"]])[0]
    mine = detail(cal, probe)
    best = max([detail(cals[c], probe) for c in rp["visible_by"] if c in cals] or [mine])
    labelled = mine >= 0.5 * best  # named on the cameras that are a good view of it; elsewhere the mark alone
    parts = rp.get("device_parts_m") or []
    if kind == "rfid_portal" and len(parts) == 2:
        a, b = px(parts)
        if not (a and b):
            continue
        cv2.line(img, a, b, RED, 1, cv2.LINE_AA)
        for q in (a, b):
            cv2.rectangle(img, (q[0] - 3, q[1] - 6), (q[0] + 3, q[1] + 6), RED, -1 if seen else 1)
        anchor = ((a[0] + b[0]) // 2, (a[1] + b[1]) // 2)
    elif parts:
        anchor = px([parts[0]])[0]
        if not anchor:
            continue
        cv2.circle(img, anchor, 5, RED, -1 if seen else 1, cv2.LINE_AA)
    elif kind == "sorter_plc":
        anchor = px([rp["position_m"]])[0]
        if not anchor:
            continue
        d = np.array([(0, -6), (6, 0), (0, 6), (-6, 0)]) + anchor
        cv2.fillPoly(img, [d], AMBER) if seen else cv2.polylines(img, [d], True, AMBER, 1, cv2.LINE_AA)
    else:  # handheld: the measured work area(s) on the floor, dashed
        drawn = []
        for poly in rp.get("work_area_m") or []:
            ring = np.array(poly + poly[:1], float)
            dense = np.vstack([np.linspace(ring[i], ring[i + 1], 24) for i in range(len(poly))])
            pts = px(np.c_[dense, np.full(len(dense), rp.get("work_height_m") or 0.0)])  # at the scan's own height
            for i, (p, q) in enumerate(zip(pts, pts[1:])):
                if p and q and i % 2 == 0 and abs(p[0] - q[0]) + abs(p[1] - q[1]) < 80:
                    cv2.line(img, p, q, BLUE, 2 if seen else 1, cv2.LINE_AA)
                    drawn.append(p)
        if not drawn:
            continue
        anchor = (int(np.mean([d[0] for d in drawn])), int(np.mean([d[1] for d in drawn])))
    if labelled:
        marks.append((anchor, sid.replace("SP-", ""), RED if parts else AMBER if kind == "sorter_plc" else BLUE))

# labels: try offsets around the mark, nearest first; keep the first spot that overlaps no label and stays in frame
LEGEND_H = 22 * 4 + 30
taken += [(0, 0, int(W * 0.42), int(H * 0.075)), (0, H - LEGEND_H - 50, int(W * 0.25), H), (int(W * 0.75), H - 30, W, H)]
for (x, y), text, col in sorted(marks, key=lambda m: m[0][1]):
    (tw, th), _ = cv2.getTextSize(text, FONT, FS, 1)
    for dx, dy in [(d * c, e * r) for r in (22, 36, 50, 64) for c in (1, -1) for d, e in ((1, -1), (0.4, -1), (1, 1))]:
        lx = int(x + dx if dx > 0 else x + dx - tw)
        ly = int(y + dy)
        box = (lx - 2, ly - th - 3, lx + tw + 2, ly + 3)
        if box[0] < 0 or box[1] < 0 or box[2] > W or box[3] > H:
            continue
        if any(not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]) for b in taken):
            continue
        taken.append(box)
        cv2.line(img, (x, y), (lx if dx > 0 else lx + tw, ly - th // 2), col, 1, cv2.LINE_AA)
        cv2.rectangle(img, box[:2], box[2:], INK, -1)
        cv2.putText(img, text, (lx, ly), FONT, FS, WHITE, 1, cv2.LINE_AA)
        break

legend = [("scan device", "dot"), ("RFID portal: 2 antennas", "pair"), ("sorter event (no device)", "diamond"),
          ("handheld scan: work area", "ring")]
x0, y0 = 10, H - 22 * len(legend) - 40
cv2.rectangle(img, (x0 - 6, y0 - 18), (x0 + 250, y0 + 22 * len(legend) - 8), INK, -1)
for i, (t, k) in enumerate(legend):
    cy = y0 + 22 * i
    c = (x0 + 8, cy - 4)
    if k == "dot":
        cv2.circle(img, c, 5, RED, -1, cv2.LINE_AA)
    elif k == "pair":
        cv2.line(img, (c[0] - 6, c[1]), (c[0] + 6, c[1]), RED, 1)
        for q in (c[0] - 6, c[0] + 6):
            cv2.rectangle(img, (q - 2, c[1] - 5), (q + 2, c[1] + 5), RED, -1)
    elif k == "diamond":
        cv2.fillPoly(img, [np.array([(0, -6), (6, 0), (0, 6), (-6, 0)]) + c], AMBER)
    elif k == "ring":
        cv2.ellipse(img, c, (8, 4), 0, 0, 360, BLUE, 1, cv2.LINE_AA)
    else:
        cv2.circle(img, c, 5, RED, 1, cv2.LINE_AA)
    cv2.putText(img, t, (x0 + 24, cy), FONT, FS, WHITE, 1, cv2.LINE_AA)
cv2.imwrite(out_path, img)
print("wrote", out_path, len(marks), "scan points in frame")
