"""The investigation run as typed steps (agent_showcase_0925: "show HOW the agent works").

One run = an ordered list of steps, each a typed event: who (crew role + model), which tool, its status, one plain
sentence, the search-map node it touches and that node's state, the running cost, cameras checked, and a receipt
(input, output, latency, cost). The Investigating screen draws everything from these events (map, crew chips, log,
meter) and the Answer screen replays them frozen. Nothing in the UI is scripted.

What runs depends on what is configured, and every step says so:
- deterministic steps always run: read the scans, pick the cameras from the floor plan and camera coverage (when the
  lead model is not configured), verify, create the search task;
- model steps (Muse Wonder plan, Glimmer triage, Muse Spark per camera, SAM 3.1 tracking) run only with their key /
  service and footage; otherwise they emit status "unavailable" with the reason, never a stand-in result.
Each step is also stored as an AgentStep (role, kind, content) so the run can be read back after the fact."""

import re
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from spoor.contracts import Case, SearchPlace, SearchTask, new_id
from spoor.store import AgentStep, EvidenceStore

from .journey import build_journey, latest_plan
from .missing import missing_moment
from .possible import possible_locations
from .triage import summary as triage_summary

CREW = {
    "lead": ("Lead investigator", "Muse Wonder"),
    "triage": ("On-site triage", "Muse Glimmer · Modal"),
    "analyst": ("Camera analysts", "Muse Spark"),
    "tracker": ("Tracker", "SAM 3.1"),
    "verifier": ("Verifier", "rules, no AI"),
    "reporter": ("Reporter", "Muse Spark Open · Baseten"),
}
TOOLS = {"lead": ["read_scans", "plan", "pick_cameras", "re_plan"], "triage": ["triage_clips"], "analyst": ["observe_clip"],
         "tracker": ["sam_track"], "verifier": ["verify", "reject"],
         "reporter": ["create_search_task", "draft_report", "ask_a_person"]}  # fmt: skip
OPTIONAL_TOOLS = {"re_plan", "reject", "ask_a_person"}  # run only when needed (drawn dashed)
COLUMNS = {"last": "Last scan", "watching_last_point": "Watching that spot", "belt_next": "Where the belt takes it",
           "on_foot_next": "Ways out on foot"}  # fmt: skip

Emit = Callable[[dict], None]
MYT = timezone(timedelta(hours=8))


def _t(iso: str) -> str:
    """'14:11:12' in Malaysia Time (the hub's clock on screen)."""
    return datetime.fromisoformat(iso).astimezone(MYT).strftime("%H:%M:%S")


def _place(name: str) -> str:
    return re.sub(r"\s*\(.*$", "", re.sub(r"^Z\d+ ", "", name)).strip()


def _cam_place(name: str) -> str:
    """'CAM_11 CHUTES C07-C12' -> 'chutes C07 to C12' (the prototype's words)."""
    words = re.sub(r"^CAM_\d+\s*", "", name or "").split()
    out = " ".join(w if any(ch.isdigit() for ch in w) else w.lower() for w in words)
    return re.sub(r"(\w\d+)-(\w\d+)", r"\1 to \2", out)


def _scan_words(kind: str, point: str | None, iso: str) -> tuple[str, str]:
    """(sentence, node name) in supervisor words, as the Hub says it (frontend lib/words.ts)."""
    t = _t(iso)
    chute = (re.search(r"C\d{2}", point or "") or [None])[0]
    return {
        "tunnel_read": (f"Read at the scan tunnel at {t}.", "Scan tunnel"),
        "inducted": (f"Loaded onto the sorter at {t}.", "Sorter induct"),
        "divert_confirmed": (f"Went into chute {chute or ''} at {t}.".replace("chute  at", "a chute at"), f"Chute {chute}" if chute else "Chute"),
        "exception_diverted": (f"Sent to the reject chute at {t}.", "Reject chute"),
        "container_add": (f"Put in a cage at {t}.", "Cage"),
        "container_loaded": (f"Left on a truck at {t}.", "Dock"),
    }.get(kind, (f"Last scanned at {t}.", point or "Last scan"))


def _cam(cid: str) -> str:
    return cid.removeprefix("cam_").replace("_", " ")


