"""Parcel pivot: scan evidence, identity, containers, facility visits and clock fitting.

Scan logs here are hand-written fixtures (labelled scan_simulated), never presented as real hub data."""

import json
import random
from datetime import UTC, datetime, timedelta

import pytest
from builders import World
from pydantic import ValidationError

from spoor.contracts import (
    AssociationStatus,
    ClockDomain,
    ClockSync,
    EvidenceLabel,
    FrameRef,
    ObjectInstance,
    ParcelIdentifier,
    ScanEvent,
    SourceType,
    gs1_check_digit,
    new_id,
)
from spoor.scans import ScanImportError, ingest_scans, parse_scan_jsonl
from spoor.spatial import AnchorPair, ClockFitError, fit_clock, normalize, sync_from_fit
from spoor.store import EvidenceStore
from spoor.store.parcels import container_chain, facility_visit, graded_last_seen, resolve_identity, scans_for

T0 = datetime(2026, 10, 27, 14, 0, tzinfo=UTC)
WB = "carrier_waybill:MY88213"


def at(s: float) -> str:
    return (T0 + timedelta(seconds=s)).isoformat()


def wb(v: str = "MY88213") -> dict:
    return {"scheme": "carrier_waybill", "value": v}


def bag(v: str) -> dict:
    return {"scheme": "container", "value": v}


@pytest.fixture
def hub(room):
    store = EvidenceStore()
    store.put(room)
    store.put(room.model_copy(update={"site_id": "site_hub_b", "name": "Hub B"}))
    for d in ("clkd_wcs", "clkd_handheld"):
        store.put(ClockDomain(clock_domain_id=d, site_id="site_test", kind="wcs_plc" if d == "clkd_wcs"
                              else "handheld_fleet", name=d))  # fmt: skip
    return store


def load(store, rows, site="site_test", source="simulated", now=None):
    text = "\n".join(json.dumps(r) for r in rows)
    scans = parse_scan_jsonl(text, site_id=site, import_batch="fixture", source=source, now=now or T0)
    return ingest_scans(store, scans, now=now or T0)


def tunnel(s, ident=None, **kw):
    return {"identifiers": [ident or wb()], "event_kind": "tunnel_read", "device_time_utc": at(s),
            "device_id": "tunnel_1", "device_kind": "tunnel", "clock_domain_id": "clkd_wcs", **kw}


def bag_add(s, bag_id, ident=None):
    return {"identifiers": [ident or wb()], "event_kind": "container_add", "container": bag(bag_id),
            "container_type": "bag", "device_time_utc": at(s), "device_id": "hh_07", "device_kind": "handheld",
            "operator_ref": "op_7f3a91"}


def load_bag(s, bag_id, trailer="TRL-22"):
    return {"event_kind": "container_loaded", "container": bag(bag_id), "parent_container": bag(trailer),
            "device_time_utc": at(s), "device_id": "hh_09", "device_kind": "handheld"}


# --- identifiers & validation ------------------------------------------------------------------------------------


def test_identifier_check_digits():
    assert ParcelIdentifier(scheme="s10", value="ee123456785my").check_digit_valid  # UPU's own example, normalized
    bad = ParcelIdentifier(scheme="s10", value="EE123456784MY")
    assert bad.check_digit_valid is False and not bad.usable_for_identity  # OCR misread: kept, never binds identity
    body = "06141411234567890"
    assert ParcelIdentifier(scheme="sscc", value=body + str(gs1_check_digit(body))).check_digit_valid
    assert ParcelIdentifier(scheme="carrier_waybill", value="X").check_digit_valid is None


@pytest.mark.parametrize("patch, msg", [
    ({"identifiers": []}, "at least one identifier"),
    ({"read_outcome": "no_read"}, "no-read carries no identifier"),
    ({"operator_ref": "Ahmad bin Ali"}, "pseudonymous"),
    ({"event_kind": "container_add"}, "needs a container"),
    ({"corrects_scan_event_id": "scan_x"}, "correction needs both"),
])  # fmt: skip
def test_scan_event_validation(patch, msg):
    base = {"scan_event_id": "scan_1", "site_id": "site_test", "source_type": "scan_simulated",
            "import_batch": "b", "identifiers": [wb()], "event_kind": "tunnel_read", "device_time_utc": T0,
            "device_id": "tunnel_1", "device_kind": "tunnel"}  # fmt: skip
    with pytest.raises(ValidationError, match=msg):
        ScanEvent(**(base | patch))
    with pytest.raises(ValidationError, match="scan_real or scan_simulated"):
        ScanEvent(**(base | {"source_type": "sensor_real"}))


