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