class _Run:
    def __init__(self, store: EvidenceStore, case_id: str, emit: Emit, now: datetime):
        self.store, self.case_id, self.emit_cb, self.now = store, case_id, emit, now
        self.t0, self.seq, self.cost, self.checked = time.perf_counter(), 0, 0.0, set()
        self.request_id = f"req_run{int(now.timestamp() * 1000):x}"

    def step(self, role: str, tool: str, status: str, text: str, *, node: dict | None = None, camera_id: str | None = None,
             cost: float = 0.0, receipt: dict | None = None) -> dict:  # fmt: skip
        self.seq += 1
        self.cost += cost
        if camera_id and status in ("done", "rejected"):
            self.checked.add(camera_id)
        who, model = CREW[role]
        ev = {"type": "run_step", "seq": self.seq, "t_s": round(time.perf_counter() - self.t0, 2),
              "clock": datetime.now(MYT).strftime("%H:%M:%S"), "role": role, "who": who,
              "model": model, "tool": tool, "status": status, "text": text, "node": node, "camera_id": camera_id,
              "cost_usd": round(self.cost, 4), "cameras_checked": len(self.checked), "receipt": receipt}  # fmt: skip
        self.emit_cb(ev)
        self.store.put(AgentStep(step_id=f"step_{self.request_id}_{self.seq:02d}", case_id=self.case_id, request_id=self.request_id,
                                 seq=self.seq, role=f"run:{role}", kind="tool_result" if status != "rejected" else "rejected",
                                 content=ev, at=self.now))  # fmt: skip
        return ev


