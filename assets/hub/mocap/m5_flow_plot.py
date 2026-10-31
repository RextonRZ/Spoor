"""M5 step 2 QA: plan-view snapshots of line A (b) from a flow --sim-only trace, plus each inductor's timeline.

  py -X utf8 assets/hub/mocap/m5_flow_plot.py qa/review/m5_flow/sim_seed7.json   -> sim_seed7.png beside it
"""
import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Polygon, Rectangle  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import line_a_geom  # noqa: E402

src = Path(sys.argv[1])
d = json.loads(src.read_text(encoding="utf-8"))
LA, MOUTHS, INDUCT, MERGES = line_a_geom.derive({"layout": "b"})
y0t, y1t = line_a_geom.table_ys(LA)
SNAP = [0.0, 6.0, 12.0, 18.0, 24.0, 29.0]
COL = {"b": "#a0703c", "m": "#7a7f8a"}


def plan(ax, row, title):
    fy, fh = LA["feed_y"], LA["feed_half"]
    ax.add_patch(Rectangle((5.0 - fh, fy - fh), MOUTHS[-1] + 0.3 - 5.0 + fh, 2 * fh, color="#e4e4e4"))  # feed
    ax.add_patch(Rectangle((5.0 - fh, fy), 2 * fh, 14.0 - fy, color="#e4e4e4"))  # collector
    ax.add_patch(Rectangle((5.0 - 0.3, 10.6), 0.6, fy - fh - 10.6, color="#ececec"))  # d02 stub
    ax.add_patch(Rectangle((5.6, LA["belt_a_y"] - LA["belt_a_half"]), 9.0, 2 * LA["belt_a_half"], color="#e4e4e4"))
    for mx in MOUTHS:
        ax.add_patch(Rectangle((mx - LA["table_w"] / 2, y0t), LA["table_w"], y1t - y0t, color="#d3dbe6"))
    for (sx, sy), (ex, ey) in INDUCT:
        w = LA["induct_w"] / 2 / math.cos(math.pi / 4)  # cut parallel to belt A: half width along x
        ax.add_patch(Polygon([(sx - w, sy), (sx + w, sy), (ex + w, ey), (ex - w, ey)], color="#e6dccb"))
    for k, x in enumerate(LA["stations_x"]):
        held = k in row.get("held", [])
        ax.add_patch(plt.Circle((x, LA["op_y"]), 0.22, fc="#f28c28" if held else "white", ec="#f28c28", lw=1.5))
        ax.text(x, LA["op_y"], f"I{k + 1}", ha="center", va="center", fontsize=7)
    for x, y, yaw, w, dd, kind in row.get("pos", []):
        c, s = math.cos(yaw), math.sin(yaw)
        pts = [(x + c * u - s * v, y + s * u + c * v) for u, v in ((-w / 2, -dd / 2), (w / 2, -dd / 2),
                                                                   (w / 2, dd / 2), (-w / 2, dd / 2))]
        ax.add_patch(Polygon(pts, fc=COL.get(kind, "k"), ec="black", lw=0.4))
    ax.set_xlim(4.4, 14.6)
    ax.set_ylim(8.9, 13.6)
    ax.set_aspect("equal")
    ax.set_title(title, fontsize=9)
    ax.tick_params(labelsize=6)


tr = {round(r["t"], 1): r for r in d["trace"]}
fig = plt.figure(figsize=(16, 12))
for i, ts in enumerate(SNAP):
    row = min(tr.values(), key=lambda r: abs(r["t"] - ts))
    ax = fig.add_subplot(4, 2, i + 1)
    plan(ax, row, f"t = {row['t']:.1f} s   feed {row['feed']}  tables {row['tables']}  induct {row['induct']}"
                  f"  (orange worker = carton in the hands)")
ax = fig.add_subplot(4, 1, 4)
for k, (name, st) in enumerate(sorted(d["line_a"]["stations"].items())):
    for r_, g_, rd in zip(st["release_s"], st["grasp_s"], st["ready_s"]):
        ax.plot([rd, g_], [k, k], color="#bbbbbb", lw=6, solid_capstyle="butt")  # parcel at the stop, not taken
        ax.plot([g_, r_], [k, k], color="#f28c28", lw=6, solid_capstyle="butt")  # in the hands
    ax.text(30.3, k, f"{st['cycles']} cycles  {st['kinds'].count('mailer')} mailers", va="center", fontsize=8)
ax.set_yticks(range(4))
ax.set_yticklabels(sorted(d["line_a"]["stations"]))
ax.set_xlim(-1, 36)
ax.set_xlabel("window time (s): grey = parcel waiting at the table stop, orange = grasp .. release", fontsize=8)
fig.suptitle(f"line A (b) flow simulation, seed {d['seed']}: tunnel reads {d['tunnel_reads_in_window']} / 30 s, "
             f"feed queue max {d['feed_queue_max']}, collector max {d['collector_max']}, conflicts "
             f"{len(d['line_a']['conflicts'])}  (brown = box, grey = mailer)", fontsize=11)
fig.tight_layout()
out = src.with_suffix(".png")
fig.savefig(out, dpi=90)
print("wrote", out)
