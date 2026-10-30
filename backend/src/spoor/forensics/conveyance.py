"""Conveyor network from the site plan: where a parcel can physically ride, and how long it takes.

A parcel left on conveyance can only move forward along a belt, from a belt onto the one it feeds, and round the sorter
loop. Between two scans this gives the ONLY physical route and its minimum travel time at the declared belt speeds.
It is an inference (amber dotted in the UI), never an observation."""

import math
from dataclasses import dataclass, field

from spoor.contracts import PlanConveyor, SitePlan

P = tuple[float, float]
SNAP_M = 1.2  # a read point further than this from every centreline is not on conveyance


def _seglen(a: P, b: P) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


@dataclass
class Line:
    """A conveyor centreline with arc-length helpers. Closed lines wrap (sorter loop)."""

    conveyor: PlanConveyor
    pts: list[P]
    cum: list[float] = field(init=False)

    def __post_init__(self) -> None:
        if self.conveyor.closed and self.pts[0] != self.pts[-1]:
            self.pts = [*self.pts, self.pts[0]]
        self.cum = [0.0]
        for a, b in zip(self.pts, self.pts[1:], strict=False):
            self.cum.append(self.cum[-1] + _seglen(a, b))

    @property
    def length(self) -> float:
        return self.cum[-1]

    def point(self, s: float) -> P:
        if self.conveyor.closed:
            s %= self.length
        s = min(max(s, 0.0), self.length)
        for i in range(1, len(self.cum)):
            if s <= self.cum[i] or i == len(self.cum) - 1:
                seg = self.cum[i] - self.cum[i - 1]
                f = 0.0 if seg == 0 else (s - self.cum[i - 1]) / seg
                a, b = self.pts[i - 1], self.pts[i]
                return (a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]))
        return self.pts[-1]

    def height(self, s: float) -> float:
        h = self.conveyor.deck_heights_m
        if len(h) == 1:
            return h[0]
        s = min(max(s % self.length if self.conveyor.closed else s, 0.0), self.length)
        for i in range(1, len(self.cum)):
            if s <= self.cum[i]:
                seg = self.cum[i] - self.cum[i - 1]
                f = 0.0 if seg == 0 else (s - self.cum[i - 1]) / seg
                return h[i - 1] + f * (h[i] - h[i - 1]) if i < len(h) else h[-1]
        return h[-1]

    def project(self, p: P) -> tuple[float, float]:
        """(arc length, distance) of the nearest centreline point."""
        best = (0.0, math.inf)
        for i in range(1, len(self.pts)):
            a, b = self.pts[i - 1], self.pts[i]
            dx, dy = b[0] - a[0], b[1] - a[1]
            seg2 = dx * dx + dy * dy
            f = 0.0 if seg2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / seg2))
            q = (a[0] + f * dx, a[1] + f * dy)
            d = _seglen(p, q)
            if d < best[1]:
                best = (self.cum[i - 1] + f * math.sqrt(seg2), d)
        return best

    def forward(self, s0: float, s1: float) -> float | None:
        """Distance travelled from s0 to s1 in the direction of travel; None if impossible (open belt backwards)."""
        if self.conveyor.closed:
            return (s1 - s0) % self.length
        return s1 - s0 if s1 >= s0 - 0.05 else None

    def slice(self, s0: float, s1: float, step: float = 0.5) -> list[P]:
        """Polyline from s0 forward to s1 (wrapping on a closed line), keeping corners."""
        d = self.forward(s0, s1)
        if d is None:
            return []
        n = max(1, math.ceil(d / step))
        offsets = {d * k / n for k in range(n + 1)}
        # keep exact corners so the drawn ribbon hugs the belt
        for c in self.cum[1:-1]:
            off = (c - s0) % self.length if self.conveyor.closed else c - s0
            if 0 < off < d:
                offsets.add(off)
        return _dedupe([self.point(s0 + off) for off in sorted(offsets)])


def _dedupe(pts: list[P]) -> list[P]:
    out: list[P] = []
    for p in pts:
        if not out or _seglen(out[-1], p) > 1e-6:
            out.append((round(p[0], 3), round(p[1], 3)))
    return out


@dataclass
class Piece:
    conveyor_id: str
    s0: float
    s1: float
    length_m: float
    speed_mps: float | None
    path_m: list[P]


@dataclass
class Route:
    pieces: list[Piece]

    @property
    def length_m(self) -> float:
        return sum(p.length_m for p in self.pieces)

    @property
    def min_time_s(self) -> float:
        """Travel time on pieces with a declared belt speed (pieces without one add no time: a lower bound)."""
        return sum(p.length_m / p.speed_mps for p in self.pieces if p.speed_mps)

    @property
    def unknown_speed_m(self) -> float:
        return sum(p.length_m for p in self.pieces if not p.speed_mps)

    @property
    def path_m(self) -> list[P]:
        out: list[P] = []
        for p in self.pieces:
            out.extend(p.path_m if not out else p.path_m[1:] if out[-1] == p.path_m[0] else p.path_m)
        return _dedupe(out)


