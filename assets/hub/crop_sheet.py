"""One labelled sheet of every PNG in a crop folder (collision_crops / qa_crops output), for reviews.
  py -X utf8 assets/hub/crop_sheet.py <dir> <out.jpg> [--cols 4] [--w 520]
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw

ap = argparse.ArgumentParser()
ap.add_argument("dir")
ap.add_argument("out")
ap.add_argument("--cols", type=int, default=4)
ap.add_argument("--w", type=int, default=520)
a = ap.parse_args()
fs = sorted(Path(a.dir).glob("*.png"))
ims = [Image.open(f).convert("RGB") for f in fs]
h = max(int(im.height * a.w / im.width) for im in ims)
rows = (len(ims) + a.cols - 1) // a.cols
sheet = Image.new("RGB", (a.cols * a.w, rows * (h + 18)), (20, 20, 20))
d = ImageDraw.Draw(sheet)
for i, (f, im) in enumerate(zip(fs, ims)):
    x, y = (i % a.cols) * a.w, (i // a.cols) * (h + 18)
    sheet.paste(im.resize((a.w, int(im.height * a.w / im.width))), (x, y + 18))
    d.text((x + 4, y + 3), f.stem[:70], fill=(240, 240, 240))
sheet.save(a.out, quality=88)
print("SHEET", a.out, len(ims))
