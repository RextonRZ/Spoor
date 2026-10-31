"""Plan view of the S2 perimeter proof (s2_perimeter.py JSON): racks, the entrance gap, cameras, and which sample
points inside Z11 / in the gap are seen by any camera (after the lens crop).

  py -X utf8 assets/hub/mocap/s2_perimeter_plot.py qa/review/s2_perimeter/perimeter.json qa/review/s2_perimeter/plan.png
"""
import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HUB = Path(__file__).resolve().parents[1]
rep = json.loads(Path(sys.argv[1]).read_text())
spec = json.loads((HUB / "hub_spec.json").read_text(encoding="utf-8"))
fig, ax = plt.subplots(figsize=(13, 8), dpi=150)
for r in spec["fixtures"]["racks"]:
    x0, y0, x1, y1 = r["rect_m"]
    ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, color="#5d6d7e"))
ax.add_patch(plt.Rectangle((0, 39.8), 20, 0.2, color="#222"))
ax.add_patch(plt.Rectangle((0, 25), 0.2, 15, color="#222"))
ax.add_patch(plt.Rectangle((13.4, 33.0), 1.8, 0.6, fill=False, ec="red", lw=1.5))
ax.text(14.3, 32.6, "entrance gap", color="red", ha="center", fontsize=8)
ax.text(6.5, 37.0, "BLIND_NW / Z11 (exception store)", ha="center", fontsize=11, color="#333")
seen = un = 0
for f in rep["faces"]:
    if f["face"] not in ("inside_Z11", "gap_mid"):
        continue
    uns = {tuple(p) for p in f["unseen"]}
    xs = [round(0.5 + i * 0.5, 2) for i in range(30)] if f["face"] == "inside_Z11" else \
        [round(13.45 + i * 0.1, 2) for i in range(18)]
    ys = [round(33.9 + j * 0.5, 2) for j in range(12)] if f["face"] == "inside_Z11" else [33.3]
    zs = (0.2, 1.0, 1.7) if f["face"] == "inside_Z11" else [round(0.1 + i * 0.1, 2) for i in range(20)]
    for x in xs:
        for y in ys:
            n = sum((x, y, z) not in uns for z in zs)
            ax.plot(x, y, "o", ms=3.5 if f["face"] == "inside_Z11" else 2.5,
                    color="#e67e22" if n else "#2e86c1", alpha=0.9)
for c in spec["cameras"]:
    x, y = c["position_m"]
    if not (0 <= x <= 32 and 22 <= y <= 40):
        continue
    hd = math.radians(c["heading_deg"])
    col = "red" if c["id"] == "CAM_19" else "#555"
    ax.plot(x, y, "s", color=col, ms=7)
    ax.arrow(x, y, 1.6 * math.cos(hd), 1.6 * math.sin(hd), head_width=0.35, color=col)
    ax.text(x + 0.3, y - 0.7, c["id"], fontsize=8, color=col)
for c in ("CAM_01", "CAM_06"):  # far away: arrows towards them
    cs = next(q for q in spec["cameras"] if q["id"] == c)
    x, y = cs["position_m"]
    dx, dy = x - 14.3, y - 33.3
    L = math.hypot(dx, dy)
    ax.annotate(f"{c} ({L:.0f} m)", xy=(14.3 + dx / L * 6, 33.3 + dy / L * 6), xytext=(14.3 + dx / L * 8.5, 33.3 + dy / L * 8.5),
                fontsize=8, color="#555", arrowprops=dict(arrowstyle="<-", color="#999"))
ax.plot([], [], "o", color="#e67e22", label="seen by >= 1 camera (after the lens crop)")
ax.plot([], [], "o", color="#2e86c1", label="seen by no camera")
ax.legend(loc="lower left", fontsize=8)
ax.set_xlim(-0.5, 31)
ax.set_ylim(24, 40.5)
ax.set_aspect("equal")
ax.set_title("S2 perimeter proof (raycast in the real hub geometry, layout b build, 31 Oct): Z11 inside sample points "
             "(0.5 m grid, z 0.2/1.0/1.7) and the gap's mid plane (z 0.1-2.0)", fontsize=9)
ax.grid(alpha=0.2)
fig.tight_layout()
fig.savefig(sys.argv[2])
print("wrote", sys.argv[2])