def test_import_labels_source_and_ignores_overrides(hub):
    rows = [tunnel(0) | {"site_id": "site_other", "source_type": "scan_real", "scan_event_id": "scan_forged"}]
    load(hub, rows)
    (s,) = hub.find(ScanEvent)
    assert s.site_id == "site_test" and s.source_type == SourceType.SCAN_SIMULATED and s.scan_event_id != "scan_forged"
    assert load(hub, rows).skipped_exact_duplicates == 1  # re-importing the same log is harmless
    with pytest.raises(ScanImportError, match="line 1"):
        parse_scan_jsonl("{not json", site_id="site_test", import_batch="b", source="real")


# --- facility visits ------------------------------------------------------------------------------------------------


def test_control_path_closes_by_inheritance_and_chain_resolves(hub):
    load(hub, [tunnel(0), bag_add(60, "BAG-0042"), load_bag(900, "BAG-0042")])
    v = facility_visit(hub, "site_test", {WB}, now=T0 + timedelta(hours=8))
    assert v.status == "closed_inherited" and v.label == EvidenceLabel.ESTIMATED
    chain = container_chain(hub, WB, T0 + timedelta(seconds=1000))
    assert [m.parent_key for m in chain] == ["container:BAG-0042", "container:TRL-22"]


def test_scanned_in_never_out_is_overdue_only_after_sla(hub):
    load(hub, [tunnel(0)])
    assert facility_visit(hub, "site_test", {WB}, now=T0 + timedelta(hours=1)).status == "open_within_sla"
    v = facility_visit(hub, "site_test", {WB}, now=T0 + timedelta(hours=8))
    assert v.status == "open_overdue" and v.label == EvidenceLabel.UNKNOWN


def test_relabel_is_not_a_disappearance(hub):
    new = wb("MY99001")
    load(hub, [tunnel(0), {"identifiers": [new, wb()], "event_kind": "relabeled", "device_time_utc": at(300),
                           "device_id": "bench_2", "device_kind": "handheld"},
               {"identifiers": [new], "event_kind": "departed_facility", "device_time_utc": at(2000),
                "device_id": "dock_3", "device_kind": "handheld"}])  # fmt: skip
    assert resolve_identity(hub, {WB}) == {WB, "carrier_waybill:MY99001"}
    v = facility_visit(hub, "site_test", {WB}, now=T0 + timedelta(hours=8))
    assert v.status == "closed_direct" and v.label == EvidenceLabel.OBSERVED


def test_missort_is_flagged(hub):
    load(hub, [tunnel(0, sort_destination_assigned="CHUTE-12", sort_destination_actual="CHUTE-14")])
    v = facility_visit(hub, "site_test", {WB}, now=T0 + timedelta(hours=1))
    assert any("missort" in n and "CHUTE-12" in n for n in v.notes)


def test_bag_emptied_elsewhere_without_parcel_contradicts_inheritance(hub):
    load(hub, [tunnel(0), bag_add(60, "BAG-0042"), bag_add(61, "BAG-0042", wb("MY11111")), load_bag(900, "BAG-0042")])
    load(hub, [{"identifiers": [wb("MY11111")], "event_kind": "container_remove", "container": bag("BAG-0042"),
                "device_time_utc": at(20000), "device_id": "hh_b1", "device_kind": "handheld"}], site="site_hub_b")
    v = facility_visit(hub, "site_test", {WB}, now=T0 + timedelta(hours=8))
    assert v.status == "open_overdue" and any("without this parcel" in n for n in v.notes)


