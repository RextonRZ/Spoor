"""Reference floor plan for Spoor (design target for the frontend agent).

Reads the real hub spec (metres, X east, Y north) and draws an architectural-style
plan in the Spoor v2 dark palette, with a SAMPLE journey overlay showing every
evidence style once.  Output: plan.svg + plan.png (2x).
"""
import json, math, sys

spec = json.load(open(sys.argv[1]))
OUT = sys.argv[2]

S = 17.0            # px per metre
OX, OY = 96, 170    # plan origin offset (room for yards / header)
W_M, H_M = 60.0, 40.0
CW, CH = int(OX + W_M * S + 64), int(OY + H_M * S + 120)

# palette (Spoor style v2)
BG, SURF, SURF2 = "#0B0C10", "#121318", "#1B1D24"
FLOOR = "#16171D"
INK_S, INK, INK_M, INK_F = "#F4F5F7", "#C9CCD3", "#8B909B", "#5A5F69"
HAIR = "rgba(255,255,255,0.07)"
HAIR2 = "rgba(255,255,255,0.13)"
MACH, MACH_E = "#23252D", "#363944"
WALL = "#4B4F5A"
OBS, HYP, UNK, CON, SCAN = "#4ADE80", "#FBBF24", "#8B909B", "#F87171", "#60A5FA"
ACC = "#818CF8"


def P(x, y):
    return OX + x * S, OY + (H_M - y) * S


def pts(poly):
    return " ".join(f"{P(x, y)[0]:.1f},{P(x, y)[1]:.1f}" for x, y in poly)


def rect_m(x1, y1, x2, y2, **kw):
    a, b = P(min(x1, x2), max(y1, y2))
    w, h = abs(x2 - x1) * S, abs(y2 - y1) * S
    attrs = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in kw.items())
    return f'<rect x="{a:.1f}" y="{b:.1f}" width="{w:.1f}" height="{h:.1f}" {attrs}/>'


def text(x, y, s, size=11, fill=INK_M, weight=560, anchor="start", ls="0", extra=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
            f'text-anchor="{anchor}" letter-spacing="{ls}" {extra}>{s}</text>')


o = []
o.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{CW}" height="{CH}" viewBox="0 0 {CW} {CH}">')
o.append(f'''<defs>
<pattern id="hatch" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
  <line x1="0" y1="0" x2="0" y2="7" stroke="{UNK}" stroke-opacity="0.38" stroke-width="1.4"/></pattern>
<pattern id="yard" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
  <line x1="0" y1="0" x2="0" y2="10" stroke="#ffffff" stroke-opacity="0.035" stroke-width="1"/></pattern>
<pattern id="zebra" width="5" height="5" patternUnits="userSpaceOnUse">
  <rect width="2.5" height="5" fill="#ffffff" fill-opacity="0.07"/></pattern>
<radialGradient id="glow"><stop offset="0" stop-color="{OBS}" stop-opacity="0.35"/><stop offset="1" stop-color="{OBS}" stop-opacity="0"/></radialGradient>
<marker id="chev" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto">
  <path d="M2,1 L7,5 L2,9" fill="none" stroke="{INK_F}" stroke-width="1.6" stroke-linecap="round"/></marker>
<filter id="soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6"/></filter>
</defs>''')
o.append(f'<style>text{{font-family:Inter,"Google Sans Flex",system-ui,sans-serif;font-feature-settings:"tnum" 1,"ss01" 1}}</style>')
o.append(f'<rect width="{CW}" height="{CH}" fill="{BG}"/>')
o.append(f'<rect x="16" y="16" width="{CW-32}" height="{CH-32}" rx="16" fill="{SURF}" stroke="{HAIR}"/>')

# header
o.append(text(40, 52, "FLOOR PLAN", 11, INK_M, 640, ls="0.12em"))
o.append(text(132, 52, "·  CONTOH EXPRESS HUB, KLANG VALLEY  ·  SYNTHETIC", 11, INK_F, 560, ls="0.08em"))
o.append(text(40, 80, "Where did CTX160258795857 go after its last scan?", 19, INK_S, 640, ls="-0.01em"))
o.append(text(CW - 40, 52, "SAMPLE DATA · STYLE REFERENCE", 10, INK_F, 600, "end", "0.1em"))

