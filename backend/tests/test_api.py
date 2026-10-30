"""Step 09 acceptance test: the end-to-end HTTP flow without a UI (upload -> segment -> investigate -> export),
plus RBAC, signed links, review, sensor import and deletion. SAM output is a synthesized wire-format fixture."""

import hashlib
import json
import time
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from test_ingest import make_video
from test_perception import LINES, FixtureSamBackend

from spoor.api.app import create_app
from spoor.api.auth import Principal, TokenRegistry
from spoor.api.services import Services
from spoor.config import Settings
from spoor.contracts import Actor, ActorKind, Hypothesis, Role, new_id

T0 = datetime(2026, 10, 27, 14, 0, tzinfo=UTC)
TOKENS = {
    "t-admin": Principal("admin", Role.SITE_ADMIN, frozenset({"site_demo"})),
    "t-inv": Principal("ivy", Role.INVESTIGATOR, frozenset({"site_demo"})),
    "t-rev": Principal("rex", Role.REVIEWER, frozenset({"site_demo"})),
    "t-out": Principal("oscar", Role.INVESTIGATOR, frozenset({"site_other"})),
}
SITE = {
    "site_id": "site_demo", "name": "Demo storeroom", "measurement_method": "synthetic test",
    "floors": [{"floor_id": "floor_g", "name": "G", "outline_m": [[0, 0], [6, 0], [6, 4], [0, 4]]}],
    "zones": [{"zone_id": "zone_shelf_a", "floor_id": "floor_g", "name": "Shelf A", "kind": "shelf",
               "polygon_m": [[0, 3.4], [2, 3.4], [2, 4], [0, 4]], "surface_height_m": 1.2, "measured": True}],
}  # fmt: skip


def h(token):
    return {"Authorization": f"Bearer {token}"}


def wait(client, job_id, token="t-inv"):
    for _ in range(200):
        j = client.get(f"/v1/jobs/{job_id}", headers=h(token)).json()
        if j["status"] in ("done", "failed"):
            return j
        time.sleep(0.05)
    raise AssertionError("job did not finish")


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    return make_video(tmp_path_factory.mktemp("api") / "camA.mp4", seconds=3)


@pytest.fixture
def client(tmp_path):
    svc = Services.from_settings(Settings(data_dir=tmp_path, model_api_key=None, agent_backend="none"))
    svc.tokens = TokenRegistry(TOKENS)
    svc.sam = FixtureSamBackend(LINES)
    return TestClient(create_app(services=svc)), svc


@pytest.fixture
def ready(client, clip):
    c, svc = client
    assert c.post("/v1/sites", json=SITE, headers=h("t-admin")).status_code == 201
    cam = {"camera_id": "cam_a", "site_id": "site_demo", "floor_id": "floor_g", "name": "A",
           "resolution_wh_px": [320, 240],
           "zone_image_regions_px": {"zone_shelf_a": [[0, 0], [160, 0], [160, 120], [0, 120]]}}  # fmt: skip
    assert c.post("/v1/sites/site_demo/cameras", json=cam, headers=h("t-admin")).status_code == 201
    assert c.post("/v1/cameras/cam_a/clock-syncs", json={"offset_ms": 0, "uncertainty_ms": 50,
                  "method": "NTP + clap check"}, headers=h("t-admin")).status_code == 201  # fmt: skip
    meta = {"site_id": "site_demo", "camera_id": "cam_a", "rights_statement": "Team-recorded staged event, consented",
            "purpose": "hackathon demo", "consent_confirmed": True, "hosted_processing_allowed": True,
            "retention_days": 30, "recording_start_camera_time": T0.isoformat(),
            "recording_kind": "synthetic_test"}  # fmt: skip
    with clip.open("rb") as f:
        up = c.post("/v1/media/uploads", data={"meta": json.dumps(meta)}, files={"file": ("camA.mp4", f)},
                    headers=h("t-inv"))  # fmt: skip
    assert up.status_code == 201, up.text
    case = c.post("/v1/cases", json={"site_id": "site_demo", "question": "Where is the blue case?",
                                     "target_description": "blue equipment case"}, headers=h("t-inv")).json()
    return c, svc, up.json(), case


