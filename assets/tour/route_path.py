"""The carton's way between two steps of the route, from the hub's layout only (its machines and walkways, as the hub
spec draws them), never from the simulation's own track. Used by tour_render.py so the fly-through's carton goes the
way a parcel goes (Rexton 4 Nov: "not fly, follow the logic path"):

  - on the belts while both steps are on them: boom, collector, induction, tunnel, merge, the sort loop (counter-
    clockwise from above, as it runs) and down a chute. Where one belt hands over to the next the layout leaves a gap
    (an inductor lifts parcels from the collector's end onto the induction belt): the shortest hop across it;
  - carried along the walkways otherwise (FloorPlan.walkRoute's rule: walkways that touch are joined);
  - a step that is only a record (the truck manifest) does not move the carton: it stays where it was last seen.

  python assets/tour/route_path.py frontend/src/data/hub.generated.json assets/tour/reel.json   (prints each leg)
"""
import heapq
import json
import math
import sys

HOP = 3.0      # a belt's end hands over to another belt this close (the inductors' reach)
ON = 1.2       # a step this close to a belt is on it


def _loop(L):
    """The sort loop as one closed polyline, counter-clockwise from above: the south straight runs east."""
    r, cy, w, e = L["radius"], L["cy"], L["west_cx"], L["east_cx"]
    pts = [(w, L["south_y"]), (e, L["south_y"])]
    pts += [(e + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in range(-80, 90, 10)]
    pts += [(e, L["north_y"]), (w, L["north_y"])]
    pts += [(w + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in range(100, 270, 10)]
    return pts + [pts[0]]


def _proj(line, p):
    """(distance, segment index, t, point) of p's nearest point on a polyline"""
    best = None
    for i in range(len(line) - 1):
        (ax, ay), (bx, by) = line[i], line[i + 1]
        dx, dy = bx - ax, by - ay
        ll = dx * dx + dy * dy
        t = 0.0 if ll == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / ll))
        q = (ax + dx * t, ay + dy * t)
        d = math.dist(p, q)
        if best is None or d < best[0]:
            best = (d, i, t, q)
    return best


class Belts:
    def __init__(self, hub):
        m = hub["machines"]
        self.lines = [[tuple(p) for p in c["path"]] for c in m["conveyors"]]
        self.lines.append(_loop(m["loop"]))
        self.lines += [[(c["x"], c["mouth_y"]), (c["x"], c["end_y"])] for c in m["chutes"]]

    def near(self, p):
        return min(_proj(line, p)[0] for line in self.lines)

    def route(self, a, b):
        """The belt route from a to b in the direction the belts run, or None."""
        lines = [list(line) for line in self.lines]
        adds = [[] for _ in lines]          # (segment, t, point) to insert into each line
        hops = []                           # (from point, to point)

        def put(li, p):
            d, i, t, q = _proj(lines[li], p)
            adds[li].append((i, t, q))
            return q
        for li, line in enumerate(self.lines):
            for lj, other in enumerate(self.lines):
                if li == lj:
                    continue
                d, _, _, _ = _proj(other, line[-1])
                if d <= HOP:                                 # this belt's end hands over onto the other
                    hops.append((line[-1], put(lj, line[-1])))
                d, _, _, _ = _proj(other, line[0])
                if d <= ON:                                  # this belt starts off the other (a chute off the loop)
                    hops.append((put(lj, line[0]), line[0]))
        ia = min(range(len(lines)), key=lambda k: _proj(lines[k], a)[0])
        ib = min(range(len(lines)), key=lambda k: _proj(lines[k], b)[0])
        qa, qb = put(ia, a), put(ib, b)
        key = lambda p: (round(p[0], 3), round(p[1], 3))
        edges = {}
        for li, line in enumerate(lines):
            pts = list(line)
            for i, t, q in sorted(adds[li], key=lambda x: (x[0], x[1]), reverse=True):
                pts.insert(i + 1, q)
            for u, v in zip(pts, pts[1:]):
                if key(u) != key(v):
                    edges.setdefault(key(u), []).append((key(v), math.dist(u, v)))
        for u, v in hops:
            edges.setdefault(key(u), []).append((key(v), math.dist(u, v) + 1.0))
        best, prev, todo = {key(qa): 0.0}, {}, [(0.0, key(qa))]
        while todo:
            d, u = heapq.heappop(todo)
            if u == key(qb):
                break
            if d > best.get(u, 1e9):
                continue
            for v, w in edges.get(u, []):
                if d + w < best.get(v, 1e9):
                    best[v], prev[v] = d + w, u
                    heapq.heappush(todo, (d + w, v))
        if key(qb) not in best:
            return None
        out, u = [key(qb)], key(qb)
        while u != key(qa):
            u = prev[u]
            out.append(u)
        return [tuple(a)] + out[::-1] + [tuple(b)]


