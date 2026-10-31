"""Build the Spoor logo SVGs (owner_final_0815: the FINAL logo is the fingerprint parcel box - "every parcel leaves a
trace": the box carries its own print; never presented as fingerprinting people). Rebuilt as exact geometry from Rexton's
PNGs (assets/brand/spoor_logo_fingerprint_{light,dark}.png), not traced from them.

Symbol: an isometric box (a hexagon split into three faces). Top face: evenly spaced straight ridges along one edge
direction. Left and right faces: nested rounded "L" ridges, concentric round each face's outer lower corner (mirrored),
like fingerprint ridges. One stroke weight, round caps, the same thin gap along every box edge. Small mark (<= 32 px,
favicon): 3 ridges per face, heavier stroke. Wordmark: "Spoor" in Google Sans Flex 700 (OFL-1.1,
@fontsource-variable/google-sans-flex), outlined to paths so the SVG renders the same everywhere.

Run: uv run --project ../backend --with fonttools --with brotli python scripts/build_logo.py
"""

import io
import math
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "public" / "brand"
FONT = HERE.parent / "node_modules/@fontsource-variable/google-sans-flex/files/google-sans-flex-latin-wght-normal.woff2"
INDIGO = {"light": "#4F46E5", "dark": "#6366F1"}
WORD = {"light": "#0E1116", "dark": "#FFFFFF"}
CX, CY, R = 62.0, 61.0, 58.0
TRACK = 0.02  # wordmark tracking, -2 % of the em  # the box's centre and corner radius in the 124 x 122 symbol box


def _pt(o, e1, e2, u, v):
    return (o[0] + u * e1[0] + v * e2[0], o[1] + u * e1[1] + v * e2[1])


def symbol(color: str, *, small: bool = False) -> str:
    """The symbol's SVG elements. `small` = the simplified mark for <= 32 px: 3 ridges per face, heavier stroke."""
    c30 = math.cos(math.radians(30))
    C = (CX, CY)
    T, B = (CX, CY - R), (CX, CY + R)
    UL, UR = (CX - R * c30, CY - R / 2), (CX + R * c30, CY - R / 2)
    LL, LR = (CX - R * c30, CY + R / 2), (CX + R * c30, CY + R / 2)
    sub = lambda p, q: (p[0] - q[0], p[1] - q[1])  # noqa: E731
    n_top, n_side = (3, 3) if small else (4, 4)
    sw = R * (0.15 if small else 0.112)  # stroke width (ridge : gap about 1 : 1, as the PNG)
    g = 0.10 if small else 0.075  # the gap along the box edges (face units, beyond the stroke's half width)
    paths = []
    # top face: origin UL, a along UL->C (down-right), b along UL->T (up-right); ridges at constant b
    o, e1, e2 = UL, sub(C, UL), sub(T, UL)
    for i in range(n_top):
        b = g + (1 - 2 * g) * (i + 0.5) / n_top
        p0, p1 = _pt(o, e1, e2, g, b), _pt(o, e1, e2, 1 - g, b)
        paths.append(f"M{p0[0]:.2f} {p0[1]:.2f} L{p1[0]:.2f} {p1[1]:.2f}")
    # side faces: origin at the outer lower corner, u along the bottom edge (towards B), v up the outer edge;
    # ridge i = the rounded L at max(u, v) = r_i, from the outer edge to the bottom edge
    # as the PNG: the right face's outer ridge hugs the seam up to the centre; the left face stops short of the seam,
    # leaving room for the short stub at the bottom corner
    for o, ub, vt, r_max in ((LL, B, UL, 1 - 2 * g if small else 0.8), (LR, B, UR, 1 - 2 * g)):
        e1, e2 = sub(ub, o), sub(vt, o)
        for i in range(n_side):
            r = g + (r_max - g) * (i + 1) / n_side
            rho = min(0.8 * r, 0.42)  # corner rounding: near quarter circles, like the PNG's fingerprint loops
            s0 = _pt(o, e1, e2, g, r)
            s1 = _pt(o, e1, e2, max(g, r - rho), r)
            cq = _pt(o, e1, e2, r, r)
            s2 = _pt(o, e1, e2, r, max(g, r - rho))
            s3 = _pt(o, e1, e2, r, g)
            paths.append(f"M{s0[0]:.2f} {s0[1]:.2f} L{s1[0]:.2f} {s1[1]:.2f} Q{cq[0]:.2f} {cq[1]:.2f} "
                         f"{s2[0]:.2f} {s2[1]:.2f} L{s3[0]:.2f} {s3[1]:.2f}")
    if not small:
        # the short separate ridge in the seam at the bottom corner (as in the PNG)
        s0, s1 = _pt(B, sub(UL, LL), (0, 0), g + 0.02, 0), _pt(B, sub(UL, LL), (0, 0), 0.30, 0)
        paths.append(f"M{s0[0]:.2f} {s0[1]:.2f} L{s1[0]:.2f} {s1[1]:.2f}")
    return "".join(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw:.2f}" stroke-linecap="round" '
                   f'stroke-linejoin="round"/>' for d in paths)


def wordmark_paths(text: str, size: float, x0: float, baseline: float) -> tuple[str, float]:
    """Outline `text` in Google Sans Flex 700 as one SVG path; returns (path d, advance width)."""
    font = TTFont(io.BytesIO(FONT.read_bytes()))
    font = instantiateVariableFont(font, {"wght": 700})
    gs, cmap = font.getGlyphSet(), font.getBestCmap()
    scale = size / font["head"].unitsPerEm
    pen = SVGPathPen(gs)
    x = 0.0
    prev = None
    kern = {}
    if "GPOS" not in font:
        kern = {}
    for ch in text:
        g = cmap[ord(ch)]
        tp = TransformPen(pen, (scale, 0, 0, -scale, x0 + x * scale, baseline))
        gs[g].draw(tp)
        x += gs[g].width + kern.get((prev, g), 0) - TRACK * font["head"].unitsPerEm  # (tighter, as the PNG)
        prev = g
    return pen.getCommands(), x * scale


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    word, adv = wordmark_paths("Spoor", 96, 138, 98)
    width = 138 + adv + 6
    for theme in ("light", "dark"):
        suffix = "" if theme == "light" else "-dark"
        full = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.1f} 122" role="img" aria-label="Spoor">'
                f"{symbol(INDIGO[theme])}<path d=\"{word}\" fill=\"{WORD[theme]}\"/></svg>\n")  # fmt: skip
        (OUT / f"spoor-logo{suffix}.svg").write_text(full, encoding="utf-8")
        mark = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 124 122" role="img" aria-label="Spoor">'
                f"{symbol(INDIGO[theme])}</svg>\n")  # fmt: skip
        (OUT / f"spoor-mark{suffix}.svg").write_text(mark, encoding="utf-8")
    small = symbol(INDIGO["dark"], small=True)
    (OUT / "spoor-mark-small.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 124 122" role="img" aria-label="Spoor">{small}</svg>\n',
        encoding="utf-8")  # fmt: skip
    # favicon / app icon: the simplified mark on a near-black rounded square
    icon = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160"><rect width="160" height="160" rx="36" '
            f'fill="#0B0C10"/><g transform="translate(18 19)">{small}</g></svg>\n')  # fmt: skip
    (OUT / "spoor-icon.svg").write_text(icon, encoding="utf-8")
    (HERE.parent / "src" / "app" / "icon.svg").write_text(icon, encoding="utf-8")
    print("wrote", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