# yards (outside)
o.append(rect_m(-4.6, 0, 0, 34, fill="url(#yard)"))
o.append(rect_m(20, 40, 60, 44.6, fill="url(#yard)"))
x, y = P(-2.3, 33.0); o.append(text(x, y, "TRUCK YARD", 9, INK_F, 600, "middle", "0.12em", f'transform="rotate(-90 {x} {y})"'))
x, y = P(51.5, 43.4); o.append(text(x, y, "TRUCK YARD", 9, INK_F, 600, "start", "0.12em"))

# floor slab
o.append(rect_m(0, 0, 60, 40, fill=FLOOR))

# aisles / walkways (very faint) + forklift lane
for w in spec["circulation"]["walkways"]:
    x1, y1, x2, y2 = w["rect_m"]
    o.append(rect_m(x1, y1, x2, y2, fill="#ffffff", fill_opacity="0.018"))
lane = spec["circulation"]["forklift_lane"]
o.append(f'<polyline points="{pts(lane["centreline_m"])}" fill="none" stroke="#ffffff" stroke-opacity="0.025" '
         f'stroke-width="{lane["width_m"]*S:.1f}" stroke-linejoin="round"/>')
o.append(f'<polyline points="{pts(lane["centreline_m"])}" fill="none" stroke="#ffffff" stroke-opacity="0.07" '
         f'stroke-width="1" stroke-dasharray="6 7"/>')
for z in spec["circulation"]["zebra_crossings"]:
    x1, y1, x2, y2 = z["rect_m"]; o.append(rect_m(x1, y1, x2, y2, fill="url(#zebra)"))

# zones: soft panels with human names
NAMES = {"Z01": "Inbound dock", "Z02": "Bag opening", "Z03": "Induction", "Z04": "Scan tunnel",
         "Z05": "Cross-belt sorter", "Z06": "Chutes + bagging", "Z07": "Reject", "Z08": "Exception bench",
         "Z09": "Oversize", "Z10": "Cage staging", "Z11": "Cage + bag store", "Z12": "Outbound dock",
         "Z13": "Office"}
LABEL_AT = {"Z01": (0.8, 29.2), "Z02": (8.6, 28.2), "Z03": (6.2, 6.0), "Z04": (17.9, 7.0), "Z05": (33.0, 15.6),
            "Z06": (30.4, 24.0), "Z07": None, "Z08": (23.4, 24.0), "Z09": (9.0, 4.4), "Z10": (25.6, 31.8),
            "Z11": (15.9, 31.2), "Z12": (24.6, 39.2), "Z13": (55.0, 5.2)}
for z in spec["zones"]:
    if z["id"] == "Z14":
        continue
    poly = z["polygon_m"]
    if z["id"] in ("Z05",):
        continue  # machine footprint drawn by the loop itself
    o.append(f'<polygon points="{pts(poly)}" fill="#ffffff" fill-opacity="0.022" stroke="{HAIR}" stroke-width="1"/>')

# columns
for cx, cy in spec["building"]["columns"]:
    o.append(rect_m(cx - 0.25, cy - 0.25, cx + 0.25, cy + 0.25, fill="#2C2F38"))

# racks + store shelves
for r in spec["fixtures"]["racks"]:
    x1, y1, x2, y2 = r["rect_m"]; o.append(rect_m(x1, y1, x2, y2, fill="#2A2D35", stroke=MACH_E))

# blind spot
bc = spec["blind_corner"]["polygon"]
o.append(f'<polygon points="{pts(bc)}" fill="url(#hatch)" stroke="{UNK}" stroke-opacity="0.5" stroke-dasharray="4 4"/>')
x, y = P(1.0, 37.6)
o.append(text(x, y, "No camera coverage", 11, INK, 600))
o.append(text(x, y + 15, "behind the sack racks", 10, INK_M, 500))

# benches, cage bays
for b in spec["fixtures"]["benches"]:
    x1, y1, x2, y2 = b["rect_m"]; o.append(rect_m(x1, y1, x2, y2, fill=MACH, stroke=MACH_E, rx="2"))
for c in spec["fixtures"]["cage_bays"]:
    x, y = c["sw_corner_m"]; s = c["size_m"]
    o.append(rect_m(x + 0.15, y + 0.15, x + s - 0.15, y + s - 0.15, fill="none", stroke="#ffffff",
                    stroke_opacity="0.08", rx="2"))