class ConveyorNet:
    def __init__(self, plan: SitePlan):
        self.plan = plan
        self.lines = {c.conveyor_id: Line(c, list(c.path_m)) for c in plan.conveyors}

    def snap(self, p: P, max_dist: float = SNAP_M) -> tuple[str, float, float] | None:
        """(conveyor_id, arc length, distance) of the nearest conveyor centreline within max_dist."""
        best = None
        for cid, line in self.lines.items():
            s, d = line.project(p)
            if d <= max_dist and (best is None or d < best[2]):
                best = (cid, s, d)
        return best

    def _handover(self, a: Line, b: Line) -> tuple[float, float]:
        """(exit arc length on a, entry arc length on b) where a discharges onto b."""
        if a.conveyor.closed:
            return a.project(b.pts[0])[0], 0.0
        return a.length, b.project(a.pts[-1])[0]

    def route(self, start: tuple[str, float], end: tuple[str, float], max_hops: int = 8) -> Route | None:
        """Shortest forward route along the network from start to end, or None when no physical route exists."""
        best: Route | None = None

        def walk(cid: str, s_in: float, pieces: list[Piece], seen: frozenset[str]) -> None:
            nonlocal best
            line = self.lines[cid]
            if cid == end[0]:
                d = line.forward(s_in, end[1])
                if d is not None:
                    cand = Route([*pieces, Piece(cid, s_in, end[1], d, line.conveyor.speed_mps,
                                                 line.slice(s_in, end[1]))])  # fmt: skip
                    if best is None or cand.length_m < best.length_m:
                        best = cand
            if len(pieces) >= max_hops:
                return
            for nxt in line.conveyor.feeds:
                if nxt in seen:
                    continue
                nline = self.lines[nxt]
                out_s, in_s = self._handover(line, nline)
                d = line.forward(s_in, out_s)
                if d is None:
                    continue
                piece = Piece(cid, s_in, out_s, d, line.conveyor.speed_mps, line.slice(s_in, out_s))
                walk(nxt, in_s, [*pieces, piece], seen | {nxt})

        walk(start[0], start[1], [], frozenset({start[0]}))
        return best

    def downstream(self, start: tuple[str, float], seconds: float, *, step_s: float = 0.5) -> list[list[P]]:
        """Every conveyor stretch reachable from `start` within `seconds` at belt speed (for the 'could be' cloud).
        Belts without a declared speed are not extended (unknown speed = no bound we can state)."""
        out: list[list[P]] = []

        def walk(cid: str, s_in: float, budget: float, seen: frozenset[str]) -> None:
            line = self.lines[cid]
            v = line.conveyor.speed_mps
            if not v or budget <= 0:
                return
            reach = budget * v
            if line.conveyor.closed:
                d_end = min(reach, line.length)
            else:
                d_end = min(reach, line.length - s_in)
            out.append(line.slice(s_in, s_in + d_end, step=max(0.3, v * step_s)))
            for nxt in line.conveyor.feeds:
                if nxt in seen:
                    continue
                out_s, in_s = self._handover(line, self.lines[nxt])
                d = line.forward(s_in, out_s)
                if d is not None and d <= reach:
                    walk(nxt, in_s, budget - d / v, seen | {nxt})

        walk(start[0], start[1], seconds, frozenset({start[0]}))
        return [p for p in out if len(p) >= 2]

    def downstream_timed(self, start: tuple[str, float], seconds: float, step_m: float = 0.25
                         ) -> list[tuple[float, P, str]]:  # fmt: skip
        """(seconds after start, floor point, conveyor_id) samples along every forward branch within `seconds`.
        Stops at belts without a declared speed (a chute: the parcel leaves timed conveyance there)."""
        out: list[tuple[float, P, str]] = []

        def walk(cid: str, s_in: float, t_in: float, seen: frozenset[str]) -> None:
            line = self.lines[cid]
            v = line.conveyor.speed_mps
            if not v or t_in > seconds:
                return
            span = line.length if line.conveyor.closed else line.length - s_in
            d = 0.0
            while d <= span and t_in + d / v <= seconds:
                out.append((t_in + d / v, line.point(s_in + d), cid))
                d += step_m
            for nxt in line.conveyor.feeds:
                if nxt in seen:
                    continue
                out_s, in_s = self._handover(line, self.lines[nxt])
                dd = line.forward(s_in, out_s)
                if dd is not None:
                    walk(nxt, in_s, t_in + dd / v, seen | {nxt})

        walk(start[0], start[1], 0.0, frozenset({start[0]}))
        return sorted(out)