def test_end_to_end_flow(ready):
    c, svc, up, case = ready
    assert up["coverage_id"] and up["frames"] == 30
    case_id, obj_id = case["case"]["case_id"], case["object_instance_id"]

    # Operator-selected instance prompt -> SAM (fixture) -> tracks linked to the case object.
    seg = c.post(f"/v1/media/{up['media_id']}/segment", headers=h("t-inv"), json={
        "case_id": case_id, "instance": {"frame_index": 0, "box_ltrb_px": [20, 30, 80, 90]}})
    job = wait(c, seg.json()["job_id"])
    assert job["status"] == "done" and job["result"]["status"] == "ok", job
    # Two SAM objects -> not auto-linked; the investigator confirms object 1's track.
    track = next(t for t in job["result"]["tracks"] if t["provider_object_id"] == "1")
    r = c.post(f"/v1/cases/{case_id}/objects/{obj_id}/tracks/{track['track_id']}", headers=h("t-inv"),
               json={"status": "human_confirmed", "reason": "overlay matches the blue case"})
    assert r.status_code == 200 and r.json()["status"] == "human_confirmed"

    # I1 follow-cam crop: original pixels around the box, its hashes, and why this track is the object.
    cr = c.get(f"/v1/cases/{case_id}/tracks/{track['track_id']}/crop", params={"frame": 5}, headers=h("t-inv")).json()
    assert cr["media_sha256"] == up["sha256"] and cr["frame_index"] == 5 and cr["asset_kind"] == "original"
    x1, y1, x2, y2 = cr["crop_rect_px"]
    assert 0 <= x1 < x2 <= cr["frame_wh_px"][0] and 0 <= y1 < y2 <= cr["frame_wh_px"][1]
    assert cr["identity"]["association"]["status"] == "human_confirmed" and 5 in cr["observed_frames"]
    img = c.get(cr["crop_url"])
    assert img.status_code == 200 and img.headers["X-Spoor-Asset-Kind"] == "original_crop"
    assert hashlib.sha256(img.content).hexdigest() == cr["crop_sha256"]
    import cv2
    import numpy as np
    crop = cv2.imdecode(np.frombuffer(img.content, np.uint8), cv2.IMREAD_UNCHANGED)
    assert crop.shape[1] == x2 - x1 and crop.shape[0] == y2 - y1  # native pixels, no upscale
    rc = c.get(f"/v1/media/{up['media_id']}/frames/5/crop", params={"box": "10,10,40,40"}, headers=h("t-inv")).json()
    assert "not an observation" in rc["label"] and c.get(rc["crop_url"]).status_code == 200
    by_t = c.get(f"/v1/cases/{case_id}/tracks/{track['track_id']}/crop", headers=h("t-inv"),
                 params={"t": (T0 + timedelta(milliseconds=520)).isoformat()}).json()  # fmt: skip
    assert by_t["frame_index"] == 5  # nearest observed frame by normalized time (10 fps)
    scaled = c.get(f"/v1/media/{up['media_id']}/frames/5/crop", headers=h("t-inv"),
                   params={"box": "20,20,80,80", "basis": f"{2 * rc['frame_wh_px'][0]},{2 * rc['frame_wh_px'][1]}"}).json()
    assert scaled["box_px"] == [10.0, 10.0, 40.0, 40.0]
    # I5 synced grid: the same instant on the camera, its original frame and the subject's box there
    grid = c.get(f"/v1/cases/{case_id}/sync-grid", headers=h("t-inv"),
                 params={"cams": "cam_a", "t": (T0 + timedelta(milliseconds=500)).isoformat()}).json()  # fmt: skip
    (g,) = grid["cameras"]
    assert g["frame"]["frame_index"] == 5 and g["clock"]["uncertainty_ms"] == 50
    assert any(b["subject"] and b["track_id"] == track["track_id"] for b in g["boxes"])
    assert c.get(f"/v1/media/{up['media_id']}/frames/5/crop", params={"box": "40,10,10,40"},
                 headers=h("t-inv")).status_code == 422  # fmt: skip

    inv = wait(c, c.post(f"/v1/cases/{case_id}/investigate", headers=h("t-inv")).json()["job_id"])
    assert inv["status"] == "done" and inv["result"]["status"] == "answered", inv
    assert "NOT established" in inv["result"]["answer"]

    state = c.get(f"/v1/cases/{case_id}/state", headers=h("t-inv")).json()
    finding = state["findings"][0]
    obs_id = finding["observation_ids"][0]

    ev = c.get(f"/v1/cases/{case_id}/evidence/{obs_id}", headers=h("t-inv")).json()
    assert ev["media"]["sha256"] == up["sha256"] and ev["observation"]["source_frame"]["frame_index"] == 5
    png = c.get(ev["frame_url"])
    assert png.status_code == 200 and png.content[:4] == b"\x89PNG"
    assert c.get(ev["frame_url"].replace("sig=", "sig=0")).status_code == 403
    ann = c.get(ev["annotated_frame_url"])
    assert ann.status_code == 200 and ann.headers["X-Spoor-Asset-Kind"] == "annotated_derivative"
    assert ann.content != png.content  # box + derivative banner drawn; the original stays untouched

    rp = c.get(f"/v1/cases/{case_id}/replay", headers=h("t-inv")).json()
    seg = rp["objects"][0]["segments"][0]
    assert seg["style"] == "solid" and seg["camera_id"] == "cam_a" and seg["points"][0]["observation_id"]
    d = c.get(f"/v1/cases/{case_id}/diff", headers=h("t-inv")).json()
    assert d["new_findings"][0]["observation_ids"] == [obs_id]
    assert c.get(f"/v1/operator/cases/{case_id}/trace", headers=h("t-inv")).status_code == 403
    trace = c.get(f"/v1/operator/cases/{case_id}/trace", headers=h("t-rev")).json()
    assert trace["models"]["meta_model_api:sam-3.1"]["calls"] == 1

    world = c.get(f"/v1/cases/{case_id}/world-at", params={"time": (T0 + timedelta(milliseconds=500)).isoformat()},
                  headers=h("t-inv")).json()  # fmt: skip
    assert world["objects"][0]["evidence_label"] == "observed"
    later = c.get(f"/v1/cases/{case_id}/world-at", params={"time": (T0 + timedelta(seconds=30)).isoformat()},
                  headers=h("t-inv")).json()  # fmt: skip
    assert later["objects"][0]["evidence_label"] == "unknown"

    exp = c.post(f"/v1/cases/{case_id}/export", headers=h("t-inv")).json()
    assert exp["manifest"]["sources"][0]["sha256"] == up["sha256"]
    appr = c.post(f"/v1/reports/{exp['report_id']}/approve", headers=h("t-rev"))
    assert appr.status_code == 201 and appr.json()["sha256"] == exp["manifest"]["report_sha256"]
    html = c.get(f"/v1/reports/{appr.json()['report_id']}", params={"format": "html"}, headers=h("t-rev")).text
    assert "APPROVED by rex" in html and "not an official forensic certification" in html

    # Purge the source: evidence disappears, the finding is invalidated (history kept).
    assert c.post(f"/v1/media/{up['media_id']}/purge", json={"reason": "retention test"},
                  headers=h("t-admin")).status_code == 200  # fmt: skip
    state = c.get(f"/v1/cases/{case_id}/state", headers=h("t-inv")).json()
    assert state["findings"][0]["invalidated"] is True
    assert c.get(f"/v1/media/{up['media_id']}", headers=h("t-inv")).status_code == 404


