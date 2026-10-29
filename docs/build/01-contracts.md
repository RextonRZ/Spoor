# Step 01 — Evidence contracts (M0)

**PRD:** §11, §13.5, §18.1, §27.1 · **Depends on:** 00 · **Package:** `packages/contracts`

## Goal

One source of truth for every ID and record shape. Everything else (store, agents, API, future frontend) imports
these types. Invalid or dangling IDs are rejected at the boundary.

## Build

1. Pydantic v2 models for the canonical entities (§11.1): `Site`, `Camera`, `MediaAsset`, `FrameRef`, `Track`,
   `RawObservation`, `SpatialEstimate`, `MultiView3DEstimate` (schema only), `Zone`, `Event`, `Hypothesis`,
   `VerifiedFinding`, `CaseRevision`, `SensorEvent`.
2. Typed ID prefixes (`obs_`, `loc_`, `hyp_`, `finding_`, …) with validators; IDs generated server-side only.
3. Enums:
   - `EvidenceLabel`: `observed | estimated | hypothesized | unknown | contradicted` (§18.1)
   - `SpatialMode`: `multiview_xyz | floor_xy | anchored_height | zone_only | image_only | unknown` (§13.5)
   - `HypothesisStatus` transitions `proposed → evaluated → supported | contradicted | insufficient_evidence` (§11.3)
   - `AssetKind`: `original | annotated_derivative | estimated_geometry | illustrative` (§7.3)
   - `SourceType`: `video | sensor_real | sensor_simulated | human_annotation`
   - `RigState`: `uncalibrated | calibrating | validated_floor_only | validated_multiview_3d | invalidated`
4. Time is explicit (§11.3): `pts_ms`, `frame_index`, `camera_clock_utc`, `normalized_utc`, `sync_offset_ms`,
   `time_uncertainty_ms`.
5. Field-level rules: `world_xyz_m` / `floor_xy_m` never hold pixels; `confidence_raw` is model-scoped and never
   compared across models; `confidence_calibrated` stays `null` until calibration exists.
6. Agent I/O envelopes (§17.2): `AgentRequest`, `AgentResponse` with `claims[]` each carrying `evidence_ids`.
7. Export JSON Schema (`scripts/export_schemas.py`) so the frontend can generate TS types later.

## Invariants 🔒

- A `VerifiedFinding` with empty `observation_ids` fails validation.
- An LLM-facing schema has no field that can set `verification_status` — only the verifier service sets it.
- Hypothesis status changes are append-only records with actor + evidence.

## Done when

- Unit tests: valid examples from PRD §11.2 parse; source-free finding rejected; pixel-in-metres rejected;
  illegal status transition rejected.
- JSON Schemas exported under `packages/contracts/schemas/`.

## Status — done (2026-10-27)

Code: `backend/src/spoor/contracts/` (`base`, `enums`, `site`, `media`, `observations`, `case`, `agents`).
Tests: `backend/tests/test_contracts.py`. Schemas: `backend/schemas/*.schema.json` via `scripts/export_schemas.py`.

Notes: IDs use type prefixes (`obs_`, `loc_`, `cam_`, `media_`, …) so the PRD's illustrative IDs (`camA_clip03`)
become e.g. `media_…`. SAM boxes are stored in **pixels of the displayed frame** plus frame size (SAM's native
format); the normalized box is derived. Status changes to `supported/contradicted/insufficient_evidence` are
rejected unless the actor is the verifier service or a human.