def walk(hub, a, b):
    """FloorPlan.walkRoute in Python: along the walkways (those that touch are joined) to the target."""
    ws = [w["rect_m"] for w in hub["walkways"]]
    gap = lambda r, p: math.hypot(max(r[0] - p[0], 0, p[0] - r[2]), max(r[1] - p[1], 0, p[1] - r[3]))

    def around(p):
        d = [gap(r, p) for r in ws]
        m = min(d)
        return [i for i in range(len(ws)) if d[i] <= m + 4]
    touch = lambda r, s: r[0] <= s[2] + 0.3 and s[0] <= r[2] + 0.3 and r[1] <= s[3] + 0.3 and s[1] <= r[3] + 0.3
    starts, ends = around(a), set(around(b))
    prev, q, t = {i: -1 for i in starts}, list(starts), -1
    while q:
        c = q.pop(0)
        if c in ends:
            t = c
            break
        for i, r in enumerate(ws):
            if i not in prev and touch(ws[c], r):
                prev[i] = c
                q.append(i)
    if t < 0:
        return [tuple(a), tuple(b)]
    chain, c = [], t
    while c != -1:
        chain.insert(0, c)
        c = prev[c]
    clamp = lambda r, p: (min(max(p[0], r[0]), r[2]), min(max(p[1], r[1]), r[3]))
    out = [tuple(a), clamp(ws[chain[0]], a)]
    for i in range(1, len(chain)):
        r, s = ws[chain[i - 1]], ws[chain[i]]
        j = ((max(r[0], s[0]) + min(r[2], s[2])) / 2, (max(r[1], s[1]) + min(r[3], s[3])) / 2)
        last = out[-1]
        out += [(j[0], last[1]) if r[2] - r[0] > r[3] - r[1] else (last[0], j[1]), j]
    out += [clamp(ws[chain[-1]], b), tuple(b)]
    return [p for i, p in enumerate(out) if i == 0 or math.dist(p, out[i - 1]) > 0.2]


def legs(hub, steps):
    """For each pair of consecutive steps at different places: (from index, to index, kind, polyline)."""
    belts = Belts(hub)
    pts, out, held = [], [], 0
    for c in steps:
        xy = c.get("xy") or (pts[-1] if pts else [0, 0])
        pts.append((float(xy[0]), float(xy[1])))
    for i in range(1, len(steps)):
        a, b = pts[held], pts[i]
        if steps[i].get("tone") == "record":
            out.append((i - 1, i, "held", [a]))     # the carton stays; only the camera goes to look at the record
            continue
        held = i
        if math.dist(pts[i - 1], b) < 0.5:
            continue
        path = belts.route(a, b) if belts.near(a) <= ON and belts.near(b) <= ON else None
        out.append((i - 1, i, "belt", path) if path else (i - 1, i, "walk", walk(hub, a, b)))
    return out


def length(path):
    return sum(math.dist(u, v) for u, v in zip(path, path[1:]))


def at(path, s):
    """The point s metres along a polyline (clamped to its ends)."""
    if len(path) == 1:
        return path[0]
    for u, v in zip(path, path[1:]):
        d = math.dist(u, v)
        if s <= d or v == path[-1]:
            t = 0 if d == 0 else max(0.0, min(1.0, s / d))
            return (u[0] + (v[0] - u[0]) * t, u[1] + (v[1] - u[1]) * t)
        s -= d
    return path[-1]


if __name__ == "__main__":
    hub = json.loads(open(sys.argv[1], encoding="utf-8").read())
    steps = [c for c in json.loads(open(sys.argv[2], encoding="utf-8").read())["chapters"] if c.get("tone") != "card"]
    for i, j, kind, path in legs(hub, steps):
        print(f"{i + 1}->{j + 1} {kind:5s} {length(path):5.1f} m  " + " ".join(f"({x:.1f},{y:.1f})" for x, y in path))
