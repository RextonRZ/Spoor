"""How the journey reel looks (tick 0125, Task 1): Spoor's own type and colours on the CCTV, calm and readable in one
second. Text is drawn with Pillow from the app's fonts (Inter; JetBrains Mono for the tag), on a 2x RGBA layer that is
scaled down onto the frame, so edges stay clean after H.264. One top bar (time, step, chip; a sub-line under it), a
progress rail of every chapter, SAM's mask edge with a dark halo, a small tag for the number. Cards (intro, a wait,
the answer) sit on their own camera frame, blurred and darkened. Nothing is drawn in the bottom 56 px: the render's own
on-screen display and the web player's controls live there. No em dashes; times in MYT."""

import re
from functools import cache, lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1280, 720
S = 2  # supersampling of the overlay layer
ROOT = Path(__file__).resolve().parents[4]
FONTS = ROOT / "assets" / "fonts"
LOGO = ROOT / "assets" / "brand" / "spoor_logo_fingerprint_dark.png"

INK, MUTE = (242, 243, 245), (163, 168, 179)
SUB = (212, 215, 222)  # the bar's sub-line: lighter than MUTE, it sits on footage
INDIGO = (99, 102, 241)
# chip tones: (border / dot colour, text colour); the fill is the border colour at 18 %
TONES = {"scan": ((34, 197, 94), (74, 222, 128)), "last": ((34, 197, 94), (74, 222, 128)),
         "seen": ((163, 168, 179), (229, 231, 235)), "noscan": ((239, 68, 68), (248, 113, 113)),
         "record": ((239, 68, 68), (248, 113, 113)), "wait": ((107, 114, 128), (156, 163, 175)),
         "card": ((107, 114, 128), (156, 163, 175))}
CHIPS = {"scan": "Scanned", "last": "Last scan", "seen": "On camera", "noscan": "Not scanned in", "record": "Records disagree"}
OUTLINE = (74, 222, 128)


@cache
def font(size: int, weight: int = 400, mono: bool = False) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONTS / ("JetBrainsMono.ttf" if mono else "Inter.ttf")), size * S)
    f.set_variation_by_axes([weight] if mono else [min(32, max(14, size)), weight])
    return f


def _layer() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    im = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def _compose(frame: np.ndarray, layer: Image.Image) -> np.ndarray:
    """The 2x overlay scaled down and laid over the BGR frame."""
    small = np.asarray(layer.resize((W, H), Image.LANCZOS), dtype=np.float32)
    a = small[:, :, 3:4] / 255.0
    rgb = small[:, :, 2::-1]  # RGBA -> BGR
    return (frame.astype(np.float32) * (1 - a) + rgb * a).astype(np.uint8)


def _text(d, xy, s, size, weight=400, color=INK, alpha=255, mono=False, anchor="ls", tnum=False):
    d.text((xy[0] * S, xy[1] * S), s, font=font(size, weight, mono), fill=(*color, alpha), anchor=anchor,
           features=["tnum"] if tnum else None)


def text_w(s: str, size: int, weight: int = 400, mono: bool = False, tnum: bool = False) -> float:
    return font(size, weight, mono).getlength(s, features=["tnum"] if tnum else None) / S


def _gradient(layer: Image.Image, height: int, top_alpha: float = 0.82):
    g = np.zeros((height * S, W * S, 4), np.uint8)
    # solid behind the words (the sub-line sat where the old ramp had faded to ~10 %, unreadable on a bright floor),
    # then a smooth fade below them
    u = np.linspace(0.0, 1.0, height * S)
    fade = np.clip((u - 0.62) / 0.38, 0, 1)
    ramp = ((1 - fade * fade * (3 - 2 * fade)) * top_alpha * 255).astype(np.uint8)
    g[:, :, :3] = (10, 11, 14)
    g[:, :, 3] = ramp[:, None]
    layer.alpha_composite(Image.fromarray(g, "RGBA"), (0, 0))