def test_downstream_scan_closes_visit(hub):
    load(hub, [tunnel(0)])
    load(hub, [tunnel(30000) | {"clock_domain_id": None}], site="site_hub_b")
    assert facility_visit(hub, "site_test", {WB}, now=T0 + timedelta(hours=12)).status == "closed_downstream"


def test_corrected_departure_no_longer_closes(hub):
    s = load(hub, [tunnel(0), {"identifiers": [wb()], "event_kind": "departed_facility", "device_time_utc": at(600),
                               "device_id": "dock_3", "device_kind": "handheld"}])  # fmt: skip
    dep = s.scans[1]
    load(hub, [{"identifiers": [wb()], "event_kind": "departed_facility", "device_time_utc": at(600),
                "device_id": "dock_3", "device_kind": "handheld", "corrects_scan_event_id": dep,
                "correction_reason": "did_not_occur"}])  # fmt: skip
    v = facility_visit(hub, "site_test", {WB}, now=T0 + timedelta(hours=8))
    assert v.status == "open_overdue" and any("corrected" in n for n in v.notes)


def test_duplicate_reads_collapse(hub):
    load(hub, [tunnel(0), tunnel(0.8)])
    tl = scans_for(hub, {WB})
    assert len(tl.scans) == 1 and len(tl.dropped_duplicates) == 1


def test_late_handheld_upload_is_flagged(hub):
    row = bag_add(60, "BAG-1") | {"record_time_utc": at(60 + 40 * 60)}
    load(hub, [tunnel(0), row])
    v = facility_visit(hub, "site_test", {WB}, now=T0 + timedelta(hours=1))
    assert any("uploaded late" in n for n in v.notes)


# --- clocks ---------------------------------------------------------------------------------------------------------


def test_clock_fit_recovers_offset_and_drift_and_rejects_mismatches():
    rng = random.Random(4)
    anchors = []
    for i in range(40):  # two hours of tunnel passages seen by the tunnel-exit camera
        dev = T0 + timedelta(seconds=180 * i)
        true = 7000 + 50e-6 * (dev - T0).total_seconds() * 1000  # +7 s, drifting 50 ppm
        noise = rng.uniform(-10, 10) + (900 if i in (7, 23) else 0)  # two anchors paired with the wrong parcel
        anchors.append(AnchorPair(dev, dev + timedelta(milliseconds=true + noise), f"a{i}"))
    fit = fit_clock(anchors)
    assert abs(fit.offset_ms - 7000) < 8 and abs(fit.drift_ppm - 50) < 3
    assert set(fit.rejected_anchor_ids) == {"a7", "a23"} and fit.residual_ms_p95 < 12
    sync = sync_from_fit(fit, clock_domain_id="clkd_wcs", now=T0)
    later = T0 + timedelta(hours=2)
    assert abs(sync.correction_ms(later) - (7000 + 50e-6 * 7200 * 1000)) < 15
    with pytest.raises(ClockFitError):
        fit_clock(anchors[:2])


def test_scans_are_normalized_through_their_clock_domain(hub):
    hub.put(ClockSync(sync_id="sync_wcs", clock_domain_id="clkd_wcs", offset_ms=-2000, uncertainty_ms=15,
                      method="fixture", created_at=T0))  # fmt: skip
    load(hub, [tunnel(100)])
    ts = scans_for(hub, {WB}).scans[0]
    assert ts.synced and ts.t == T0 + timedelta(seconds=98) and ts.unc_ms == 15


def test_camera_clip_normalization_applies_drift():
    sync = ClockSync(sync_id="sync_c", camera_id="cam_a", offset_ms=1000, drift_ppm=100, drift_reference=T0,
                     uncertainty_ms=20, method="fixture", created_at=T0)  # fmt: skip
    ref = normalize(FrameRef(media_id="media_x", pts_ms=3_600_000, frame_index=36000),
                    clip_start_camera_time=T0, sync=sync)  # fmt: skip
    assert ref.normalized_utc == T0 + timedelta(hours=1, milliseconds=1000 + 360)
    with pytest.raises(ValidationError, match="camera or a clock domain"):
        ClockSync(sync_id="sync_x", offset_ms=0, uncertainty_ms=0, method="x", created_at=T0)


# --- graded last seen -------------------------------------------------------------------------------------------------


