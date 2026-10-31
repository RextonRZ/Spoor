# F-022 — J1 smoke tests with Rexton's keys (Meta SAM 3.1 / Spark 1.3 / Wonder 1.0 + Baseten Muse Spark Open)

From the frontend agent. Keys stayed in `backend/.env`: never printed, logged or copied. No request headers are saved.

## 1. Changed since last request
- **J1 smoke tests run.** All passed. The table is filled in `docs/META_MODEL_USAGE.md`, and estimates (before) and
  actuals (after) are in log.md.

  | Test | Result | Latency | Cost |
  |---|---|---|---|
  | List models | sam-3.1, muse-spark-1.3, muse-wonder-1.0 all visible | <1 s | free |
  | SAM 3.1 image ("box") | 3 parcels, conf 0.62–0.66, masks decoded | 4.7 s | ≈ $0.0025 |
  | SAM 3.1 video, 60 frames, "cardboard box" | **0 records** | 9.3 s | ≈ $0.012 |
  | SAM 3.1 video, 60 frames, "box" | 2 objects tracked (32 + 26 frames, ~8 px/frame along the belt) | 7.3 s | ≈ $0.012 |
  | Spark 1.3 video question | correct: the red parcel on the lower straight, 0–5.3 s; exit "not_observable" | 16.3 s | ≈ $0.014 |
  | Spark 1.3 strict json_schema | valid; cites only real ids; abstains on "did it leave" | 14.0 s | ≈ $0.009 |
  | Wonder 1.0 investigation plan (new `scripts/smoke/wonder_plan.py`, fed the real `/journey` + `/missing-moment`) | valid plan: CAM_07 then CAM_10 at the divert window (the only cameras with footage); 0 dangling citations; no location claimed | 23.7 s | ≈ $0.067 |
  | Baseten `meta-models/muse-spark-open-1026` | 2/2 PASS (answer + abstain); reasoning arrives in `reasoning_content` (~2k chars) and is kept apart from the JSON answer (J2a groundwork) | 3.9 / 2.4 s | ≈ 1.8k tokens |

  - Total spend: Meta ≈ $0.12 (cap $60), Baseten ≈ 1.8k tokens (cap $50). The running total is in FOR_REXTON.md.
  - Open-weights proof (redacted, with response ids): `docs/open_weights_proof/2026-10-31_j1_baseten_smoke.json`.
  - Answers to the doc's open questions:
    - Spark samples short clips sparsely: ~270 input tokens per second of 960×540 video.
    - All Muse models spend most output tokens on reasoning (67–95 %), so budget by output.
    - SAM text prompts must be short generic nouns.
- **I3 honesty fix found while preparing the keyed run.** A clip with SAM tracks of every box would have turned
  "subject not confirmed" into `not_seen`. Now, when a clip is analysed but has a track overlapping the expected region
  in the window, and that track is not linked to the subject, the result is `unresolved_candidates` (with the track
  ids). There is no negative observation until an identity decision is made. Test added (tests: 11 forensics ✓).

## 2. Check these
- `docs/META_MODEL_USAGE.md` (smoke-test log)
- `docs/open_weights_proof/2026-10-31_j1_baseten_smoke.json`
- `backend/scripts/smoke/wonder_plan.py` (new) and `baseten_open.py` (now splits reasoning from the answer)
- `backend/src/spoor/forensics/missing.py` (`_candidates`, `unresolved_candidates`), `backend/tests/test_forensics.py`
- Raw outputs: `backend/scripts/smoke/out/*_20261030T17*.json` (git-ignored)

## 3. Known issues: J1 step 4 ("default case once with keys vs no-key") is not run yet, on purpose
- A keyed run today would add SAM tracks of every parcel, but nothing links a track to the case parcel. The backend has
  no scan-anchored association: the only link statuses are same-camera verification, human review, or a cross-camera
  candidate.
- So `/last-seen`, the journey and the eval answer would be identical to no-key, at ≈ $0.25 of SAM frames on the old
  white-floor QA clips.
- The meaningful comparison needs:
  1. the S2 final render;
  2. the identity link: a SAM box prompt at the read point's expected region at scan time (the I1 identity chain),
     recorded as a typed scan-anchored association;
  3. then one keyed run of S2 vs no-key, scored by `ml/evaluation`.
- I'll do that right after I1, and estimate before running.

## 4. Questions
1. OK to add a typed association status `scan_anchored` for the identity link? SAM box prompt at the tunnel/divert read
   point at scan time; tracks the same camera only; never cross-camera; shown as "identified by tunnel read". Or must
   every first link be human-confirmed?
