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
from spoor.contracts.parcels import ContainerType
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
    third = ParcelIdentifier(scheme="carrier_waybill", value="CTX111222333444")
    world.store.put(ScanEvent(scan_event_id=new_id("scan_event"), site_id=world.site.site_id, source_type="scan_simulated",
                              import_batch="t", identifiers=[third], event_kind="inducted", device_id="SP-INDUCT",
                              device_time_utc=world.t0 + timedelta(seconds=90), device_kind="sorter_plc"))  # fmt: skip
    other = ParcelIdentifier(scheme="carrier_waybill", value="CTX999888777666")
    world.store.put(ScanEvent(scan_event_id=new_id("scan_event"), site_id=world.site.site_id, source_type="scan_simulated",
                              import_batch="t", identifiers=[other], event_kind="tunnel_read", device_id="SP-TUN",
                              device_time_utc=world.t0 + timedelta(seconds=100), device_kind="tunnel", station_id="SP-TUN"))
    box = exceptions_inbox(world.store, world.site.site_id)
    assert box["as_of"].startswith("2026-10-27T14:01:40") and box["basis"] == "as of the last imported scan"
    assert box["counts"]["parcels"] == 3
    (row,) = box["stalled"]  # the parcel scanned at the log's end is still in progress
    assert row["waybill"] == WAYBILL.value and row["overdue_s"] == 70.0 and row["expected_next"] == "loaded onto a carrier"
    assert row["proof"]["event_kind"] == "inducted"  # the induct point kept working after the allowance
    assert row["case_id"] == world.case.case_id and box["counts"]["stalled"] == 1 and box["counts"]["in_progress"] == 2


@pytest.mark.skipif(not (REPO / "assets/hub/hub_spec.json").exists(), reason="hub spec not present")
def test_divert_c04_projects_inside_the_cameras_that_watch_it_with_current_poses(now):
    """F-024 #1: expected regions use the CURRENT mounting poses from the hub spec (CAM_07 / CAM_04 were re-aimed)."""
    sys.path.insert(0, str(REPO / "frontend/scripts"))
    from seed_nokey import zone_polys
    from site_plan import site_plan

    from spoor.forensics.viewgeom import expected_region, project

    spec = json.loads((REPO / "assets/hub/hub_spec.json").read_text(encoding="utf-8"))
    plan = SitePlan(plan_id="plan_hub", site_id="site_contoh_hub", created_by="t", created_at=now,
                    **site_plan(spec, zone_polys))  # fmt: skip
    div = plan.read_point("SP-DIV-C04").position_for("divert_confirmed")
    for cam_id in ("cam_CAM_07", "cam_CAM_10"):
        pose = next(c for c in plan.cameras if c.camera_id == cam_id)
        spec_cam = next(c for c in spec["cameras"] if f"cam_{c['id']}" == cam_id)
        assert list(pose.position_m[:2]) == spec_cam["position_m"] and pose.heading_deg == spec_cam["heading_deg"]
        uv = project(pose, (*div, 1.5))
        assert uv is not None, f"C04 divert is outside {cam_id}'s frame"
        r = expected_region(pose, (*div, 1.5))
        assert r and 0 <= r[0] < r[2] <= pose.resolution_wh_px[0] and 0 <= r[1] < r[3] <= pose.resolution_wh_px[1]


# --- I4: where it could be ----------------------------------------------------------------------------------------


