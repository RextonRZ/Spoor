# Step 10 — Evaluation harness (M10)

**PRD:** §8.1, §21 · **Depends on:** 08 · **Location:** `ml/evaluation`

## Goal

Test the frontier claim honestly: does evidence graph + bounded agents beat a plain "ask Muse Spark about the video"
baseline? Report wins **and** losses.

## Build

1. **Ground-truth store** separate from runtime (different directory/DB, never importable by agents) 🔒.
   Annotation fields: reviewer, interval, frame ID, coordinates, annotation confidence.
2. **Scenarios** C01–C10 core (C11–C14 only if step 11 multi-view is attempted). Split holdouts by incident.
3. **Ablations** (§21.4): A0 Spark direct · A1 + SAM tracks · A2 + spatial graph · A3 + agents/verifier.
4. **Metrics** (§21.3): last-seen accuracy (time + zone), event P/R, spatial error (m), citation validity,
   unsupported-claim rate, abstention quality, active-evidence benefit, cost/latency per case.
5. **Blind claim review:** a human scores whether each cited frame supports its claim (simple CLI/CSV workflow).
6. **Runner:** `uv run python -m ml.evaluation.run --variant A3 --scenarios C01..C10` → results JSON + markdown table
   into `docs/EVALUATION.md`. Fixed seeds where applicable.

## Done when

- Table of real numbers for A0–A3 on the recorded scenarios, plus written failure cases. If A3 ≤ A2, say so and
  simplify (§21.4).

## Status — harness done (2026-10-27); no real results

Code: `ml/evaluation/spoor_eval/` (`schema`, `metrics`, `variants`, `run`). Tests: `backend/tests/test_evaluation.py`.
Inputs (`scenarios/`) and labels (`ground_truth/`) are separate files; predictions are produced before labels are
loaded; a test fails if runtime code mentions the evaluation package. Dataset format: `ml/evaluation/datasets/README.md`.

## Parcel hub, no-key answers (2026-10-30, QUEUE F3)

`ml/evaluation/spoor_eval/hub.py` + `ml/evaluation/run_hub.py`. Phase 1 runs the real backend in-process (TestClient, no
model keys) on inputs only (hub_spec, synthetic clips, `events_scan_simulated.jsonl` through the same loader as the web
seed) and creates one input case per identified parcel. Phase 2 reads evaluator-only truth
(`assets/hub/build/truth/events_truth.jsonl`, `flow_truth.json`) after every prediction exists. Scores: last-seen event +
time, abstention after the last scan (correct / "missed: visible on CAM_x, needs SAM"), false "left the hub".
Results go to `<DATA_DIR>/evaluation/latest.json` and show on the Operator page. Boundary tests in
`backend/tests/test_evaluation.py`: the runtime package and `frontend/src` never name truth files; `predict()` has no
truth argument. Run: `cd backend && uv run python ../ml/evaluation/run_hub.py --out ../frontend/.local/backend-data/evaluation`.

**Headline (review 007 #4).** On the control flow "last seen 100 %, median 0.0 s" is expected (the scan log is the
sorter's own clock) and proves little. `run_hub` therefore reads `ml/evaluation/scenarios/manifest.json` and scores the D
scenarios S1–S5 that have BOTH renders (`CAM_*.mp4` in the scenario's clips folder) and evaluator files
(`scenario_<S>.json`, `events_truth_<S>.jsonl`, `flow_truth_<S>.json`), one input case per scenario subject (the
manifest's waybill or cage id, an input). Those are the headline. The control flow (the S0 renders once they exist,
else the QA clips) runs as a sanity check and becomes the headline only as a fallback, with the caveat written into
`latest.json` and shown on the Operator page, plus the reason each scenario is still waiting. All predictions run before
any evaluator file is opened (tested). Container subjects (S4 roll cage) are scored on last seen; abstention is "not
scored" when the reference data has no track for them.