def investigation_run(store: EvidenceStore, case_id: str, *, now: datetime, emit: Emit, models: dict[str, Any] | None = None,
                      keyed: bool = False) -> dict:
    """Run the crew over the case. `models` names what is configured: {"lead": backend|None, "analyst": ..., "tracker":
    ..., "triage_flags": {camera_id: [...]}|None}. Without them, the model steps are reported unavailable."""
    models = models or {}
    # plain words (review F-046 #3): the demo-mode reason is said once; later skipped AI steps say so briefly
    told = {"once": False}

    def off(what: str, then: str) -> str:
        if keyed:
            return f"The {what} isn't part of this run yet{then}."
        if not told["once"]:
            told["once"] = True
            return f"The AI {what} isn't connected in this demo mode{then}."
        return f"Skipped: the AI {what} isn't connected in this demo mode."
    r = _Run(store, case_id, emit, now)
    jo = build_journey(store, case_id)["objects"][0]
    mm = missing_moment(store, case_id)["objects"][0]
    scans = jo["scans"]
    last = jo.get("last_confirmed")

    # 1. lead · read_scans (deterministic)
    if scans:
        ls = scans[-1]
        said, where = _scan_words(ls["event_kind"], ls.get("station_id") or ls.get("device_id"), ls["t"])
        r.step("lead", "read_scans", "done", f"Read {len(scans)} scan{'s' if len(scans) != 1 else ''}. Last: {said[0].lower()}{said[1:]}",
               node={"key": "last", "column": "last", "name": where, "place": f"scan {_t(ls['t'])}", "state": "seen", "label": "Last scan"},
               receipt={"input": {"case_id": case_id}, "output": {"scans": len(scans), "last_scan_id": ls["scan_event_id"]}, "cost_usd": 0})  # fmt: skip
    else:
        r.step("lead", "read_scans", "done", "No scans of this parcel at this hub, so there is no last point to start from.")
        return _end(r, places=0)

    # 2. triage · triage_clips (Glimmer on site): seconds sent out of seconds recorded, not cameras flagged
    tri = models.get("triage_flags")
    if tri and tri.get("flags"):
        t = triage_summary(tri)
        pct = round(100 * t["sent_share"])
        r.step("triage", "triage_clips", "done",
               f"Glimmer, on the hub's own GPU, looked at {t['frames']} frames and flagged parcel handling in {t['sent_s']:.0f} s "
               f"of {t['total_s']:.0f} s of footage ({pct}%). Only those moments go to the cloud models: {100 - pct}% less footage.",
               cost=float(tri.get("usd") or 0.0),
               receipt={"input": {"model": tri.get("model"), "frames": t["frames"], "every_s": tri["every_s"]},
                        "output": {k: t[k] for k in ("sent_s", "total_s", "sent_share", "pad_s", "cameras_flagged", "cameras")},
                        "cost_usd": tri.get("usd")})  # fmt: skip
    else:
        r.step("triage", "triage_clips", "unavailable", "On-site triage has nothing for this window yet.")

    # 3. lead · plan + pick_cameras: Muse Wonder when configured, else the floor plan's own camera candidates
    cands = [row for row in mm.get("expected_next", [])]
    for row in cands:
        col = row["role"] if row["role"] in COLUMNS else "on_foot_next"
        row["_node"] = {"key": row["camera_id"], "column": col, "name": _cam(row["camera_id"]), "place": _cam_place(row.get("camera_name", "")),
                        "state": "queued", "label": "Picked"}  # fmt: skip
    if models.get("lead") is None:
        r.step("lead", "plan", "unavailable", off("planner", ", so the plan comes from the floor plan and belt routes"))
        names = ", ".join(_cam(c["camera_id"]) for c in cands) or "none"
        r.step("lead", "pick_cameras", "done", f"Picked {len(cands)} camera{'s' if len(cands) != 1 else ''} that watch the last point or where it could go next: {names}.",
               receipt={"output": {"cameras": [c["camera_id"] for c in cands], "basis": "floor plan, belt routes and camera views"}})  # fmt: skip
        for c in cands:
            r.emit_cb({"type": "node", "node": c["_node"], "seq": r.seq})
    # (keyed path: models["lead"] plans with Muse Wonder; added with the keyed S2 run)

    # 4. analysts + tracker per camera
    for c in cands:
        node = dict(c["_node"])
        if c["result"] == "no_footage":
            r.step("analyst", "observe_clip", "unavailable", f"{node['name']}: no footage for this camera yet.",
                   node={**node, "state": "nofoot", "label": "No footage"}, camera_id=c["camera_id"])  # fmt: skip
        elif models.get("analyst") is None:
            r.step("analyst", "observe_clip", "unavailable", f"{node['name']}: footage is here. " + off("camera analyst", ""),
                   node={**node, "state": "queued", "label": "Not checked yet"}, camera_id=c["camera_id"])  # fmt: skip
        elif c["result"] == "seen":
            r.step("analyst", "observe_clip", "done", f"{node['name']}: seen.", node={**node, "state": "seen", "label": "Seen"}, camera_id=c["camera_id"])
        elif c["result"] == "not_seen":
            r.step("analyst", "observe_clip", "done", f"{node['name']}: not seen, clear view.", node={**node, "state": "ruled", "label": "Not seen"},
                   camera_id=c["camera_id"])  # fmt: skip
    if models.get("tracker") is None:
        r.step("tracker", "sam_track", "unavailable", off("tracker", ", so nothing is followed frame by frame"))

    # 5. verifier (rules): what was observed must fit times, plan and belt speed
    seen = [c for c in cands if c["result"] == "seen"]
    r.step("verifier", "verify", "done", f"{len(seen)} sighting{'s' if len(seen) != 1 else ''} to check against the times, the floor plan and the belt speed."
           + ("" if seen else " Nothing to verify yet."), receipt={"output": {"accepted": len(seen), "rejected": 0}})  # fmt: skip

    # 6. reporter: where to look, and whether a person must go
    places = [p for p in possible_locations(store, case_id)["objects"][0]["places"] if p["possible_share"] > 0]
    if places:
        # the tool really creates the task (the same ranking as POST /search-tasks), unless one is already open
        open_task = next((t for t in store.find(SearchTask, case_id=case_id)), None)
        if open_task is None:
            pick = places[:6]
            pick.sort(key=lambda q: (q.get("machine", False), -q.get("searchable_score", 0), q["reach_m"] if q["reach_m"] is not None else 1e9))
            case = store.get(Case, case_id)
            plan = latest_plan(store, case.site_id) if case else None
            open_task = store.put(SearchTask(
                search_task_id=new_id("search_task"), case_id=case_id, plan_id=plan.plan_id if plan else None,
                places=[SearchPlace(area_id=q["area_id"], name=q["name"], zone_id=q["zone_id"], centroid_xy=q["centroid_xy"],
                                    why=q["evidence_for"][:3]) for q in pick],
                created_by="spoor_reporter", created_at=r.now))  # fmt: skip
        first = open_task.places[0]
        r.step("reporter", "create_search_task", "done", f"{len(places)} place{'s' if len(places) != 1 else ''} it could be. Search task ready, first stop: {_place(first.name)}.",
               receipt={"output": {"search_task_id": open_task.search_task_id, "places": [q.area_id for q in open_task.places]}})  # fmt: skip
        if len(places) >= 2:
            r.step("reporter", "ask_a_person", "done", "More than one place remains, so a person is asked to go and look.")
    return _end(r, places=len(places), last=last)


def _end(r: _Run, *, places: int, last: dict | None = None) -> dict:
    took = round(time.perf_counter() - r.t0, 1)
    ev = {"type": "run_end", "seq": r.seq + 1, "t_s": took, "cost_usd": round(r.cost, 4), "cameras_checked": len(r.checked),
          "places": places, "request_id": r.request_id,
          "text": f"Took {took} s and US${r.cost:.2f}. {len(r.checked)} camera{'s' if len(r.checked) != 1 else ''} checked of 19."}  # fmt: skip
    r.emit_cb(ev)
    return ev


def latest_run(store: EvidenceStore, case_id: str) -> list[dict]:
    """The latest run's steps in order (for the frozen map on the Answer screen)."""
    steps = [s for s in store.find(AgentStep, case_id=case_id) if s.role.startswith("run:")]
    if not steps:
        return []
    rid = max(steps, key=lambda s: s.at).request_id
    return [s.content for s in sorted((s for s in steps if s.request_id == rid), key=lambda s: s.seq)]
