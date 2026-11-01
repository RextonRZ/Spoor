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
    assert [s["seq"] for s in latest_run(world.store, world.case.case_id)] == [s["seq"] for s in steps]


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
    assert step["cost_usd"] == 0.5
