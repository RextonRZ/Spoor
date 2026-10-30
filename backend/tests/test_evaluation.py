"""Step 10 acceptance tests: harness wiring, metrics, and the ground-truth firewall (PRD §8.1, §21).

The dataset here is synthetic (ffmpeg test pattern + synthesized SAM wire output): it tests the harness, it is NOT an
evaluation result and must never be reported as one.
"""

import inspect
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import sam_wire
from test_ingest import make_video

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml" / "evaluation"))

from spoor_eval import metrics, variants
from spoor_eval.run import markdown_table, run
from spoor_eval.schema import GroundTruth, Prediction, ScenarioInputs, TruthEvent

from spoor.perception import parse_sam_stream

T0 = datetime(2026, 10, 27, 14, 0, tzinfo=UTC)
W, H = 320, 240


class PromptAwareFixtureSam:
    """Returns one tracked object for operator box prompts, nothing for concept prompts (fixture behaviour)."""

    model = "sam-3.1"

    async def segment_video(self, video, prompt, *, propagation="both"):
        lines = [] if not prompt.startswith("<") else [
            sam_wire.line(f, sam_wire.record(1, (20 + f, 30, 79 + f, 89), (W, H), conf=0.9)) for f in (0, 1, 2, 5)
        ]  # fmt: skip
        return await parse_sam_stream(sam_wire.stream(sam_wire.events(lines)), model=self.model)


@pytest.fixture
def dataset(tmp_path, room):
    d = tmp_path / "ds"
    (d / "scenarios").mkdir(parents=True)
    (d / "ground_truth").mkdir()
    make_video(d / "camA.mp4", seconds=3)
    (d / "site.json").write_text(room.model_copy(update={"site_id": "site_eval"}).model_dump_json())
    cam = {"camera_id": "cam_a", "resolution_wh_px": [W, H], "clock_uncertainty_ms": 50, "clock_method": "fixture",
           "zone_image_regions_px": {"zone_shelf_a": [[0, 0], [160, 0], [160, 120], [0, 120]]}}  # fmt: skip
    clip = {"camera_id": "cam_a", "file": "camA.mp4", "recording_start_camera_time": T0.isoformat()}
    common = {"question": "Where is it?", "cameras": [cam], "clips": [clip], "split": "holdout"}
    (d / "scenarios" / "s1.json").write_text(json.dumps({
        **common, "scenario_id": "s1", "category": "C01", "target_description": "blue equipment case",
        "target_init": {"camera_id": "cam_a", "clip_index": 0, "frame_index": 0, "box_ltrb_px": [20, 30, 80, 90]}}))
    (d / "scenarios" / "s2.json").write_text(json.dumps({
        **common, "scenario_id": "s2", "category": "C09", "target_description": "red tool pouch"}))
    truth = {"annotator": "fixture", "annotated_at": T0.isoformat(), "annotation_confidence": "high"}
    (d / "ground_truth" / "s1.json").write_text(json.dumps({
        **truth, "scenario_id": "s1", "answerable": True, "last_seen_utc": (T0 + timedelta(seconds=0.5)).isoformat(),
        "last_seen_zone": "zone_shelf_a", "left_area": "unknown"}))
    (d / "ground_truth" / "s2.json").write_text(json.dumps({**truth, "scenario_id": "s2", "answerable": False}))
    return d


def test_harness_runs_variants_and_scores(dataset, tmp_path):
    backends = variants.Backends(sam=PromptAwareFixtureSam())
    result = run(dataset, ["A0", "A1", "A2", "A3"], split="holdout", backends=backends, out_dir=tmp_path / "out")
    preds = {(p["scenario_id"], p["variant"]): p for p in result["predictions"]}
    assert preds[("s1", "A0")]["status"] == "unavailable" and preds[("s1", "A3")]["status"] == "unavailable"
    assert preds[("s1", "A2")]["status"] == "answered" and preds[("s2", "A2")]["status"] == "abstained"
    a2 = result["variants"]["A2"]
    assert a2["last_seen_accuracy"] == 1.0 and a2["abstention_recall"] == 1.0 and a2["abstention_precision"] == 1.0
    assert preds[("s1", "A2")]["last_seen_zone"] == "zone_shelf_a"
    assert (tmp_path / "out" / "latest.json").exists() and "| A2 |" in (tmp_path / "out" / "latest.md").read_text()