def test_possible_area_collapses_into_the_store_when_its_only_exit_was_watched(site, now):
    """S2 in miniature: last confirmed inside a store; the band between store and hall is watched by an analysed camera
    that never saw the parcel -> the computed area stays in the store, and the store ranks first."""
    from spoor.forensics.possible import possible_locations

    w = World(EvidenceStore(), site, now)
    w.store.put(SitePlan(
        plan_id="plan_store", site_id=site.site_id, source="unit test fixture", outline_m=[(0, -2), (6, -2), (6, 4), (0, 4)],
        areas=[{"area_id": "store", "kind": "store", "name": "Exception store", "polygon_m": [(0, -2), (2, -2), (2, 4), (0, 4)],
                "zone_id": "zone_shelf_a", "walkable": True},
               {"area_id": "hall", "kind": "zone", "name": "Hall", "polygon_m": [(3, -2), (6, -2), (6, 4), (3, 4)],
                "zone_id": "zone_hall", "walkable": True}],
        read_points=[{"scan_point_id": "SP-STORE", "device_kind": "handheld", "position_m": (1, 1, 1.0)}],
        created_by="tester", created_at=now))  # fmt: skip
    w.store.put(ObjectInstance(object_instance_id="objinst_parcel", case_id=w.case.case_id, label="parcel",
                               identifiers=[WAYBILL], created_by="tester", created_at=now))  # fmt: skip
    cam(w, "cam_door", [(2, -2), (3, -2), (3, 4), (2, 4)])
    m = w.clip("cam_door", -5, 60)
    scan(w, "SP-STORE", "relabeled", 0, "handheld", domain=None)

    before = possible_locations(w.store, w.case.case_id)["objects"][0]
    assert before["note"] and "SAM" in before["note"]  # nothing analysed: no area removed
    assert before["steps"][-1]["area_m2"] > 20  # the hall is reachable too

    other = w.track("cam_door", m, label="box")  # analysed: something else tracked, before the window
    w.obs(other, -3.0)
    after = possible_locations(w.store, w.case.case_id)["objects"][0]
    last = after["steps"][-1]
    assert last["removed_by_cameras"] == ["cam_door"] and last["area_m2"] <= 12.5
    assert after["places"][0]["area_id"] == "store" and after["places"][0]["possible_share"] > 0.85  # 0.25 m grid edge
    hall = next(p for p in after["places"] if p["area_id"] == "hall")
    assert hall["possible_share"] == 0 and after["note"] is None


def test_exceptions_inbox_clock_offset_replays_a_later_moment(world):
    from spoor.forensics.exceptions import exceptions_inbox

    world.store.put(ScanEvent(scan_event_id=new_id("scan_event"), site_id=world.site.site_id, source_type="scan_simulated",
                              import_batch="t", identifiers=[WAYBILL], event_kind="divert_confirmed", device_id="SP-DIV-C04",
                              station_id="SP-DIV-C04", device_kind="sorter_plc", device_time_utc=world.t0))  # fmt: skip
    assert exceptions_inbox(world.store, world.site.site_id)["counts"]["stalled"] == 0  # at the log's end: in time
    later = exceptions_inbox(world.store, world.site.site_id, after_log_min=30)
    # the log just ends: no proof the bagging point kept working, so nobody can judge (no false alarm)
    assert later["stalled"] == [] and later["counts"]["cannot_judge"] == 1
    other = ParcelIdentifier(scheme="carrier_waybill", value="CTX555444333222")
    world.store.put(ScanEvent(scan_event_id=new_id("scan_event"), site_id=world.site.site_id, source_type="scan_simulated",
                              import_batch="t", identifiers=[other], event_kind="container_closed", device_id="SP-BAG-C04",
                              station_id="SP-BAG-C04", device_kind="handheld",
                              container=ParcelIdentifier(scheme="container", value="BAG-1"),
                              device_time_utc=world.t0 + timedelta(minutes=25)))  # fmt: skip
    proof = exceptions_inbox(world.store, world.site.site_id)  # the log now runs 25 min and C04 bagging kept working
    (row,) = proof["stalled"]
    assert row["waybill"] == WAYBILL.value and row["proof"]["station"] == "SP-BAG-C04" and row["overdue_s"] == 300.0


# --- I6: records vs video -----------------------------------------------------------------------------------------