def test_rbac_and_site_isolation(ready):
    c, svc, up, case = ready
    case_id = case["case"]["case_id"]
    assert c.get(f"/v1/cases/{case_id}/state").status_code == 401
    assert c.get(f"/v1/cases/{case_id}/state", headers=h("bogus")).status_code == 401
    assert c.get(f"/v1/cases/{case_id}/state", headers=h("t-out")).status_code == 403
    assert c.post("/v1/sites", json=SITE, headers=h("t-inv")).status_code == 403
    assert c.post(f"/v1/cases/{case_id}/investigate", headers=h("t-rev")).status_code == 403
    exp = c.post(f"/v1/cases/{case_id}/export", headers=h("t-rev")).json()
    assert c.post(f"/v1/reports/{exp['report_id']}/approve", headers=h("t-rev")).status_code == 403  # own export


def test_upload_requires_consent_and_valid_media(client, tmp_path):
    c, svc = client
    c.post("/v1/sites", json=SITE, headers=h("t-admin"))
    c.post("/v1/sites/site_demo/cameras", json={"camera_id": "cam_a", "site_id": "site_demo", "floor_id": "floor_g",
           "name": "A", "resolution_wh_px": [320, 240]}, headers=h("t-admin"))  # fmt: skip
    meta = {"site_id": "site_demo", "camera_id": "cam_a", "rights_statement": "Team-recorded staged event",
            "purpose": "demo", "consent_confirmed": False, "hosted_processing_allowed": False, "retention_days": 1,
            "recording_kind": "synthetic_test"}
    bad = c.post("/v1/media/uploads", data={"meta": json.dumps(meta)}, files={"file": ("x.mp4", b"0" * 100)},
                 headers=h("t-inv"))  # fmt: skip
    assert bad.status_code == 422
    meta["consent_confirmed"] = True
    junk = c.post("/v1/media/uploads", data={"meta": json.dumps(meta)},
                  files={"file": ("../../etc/notes.mp4", b"not a video")}, headers=h("t-inv"))  # fmt: skip
    assert junk.status_code == 422 and "rejected" in junk.json()["detail"]


