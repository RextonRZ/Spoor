"""Forensic journey (QUEUE block I). Plans, scans and tracks here are hand-made test fixtures, not demo data."""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from builders import HUMAN, World

from spoor.contracts import (
    AssociationStatus,
    Camera,
    ClockDomain,
    ClockSync,
    ObjectInstance,
    ParcelIdentifier,
    ScanEvent,
    SitePlan,
    new_id,
)
from spoor.forensics import ConveyorNet, build_journey
from spoor.forensics.missing import missing_moment
from spoor.store import EvidenceStore

REPO = Path(__file__).resolve().parents[2]
WAYBILL = ParcelIdentifier(scheme="carrier_waybill", value="CTX100200300400")


def plan_for(site_id: str, now) -> SitePlan:
    """Belt A runs east (1 m/s) and feeds belt B north (2 m/s); a handheld bench sits off the belts."""
    return SitePlan(
        plan_id="plan_test", site_id=site_id, source="unit test fixture", outline_m=[(0, -2), (6, -2), (6, 4), (0, 4)],
        conveyors=[
            {"conveyor_id": "belt_a", "kind": "belt", "path_m": [(0, 1), (5, 1)], "deck_heights_m": [1.0],
             "speed_mps": 1.0, "feeds": ["belt_b"]},
            {"conveyor_id": "belt_b", "kind": "belt", "path_m": [(5, 1), (5, 3.5)], "deck_heights_m": [1.0],
             "speed_mps": 2.0},
        ],
        read_points=[
            {"scan_point_id": "SP-TUN", "device_kind": "tunnel", "position_m": (1, 1, 1.5)},
            {"scan_point_id": "SP-PLC", "device_kind": "sorter_plc", "position_m": (5, 3, 1.5)},
            {"scan_point_id": "SP-BENCH", "device_kind": "handheld", "position_m": (2, 3, 1.0)},
        ],
        created_by="tester", created_at=now,
    )  # fmt: skip


@pytest.fixture
def world(site, now):
    w = World(EvidenceStore(), site, now)
    w.store.put(plan_for(site.site_id, now))
    w.store.put(ClockDomain(clock_domain_id="clkd_wcs", site_id=site.site_id, kind="wcs_plc", name="sorter WCS"))
    w.oid = w.store.put(ObjectInstance(object_instance_id="objinst_parcel", case_id=w.case.case_id,
                                       label="parcel CTX100200300400", identifiers=[WAYBILL], created_by="tester",
                                       created_at=now)).object_instance_id  # fmt: skip
    return w


def scan(w: World, station: str, kind: str, t_s: float, device_kind: str, domain: str | None = "clkd_wcs") -> str:
    sid = new_id("scan_event")
    w.store.put(ScanEvent(scan_event_id=sid, site_id=w.site.site_id, source_type="scan_simulated", import_batch="t",
                          identifiers=[WAYBILL], event_kind=kind, device_time_utc=w.t0 + timedelta(seconds=t_s),
                          clock_domain_id=domain, device_id=station, device_kind=device_kind, station_id=station))
    return sid


def segs(w: World) -> list[dict]:
    return build_journey(w.store, w.case.case_id)["objects"][0]["segments"]


def test_conveyor_route_and_belt_time(world, now):
    net = ConveyorNet(plan_for(world.site.site_id, now))
    r = net.route(net.snap((1, 1))[:2], net.snap((5, 3))[:2])
    assert [p.conveyor_id for p in r.pieces] == ["belt_a", "belt_b"]
    assert r.length_m == pytest.approx(6.0) and r.min_time_s == pytest.approx(4.0 + 1.0)
    assert net.route(net.snap((5, 3))[:2], net.snap((1, 1))[:2]) is None  # belts never run backwards
    assert r.path_m[0] == (1.0, 1.0) and r.path_m[-1] == (5.0, 3.0) and (5.0, 1.0) in r.path_m


