"""CONTOH Express shipping labels + stickers as one texture atlas, and the label registry the scenes use.

Fictional brand, fictional IDs (carrier_waybill scheme "CTX" + 12 digits), fake barcode (bars derived from the ID,
not a real symbology), fictional recipient ("Penerima #nnnn") on real town names/postcodes. Tiles 0–31 are
reserved for scenario parcels (their IDs are written into the scenario truth files); 32+ are background parcels.

  cd backend && uv run --with pillow python ../assets/hub/make_labels.py
Writes assets/hub/build/labels/label_atlas.png and labels.json (render side; evaluator truth reads labels.json).
"""

import hashlib
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
OUT = HERE / "build" / "labels"
FONT = HERE / "build" / "third_party" / "fonts" / "BarlowCondensed-Bold.ttf"
COLS, ROWS, TW, TH = 32, 40, 128, 192  # 1280 tiles (10 x 15 cm at 128 x 192 px): every parcel keeps a unique waybill
STICKER_TILES = 8  # the last 8 tiles are stickers
DESTS = [("C01", "PEN", "Pulau Pinang", "10450 George Town"), ("C02", "AOR", "Kedah / Perlis", "05000 Alor Setar"),
         ("C03", "IPH", "Perak", "30000 Ipoh"), ("C04", "KLG", "Klang", "41200 Klang"),
         ("C05", "KUL", "Kuala Lumpur", "50450 Kuala Lumpur"), ("C06", "SBN", "Negeri Sembilan", "70000 Seremban"),
         ("C07", "MLK", "Melaka", "75000 Melaka"), ("C08", "JHB", "Johor Bahru", "80000 Johor Bahru"),
         ("C09", "KTN", "Pahang", "25000 Kuantan"), ("C10", "KBR", "Kelantan / Terengganu", "15000 Kota Bharu"),
         ("C11", "BKI", "Sabah", "88000 Kota Kinabalu"), ("C12", "KCH", "Sarawak", "93000 Kuching")]
TEAL = (14, 124, 123)
STICKERS = [("MUDAH PECAH", "FRAGILE", (200, 30, 30)), ("BAYAR SEMASA", "COD", (230, 120, 10)),
            ("ARAH ATAS", "THIS WAY UP", (30, 30, 30)), ("MUDAH PECAH", "FRAGILE", (200, 30, 30)),
            ("COD", "RM 89.00", (230, 120, 10)), ("JANGAN BASAH", "KEEP DRY", (20, 80, 170)),
            ("PRIORITI", "PRIORITY", (14, 124, 123)), ("BERAT", "HEAVY", (120, 60, 20))]


def font(size):
    return ImageFont.truetype(str(FONT), size) if FONT.exists() else ImageFont.load_default()


def waybill(rnd):
    return "CTX" + "".join(str(rnd.randint(0, 9)) for _ in range(12))


def label_tile(pid, dest, rnd):
    im = Image.new("RGB", (TW, TH), (246, 246, 240))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, TW, 26], fill=TEAL)
    d.text((5, 2), "CONTOH Express", font=font(19), fill=(255, 255, 255))
    d.text((5, 30), f"{dest[1]}  {dest[0]}", font=font(30), fill=(0, 0, 0))
    bars = hashlib.sha256(pid.encode()).digest()  # fake barcode: widths from the ID's hash
    x = 6
    for b in bars:
        for bit in range(0, 8, 2):
            w = 1 + ((b >> bit) & 1)
            if (b >> (bit + 1)) & 1:
                d.rectangle([x, 70, x + w - 1, 108], fill=(0, 0, 0))
            x += w
            if x > TW - 6:
                break
        if x > TW - 6:
            break
    d.text((6, 109), f"{pid[:3]} {pid[3:7]} {pid[7:11]} {pid[11:]}", font=font(15), fill=(0, 0, 0))
    d.line([4, 128, TW - 4, 128], fill=(0, 0, 0), width=1)
    d.text((5, 130), f"Kepada: Penerima #{rnd.randint(1000, 9999)}", font=font(13), fill=(20, 20, 20))
    d.text((5, 145), f"No. {rnd.randint(1, 99)}, Jalan Contoh {rnd.randint(1, 12)}", font=font(13), fill=(20, 20, 20))
    d.text((5, 160), dest[3], font=font(13), fill=(20, 20, 20))
    d.text((5, 175), f"{rnd.randint(1, 30) / 10:.1f} kg  ·  {rnd.choice(['COD', 'PREPAID', 'PREPAID', 'PREPAID'])}",
           font=font(12), fill=(60, 60, 60))
    return im


def sticker_tile(top, bottom, col):
    im = Image.new("RGB", (TW, TH), col)
    d = ImageDraw.Draw(im)
    d.rectangle([4, 4, TW - 5, TH - 5], outline=(255, 255, 255), width=3)
    for txt, y, size in ((top, 55, 26), (bottom, 100, 32)):
        while size > 10 and d.textlength(txt, font=font(size)) > TW - 18:  # shrink to fit the sticker
            size -= 1
        d.text(((TW - d.textlength(txt, font=font(size))) / 2, y), txt, font=font(size), fill=(255, 255, 255))
    return im


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(20261029)
    atlas = Image.new("RGB", (COLS * TW, ROWS * TH), (246, 246, 240))
    labels, seen = [], set()
    n_labels = COLS * ROWS - STICKER_TILES
    for t in range(n_labels):
        pid = waybill(rnd)
        while pid in seen:
            pid = waybill(rnd)
        seen.add(pid)
        dest = DESTS[rnd.randrange(len(DESTS))]
        atlas.paste(label_tile(pid, dest, rnd), ((t % COLS) * TW, (t // COLS) * TH))
        labels.append({"tile": t, "parcel_id": pid, "scheme": "carrier_waybill", "chute": dest[0], "dest_code": dest[1],
                       "destination": dest[2], "reserved_for_scenarios": t < 32})
    for k, (a, b, col) in enumerate(STICKERS):
        t = n_labels + k
        atlas.paste(sticker_tile(a, b, col), ((t % COLS) * TW, (t // COLS) * TH))
    atlas.save(OUT / "label_atlas.png")
    (OUT / "labels.json").write_text(json.dumps({"cols": COLS, "rows": ROWS, "label_tiles": n_labels,
                                                 "sticker_tiles": list(range(n_labels, n_labels + STICKER_TILES)),
                                                 "labels": labels}, indent=1), encoding="utf-8")
    print(f"{n_labels} labels + {STICKER_TILES} stickers -> {OUT / 'label_atlas.png'}")


if __name__ == "__main__":
    main()
