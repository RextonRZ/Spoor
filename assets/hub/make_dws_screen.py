"""DWS tunnel screens (scan checkpoints, Rexton 31 Oct): the HMI a dimension-weigh-scan tunnel shows at its exit -
the last parcel's record (camera view with the read box, barcode, weight, L x W x H, dimensional weight, destination)
and the shift counters, as on a Mettler-Toledo TLX / SICK DWS terminal. Fictional brand only ("SUKAT", Malay for
'measure'); no real product names or logos. Static images: the screen is a texture, not live.

  py -X utf8 assets/hub/make_dws_screen.py        -> assets/hub/build/signs/dws_screen_A.png, dws_screen_B.png,
                                                     scan_in_sign.png (the exception store's SCAN IN sign)
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "build" / "signs"
W, H = 1280, 720  # 15.6" 16:9 touch panel, as BeeVision's tunnel HMI (BeeSort video, 2:14)
BG, PANEL, INK, DIM, VAL, OK, AMBER = (18, 86, 160), (12, 58, 112), (236, 242, 250), (170, 196, 226), (250, 214, 60),     (52, 199, 120), (240, 176, 40)
TILE = OUT / "dws_tile_{}.png"  # the tunnel camera's own picture of the last parcel (scanner_photos.py), if made


def font(size, bold=False):
    for name in (("arialbd.ttf", "DejaVuSans-Bold.ttf") if bold else ("arial.ttf", "DejaVuSans.ttf")):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def screen(line, unit, rows, status, tile_png=None, idle=False):
    """BeeVision-like layout: brand + mode in the header, the tunnel camera's picture left, the record right (label,
    value, unit), a status line. Fictional brand."""
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 64], fill=PANEL)
    d.text((24, 12), "SUKAT", font=font(34, True), fill=INK)
    d.text((170, 20), f"DWS {unit}  ·  {line}", font=font(24), fill=DIM)
    d.text((W // 2 + 40, 16), "Measure", font=font(30, True), fill=INK)
    x0, y0, x1, y1 = 24, 84, 760, 630
    d.rectangle([x0 - 3, y0 - 3, x1 + 3, y1 + 3], fill=PANEL)
    if tile_png and Path(tile_png).exists():
        t = Image.open(tile_png).convert("RGB")
        tw = int(t.height * (x1 - x0) / (y1 - y0))  # centre crop to the tile's aspect (no stretch)
        t = t.crop(((t.width - tw) // 2, 0, (t.width + tw) // 2, t.height)).resize((x1 - x0, y1 - y0))
        im.paste(t, (x0, y0))
    else:
        d.rectangle([x0, y0, x1, y1], fill=(22, 24, 28))
        if idle:
            d.text((x0 + 250, y0 + 250), "NO PARCEL", font=font(40, True), fill=DIM)
    d.rectangle([x0, y0, x0 + 120, y0 + 30], fill=PANEL)
    d.text((x0 + 8, y0 + 3), "CAM  TOP", font=font(18), fill=DIM)
    for i, (k, v, u) in enumerate(rows):
        y = 92 + i * 66
        d.ellipse([790, y + 4, 822, y + 36], outline=VAL, width=4)
        d.text((836, y + 6), k, font=font(24), fill=INK)
        d.text((1010, y + 2), v, font=font(32 if len(v) <= 10 else 24, True), fill=VAL)
        if u:
            d.text((1200, y + 8), u, font=font(22), fill=DIM)
    d.rectangle([0, 650, W, H], fill=PANEL)
    d.text((24, 668), "Status:", font=font(26), fill=INK)
    d.text((140, 668), status, font=font(26, True), fill=VAL if not idle else AMBER)
    return im


def screen_a():
    """The record of the parcel in the camera tile (scanner_photos.py --tile), else a sample one."""
    import json
    jp = TILE.with_name("dws_tile_A.json")
    r = json.loads(jp.read_text(encoding="utf-8")) if jp.exists() else dict(
        barcode="CTX488172093561", weight_kg=1.824, length_cm=25.5, width_cm=18.3, height_cm=10.2, dim_weight_kg=0.79,
        destination_chute="C12")
    if r.get("length_cm") is None and r.get("dims_mm"):  # a log from before the DWS fields: the same numbers
        L_, W_, H_ = sorted((x / 10 for x in r["dims_mm"]), reverse=True)
        r.update(length_cm=L_, width_cm=W_, height_cm=H_, weight_kg=r["weight_g"] / 1000,
                 dim_weight_kg=L_ * W_ * H_ / 6000, barcode=r.get("barcode") or r["parcel_id"],
                 destination_chute=r.get("destination_chute") or r.get("truth_chute"))
    vol = round(r["length_cm"] * r["width_cm"] * r["height_cm"])
    return screen("LINE A", "01", [("Width", f"{r['width_cm']:.1f}", "cm"), ("Length", f"{r['length_cm']:.1f}", "cm"),
                                   ("Height", f"{r['height_cm']:.1f}", "cm"), ("Dim Wt", f"{r['dim_weight_kg']:.2f}", "kg"),
                                   ("Volume", f"{vol}", "cm3"), ("Weight", f"{r['weight_kg']:.3f}", "kg"),
                                   ("Barcode", r["barcode"], ""), ("Dest.", r["destination_chute"], "")],
                  "Measurement complete  ·  read OK  ·  1,110 /h", TILE.with_name("dws_tile_A.png"))


def screen_b():
    return screen("LINE B", "02", [(k, "-", "") for k in ("Width", "Length", "Height", "Dim Wt", "Volume", "Weight",
                                                          "Barcode", "Dest.")],
                  "Belt stopped  ·  waiting for parcels", None, idle=True)


def scan_in_sign():
    """The exception store's door sign: the procedure in the hub's two languages (Malay first, as its other signs),
    a mandatory-action style blue disc (ISO 7010 colour) with a white handheld-scanner pictogram."""
    im = Image.new("RGB", (1000, 600), (250, 250, 248))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 1000, 600], outline=(30, 30, 30), width=10)
    d.ellipse([50, 150, 350, 450], fill=(0, 82, 155))
    d.rounded_rectangle([140, 240, 290, 300], 12, fill=(255, 255, 255))  # scanner body (nose to the right)
    d.polygon([(165, 296), (215, 296), (200, 390), (160, 390)], fill=(255, 255, 255))  # grip
    for k in range(4):  # the beam
        d.line([294, 270, 332, 240 + k * 20], fill=(255, 255, 255), width=5)
    d.text((390, 150), "IMBAS SETIAP", font=font(62, True), fill=(20, 20, 20))
    d.text((390, 230), "PARSEL MASUK", font=font(62, True), fill=(20, 20, 20))
    d.line([390, 350, 950, 350], fill=(0, 82, 155), width=6)
    d.text((390, 380), "SCAN EVERY PARCEL IN", font=font(42, True), fill=(0, 82, 155))
    return im


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    screen_a().save(OUT / "dws_screen_A.png")
    screen_b().save(OUT / "dws_screen_B.png")
    scan_in_sign().save(OUT / "scan_in_sign.png")
    print("DWS screens", OUT / "dws_screen_A.png", OUT / "dws_screen_B.png")
