"""Real-footage test: draw each handshake's outline on its own frames (scan instant, then every second it follows), one
row per scan, so each can be judged by eye: is the outline on the item that was at the scan spot, and does it stay on
it (not a neighbour)? The red dot is the prompt (the scan spot at the scan instant).

  python overlay_sheet.py pexels_4156510 [--clip clip_blur.mp4]
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("dir")
ap.add_argument("--clip", default="clip_blur.mp4")
ap.add_argument("--w", type=int, default=384)
ap.add_argument("--only", default="")
ap.add_argument("--crop", default="", help="x0,y0,x1,y1 of the full frame to show")
ap.add_argument("--out", default="handshakes_sheet.jpg")
a = ap.parse_args()
d = Path(a.dir)
cap = cv2.VideoCapture(str(d / a.clip))
OFFS = [0, 1, 2, 3, 4, 5]
rows = []
for res in sorted((d / "sam").glob("S*.json")):
    j = json.loads(res.read_text())
    if a.only and j["scan_id"] not in a.only.split(","):
        continue
    run, lo, f, fps = j["run"], j["lo"], j["frame"], j["fps"]
    boxes = {}
    for det in run["detections"]:
        boxes.setdefault(lo + det["frame_index"], []).append(det["box_ltrb_px"])
    tiles = []
    for o in OFFS:
        fr = f + round(o * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, fr)
        ok, img = cap.read()
        if not ok or fr > j["hi"]:
            tiles.append(np.zeros_like(tiles[-1]) if tiles else np.zeros((10, a.w, 3), np.uint8)); continue
        for b in boxes.get(fr, []):
            cv2.rectangle(img, (int(b[0]), int(b[1])), (int(b[2]), int(b[3])), (60, 220, 60), 6)
        if o == 0:
            cv2.circle(img, tuple(j["point_px"]), 14, (0, 0, 255), -1)
        if a.crop:
            x0, y0, x1, y1 = map(int, a.crop.split(","))
            img = img[y0:y1, x0:x1]
        img = cv2.resize(img, (a.w, round(a.w * img.shape[0] / img.shape[1])))
        cv2.putText(img, f"{j['scan_id']} +{o}s" if o else f"{j['scan_id']} scan {j['time_s']}s", (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        tiles.append(img)
    rows.append(np.hstack(tiles))
sheet = np.vstack(rows)
cv2.imwrite(str(d / a.out), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
print(sheet.shape)
