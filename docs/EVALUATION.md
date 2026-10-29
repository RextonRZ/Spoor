# Evaluation

**Status (2026-10-27): no results yet.** The harness exists and is tested on synthetic data; no staged footage has been
recorded and no live model has been called. Nothing below is a measured result until the table is filled from a run.

## Question being tested (PRD §21.1)

Does a persistent evidence graph plus bounded agent investigation produce more accurate, better-grounded answers than
asking a video model directly?

## Variants (PRD §21.4)

| Variant | What it is |
|---|---|
| A0 | Muse Spark 1.3 reads the clip(s) and answers in one structured reply |
| CD | Deterministic change detection on the operator-selected region (no model; PRD §1.3) |
| A1 | SAM 3.1 tracks only: latest detection, no graph, no verification |
| A2 | SAM + evidence store + deterministic verifier and orchestrator, no LLM agents |
| A3 | A2 + Evidence/Hypothesis agents |

If A3 does not beat A2, the agents are simplified or the limited benefit is explained (no invented percentages).

## Firewall

`scenarios/*.json` (inputs) and `ground_truth/*.json` (labels) are separate files and types. The runner produces every
prediction before loading any label. A test fails if runtime code under `backend/src/spoor` mentions the evaluation
package or ground truth. Target initiation (an operator box on one frame) is an investigator input, not an answer.

## Metrics

Last-seen accuracy (time within tolerance AND zone), median time error, zone accuracy, left-the-area accuracy,
event precision/recall (temporal IoU matching), spatial error median/p95 (m), abstention precision/recall, model calls,
tokens, latency. Citation validity and unsupported-claims-per-100 come from a **blind human review** CSV
(`metrics.citation_review`).

## Running

```bash
cd backend
uv run python ../ml/evaluation/run.py --dataset ../ml/evaluation/datasets/<name> --variants A0,A1,A2,A3 --split holdout
```

Writes `data/evaluation/latest.json` and `latest.md`; the API serves the latest at `GET /v1/evaluations`.

## Results

| variant | n | last-seen acc. | median time err (s) | zone acc. | left-area acc. | abstention P / R | calls |
|---|---|---|---|---|---|---|---|
| — | — | not yet run | — | — | — | — | — |

## Failure cases

To be written from real runs, including cases where Spoor is worse than a baseline.