def test_review_sensor_import_and_audit(ready):
    c, svc, up, case = ready
    case_id = case["case"]["case_id"]
    hyp = svc.store.put(Hypothesis(hypothesis_id=new_id("hypothesis"), case_id=case_id, claim="Case moved to desk",
                                   proposed_by=Actor(kind=ActorKind.AGENT, id="hypothesis", model="fixture"),
                                   created_at=T0))  # fmt: skip
    r = c.post(f"/v1/cases/{case_id}/review", headers=h("t-rev"), json={
        "hypothesis_id": hyp.hypothesis_id, "to_status": "insufficient_evidence",
        "reason": "desk not visible from camera A"})
    assert r.status_code == 200 and r.json()["status"] == "insufficient_evidence"
    assert c.post(f"/v1/cases/{case_id}/review", headers=h("t-inv"), json={
        "hypothesis_id": hyp.hypothesis_id, "to_status": "supported", "reason": "x" * 6}).status_code == 403

    csv_ok = ("device_id,kind,value,zone_id,device_time_utc,clock_quality,source\n"
              "door_b,door_contact,open,,2026-10-27T14:00:10+00:00,ntp,simulated\n")  # fmt: skip
    r = c.post(f"/v1/cases/{case_id}/evidence/import", data={"batch": "door-sim-1"},
               files={"file": ("door.csv", csv_ok.encode())}, headers=h("t-inv"))  # fmt: skip
    assert r.status_code == 201 and r.json()["simulated"] == 1
    csv_bad = csv_ok.replace(",simulated", ",")
    r = c.post(f"/v1/cases/{case_id}/evidence/import", data={"batch": "b2"},
               files={"file": ("door.csv", csv_bad.encode())}, headers=h("t-inv"))  # fmt: skip
    assert r.status_code == 422

    from spoor.store import AuditEntry

    actions = {a.action for a in svc.store.find(AuditEntry)}
    assert {"upload_media", "create_case", "review_hypothesis", "import_sensor_log"} <= actions