def chip(d, right_x: float, cy: float, tone: str, label: str):
    border, ink = TONES.get(tone, TONES["seen"])
    tw = text_w(label, 15, 600)
    x0, x1, y0, y1 = right_x - tw - 24, right_x, cy - 14, cy + 14
    d.rounded_rectangle((x0 * S, y0 * S, x1 * S, y1 * S), radius=14 * S, fill=(*border, 46), outline=(*border, 153), width=S)
    _text(d, (x0 + 12, cy), label, 15, 600, ink, anchor="lm")


def rail(d, y: float, tones: list[str], cur: int, x0: float = 24, x1: float = W - 24):
    """One dot per chapter: done ink 70 %, the current one an indigo ring, future ink 25 %; red where the records fail."""
    n = len(tones)
    if n < 2:
        return
    xs = [x0 + (x1 - x0) * i / (n - 1) for i in range(n)]
    d.line((xs[0] * S, y * S, xs[-1] * S, y * S), fill=(*INK, 51), width=2 * S)
    for i, (x, t) in enumerate(zip(xs, tones, strict=True)):
        red = t in ("noscan", "record")
        a = 179 if i < cur else 64 if i > cur else 255
        col = (239, 68, 68) if red else (107, 114, 128) if t in ("wait",) else INK
        r = 4
        if i == cur:
            d.ellipse(((x - 6) * S, (y - 6) * S, (x + 6) * S, (y + 6) * S), outline=(*INDIGO, 255), width=2 * S)
            col, a = (INDIGO if not red else (239, 68, 68)), 255
        d.ellipse(((x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S), fill=(*col, a))


def top_bar(frame: np.ndarray, *, time: str, title: str, tone: str | None, sub: str = "", tones: list[str] | None = None,
            cur: int = 0, note: str = "", rise: float = 1.0) -> np.ndarray:
    """The one top bar on a footage frame: time · title, the chip on the right, the progress rail, the sub-line.
    rise < 1: the chapter's first frames, its words rising 8 px into place as they fade in."""
    return _over(frame, _bar(time, title, tone, sub, tuple(tones or ()), cur, note, round(min(1.0, rise), 2)))


def _shadow(layer: Image.Image, draw) -> None:
    """A soft dark halo under the words drawn by draw(d): readable on any frame, invisible on a dark one."""
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    draw(ImageDraw.Draw(sh))
    a = sh.getchannel("A").filter(ImageFilter.GaussianBlur(3 * S))
    dark = Image.new("RGBA", layer.size, (6, 7, 9, 0))
    dark.putalpha(a.point(lambda v: min(255, int(v * 0.9))))
    layer.alpha_composite(dark)


@lru_cache(maxsize=256)
def _bar(time, title, tone, sub, tones, cur, note, rise=1.0) -> np.ndarray:
    layer, d = _layer()
    _gradient(layer, 132 if sub else 88, 0.86)
    if sub or note:
        _shadow(layer, lambda d_: (sub and _text(d_, (24, 84), sub, 18, 500, INK), note and _text(d_, (16, H - 20), note, 14, 500, INK)))
    e = 1 - (1 - rise) ** 3  # ease-out
    a, dy = int(255 * e), 8 * (1 - e)
    _text(d, (24, 34 + dy), time, 22, 500, INK, a, tnum=True)
    _text(d, (24 + text_w(time, 22, 500, tnum=True) + 16, 34 + dy), title, 26, 600, INK, a)
    if tone in CHIPS:
        chip(d, W - 24, 27, tone, CHIPS[tone])
    if tones:
        rail(d, 56, list(tones), cur)
    if sub:
        _text(d, (24, 84 + dy), sub, 18, 500, SUB, a)
    if note:  # a still with no on-screen display of its own (the tunnel reader's photo): its source, OSD-style
        _text(d, (16, H - 20), note, 14, 500, SUB)
    return _small(layer)


def _small(layer: Image.Image) -> np.ndarray:
    """The 2x overlay as a 1x premultiplied BGR + alpha array, ready to lay over frames."""
    small = np.asarray(layer.resize((W, H), Image.LANCZOS), dtype=np.float32)
    a = small[:, :, 3:4] / 255.0
    return np.concatenate([small[:, :, 2::-1] * a, a], axis=2)


def _over(frame: np.ndarray, ov: np.ndarray, x: int = 0, y: int = 0) -> np.ndarray:
    out = frame.copy()
    h, w = ov.shape[:2]
    x1, y1 = min(W, x + w), min(H, y + h)
    if x1 <= x or y1 <= y:
        return out
    roi = out[y:y1, x:x1].astype(np.float32)
    o = ov[: y1 - y, : x1 - x]
    out[y:y1, x:x1] = (roi * (1 - o[:, :, 3:4]) + o[:, :, :3]).astype(np.uint8)
    return out


def outline(frame: np.ndarray, poly: list[list[float]] | None, box: list[float] | None, opacity: float = 1.0):
    """SAM's mask edge (else its box): a 4 px dark halo, then the 2 px green line. Returns the top-left anchor point."""
    out = frame.copy()
    if poly:
        pts = np.array(poly, np.int32)
        cv2.polylines(out, [pts], True, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.polylines(out, [pts], True, OUTLINE[::-1], 2, cv2.LINE_AA)
        top = (int(pts[:, 0].min()), int(pts[:, 1].min()), int(pts[:, 0].max()))
    elif box:
        p1, p2 = (round(box[0]), round(box[1])), (round(box[2]), round(box[3]))
        cv2.rectangle(out, p1, p2, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.rectangle(out, p1, p2, OUTLINE[::-1], 2, cv2.LINE_AA)
        top = (p1[0], p1[1], p2[0])
    else:
        return frame, None
    if opacity < 1.0:
        out = cv2.addWeighted(out, opacity, frame, 1 - opacity, 0)
    return out, top


@lru_cache(maxsize=32)
def _tag_patch(text: str) -> np.ndarray:
    tw, th = int(text_w(text, 14, 500, mono=True) + 16), 24
    im = Image.new("RGBA", ((tw + 2) * S, (th + 2) * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((S, S, (tw + 1) * S, (th + 1) * S), radius=4 * S, fill=(10, 11, 14, 199), outline=(*OUTLINE, 255), width=S)
    d.text(((8 + 1) * S, (th / 2 + 2) * S), text, font=font(14, 500, True), fill=(229, 231, 235, 255), anchor="lm")
    small = np.asarray(im.resize((tw + 2, th + 2), Image.LANCZOS), dtype=np.float32)
    a = small[:, :, 3:4] / 255.0
    return np.concatenate([small[:, :, 2::-1] * a, a], axis=2)


def tag(frame: np.ndarray, text: str, anchor: tuple[int, int, int], min_y: int = 100) -> np.ndarray:
    """The number on a small dark tag 6 px above the outline (moved to stay on screen, with a leader line)."""
    patch = _tag_patch(text)
    ph, pw = patch.shape[:2]
    x0, y_top, _x_right = anchor
    x = int(min(max(8, x0), W - pw - 8))
    y = int(y_top - 6 - ph)
    moved = y < min_y
    if moved:
        y = min_y
    out = _over(frame, patch, x, y)
    if moved:
        cv2.line(out, (x + 10, y + ph), (int(x0) + 4, int(y_top)), OUTLINE[::-1], 1, cv2.LINE_AA)
    return out


def blurred(frame: np.ndarray | None) -> np.ndarray:
    """A card's background: its camera frame to cover, darkened to ~25 % and blurred, calmer on the text side."""
    if frame is None:
        return np.full((H, W, 3), (15, 12, 11), np.uint8)
    h, w = frame.shape[:2]
    k = max(W / w, H / h)
    img = cv2.resize(frame, (round(w * k), round(h * k)), interpolation=cv2.INTER_AREA)
    dx, dy = (img.shape[1] - W) // 2, (img.shape[0] - H) // 2
    img = cv2.GaussianBlur(img[dy:dy + H, dx:dx + W], (0, 0), 8)
    img = (img.astype(np.float32) * 0.25).astype(np.uint8)
    g = np.linspace(0.85, 0.4, W, dtype=np.float32)[None, :, None]
    return (img.astype(np.float32) * (1 - g) + np.array((14, 11, 10), np.float32) * g).astype(np.uint8)


def card(bg: np.ndarray, lines: list[tuple[str, int, int, tuple]], *, rise: float = 1.0, logo: bool = False,
         footer: bool = False, dots: list[tuple[str, str, bool]] | None = None) -> np.ndarray:
    """Text block left, vertically centred. lines: (text, size, weight, colour). rise 0..1 fades the text up 8 px."""
    layer, d = _layer()
    alpha = int(255 * rise)
    off = 8 * (1 - rise)
    heights = [size * 1.45 for _, size, _, _ in lines] + ([96] if dots else []) + ([60] if logo else [])
    y = (H - sum(heights)) / 2 + off
    x = 72
    if logo and LOGO.exists():
        lg = Image.open(LOGO).convert("RGBA")
        lg = lg.resize((round(lg.width * 44 * S / lg.height), 44 * S), Image.LANCZOS)
        if alpha < 255:
            lg.putalpha(lg.getchannel("A").point(lambda v: v * alpha // 255))
        layer.alpha_composite(lg, (int(x * S), int(y * S)))
        y += 60
    for text, size, weight, color in lines:
        y += size * 1.1
        _text(d, (x, y), text, size, weight, color, alpha, tnum=bool(re.match(r"^\d\d:\d\d", text)))
        y += size * 0.35
    if dots:  # the checkpoints as a compact rail: label under each dot
        y += 30
        n = len(dots)
        x1 = min(W - 96, x + 168 * (n - 1))
        xs = [x + (x1 - x) * i / max(1, n - 1) for i in range(n)]
        d.line((xs[0] * S, y * S, xs[-1] * S, y * S), fill=(*INK, int(0.25 * alpha)), width=3 * S)
        for xi, (name, tone, here) in zip(xs, dots, strict=True):
            col = TONES.get(tone, TONES["seen"])[0]
            if here:
                d.ellipse(((xi - 13) * S, (y - 13) * S, (xi + 13) * S, (y + 13) * S), outline=(*INDIGO, alpha), width=3 * S)
            d.ellipse(((xi - 8) * S, (y - 8) * S, (xi + 8) * S, (y + 8) * S), fill=(*col, alpha))
            _text(d, (xi, y + 40), name, 18, 600 if here else 500, INK if here else MUTE, alpha, anchor="ms")
    if footer:
        if LOGO.exists():
            lg = Image.open(LOGO).convert("RGBA")
            lg = lg.resize((round(lg.width * 32 * S / lg.height), 32 * S), Image.LANCZOS)
            layer.alpha_composite(lg, (24 * S, (H - 56) * S))
            fx = 24 + lg.width / S + 8
        else:
            fx = 24
        _text(d, (fx + 8, H - 34), "Every parcel leaves a trail.", 16, 400, MUTE)
    return _compose(bg, layer)


def still_card(photo: np.ndarray, label: str | None, caption: str) -> tuple[np.ndarray, tuple[int, int, int] | None]:
    """The tunnel reader's photo as a card: dark ground, the photo at ~70 % height with a hairline border, its caption."""
    bg = np.full((H, W, 3), (15, 12, 11), np.uint8)
    ph = round(H * 0.6)
    pw = round(photo.shape[1] * ph / photo.shape[0])
    if pw > W - 160:
        pw = W - 160
        ph = round(photo.shape[0] * pw / photo.shape[1])
    img = cv2.resize(photo, (pw, ph), interpolation=cv2.INTER_AREA)
    x0, y0 = (W - pw) // 2, 128
    mask = np.zeros((ph, pw), np.uint8)
    cv2.rectangle(mask, (8, 0), (pw - 9, ph - 1), 255, -1)
    cv2.rectangle(mask, (0, 8), (pw - 1, ph - 9), 255, -1)
    for cx, cy in ((8, 8), (pw - 9, 8), (8, ph - 9), (pw - 9, ph - 9)):
        cv2.circle(mask, (cx, cy), 8, 255, -1)
    roi = bg[y0:y0 + ph, x0:x0 + pw]
    roi[mask > 0] = img[mask > 0]
    layer, d = _layer()
    d.rounded_rectangle((x0 * S, y0 * S, (x0 + pw) * S, (y0 + ph) * S), radius=8 * S, outline=(42, 45, 53, 255), width=S)
    _text(d, (x0, y0 + ph + 30), caption, 17, 400, MUTE)
    out = _compose(bg, layer)
    return out, ((x0 + 12, y0 + 12, x0 + pw) if label else None)
