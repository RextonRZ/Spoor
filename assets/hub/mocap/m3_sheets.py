"""Lay out the M3 dense hand crops and the bare-head stills as labelled sheets.

  py -X utf8 assets/hub/mocap/m3_sheets.py qa/review/m3_hub
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

D = Path(sys.argv[1])
try:
    font = ImageFont.truetype("arial.ttf", 16)
except OSError:
    font = ImageFont.load_default()


def sheet(files, cols, out, label):
    if not files:
        return
    ims = [Image.open(f).convert("RGB") for f in files]
    w, h = ims[0].size
    sh = Image.new("RGB", (cols * w, ((len(ims) + cols - 1) // cols) * h), (20, 20, 20))
    d = ImageDraw.Draw(sh)
    for i, (f, im) in enumerate(zip(files, ims)):
        x, y = (i % cols) * w, (i // cols) * h
        sh.paste(im, (x, y))
        d.text((x + 6, y + 4), label(f), fill=(255, 255, 0), font=font)
    sh.save(out, quality=85)
    print("wrote", out)


for kind in ("grasp", "release"):
    fs = sorted((D / "dense").glob(f"d_{kind}_*.png"))
    # pairs (L, R) per frame: 2 views x 15 frames -> 6 columns = 3 frames per row
    sheet(fs, 6, D / f"dense_{kind}.jpg", lambda f: f"{f.stem.split('_')[1]} f{int(f.stem.split('_')[2])} "
                                                  f"from {f.stem.split('_')[3]} hand side")
sheet(sorted((D / "heads").glob("head_*.png")), 6, D / "heads_sheet.jpg",
      lambda f: f"f{int(f.stem.split('_')[1])} {f.stem.split('_')[2]}")
