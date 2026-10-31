"""Journey segments (QUEUE I2): the backend, not the browser, types every stretch of a case object's path.

- observed: inside one camera's continuous track (existing track segments; solid green).
- inferred_along_conveyor: between two anchors (scan or placed observation) that both sit on conveyance, when the plan
  has a forward belt route between them and the times allow it; carries the route, belt time and the time window
  (amber dotted). Identity is carried by the two scans, the route by the plan — nothing in between was seen.
- gap: everything else, including after the last confirmed point. Never bridged; carries the cameras that recorded.
Every segment lists the evidence ids it rests on. No-key mode: scans + inferred + gaps; `needs` says tracking needs SAM.
"""

import itertools
from dataclasses import dataclass
from datetime import UTC, datetime

from spoor.contracts import Case, ClockDomain, DeviceKind, ObjectInstance, ReadOutcome, SitePlan
from spoor.store import EvidenceStore, ObjectView, coverage_intervals, site_camera_ids, track_segments
from spoor.store.parcels import TimedScan, object_keys, scans_for

from .conveyance import ConveyorNet, Route

ON_CONVEYANCE_DEVICES = frozenset({DeviceKind.TUNNEL, DeviceKind.SORTER_PLC, DeviceKind.DWS_STATIC,
                                   DeviceKind.SHIP_SORTER})  # fmt: skip
SAME_CLOCK_TOL_S = 0.5  # same device clock: logging granularity (0.1 s) + photo-eye / encoder latency
DWELL_FACTOR = 0.5  # scan gap longer than belt time by more than this share (and > 5 s) => may have waited / left
CONTRACT = ("observed = inside one camera track; inferred_along_conveyor = the plan's only forward belt route between "
            "two anchors whose times allow it (not seen); gap = unknown, never bridged.")  # fmt: skip


def iso(ms: float) -> str:
    return datetime.fromtimestamp(ms / 1000, UTC).isoformat(timespec="milliseconds")


def latest_plan(store: EvidenceStore, site_id: str) -> SitePlan | None:
    plans = store.find(SitePlan, site_id=site_id)
    return plans[-1] if plans else None


@dataclass
class Anchor:
    """A confirmed point in time and (maybe) space: a scan, or one end of an observed track segment."""

    kind: str  # "scan" | "observation"
    evidence_id: str
    t_ms: float
    xy: tuple[float, float] | None
    unc_ms: float | None  # None = clock not synchronized
    clock_domain_id: str | None
    on_belt: tuple[str, float] | None  # (conveyor_id, arc length)
    camera_id: str | None = None
    station_id: str | None = None
    event_kind: str | None = None


def scan_xy(plan: SitePlan | None, ts: TimedScan) -> tuple[float, float] | None:
    rp = plan.read_point(ts.scan.station_id or ts.scan.device_id) if plan else None
    return rp.position_for(ts.scan.event_kind.value) if rp else None


def _timing(a: Anchor, b: Anchor) -> tuple[bool, float | None, str]:
    """(checkable, tolerance_s, clock note) for comparing the interval a->b with a belt travel time."""
    if a.kind == b.kind == "scan" and a.clock_domain_id and a.clock_domain_id == b.clock_domain_id:
        return True, SAME_CLOCK_TOL_S, "same device clock"
    if a.unc_ms is not None and b.unc_ms is not None:
        return True, SAME_CLOCK_TOL_S + (a.unc_ms + b.unc_ms) / 1000, "clocks synchronized"
    return False, None, "different clocks, not synchronized: timing not checkable"


def _clock_view(ts: TimedScan) -> dict:
    return {"synchronized": ts.synced, "uncertainty_ms": ts.unc_ms, "late_upload": ts.late_upload,
            "clock_domain_id": ts.scan.clock_domain_id}  # fmt: skip