def test_graded_last_seen_keeps_inherited_location_as_a_lead(room, now):
    w = World(EvidenceStore(), room, now)
    w.store.put(ClockDomain(clock_domain_id="clkd_wcs", site_id=room.site_id, kind="wcs_plc", name="wcs"))
    w.camera("cam_a")
    t = w.track("cam_a", w.clip("cam_a", 0, 30))
    w.obs(t, 5.0, xy=(1.0, 3.6), zone="zone_shelf_a")
    oid = new_id("object_instance")
    w.store.put(ObjectInstance(object_instance_id=oid, case_id="case_w", label="parcel MY88213",
                               identifiers=[ParcelIdentifier(scheme="carrier_waybill", value="MY88213")],
                               created_by="t", created_at=now))  # fmt: skip
    w.link(oid, t, AssociationStatus.SCAN_BOUND)
    rows = [tunnel(1) | {"device_time_utc": (now + timedelta(seconds=1)).isoformat()},
            bag_add(20, "BAG-7") | {"device_time_utc": (now + timedelta(seconds=20)).isoformat()},
            load_bag(600, "BAG-7") | {"device_time_utc": (now + timedelta(seconds=600)).isoformat()}]
    ingest_scans(w.store, parse_scan_jsonl("\n".join(json.dumps(r) for r in rows), site_id=room.site_id,
                                           import_batch="f", source="simulated", now=now), now=now)  # fmt: skip
    g = graded_last_seen(w.store, oid)
    assert [s.klass for s in g.confident] == ["fixed_scan", "video", "handheld_scan"]
    assert g.last_confident.klass == "handheld_scan" and g.last_confident.label == EvidenceLabel.ESTIMATED
    assert g.leads and g.leads[0].klass == "inherited_container" and "BAG-7" in g.leads[0].where


def test_container_level_departure_closes_by_inheritance(hub):
    """A trailer/bag departure scan identifies the container, not each parcel."""
    load(hub, [tunnel(0), bag_add(60, "BAG-9"),
               {"event_kind": "departed_facility", "container": bag("BAG-9"), "device_time_utc": at(1200),
                "device_id": "dock_1", "device_kind": "handheld"}])  # fmt: skip
    v = facility_visit(hub, "site_test", {WB}, now=T0 + timedelta(hours=8))
    assert v.status == "closed_inherited" and "departed facility" in v.notes[-1]


def test_bag_lifecycle_and_bag_into_cage_are_container_scans(hub):
    """Hub log v2: bag_open / bag_close are container lifecycle scans (no parcel identity); a bag put into a roll cage
    is a container_add whose identifier is the bag, so the bag -> cage link is aggregation evidence, not a parcel read."""
    rows = [
        {"event_kind": "container_opened", "container": bag("BAG-C03-0007"), "container_type": "bag",
         "device_time_utc": at(0), "device_id": "SP-BAG-C03", "device_kind": "handheld", "clock_domain_id": "clkd_handheld"},
        {"event_kind": "container_closed", "container": bag("BAG-C03-0007"), "container_type": "bag",
         "device_time_utc": at(60), "device_id": "SP-BAG-C03", "device_kind": "handheld", "clock_domain_id": "clkd_handheld"},
        {"identifiers": [bag("BAG-C03-0007")], "event_kind": "container_add", "container": bag("CAGE-S04"),
         "container_type": "cage", "device_time_utc": at(90), "device_id": "SP-CAGE-W", "device_kind": "handheld",
         "clock_domain_id": "clkd_handheld"},
    ]  # fmt: skip
    summary = load(hub, rows)
    assert len(summary.scans) == 3 and len(summary.memberships_opened) == 1
    chain = container_chain(hub, "container:BAG-C03-0007", T0 + timedelta(seconds=120))
    assert [m.parent_key for m in chain] == ["container:CAGE-S04"]
    with pytest.raises(ValidationError):  # a lifecycle scan still needs its container
        ScanEvent(scan_event_id="scan_x1", site_id="site_test", source_type="scan_simulated", import_batch="b",
                  event_kind="container_opened", device_time_utc=at(0), device_id="d", device_kind="handheld")
