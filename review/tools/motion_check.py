"""Reviewer's frame-by-frame motion check for one video.

Usage: python3 motion_check.py VIDEO OUTDIR [--dense START_S END_S [x0 y0 x1 y1]]

Writes into OUTDIR:
  overview.jpg   12 evenly spaced frames with frame numbers
  trails_NN.jpg  motion trails per 10 s chunk (colour = time: blue -> red). A gap in a trail = teleport/pop;
                 a trail through solid geometry = clipping; no trail on a "working" person = frozen/miming.
  events.csv     per-frame global diff + local "pop" events (cell jumps much more than its neighbours in time)
  pops.jpg       top local pop events: crops of frames t-1, t, t+1
  dense.jpg      (with --dense) every frame in a time window, optionally cropped
"""
import sys, os, csv
import numpy as np, cv2

def label(img, text):
    cv2.putText(img, text, (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(img, text, (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)
    return img

def tile(imgs, cols):
    h, w = imgs[0].shape[:2]
    rows = (len(imgs) + cols - 1) // cols
    out = np.zeros((rows * h, cols * w, 3), np.uint8)
    for i, im in enumerate(imgs):
        r, c = divmod(i, cols)
        out[r*h:(r+1)*h, c*w:(c+1)*w] = cv2.resize(im, (w, h))
    return out

def main():
    vid, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    cap = cv2.VideoCapture(vid)
    fps = cap.get(cv2.CAP_PROP_FPS) or 10
    frames = []
    while True:
        ok, f = cap.read()
        if not ok: break
        frames.append(f)
    n = len(frames)
    H, W = frames[0].shape[:2]
    sw = 640; sh = int(H * sw / W)
    small = [cv2.resize(f, (sw, sh)) for f in frames]
    gray = [cv2.GaussianBlur(cv2.cvtColor(s, cv2.COLOR_BGR2GRAY), (3, 3), 0).astype(np.float32) for s in small]

    # overview
    idx = np.linspace(0, n - 1, 12).astype(int)
    cv2.imwrite(f"{out}/overview.jpg", tile([label(small[i].copy(), f"f{i} {i/fps:.1f}s") for i in idx], 4),
                [cv2.IMWRITE_JPEG_QUALITY, 85])

    # diffs
    gx, gy = 16, 9
    cw, ch = sw // gx, sh // gy
    gdiff = [0.0]; cells = [np.zeros((gy, gx))]
    for t in range(1, n):
        d = np.abs(gray[t] - gray[t-1])
        gdiff.append(float(d.mean()))
        cells.append(d[:gy*ch, :gx*cw].reshape(gy, ch, gx, cw).mean(axis=(1, 3)))
    cells = np.array(cells)
    events = []
    for t in range(2, n - 1):
        prev, cur, nxt = cells[t-1], cells[t], cells[t+1]
        base = np.median(cells[max(1, t-10):t+10], axis=0) + 0.5
        score = cur / np.maximum(np.maximum(prev, nxt), base)
        for (y, x) in zip(*np.where((score > 3.0) & (cur > 6.0))):
            events.append((float(score[y, x]), t, int(x), int(y), float(cur[y, x])))
    events.sort(reverse=True)
    with open(f"{out}/events.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["kind", "frame", "time_s", "cell_x", "cell_y", "score", "diff"])
        med = np.median(gdiff[1:]) if n > 2 else 0
        for t, g in enumerate(gdiff):
            if t > 0 and g > max(4 * med, 2.0):
                w.writerow(["global_jump", t, f"{t/fps:.2f}", "", "", f"{g/(med+1e-6):.1f}", f"{g:.2f}"])
        for s, t, x, y, c in events[:200]:
            w.writerow(["local_pop", t, f"{t/fps:.2f}", x, y, f"{s:.1f}", f"{c:.1f}"])

    # pops sheet: top 10 distinct events
    picked = []
    for s, t, x, y, c in events:
        if all(abs(t - pt) > 3 or abs(x - px) > 1 or abs(y - py) > 1 for _, pt, px, py, _ in picked):
            picked.append((s, t, x, y, c))
        if len(picked) == 10: break
    rows = []
    for s, t, x, y, c in picked:
        x0 = max(0, (x - 2) * cw); y0 = max(0, (y - 2) * ch); x1 = min(sw, (x + 3) * cw); y1 = min(sh, (y + 3) * ch)
        trip = [label(cv2.resize(small[k][y0:y1, x0:x1], (300, 200)), f"f{k}") for k in (t-1, t, t+1)]
        rows.append(np.hstack(trip))
    if rows:
        cv2.imwrite(f"{out}/pops.jpg", np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])

    # trails per 10 s chunk
    chunk = int(fps * 10)
    for k, start in enumerate(range(0, n, chunk)):
        end = min(n, start + chunk)
        if end - start < 3: continue
        bg = small[start].copy() // 2
        trail = np.zeros_like(bg)
        for t in range(start + 1, end):
            m = (np.abs(gray[t] - gray[t-1]) > 18).astype(np.uint8)
            m = cv2.dilate(m, np.ones((3, 3), np.uint8))
            u = (t - start) / max(1, end - start - 1)
            col = np.array([255 * (1 - u), 60, 255 * u], np.uint8)
            trail[m > 0] = col
        img = np.where(trail.sum(axis=2, keepdims=True) > 0, trail, bg)
        cv2.imwrite(f"{out}/trails_{k:02d}.jpg", label(img, f"trails f{start}-{end-1}  blue=early red=late"),
                    [cv2.IMWRITE_JPEG_QUALITY, 85])

    # dense window
    if "--dense" in sys.argv:
        i = sys.argv.index("--dense")
        a, b = float(sys.argv[i+1]), float(sys.argv[i+2])
        reg = list(map(int, sys.argv[i+3:i+7])) if len(sys.argv) >= i + 7 else None
        imgs = []
        for t in range(int(a * fps), min(n, int(b * fps) + 1)):
            f = frames[t]
            if reg: f = f[reg[1]:reg[3], reg[0]:reg[2]]
            imgs.append(label(cv2.resize(f, (400, int(400 * f.shape[0] / f.shape[1]))), f"f{t}"))
        if imgs:
            cv2.imwrite(f"{out}/dense.jpg", tile(imgs, 6), [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"{vid}: {n} frames @ {fps:.1f} fps, {W}x{H}; global jumps={sum(1 for t,g in enumerate(gdiff) if t and g > max(4*np.median(gdiff[1:]),2))}; local pops={len(events)}")

if __name__ == "__main__":
    main()