def test_scans_on_belts_become_inferred_with_their_evidence(world):
    a = scan(world, "SP-TUN", "tunnel_read", 0, "tunnel")
    b = scan(world, "SP-PLC", "divert_confirmed", 5.2, "sorter_plc")
    j = build_journey(world.store, world.case.case_id)
    out = j["objects"][0]
    inf = [s for s in out["segments"] if s["kind"] == "inferred_along_conveyor"]
    assert len(inf) == 1 and inf[0]["evidence_ids"] == [a, b] and inf[0]["route"] == ["belt_a", "belt_b"]
    assert inf[0]["belt_time_s"] == 5.0 and inf[0]["timing"] == "consistent" and inf[0]["clock_note"] == "same device clock"
    assert [x["on_conveyor"] for x in out["scans"]] == ["belt_a", "belt_b"]
    assert out["last_confirmed"]["evidence_id"] == b
    assert j["needs"] and "SAM" in j["needs"][0]  # no-key: says what observed segments need


def test_records_faster_than_the_belt_are_a_gap_never_a_route(world):
    scan(world, "SP-TUN", "tunnel_read", 0, "tunnel")
    scan(world, "SP-PLC", "divert_confirmed", 3.0, "sorter_plc")  # belt needs 5 s
    (g,) = [s for s in segs(world) if s["start"] < s["end"] and s["kind"] != "observed"][:1]
    assert g["kind"] == "gap" and g["reason"] == "faster_than_belt" and "conflict" in g["note"]


def test_unsynchronized_different_clocks_are_not_timing_checked(world):
    scan(world, "SP-TUN", "tunnel_read", 0, "tunnel", domain=None)
    scan(world, "SP-PLC", "divert_confirmed", 3.0, "sorter_plc", domain=None)
    (inf,) = [s for s in segs(world) if s["kind"] == "inferred_along_conveyor"]
    assert inf["timing"] == "not_checkable"


def test_long_wait_is_flagged_and_handheld_scans_are_off_conveyance(world):
    scan(world, "SP-TUN", "tunnel_read", 0, "tunnel")
    scan(world, "SP-PLC", "divert_confirmed", 30.0, "sorter_plc")
    scan(world, "SP-BENCH", "relabeled", 40.0, "handheld", domain=None)
    s = segs(world)
    assert s[0]["kind"] == "inferred_along_conveyor" and s[0]["timing"] == "longer_than_belt"
    assert s[1]["kind"] == "gap" and s[1]["reason"] == "unobserved" and "not both on conveyance" in s[1]["note"]


def test_after_last_confirmed_runs_to_coverage_end_and_lists_recording_cameras(world):
    world.camera("cam_a")
    world.clip("cam_a", -5, 60)
    last = scan(world, "SP-TUN", "tunnel_read", 0, "tunnel")
    (g,) = segs(world)
    assert g["kind"] == "gap" and g["reason"] == "after_last_confirmed" and g["after"] == last
    assert g["covering_camera_ids"] == ["cam_a"] and g["end"].startswith("2026-10-27T14:01:00")


def test_observed_track_is_its_own_segment_and_scans_inside_it_are_beads(world):
    world.camera("cam_a")
    m = world.clip("cam_a", -5, 60)
    t = world.track("cam_a", m)
    world.link(world.oid, t, AssociationStatus.HUMAN_CONFIRMED)
    for k in range(5):
        world.obs(t, 10 + k * 0.5, xy=(1 + k * 0.5, 1))
    scan(world, "SP-TUN", "tunnel_read", 10.5, "tunnel")
    scan(world, "SP-PLC", "divert_confirmed", 17.0, "sorter_plc")  # 3 m from (3,1) on A + 2 m on B = 4 s
    s = segs(world)
    kinds = [x["kind"] for x in s]
    assert kinds == ["observed", "inferred_along_conveyor", "gap"]
    assert s[0]["evidence_ids"] and len(s[0]["points"]) == 5
    # camera clock is synchronized, the WCS clock is not: the route stands, its timing cannot be checked
    assert s[1]["from"].startswith("obs_") and s[1]["timing"] == "not_checkable"
    # solid never crosses a gap: every gap starts at or after the end of an observed segment
    assert all(g["start"] >= s[0]["end"] for g in s if g["kind"] == "gap")