def test_records_say_it_left_on_the_truck_but_a_camera_confirms_it_inside(world):
    """S2 in miniature: parcel inside cage RC-864; the cage's loading scan at D08 says it left; a confirmed track shows
    the parcel in the hall afterwards -> a typed departure conflict with the divergence time and both evidence ids."""
    from spoor.contracts import ContainerMembership
    from spoor.forensics.conflicts import records_vs_video

    cage = ParcelIdentifier(scheme="container", value="RC-864")
    world.store.put(ContainerMembership(membership_id="cmem_rc864", version=1, child_key=WAYBILL.key,
                                        parent_key=cage.key, valid_from=world.t0 + timedelta(seconds=1),
                                        basis="scan", status="active", created_at=world.t0))  # fmt: skip
    load = new_id("scan_event")
    world.store.put(ScanEvent(scan_event_id=load, site_id=world.site.site_id, source_type="scan_simulated", import_batch="t",
                              identifiers=[cage], container=cage, event_kind="container_loaded", device_id="SP-LOAD-D08",
                              parent_container=ParcelIdentifier(scheme="container", value="TRAILER-D08"),
                              station_id="SP-LOAD-D08", device_kind="handheld", read_point_zone_id="zone_shelf_a",
                              device_time_utc=world.t0 + timedelta(seconds=5)))  # fmt: skip
    none_yet = records_vs_video(world.store, world.case.case_id)["objects"][0]
    assert none_yet["conflicts"] == [] and "not agreement" in none_yet["note"]

    world.camera("cam_a")
    m = world.clip("cam_a", -5, 60)
    t = world.track("cam_a", m)
    world.link(world.oid, t, AssociationStatus.HUMAN_CONFIRMED)
    obs = world.obs(t, 20.0, xy=(5, -1), zone="zone_hall")
    out = records_vs_video(world.store, world.case.case_id)["objects"][0]
    (c,) = [x for x in out["conflicts"] if x["kind"] == "departure"]
    assert c["divergence_t"].startswith("2026-10-27T14:00:20") and c["observation"]["observation_id"] == obs
    assert load in c["claim"]["evidence_ids"] and "left the hub" in c["statement"] and out["note"] is None
    assert any(r.get("claim") == "departure" for r in out["records"]) and out["video"]


# --- I7: floor search ------------------------------------------------------------------------------------------------


def test_search_outcomes_revise_the_possible_area_and_the_status(world, now):
    from spoor.contracts import SearchOutcome, SearchPlace, SearchTask
    from spoor.forensics.possible import possible_locations
    from spoor.forensics.search import search_view

    world.store.put(SitePlan(
        plan_id="plan_two", site_id=world.site.site_id, source="unit test fixture", outline_m=[(0, -2), (6, -2), (6, 4), (0, 4)],
        areas=[{"area_id": "store", "kind": "store", "name": "Store", "polygon_m": [(0, -2), (2, -2), (2, 4), (0, 4)], "walkable": True},
               {"area_id": "hall", "kind": "zone", "name": "Hall", "polygon_m": [(3, -2), (6, -2), (6, 4), (3, 4)], "walkable": True}],
        read_points=[{"scan_point_id": "SP-STORE", "device_kind": "handheld", "position_m": (2.5, 1, 1.0)}],
        created_by="tester", created_at=now))  # fmt: skip
    world.camera("cam_a")
    world.clip("cam_a", -5, 60)
    scan(world, "SP-STORE", "relabeled", 0, "handheld", domain=None)
    task = world.store.put(SearchTask(search_task_id="srch_t1", case_id=world.case.case_id, created_by="ivy", created_at=now,
                                      places=[SearchPlace(area_id="store", name="Store", centroid_xy=(1, 1)),
                                              SearchPlace(area_id="hall", name="Hall", centroid_xy=(4.5, 1))]))  # fmt: skip
    assert search_view(world.store, world.case.case_id)["status"] == "searching"
    world.store.put(SearchOutcome(search_outcome_id="sout_1", search_task_id=task.search_task_id, case_id=world.case.case_id,
                                  area_id="hall", outcome="not_found", recorded_by="ivy", recorded_at=now,
                                  content_sha256="a" * 64))  # fmt: skip
    out = possible_locations(world.store, world.case.case_id)["objects"][0]
    hall = next(p for p in out["places"] if p["area_id"] == "hall")
    assert hall["possible_share"] == 0 and hall["evidence_against"][0].startswith("searched by ivy")
    assert out["steps"][-1]["searched_not_here"] == ["hall"]
    world.store.put(SearchOutcome(search_outcome_id="sout_2", search_task_id=task.search_task_id, case_id=world.case.case_id,
                                  area_id="store", outcome="found", recorded_by="ivy", recorded_at=now,
                                  content_sha256="b" * 64))  # fmt: skip
    view = search_view(world.store, world.case.case_id)
    assert view["status"] == "found" and view["found"]["name"] == "Store" and view["not_here"] == ["hall"]
    assert possible_locations(world.store, world.case.case_id)["objects"][0]["places"][0]["area_id"] == "store"


