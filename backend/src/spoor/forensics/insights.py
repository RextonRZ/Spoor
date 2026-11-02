"""Hub insights (Rexton 2 Nov, tick 2315): the feedback loop, from records already in the store and nothing else.

cases opened (a customer asked / the hub's own checks) -> answered by an investigation -> checked on the floor by staff
(Go look: found / not found) -> resolved; where the trail breaks (the checkpoint or place each answered case points to,
with the fix in plain words), the records the cameras contradicted, how well the system can check itself (scan points no
camera sees, checkpoint cameras on a fitted clock, the numbers shown per camera, footage skipped before the cloud) and
what it cost. Every count carries the ids it was counted from, so the screen can link each one to its source. Nothing
is estimated here: with no confirmed outcome yet it says so. Demo hub data (a synthetic hub, simulated scans).
"""

from collections import defaultdict
from datetime import datetime
from itertools import pairwise

from spoor.agents.orchestrator import latest_answer
from spoor.contracts import (
    Camera,
    CameraCoverage,
    Case,
    ClockSync,
    MediaAsset,
    ScanEvent,
    SearchOutcome,
    SearchTask,
)
from spoor.store import CostEntry, EvidenceStore, LiveAlert, ScanHandshake

from .dashboard import hub_dashboard
from .journey import latest_plan
from .run import latest_run

WORDS = {"arrived_facility": "unloading", "tunnel_read": "the tunnel read", "inducted": "induction",
         "divert_confirmed": "its chute", "container_add": "its cage or bag", "container_loaded": "loading"}


def _place(name: str) -> str:
    return name.split(" (")[0]


FLOW = [("arrived_facility", "Unloaded"), ("tunnel_read", "Label read"), ("inducted", "On the sorter"),
        ("divert_confirmed", "Into a chute"), ("container_add", "Into a bag or cage")]


def _q(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, max(0, round(q * (len(xs) - 1))))]


def scan_flow(store: EvidenceStore, site_id: str) -> dict:
    """The whole scan log, parcel by parcel (not only the cases): how many reached each checkpoint, how long each hop
    takes (median and the 10th-90th percentile), and per hop the parcels with no next scan, split into OVERDUE (waited
    more than twice the hop's 90th percentile before the log ends) and RECENT (the log ended before they were due):
    without that split the last hop looks like a loss when it is only the end of the log. Scans per minute too."""
    evs = sorted((e for e in store.find(ScanEvent, site_id=site_id) if e.read_outcome.value == "read"),
                 key=lambda e: e.device_time_utc)  # fmt: skip
    if not evs:
        return {}
    first: dict[str, dict] = defaultdict(dict)
    for e in evs:
        for i in e.identifiers:
            if i.scheme.value == "carrier_waybill":
                first[i.value].setdefault(e.event_kind.value, e.device_time_utc)
    end, start = evs[-1].device_time_utc, evs[0].device_time_utc
    hops = []
    for (a, an), (b, bn) in pairwise(FLOW):
        d = [(p[b] - p[a]).total_seconds() for p in first.values() if a in p and b in p]
        if len(d) < 3:
            continue
        p90 = _q(d, 0.9)
        waiting = [(end - p[a]).total_seconds() for p in first.values() if a in p and b not in p]
        hops.append({"from": an, "to": bn, "n": len(d), "median_s": round(_q(d, 0.5), 1), "p10_s": round(_q(d, 0.1), 1),
                     "p90_s": round(p90, 1), "overdue": sum(w > 2 * p90 for w in waiting),
                     "recent": sum(w <= 2 * p90 for w in waiting)})  # fmt: skip
    minute: dict[str, int] = defaultdict(int)
    for e in evs:
        minute[e.device_time_utc.replace(second=0, microsecond=0).isoformat()] += 1
    return {"parcels": len(first), "window": [start.isoformat(), end.isoformat()],
            "reached": [{"stage": n, "parcels": sum(1 for p in first.values() if k in p)} for k, n in FLOW],
            "hops": hops, "per_minute": [{"t": k, "scans": v} for k, v in sorted(minute.items())]}  # fmt: skip


