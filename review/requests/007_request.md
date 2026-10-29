# Request 007 — Frontend: F3 evaluation harness, F4 demo script, F5 polish (+ F1/F2 prepared, scan log v2)

From the frontend agent. (006 is reserved for the builder.)

## 1. Changed since last request
- **Scan log v2** (builder's format change, 03:58 flow run): seed maps `device_time_utc = time` (device clock of the
  record's own `clock_domain`), `record_time_utc = received_time` when present (handhelds upload ~40 min later, so they
  show as late uploads), never uses truth seconds. New kinds mapped as container / aggregation scans, not parcel reads:
  `bag_open` → `container_opened` (new `ScanEventKind`, in `CONTAINER_KINDS`, schemas + TS types regenerated),
  `bag_close` → `container_closed`, `container_add` (item_kind bag) → bag-into-cage `container_add` (opens a bag → cage
  membership), `recirculate_chute_full` → `recirculated` (reason `chute_full`). 69/69 identity/container rows imported;
  18 `bag_drop` pulses → simulated photo-eye sensor events. New backend test
  `test_bag_lifecycle_and_bag_into_cage_are_container_scans`.
- **F3 evaluation** — `ml/evaluation/spoor_eval/hub.py`, `ml/evaluation/run_hub.py`.
  Phase 1 runs the real backend in-process (TestClient, no keys) on inputs only, through the same loader as the web
  seed (`frontend/scripts/seed_nokey.py → load_inputs`), one input case per identified parcel. Phase 2 reads
  `build/truth/events_truth.jsonl` + `flow_truth.json` after every prediction exists. Per case: last-seen event + time,
  abstention after the last scan ("correct: no imported camera saw it" vs "missed: visible on CAM_x, needs SAM", using
  the mounting-plan FOV and clip times), false "left the hub". Shown on the Operator page.
  Current result (control flow, 42 cases): last seen **100 %** (median error 0.0 s, WCS is the reference clock),
  abstained after the last scan 42/42, of which **2 correct** and **40 "visible but unanalysed"** (CAM_07/CAM_10 had the
  parcel in view: SAM would be needed), **0 false "left the hub"**. Caveat on screen: the clips are QA renders from an
  earlier flow run, so the FOV check uses time + geometry only.
  Boundary tests: runtime package and `frontend/src` never name truth files; `predict()` has no truth argument; the
  existing `spoor_eval`/`ground_truth` firewall test stays. Backend pytest **211** ✓.
- **F4** — `docs/DEMO_SCRIPT.md` rewritten for the parcel hub on the real app: 8 timed steps, which click, what each
  screen proves, and a 🔑 column + "Without keys" column for every step that changes once keys are in.
- **F5 (review 005 P2)** —
  1 hypothesis links follow known conveyance (`frontend/src/lib/topology.ts`: loop runs counter-clockwise, chutes leave
  the north straight); straight only without known conveyance; still amber dashed, with a dark backing so it reads
  against the yellow loop guarding; unit-tested (never cuts through the middle of the loop).
  2 trace height: the observation's own z when the backend sends one, else the surface under it (deck 1.55 m, chute
  lip 1.0 m, floor 0.12 m). 3 recording: loading spans are cut (`scripts/make-recording.mjs` reads the spec's cut list),
  **36 s**, no skeleton dead air. 4 mobile 02 re-shot with the label clamp.
  Also fixed: drei's dashed `Line` lost its dash distances when geometry was rebuilt (now memoised + recomputed).
- **F1 prepared** — `npm run seed -- --scenarios <manifest.json>` creates one input case per scenario (question prefix
  "S3 · Wrong bag at bagging: …", its own clips + scan-log slice, separate batch). Manifest format in
  `seed_scenarios()` docstring; I need the builder to write it next to the scenario cards (parcel from the card, never
  from truth). Cases list now shows a "synthetic" chip (backend `/v1/cases` returns `footage_kinds`).
- **F2 prepared** — `tests/review/new-evidence.spec.ts` (project `new-evidence`, recorded): investigate → Operator
  imports one more camera clip → re-run → "What changed" panel. Skips until `SPOOR_NEW_CLIP` / `SPOOR_NEW_CLIP_CAMERA`
  point at a B3 clip.

## 2. Check these
- `frontend/review_pack/f3/operator_evaluation_1440.png`, `frontend/review_pack/f3/operator_evaluation_390.png`
- `frontend/review_pack/desktop/fx_16_trace_3d.png`, `fx_17_trace_plan.png` (routed hypothesis), `mobile/02_workspace_3d_overview.png`
- `frontend/review_pack/signature_interaction.mp4` (36 s)
- `docs/DEMO_SCRIPT.md`, `ml/evaluation/spoor_eval/hub.py`
- Tests: frontend typecheck ✓, lint ✓, unit 9/9 ✓, e2e 13/13 ✓ (smoke + axe AA), `next build` ✓; backend pytest 211 ✓.

## 3. Known issues
- F1/F2 final capture waits for D scenario renders and B3 clips (builder will message).
- The evaluation's "visible" test uses approximate FOV footprints (no occlusion); a parcel on the 1.5 m deck is tested
  at its floor projection. Fine for "could a camera have seen it", not for a pixel claim.

## 4. Questions
1. Scenario manifest: OK to ask the builder for `assets/hub/build/scenarios/manifest.json` in the format above (one entry
   per scenario: id, title, parcel from the card, clips dir, scan-log slice, clip start)?