@pytest.mark.skipif(not (REPO / "assets/hub/hub_spec.json").exists(), reason="hub spec not present")
def test_hub_plan_matches_the_sorter_timing_of_the_scan_log(now):
    """The hub plan converter: tunnel -> carrier assignment -> divert C04 in the belt time the scan log shows."""
    sys.path.insert(0, str(REPO / "frontend/scripts"))
    from seed_nokey import zone_polys
    from site_plan import site_plan

    spec = json.loads((REPO / "assets/hub/hub_spec.json").read_text(encoding="utf-8"))
    plan = SitePlan(plan_id="plan_hub", site_id="site_contoh_hub", created_by="t", created_at=now,
                    **site_plan(spec, zone_polys))  # fmt: skip
    net = ConveyorNet(plan)
    tun = net.snap(plan.read_point("SP-TUNNEL").position_for("tunnel_read"))
    car = net.snap(plan.read_point("SP-INDUCT").position_for("inducted"))
    div = net.snap(plan.read_point("SP-DIV-C04").position_for("divert_confirmed"))
    assert net.route(tun[:2], car[:2]).min_time_s == pytest.approx(4.7, abs=0.1)
    assert net.route(car[:2], div[:2]).min_time_s == pytest.approx(19.2, abs=0.1)


# --- I3: the missing moment -------------------------------------------------------------------------------------


def cam(w: World, camera_id: str, footprint) -> str:
    w.store.put(Camera(camera_id=camera_id, site_id=w.site.site_id, floor_id="floor_g", name=camera_id,
                       resolution_wh_px=(1280, 720), fov_polygon_m=footprint))  # fmt: skip
    w.cameras[camera_id] = w.store.get(Camera, camera_id)
    w.syncs[camera_id] = w.store.put(ClockSync(sync_id=f"sync_{camera_id}", camera_id=camera_id, offset_ms=0,
                                               uncertainty_ms=40, method="test fixture", created_at=w.t0))
    return camera_id