def test_review_fixes_api_isolation_and_integrity(ready, clip):
    """Independent review #1, #4, #6, #8, #11, #12, #14."""
    c, svc, up, case = ready
    case_id, obj_id = case["case"]["case_id"], case["object_instance_id"]
    # #6: another site cannot take over cam_a
    other = {**SITE, "site_id": "site_other"}
    svc.tokens = TokenRegistry({**TOKENS, "t-oadmin": Principal("o", Role.SITE_ADMIN, frozenset({"site_other"}))})
    assert c.post("/v1/sites", json=other, headers=h("t-oadmin")).status_code == 201
    takeover = {"camera_id": "cam_a", "site_id": "site_other", "floor_id": "floor_g", "name": "x",
                "resolution_wh_px": [320, 240]}  # fmt: skip
    assert c.post("/v1/sites/site_other/cameras", json=takeover, headers=h("t-oadmin")).status_code == 409
    # #1: a user of another site cannot segment into this case
    r = c.post(f"/v1/media/{up['media_id']}/segment", headers=h("t-out"),
               json={"case_id": case_id, "instance": {"frame_index": 0, "box_ltrb_px": [20, 30, 80, 90]}})
    assert r.status_code == 403
    # #8: another case's object is not readable through my case
    mine = c.post("/v1/cases", json={"site_id": "site_demo", "question": "Where is the laptop?", "target_description": "laptop"},
                  headers=h("t-inv")).json()  # fmt: skip
    gap = {"object_instance_id": obj_id, "start": T0.isoformat(), "end": (T0 + timedelta(seconds=5)).isoformat()}
    assert c.post(f"/v1/cases/{mine['case']['case_id']}/unobserved", json=gap, headers=h("t-inv")).status_code == 404
    # #14: identical bytes cannot be re-registered to another camera
    c.post("/v1/sites/site_demo/cameras", json={"camera_id": "cam_b", "site_id": "site_demo", "floor_id": "floor_g",
           "name": "B", "resolution_wh_px": [320, 240]}, headers=h("t-admin"))  # fmt: skip
    meta = {"site_id": "site_demo", "camera_id": "cam_b", "rights_statement": "Team-recorded staged event, consented",
            "purpose": "demo", "consent_confirmed": True, "hosted_processing_allowed": True, "retention_days": 1,
            "recording_kind": "staged_event"}  # fmt: skip
    with clip.open("rb") as f:
        dup = c.post("/v1/media/uploads", data={"meta": json.dumps(meta)}, files={"file": ("x.mp4", f)},
                     headers=h("t-inv"))  # fmt: skip
    assert dup.status_code == 409

    # #11: provenance label comes from the declared recording kind
    seg = c.post(f"/v1/media/{up['media_id']}/segment", headers=h("t-inv"), json={
        "case_id": case_id, "instance": {"frame_index": 0, "box_ltrb_px": [20, 30, 80, 90]}})
    job = wait(c, seg.json()["job_id"])
    track = next(t for t in job["result"]["tracks"] if t["provider_object_id"] == "1")
    c.post(f"/v1/cases/{case_id}/objects/{obj_id}/tracks/{track['track_id']}", headers=h("t-inv"),
           json={"status": "human_confirmed", "reason": "matches"})
    wait(c, c.post(f"/v1/cases/{case_id}/investigate", headers=h("t-inv")).json()["job_id"])
    exp = c.post(f"/v1/cases/{case_id}/export", headers=h("t-inv")).json()
    report = c.get(f"/v1/reports/{exp['report_id']}", headers=h("t-inv")).json()["content"]
    assert report["sources"][0]["label"] == "Synthetic test footage"

    # #4 + #12: purge after the draft -> approval refused; derived files are gone
    cache = svc.settings.data_dir / "inference_cache"
    assert list(cache.glob("sam_*.json"))
    c.post(f"/v1/media/{up['media_id']}/purge", json={"reason": "retention"}, headers=h("t-admin"))
    assert c.post(f"/v1/reports/{exp['report_id']}/approve", headers=h("t-rev")).status_code == 409
    assert not list(cache.glob("sam_*.json"))
    assert not (svc.media.root / "manifests" / f"{up['media_id']}.json").exists()


