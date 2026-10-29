"""Safety-sign textures for the demo hub, in the format real Malaysian workplace signs use.

  py -X utf8 assets/hub/make_signs.py

Sources (nothing invented):
- Layout, wording and sizes copy the QuickSign catalogue (Safetyware Sdn Bhd, Malaysia, 2025 edition): 300 x 400 mm
  portrait, 1 mm HIPS for indoor use. Warning signs: yellow board, black/yellow hazard stripes top and bottom, the
  Malay header + line ABOVE the triangle, the English header + line BELOW (e.g. WS 115 "AWAS / TRAK ANGKAT SUSUN /
  CAUTION / FORKLIFT TRUCK"). Danger signs (WS 021): yellow board, triangle on top, BAHAYA / DANGER below.
  Mandatory signs (MS 017 / 027 / 038): solid blue board, white pictogram, Malay then English in white below.
  The wording below is the catalogue's own. Only the layout is copied, not the supplier's name.
- Colours / sign families: MS 2558:2022 and ISO 7010 (red prohibition, blue mandatory, yellow warning, green safe
  condition).
- Pictograms: the ISO 7010 symbols as drawn on Wikimedia Commons (public domain), downloaded to
  build/third_party/iso7010/. CCTV has no ISO symbol: a plain camera silhouette in a warning triangle, as WS 053.
- Font: Barlow Condensed Bold (OFL), close to the condensed grotesque printed on these signs.
Output: build/signs/<id>.png (600 x 800 px = 2 px/mm) + signs.json (id, size_mm, wording, source).
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HUB = Path(__file__).resolve().parent
ISO = HUB / "build" / "third_party" / "iso7010"
FONT = HUB / "build" / "third_party" / "fonts" / "BarlowCondensed-Bold.ttf"
OUT = HUB / "build" / "signs"
W, H = 600, 800  # 300 x 400 mm
# board colours = the ISO pictograms' own (sampled), so symbol and board match as on the printed signs; the warning
# board is the catalogue's lemon yellow and the ISO triangle fill (249, 168, 0) is recoloured to it
YELLOW, BLUE, RED, GREEN, BLACK, WHITE = (255, 206, 0), (0, 83, 135), (183, 31, 46), (35, 127, 82), (20, 20, 20), (255, 255, 255)

SIGNS = [  # id, family, header_ms, line_ms, header_en, line_en, pictogram, source
    ("ws115_forklift", "warning", "AWAS", "TRAK ANGKAT SUSUN", "CAUTION", "FORKLIFT TRUCK", "W014", "QuickSign WS 115"),
    ("ws116_slippery", "warning", "AWAS", "PERMUKAAN LICIN", "CAUTION", "SLIPPERY SURFACE", "W011", "QuickSign WS 116"),
    ("ws021_machinery", "danger", "BAHAYA", "Mesin bergerak, jauhi tangan", "DANGER", "Moving machinery, keep hands away",
     "W024", "QuickSign WS 021 (ISO W024 pictogram)"),
    ("ws053_cctv", "cctv", "CCTV", "", "In Operation", "", "camera", "QuickSign WS 053"),
    ("ms017_vest", "mandatory", "", "Jaket keselamatan\nmesti dipakai", "", "Safety vests\nmust be worn", "M015",
     "QuickSign MS 017"),
    ("ms027_shoes", "mandatory", "", "Gunakan kasut\nkeselamatan", "", "Wear safety shoes", "M008", "QuickSign MS 027"),
    ("ms038_walkway", "mandatory", "", "Pejalan kaki\nikut laluan ini", "", "Pedestrian must\nuse this route", "M024",
     "QuickSign MS 038"),
    ("ps061_conveyor", "prohibition", "", "Dilarang berjalan atau\nberdiri di atas penghantar", "",
     "Do not walk or stand\non conveyor", "P004", "QuickSign PS 061 (ISO P004 pictogram)"),
    ("p002_nosmoking", "prohibition", "", "DILARANG MEROKOK", "", "NO SMOKING", "P002", "ISO P002 + catalogue wording"),
    ("e003_firstaid", "safe", "", "PERTOLONGAN CEMAS", "", "FIRST AID", "E003", "ISO E003 + catalogue wording"),
]


def font(px):
    return ImageFont.truetype(str(FONT), px)


def centred(d, y, text, px, fill, max_w=W - 60):
    for line in text.split("\n"):
        f = font(px)
        while d.textlength(line, font=f) > max_w and px > 12:
            px -= 2
            f = font(px)
        d.text(((W - d.textlength(line, font=f)) / 2, y), line, font=f, fill=fill)
        y += int(px * 1.08)
    return y


def pictogram(code, size):
    im = Image.open(ISO / f"{code}.png").convert("RGBA")
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if a and abs(r - 249) < 12 and abs(g - 168) < 30 and b < 40:  # ISO triangle yellow -> board yellow
                px[x, y] = (*YELLOW, a)
    im.thumbnail((size, size), Image.LANCZOS)
    return im


def camera_triangle(size):
    im = Image.new("RGBA", (size, int(size * 0.87)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    s, h = size, int(size * 0.87)
    d.polygon([(s / 2, 0), (s, h), (0, h)], fill=BLACK)
    m = s * 0.09
    d.polygon([(s / 2, m * 1.7), (s - m, h - m * 0.75), (m, h - m * 0.75)], fill=YELLOW)
    cx, cy, k = s * 0.47, h * 0.66, s * 0.62  # bullet camera on a wall bracket, tilted down, inside the border
    d.polygon([(cx - 0.24 * k, cy - 0.10 * k), (cx + 0.14 * k, cy - 0.19 * k), (cx + 0.18 * k, cy - 0.06 * k),
               (cx - 0.20 * k, cy + 0.03 * k)], fill=BLACK)  # body
    d.polygon([(cx + 0.14 * k, cy - 0.21 * k), (cx + 0.24 * k, cy - 0.23 * k), (cx + 0.27 * k, cy - 0.05 * k),
               (cx + 0.18 * k, cy - 0.04 * k)], fill=BLACK)  # hood
    d.rectangle([cx - 0.06 * k, cy, cx - 0.02 * k, cy + 0.16 * k], fill=BLACK)  # arm
    d.rectangle([cx - 0.16 * k, cy + 0.16 * k, cx + 0.08 * k, cy + 0.2 * k], fill=BLACK)  # mount plate
    return im


def stripes(d, y0, y1):
    d.rectangle([0, y0, W, y1], fill=YELLOW)
    for x in range(-W, W * 2, 50):
        d.polygon([(x, y1), (x + 25, y1), (x + 25 + (y1 - y0), y0), (x + (y1 - y0), y0)], fill=BLACK)


def make(sid, fam, h_ms, l_ms, h_en, l_en, pic):
    bg = {"warning": YELLOW, "danger": YELLOW, "cctv": YELLOW, "mandatory": BLUE, "prohibition": WHITE,
          "safe": GREEN}[fam]
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    ink = WHITE if fam in ("mandatory", "safe") else BLACK
    if fam == "warning":  # WS 115 layout
        stripes(d, 0, 46)
        stripes(d, H - 46, H)
        y = centred(d, 58, h_ms, 112, BLACK)
        centred(d, y - 6, l_ms, 40, BLACK)
        p = pictogram(pic, 330)
        im.paste(p, ((W - p.width) // 2, 240), p)
        y = centred(d, 585, h_en, 112, BLACK)
        centred(d, y - 6, l_en, 40, BLACK)
    elif fam in ("danger", "cctv"):  # WS 021 / WS 053 layout: triangle on top, text below
        p = camera_triangle(470) if pic == "camera" else pictogram(pic, 470)
        im.paste(p, ((W - p.width) // 2, 40), p)
        y = 470
        y = centred(d, y, h_ms, 96 if fam == "danger" else 130, BLACK)
        if l_ms:
            y = centred(d, y - 4, l_ms, 36, BLACK)
        y = centred(d, y + 4, h_en, 96 if fam == "danger" else 64, BLACK)
        if l_en:
            centred(d, y - 4, l_en, 36, BLACK)
    else:  # mandatory / prohibition / safe: pictogram, then Malay, then English
        if fam == "prohibition":
            d.rectangle([0, 0, W - 1, H - 1], outline=(200, 200, 200), width=3)
        p = pictogram(pic, 440)
        im.paste(p, ((W - p.width) // 2, 50), p)
        y = centred(d, 520, l_ms, 52, ink if fam != "prohibition" else RED)
        centred(d, y + 10, l_en, 46, ink)
    d.rectangle([0, 0, W - 1, H - 1], outline=(90, 90, 90), width=2)  # board edge
    im.save(OUT / f"{sid}.png")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    meta = []
    for sid, fam, h_ms, l_ms, h_en, l_en, pic, src in SIGNS:
        make(sid, fam, h_ms, l_ms, h_en, l_en, pic)
        meta.append({"id": sid, "family": fam, "size_mm": [300, 400], "material": "1 mm HIPS (indoor)",
                     "wording_ms": " ".join(x for x in (h_ms, l_ms) if x).replace("\n", " "),
                     "wording_en": " ".join(x for x in (h_en, l_en) if x).replace("\n", " "),
                     "pictogram": pic, "source": src})
    (OUT / "signs.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    sheet = Image.new("RGB", (W * 5 // 2, H * 2 // 2), (40, 40, 40))
    for k, m in enumerate(meta):
        im = Image.open(OUT / f"{m['id']}.png").resize((W // 2, H // 2))
        sheet.paste(im, ((k % 5) * W // 2, (k // 5) * H // 2))
    sheet.save(OUT / "_sheet.png")
    print("signs:", [m["id"] for m in meta])