# --- I8: evidence reel ----------------------------------------------------------------------------------------------


@pytest.mark.skipif(__import__("shutil").which("ffmpeg") is None, reason="ffmpeg not installed")
def test_reel_is_built_in_time_order_with_a_card_per_piece_of_evidence(tmp_path):
    import cv2
    import numpy as np

    from spoor.forensics.reel import build_reel

    png = cv2.imencode(".png", np.full((540, 960, 3), 120, np.uint8))[1].tobytes()
    jo = {"scans": [{"scan_event_id": "scan_a", "t": "2026-10-27T14:00:00+00:00", "event_kind": "tunnel_read", "raw_code": "tunnel_read",
                     "station_id": "SP-TUN", "_watchers": ["cam_a"]}],
          "segments": [{"kind": "gap", "start": "2026-10-27T14:00:00+00:00", "end": "2026-10-27T14:00:20+00:00"}]}
    ref = {"camera_id": "cam_a", "media_id": "media_x", "frame_index": 3, "sha256": "f" * 64}
    man = build_reel(jo, frame_get=lambda m, i: png, frame_lookup=lambda c, t: ref, crop_of=lambda o: None,
                     out_dir=tmp_path, reel_id="reel_test", case_label="unit test")  # fmt: skip
    assert man["cards"] == 3 and man["sources"] == [{"kind": "context_frame", "media_id": "media_x", "frame_index": 3,
                                                      "sha256": "f" * 64, "scan_event_id": "scan_a"}]
    mp4 = tmp_path / "reel_test.mp4"
    assert mp4.exists() and mp4.stat().st_size > 1000 and (tmp_path / "reel_test.json").exists()


# --- J2: lead investigator ------------------------------------------------------------------------------------------


def test_lead_plan_keeps_only_steps_that_cite_real_evidence_and_candidate_cameras(world, now):
    from types import SimpleNamespace

    from spoor.forensics.lead import InvestigationPlan, latest_plan_step, plan_investigation
    from spoor.store import CostEntry

    cam(world, "cam_b", [(4, 1.6), (6, 1.6), (6, 4), (4, 4)])
    world.clip("cam_b", -5, 60)
    sid = scan(world, "SP-TUN", "tunnel_read", 0, "tunnel")
    at = lambda s: (world.t0 + timedelta(seconds=s)).isoformat()
    plan = InvestigationPlan(summary="check belt B", unknowns=["where it went after the tunnel"], steps=[
        {"camera_id": "cam_b", "window_start": at(0), "window_end": at(20), "what_to_check": "parcel on belt B",
         "why": "next on the belt", "evidence_ids": [sid]},
        {"camera_id": "cam_zz", "window_start": at(0), "window_end": at(20), "what_to_check": "x", "why": "y", "evidence_ids": [sid]},
        {"camera_id": "cam_b", "window_start": at(0), "window_end": at(20), "what_to_check": "x", "why": "y",
         "evidence_ids": ["scan_made_up"]},
        {"camera_id": "cam_b", "window_start": at(3600), "window_end": at(3700), "what_to_check": "x", "why": "y",
         "evidence_ids": [sid]},  # an hour after the footage ends
        {"camera_id": "cam_b", "window_start": "a", "window_end": "b", "what_to_check": "x", "why": "y", "evidence_ids": [sid]},
    ])  # fmt: skip
    fake = SimpleNamespace(complete=lambda **kw: SimpleNamespace(data=plan, model="muse-wonder-1.0", provider="meta_model_api",
                                                                response_id="resp_1", input_tokens=2000, output_tokens=3000,
                                                                latency_s=20.0))  # fmt: skip
    out = plan_investigation(world.store, world.case.case_id, fake, now=now)
    assert [s["camera_id"] for s in out["steps"]] == ["cam_b"] and len(out["rejected"]) == 4
    assert {r["reason"] for r in out["rejected"]} == {"camera has no footage on this site",
                                                      "cites unknown evidence ['scan_made_up']",
                                                      "window outside the camera's footage",
                                                      "window is not an ISO time with an offset"}
    assert out["usd_estimate"] == 0.068 and world.store.find(CostEntry, case_id=world.case.case_id)[0].model == "muse-wonder-1.0"
    assert latest_plan_step(world.store, world.case.case_id)["summary"] == "check belt B"


