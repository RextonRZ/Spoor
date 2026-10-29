# Step 04 — Evidence memory store (M5)

**PRD:** §16, §11.3, §7.1 (retention/deletion) · **Depends on:** 01 · **Location:** `services/api/store`

## Goal

A durable, event-sourced record of observations, estimates, hypotheses and findings that can answer "when was
object A last **visibly confirmed**?" without asking an LLM.

## Build

1. **Database:** PostgreSQL (PRD default). 🧭 For the first local build, SQLAlchemy with SQLite is acceptable behind
   the same repository interface; switch to Postgres via Docker Compose before demo. Record in `DECISIONS.md`.
2. **Immutable tables:** `source_media`, `raw_observation` (no UPDATE path).
3. **Versioned tables:** `spatial_estimate`, `track_association`, `calibration`.
4. **Append-only logs:** `event`, `hypothesis_status_change`, `audit_log` (actor, action, before/after, reason).
5. **Projections:** current case state rebuilt from the event log; `case_revision_id` on every change.
6. **Core queries (deterministic tools for agents):**
   - `last_confirmed(object_instance_id)` → latest `observed` observation + frame ref
   - `transitions(object, t1, t2)`; `unobserved_intervals(zone | camera, t1, t2)`
   - `claims_relying_on_inferred_links(case)`; `world_state_at(case, t)`
7. **Object state machine** (§16.3): `unobserved → visible → partially_occluded → out_of_view → visible_again`;
   never collapses gaps into continuous motion.
8. **Optimistic versioning** for concurrent agent/human edits.
9. **Deletion & retention:** delete-case cascades to derivatives/embeddings; dependent findings/reports marked
   invalid; issued reports never silently mutate (§16.4).

## Done when

- Tests: raw observations cannot be updated; replaying the event log reproduces the same projection;
  `last_confirmed` ignores hypothesized/estimated records; deleting a source invalidates dependent findings.

## Status — done (2026-10-27)

Code: `backend/src/spoor/store/` (`db`, `repository`, `queries`, `records`). Tests: `tests/test_store.py`.
- SQLAlchemy Core; SQLite locally. Append-only tables have DB triggers that abort UPDATE (tested with raw SQL).
- Every write checks referenced IDs exist; dependency edges (`refs`) drive invalidation and purge.
- Hypothesis status = projection of append-only status changes; stale writers get `ConflictError`.
- Queries: `last_confirmed`, `visibility_timeline`, `unobserved_intervals` (split at camera-coverage boundaries so
  blind spots are exact), `transitions` (observed only within one continuous span), `world_state_at`,
  `claims_relying_on_inferred_links`.
- Postgres: schema + triggers + `ON CONFLICT DO NOTHING` written but **not yet run** (Docker daemon was off).
