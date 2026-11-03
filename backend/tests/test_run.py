"""The investigation run as typed steps (agent_showcase_0925): in no-key mode the deterministic steps run and every model
step says it is unavailable and why; nothing is a stand-in result. Steps are stored so the run can be replayed."""

from test_forensics import scan, world  # noqa: F401  (pytest fixture re-export)

from spoor.forensics.run import investigation_run, latest_run


def test_no_key_run_is_typed_and_honest(world):  # noqa: F811
    scan(world, "SP-TUN", "tunnel_read", 0, "tunnel")
    scan(world, "SP-PLC", "divert_confirmed", 6, "sorter_plc")
    events = []
    end = investigation_run(world.store, world.case.case_id, now=world.t0, emit=events.append)
    steps = [e for e in events if e["type"] == "run_step"]
    assert [(s["role"], s["tool"]) for s in steps][:4] == [("lead", "read_scans"), ("triage", "triage_clips"), ("lead", "plan"), ("lead", "pick_cameras")]
    first = steps[0]
    assert first["status"] == "done" and first["node"]["state"] == "seen" and "at " in first["text"] and "SP-" not in first["text"]
    assert all(s["status"] == "unavailable" for s in steps if s["tool"] in ("triage_clips", "plan", "sam_track"))
    texts = [s["text"] for s in steps if s["status"] == "unavailable" and s["tool"] in ("plan", "sam_track")]
    assert "demo mode" in texts[0] and "model key" not in " ".join(texts) and sum("so the plan comes from" in x for x in texts) == 1
    assert end["type"] == "run_end" and end["cost_usd"] == 0 and "Took" in end["text"]
    stored = latest_run(world.store, world.case.case_id)
    assert [s["seq"] for s in stored if s["type"] == "run_step"] == [s["seq"] for s in steps]
    assert stored[-1]["type"] == "run_end" and stored[-1]["text"] == end["text"]  # a replay ends on the same words


def test_keyed_but_unwired_steps_say_so(world):  # noqa: F811
    scan(world, "SP-TUN", "tunnel_read", 0, "tunnel")
    events = []
    investigation_run(world.store, world.case.case_id, now=world.t0, emit=events.append, keyed=True)
    plan = next(e for e in events if e.get("tool") == "plan")
    assert "isn't part of this run yet" in plan["text"] and "demo mode" not in plan["text"]


def test_triage_reports_seconds_sent_not_cameras(world):  # noqa: F811
    from spoor.forensics.triage import summary, windows

    # a flag sends from the sample before to the sample after; overlaps merge
    assert windows([2.0, 6.0], 2.0, 90.0) == [(0.0, 8.0)] and windows([88.0], 2.0, 90.0) == [(86.0, 90.0)]
    tri = {"every_s": 2.0, "seconds": 90.0, "frames": 90, "cameras": ["cam_A", "cam_B"], "flags": {"cam_A": [10.0], "cam_B": []},
           "model": "glimmer", "usd": 0.5}
    assert summary(tri)["sent_s"] == 4.0 and summary(tri)["total_s"] == 180.0 and summary(tri)["cameras_flagged"] == 1
    scan(world, "SP-TUN", "tunnel_read", 0, "tunnel")
    events = []
    investigation_run(world.store, world.case.case_id, now=world.t0, emit=events.append, models={"triage_flags": tri})
    step = next(e for e in events if e.get("tool") == "triage_clips")
    assert step["status"] == "done" and "4 s of 180 s" in step["text"] and "98% less footage" in step["text"]
    assert step["cost_usd"] == 0 and step["receipt"]["cost_usd"] == 0.5  # on-site, over all footage: not this case's cost
    assert step["receipt"]["output"]["flagged"] == ["cam_A"] and step["receipt"]["output"]["swept"] == ["cam_A", "cam_B"]


def test_a_stored_run_names_the_flagged_cameras_only_from_its_own_triage_file():
    from spoor.forensics.triage import name_flagged, summary

    tri = {"every_s": 2.0, "seconds": 90.0, "cameras": ["cam_A", "cam_B"], "flags": {"cam_A": [10.0], "cam_B": []}}
    t = summary(tri)
    old = {"tool": "triage_clips", "receipt": {"output": {k: t[k] for k in ("cameras_flagged", "cameras", "sent_s", "total_s")}}}
    named = name_flagged([old], tri)[0]["receipt"]["output"]
    assert named["flagged"] == ["cam_A"] and named["swept"] == ["cam_A", "cam_B"] and "flagged" not in old["receipt"]["output"]
    other = {**tri, "flags": {"cam_A": [10.0], "cam_B": [40.0]}}  # a different file: no names
    assert "flagged" not in name_flagged([old], other)[0]["receipt"]["output"]


def test_keyed_run_streams_the_agents_tool_calls_and_ends_on_the_verified_answer(world):  # noqa: F811
    from types import SimpleNamespace

    scan(world, "SP-TUN", "tunnel_read", 0, "tunnel")
    plan = {"model": "muse-wonder", "steps": [{"camera_id": "cam_a", "window_start": "2026-10-28T14:32:30+08:00",
                                               "window_end": "2026-10-28T14:33:30+08:00"}], "usd_estimate": 0.12}

    def agents(p, on_step):
        assert p is plan  # the lead's checked plan goes to the agents
        on_step({"role": "evidence", "tool": "run_sam", "args": {"camera_id": "cam_a", "concept": "person"},
                 "result": {"tracks": [{"track_id": "t1"}, {"track_id": "t2"}]}, "status": "done"})
        on_step({"role": "evidence", "tool": "door_crossings", "args": {"camera_id": "cam_a", "area_id": "AREA_1"},
                 "result": {"area": "Store room", "crossings": [{"kind": "went in"}, {"kind": "came out"}]}, "status": "done"})
        hyp = SimpleNamespace(claim="It went into AREA_1 at 06:32:32Z", status=SimpleNamespace(value="supported"),
                              tested=[{"kind": "stayed_in_area", "verdict": "supported", "check": "..."}])
        facts = {"place": "Store room", "door_at": "14:32:30", "camera": "CAM 9", "carried_in_at": "14:32:32", "until": "14:33:36"}
        return SimpleNamespace(agent_runs={"evidence": {"input_tokens": 1000, "output_tokens": 100}}, hypotheses=[hyp],
                               objects=[SimpleNamespace(inside_facts=facts)])

    events = []
    end = investigation_run(world.store, world.case.case_id, now=world.t0, emit=events.append, keyed=True,
                            models={"lead": lambda: plan, "agents": agents, "plain": lambda x: x.replace("AREA_1", "Store room")})
    steps = [e for e in events if e["type"] == "run_step"]
    texts = " | ".join(s["text"] for s in steps)
    assert ("lead", "plan") in [(s["role"], s["tool"]) for s in steps] and "isn't part of this run" not in texts
    assert "SAM 3.1 tracked people (2 tracks)" in texts and "1 went in and 1 came out" in texts
    assert "Idea: “It went into Store room" in texts and "Passed (tested: stayed inside)" in texts
    assert end["headline"] == "Most likely in the Store room." and end["cost_usd"] == 0.12 and end["tokens"] == [1000, 100]
