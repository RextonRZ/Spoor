"""Real-footage test, step 1: the camera's shift on every frame (phase correlation on the static wall above the belt),
and a slit-scan through a fixed belt spot (the scan line) so each item crossing can be timed by hand.
  python stab_slit.py clip.mp4 --ref 12 --x 864 --y0 380 --y1 560"""
import argparse, json
import cv2, numpy as np
ap = argparse.ArgumentParser(); ap.add_argument("clip"); ap.add_argument("--ref", type=float, default=12); ap.add_argument("--x", type=int, default=864)
ap.add_argument("--y0", type=int, default=380); ap.add_argument("--y1", type=int, default=560); ap.add_argument("--roi", type=float, default=0.35)
a = ap.parse_args()
cap = cv2.VideoCapture(a.clip); fps = cap.get(5); frames = []
while True:
    ok, f = cap.read()
    if not ok: break
    frames.append(f)
H, W = frames[0].shape[:2]; k = 4
prev, cum, shifts = None, np.zeros(2), []
for f in frames:
    g = cv2.cvtColor(cv2.resize(f, (W // k, H // k)), cv2.COLOR_BGR2GRAY).astype(np.float32)[: int(H // k * a.roi)]
    if prev is not None:
        (dx, dy), _ = cv2.phaseCorrelate(prev, g); cum = cum + np.array([dx, dy]) * k
    shifts.append(cum.copy()); prev = g
S = np.array(shifts); r = int(round(a.ref * fps)); S = S - S[r]   # shift relative to the reference frame
json.dump({"fps": fps, "W": W, "H": H, "ref_frame": r, "shift": S.round(2).tolist()}, open("shift.json", "w"))
cols = []
for i, f in enumerate(frames):
    x = int(round(a.x + S[i, 0])); dy = int(round(S[i, 1]))
    cols.append(f[a.y0 + dy:a.y1 + dy, x:x + 3].mean(axis=1) if 0 <= x < W - 3 else np.zeros((a.y1 - a.y0, 3)))
slit = np.stack(cols, axis=1).astype(np.uint8)          # height x frames x 3
slit = cv2.resize(slit, (len(frames), (a.y1 - a.y0)))
for s in range(0, int(len(frames) / fps) + 1):          # a tick each second
    c = int(s * fps); cv2.line(slit, (c, 0), (c, 8 if s % 5 else 20), (0, 0, 255), 1)
    if s % 2 == 0: cv2.putText(slit, str(s), (c + 2, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
cv2.imwrite("slit.png", cv2.resize(slit, (len(frames) * 2, (a.y1 - a.y0) * 2), interpolation=cv2.INTER_NEAREST))
print("frames", len(frames), "fps", round(fps, 3), "shift range x", S[:, 0].min().round(), S[:, 0].max().round())
