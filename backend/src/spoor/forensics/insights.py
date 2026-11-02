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


def unread_at_tunnel(store: EvidenceStore, site_id: str) -> dict | None:
    """Root cause of the parcels 'lost' after unloading (tick 2315 RCA): a tunnel NO-READ carries no waybill, so a parcel
    whose label was not read shows only its unload scan and then nothing. Each no-read is matched to the unload-only
    parcel whose unload scan sits one usual unload-to-tunnel time before it (median +- 3x the 10th-90th spread, nearest
    first, each used once). Matched = the parcel went on unread (to the reject chute), not lost; unmatched stays open."""
    evs = store.find(ScanEvent, site_id=site_id)
    nr = sorted((e for e in evs if e.event_kind.value == "tunnel_no_read"), key=lambda e: e.device_time_utc)
    if not nr:
        return None
    first: dict[str, dict] = defaultdict(dict)
    for e in sorted(evs, key=lambda e: e.device_time_utc):
        if e.read_outcome.value != "read":
            continue
        for i in e.identifiers:
            if i.scheme.value == "carrier_waybill":
                first[i.value].setdefault(e.event_kind.value, e.device_time_utc)
    hop = [(p["tunnel_read"] - p["arrived_facility"]).total_seconds() for p in first.values()
           if "arrived_facility" in p and "tunnel_read" in p]  # fmt: skip
    if len(hop) < 5:
        return None
    med, tol = _q(hop, 0.5), max(2.0, 3 * (_q(hop, 0.9) - _q(hop, 0.1)))
    lone = {w: p["arrived_facility"] for w, p in first.items() if "arrived_facility" in p and "tunnel_read" not in p}
    exc = {e.device_time_utc for e in evs if e.event_kind.value == "exception_diverted" and e.read_outcome.value != "read"}
    matched, used = [], set()
    for r in nr:
        best = min(((abs((r.device_time_utc - t).total_seconds() - med), w) for w, t in lone.items() if w not in used),
                   default=None)  # fmt: skip
        if best and best[0] <= tol:
            used.add(best[1])
            matched.append({"waybill": best[1], "unloaded": lone[best[1]].isoformat(), "no_read": r.device_time_utc.isoformat()})
    return {"no_reads": len(nr), "to_reject_chute": len(exc), "matched": sorted(matched, key=lambda m: m["unloaded"]),
            "unmatched_unload_only": sorted(w for w in lone if w not in used), "usual_s": round(med, 1)}


def actions(ins: dict, unread: dict | None) -> list[dict]:
    """What needs fixing, most urgent first: a customer's case first, then records the cameras contradict, then the
    hub-wide patterns by how many parcels they touch. Each with its count, where, why (the evidence in one line), the
    fix in plain words and the parcels or cases behind it."""
    out = []
    for b in ins["breaks"]:
        out.append({"key": f"break:{b['where']}", "tone": "bad", "count": len(b["cases"]), "unit": "case",
                    "title": f"{b['where']}: {b['what'].lower()}", "why": "An answered case: the cameras show it carried in, with no scan-in",
                    "fix": b.get("fix", ""), "cases": b["cases"], "parcels": []})  # fmt: skip
    for d in ins["disagreed"]:
        out.append({"key": f"rec:{d['where']}", "tone": "bad", "count": len(d["cases"]), "unit": "case",
                    "title": f"{d['where']} {d['what']}", "why": "The record says it left; the cameras show it still inside",
                    "fix": "Read each parcel at the dock, or check the cage's contents before it is marked loaded",
                    "cases": d["cases"], "parcels": []})  # fmt: skip
    if unread and unread["no_reads"]:
        m = len(unread["matched"])
        out.append({"key": "unread", "tone": "warn", "count": unread["no_reads"], "unit": "carton",
                    "title": "Labels not read at the scan tunnel",
                    "why": f"{m} of them match a parcel that was unloaded {round(unread['usual_s'])} s earlier and never scanned "
                           "again: not lost, sent on unread" + (f"; {unread['to_reject_chute']} went to the reject chute"
                                                                 if unread["to_reject_chute"] else ""),
                    "fix": "Check the tunnel's read rate (camera, lighting, damaged labels) and match the reject chute's "
                           "cartons to these unload scans", "cases": [],
                    "parcels": [{"waybill": x["waybill"], "t": x["unloaded"]} for x in unread["matched"]]})  # fmt: skip
    return out


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
                    f"Make the scan-in at the {_place(inside['place'])} door a must: nothing goes in without it")].append(cid)
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

    out = {
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
        "unread": unread_at_tunnel(store, site_id),
        "cost": {"usd": round(sum(c.usd_estimate or 0 for c in spend), 4), "calls": len(spend),
                 "cases_with_spend": len({c.case_id for c in spend}),
                 "answer_seconds": sorted(answer_s), "footage_hours": round(footage_s / 3600, 2)},
    }  # fmt: skip
    out["actions"] = actions(out, out["unread"])
    return out

