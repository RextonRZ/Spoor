"""Evaluation runner (PRD §21).

    cd backend
    uv run python ../ml/evaluation/run.py --dataset ../ml/evaluation/datasets/<name> --variants A0,A1,A2,A3

Dataset layout:
    site.json                    Site record (measured room)
    scenarios/<id>.json          ScenarioInputs  — the ONLY thing variants see
    ground_truth/<id>.json       GroundTruth     — loaded by the scorer after all predictions exist
    media/...                    clips referenced by scenarios
"""

import argparse
import json
import shutil
import tempfile
import traceback
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .metrics import aggregate, score
from .schema import GroundTruth, Prediction, ScenarioInputs
from .variants import VARIANTS, Backends


def backends_from_settings() -> Backends:
    from spoor.api.services import Services
    from spoor.config import get_settings

    s = get_settings()
    tmp = Path(tempfile.mkdtemp(prefix="spoor_eval_backends_"))
    svc = Services.from_settings(s.model_copy(update={"data_dir": tmp, "database_url": "sqlite:///:memory:"}))
    return Backends(sam=svc.sam, spark=svc.spark, spark_client=svc.spark_client, agent=svc.agent)


def run(dataset: Path, variants: list[str], *, split: str | None, backends: Backends, out_dir: Path) -> dict:
    scenarios = [ScenarioInputs.model_validate_json(p.read_text(encoding="utf-8"))
                 for p in sorted((dataset / "scenarios").glob("*.json"))]  # fmt: skip
    if split:
        scenarios = [s for s in scenarios if s.split == split]

    # Phase 1: predictions. Ground truth is not loaded yet.
    predictions: list[Prediction] = []
    for sc in scenarios:
        for v in variants:
            work = Path(tempfile.mkdtemp(prefix=f"spoor_eval_{sc.scenario_id}_{v}_"))
            try:
                predictions.append(VARIANTS[v](sc, dataset, work, backends))
            except Exception as e:  # noqa: BLE001 — record failures as failures, never as answers
                predictions.append(Prediction(scenario_id=sc.scenario_id, variant=v, status="error",
                                              detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()[-800:]}"))
            finally:
                shutil.rmtree(work, ignore_errors=True)

    # Phase 2: scoring against separately stored labels.
    truth = {t.scenario_id: t for t in (GroundTruth.model_validate_json(p.read_text(encoding="utf-8"))
                                        for p in (dataset / "ground_truth").glob("*.json"))}  # fmt: skip
    scores = [score(p, truth[p.scenario_id]) for p in predictions if p.scenario_id in truth]
    by_variant = {v: aggregate([s for s in scores if s.variant == v]) for v in variants}
    result = {
        "run_at": datetime.now(UTC).isoformat(), "dataset": dataset.name, "split": split,
        "variants": by_variant, "scores": [asdict(s) for s in scores],
        "predictions": [p.model_dump(mode="json") for p in predictions],
        "note": "Measured on the listed scenarios only; see docs/EVALUATION.md for failures and limitations.",
    }  # fmt: skip
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "latest.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    (out_dir / "latest.md").write_text(markdown_table(by_variant), encoding="utf-8")
    return result


def _fmt(v) -> str:
    return "—" if v is None else f"{v:.2f}" if isinstance(v, float) else str(v)


def markdown_table(by_variant: dict) -> str:
    cols = ["n", "unavailable", "last_seen_accuracy", "median_time_error_s", "zone_accuracy", "left_area_accuracy",
            "event_precision", "event_recall", "spatial_error_median_m", "abstention_precision", "abstention_recall"]
    lines = ["| variant | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    lines += [f"| {v} | " + " | ".join(_fmt(m.get(c)) for c in cols) + " |" for v, m in by_variant.items()]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--variants", default="A0,A1,A2,A3")
    ap.add_argument("--split", choices=["dev", "holdout"], default=None)
    ap.add_argument("--out", type=Path, default=Path("data/evaluation"))
    args = ap.parse_args()
    result = run(args.dataset, args.variants.split(","), split=args.split, backends=backends_from_settings(),
                 out_dir=args.out)  # fmt: skip
    print(markdown_table(result["variants"]))


if __name__ == "__main__":
    main()