def test_variants_never_receive_ground_truth():
    """Firewall: variant signatures accept ScenarioInputs only, and inputs have no truth fields."""
    for fn in variants.VARIANTS.values():
        params = inspect.signature(fn).parameters
        assert "truth" not in " ".join(params) and next(iter(params)) == "inputs"
    truth_fields = set(GroundTruth.model_fields) - {"scenario_id"}
    assert not truth_fields & set(ScenarioInputs.model_fields)


def test_runtime_package_cannot_see_evaluation_code():
    src = ROOT / "backend" / "src" / "spoor"
    for path in src.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "spoor_eval" not in text and "ground_truth" not in text, path


def _ev(kind, a, b):
    return TruthEvent(kind=kind, start_utc=T0 + timedelta(seconds=a), end_utc=T0 + timedelta(seconds=b))


def test_event_matching():
    truth = [_ev("moved", 0, 4), _ev("occluded", 5, 9)]
    pred = [_ev("moved", 1, 4), _ev("moved", 10, 12), _ev("occluded", 20, 21)]
    assert metrics.match_events(pred, truth) == (1, 2, 1)


def test_scoring_rules():
    truth = GroundTruth(scenario_id="x", answerable=True, last_seen_utc=T0, last_seen_zone="zone_desk",
                        last_seen_xy_m=(1, 1), annotator="a", annotated_at=T0, annotation_confidence="high")
    good = Prediction(scenario_id="x", variant="A2", status="answered", last_seen_utc=T0 + timedelta(seconds=0.4),
                      last_seen_zone="zone_desk", last_seen_xy_m=(1.3, 1.4))  # fmt: skip
    wrong_zone = good.model_copy(update={"last_seen_zone": "zone_door_b"})
    abstain = Prediction(scenario_id="x", variant="A2", status="abstained")
    s = metrics.score(good, truth)
    assert s.last_seen_correct and s.spatial_error_m == pytest.approx(0.5)
    assert metrics.score(wrong_zone, truth).last_seen_correct is False
    assert metrics.score(abstain, truth).last_seen_correct is False
    agg = metrics.aggregate([s, metrics.score(abstain, truth)])
    assert agg["last_seen_accuracy"] == 0.5 and agg["abstention_precision"] == 0.0
    assert "| A |" in markdown_table({"A": agg})


def test_blind_citation_review(tmp_path):
    p = tmp_path / "review.csv"
    p.write_text("claim_id,variant,supported,cited\n1,A0,no,no\n2,A0,yes,no\n3,A3,yes,yes\n4,A3,partial,yes\n")
    out = metrics.citation_review(p)
    assert out["A0"]["unsupported_per_100_claims"] == 50 and out["A0"]["citation_validity"] is None
    assert out["A3"]["citation_validity"] == 0.5


