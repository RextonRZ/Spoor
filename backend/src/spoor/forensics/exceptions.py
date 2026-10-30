"""Exceptions inbox (QUEUE H15, floorplan_design_0300 §3): parcels whose next expected scan is overdue, from the scan log.

Alerting comes from the scan log, not from watching every camera: after each kind of scan the next one is expected
within an allowance (belt time from the site plan plus slack, or an operating limit for manual steps). A parcel whose
last scan is older than its allowance, measured on the log's own clock, is "stalled". One click opens a case; only
then do SAM and the agents run on the cameras that matter ("catch it before the customer complains").

The clock is `as_of` (default: the latest imported scan of the site), so an old or synthetic log is judged against its
own time, never against today's date. Allowances are stated in the response; they are operating rules, not findings."""

from datetime import datetime

from spoor.contracts import Case, ObjectInstance, ReadOutcome, ScanEvent, ScanEventKind
from spoor.store import EvidenceStore

from .journey import latest_plan

# Allowance (seconds) for the NEXT scan after each kind of last scan. Belt steps are a few belt traversals of the plan
# (tunnel -> carrier ~5 s, carrier -> divert <= one loop of 69 m at 2 m/s ~35 s, recirculation allowed 3x);
# manual steps use operating limits a hub would set (bag closed within 20 min of the divert; cage loaded within 2 h).
ALLOWANCE_S = {
    ScanEventKind.TUNNEL_READ: 30.0,
    ScanEventKind.INDUCTED: 3 * 35.0,
    ScanEventKind.RECIRCULATED: 3 * 35.0,
    ScanEventKind.DIVERT_CONFIRMED: 20 * 60.0,
    ScanEventKind.EXCEPTION_DIVERTED: 20 * 60.0,
    ScanEventKind.ARRIVED_FACILITY: 2 * 3600.0,
    ScanEventKind.CONTAINER_ADD: 2 * 3600.0,
    ScanEventKind.CONTAINER_CLOSED: 2 * 3600.0,
}
NEXT_WORDS = {
    ScanEventKind.TUNNEL_READ: "loaded onto a carrier",
    ScanEventKind.INDUCTED: "a divert to its chute",
    ScanEventKind.RECIRCULATED: "a divert to its chute",
    ScanEventKind.DIVERT_CONFIRMED: "a bagging scan",
    ScanEventKind.EXCEPTION_DIVERTED: "a rework scan",
    ScanEventKind.ARRIVED_FACILITY: "induction",
    ScanEventKind.CONTAINER_ADD: "a loading scan",
    ScanEventKind.CONTAINER_CLOSED: "a loading scan",
}
CLOSED = {ScanEventKind.DEPARTED_FACILITY, ScanEventKind.CONTAINER_LOADED}


def exceptions_inbox(store: EvidenceStore, site_id: str, *, as_of: datetime | None = None, limit: int = 50) -> dict:
    scans = [s for s in store.find(ScanEvent, site_id=site_id)
             if s.read_outcome == ReadOutcome.READ and s.corrects_scan_event_id is None]  # fmt: skip
    if not scans:
        return {"site_id": site_id, "as_of": None, "basis": "no scans imported", "stalled": [], "counts": {}}
    clock = as_of or max(s.device_time_utc for s in scans)
    last: dict[str, ScanEvent] = {}
    for s in scans:
        for i in s.identifiers:
            if i.scheme.value == "carrier_waybill" and s.device_time_utc <= clock:
                cur = last.get(i.value)
                if cur is None or s.device_time_utc > cur.device_time_utc:
                    last[i.value] = s
    cases = {}
    for c in store.find(Case, site_id=site_id):
        for o in store.find(ObjectInstance, case_id=c.case_id):
            for i in o.identifiers:
                cases.setdefault(i.value, c.case_id)
    plan = latest_plan(store, site_id)
    stalled, in_progress, closed = [], 0, 0
    for waybill, s in last.items():
        if s.event_kind in CLOSED:
            closed += 1
            continue
        allow = ALLOWANCE_S.get(s.event_kind)
        age = (clock - s.device_time_utc).total_seconds()
        if allow is None or age <= allow:
            in_progress += 1
            continue
        rp = plan.read_point(s.station_id or s.device_id) if plan else None
        stalled.append({
            "waybill": waybill, "last_scan_id": s.scan_event_id, "last_event_kind": s.event_kind.value,
            "raw_code": s.raw_code, "raw_description": s.raw_description, "read_point": s.station_id or s.device_id,
            "zone_id": s.read_point_zone_id or (rp.zone_id if rp else None), "last_at": s.device_time_utc.isoformat(),
            "age_s": round(age, 1), "allowance_s": allow, "overdue_s": round(age - allow, 1),
            "expected_next": NEXT_WORDS.get(s.event_kind, "a next scan"), "case_id": cases.get(waybill),
            "source_type": s.source_type.value,
        })  # fmt: skip
    stalled.sort(key=lambda r: -r["overdue_s"])
    return {
        "site_id": site_id, "as_of": clock.isoformat(),
        "basis": "as of the last imported scan" if as_of is None else "as of the requested time",
        "rule": "stalled = the next expected scan is overdue (allowance per last scan kind)",
        "allowances_s": {k.value: v for k, v in ALLOWANCE_S.items()},
        "counts": {"parcels": len(last), "stalled": len(stalled), "in_progress": in_progress, "closed": closed},
        "stalled": stalled[:limit],
    }
