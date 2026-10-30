"""Hub dashboard (QUEUE H15): what a hub / regional manager watches, aggregated from the same read models the cases use.

Per case: status (found / located / unknown), how long it has been open, where its evidence trail ends, the cameras it
depends on next, records that conflict with the belt, and model spend. Across cases: trail ends by zone (the blind
spots that cost the most), cameras most relied on, conflicts by read point, cost per case. Nothing is estimated here
that the case views do not already show."""

from collections import Counter
from datetime import datetime
from statistics import median

from spoor.contracts import Case, ObjectInstance, Site, point_in_polygon
from spoor.store import CostEntry, EvidenceStore

from .journey import build_journey, latest_plan
from .missing import missing_moment


def _zone_of(site: Site, plan, last: dict | None) -> str | None:
    if not last:
        return None
    rp = plan.read_point(last.get("station_id")) if plan else None
    if last["kind"] == "scan" and rp and rp.zone_id:  # a scan belongs to its read point's zone
        return rp.zone_id
    if last.get("xy"):
        for a in plan.areas if plan else []:
            if a.kind in ("zone", "store") and point_in_polygon(tuple(last["xy"]), a.polygon_m):
                return a.zone_id
        for z in site.zones:
            if point_in_polygon(tuple(last["xy"]), z.polygon_m):
                return z.zone_id
    return rp.zone_id if rp else None


def hub_dashboard(store: EvidenceStore, site_id: str, *, now: datetime) -> dict:
    site = store.get(Site, site_id)
    plan = latest_plan(store, site_id)
    zones = {z.zone_id: z.name for z in site.zones}
    rows, trail_ends, relied, conflicts, costs = [], Counter(), Counter(), Counter(), []
    for case in store.find(Case, site_id=site_id):
        if not store.find(ObjectInstance, case_id=case.case_id):
            continue
        j = build_journey(store, case.case_id, plan=plan)["objects"][0]
        mm = missing_moment(store, case.case_id)["objects"][0]
        last = j["last_confirmed"]
        zone = _zone_of(site, plan, last)
        if zone:
            trail_ends[zone] += 1
        depends = [r["camera_id"] for r in mm["expected_next"] if r.get("result") != "no_footage"]
        relied.update(depends)
        scans = {s["scan_event_id"]: s for s in j["scans"]}
        for g in j["segments"]:
            if g["kind"] == "gap" and g["reason"] == "faster_than_belt" and g["after"] in scans:
                conflicts[scans[g["after"]]["station_id"] or scans[g["after"]]["device_id"]] += 1
        spend = store.find(CostEntry, case_id=case.case_id)
        usd = round(sum(c.usd_estimate or 0 for c in spend), 4)
        costs.append(usd)
        rows.append({
            "case_id": case.case_id, "question": case.question, "target": case.target_description,
            "status": "unknown",  # found needs a recorded search outcome (I7); located needs a collapsed area (I4)
            "opened_at": case.created_at.isoformat(), "open_hours": round((now - case.created_at).total_seconds() / 3600, 1),
            "trail_end": {"zone_id": zone, "zone": zones.get(zone, zone), "t": last["t"] if last else None,
                          "kind": last["kind"] if last else None, "event_kind": last.get("event_kind") if last else None},
            "depends_on_cameras": depends, "model_calls": len(spend), "cost_usd": usd,
        })  # fmt: skip
    located = [r for r in rows if r["status"] in ("located", "found")]
    return {
        "site_id": site_id, "generated_at": now.isoformat(), "label": "synthetic hub, simulated scans",
        "kpis": {"open_cases": sum(r["status"] != "found" for r in rows), "cases": len(rows),
                 "located": len(located), "found": sum(r["status"] == "found" for r in rows),
                 "median_hours_to_locate": None if not located else median(r["open_hours"] for r in located),
                 "median_cost_usd": median(costs) if costs else None, "total_cost_usd": round(sum(costs), 4)},
        "trail_ends_by_zone": [{"zone_id": z, "zone": zones.get(z, z), "cases": n} for z, n in trail_ends.most_common()],
        "cameras_relied_on": [{"camera_id": c, "cases": n} for c, n in relied.most_common()],
        "conflicts_by_read_point": [{"read_point": k, "count": n} for k, n in conflicts.most_common()],
        "cases": sorted(rows, key=lambda r: r["opened_at"], reverse=True),
    }  # fmt: skip