def test_change_detection_baseline_finds_when_region_changes(tmp_path, room):
    """A blue box present for 1.5 s then gone: CD reports ~1.4 s without any model."""
    from spoor.ingest.ffmpeg import run_ffmpeg

    d = tmp_path / "cd"
    (d / "scenarios").mkdir(parents=True)
    run_ffmpeg("-y", "-f", "lavfi", "-i", "color=c=gray:s=320x240:r=10:d=3",
               "-vf", "drawbox=x=20:y=30:w=60:h=60:color=blue:t=fill:enable='lt(t,1.5)'",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", str(d / "cam.mp4"))  # fmt: skip
    (d / "site.json").write_text(room.model_dump_json())
    sc = ScenarioInputs.model_validate({
        "scenario_id": "cd1", "category": "C01", "question": "Where is it?", "target_description": "blue case",
        "cameras": [{"camera_id": "cam_a", "resolution_wh_px": [W, H], "clock_uncertainty_ms": 50,
                     "clock_method": "fixture",
                     "zone_image_regions_px": {"zone_shelf_a": [[0, 0], [160, 0], [160, 120], [0, 120]]}}],
        "clips": [{"camera_id": "cam_a", "file": "cam.mp4", "recording_start_camera_time": T0.isoformat()}],
        "target_init": {"camera_id": "cam_a", "clip_index": 0, "frame_index": 0, "box_ltrb_px": [20, 30, 80, 90]},
        "split": "dev"})  # fmt: skip
    pred = variants.variant_cd(sc, d, tmp_path / "work", variants.Backends())
    assert pred.status == "answered" and pred.last_seen_zone == "zone_shelf_a"
    assert abs((pred.last_seen_utc - T0).total_seconds() - 1.4) <= 0.1


# --- parcel-hub no-key evaluator (QUEUE F3) -------------------------------------------------------------------------

TRUTH_MARKERS = ("events_truth", "flow_truth", "render_truth", "build/truth", "build\truth", "scenario_card")


def test_runtime_and_web_app_never_reference_truth_files():
    """The runtime package and the web app source may not even name evaluator-only truth files."""
    for base in (ROOT / "backend" / "src" / "spoor", ROOT / "frontend" / "src"):
        for path in base.rglob("*"):
            if path.suffix in (".py", ".ts", ".tsx", ".json") and path.is_file():
                text = path.read_text(encoding="utf-8", errors="ignore")
                assert not any(m in text for m in TRUTH_MARKERS), path


def test_hub_predict_phase_cannot_see_truth():
    from spoor_eval import hub

    params = inspect.signature(hub.predict).parameters
    assert not any("truth" in p for p in params)
    assert "truth" not in inspect.getsource(hub.predict).split('"""')[-1]  # body never opens a truth path
    seed = (ROOT / "frontend" / "scripts" / "seed_nokey.py").read_text(encoding="utf-8")
    assert "def guard" in seed and "render_truth" in seed  # the loader refuses truth paths


def test_hub_scoring_rules():
    from spoor_eval.hub import HubPrediction, HubTruth, aggregate, score

    pred = HubPrediction(parcel="CTX1", case_id="case_x", status="abstained", last_seen_time="2026-10-28T14:32:10+08:00",
                         last_seen_event="divert_confirm", last_seen_device="SP-DIV-C03", last_seen_class="fixed_scan",
                         later_location_claims=0, left_area="unknown", no_coverage_intervals=1, answer="", latency_s=0.1)
    truth = HubTruth("CTX1", "divert_confirm", "2026-10-28T14:32:10.400+08:00", (44.1, 20.5), 1.0, "Z06", True, [])
    s = score(pred, truth)
    assert s["last_seen_correct"] and s["abstention_correct"] and not s["false_left_hub"]
    seen = score(pred, HubTruth("CTX1", "divert_confirm", "2026-10-28T14:32:10+08:00", None, None, None, True, ["CAM_10"]))
    assert seen["abstention"].startswith("missed") and not seen["abstention_correct"]
    wrong = score(pred.__class__(**{**pred.__dict__, "last_seen_event": "tunnel_read", "left_area": "yes"}), truth)
    assert not wrong["last_seen_correct"] and wrong["false_left_hub"]
    agg = aggregate([s, seen, wrong])
    assert agg["n_cases"] == 3 and agg["false_left_hub"] == 1 and agg["abstention_missed_visible"] == 1


# --- review 007 #4: D scenarios are the headline when renders and reference data exist -----------------------------


def _manifest(tmp_path: Path, entries: dict[str, bool]) -> tuple[Path, Path]:
    """entries: scenario -> has renders. Reference files are written for S0, S1, S3 only."""
    scen = tmp_path / "ml" / "evaluation" / "scenarios"
    scen.mkdir(parents=True)
    ref = tmp_path / "ref"
    ref.mkdir()
    items = []
    for sc, rendered in entries.items():
        clips = tmp_path / "renders" / sc
        clips.mkdir(parents=True)
        if rendered:
            (clips / "CAM_10.mp4").write_bytes(b"x")
        items.append({"scenario": sc, "title": f"title {sc}", "parcel": f"CTX{sc}", "subject_kind": "parcel",
                      "clips": f"../../../renders/{sc}", "scans": f"../../../scans_{sc}.jsonl",
                      "clip_start": "2026-10-28T14:32:07+08:00"})  # fmt: skip
    for sc in ("S0", "S1", "S3"):
        suf = "" if sc == "S0" else f"_{sc}"
        for name in (f"scenario_{sc}.json", f"events_truth{suf}.jsonl", f"flow_truth{suf}.json"):
            (ref / name).write_text("{}", encoding="utf-8")
    (scen / "manifest.json").write_text(json.dumps(items), encoding="utf-8")
    return scen / "manifest.json", ref


def test_hub_plan_needs_renders_and_reference_data(tmp_path):
    from spoor_eval.hub import plan_suite

    manifest, ref = _manifest(tmp_path, {"S0": True, "S1": True, "S2": True, "S3": False})
    plan = plan_suite(manifest, ref)
    assert [e["scenario"] for e in plan["eligible"]] == ["S1"]
    why = {s["scenario"]: s["reason"] for s in plan["skipped"]}
    assert why["S2"].startswith("reference data not written") and why["S3"] == "renders not produced yet"
    assert why["S4"] == why["S5"] == "not in the manifest"
    assert plan["control"]["scenario"] == "S0"
    assert all(s["reason"] == "scenario manifest not written yet" for s in plan_suite(tmp_path / "none.json", ref)["skipped"])


def _fake_phase(monkeypatch, calls):
    from spoor_eval import hub

    def predict(**kw):
        calls.append("predict")
        subj = kw.get("subjects") or [("CTX_A", "parcel")]
        return {"predictions": [hub.HubPrediction(parcel=s, case_id="c", status="abstained",
                                                  last_seen_time="2026-10-28T14:32:10+08:00", last_seen_event="tunnel_read",
                                                  last_seen_device="SP-TUNNEL", last_seen_class="fixed_scan",
                                                  later_location_claims=0, left_area="unknown", no_coverage_intervals=None,
                                                  answer="", latency_s=0.0, subject_kind=k) for s, k in subj],
                "clip_cameras": ["CAM_10"], "spec": {}, "scans_not_imported": {}, "clip_seconds": 30.0}  # fmt: skip

    def load_truth(truth_dir, parcels, **kw):
        calls.append("truth")
        return {p: hub.HubTruth(p, "divert_confirm", "2026-10-28T14:32:20+08:00", (40.0, 20.0), 0.1, "Z06", True,
                                ["CAM_10"]) for p in parcels}  # fmt: skip

    monkeypatch.setattr(hub, "predict", predict)
    monkeypatch.setattr(hub, "load_truth", load_truth)
    monkeypatch.setattr(hub, "_clip_seconds", lambda d: 30.0)
    return hub


def test_hub_headline_prefers_scenarios_and_predicts_first(tmp_path, monkeypatch):
    calls: list[str] = []
    hub = _fake_phase(monkeypatch, calls)
    manifest, ref = _manifest(tmp_path, {"S0": True, "S1": True, "S3": True})
    res = hub.run_hub(scans=tmp_path / "s.jsonl", clips=tmp_path, spec=tmp_path / "spec.json", truth_dir=ref,
                      clip_start="2026-10-28T14:32:07+08:00", scenario="control_flow", out_dir=tmp_path / "out",
                      manifest=manifest)  # fmt: skip
    assert calls == ["predict"] * 3 + ["truth"] * 3  # S1, S3, control: every prediction before any reference file
    assert res["headline"]["source"] == "scenarios" and res["headline"]["caveat"] is None
    assert res["headline"]["scenarios"] == ["S1", "S3"] and {c["scenario"] for c in res["cases"]} == {"S1", "S3"}
    assert res["aggregate"]["last_seen_accuracy"] == 0.0  # the scenarios can fail; here they do
    assert [s["name"] for s in res["suites"]] == ["scenarios", "control_flow"]
    assert json.loads((tmp_path / "out" / "latest.json").read_text())["headline"]["source"] == "scenarios"


def test_hub_headline_falls_back_to_control_with_caveat(tmp_path, monkeypatch):
    calls: list[str] = []
    hub = _fake_phase(monkeypatch, calls)
    manifest, ref = _manifest(tmp_path, {"S1": False, "S2": True})
    res = hub.run_hub(scans=tmp_path / "s.jsonl", clips=tmp_path, spec=tmp_path / "spec.json", truth_dir=ref,
                      clip_start="2026-10-28T14:32:07+08:00", scenario="control_flow", out_dir=tmp_path / "out",
                      manifest=manifest)  # fmt: skip
    assert res["headline"]["source"] == "control_flow" and "prove little" in res["headline"]["caveat"]
    assert "S1: renders not produced yet" in res["headline"]["caveat"]
    assert "S3, S4, S5: not in the manifest" in res["headline"]["caveat"]
    assert [s["name"] for s in res["suites"]] == ["control_flow"]


def test_hub_container_subject_without_track_is_not_scored_for_abstention(tmp_path):
    from spoor_eval.hub import HubPrediction, load_truth, score

    (tmp_path / "events_truth_S4.jsonl").write_text("\n".join(json.dumps(r) for r in [
        {"event": "container_close", "container_id": "RC-7", "true_time": "2026-10-28T14:32:09+08:00"},
        {"event": "rfid_read", "container_id": "RC-7", "true_time": "2026-10-28T14:32:15+08:00"},
        {"event": "tunnel_read", "parcel_id": "CTX9", "true_time": "2026-10-28T14:32:01+08:00"}]), encoding="utf-8")
    (tmp_path / "flow_truth_S4.json").write_text(json.dumps({"t0": "2026-10-28T14:32:07+08:00", "fps": 10,
                                                             "parcels": []}), encoding="utf-8")  # fmt: skip
    spec = {"building": {"footprint_m": [60, 40]}, "zones": [], "cameras": []}
    t = load_truth(tmp_path, ["RC-7"], spec=spec, clip_cameras=[], clip_start="2026-10-28T14:32:07+08:00",
                   scenario="S4")["RC-7"]  # fmt: skip
    assert t.last_event == "rfid_read" and not t.track_known and t.inside_building is None
    pred = HubPrediction(parcel="RC-7", case_id="c", status="abstained", last_seen_time="2026-10-28T14:32:15+08:00",
                         last_seen_event="rfid_read", last_seen_device="SP-DOCK", last_seen_class="fixed_scan",
                         later_location_claims=0, left_area="yes", no_coverage_intervals=None, answer="", latency_s=0.0,
                         subject_kind="container")  # fmt: skip
    s = score(pred, t)
    assert s["last_seen_correct"] and s["abstention"].startswith("claimed") and not s["false_left_hub"]
    s2 = score(HubPrediction(**{**pred.__dict__, "left_area": "unknown"}), t)
    assert s2["abstention"].startswith("not scored") and not s2["abstention_correct"]


def test_seed_maps_induction_line_b_to_its_own_scan_points():
    """Hub line B (30 Oct): tunnel / induction records carry SP-TUNNEL-B / SP-INDUCT-B; the seed must not fold them into
    line A, and the default input case stays a line-A parcel."""
    from spoor_eval.hub import _seed_module

    seed = _seed_module()
    spec = json.loads((ROOT / "assets" / "hub" / "hub_spec.json").read_text(encoding="utf-8"))
    ids = {p["id"] for p in spec["scan_points"]}
    if "SP-TUNNEL-B" not in ids:
        pytest.skip("site plan without line B")
    t = "2026-10-28T14:32:07.100+08:00"
    lines = [json.dumps(r) for r in [
        {"time": t, "event": "tunnel_read", "scan_point": "SP-TUNNEL-B", "parcel_id": "CTXB1", "clock_domain": "clkd_wcs"},
        {"time": t, "event": "induct_to_carrier", "scan_point": "SP-INDUCT-B", "carrier": 7, "parcel_id": "CTXB1",
         "clock_domain": "clkd_wcs"},
        {"time": t, "event": "tunnel_read", "scan_point": "SP-TUNNEL", "parcel_id": "CTXA1", "clock_domain": "clkd_wcs"},
        {"time": t, "event": "tunnel_read", "parcel_id": "CTXA2", "clock_domain": "clkd_wcs"},  # older log: no point
    ]]  # fmt: skip
    rows, skipped = seed.convert_scans(lines, {"clkd_wcs": "dom_wcs"}, spec)
    assert [(r["device_id"], r["read_point_zone_id"]) for r in rows] == [
        ("SP-TUNNEL-B", "zone_Z05"), ("SP-INDUCT-B", "zone_Z05"), ("SP-TUNNEL", "zone_Z04"), ("SP-TUNNEL", "zone_Z04")]
    assert rows[1]["device_kind"] == "sorter_plc" and not skipped
    assert seed.auto_case_parcel(rows + [rows[0], rows[1]]) == "CTXA1"  # line B never takes the default case
    with pytest.raises(ValueError):
        seed.convert_scans([json.dumps({"time": t, "event": "tunnel_read", "scan_point": "SP-NOPE", "parcel_id": "X",
                                        "clock_domain": "clkd_wcs"})], {"clkd_wcs": "d"}, spec)  # fmt: skip