# office
o.append(rect_m(54.6, 0.2, 59.8, 6.0, fill="#ffffff", fill_opacity="0.03", stroke=MACH_E))
a = P(54.6, 6.0); b = P(59.8, 6.0)
o.append(f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}" stroke="{INK_F}" stroke-width="2.5"/>')

# conveyors as belts with flow chevrons
def belt(path, width=0.8, fill=MACH):
    d = pts(path)
    o.append(f'<polyline points="{d}" fill="none" stroke="{MACH_E}" stroke-width="{width*S+2:.1f}" stroke-linejoin="round"/>')
    o.append(f'<polyline points="{d}" fill="none" stroke="{fill}" stroke-width="{width*S:.1f}" stroke-linejoin="round"/>')
    # chevrons every 2.2 m
    for (x1, y1), (x2, y2) in zip(path, path[1:]):
        L = math.hypot(x2 - x1, y2 - y1); n = int(L // 2.2)
        for i in range(1, n + 1):
            t = (i * 2.2 - 0.5) / L
            if t >= 1: break
            ax, ay = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
            bx, by = x1 + (x2 - x1) * (t + 0.3 / L), y1 + (y2 - y1) * (t + 0.3 / L)
            pa, pb = P(ax, ay), P(bx, by)
            o.append(f'<line x1="{pa[0]:.1f}" y1="{pa[1]:.1f}" x2="{pb[0]:.1f}" y2="{pb[1]:.1f}" stroke="none" marker-end="url(#chev)"/>')

for cv in spec["machines"]["conveyors"]:
    w = 0.7 if cv["kind"] == "telescopic" else 0.8
    belt(cv["path"], w)

# scan tunnel box
o.append(rect_m(19.5, 8.6, 22.0, 10.4, fill="#2A2D36", stroke="#4A4E59", rx="3"))

# loop sorter: stadium track with carrier ticks
L = spec["machines"]["loop"]
r, wcx, ecx, cy = L["radius"], L["west_cx"], L["east_cx"], L["cy"]
def stadium(rr):
    a = P(wcx, cy - rr); b = P(ecx, cy - rr); c = P(ecx, cy + rr); d = P(wcx, cy + rr)
    R = rr * S
    return (f'M{a[0]:.1f},{a[1]:.1f} L{b[0]:.1f},{b[1]:.1f} A{R:.1f},{R:.1f} 0 0 0 {c[0]:.1f},{c[1]:.1f} '
            f'L{d[0]:.1f},{d[1]:.1f} A{R:.1f},{R:.1f} 0 0 0 {a[0]:.1f},{a[1]:.1f} Z')
o.append(f'<path d="{stadium(r)}" fill="none" stroke="{MACH_E}" stroke-width="{1.0*S+2:.1f}"/>')
o.append(f'<path d="{stadium(r)}" fill="none" stroke="{MACH}" stroke-width="{1.0*S:.1f}"/>')
o.append(f'<path d="{stadium(r)}" fill="none" stroke="#3A3D47" stroke-width="{0.8*S:.1f}" '
         f'stroke-dasharray="1.2 {0.7*S-1.2:.1f}"/>')
# inner island
o.append(f'<path d="{stadium(r-0.5)}" fill="#ffffff" fill-opacity="0.012" stroke="none"/>')
x, y = P((wcx + ecx) / 2, cy + 0.2)
o.append(text(x, y, "Cross-belt sorter", 12, INK_M, 600, "middle"))
o.append(text(x, y + 15, "99 carriers · 2.0 m/s · counter-clockwise", 10, INK_F, 500, "middle"))
# direction arrows on the loop
for (ax, ay, bx, by) in [(36, cy - r, 37.2, cy - r), (42.5, cy + r, 41.3, cy + r)]:
    pa, pb = P(ax, ay), P(bx, by)
    o.append(f'<line x1="{pa[0]:.1f}" y1="{pa[1]:.1f}" x2="{pb[0]:.1f}" y2="{pb[1]:.1f}" stroke="none" marker-end="url(#chev)"/>')

# crossovers (bridges) as outlines
for xo in spec["circulation"]["crossovers"]:
    x0, w = xo["x"], xo["width"]
    y1, y2 = xo["south_stair_y"][0], xo["north_stair_y"][1]
    o.append(rect_m(x0 - w / 2, y1, x0 + w / 2, y2, fill="none", stroke="#ffffff", stroke_opacity="0.16",
                    stroke_dasharray="3 3", rx="2"))

# chutes
for ch in spec["machines"]["chutes"]:
    x0, m, e, w = ch["x"], ch["mouth_y"], ch["end_y"], ch["width"]
    poly = [(x0 - 0.42, m - 0.25), (x0 + 0.42, m - 0.25), (x0 + w / 2 - 0.05, e), (x0 - w / 2 + 0.05, e)]
    o.append(f'<polygon points="{pts(poly)}" fill="#2A2D36" stroke="#474B56" stroke-linejoin="round"/>')
    lab = "R" if ch["id"] == "REJECT" else ch["id"][1:]
    x, y = P(x0, e + 0.75)
    o.append(text(x, y + 3, lab, 9, INK_F, 600, "middle"))

# walls with door openings
doors = spec["building"]["doors"]
def wall_segments(wall, length, coord):
    gaps = sorted((d["centre"][coord] - d["width"] / 2, d["centre"][coord] + d["width"] / 2, d)
                  for d in doors if d["wall"] == wall)
    segs, cur = [], 0.0
    for g0, g1, d in gaps:
        segs.append((cur, g0)); cur = g1
    segs.append((cur, length)); return segs, gaps
WT = 0.32
for wall, fixed, length, coord in [("W", 0.0, 40.0, 1), ("E", 60.0, 40.0, 1), ("S", 0.0, 60.0, 0), ("N", 40.0, 60.0, 0)]:
    segs, gaps = wall_segments(wall, length, coord)
    for s0, s1 in segs:
        if coord == 1:
            a, b = P(fixed, s0), P(fixed, s1)
        else:
            a, b = P(s0, fixed), P(s1, fixed)
        o.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="{WALL}" '
                 f'stroke-width="{WT*S:.1f}" stroke-linecap="square"/>')
    for g0, g1, d in gaps:
        if d["kind"] == "dock":
            if coord == 1:
                a, b = P(fixed, g0), P(fixed, g1); lx, ly = P(fixed - 1.3, d["centre"][1])
            else:
                a, b = P(g0, fixed), P(g1, fixed); lx, ly = P(d["centre"][0], fixed + 1.0)
            o.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="{INK_F}" '
                     f'stroke-width="1.5" stroke-dasharray="2 3"/>')
            o.append(text(lx, ly + 4, d["board"], 10, INK_M, 640, "middle"))
        else:
            # personnel door: small swing arc
            if coord == 1:
                hx, hy = P(fixed, g0)
                o.append(f'<path d="M{hx:.1f},{hy:.1f} a{S:.1f},{S:.1f} 0 0 0 {-S if fixed>0 else S:.1f},{-S:.1f}" '
                         f'fill="none" stroke="{INK_F}" stroke-width="1"/>')
            else:
                hx, hy = P(g0, fixed)
                o.append(f'<path d="M{hx:.1f},{hy:.1f} a{S:.1f},{S:.1f} 0 0 1 {S:.1f},{S:.1f}" '
                         f'fill="none" stroke="{INK_F}" stroke-width="1"/>')