def test_lead_replans_once_with_the_reasons_when_no_step_survives(world, now):
    from types import SimpleNamespace

    from spoor.forensics.lead import InvestigationPlan, plan_investigation

    cam(world, "cam_b", [(4, 1.6), (6, 1.6), (6, 4), (4, 4)])
    world.clip("cam_b", -5, 60)
    sid = scan(world, "SP-TUN", "tunnel_read", 0, "tunnel")
    at = lambda s: (world.t0 + timedelta(seconds=s)).isoformat()
    bad = InvestigationPlan(summary="x", unknowns=[], steps=[{"camera_id": "CAM_001", "window_start": at(0), "window_end": at(9),
                                                              "what_to_check": "x", "why": "y", "evidence_ids": [sid]}])
    good = InvestigationPlan(summary="y", unknowns=[], steps=[{"camera_id": "cam_b", "window_start": at(0), "window_end": at(9),
                                                               "what_to_check": "parcel on belt B", "why": "next", "evidence_ids": [sid]}])
    asked = []

    def complete(**kw):
        asked.append(kw["content"])
        return SimpleNamespace(data=bad if len(asked) == 1 else good, model="muse-wonder-1.0", provider="meta_model_api",
                               response_id=f"resp_{len(asked)}", input_tokens=1000, output_tokens=1000, latency_s=1.0)

    out = plan_investigation(world.store, world.case.case_id, SimpleNamespace(complete=complete), now=now)
    assert out["replanned"] and [s["camera_id"] for s in out["steps"]] == ["cam_b"] and len(asked) == 2
    assert "CAM_001: camera has no footage on this site" in asked[1]


def test_handshake_plan_rules_and_honest_gaps(world, now):
    """Each scan becomes one row per camera that sees its scan point: tunnel = the first carton out just after the
    read, sorter = the point at the confirm, handheld = the work area; no camera / no footage are said, never faked."""
    from spoor.forensics.handshake import TUNNEL_EXIT_S, plan_handshakes, sam_frames

    w = world
    w.camera("cam_a")
    w.clip("cam_a", 0, 20)
    plan = SitePlan.model_validate(plan_for(w.site.site_id, now).model_dump() | {"read_points": [
        {"scan_point_id": "SP-TUN", "device_kind": "tunnel", "position_m": (1, 1, 1.5), "visible_by": ["cam_a"]},
        {"scan_point_id": "SP-PLC", "device_kind": "sorter_plc", "position_m": (5, 3, 1.5), "visible_by": ["cam_a"]},
        {"scan_point_id": "SP-BENCH", "device_kind": "handheld", "position_m": (2, 3, 1.0)}]})
    scan(w, "SP-TUN", "tunnel_read", 2.0, "tunnel")
    scan(w, "SP-PLC", "divert_confirmed", 6.0, "sorter_plc")
    scan(w, "SP-BENCH", "arrived_facility", 8.0, "handheld")
    scan(w, "SP-PLC", "divert_confirmed", 40.0, "sorter_plc")  # after the clip ends
    rows = {(r.scan_point_id, r.reason): r for r in plan_handshakes(w.store, plan, w.store.find(ScanEvent))}
    tun = rows[("SP-TUN", "")]
    assert tun.rule == "tunnel_exit" and tun.camera_id == "cam_a" and tun.waybill == WAYBILL.value
    assert (tun.at - (w.t0 + timedelta(seconds=2.0))).total_seconds() == pytest.approx(TUNNEL_EXIT_S)
    assert rows[("SP-PLC", "")].rule == "point"
    assert ("SP-BENCH", "not_on_camera") in rows and ("SP-PLC", "no_footage") in rows
    assert sam_frames(list(rows.values())) == 2 * 56  # the two runnable ones, 5.5 s at 10 fps each


