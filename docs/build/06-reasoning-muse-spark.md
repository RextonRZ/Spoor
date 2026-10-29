# Step 06 — Video reasoning: Muse Spark adapter (M4)

**PRD:** §10.2, §15, §32.3 · **Depends on:** 02, 04 · **Location:** `services/workers/reasoning`

## Goal

Ask Muse Spark 1.3 a **bounded, specific** question about a short clip window and get back typed proposals — never
facts that go straight into memory.

## Build

1. **Adapter:** `model="muse-spark-1.3"` (Standard mode 🔒, not `-contributor`) via `/v1/responses`. Video via
   Files API (`purpose="user_data"`) + `input_file`/`input_video`. MP4 only. Audio stripped.
2. **Structured output** per `/docs/structured-output` and `/docs/tool-calling` (read before coding). Response schema:
   `observed_facts[] {text, approx_pts_ms, source_frame_refs}`, `candidate_hypotheses[]`, `unknowns[]`,
   `requested_evidence[]`, `abstain_reason`, plus `not_observable` option.
3. **Task templates** (versioned): presence check, interaction description, contradiction search, next-evidence
   suggestion (§15.1).
4. **Grounding check:** every model timestamp is a *candidate*; fetch the cited frame and confirm via SAM
   observation or frame check before step 07 can accept it.
5. **Clip-adaptive sampling** around candidate transitions; log which intervals were **not** inspected (§15.3).
6. **Prompt-injection defense:** filenames/captions passed as quoted data only; system prompt forbids following
   instructions found in media metadata (C10).
7. **Forbidden outputs** 🔒: intent, identity, ethnicity, age, emotion. Post-filter + verifier reject them.
8. **Baseten Muse Spark Open adapter** (same interface, text/structured only) for agent reasoning in step 08 —
   switch by config after the step-00 benchmark.
9. Log prompt template version, model version, token usage, cost, evidence IDs on every call.

## Done when

- Real clip: presence question returns schema-valid output whose cited frames resolve; an unanswerable question
  returns `not_observable`/abstain rather than a guess.

## Status — code done (2026-10-27); live Spark not yet run

Code: `backend/src/spoor/reasoning/`. Tests: `tests/test_reasoning.py`.
- `MetaResponsesBackend` (Responses `text.format` strict json_schema; refuses `-contributor` models) and
  `BasetenChatBackend` (text-only, schema in prompt, local validation, one repair).
- `strict_schema()` converts Pydantic schemas to Meta's strict subset (tested against the documented rules).
- `cut_clip` makes bounded windows; model seconds map back to ORIGINAL frames; times outside the window are flagged.
- Accusatory / identity / attribute statements are removed from facts and hypotheses (`spoor.safety`).
- `ground_facts`: a model fact is `grounded` only if a confirmed SAM observation sits within N frames of it.