# zone labels (name + faint code)
for z in spec["zones"]:
    at = LABEL_AT.get(z["id"])
    if not at or z["id"] == "Z05":
        continue
    x, y = P(*at)
    o.append(text(x, y, NAMES[z["id"]], 11, INK_M, 600))
    o.append(text(x, y + 13, z["id"], 9, INK_F, 600, ls="0.04em"))

# cameras: dim everywhere, two highlighted with FOV
def cam_icon(c, hi=False, rng=9.0):
    x, y = c["position_m"]; h = math.radians(c["heading_deg"]); half = math.radians(c["hfov_deg"] / 2)
    cx, cy_ = P(x, y)
    if hi:
        p1 = P(x + rng * math.cos(h - half), y + rng * math.sin(h - half))
        p2 = P(x + rng * math.cos(h + half), y + rng * math.sin(h + half))
        R = rng * S
        o.append(f'<path d="M{cx:.1f},{cy_:.1f} L{p1[0]:.1f},{p1[1]:.1f} A{R:.1f},{R:.1f} 0 0 0 {p2[0]:.1f},{p2[1]:.1f} Z" '
                 f'fill="{ACC}" fill-opacity="0.07" stroke="{ACC}" stroke-opacity="0.35" stroke-width="1"/>')
    # body: rounded square rotated to heading, lens tick
    dx, dy = math.cos(h), -math.sin(h)
    col = ACC if hi else INK_F
    o.append(f'<circle cx="{cx:.1f}" cy="{cy_:.1f}" r="{6 if hi else 3.5}" fill="{SURF}" stroke="{col}" stroke-width="1.6"/>')
    o.append(f'<line x1="{cx:.1f}" y1="{cy_:.1f}" x2="{cx+dx*(11 if hi else 6.5):.1f}" y2="{cy_+dy*(11 if hi else 6.5):.1f}" '
             f'stroke="{col}" stroke-width="1.8" stroke-linecap="round"/>')
    if hi:
        o.append(text(cx - dx * 14, cy_ - dy * 14 + 4, c["id"].replace("CAM_", "CAM "), 10, ACC, 640, "middle"))

