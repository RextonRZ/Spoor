"""The investigation run as typed steps (agent_showcase_0925: "show HOW the agent works").

One run = an ordered list of steps, each a typed event: who (crew role + model), which tool, its status, one plain
sentence, the search-map node it touches and that node's state, the running cost, cameras checked, and a receipt
(input, output, latency, cost). The Investigating screen draws everything from these events (map, crew chips, log,
meter) and the Answer screen replays them frozen. Nothing in the UI is scripted.

With model keys the run is the real investigation: Muse Wonder plans, the Spark Open evidence and hypothesis agents
call their tools (each finished call becomes a step, live), SAM tracks, the verifier decides, and the answer is the
verifier's sentence. Without keys:
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

from spoor.contracts import Case, MediaAsset, SearchPlace, SearchTask, new_id
from spoor.store import AgentStep, EvidenceStore

from .journey import build_journey, latest_plan
from .missing import missing_moment
from .possible import possible_locations
from .triage import summary as triage_summary

CREW = {
    "lead": ("Lead investigator", "Muse Wonder"),
    "triage": ("On-site triage", "Muse Glimmer · Modal"),
    "evidence": ("Evidence agent", "Muse Spark Open · Baseten"),
    "analyst": ("Camera analyst", "Muse Spark"),
    "tracker": ("Tracker", "SAM 3.1"),
    "hypothesis": ("Hypothesis agent", "Muse Spark Open · Baseten"),
    "verifier": ("Verifier", "rules, no AI"),
    "reporter": ("Reporter", "rules, no AI"),
}
TOOLS = {"lead": ["read_scans", "plan", "pick_cameras", "re_plan"], "triage": ["triage_clips"],
         "evidence": ["scan_history", "footage_for", "door_crossings", "carrier_check"], "analyst": ["observe_clip"],
         "tracker": ["sam_track"], "hypothesis": ["propose", "verify_claim"], "verifier": ["verify", "reject"],
         "reporter": ["create_search_task", "ask_a_person"]}  # fmt: skip
OPTIONAL_TOOLS = {"re_plan", "reject", "ask_a_person", "observe_clip", "carrier_check", "verify_claim"}  # drawn dashed
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

    def end(self, ev: dict) -> dict:
        """The closing event: emitted and stored with the run, so a replay ends on the same words (and headline)."""
        self.emit_cb(ev)
        self.store.put(AgentStep(step_id=f"step_{self.request_id}_{ev['seq']:02d}", case_id=self.case_id,
                                 request_id=self.request_id, seq=ev["seq"], role="run:end", kind="final", content=ev,
                                 at=self.now))  # fmt: skip
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
    if models.get("agents") is not None:  # model keys: the real investigation, step by step
        return _keyed(r, store, case_id, models, cands)
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


VERDICT = {"supported": "passed", "contradicted": "ruled out", "insufficient_evidence": "not shown either way",
           "not_evaluable": "could not be checked"}
CHECK = {"stayed_in_area": "stayed inside", "exit": "left through a door", "transition": "moved between areas",
         "transfer": "handed over", "parcel_match": "same parcel", "order": "order of sightings"}


def _keyed(r: _Run, store: EvidenceStore, case_id: str, models: dict[str, Any], cands: list[dict]) -> dict:
    """The real run: Muse Wonder's checked plan, the agents' tool calls as they finish, the verifier's verdicts, the
    answer. Every sentence here is Spoor's own, built from tool results; agents' words appear only quoted as ideas."""
    plain = models.get("plain") or (lambda x: x)
    tri = models.get("triage_flags") or {}
    swept = len(tri.get("cameras") or [])  # Glimmer looked at every one of these on site
    col = {c["camera_id"]: c["role"] if c["role"] in COLUMNS else "on_foot_next" for c in cands}
    place = {c["camera_id"]: _cam_place(c.get("camera_name", "")) for c in cands}
    tokens = [0, 0]

    def node(cid: str, state: str, label: str) -> dict:
        return {"key": cid, "column": col.get(cid, "watching_last_point"), "name": _cam(cid), "place": place.get(cid, ""),
                "state": state, "label": label}  # fmt: skip

    # 1. lead · plan (Muse Wonder, checked: real cameras, windows inside footage, real evidence ids)
    try:
        plan = models["lead"]()
    except Exception as e:  # noqa: BLE001 - the agents can still work from the scans without a plan
        plan = None
        r.step("lead", "plan", "unavailable", f"The lead could not plan this time ({type(e).__name__}); the agents start from the scans.")
    if plan:
        steps = plan.get("steps") or []
        cams = list(dict.fromkeys(st["camera_id"] for st in steps))
        what = "; ".join(f"{_cam(st['camera_id'])} from {_t(st['window_start'])} to {_t(st['window_end'])}" for st in steps[:3])
        r.step("lead", "plan", "done", f"Planned {len(steps)} check{'s' if len(steps) != 1 else ''}: {what}." if steps
               else "None of the plan's camera checks passed the checks (cameras or windows without footage), so the "
                    "agents start from the scans.",
               cost=float(plan.get("usd_estimate") or 0.0),
               receipt={"input": {"model": plan.get("model")}, "output": {"steps": len(steps), "cameras": cams,
                        "unknowns": [plain(u) for u in plan.get("unknowns") or []][:4]}, "cost_usd": plan.get("usd_estimate")})  # fmt: skip
        if plan.get("replanned"):
            r.step("lead", "re_plan", "done", f"The first plan failed the checks ({len(plan.get('rejected') or [])} step(s): unknown camera, "
                   "or a window outside its footage), so it was sent back once with the reasons.")
        if cams:
            r.step("lead", "pick_cameras", "done", f"Watching first: {', '.join(_cam(c) for c in cams)}.",
                   receipt={"output": {"cameras": cams}})  # fmt: skip
            for c in cams:
                r.emit_cb({"type": "node", "node": node(c, "queued", "Picked by the lead"), "seq": r.seq})

    # 2. the agents, one step per finished tool call
    def media_cam(mid: str | None) -> str | None:
        try:
            return store.get(MediaAsset, mid).camera_id if mid else None
        except Exception:  # noqa: BLE001
            return None

    def on_step(ev: dict) -> None:
        tool, a, res, ok = ev["tool"], ev.get("args") or {}, ev.get("result") or {}, ev["status"] == "done"
        if ev["role"] == "hypothesis" and tool != "verify_claim" and tool not in ("door_crossings", "carrier_check"):
            return  # the hypothesis agent reading timelines: its ideas are reported below, with their verdicts
        cid = a.get("camera_id") or media_cam(a.get("media_id"))
        for c in [cid, *(x.get("camera_id") for x in res.get("clips") or [] if isinstance(x, dict))]:
            if c and ok:
                r.checked.add(c)  # examined closely: any camera an agent's tool used, fresh or from earlier SAM results
        err = res.get("error") or (res.get("reason") if res.get("status") in ("analysis_unavailable", "unavailable") else None)
        if tool == "run_sam":
            who = "people" if (a.get("concept") or "").lower() in ("person", "people") else "the parcel"
            n = len(res.get("tracks") or [])
            if err or not ok:
                why = ("not one of this case's cameras" if "outside the granted scope" in str(err)
                       else "no detection there" if "no_detections" in str(err) else "the model did not answer")
                r.step("tracker", "sam_track", "unavailable", f"{_cam(cid or '')}: SAM not run ({why}).", camera_id=None)
            else:
                r.step("tracker", "sam_track", "done", f"{_cam(cid or '')}: SAM 3.1 tracked {who} ({n} track{'s' if n != 1 else ''}).",
                       node=node(cid, "seen", "Tracked") if cid and who == "the parcel" and n else None, camera_id=cid,
                       receipt={"input": {"media": a.get("media_id"), "concept": a.get("concept"), "window": res.get("frames_sent")},
                                "output": {"tracks": n, "cache_hit": res.get("cache_hit")}})  # fmt: skip
        elif tool == "ask_spark":
            r.step("analyst", "observe_clip", "done" if ok and not err else "unavailable",
                   f"{_cam(cid or '')}: Muse Spark checked a short clip ({a.get('template', 'question')})." if ok and not err
                   else f"{_cam(cid or '')}: Muse Spark could not check the clip.", camera_id=cid if ok and not err else None)  # fmt: skip
        elif tool == "door_crossings":
            xs = res.get("crossings") or []
            nin, nout = sum(x["kind"] == "went in" for x in xs), sum(x["kind"] == "came out" for x in xs)
            r.step("evidence", "door_crossings", "done" if xs else "unavailable",
                   f"{plain(res.get('area') or a.get('area_id', 'the area'))}: {nin} went in and {nout} came out at its door ({_cam(cid or '')})."
                   if xs else f"{_cam(cid or '')}: nobody tracked at that door yet.", camera_id=cid if xs else None)  # fmt: skip
        elif tool == "carrier_check":
            likely = sum(x.get("verdict") == "likely carrier" for x in res.get("results") or [])
            r.step("evidence", "carrier_check", "done", f"{_cam(cid or '')}: {likely} likely carrier{'s' if likely != 1 else ''} by place and "
                   "time (a link by place and time, never an identity).", camera_id=cid)  # fmt: skip
        elif tool == "scan_history":
            r.step("evidence", "scan_history", "done", f"Read the parcel's {len(res.get('scans') or [])} scans and where the last one leaves it.")
        elif tool == "footage_for":
            clips = res.get("clips") or []
            said = f"Found {len(clips)} recording{'s' if len(clips) != 1 else ''} for the window." if clips                 else "No recording covers that window."  # fmt: skip
            r.step("evidence", "footage_for", "done", f"{_cam(cid)}: {said[0].lower()}{said[1:]}" if cid else said,
                   camera_id=cid if clips else None)
        elif tool == "verify_claim":
            v = (res.get("verdict") or "").lower()
            r.step("hypothesis", "verify_claim", "done", f"Tested an idea with the verifier: {VERDICT.get(v, v or 'no verdict')}.")

    res = models["agents"](plan, on_step)
    for run in (res.agent_runs or {}).values():
        tokens[0] += run.get("input_tokens") or 0
        tokens[1] += run.get("output_tokens") or 0

    # 3. the ideas and the verifier's verdicts (agents' words quoted, in plain names and local time)
    for o in res.hypotheses:
        r.step("hypothesis", "propose", "done", f"Idea: \u201c{plain(o.claim)[:160]}\u201d")
        decided = next((t for t in o.tested if t["verdict"] == o.status.value), o.tested[0] if o.tested else None)
        on = f" (tested: {CHECK.get(decided['kind'], decided['kind'])})" if decided else " (nothing beyond where it was last seen)"
        if o.status.value == "contradicted":
            r.step("verifier", "reject", "rejected", f"Ruled out{on}.")
        else:
            r.step("verifier", "verify", "done", f"{'Passed' if o.status.value == 'supported' else 'Unproven'}{on}.")
    inside = next((a for a in res.objects if a.inside_facts), None)
    head = None
    if inside:
        f = inside.inside_facts
        head = f"Most likely in the {f['place']}."
        r.step("verifier", "verify", "done", f"Verified: last seen at the door of the {f['place']} at {f['door_at']} on {f['camera']}, "
               f"carried in at {f['carried_in_at']}, not seen coming out until {f['until']}.",
               node=node(f"cam_{f['camera'].replace(' ', '_')}", "seen", "Seen at the door"), camera_id=f"cam_{f['camera'].replace(' ', '_')}")  # fmt: skip

    # 4. reporter: where a person should look first
    places = [p for p in possible_locations(store, case_id)["objects"][0]["places"] if p["possible_share"] > 0]
    if inside:
        r.step("reporter", "create_search_task", "done", f"Search task ready, first stop: the {inside.inside_facts['place']}.")
        r.step("reporter", "ask_a_person", "done", f"No camera sees inside the {inside.inside_facts['place']}, so a person is asked to look.")
    elif places:
        r.step("reporter", "create_search_task", "done", f"{len(places)} place{'s' if len(places) != 1 else ''} it could be; a person is asked to look.")
    took = round(time.perf_counter() - r.t0, 1)
    ev = {"type": "run_end", "seq": r.seq + 1, "t_s": took, "cost_usd": round(r.cost, 4), "cameras_checked": len(r.checked),
          "places": len(places), "request_id": r.request_id, "headline": head, "tokens": tokens, "swept": swept,
          "text": f"Took {took:.0f} s. Muse Wonder US${r.cost:.2f}; Spark Open {round(sum(tokens) / 1000)}k tokens on Baseten. "
                  + (f"{swept} wide cameras swept on site, " if swept else "")
                  + f"{len(r.checked)} examined closely."}  # fmt: skip
    return r.end(ev)


def _end(r: _Run, *, places: int, last: dict | None = None) -> dict:
    took = round(time.perf_counter() - r.t0, 1)
    ev = {"type": "run_end", "seq": r.seq + 1, "t_s": took, "cost_usd": round(r.cost, 4), "cameras_checked": len(r.checked),
          "places": places, "request_id": r.request_id,
          "text": f"Took {took} s and US${r.cost:.2f}. {len(r.checked)} camera{'s' if len(r.checked) != 1 else ''} checked of 19."}  # fmt: skip
    return r.end(ev)


def latest_run(store: EvidenceStore, case_id: str) -> list[dict]:
    """The latest run's steps in order (for the frozen map on the Answer screen)."""
    steps = [s for s in store.find(AgentStep, case_id=case_id) if s.role.startswith("run:")]
    if not steps:
        return []
    rid = max(steps, key=lambda s: s.at).request_id
    return [s.content for s in sorted((s for s in steps if s.request_id == rid), key=lambda s: s.seq)]
