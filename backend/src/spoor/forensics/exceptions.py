"""Exceptions inbox (QUEUE H15, floorplan_design_0300 §3): parcels whose next expected scan is overdue, from the scan log.

Alerting comes from the scan log, not from watching every camera: after each kind of scan the next one is expected
within an allowance (belt time from the site plan plus slack, or an operating limit for manual steps). A parcel whose
last scan is older than its allowance, measured on the log's own clock, is "stalled". One click opens a case; only
then do SAM and the agents run on the cameras that matter ("catch it before the customer complains").

The clock is `as_of` (default: the latest imported scan of the site), so an old or synthetic log is judged against its
own time, never against today's date. Allowances are stated in the response; they are operating rules, not findings."""

from datetime import datetime, timedelta

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
# What the NEXT point on the route records (review F-026..031 P0): a parcel is only stalled if that point kept recording
# other parcels after its allowance ran out; if the log simply ends, nobody can judge.
NEXT_KINDS = {
    ScanEventKind.TUNNEL_READ: {ScanEventKind.INDUCTED},
    ScanEventKind.INDUCTED: {ScanEventKind.DIVERT_CONFIRMED, ScanEventKind.RECIRCULATED},
    ScanEventKind.RECIRCULATED: {ScanEventKind.DIVERT_CONFIRMED, ScanEventKind.RECIRCULATED},
    ScanEventKind.DIVERT_CONFIRMED: {ScanEventKind.CONTAINER_ADD, ScanEventKind.CONTAINER_CLOSED,
                                     ScanEventKind.CONTAINER_OPENED},
    ScanEventKind.EXCEPTION_DIVERTED: {ScanEventKind.MANUAL_ENCODED, ScanEventKind.RELABELED, ScanEventKind.INDUCTED},
    ScanEventKind.ARRIVED_FACILITY: {ScanEventKind.INDUCTED, ScanEventKind.TUNNEL_READ},
    ScanEventKind.CONTAINER_ADD: {ScanEventKind.CONTAINER_LOADED},
    ScanEventKind.CONTAINER_CLOSED: {ScanEventKind.CONTAINER_LOADED},
}


def _next_station(s: ScanEvent) -> str | None:
    """The read point the parcel should reach next when the route fixes it (divert at C04 -> the C04 bagging point;
    a line tunnel -> that line induct point)."""
    st = s.station_id or ""
    if st.startswith("SP-DIV-"):
        return "SP-BAG-" + st.removeprefix("SP-DIV-")
    if st.startswith("SP-TUNNEL"):
        return st.replace("SP-TUNNEL", "SP-INDUCT")
    return None


def _kept_working(scans: list[ScanEvent], last: ScanEvent, after, upto) -> ScanEvent | None:
    """A scan of ANOTHER parcel at the next point on the route, after the allowance ran out: the hub kept working."""
    kinds = NEXT_KINDS.get(last.event_kind, set())
    station = _next_station(last)
    mine = {i.key for i in last.identifiers}
    for s in scans:
        at_point = station is None or (s.station_id or s.device_id) == station
        if after < s.device_time_utc <= upto and s.event_kind in kinds and at_point and not ({i.key for i in s.identifiers} & mine):
            return s
    return None


def exceptions_inbox(store: EvidenceStore, site_id: str, *, as_of: datetime | None = None, after_log_min: float = 0,
                     limit: int = 50) -> dict:  # fmt: skip
    """`as_of` wins; otherwise the clock is the last imported scan + `after_log_min` (an operator setting that replays
    "what would the inbox show N minutes after this log ended")."""
    scans = [s for s in store.find(ScanEvent, site_id=site_id)
             if s.read_outcome == ReadOutcome.READ and s.corrects_scan_event_id is None]  # fmt: skip
    if not scans:
        return {"site_id": site_id, "as_of": None, "basis": "no scans imported", "stalled": [], "counts": {}}
    log_end = max(s.device_time_utc for s in scans)
    clock = as_of or log_end + timedelta(minutes=after_log_min)
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
    stalled, in_progress, closed, cannot_judge = [], 0, 0, 0
    for waybill, s in last.items():
        if s.event_kind in CLOSED:
            closed += 1
            continue
        allow = ALLOWANCE_S.get(s.event_kind)
        age = (clock - s.device_time_utc).total_seconds()
        if allow is None or age <= allow:
            in_progress += 1
            continue
        proof = _kept_working(scans, s, s.device_time_utc + timedelta(seconds=allow), clock)
        if proof is None:
            cannot_judge += 1  # the log ends (or the next point went quiet): no evidence the parcel failed to arrive
            continue
        rp = plan.read_point(s.station_id or s.device_id) if plan else None
        stalled.append({
            "waybill": waybill, "last_scan_id": s.scan_event_id, "last_event_kind": s.event_kind.value,
            "raw_code": s.raw_code, "raw_description": s.raw_description, "read_point": s.station_id or s.device_id,
            "zone_id": s.read_point_zone_id or (rp.zone_id if rp else None), "last_at": s.device_time_utc.isoformat(),
            "age_s": round(age, 1), "allowance_s": allow, "overdue_s": round(age - allow, 1),
            "expected_next": NEXT_WORDS.get(s.event_kind, "a next scan"), "case_id": cases.get(waybill),
            "source_type": s.source_type.value,
            "proof": {"scan_event_id": proof.scan_event_id, "station": proof.station_id or proof.device_id,
                      "at": proof.device_time_utc.isoformat(), "event_kind": proof.event_kind.value},
        })  # fmt: skip
    stalled.sort(key=lambda r: -r["overdue_s"])
    return {
        "site_id": site_id, "as_of": clock.isoformat(),
        "basis": ("as of the requested time" if as_of else f"{after_log_min:g} min after the last imported scan"
                  if after_log_min else "as of the last imported scan"), "log_end": log_end.isoformat(),
        "rule": ("stalled = the next expected scan is overdue and the next point on its route kept scanning other "
                 "parcels after that; otherwise the log cannot judge"),
        "allowances_s": {k.value: v for k, v in ALLOWANCE_S.items()},
        "counts": {"parcels": len(last), "stalled": len(stalled), "in_progress": in_progress, "closed": closed,
                   "cannot_judge": cannot_judge},
        "stalled": stalled[:limit],
    }