cams = {c["id"]: c for c in spec["cameras"]}
for c in spec["cameras"]:
    if c["id"] not in ("CAM_07", "CAM_10"):
        cam_icon(c)

# other scan points: tiny faint
for sp in spec["scan_points"]:
    x, y = P(*sp["position_m"][:2])
    o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.6" fill="{SCAN}" fill-opacity="0.35"/>')

# ---------------- SAMPLE journey ----------------
cam_icon(cams["CAM_10"], True, 8.0)
cam_icon(cams["CAM_07"], True, 8.0)

def arc_pts(cx, cy, rr, a0, a1, n=24):
    return [(cx + rr * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + rr * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]

tunnel = (22.2, 9.5); load = (30.0, 11.0); div = (44.1, 19.0)
observed = [tunnel, (23.0, 9.5), (27.6, 9.5), load]
inferred = [load, (ecx, cy - r)] + arc_pts(ecx, cy, r, -90, 90)[1:] + [(44.1, cy + r)]
# observed: solid green with soft glow
o.append(f'<polyline points="{pts(observed)}" fill="none" stroke="{OBS}" stroke-width="10" stroke-opacity="0.18" stroke-linecap="round" stroke-linejoin="round"/>')
o.append(f'<polyline points="{pts(observed)}" fill="none" stroke="{OBS}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
# inferred along belt: amber dotted
o.append(f'<polyline points="{pts(inferred)}" fill="none" stroke="{HYP}" stroke-width="3" stroke-dasharray="0.1 7" stroke-linecap="round" stroke-linejoin="round"/>')
# divert into chute (inferred, short)
o.append(f'<polyline points="{pts([(44.1, cy + r), (44.1, 20.5)])}" fill="none" stroke="{HYP}" stroke-width="3" stroke-dasharray="0.1 7" stroke-linecap="round"/>')

# unknown after: possible area (grey hatched) bag C04 + bagging aisle
poss = [(42.9, 20.6), (45.3, 20.6), (46.4, 24.4), (41.6, 24.4)]
o.append(f'<polygon points="{pts(poss)}" fill="url(#hatch)" stroke="{UNK}" stroke-dasharray="3 3" stroke-opacity="0.7"/>')

# missing moment: expected-here marker on the bag frame (red dashed ring = expected, not seen)
mx, my = P(44.1, 21.4)
o.append(f'<rect x="{mx-11:.1f}" y="{my-9:.1f}" width="22" height="18" rx="4" fill="none" stroke="{CON}" stroke-width="1.6" stroke-dasharray="4 3"/>')

# scan beads
def bead(pt, last=False):
    x, y = P(*pt)
    if last:
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="22" fill="url(#glow)"/>')
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="10" fill="none" stroke="{OBS}" stroke-width="1.5" stroke-opacity="0.8"/>')
    o.append(f'<rect x="{x-5.5:.1f}" y="{y-5.5:.1f}" width="11" height="11" rx="2" transform="rotate(45 {x:.1f} {y:.1f})" '
             f'fill="{SCAN}" stroke="{SURF}" stroke-width="2"/>')
bead(tunnel); bead(load); bead((44.1, cy + r), last=True)

# time chips with leader lines
def chip(anchor, offset, t, sub, col=INK_S, dot=SCAN):
    ax, ay = P(*anchor); bx, by = ax + offset[0], ay + offset[1]
    o.append(f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="{INK_F}" stroke-width="1"/>')
    w = 9 + 7.0 * max(len(t) * 0.92, len(sub) * 0.82) + 18
    o.append(f'<rect x="{bx:.1f}" y="{by-15:.1f}" width="{w:.1f}" height="36" rx="9" fill="{SURF2}" stroke="{HAIR2}"/>')
    o.append(f'<circle cx="{bx+11:.1f}" cy="{by-3:.1f}" r="3.2" fill="{dot}"/>')
    o.append(text(bx + 20, by + 1, t, 11.5, col, 640))
    o.append(text(bx + 11, by + 15, sub, 9.5, INK_M, 520))
chip(tunnel, (-118, -64), "14:32:07", "Label read · tunnel")
chip(load, (-26, 70), "14:32:12", "On carrier 87 · seen")
chip((44.1, cy + r), (64, -76), "14:32:31.8", "Last confirmed · divert C04", dot=OBS)
# missing-moment callout
chip((44.1, 21.4), (96, 34), "14:32:33–35", "Expected on CAM 10 · not seen", dot=CON)

# north arrow + scale bar
nx, ny = OX + W_M * S - 4, OY + H_M * S + 44
o.append(f'<path d="M{nx},{ny-16} L{nx+6},{ny} L{nx},{ny-4} L{nx-6},{ny} Z" fill="{INK_M}"/>')
o.append(text(nx, ny + 14, "N", 9, INK_M, 640, "middle"))
sx, sy = OX, OY + H_M * S + 40
o.append(f'<line x1="{sx}" y1="{sy}" x2="{sx+10*S}" y2="{sy}" stroke="{INK_M}" stroke-width="1.5"/>')
for i in (0, 5, 10):
    o.append(f'<line x1="{sx+i*S}" y1="{sy-4}" x2="{sx+i*S}" y2="{sy+4}" stroke="{INK_M}" stroke-width="1.5"/>')
o.append(text(sx, sy + 18, "0", 9.5, INK_M, 560, "middle"))
o.append(text(sx + 10 * S, sy + 18, "10 m", 9.5, INK_M, 560, "middle"))

# legend
lx, ly = OX + 230, OY + H_M * S + 38
items = [("line", OBS, "Seen on camera"), ("dots", HYP, "Inferred along belt (not seen)"),
         ("bead", SCAN, "Scan"), ("ring", OBS, "Last confirmed"), ("dash", CON, "Expected, not seen"),
         ("hatch", UNK, "Could be here / no coverage"), ("cam", ACC, "Camera in play")]
cx_ = lx
for kind, col, lab in items:
    if kind == "line":
        o.append(f'<line x1="{cx_}" y1="{ly}" x2="{cx_+20}" y2="{ly}" stroke="{col}" stroke-width="3" stroke-linecap="round"/>')
    elif kind == "dots":
        o.append(f'<line x1="{cx_}" y1="{ly}" x2="{cx_+20}" y2="{ly}" stroke="{col}" stroke-width="3" stroke-dasharray="0.1 6" stroke-linecap="round"/>')
    elif kind == "bead":
        o.append(f'<rect x="{cx_+5}" y="{ly-5}" width="10" height="10" rx="2" transform="rotate(45 {cx_+10} {ly})" fill="{col}"/>')
    elif kind == "ring":
        o.append(f'<circle cx="{cx_+10}" cy="{ly}" r="7" fill="none" stroke="{col}" stroke-width="1.5"/>')
    elif kind == "dash":
        o.append(f'<rect x="{cx_+1}" y="{ly-7}" width="18" height="14" rx="3" fill="none" stroke="{col}" stroke-width="1.5" stroke-dasharray="4 3"/>')
    elif kind == "hatch":
        o.append(f'<rect x="{cx_}" y="{ly-7}" width="20" height="14" rx="3" fill="url(#hatch)" stroke="{col}" stroke-opacity="0.6"/>')
    elif kind == "cam":
        o.append(f'<circle cx="{cx_+10}" cy="{ly}" r="5" fill="{SURF}" stroke="{col}" stroke-width="1.6"/>')
    o.append(text(cx_ + 28, ly + 4, lab, 11, INK, 540))
    cx_ += 28 + len(lab) * 6.1 + 26
    if cx_ > CW - 200 and kind != items[-1][0]:
        cx_ = lx; ly += 28
o.append('</svg>')
open(OUT, "w").write("\n".join(o))
print("ok", CW, CH)
