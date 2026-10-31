"""Where it could be (QUEUE I4 / H4 / H12): the floor area the subject can have reached since the last confirmed point,
minus every area a camera watched without seeing it. Computed, never observed.

- Reach on foot: geodesic walking distance on the plan's walkability grid at the brisk walking speed (racks, benches and
  belt decks block; walkways and crossovers do not) — a person could have carried it.
- Reach on conveyance: while the subject is still on a belt (not after a divert), every belt stretch it can have ridden
  at belt speed.
- Negative evidence: a camera whose clip was ANALYSED for this case, covered the window, and did not confirm the subject
  removes its floor footprint — the subject cannot be there, nor have passed through it unseen. A clip with unresolved
  candidate tracks removes nothing (identity open). Unanalysed footage removes nothing; the response says so.
Output: polygons per time step (or at `t`) and the places ranked by how much of them is still possible, each with its
evidence for and against."""

from datetime import datetime

import numpy as np

from spoor.contracts import Case, ObjectInstance, RawObservation, SitePlan, point_in_polygon
from spoor.store import EvidenceStore, epoch_ms

from .conveyance import ConveyorNet
from .floorgrid import BELT_DECK_M, FloorGrid, grid_for
from .journey import build_journey, iso, latest_plan
from .missing import LEAVES_BELT, CameraContext, _confirmed_after, analysed, camera_contexts
from .search import outcomes_by_area

STEPS_S = (2, 5, 10, 20, 40, 60, 120, 300)
PLACE_KINDS = ("zone", "store", "blind_spot", "machine")
LABEL = "possible area, computed from the site plan and the cameras that watched; not an observation"


def possible_locations(store: EvidenceStore, case_id: str, *, t: datetime | None = None) -> dict:
    case = store.get(Case, case_id)
    plan = latest_plan(store, case.site_id)
    journey = build_journey(store, case_id, plan=plan)
    out = []
    for obj, oj in zip(store.find(ObjectInstance, case_id=case_id), journey["objects"], strict=True):
        out.append(_for_object(store, case, obj, oj, plan, t))
    return {"case_id": case_id, "plan_id": plan.plan_id if plan else None, "label": LABEL, "objects": out}


def _horizon_ms(store: EvidenceStore, case: Case, ctx: dict[str, CameraContext], t0: float) -> float:
    ends = [epoch_ms(c.end_utc) for cc in ctx.values() for c in cc.coverage]
    if case.window:
        ends.append(case.window.end_utc.timestamp() * 1000)
    return max([t0 + 1000, *ends])


def _for_object(store, case, obj, oj, plan: SitePlan | None, t: datetime | None) -> dict:
    last = oj["last_confirmed"]
    base = {"object_instance_id": obj.object_instance_id, "label": obj.label}
    if plan is None or not last or not last.get("xy"):
        return {**base, "steps": [], "places": [], "note": "no confirmed point with a floor position to start from"}
    grid = grid_for(plan)
    ctx = camera_contexts(store, case.site_id, plan, grid)
    t0 = datetime.fromisoformat(last["t"]).timestamp() * 1000
    horizon = _horizon_ms(store, case, ctx, t0)
    seen_after = _confirmed_after(store, obj.object_instance_id, t0)
    times = [t.timestamp() * 1000] if t else [t0 + s * 1000 for s in STEPS_S if t0 + s * 1000 < horizon] + [horizon]
    xy = tuple(last["xy"])
    net = ConveyorNet(plan)
    on_belt = last.get("on_conveyor") and last.get("event_kind") not in LEAVES_BELT
    snap = net.snap(xy) if on_belt else None

    steps, cache = [], {}
    final_mask = None
    for tm in times:
        dt = max(0.0, (tm - t0) / 1000)
        watched, negatives, open_ids = _negative(store, ctx, t0, tm, seen_after)
        key = tuple(sorted(negatives))
        if key not in cache:
            cache[key] = grid.distance_from(xy, blocked_extra=watched if watched.any() else None)
        dist = cache[key]
        foot = np.isfinite(dist) & (dist <= plan.walk_speed_max_mps * dt)
        belt = np.zeros_like(foot)
        if snap:
            for line in net.downstream(snap[:2], dt):
                belt |= grid.polyline_mask(line, BELT_DECK_M)
        mask = (foot | belt) & ~watched & grid.inside
        final_mask = mask
        steps.append({"t": iso(tm), "seconds_after": round(dt, 1), "area_m2": round(grid.area_m2(mask), 1),
                      "polygons": grid.contours(mask), "removed_by_cameras": sorted(negatives),
                      "identity_open_on": sorted(open_ids)})  # fmt: skip
    rp = plan.read_point(last.get("station_id")) if last["kind"] == "scan" else None
    places = _rank(plan, grid, final_mask, cache[tuple(sorted(steps[-1]["removed_by_cameras"]))], ctx, steps[-1],
                   last_xy=xy, last_zone=rp.zone_id if rp else None)
    # floor search outcomes (I7): "not here" is negative evidence a person gave; "found" puts the place first
    outcomes = outcomes_by_area(store, case.case_id)
    if outcomes and steps:
        for aid, o in outcomes.items():
            area = next((a for a in plan.areas if a.area_id == aid), None)
            if o.outcome == "not_found" and area is not None:
                final_mask = final_mask & ~grid.polygon_mask(area.polygon_m)
        steps[-1] = {**steps[-1], "area_m2": round(grid.area_m2(final_mask), 1), "polygons": grid.contours(final_mask),
                     "searched_not_here": sorted(a for a, o in outcomes.items() if o.outcome == "not_found")}  # fmt: skip
        for pl in places:
            o = outcomes.get(pl["area_id"])
            if o is None:
                continue
            when = o.recorded_at.isoformat(timespec="seconds")
            if o.outcome == "not_found":
                pl["possible_share"] = 0.0
                pl["evidence_against"].insert(0, f"searched by {o.recorded_by} at {when}: not there")
            else:
                pl["found"] = True
                pl["evidence_for"].insert(0, f"found here by {o.recorded_by} at {when}")
        places.sort(key=lambda pl: (not pl.get("found"), pl["possible_share"] == 0))
    analysed_any = any(steps[-1]["removed_by_cameras"]) or any(steps[-1]["identity_open_on"])
    return {**base, "from": {"t": last["t"], "xy": last["xy"], "kind": last["kind"], "evidence_id": last["evidence_id"]},
            "walk_speed_max_mps": plan.walk_speed_max_mps, "steps": steps, "places": places,
            "note": None if analysed_any else "no footage has been analysed, so no camera can remove area yet "
                                              "(negative evidence needs SAM tracking)"}  # fmt: skip


