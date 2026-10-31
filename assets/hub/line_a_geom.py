"""Line A option (b) geometry (reviews 015 / 016, M5): one place for build_hub (meshes), flow (belts, diverters) and
stations (the mocap inductors). No bpy here.

Per inductor k (x = stations_x[k], facing -y): a gravity roller table on his left (centre x + table_dx) falling from
the feed line (y 12.25) towards him, its end stop at op_y - 0.13; in front of him an induct belt 1.2 m at 45 deg
into belt A (y 9.5), merging at LA_MERGES[k]. A diverter paddle at each table mouth pushes the parcel off the feed.
"""
import math

LA = {"stations_x": [7.0, 8.6, 10.2, 11.8], "op_y": 11.15, "table_dx": 0.68, "table_w": 0.5, "table_len": 0.73,
      "table_top": (0.95, 0.88), "induct_len": 1.2, "induct_w": 0.5, "belt_a_y": 9.5, "belt_a_half": 0.4,
      "feed_y": 12.25, "feed_x": (5.0, 13.0), "feed_half": 0.4}
_R2 = math.sqrt(0.5)


def derive(spec_line_a=None):
    """(LA, mouths x, induct (start, end) xy pairs, merge x on belt A) for the spec's "line_a" overrides."""
    la = dict(LA)
    la.update(spec_line_a or {})
    mouths = [x + la["table_dx"] for x in la["stations_x"]]
    induct = []  # (start, end) on the floor plan: 0.5 m in front of the worker, 0.15 m to his right, 45 deg into A
    for x in la["stations_x"]:
        s0 = (x - 0.15, la["op_y"] - 0.5)
        y_end = la["belt_a_y"] + la["belt_a_half"] + 0.05  # flush with belt A's frame (the carton crosses onto A)
        ln_ = (s0[1] - y_end) / _R2
        induct.append((s0, (s0[0] + ln_ * _R2, y_end)))
    merges = [e[0] - 0.15 for (_, e) in induct]  # where the carton comes onto belt A
    return la, mouths, induct, merges


def table_ys(la):
    """(stop end y, head y at the feed) of the roller tables."""
    return la["op_y"] - 0.10, la["op_y"] - 0.10 + la["table_len"]