def hub_insights(store: EvidenceStore, site_id: str, *, now: datetime) -> dict:
    dash = hub_dashboard(store, site_id, now=now)
    plan = latest_plan(store, site_id)
    cases = {c.case_id: c for c in store.find(Case, site_id=site_id)}
    rows = [r for r in dash["cases"] if r["case_id"] in cases]
    invalid = store.invalid_ids()

    # 1. the loop
    asked = [r["case_id"] for r in rows if r["customer_asked"]]
    alerts = [a.alert_id for a in store.find(LiveAlert) if a.site_id == site_id]
    answered, confirmed, refuted, resolved = [], [], [], []
    breaks: dict[tuple, list[str]] = defaultdict(list)
    disagreed: dict[tuple, list[str]] = defaultdict(list)
    answer_s, footage_s = [], 0.0
    for r in rows:
        cid = r["case_id"]
        ans = latest_answer(store, cid) or {}
        o = next(iter(ans.get("objects") or []), {})
        inside, last_scan = o.get("inside"), o.get("last_scan")
        if inside or last_scan:
            answered.append(cid)
        outcomes = store.find(SearchOutcome, case_id=cid)
        names = {pl.area_id: pl.name for t in store.find(SearchTask, case_id=cid) for pl in t.places}
        found = next((x for x in reversed(outcomes) if x.outcome == "found"), None)
        if found:
            resolved.append(cid)
            if inside and _place(names.get(found.area_id, found.area_id)) == _place(inside["place"]):
                confirmed.append(cid)  # staff found it where the answer said
        if inside and any(x.outcome == "not_found" and _place(names.get(x.area_id, "")) == _place(inside["place"])
                          for x in outcomes):  # fmt: skip
            refuted.append(cid)
        # 2. where the trail breaks: the answer's own place (carried in, not scanned in), else where the scans stop
        if inside:
            breaks[(_place(inside["place"]), "Carried in, not scanned in",
                    f"The scan-in at the {_place(inside['place'])} door was skipped")].append(cid)
            # 3. a record the cameras contradict: the cage's load read while its parcel was inside
            until, came_in = inside["iso"].get("until"), inside["iso"].get("carried_in_at")
            for s in store.find(ScanEvent, event_kind="container_loaded"):
                t = s.device_time_utc.isoformat()
                if came_in and until and came_in < t < until and (s.station_id or s.device_id):
                    door = next((p for p in (s.station_id or "").split("-") if p.startswith("D")), s.station_id)
                    how = "RFID" if s.device_kind.value == "rfid_portal" else "Handheld scan"
                    disagreed[(f"{how} at {door}", f"marked a cage loaded while its parcel was in the {_place(inside['place'])}")].append(cid)
        elif r["status"] == "unknown" and r["trail_end"]["zone"]:  # lost track (a case confirmed on camera at its
            # last scan, or one its latest scan still places, is not a place the hub loses parcels)
            kind = WORDS.get(r["trail_end"]["event_kind"] or "", (r["trail_end"]["event_kind"] or "").replace("_", " "))
            breaks[(r["trail_end"]["zone"], f"Trail ends after {kind or 'its last sighting'}",
                    "No camera shows where it went next")].append(cid)
        # 5. time to an answer, and the footage a person would have scrolled
        end = next((s for s in reversed(latest_run(store, cid)) if s.get("type") == "run_end"), None)
        if end:
            answer_s.append(end["t_s"])
    for m in store.find(MediaAsset):
        if m.site_id == site_id and m.kind.value == "original" and m.media_id not in invalid:
            for c in store.find(CameraCoverage, media_id=m.media_id):
                footage_s += (c.end_utc - c.start_utc).total_seconds()

    # 4. the system checking itself
    unseen = sorted(rp.scan_point_id for rp in (plan.read_points if plan else []) if not rp.visible_by)
    cams = [c for c in store.find(Camera) if c.site_id == site_id]
    clock = {}
    for c in cams:
        syncs = store.find(ClockSync, camera_id=c.camera_id)
        clock[c.camera_id] = bool(syncs) and syncs[-1].method == "fitted_from_anchor_events"
    chk = sorted(c for c in clock if c.removeprefix("cam_").startswith("CHK_"))
    per_cam: dict[str, dict] = defaultdict(lambda: {"outlined": 0, "labelled": 0})
    for h in store.find(ScanHandshake):
        if h.site_id == site_id and h.camera_id and h.media_id not in invalid and h.outcome == "outlined":
            per_cam[h.camera_id]["outlined"] += 1
            per_cam[h.camera_id]["labelled"] += int(bool(h.labelled))
    skipped = None
    for cid in answered:
        tri = next((s for s in latest_run(store, cid) if s.get("tool") == "triage_clips" and s.get("receipt")), None)
        share = ((tri or {}).get("receipt") or {}).get("output", {}).get("sent_share")
        if share is not None:
            skipped = {"share": round(1 - share, 3), "case_id": cid}
            break
    spend = [c for c in store.find(CostEntry) if c.case_id in cases]

    def rank(d: dict) -> list[dict]:
        return [{"where": k[0], "what": k[1], **({"fix": k[2]} if len(k) > 2 else {}), "cases": v}
                for k, v in sorted(d.items(), key=lambda kv: -len(kv[1]))]

    return {
        "site_id": site_id, "generated_at": now.isoformat(), "label": "Demo hub data",
        "loop": {"customer_asked": asked, "alerts": alerts, "opened": [r["case_id"] for r in rows], "answered": answered,
                 "checked": sorted(set(confirmed) | set(refuted) | set(resolved)), "confirmed": confirmed,
                 "refuted": refuted, "resolved": resolved,
                 "resolved_on_camera": [r["case_id"] for r in rows if r["status"] == "confirmed"]},
        "breaks": rank(breaks),
        "disagreed": rank(disagreed),
        "health": {
            "scan_points_unseen": unseen, "scan_points": len(plan.read_points) if plan else 0,
            "checkpoint_cameras": [{"camera_id": c, "clock_fitted": clock[c]} for c in chk],
            "cameras_fitted": sum(clock.values()), "cameras": len(clock),
            "numbers_by_camera": [{"camera_id": k, **v} for k, v in sorted(per_cam.items(), key=lambda kv: -kv[1]["outlined"])],
            "footage_skipped": skipped,
        },
        "flow": scan_flow(store, site_id),
        "cost": {"usd": round(sum(c.usd_estimate or 0 for c in spend), 4), "calls": len(spend),
                 "cases_with_spend": len({c.case_id for c in spend}),
                 "answer_seconds": sorted(answer_s), "footage_hours": round(footage_s / 3600, 2)},
    }  # fmt: skip