def test_parcel_scan_routes(client):
    """Parcel pivot: clock domain + fit, scan import, and parcel lookup over HTTP."""
    c, svc = client
    assert c.post("/v1/sites", json=SITE, headers=h("t-admin")).status_code == 201
    dom = c.post("/v1/sites/site_demo/clock-domains", json={"kind": "wcs_plc", "name": "sorter WCS"},
                 headers=h("t-admin")).json()  # fmt: skip
    anchors = [{"device_time": (T0 + timedelta(minutes=i)).isoformat(),
                "reference_time": (T0 + timedelta(minutes=i, milliseconds=7000)).isoformat(),
                "anchor_id": f"tunnel_pass_{i}"} for i in range(5)]  # fmt: skip
    fit = c.post(f"/v1/clock-domains/{dom['clock_domain_id']}/fit", json={"anchors": anchors}, headers=h("t-admin"))
    assert fit.status_code == 201 and abs(fit.json()["sync"]["offset_ms"] - 7000) < 1
    assert c.post(f"/v1/clock-domains/{dom['clock_domain_id']}/fit", json={"anchors": anchors[:2]},
                  headers=h("t-admin")).status_code == 422  # fmt: skip

    lines = [
        {"identifiers": [{"scheme": "carrier_waybill", "value": "MY88213"}], "event_kind": "tunnel_read",
         "device_time_utc": T0.isoformat(), "device_id": "tunnel_1", "device_kind": "tunnel",
         "clock_domain_id": dom["clock_domain_id"], "read_point_zone_id": "zone_shelf_a"},
        {"identifiers": [{"scheme": "carrier_waybill", "value": "MY99001"},
                         {"scheme": "carrier_waybill", "value": "MY88213"}], "event_kind": "relabeled",
         "device_time_utc": (T0 + timedelta(minutes=5)).isoformat(), "device_id": "bench_2", "device_kind": "handheld"},
    ]  # fmt: skip
    body = "\n".join(json.dumps(x) for x in lines).encode()
    r = c.post("/v1/sites/site_demo/scans/import", data={"batch": "sim-1", "source": "simulated"},
               files={"file": ("scans.jsonl", body)}, headers=h("t-inv"))  # fmt: skip
    assert r.status_code == 201 and r.json() == {"imported": 2, "skipped_exact_duplicates": 0,
                                                 "memberships_opened": 0, "memberships_closed": 0, "aliases": 1}
    assert c.post("/v1/sites/site_demo/scans/import", data={"batch": "x", "source": "simulated"},
                  files={"file": ("s.jsonl", body)}, headers=h("t-out")).status_code == 403  # fmt: skip

    look = c.get("/v1/sites/site_demo/parcels/carrier_waybill/MY99001", headers=h("t-inv")).json()
    assert look["aliases"] == ["carrier_waybill:MY88213"]
    first = look["scans"][0]
    assert first["synced"] and first["time"].startswith("2026-10-27T14:00:07") and first["source_type"] == "scan_simulated"
    assert look["visit"]["status"] in ("open_within_sla", "open_overdue")

    case = c.post("/v1/cases", json={"site_id": "site_demo", "question": "Where is parcel MY88213?",
                                     "target_description": "parcel MY88213",
                                     "identifiers": [{"scheme": "carrier_waybill", "value": "MY88213"}],
                                     "claim_reference": "CLM-0042", "complaint": "Parcel MY88213 never arrived.",
                                     "reported_at": "2026-10-29T09:15:00+08:00"},
                  headers=h("t-inv"))  # fmt: skip
    assert case.status_code == 201

    # Report follows a claims trace (QUEUE G): scan history first, gaps between scans, records a claim needs.
    exp = c.post(f"/v1/cases/{case.json()['case']['case_id']}/export", headers=h("t-inv")).json()
    rep = c.get(f"/v1/reports/{exp['report_id']}", headers=h("t-inv")).json()["content"]
    hist = rep["scan_history"]
    assert [x["event"] for x in hist] == ["tunnel_read", "relabeled"] and hist[0]["gap_from_previous_s"] is None
    # 300 s on the device clocks; the tunnel read is corrected +7 s by its fitted WCS clock, the handheld is not
    assert hist[1]["gap_from_previous_s"] == 293.0 and hist[1]["clock"] == "device time, not synchronized"
    assert hist[0]["clock"].startswith("synchronized")
    assert rep["consignment"]["scan_events"] == 2 and "carrier_waybill:MY88213" in rep["consignment"]["identifiers"]
    held = {r["record"].split(" (")[0]: r["held"] for r in rep["records_not_held"]}
    assert held["Linehaul loading or departure scan"].startswith("no") and held["Proof of delivery"].startswith("no")
    assert rep["footage_reviewed"] == [] and rep["continuity"][0]["item"].startswith("scan log batch sim-1")
    page = c.get(f"/v1/reports/{exp['report_id']}", params={"format": "html"}, headers=h("t-inv")).text
    assert "Scan history (where the consignment was scanned, not where it went)" in page
    # Review 012: a document a claims team hands over: complaint block, human labels, one time zone, no literals.
    assert rep["claim"] == {"claim_reference": "CLM-0042", "complaint": "Parcel MY88213 never arrived.",
                            "reported_at": "2026-10-29T09:15:00.000+08:00"}  # fmt: skip
    assert "CLM-0042" in page and "Parcel MY88213 never arrived." in page and "29 Oct 2026, 09:15:00.0 MYT" in page
    assert "Gap since previous scan" in page and "293 s" in page and "gap_from_previous_s" not in page
    assert "+00:00" not in page and "<td>None</td>" not in page and "<td>False</td>" not in page
    assert "None. None." not in page and "Malaysia Time (MYT, UTC+08:00)" in page
    assert rep["sources_used"][0]["kind"] == "Scan log batch" and "Simulated scan log" in page