def build_journey(store: EvidenceStore, case_id: str, *, plan: SitePlan | None = None) -> dict:
    case = store.get(Case, case_id)
    plan = plan or latest_plan(store, case.site_id)
    net = ConveyorNet(plan) if plan else None
    domains = {d.clock_domain_id: d for d in store.find(ClockDomain, site_id=case.site_id)}
    out = []
    for obj in store.find(ObjectInstance, case_id=case_id):
        out.append(_object_journey(store, case, obj, plan, net, domains))
    needs = [] if any(o["observed_segments"] for o in out) else [
        ("Observed segments need object tracking in the footage (SAM 3.1 via MODEL_API_KEY). Without it the journey "
        "is scans, belt-routed inferences between them, and gaps.")]  # fmt: skip
    return {"case_id": case_id, "plan_id": plan.plan_id if plan else None, "contract": CONTRACT,
            "needs": needs + ([] if plan else ["No site plan imported: scans cannot be placed or routed on belts."]),
            "objects": out}  # fmt: skip


def _object_journey(store, case, obj, plan, net, domains) -> dict:
    keys = object_keys(store, obj.object_instance_id)
    timeline = scans_for(store, keys, site_id=case.site_id) if keys else None
    scans = [ts for ts in (timeline.scans if timeline else []) if ts.scan.read_outcome == ReadOutcome.READ]
    beads, anchors = [], []
    for ts in scans:
        xy = scan_xy(plan, ts)
        belt = None
        if net and xy and ts.scan.device_kind in ON_CONVEYANCE_DEVICES:
            snap = net.snap(xy)
            belt = (snap[0], snap[1]) if snap else None
        beads.append({"scan_event_id": ts.scan.scan_event_id, "t": iso(ts.t_ms), "event_kind": ts.scan.event_kind.value,
                      "raw_code": ts.scan.raw_code, "raw_description": ts.scan.raw_description,
                      "read_outcome": ts.scan.read_outcome.value, "source_type": ts.scan.source_type.value,
                      "station_id": ts.scan.station_id, "device_id": ts.scan.device_id,
                      "device_kind": ts.scan.device_kind.value, "zone_id": ts.scan.read_point_zone_id,
                      "xy": xy, "on_conveyor": belt[0] if belt else None, "clock": _clock_view(ts),
                      "clock_domain": domains[d].name if (d := ts.scan.clock_domain_id) in domains else None,
                      "sort_destination_actual": ts.scan.sort_destination_actual,
                      "weight_g": ts.scan.weight_g, "dims_mm": ts.scan.dims_mm})  # fmt: skip
        anchors.append(Anchor("scan", ts.scan.scan_event_id, ts.t_ms, xy, ts.unc_ms if ts.synced else None,
                              ts.scan.clock_domain_id, belt, station_id=ts.scan.station_id or ts.scan.device_id,
                              event_kind=ts.scan.event_kind.value))

    view = ObjectView.load(store, obj.object_instance_id)
    observed = []
    for seg in track_segments(store, obj.object_instance_id, view=view):
        pts = []
        for t in seg.observations:
            est = view.estimates.get(t.obs.observation_id)
            pts.append({"t": iso(t.t_ms), "observation_id": t.obs.observation_id,
                        "xy": est.floor_xy_m if est else None, "zone_id": est.zone_id if est else None,
                        "uncertainty_radius_m": est.uncertainty_radius_m if est else None})  # fmt: skip
        observed.append({"kind": "observed", "start": iso(seg.start_ms), "end": iso(seg.end_ms),
                         "camera_id": seg.camera_id, "track_id": seg.track_id, "points": pts,
                         "evidence_ids": seg.observation_ids})  # fmt: skip
        for edge, t in (("start", seg.observations[0]), ("end", seg.observations[-1])):
            est = view.estimates.get(t.obs.observation_id)
            xy = tuple(est.floor_xy_m) if est and est.floor_xy_m else None
            snap = net.snap(xy) if net and xy else None
            anchors.append(Anchor("observation", t.obs.observation_id, t.t_ms + (0.001 if edge == "end" else 0), xy,
                                  t.unc_ms, None, (snap[0], snap[1]) if snap else None, seg.camera_id))  # fmt: skip

    anchors.sort(key=lambda a: (a.t_ms, a.evidence_id))
    obs_spans = [(s["start"], s["end"]) for s in observed]
    covs = coverage_intervals(store, site_camera_ids(store, obj.object_instance_id))
    segments: list[dict] = list(observed)
    for a, b in itertools.pairwise(anchors):
        if b.t_ms - a.t_ms <= 0 or any(s <= iso(a.t_ms) and iso(b.t_ms) <= e for s, e in obs_spans):
            continue  # inside an observed segment: scans there are beads only
        segments.append(_between(a, b, net, covs))

    window_end = case.window.end_utc.timestamp() * 1000 if case.window else None
    cov_end = max((e for _, e, _ in covs), default=None)
    horizon = max(x for x in (window_end, cov_end) if x is not None) if (window_end or cov_end) else None
    last = anchors[-1] if anchors else None
    if last and horizon and horizon > last.t_ms:
        segments.append(_gap(last.t_ms, horizon, covs, after=last.evidence_id, before=None,
                             reason="after_last_confirmed"))  # fmt: skip
    segments.sort(key=lambda s: (s["start"], s["kind"] != "observed"))
    return {"object_instance_id": obj.object_instance_id, "label": obj.label, "identity_keys": sorted(keys),
            "scans": beads, "segments": segments, "observed_segments": len(observed),
            "last_confirmed": (_anchor_view(last) if last else None)}  # fmt: skip