def test_left_alert_watches_open_containers_only(world, now):
    """A parcel whose last scan put it in a cage is watched on the cameras that see that point; one whose last scan put
    it in a bag is not (a carton in a sack can't be seen leaving as a carton), and a later scan clears a parcel."""
    from spoor.forensics.left_alert import plan_watches

    w = world
    w.camera("cam_a")
    w.clip("cam_a", 0, 30)
    plan = SitePlan.model_validate(plan_for(w.site.site_id, now).model_dump() | {"read_points": [
        {"scan_point_id": "SP-CAGE", "device_kind": "handheld", "position_m": (2, 3, 1.0), "work_area_m": [[(1.5, 2.5), (2.5, 2.5), (2.5, 3.5), (1.5, 3.5)]],
         "visible_by": ["cam_a"]},
        {"scan_point_id": "SP-BAG", "device_kind": "handheld", "position_m": (4, 3, 1.0), "work_area_m": [[(3.5, 2.5), (4.5, 2.5), (4.5, 3.5), (3.5, 3.5)]],
         "visible_by": ["cam_a"]}]})

    def into(station, kind, t_s, wb, ctype, cid):
        w.store.put(ScanEvent(scan_event_id=new_id("scan_event"), site_id=w.site.site_id, source_type="scan_simulated",
                              import_batch="t", identifiers=[ParcelIdentifier(scheme="carrier_waybill", value=wb)],
                              event_kind=kind, device_time_utc=w.t0 + timedelta(seconds=t_s), clock_domain_id="clkd_wcs",
                              device_id=station, device_kind="handheld", station_id=station,
                              container=ParcelIdentifier(scheme="container", value=cid), container_type=ctype))

    into("SP-CAGE", "container_add", 2.0, "CTX100000000001", "cage", "RC-1")
    into("SP-CAGE", "container_add", 3.0, "CTX100000000002", "cage", "RC-1")
    into("SP-BAG", "container_add", 4.0, "CTX100000000003", "bag", "BG-1")
    w.store.put(ScanEvent(scan_event_id=new_id("scan_event"), site_id=w.site.site_id, source_type="scan_simulated",
                          import_batch="t", identifiers=[ParcelIdentifier(scheme="carrier_waybill", value="CTX100000000002")],
                          event_kind="arrived_facility", device_time_utc=w.t0 + timedelta(seconds=9),
                          clock_domain_id="clkd_wcs", device_id="SP-BENCH", device_kind="handheld", station_id="SP-BENCH"))
    ws = plan_watches(w.store, plan, w.store.find(ScanEvent))
    assert [(x.scan_point_id, x.camera_id) for x in ws] == [("SP-CAGE", "cam_a")]
    assert [p["waybill"] for p in ws[0].parcels] == ["CTX100000000001"]


