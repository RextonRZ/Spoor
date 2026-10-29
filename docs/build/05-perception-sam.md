# Step 05 — Perception: SAM 3.1 adapter (M3)

**PRD:** §10.3, §14.1, §14.2, §14.4 · **Depends on:** 02, 04 · **Location:** `services/workers/perception`

## Goal

Turn "track the blue equipment case in clip X" into frame-aligned `RawObservation`s with boxes, masks, per-video
track IDs, occlusion flags and full provenance.

## Build

1. **Adapter** over `POST https://api.meta.ai/v1/responses`, `model="sam-3.1"` (OpenAI SDK, `base_url` set).
   Server-side key only. Pin model ID/version from `GET /v1/models`.
2. **Prompts:** short concrete noun phrase (`"blue equipment case"`), or box/point prompt for a specific instance
   (fields per `/docs/sam/segmenting` — read before coding). Never abstract prompts like "the thief" 🔒.
3. **Parse** streamed special-token output with the documented parser/client library; keep frame index + track ID;
   map coordinates back to **original** pixel space (rotation/scale from step 02).
4. **Normalize** to `RawObservation` (`model`, `model_version`, `confidence_raw`, `quality_flags`, mask asset).
5. **Keyframe start:** segment on a high-quality keyframe, then track across the clip. Investigator can correct the
   initial target with a box/point — new observations, old ones kept (§14.1 step 6).
6. **Fallback** (§10.5 step 6): weak segmentation → ask operator for box/point → retry → else abstain.
7. **Cost & reliability:** cache by step-02 key; ledger every call; timeout = unknown completion, not blind retry.
8. **Empirical tests** on own footage: occlusion, reflections, small objects, lookalikes. Results →
   `docs/EVALUATION.md`.

## Not in this step

Cross-camera association (step 11). Floor position (step 03 consumes SAM's floor-contact point).

## Done when

- Real clip: target tracked; each observation resolves to a frame via `get_frame`; overlay matches visually.
- Recorded: latency, cost per clip-second, failure cases.

## Status — code done (2026-10-27); live SAM not yet run

Code: `backend/src/spoor/perception/`. Tests: `tests/test_perception.py`.
- `MetaSamBackend`: Files API upload (1 h expiry, deleted after) -> streamed `/v1/responses` with
  `include_confidence` + `propagation_direction` -> Meta's `meta-sam-parser`. Request shape asserted in tests.
- Parser behaviour verified from its source: wire boxes are inclusive and become half-open; masks are encoded over the
  box, so `mask_fill` = fraction of the box covered (low fill flags `partially_occluded`).
- Tests replay synthesized streams in the documented wire format through the real parser (`tests/sam_wire.py`).
- Observations cite the ORIGINAL media (proxy frame i == original frame i, enforced at ingest).
- Concept prompts reject roles/questions/lists ("the thief", "who took..."); instance prompts are pixel tokens.
- Cache by proxy hash + model + prompt; ledger records billed frames (50-frame minimum); timeout = unknown completion.
- Linking policy: tracks are linked to the case object only by an operator instance prompt (single track) or explicit
  investigator confirmation via the API.