def test_workspace_read_routes(ready):
    """Read models used by the web workspace: lists, frame-at-time, graded last seen, reports, capabilities."""
    c, svc, up, case = ready
    case_id = case["case"]["case_id"]
    caps = c.get("/v1/capabilities", headers=h("t-inv")).json()
    assert caps["spark"] is False and caps["agents"] is False
    assert caps["site_to_renderer"] == [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]]
    assert c.get("/v1/me", headers=h("t-rev")).json() == {"user_id": "rex", "role": "reviewer",
                                                         "site_ids": ["site_demo"]}  # fmt: skip
    assert [s["site_id"] for s in c.get("/v1/sites", headers=h("t-inv")).json()] == ["site_demo"]
    assert c.get("/v1/sites/site_demo", headers=h("t-out")).status_code == 403

    cams = c.get("/v1/sites/site_demo/cameras", headers=h("t-inv")).json()
    assert cams[0]["camera"]["camera_id"] == "cam_a" and cams[0]["clock_sync"]["uncertainty_ms"] == 50
    assert cams[0]["calibration"] is None and cams[0]["coverage"][0]["media_id"] == up["media_id"]
    media = c.get("/v1/sites/site_demo/media", headers=h("t-inv")).json()
    assert [m["media"]["media_id"] for m in media] == [up["media_id"]]  # originals only, not the proxy
    assert media[0]["recording_kind"] == "synthetic_test"

    # Frame at a normalized time: nearest frame, signed link, and an explicit "not an observation" label.
    fa = c.get(f"/v1/media/{up['media_id']}/frame-at", params={"time": (T0 + timedelta(seconds=1)).isoformat()},
               headers=h("t-inv")).json()  # fmt: skip
    assert fa["frame_index"] == 10 and abs(fa["delta_ms"]) < 1 and "not an observation" in fa["label"]
    assert c.get(fa["frame_url"]).content[:4] == b"\x89PNG"
    late = c.get(f"/v1/media/{up['media_id']}/frame-at", params={"time": (T0 + timedelta(minutes=5)).isoformat()},
                 headers=h("t-inv"))  # fmt: skip
    assert late.status_code == 404

    # Context playback (review 007 #1): the original's frame table, a signed byte-range stream of its working proxy.
    pb = c.get(f"/v1/media/{up['media_id']}/playback", headers=h("t-inv")).json()
    assert pb["proxy_media_id"] == up["proxy_media_id"] and pb["frame_count"] == len(pb["pts_ms"]) == up["frames"]
    assert "not an observation" in pb["label"] and pb["start_utc"] is not None
    full = c.get(pb["url"])
    assert full.status_code == 200 and full.headers["content-type"] == "video/mp4" and full.content[4:8] == b"ftyp"
    part = c.get(pb["url"], headers={"Range": "bytes=0-99"})
    assert part.status_code == 206 and len(part.content) == 100
    assert c.get(pb["url"].replace("sig=", "sig=0")).status_code == 403
    assert c.get(f"/v1/media/{up['proxy_media_id']}/playback", headers=h("t-inv")).status_code == 400
    assert c.get(f"/v1/media/{up['media_id']}/playback", headers=h("t-out")).status_code == 403

    listed = c.get("/v1/cases", headers=h("t-inv")).json()
    assert listed[0]["case"]["case_id"] == case_id and listed[0]["report_status"] is None
    assert c.get("/v1/cases", params={"site_id": "site_demo"}, headers=h("t-out")).status_code == 403
    ls = c.get(f"/v1/cases/{case_id}/last-seen", headers=h("t-inv")).json()
    assert ls[0]["last_confident"] is None and ls[0]["leads"] == []  # nothing observed or scanned yet
    assert c.get(f"/v1/cases/{case_id}/reports", headers=h("t-inv")).json() == []
    c.post(f"/v1/cases/{case_id}/export", headers=h("t-inv"))
    assert c.get(f"/v1/cases/{case_id}/reports", headers=h("t-inv")).json()[0]["status"] == "draft"