def test_handshake_needs_a_fitted_clock(world, now):
    """A camera whose clock is only the uploader's declared start (+-5 s) can't say which carton was at the point at
    the scan's second: the row says so instead of outlining whichever carton is there."""
    from spoor.forensics.handshake import plan_handshakes

    w = world
    w.camera("cam_a", sync_uncertainty_ms=5000)
    w.clip("cam_a", 0, 20)
    plan = SitePlan.model_validate(plan_for(w.site.site_id, now).model_dump() | {"read_points": [
        {"scan_point_id": "SP-PLC", "device_kind": "sorter_plc", "position_m": (5, 3, 1.5), "visible_by": ["cam_a"]}]})
    scan(w, "SP-PLC", "divert_confirmed", 6.0, "sorter_plc")
    assert [r.reason for r in plan_handshakes(w.store, plan, w.store.find(ScanEvent))] == ["clock_not_fitted"]


def test_planners_read_the_log_after_its_corrections(world, now):
    """A container scan corrected as a bag (incorrect_data) stands in place of the original typed as a cage: the live
    alert stops watching it, and the handshake plans one row for it, not two."""
    from spoor.forensics.handshake import plan_handshakes
    from spoor.forensics.left_alert import plan_watches

    w = world
    w.camera("cam_a")
    w.clip("cam_a", 0, 30)
    plan = SitePlan.model_validate(plan_for(w.site.site_id, now).model_dump() | {"read_points": [
        {"scan_point_id": "SP-BAG", "device_kind": "handheld", "position_m": (4, 3, 1.0),
         "work_area_m": [[(3.5, 2.5), (4.5, 2.5), (4.5, 3.5), (3.5, 3.5)]], "visible_by": ["cam_a"]}]})
    first = ScanEvent(scan_event_id=new_id("scan_event"), site_id=w.site.site_id, source_type="scan_simulated",
                      import_batch="t", identifiers=[WAYBILL], event_kind="container_add",
                      device_time_utc=w.t0 + timedelta(seconds=4), clock_domain_id="clkd_wcs", device_id="SP-BAG",
                      device_kind="handheld", station_id="SP-BAG", container_type="cage",
                      container=ParcelIdentifier(scheme="container", value="BAG-1"))
    w.store.put(first)
    assert len(plan_watches(w.store, plan, w.store.find(ScanEvent))) == 1
    w.store.put(first.model_copy(update={"scan_event_id": new_id("scan_event"), "container_type": ContainerType.BAG,
                                         "corrects_scan_event_id": first.scan_event_id,
                                         "correction_reason": "incorrect_data"}))
    assert plan_watches(w.store, plan, w.store.find(ScanEvent)) == []
    assert len(plan_handshakes(w.store, plan, w.store.find(ScanEvent))) == 1


def test_left_alert_candidates_are_parcels_and_know_when_their_cage_left(world, now):
    """Candidates are parcels: a bag scanned into a cage is not a carton. A parcel whose cage was then loaded with the
    cage's own read (RFID at a dock) is accounted for through the cage from that read on, so the watch carries when."""
    from spoor.forensics.left_alert import plan_watches

    w = world
    w.camera("cam_a")
    w.clip("cam_a", 0, 30)
    plan = SitePlan.model_validate(plan_for(w.site.site_id, now).model_dump() | {"read_points": [
        {"scan_point_id": "SP-CAGE", "device_kind": "handheld", "position_m": (2, 3, 1.0),
         "work_area_m": [[(1.5, 2.5), (2.5, 2.5), (2.5, 3.5), (1.5, 3.5)]], "visible_by": ["cam_a"]}]})

    def put(ident, kind, t_s, cid, **kw):
        w.store.put(ScanEvent(scan_event_id=new_id("scan_event"), site_id=w.site.site_id, source_type="scan_simulated",
                              import_batch="t", identifiers=ident, event_kind=kind,
                              device_time_utc=w.t0 + timedelta(seconds=t_s), clock_domain_id="clkd_wcs",
                              device_id=kw.pop("device", "SP-CAGE"), device_kind=kw.pop("dev_kind", "handheld"),
                              station_id="SP-CAGE", container=ParcelIdentifier(scheme="container", value=cid),
                              container_type="cage", **kw))

    put([ParcelIdentifier(scheme="carrier_waybill", value="CTX100000000001")], "container_add", 2.0, "RC-1")
    put([ParcelIdentifier(scheme="container", value="BAG-C01-1")], "container_add", 3.0, "RC-1")
    put([ParcelIdentifier(scheme="carrier_waybill", value="CTX100000000002")], "container_add", 4.0, "RC-2")
    put([], "container_loaded", 8.0, "RC-2", device="SP-RFID", dev_kind="rfid_portal",
        parent_container=ParcelIdentifier(scheme="container", value="TRUCK-D08"))
    ws = plan_watches(w.store, plan, w.store.find(ScanEvent))
    got = {p["waybill"]: p["container_left"] for p in ws[0].parcels}
    assert set(got) == {"CTX100000000001", "CTX100000000002"}  # (not the bag)
    assert got["CTX100000000001"] is None and got["CTX100000000002"] == w.t0 + timedelta(seconds=8)


