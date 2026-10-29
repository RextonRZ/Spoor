# Step 07 — Verification & uncertainty engine (M7)

**PRD:** §11.3, §17.4, §18 · **Depends on:** 03, 04 · **Location:** `packages/agents/verification`

## Goal

A mostly **deterministic** gate that decides whether a proposed claim may become a finding. The LLM verifier agent
(step 08) adds judgment on top of this, never instead of it.

## Build — programmatic checks

1. **Citation resolution:** every evidence ID exists, is not deleted/expired, and its frame/time matches the claim.
2. **Physical consistency:** same object in two impossible places at one synchronized time; implied speed above a
   plausible limit; route crossing walls / outside site connectivity.
3. **Temporal consistency:** clock-offset uncertainty too large for the ordering claimed → `insufficient_evidence`.
4. **Transfer claims:** require before/after visibility plus contact evidence; otherwise hypothesis only (§14.2).
5. **Sensor sanity:** sensor event vs video contradiction is flagged, not resolved by trusting either (C08).
6. **Overreach filter:** "left the building", identity, intent, guilt → `unsupported` 🔒.
7. **Gap rule:** a path between two observations with an unobserved interval is `hypothesized`, never `observed`.

## Outputs

`supported | contradicted | insufficient_evidence | unsupported` + reasons + checked evidence IDs. Status changes are
written by this service only (agents cannot set them) and logged with actor and evidence.

## Confidence

Qualitative labels (`observed/estimated/possible/unverified`) until calibrated on holdout data — no synthetic
percentages (§18.3).

## Done when

- Table-driven tests covering every check above, including C02, C05, C08, C09 from the PRD scenario matrix.

## Status — done (2026-10-27)

Code: `backend/src/spoor/verification/`. Tests: `tests/test_verification.py` (incl. C02, C05, C08, C09).
Typed claims: `last_seen`, `presence`, `transition`, `exit`, `transfer`, `order`. `Verifier.decide()` writes
append-only status changes as `verifier_service`; `promote()` stores findings only for SUPPORTED claims.
A test fixture with a physically impossible ~5 m/s carry was correctly rejected during development.