def test_scan_and_clock_lists(client):
    c, svc = client
    assert c.post("/v1/sites", json=SITE, headers=h("t-admin")).status_code == 201
    dom = c.post("/v1/sites/site_demo/clock-domains", json={"kind": "wcs_plc", "name": "sorter WCS"},
                 headers=h("t-admin")).json()  # fmt: skip
    line = {"identifiers": [{"scheme": "carrier_waybill", "value": "MY88213"}], "event_kind": "tunnel_read",
            "device_time_utc": T0.isoformat(), "device_id": "tunnel_1", "device_kind": "tunnel",
            "clock_domain_id": dom["clock_domain_id"], "read_point_zone_id": "zone_shelf_a"}  # fmt: skip
    c.post("/v1/sites/site_demo/scans/import", data={"batch": "sim-1", "source": "simulated"},
           files={"file": ("scans.jsonl", json.dumps(line).encode())}, headers=h("t-inv"))  # fmt: skip
    doms = c.get("/v1/sites/site_demo/clock-domains", headers=h("t-inv")).json()
    assert doms[0]["domain"]["name"] == "sorter WCS" and doms[0]["sync"] is None
    scans = c.get("/v1/sites/site_demo/scans", headers=h("t-inv")).json()
    assert scans["total"] == 1 and scans["scans"][0]["synced"] is False  # no fit: device time, flagged unsynced
    assert scans["scans"][0]["source_type"] == "scan_simulated"
    assert c.get("/v1/sites/site_demo/scans", params={"start": (T0 + timedelta(seconds=1)).isoformat()},
                 headers=h("t-inv")).json()["total"] == 0  # fmt: skip
