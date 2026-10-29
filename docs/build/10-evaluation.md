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