def fake_frames(camera_id: str, t_ms: float) -> dict:
    return {"camera_id": camera_id, "media_id": "media_fake", "frame_index": int(t_ms // 100) % 100000,
            "frame_url": "/fake"}  # fmt: skip


def test_missing_moment_predicts_the_next_camera_on_the_belt_and_types_negative_evidence(world):
    cam(world, "cam_b", [(4, 1.6), (6, 1.6), (6, 4), (4, 4)])  # watches belt B only
    cam(world, "cam_none", [(0, -2), (2, -2), (2, -0.5), (0, -0.5)])  # no footage at all
    m = world.clip("cam_b", -5, 60)
    scan(world, "SP-TUN", "tunnel_read", 0, "tunnel")
    mm = missing_moment(world.store, world.case.case_id, frame_lookup=fake_frames)["objects"][0]
    rows = {r["camera_id"]: r for r in mm["expected_next"]}
    b = rows["cam_b"]
    assert b["role"] == "belt_next" and b["result"] == "not_analysed" and "SAM" in b["needs"]
    # 4 m along belt A at 1 m/s, then 0.6 m up belt B at 2 m/s
    t_pred = datetime.fromisoformat(b["predicted_t"]) - world.t0
    assert t_pred.total_seconds() == pytest.approx(4.3, abs=0.15)  # floor grid is 0.25 m
    assert b["frame"] == fake_frames("cam_b", datetime.fromisoformat(b["predicted_t"]).timestamp() * 1000)
    assert rows["cam_none"]["result"] == "no_footage"

    # an unlinked track where the subject should be blocks a negative observation
    other = world.track("cam_b", m, label="box")
    world.obs(other, 4.3)
    b = {r["camera_id"]: r for r in missing_moment(world.store, world.case.case_id,
                                                   frame_lookup=fake_frames)["objects"][0]["expected_next"]}["cam_b"]
    assert b["result"] == "unresolved_candidates" and b["candidate_track_ids"] == [other]

    # analysed, but the only track is outside the window: absence of the subject is negative evidence
    world.store.invalidate(other, reason="test: wrong track", actor=HUMAN, now=world.t0)
    elsewhere = world.track("cam_b", m, label="box")
    world.obs(elsewhere, 30.0)
    b = {r["camera_id"]: r for r in missing_moment(world.store, world.case.case_id,
                                                   frame_lookup=fake_frames)["objects"][0]["expected_next"]}["cam_b"]
    neg = b["negative_observation"]
    assert b["result"] == "not_seen" and neg["kind"] == "negative_observation" and neg["frame_indices"]
    assert neg["evidence_ids"][0] == m and "not confirmed" in neg["basis"]


def test_after_a_divert_the_parcel_is_not_predicted_to_ride_on(world):
    cam(world, "cam_b", [(4, 1.6), (6, 1.6), (6, 4), (4, 4)])
    world.clip("cam_b", -5, 60)
    scan(world, "SP-TUN", "divert_confirmed", 0, "tunnel")  # discharged at the tunnel point: leaves the belt
    rows = missing_moment(world.store, world.case.case_id)["objects"][0]["expected_next"]
    assert all(r["role"] != "belt_next" for r in rows)


def test_missing_moment_without_any_evidence_says_so(world):
    out = missing_moment(world.store, world.case.case_id)["objects"][0]
    assert out["last_confirmed"] is None and out["expected_next"] == []


def test_hub_dashboard_aggregates_trail_ends_and_dependencies(world):
    from spoor.forensics.dashboard import hub_dashboard

    cam(world, "cam_b", [(4, 1.6), (6, 1.6), (6, 4), (4, 4)])
    world.clip("cam_b", -5, 60)
    scan(world, "SP-TUN", "tunnel_read", 0, "tunnel")
    scan(world, "SP-PLC", "divert_confirmed", 2.0, "sorter_plc")  # faster than the 5 s belt: a records conflict
    d = hub_dashboard(world.store, world.site.site_id, now=world.t0 + timedelta(hours=3))
    (row,) = d["cases"]
    assert row["status"] == "unknown" and row["open_hours"] == 3.0 and row["trail_end"]["event_kind"] == "divert_confirmed"
    assert d["kpis"] == {"open_cases": 1, "cases": 1, "located": 0, "found": 0, "median_hours_to_locate": None,
                         "median_cost_usd": 0, "total_cost_usd": 0}
    assert d["conflicts_by_read_point"] == [{"read_point": "SP-TUN", "count": 1}]
    assert {c["camera_id"] for c in d["cameras_relied_on"]} == {"cam_b"}


def test_exceptions_inbox_flags_an_overdue_next_scan_on_the_logs_own_clock(world):
    from spoor.forensics.exceptions import exceptions_inbox

    scan(world, "SP-TUN", "tunnel_read", 0, "tunnel")  # never loaded onto a carrier
    other = ParcelIdentifier(scheme="carrier_waybill", value="CTX999888777666")
    world.store.put(ScanEvent(scan_event_id=new_id("scan_event"), site_id=world.site.site_id, source_type="scan_simulated",
                              import_batch="t", identifiers=[other], event_kind="tunnel_read", device_id="SP-TUN",
                              device_time_utc=world.t0 + timedelta(seconds=100), device_kind="tunnel", station_id="SP-TUN"))
    box = exceptions_inbox(world.store, world.site.site_id)
    assert box["as_of"].startswith("2026-10-27T14:01:40") and box["basis"] == "as of the last imported scan"
    (row,) = box["stalled"]  # the parcel scanned at the log's end is still in progress
    assert row["waybill"] == WAYBILL.value and row["overdue_s"] == 70.0 and row["expected_next"] == "loaded onto a carrier"
    assert row["case_id"] == world.case.case_id and box["counts"] == {"parcels": 2, "stalled": 1, "in_progress": 1, "closed": 0}
