# New work created during the hackathon

Everything in this repository was started on 2026-10-27, during the Meta Global AI Developer Hackathon 2026.
No pre-existing project code is reused. Third-party libraries are listed in `DEPENDENCIES.md` and are not claimed
as new work.

| Date | Area | What was built |
|---|---|---|
| 2026-10-27 | Planning | PRD split into step-by-step build plan (`docs/build/`) |
| 2026-10-27 | Backend scaffold | `uv` project, config, `/healthz`, provider smoke-test scripts |
| 2026-10-27 | Contracts (step 01) | Pydantic evidence contract with invariant validators, JSON Schema export, 28 tests |
| 2026-10-27 | Ingest (step 02) | Hash-on-copy storage, ffprobe timing flags, aligned H.264 proxy, frame-exact extraction, 14 tests |
| 2026-10-27 | Spatial (step 03) | Validated floor homography, projection fallback chain, frame transforms, clock sync, 18 tests |
| 2026-10-27 | Store (step 04) | Append-only evidence store with DB-level immutability, projections, spatiotemporal queries, invalidation/purge |
| 2026-10-27 | Perception (step 05) | SAM 3.1 adapter, prompt safety, parser integration, caching, cost ledger |
| 2026-10-27 | Reasoning (step 06) | Muse Spark / Baseten structured backends, clip windows, safety filter, fact grounding |
| 2026-10-27 | Verification (step 07) | Deterministic claim verifier (citations, speed, ordering, gaps, exit, transfer, overreach) |
| 2026-10-27 | Agents (step 08) | Bounded agent runtime, typed tools with scope checks, orchestrator, deterministic answer |
| 2026-10-27 | API (step 09) | FastAPI with RBAC, signed links, jobs/SSE, audit, report export/approval, Docker files |
| 2026-10-27 | Evaluation (step 10) | Ablation harness A0–A3, metrics, blind-review scoring, ground-truth firewall |
| 2026-10-27 | Extensions (step 11) | Sensor CSV import, gated cross-camera association, gated multi-view triangulation |
| 2026-10-28 | Review fixes | 21 logic/security/performance fixes with regression tests (docs/IMPROVEMENTS.md) |
| 2026-10-28 | Demo support | Revision diff, replay endpoint, annotated derivative frames, operator trace, change-detection baseline |
| 2026-10-28 | Parcel pivot | Deep research report; ScanEvent/identifier/container/alias/clock-domain model; scan import; facility-visit and graded last-seen logic; parcel API routes; 22 tests |
