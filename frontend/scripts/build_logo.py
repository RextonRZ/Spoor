"""Build the Spoor logo SVGs (owner_style_0136, update 02:08): an "S" drawn as an evidence trail, rebuilt by hand as exact
geometry from the chosen ChatGPT concept (assets/brand/logo_concept_chatgpt.png), never traced from the raster.

Symbol: one stroke weight, rounded caps, hollow nodes where the trail starts (camera detections), evenly spaced dots
for the inferred stretches, a filled dot where the trail ends. Wordmark: "Spoor" in Google Sans Flex at weight 700
(OFL-1.1, @fontsource-variable/google-sans-flex), outlined to paths so the SVG renders the same everywhere.

Run: uv run --project ../backend --with fonttools --with brotli python scripts/build_logo.py
"""

import io
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
SW = 6.0  # one stroke weight for every line
DOT_R = 3.2  # inferred dots
NODE_R = 6.2  # hollow start nodes (ring stroke 3.4)
END_R = 7.4  # filled end dots

# The S, in a 124 x 122 box: upper bowl, middle bar, lower bowl (coordinates read off the concept, then made exact).
SOLID = [
    "M21.8 12 C12 12 5 22 5 35 C5 48 15 58 30 58 L86 58",  # upper-left bowl into the middle bar
    "M34.2 12 L74 12",  # top bar leaving the first node
    "M99 60.5 C110 64 116 73 116 85 C116 97 110 106 101.5 109.5",  # lower-right bowl into the end dot
    "M9.6 83.4 C5.5 89 5.8 100 16 106 C20 108.6 25 110 32 110 L94 110",  # lower-left bowl into the bottom bar
]
TOP_DOTS = [(86, 12), (97.5, 12.4), (108.4, 15.2), (115.6, 23.6), (117, 34.6), (112.6, 45.2)]  # top-right, inferred
MID_DOTS = [(34, 79), (44, 79), (54, 79), (64, 79), (74, 79)]  # lower bar, inferred
NODES = [(28, 12), (14, 79)]
ENDS = [(93, 58), (101, 110)]


def symbol(color: str, *, small: bool = False) -> str:
    """The symbol's SVG elements. `small` = the simplified mark for <= 32 px: fewer, larger dots, heavier stroke."""
    sw = SW * (1.45 if small else 1)
    parts = [f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" '
             f'stroke-linejoin="round"/>' for d in SOLID]  # fmt: skip
    dots = (TOP_DOTS[::2] + MID_DOTS[::2]) if small else (TOP_DOTS + MID_DOTS)
    r = DOT_R * (1.6 if small else 1)
    parts += [f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}"/>' for x, y in dots]
    parts += [f'<circle cx="{x}" cy="{y}" r="{NODE_R}" fill="none" stroke="{color}" stroke-width="{3.4 * (1.3 if small else 1)}"/>'
              for x, y in NODES]  # fmt: skip
    parts += [f'<circle cx="{x}" cy="{y}" r="{END_R * (1.15 if small else 1)}" fill="{color}"/>' for x, y in ENDS]
    return "".join(parts)


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
        x += gs[g].width + kern.get((prev, g), 0)
        prev = g
    return pen.getCommands(), x * scale


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    word, adv = wordmark_paths("Spoor", 96, 148, 98)
    width = 148 + adv + 6
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
