"""Blur a box (given at the reference frame) that follows the camera's measured shift: faces never leave this script.
  python blur_box.py clip.mp4 shift.json x0 y0 x1 y1 out.mp4"""
import json, sys
import cv2, numpy as np
clip, sj, x0, y0, x1, y1, out = sys.argv[1], sys.argv[2], *map(int, sys.argv[3:7]), sys.argv[7]
S = np.array(json.load(open(sj))["shift"])
cap = cv2.VideoCapture(clip); fps = cap.get(5); W, H = int(cap.get(3)), int(cap.get(4))
w = cv2.VideoWriter(out, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H)); i = 0
while True:
    ok, f = cap.read()
    if not ok: break
    dx, dy = S[min(i, len(S) - 1)]
    a, b, c, d = int(max(0, x0 + dx)), int(max(0, y0 + dy)), int(min(W, x1 + dx)), int(min(H, y1 + dy))
    if c > a and d > b:
        f[b:d, a:c] = cv2.GaussianBlur(f[b:d, a:c], (0, 0), 18)
    w.write(f); i += 1
w.release(); print("blurred", i, "frames")
