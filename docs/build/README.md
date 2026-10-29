# Spoor — Build Plan (step by step)

The full spec is [Spoor_Meta_Hackathon_PRD_v3.md](../../Spoor_Meta_Hackathon_PRD_v3.md). This folder splits it into
ordered development steps. Each step file says **what to build, which PRD sections it implements, what it depends on,
and how we know it is done**. The PRD stays the source of truth; when a step file and the PRD disagree, the PRD wins
(and we fix the step file).

Markers follow the PRD: 🔒 invariant · 🧭 default · 🎨 open.

## Order

| # | Step | PRD | Depends on | Needs API key? | Status |
|---|---|---|---|---|---|
| 00 | [Repo setup & provider smoke tests](00-setup-and-smoke-tests.md) | §0.4, §10.5, §32 | — | Yes (smoke tests only) | Scaffold done · smoke tests need keys |
| 01 | [Evidence contracts (M0)](01-contracts.md) | §11 | 00 | No | **Done** |
| 02 | [Media ingest & provenance (M1)](02-media-ingest.md) | §12, §7.3, §8.3 | 01 | No | **Done** |
| 03 | [Site, cameras & floor calibration (M2)](03-calibration.md) | §13.1–13.3, §13.5 | 01 | No | **Done** (code) · real-room numbers pending |
| 04 | [Evidence memory store (M5)](04-evidence-store.md) | §16 | 01 | No | **Done** (SQLite tested; Postgres untested) |
| 05 | [Perception — SAM 3.1 adapter (M3)](05-perception-sam.md) | §10.3, §14.1–14.2 | 02, 04 | Yes | **Done** (code) · live SAM untested |
| 06 | [Video reasoning — Muse Spark adapter (M4)](06-reasoning-muse-spark.md) | §10.2, §15 | 02, 04 | Yes | **Done** (code) · live Spark untested |
| 07 | [Verification & uncertainty engine (M7)](07-verification.md) | §17.4, §18 | 03, 04 | No | **Done** |
| 08 | [Multi-agent investigation (M6)](08-agents.md) | §17 | 05, 06, 07 | Yes | **Done** (code) · live agents untested |
| 09 | [API, audit, reports & access (M11)](09-api-reports.md) | §22, §25, §7.4 | 04, 08 | No | **Done** |
| 10 | [Evaluation harness (M10)](10-evaluation.md) | §21, §8.1 | 08 | Yes | **Harness done** · no real results yet |
| 11 | [Optional extensions](11-optional-extensions.md) | §13.4, §14.3, §20 | 03, 05 | Partly | **Done** (code, flags off) |
| 12 | [Frontend (deferred)](12-frontend.md) | §19, §23 | 09 | No | **On hold — owner designing** |
| 14 | [Parcel-hub pivot: scan evidence](14-parcel-pivot.md) | Addendum A, research report | 01–09 | No | **Core done** (items 1–3, 5; 6 partial) |
| 13 | [Demo footage & submission](13-demo-and-submission.md) | §5, §27, §28 | all | — | Todo |

Steps 01–04 need no API key and can be built and unit-tested immediately. Steps 05–06 are where the riskiest
assumptions live (PRD §0.3), so their smoke tests in step 00 should happen as early as credits allow.

## Working rules for every step

- 🔒 Never inject ground-truth labels or expected answers into inference (PRD §8.1).
- 🔒 No fabricated detections, traces, or metrics. If a model call is unavailable, return `analysis_unavailable`.
- Record design changes in `docs/DECISIONS.md` and every new dependency in `docs/DEPENDENCIES.md`.
- Every step ends with tests that pass locally before the next step starts relying on it.

## Where things stand (2026-10-27)

183 backend tests pass (`cd backend && uv run pytest`). A logic review on 2026-10-28 found and fixed 21 issues (see `docs/IMPROVEMENTS.md`). Everything that needs a Meta/Baseten key or real footage is
built and tested against fixtures, **not** against the live services. The first real run is the step-00 smoke tests.
