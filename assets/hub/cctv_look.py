"""Turn a clean Blender render into a CCTV-looking frame, in the order a real camera does it:
lens (barrel distortion, vignette, softness) -> sensor (grain, worse in the dark) -> ISP (over-sharpening, cool cast,
flat colour) -> OSD burned in (camera name + its own clock) -> H.265 at low quality (blocking, chroma bleed).

The lens k1 and the OSD time come from the RENDER side (evaluator-only render_truth.yaml in the real pipeline);
Spoor's runtime never sees them. Every frame carries a small 'SYNTHETIC' mark (simulated data labelled end to end).

  uv run python assets/hub/cctv_look.py <in.png> <out.png> --cam CAM_09 --label "REJECT CHUTE" ^
      [--k1 -0.06] [--qp 33] [--osd-time "2026-10-28 14:32:07"] [--compare <side_by_side.png>]
"""

import argparse
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np


def lens(img, k1, hfov_deg=103.0, vignette=0.38, blur_sigma=0.9):
    h, w = img.shape[:2]
    f = w / (2 * np.tan(np.radians(hfov_deg / 2)))
    u, v = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    x, y = (u - w / 2) / f, (v - h / 2) / f
    r2 = x * x + y * y
    edge = (w / 2 / f) ** 2  # keep the left/right edge midpoints in place, corners bend in (barrel)
    scale = (1 - k1 * r2) / (1 - k1 * edge)
    mx = (x * scale * f + w / 2).astype(np.float32)
    my = (y * scale * f + h / 2).astype(np.float32)
    out = cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    rn = np.sqrt(r2 / r2.max())
    out = out.astype(np.float32) * (1 - vignette * rn ** 2.2)[..., None]
    # lateral chromatic aberration: red and blue land slightly apart toward the edges (cheap lens)
    for ch, k in ((2, 1.0012), (0, 0.9988)):
        sx = ((u - w / 2) * k + w / 2).astype(np.float32)
        sy = ((v - h / 2) * k + h / 2).astype(np.float32)
        out[..., ch] = cv2.remap(out[..., ch], sx, sy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return cv2.GaussianBlur(out, (0, 0), blur_sigma)


def dome(img, rng, smudge=False, web=False):
    """Dome-bubble flaws on 1–2 cameras only (pack): a soft greasy smudge, or a spider web catching the light."""
    h, w = img.shape[:2]
    layer = np.zeros((h, w), np.float32)
    if smudge:
        cx, cy = int(w * 0.72), int(h * 0.3)
        cv2.ellipse(layer, (cx, cy), (int(w * 0.16), int(h * 0.12)), 25, 0, 360, 1.0, -1)
        layer = cv2.GaussianBlur(layer, (0, 0), w * 0.04) * 0.28
        img = img * (1 - layer[..., None]) + cv2.GaussianBlur(img, (0, 0), 9) * layer[..., None] + 25 * layer[..., None]
    if web:
        ox, oy = int(w * 0.93), int(h * 0.08)
        for k in range(9):
            a = np.radians(95 + k * 11 + rng.uniform(-3, 3))
            ln = rng.uniform(0.25, 0.45) * w
            cv2.line(layer, (ox, oy), (int(ox + ln * np.cos(a)), int(oy + ln * np.sin(a))), 1.0, 2, cv2.LINE_AA)
        for r in np.linspace(0.05, 0.35, 7) * w:
            cv2.ellipse(layer, (ox, oy), (int(r), int(r)), 0, 95, 195, 0.8, 1, cv2.LINE_AA)
        layer = cv2.GaussianBlur(layer, (0, 0), 2.5) * 0.35
        img = img + 200 * layer[..., None]
    return img


def sensor(img, rng, sigma=3.6):
    lum = img.mean(axis=2, keepdims=True) / 255.0
    gain = sigma * (1.6 - lum)  # more grain in the shadows, like a small sensor at high gain
    luma_noise = rng.normal(0, 1, img.shape[:2])[..., None] * gain
    chroma_noise = rng.normal(0, 0.4, img.shape) * gain
    return img + luma_noise + chroma_noise


def isp(img):
    img = np.clip(img, 0, 255)
    blur = cv2.GaussianBlur(img, (0, 0), 1.3)
    img = img + 0.4 * (img - blur)  # mild DSP sharpening halo on edges
    grey = img.mean(axis=2, keepdims=True)
    img = grey + 0.68 * (img - grey)  # low saturation
    img = img * np.array([1.03, 1.02, 0.94])  # BGR: slight green-cyan cast (cheap sensor AWB under LED)
    img = 9 + img * (238 / 255)  # slightly lifted blacks, compressed range
    return np.clip(img, 0, 255).astype(np.uint8)


def osd(img, cam, label, when, mark=True):
    h, w = img.shape[:2]
    s = w / 2688

    def put(t, org, scale, thick):
        cv2.putText(img, t, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thick + 3, cv2.LINE_AA)
        cv2.putText(img, t, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (235, 235, 235), thick, cv2.LINE_AA)

    put(when, (int(40 * s), int(70 * s)), 1.5 * s, max(1, int(3 * s)))
    put(f"{cam}  {label}", (int(40 * s), h - int(50 * s)), 1.3 * s, max(1, int(3 * s)))
    if mark:
        put("SYNTHETIC - fictional hub", (w - int(560 * s), h - int(30 * s)), 0.8 * s, max(1, int(2 * s)))
    return img


PRIVATE = "ml/evaluation/blind_test/private/"  # gitignored; the only place unmarked stills may be written


def h265(img, qp):
    with tempfile.TemporaryDirectory() as td:
        src, enc, dec = Path(td) / "in.png", Path(td) / "f.mp4", Path(td) / "out.png"
        cv2.imwrite(str(src), img)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-c:v", "libx265", "-pix_fmt", "yuv420p",
                        "-x265-params", f"qp={qp}:keyint=1:log-level=error", str(enc)], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(enc), "-frames:v", "1", str(dec)], check=True)
        return cv2.imread(str(dec))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--cam", default="CAM_09")
    ap.add_argument("--label", default="")
    ap.add_argument("--k1", type=float, default=-0.06)
    ap.add_argument("--qp", type=int, default=33)
    ap.add_argument("--osd-time", default="2026-10-28 14:32:07")
    ap.add_argument("--seed", type=int, default=9)
    ap.add_argument("--compare", default="")
    ap.add_argument("--smudge", action="store_true")
    ap.add_argument("--web", action="store_true")
    ap.add_argument("--unmarked", action="store_true",
                    help=f"private blind test only: refused unless dst is under {PRIVATE}")
    a = ap.parse_args()
    if a.unmarked and PRIVATE not in Path(a.dst).resolve().as_posix():
        raise SystemExit(f"--unmarked output must go under {PRIVATE} (gitignored); demo footage is always marked")
    raw = cv2.imread(a.src)
    if raw is None:
        raise SystemExit(f"cannot read {a.src}")
    rng = np.random.default_rng(a.seed)
    out = isp(sensor(dome(lens(raw, a.k1), rng, a.smudge, a.web), rng))
    out = h265(osd(out, a.cam, a.label, a.osd_time, mark=not a.unmarked), a.qp)
    cv2.imwrite(a.dst, out)
    if a.compare:
        hw = (raw.shape[1] // 2, raw.shape[0] // 2)
        sbs = np.hstack([cv2.resize(raw, hw, interpolation=cv2.INTER_AREA),
                         cv2.resize(out, hw, interpolation=cv2.INTER_AREA)])
        for t, x in (("clean render", 20), ("after CCTV pass", hw[0] + 20)):
            cv2.putText(sbs, t, (x, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 6, cv2.LINE_AA)
            cv2.putText(sbs, t, (x, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.imwrite(a.compare, sbs)
    print(f"wrote {a.dst}")


if __name__ == "__main__":
    main()