def _anchor_view(a: Anchor) -> dict:
    return {"kind": a.kind, "evidence_id": a.evidence_id, "t": iso(a.t_ms), "xy": a.xy, "camera_id": a.camera_id,
            "on_conveyor": a.on_belt[0] if a.on_belt else None, "station_id": a.station_id,
            "event_kind": a.event_kind}  # fmt: skip


def _gap(t0: float, t1: float, covs, *, after: str | None, before: str | None, reason: str, note: str = "") -> dict:
    cams = sorted({c for a, b, c in covs if a < t1 and b > t0})
    return {"kind": "gap", "start": iso(t0), "end": iso(t1), "reason": reason, "note": note,
            "covering_camera_ids": cams, "after": after, "before": before,
            "evidence_ids": [x for x in (after, before) if x]}  # fmt: skip


def _between(a: Anchor, b: Anchor, net: ConveyorNet | None, covs) -> dict:
    gap_s = (b.t_ms - a.t_ms) / 1000
    if not (net and a.on_belt and b.on_belt):
        why = "no site plan" if net is None else "not both on conveyance"
        return _gap(a.t_ms, b.t_ms, covs, after=a.evidence_id, before=b.evidence_id, reason="unobserved",
                    note=f"{why}: how it moved between these two points is unknown")  # fmt: skip
    route: Route | None = net.route(a.on_belt, b.on_belt)
    if route is None:
        return _gap(a.t_ms, b.t_ms, covs, after=a.evidence_id, before=b.evidence_id, reason="no_belt_route",
                    note="no forward conveyor route joins these two points; it left the belts in between")  # fmt: skip
    checkable, tol, clock_note = _timing(a, b)
    belt_s = route.min_time_s
    if checkable and gap_s + tol < belt_s:
        return _gap(a.t_ms, b.t_ms, covs, after=a.evidence_id, before=b.evidence_id, reason="faster_than_belt",
                    note=f"recorded {gap_s:.1f} s, but the belt route needs {belt_s:.1f} s: the records conflict")
    slack = gap_s - belt_s
    dwell = checkable and slack > max(5.0, DWELL_FACTOR * belt_s)
    return {"kind": "inferred_along_conveyor", "start": iso(a.t_ms), "end": iso(b.t_ms),
            "from": a.evidence_id, "to": b.evidence_id, "evidence_ids": [a.evidence_id, b.evidence_id],
            "route": [p.conveyor_id for p in route.pieces], "path_m": route.path_m,
            "length_m": round(route.length_m, 2), "belt_time_s": round(belt_s, 2), "recorded_gap_s": round(gap_s, 2),
            "slack_s": round(slack, 2), "timing": ("consistent" if checkable and not dwell else
                                                   "longer_than_belt" if dwell else "not_checkable"),
            "clock_note": clock_note, "unknown_speed_m": round(route.unknown_speed_m, 2),
            "note": ("recorded gap is longer than the belt needs: it may have waited in accumulation or left the "
                     "belt and come back; not observed" if dwell else "inferred from the plan's belt route; not seen"),
            "covering_camera_ids": sorted({c for x, y, c in covs if x < b.t_ms and y > a.t_ms})}  # fmt: skip
