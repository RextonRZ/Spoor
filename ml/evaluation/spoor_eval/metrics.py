"""Metrics (PRD §21.3). Pure functions over predictions + ground truth; nothing here calls a model."""

import csv
import math
import statistics
from dataclasses import dataclass
from pathlib import Path

from .schema import GroundTruth, Prediction, TruthEvent


@dataclass
class ScenarioScore:
    scenario_id: str
    variant: str
    status: str
    last_seen_correct: bool | None  # None when the scenario is unanswerable
    last_seen_time_error_s: float | None
    zone_correct: bool | None
    spatial_error_m: float | None
    left_area_correct: bool
    abstained: bool
    should_abstain: bool
    event_tp: int
    event_fp: int
    event_fn: int


def _iou(a: TruthEvent, b: TruthEvent) -> float:
    inter = (min(a.end_utc, b.end_utc) - max(a.start_utc, b.start_utc)).total_seconds()
    union = (max(a.end_utc, b.end_utc) - min(a.start_utc, b.start_utc)).total_seconds()
    return max(0.0, inter) / union if union > 0 else float(a.start_utc == b.start_utc)


def match_events(pred: list[TruthEvent], truth: list[TruthEvent], min_iou: float = 0.3) -> tuple[int, int, int]:
    """Greedy one-to-one matching by kind and temporal IoU."""
    used, tp = set(), 0
    for p in pred:
        best, best_iou = None, min_iou
        for i, t in enumerate(truth):
            if i in used or t.kind != p.kind:
                continue
            if (iou := _iou(p, t)) >= best_iou:
                best, best_iou = i, iou
        if best is not None:
            used.add(best)
            tp += 1
    return tp, len(pred) - tp, len(truth) - tp


def score(pred: Prediction, truth: GroundTruth) -> ScenarioScore:
    abstained = pred.status in ("abstained", "unavailable", "error") or pred.last_seen_utc is None
    should_abstain = not truth.answerable
    ls_ok = time_err = zone_ok = spatial = None
    if truth.answerable and truth.last_seen_utc is not None:
        if abstained:
            ls_ok = False
        else:
            time_err = abs((pred.last_seen_utc - truth.last_seen_utc).total_seconds())
            zone_ok = (pred.last_seen_zone == truth.last_seen_zone) if truth.last_seen_zone else None
            ls_ok = time_err <= truth.time_tolerance_s and zone_ok is not False
            if pred.last_seen_xy_m and truth.last_seen_xy_m:
                spatial = math.dist(pred.last_seen_xy_m, truth.last_seen_xy_m)
    tp, fp, fn = match_events(pred.events, truth.events)
    return ScenarioScore(pred.scenario_id, pred.variant, pred.status, ls_ok, time_err, zone_ok, spatial,
                         pred.status not in ("unavailable", "error") and pred.left_area == truth.left_area,
                         abstained, should_abstain, tp, fp, fn)  # fmt: skip


def _rate(num: int, den: int) -> float | None:
    return num / den if den else None


def aggregate(scores: list[ScenarioScore]) -> dict:
    answerable = [s for s in scores if not s.should_abstain]
    unanswerable = [s for s in scores if s.should_abstain]
    tp, fp, fn = (sum(getattr(s, k) for s in scores) for k in ("event_tp", "event_fp", "event_fn"))
    spatial = [s.spatial_error_m for s in scores if s.spatial_error_m is not None]
    abst = [s for s in scores if s.abstained]
    return {
        "n": len(scores),
        "unavailable": sum(s.status == "unavailable" for s in scores),
        "last_seen_accuracy": _rate(sum(bool(s.last_seen_correct) for s in answerable), len(answerable)),
        "median_time_error_s": statistics.median(e) if (e := [s.last_seen_time_error_s for s in scores
                                                              if s.last_seen_time_error_s is not None]) else None,
        "zone_accuracy": _rate(sum(s.zone_correct is True for s in scores),
                               sum(s.zone_correct is not None for s in scores)),
        "left_area_accuracy": _rate(sum(s.left_area_correct for s in scores), len(scores)),
        "event_precision": _rate(tp, tp + fp), "event_recall": _rate(tp, tp + fn),
        "spatial_error_median_m": statistics.median(spatial) if spatial else None,
        "spatial_error_p95_m": sorted(spatial)[max(0, math.ceil(0.95 * len(spatial)) - 1)] if spatial else None,
        # Abstention quality: of the times we abstained, how often was abstaining right; of the times we should
        # have abstained, how often did we.
        "abstention_precision": _rate(sum(s.should_abstain for s in abst), len(abst)),
        "abstention_recall": _rate(sum(s.abstained for s in unanswerable), len(unanswerable)),
    }  # fmt: skip


def citation_review(csv_path: Path) -> dict:
    """Blind human review (PRD §21.5): one row per claim with columns
    claim_id, variant, supported (yes/no/partial), cited (yes/no). Reviewers do not see which variant made it."""
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    by_variant: dict[str, dict] = {}
    for r in rows:
        v = by_variant.setdefault(r["variant"], {"claims": 0, "unsupported": 0, "cited": 0, "cited_supported": 0})
        v["claims"] += 1
        v["unsupported"] += r["supported"] == "no"
        if r["cited"] == "yes":
            v["cited"] += 1
            v["cited_supported"] += r["supported"] == "yes"
    return {k: {"unsupported_per_100_claims": 100 * v["unsupported"] / v["claims"],
                "citation_validity": _rate(v["cited_supported"], v["cited"])} for k, v in by_variant.items()}
