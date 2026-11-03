"""Publish the turntables (spin_render.py's output) to the web app: every frame re-encoded as a smaller WebP (a ring
should load in about a second), and spin.json beside them.

  python assets/tour/publish_spin.py assets/tour/spin frontend/public/tour/<case>/spin [--q 64]
"""
import argparse
import shutil
from pathlib import Path

from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("dst")
ap.add_argument("--q", type=int, default=64)
a = ap.parse_args()
src, dst = Path(a.src), Path(a.dst)
n, before, after = 0, 0, 0
for f in sorted(src.glob("*/*/f*.webp")):
    out = dst / f.relative_to(src)
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.open(f).convert("RGB").save(out, "WEBP", quality=a.q, method=6)
    n += 1
    before += f.stat().st_size
    after += out.stat().st_size
shutil.copy(src / "spin.json", dst / "spin.json")
rings = len({f.parent for f in dst.glob("*/*/f*.webp")})
print(f"published {n} frames in {rings} rings: {before / 1e6:.1f} MB -> {after / 1e6:.1f} MB ({after / max(rings, 1) / 1e6:.2f} MB a ring)")
