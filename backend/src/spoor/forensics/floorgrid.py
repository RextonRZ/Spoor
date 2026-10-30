"""Floor model for reachability (QUEUE I3/I4): a walkability grid rasterized from the site plan.

Walkable = inside the building outline and not inside a rack, bench or conveyor deck; walkways (incl. belt
crossovers) are walkable even where they pass over a belt. Distances are geodesic (around obstacles, 8-neighbour).
A camera footprint is the floor area its mounting-plan view covers, clipped to the building, minus areas the plan marks
as blind (racks block those views). Footprints ignore other occlusion: they are approximate and labelled so."""

import math
from functools import lru_cache

import cv2
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

from spoor.contracts import SitePlan

RES_M = 0.25
BELT_DECK_M = 0.9  # conveyor deck width blocked for walking (belts and the loop are ~0.8-1.0 m wide)
P = tuple[float, float]


class FloorGrid:
    def __init__(self, plan: SitePlan, res: float = RES_M):
        self.plan, self.res = plan, res
        xs = [p[0] for p in plan.outline_m]
        ys = [p[1] for p in plan.outline_m]
        self.x0, self.y0 = min(xs), min(ys)
        self.nx = math.ceil((max(xs) - self.x0) / res) + 1
        self.ny = math.ceil((max(ys) - self.y0) / res) + 1
        self.inside = self.polygon_mask(plan.outline_m)
        blocked = np.zeros_like(self.inside)
        for a in plan.areas:
            if not a.walkable and a.kind in ("rack", "bench"):
                blocked |= self.polygon_mask(a.polygon_m)
        for c in plan.conveyors:
            blocked |= self.polyline_mask(c.path_m, BELT_DECK_M, closed=c.closed)
        override = np.zeros_like(self.inside)
        for a in plan.areas:
            if a.kind == "walkway":
                override |= self.polygon_mask(a.polygon_m)
        self.walkable = self.inside & (~blocked | override)
        self.blind = np.zeros_like(self.inside)
        for a in plan.areas:
            if a.kind == "blind_spot":
                self.blind |= self.polygon_mask(a.polygon_m)
        self._graph = None

    # --- rasterizing ------------------------------------------------------------------------------------------------

    def _px(self, pts) -> np.ndarray:
        return np.array([[(x - self.x0) / self.res, (y - self.y0) / self.res] for x, y in pts], dtype=np.float32)

    def polygon_mask(self, poly) -> np.ndarray:
        m = np.zeros((self.ny, self.nx), np.uint8)
        cv2.fillPoly(m, [np.round(self._px(poly)).astype(np.int32)], 1)
        return m.astype(bool)

    def polyline_mask(self, pts, width_m: float, closed: bool = False) -> np.ndarray:
        m = np.zeros((self.ny, self.nx), np.uint8)
        cv2.polylines(m, [np.round(self._px(pts)).astype(np.int32)], closed, 1,
                      thickness=max(1, round(width_m / self.res)))  # fmt: skip
        return m.astype(bool)

    def cell(self, xy: P) -> tuple[int, int]:
        return (min(self.ny - 1, max(0, round((xy[1] - self.y0) / self.res))),
                min(self.nx - 1, max(0, round((xy[0] - self.x0) / self.res))))  # fmt: skip

    def xy(self, r: int, c: int) -> P:
        return (round(self.x0 + c * self.res, 3), round(self.y0 + r * self.res, 3))

    # --- reachability -----------------------------------------------------------------------------------------------

    def _edges(self, passable: np.ndarray):
        idx = np.full(passable.shape, -1, np.int64)
        idx[passable] = np.arange(int(passable.sum()))
        rows, cols, w = [], [], []
        for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):  # dr >= 0 always
            r0, r1 = 0, self.ny - dr
            c0, c1 = max(0, -dc), self.nx - max(0, dc)
            src = (slice(r0, r1), slice(c0, c1))
            dst = (slice(r0 + dr, r1 + dr), slice(c0 + dc, c1 + dc))
            both = passable[src] & passable[dst]
            ia, ib = idx[src][both], idx[dst][both]
            rows += [ia, ib]
            cols += [ib, ia]
            w += [np.full(ia.size, self.res * math.hypot(dr, dc))] * 2
        n = int(passable.sum())
        g = coo_matrix((np.concatenate(w), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tocsr()
        return g, idx

    def seeds(self, xy: P, passable: np.ndarray, reach_m: float = 1.5) -> list[tuple[int, int]]:
        """Walkable cells next to a point: a parcel on a belt deck is reached from the aisle beside it."""
        r, c = self.cell(xy)
        if passable[r, c]:
            return [(r, c)]
        k = math.ceil(reach_m / self.res)
        out = [(rr, cc) for rr in range(max(0, r - k), min(self.ny, r + k + 1))
               for cc in range(max(0, c - k), min(self.nx, c + k + 1))
               if passable[rr, cc] and math.hypot(rr - r, cc - c) * self.res <= reach_m]  # fmt: skip
        return out

    def distance_from(self, xy: P, blocked_extra: np.ndarray | None = None) -> np.ndarray:
        """Geodesic walking distance (m) from `xy` to every cell; inf where unreachable. `blocked_extra` removes
        cells the subject cannot have crossed (e.g. floor watched by an analysed camera that did not see it)."""
        passable = self.walkable & ~blocked_extra if blocked_extra is not None else self.walkable
        g, idx = self._edges(passable)
        src = [int(idx[r, c]) for r, c in self.seeds(xy, passable)]
        out = np.full(passable.shape, np.inf)
        if not src:
            return out
        d = dijkstra(g, directed=False, indices=src, min_only=True)
        out[passable] = d
        return out

    def contours(self, mask: np.ndarray, simplify_m: float = 0.2) -> list[list[P]]:
        """Outer boundaries of a cell mask as floor polygons (metres), simplified."""
        cs, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        out = []
        for c in cs:
            c = cv2.approxPolyDP(c, simplify_m / self.res, True)
            if len(c) >= 3:
                out.append([self.xy(int(p[0][1]), int(p[0][0])) for p in c])
        return out

    def area_m2(self, mask: np.ndarray) -> float:
        return float(mask.sum()) * self.res * self.res


@lru_cache(maxsize=8)
def _grid_cached(plan_json: str) -> FloorGrid:
    return FloorGrid(SitePlan.model_validate_json(plan_json))


def grid_for(plan: SitePlan) -> FloorGrid:
    return _grid_cached(plan.model_dump_json())


def footprint_mask(grid: FloorGrid, polygon: list[P] | None) -> np.ndarray:
    """Camera floor footprint inside the building, minus plan-declared blind areas (approximate: no occlusion)."""
    if not polygon or len(polygon) < 3:
        return np.zeros_like(grid.inside)
    return grid.polygon_mask(polygon) & grid.inside & ~grid.blind
