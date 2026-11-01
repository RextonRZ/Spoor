"""App logo + icon from Rexton's logo PNGs (assets/brand/spoor_logo_fingerprint_{dark,light}.png).

  python frontend/scripts/build_logo_png.py [--gap 0.26]

- public/brand/spoor-logo-{dark,light}.png: the mark and the wordmark re-spaced (the source's gap was 12 % of the
  mark's height and read cramped in the top bar; --gap is the new gap as a share of the mark's height), trimmed,
  96 px tall (3x the 30 px it is shown at).
- src/app/icon.png (512, transparent) and src/app/apple-icon.png (180, on the app's dark background): the mark
  alone, from the dark version (its indigo holds up on light and dark browser tabs).
The split is the first fully empty pixel column between the mark and the word.
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "assets" / "brand"
PUB = ROOT / "frontend" / "public" / "brand"
APP = ROOT / "frontend" / "src" / "app"
BG = (14, 17, 22, 255)  # #0E1116, the app's ink-black


def split(im):
    """(mark, word) crops of a logo image, each trimmed to its ink, + the mark's top/bottom in the source."""
    a = np.asarray(im)[:, :, 3] > 8
    col = a.sum(0)
    xs = np.nonzero(col)[0]
    gap0 = next(x for x in range(xs[0], xs[-1]) if col[x] == 0)  # first empty column after the mark
    word0 = next(x for x in range(gap0, xs[-1]) if col[x] > 0)
    mark, word = im.crop((xs[0], 0, gap0, im.height)), im.crop((word0, 0, xs[-1] + 1, im.height))
    return mark, word


def trim(im):
    return im.crop(im.split()[3].point(lambda v: 255 if v > 8 else 0).getbbox())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gap", type=float, default=0.26)
    a = ap.parse_args()
    for n in ("dark", "light"):
        im = Image.open(SRC / f"spoor_logo_fingerprint_{n}.png").convert("RGBA")
        mark, word = split(im)
        mh = trim(mark).height
        g = round(a.gap * mh)
        out = Image.new("RGBA", (mark.width + g + word.width, im.height), (0, 0, 0, 0))
        out.alpha_composite(mark, (0, 0))  # same rows as the source: the vertical alignment is kept
        out.alpha_composite(word, (mark.width + g, 0))
        out = trim(out)
        h = 96
        out = out.resize((round(out.width * h / out.height), h), Image.LANCZOS)
        out.save(PUB / f"spoor-logo-{n}.png", optimize=True)
        print(n, "gap", g, "px of mark height", mh, "->", out.size)
        if n == "dark":
            m = trim(mark)
            for size, pad, bg, name in ((512, 0.06, None, "icon.png"), (180, 0.16, BG, "apple-icon.png")):
                side = max(m.size)
                inner = round(size * (1 - 2 * pad))
                mm = m.resize((round(m.width * inner / side), round(m.height * inner / side)), Image.LANCZOS)
                canvas = Image.new("RGBA", (size, size), bg or (0, 0, 0, 0))
                canvas.alpha_composite(mm, ((size - mm.width) // 2, (size - mm.height) // 2))
                canvas.save(APP / name, optimize=True)
                print(name, canvas.size)


if __name__ == "__main__":
    main()