def _negative(store, ctx: dict[str, CameraContext], t0: float, t1: float, seen_after: dict) -> tuple:
    """Union of footprints of cameras that watched [t0, t1] on analysed footage without confirming the subject."""
    watched = None
    negatives, open_ids = [], []
    for cid, c in ctx.items():
        covs = [x for x in c.coverage if epoch_ms(x.start_utc) <= t0 and epoch_ms(x.end_utc) >= min(t1, epoch_ms(x.end_utc))]
        if not covs or cid in seen_after or not c.footprint.any():
            continue
        media = covs[-1].media_id
        if not analysed(store, media):
            continue
        unlinked = [o for o in store.find(RawObservation, media_id=media)
                    if o.source_frame and o.source_frame.normalized_utc
                    and t0 <= o.source_frame.normalized_utc.timestamp() * 1000 <= t1 and not store.is_invalid(o.observation_id)]
        if unlinked:
            open_ids.append(cid)  # something tracked in view during the window: identity open, remove nothing
            continue
        negatives.append(cid)
        watched = c.footprint.copy() if watched is None else watched | c.footprint
    if watched is None:
        watched = np.zeros_like(next(iter(ctx.values())).footprint) if ctx else np.zeros((1, 1), bool)
    return watched, negatives, open_ids


def _rank(plan: SitePlan, grid: FloorGrid, mask, dist, ctx: dict[str, CameraContext], step: dict, *,
          last_xy: tuple[float, float], last_zone: str | None) -> list[dict]:
    """Rank places: the one holding the last confirmed point first (if still possible), then by the share still
    possible (uncovered places weigh more), then by walking distance."""
    places = []
    for a in plan.areas:
        if a.kind not in PLACE_KINDS or not a.walkable:
            continue
        area = grid.polygon_mask(a.polygon_m) & grid.inside
        n = int(area.sum())
        if not n:
            continue
        possible = area & mask
        share = float(possible.sum()) / n
        reach = float(dist[area & np.isfinite(dist)].min()) if (area & np.isfinite(dist)).any() else None
        watchers = sorted(cid for cid, c in ctx.items() if (c.footprint & area).sum() > 0.3 * n)
        removed = [c for c in step["removed_by_cameras"] if c in watchers]
        why_for, why_against = [], []
        # a scan belongs to its read point's zone; only a sighting without one falls back to the point itself
        here = a.zone_id == last_zone if last_zone is not None else point_in_polygon(last_xy, a.polygon_m)
        if here and share > 0:
            why_for.append("last confirmed here")
        if share > 0:
            why_for.append(f"{round(100 * share)} % of it is still possible")
        if reach is not None:
            why_for.append(f"reachable on foot: {reach:.0f} m from the last confirmed point")
        if a.kind == "blind_spot" or not watchers:
            why_for.append("no camera covers it")
        if a.kind == "machine":
            why_against.append("inside a running machine: stop the line to check")
        if removed:
            why_against.append(f"watched by {', '.join(removed)} (analysed, not seen)")
        elif watchers:
            why_against.append(f"in view of {', '.join(watchers)}, footage not analysed for it yet")
        if share == 0:
            why_against.append("outside the possible area" if reach is None or not removed else "watched without seeing it")
        places.append({"area_id": a.area_id, "name": a.name, "kind": a.kind, "zone_id": a.zone_id,
                       "possible_share": round(share, 3), "reach_m": None if reach is None else round(reach, 1),
                       "last_confirmed_here": bool(here and share > 0), "machine": a.kind == "machine",
                       "searchable_score": round(share * (1.6 if not watchers else 1.0)
                                                 * (1.3 if a.kind in ("store", "blind_spot") else 1.0)
                                                 + (0.15 if here and share > 0 else 0.0), 3),
                       "covered_by": watchers, "evidence_for": why_for, "evidence_against": why_against,
                       "centroid_xy": [round(float(v), 2) for v in np.mean(np.array(a.polygon_m), axis=0)]})  # fmt: skip
    # search order (review F-026..031 #3): searchable places first, machines last; within each, blind / unwatched places
    # and the store weigh more, then the share still possible and walking distance
    places.sort(key=lambda p: (p["machine"], -p["searchable_score"], p["reach_m"] if p["reach_m"] is not None else 1e9))
    return [p for p in places if p["possible_share"] > 0][:8] + [p for p in places if p["possible_share"] == 0][:3]