def test_unfitted_handheld_point_is_looked_at_only_when_no_other_scan_shares_its_window(world, now):
    """On a +-5 s clock a handheld scan with another scan at the same point within 10 s can't be told apart on camera;
    an isolated one is looked at over the whole window."""
    from spoor.forensics.handshake import plan_handshakes

    w = world
    w.camera("cam_a", sync_uncertainty_ms=5000)
    w.clip("cam_a", 0, 60)
    plan = SitePlan.model_validate(plan_for(w.site.site_id, now).model_dump() | {"read_points": [
        {"scan_point_id": "SP-BENCH", "device_kind": "handheld", "position_m": (2, 3, 1.0),
         "work_area_m": [[(1.5, 2.5), (2.5, 2.5), (2.5, 3.5), (1.5, 3.5)]], "visible_by": ["cam_a"]}]})
    scan(w, "SP-BENCH", "arrived_facility", 10.0, "handheld")
    scan(w, "SP-BENCH", "arrived_facility", 14.0, "handheld")
    scan(w, "SP-BENCH", "arrived_facility", 40.0, "handheld")
    rows = sorted(plan_handshakes(w.store, plan, w.store.find(ScanEvent)), key=lambda r: r.at)
    assert [r.reason for r in rows] == ["cant_tell", "cant_tell", ""]
    assert rows[0].note == "Two cartons scanned 4.0 s apart here"


def test_never_followed_parcel_is_located_by_its_last_scan_and_confirmed_only_by_a_labelled_handshake(world, now):
    """Not seen on camera: the answer is its last scan record ("located by scan"). A handshake that met it there counts
    as "confirmed on camera" only when it carries the label (an unlabelled outline could be a neighbour)."""
    from spoor.agents import ToolContext
    from spoor.agents.orchestrator import _last_scan
    from spoor.contracts import EvidenceScope
    from spoor.store import ScanHandshake
    from spoor.verification import Verifier

    w = world
    scan(w, "SP-TUN", "tunnel_read", 1.0, "tunnel")
    sid = scan(w, "SP-PLC", "divert_confirmed", 6.0, "sorter_plc")
    ctx = ToolContext(store=w.store, site=w.site, case=w.case, verifier=Verifier(w.store, w.site), scope=EvidenceScope(),
                      now=lambda: now)  # fmt: skip
    obj = w.store.get(ObjectInstance, w.oid)
    first = _last_scan(ctx, obj)
    assert first["scan_point_id"] == "SP-PLC" and first["located_by"] == "scan" and first["camera"] is None

    def met(hid, labelled):
        w.store.put(ScanHandshake(handshake_id=hid, site_id=w.site.site_id, scan_event_id=sid, waybill=WAYBILL.value,
                                  event_kind="divert_confirmed", scan_point_id="SP-PLC", camera_id="cam_a",
                                  media_id="media_x", at_utc=w.t0 + timedelta(seconds=6), rule="point",
                                  outcome="outlined", labelled=labelled, at=now))  # fmt: skip

    met("hs_unlabelled", False)
    assert _last_scan(ctx, obj)["located_by"] == "scan"
    met("hs_labelled", True)
    assert _last_scan(ctx, obj)["located_by"] == "camera" and _last_scan(ctx, obj)["camera"] == "cam_a"
