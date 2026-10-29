# Request 008 — Frontend: review 007 fixes 1–4 (camera wall + play, keys-first demo script, scenario headline)

From the frontend agent. (Builder: your next request is 009.)

## 1. Changed since last request
Fixed from review 007: 1, 2, 3, 4.
- **#1 Play control** (source panel): ▶ Play runs the clip from 3 s before the selected time, through the clip's H.264
  working proxy (ingest already checks it frame for frame against the original). The frame counter follows the
  original's frame table (requestVideoFrameCallback media time → original pts). Pause lands on the last presented
  frame and loads that exact original PNG. Checked: paused counter 245 ↔ burned-in QA OSD "frame 246" (1-based OSD).
  The caption stays "Context playback … Not an observation". An observation view gets "Play around this frame",
  captioned "the observation is frame N only; the playback around it is context".
  Backend: `GET /v1/media/{id}/playback` (original's pts table, start, signed link) + `GET /v1/signed/playback/{proxy}`
  (byte ranges, 206). The Next proxy now forwards Range and HEAD. Test added to `test_workspace_read_routes`.
- **#1 Camera wall** (`/wall`, sidebar "Camera wall"): 2×2 / 3×3 synchronized grid (pages of 9), one wall clock with
  drift correction, scrubber, loop, Full screen. The burned-in OSD and SYNTHETIC mark come from the footage itself.
  Sources:
  - scenario: `ml/evaluation/scenarios/manifest.json` + `<S>/case_input.json` only (complaint, waybill, question,
    cameras). A server route stats/hashes `CAM_xx.mp4` in the manifest's clips folder. A tile plays the backend media
    whose SHA-256 equals the render file, else it says "Render not produced yet" (with the path) or "Rendered, not
    imported". The manifest is missing today, so the wall says so.
  - `?case=<id>`: a case's imported footage. This is the 4 QA clips today.
  No footage or detection is ever drawn in place of a missing clip.
- **#2/#3 `docs/DEMO_SCRIPT.md`** rewritten keys-first:
  - It opens with the one-sentence problem → camera wall (S2, full screen) → the case.
  - Each step has a "With keys: what SAM 3.1 + Muse Spark do" column and a "Fallback (no key)" column.
  - Smoke tests come first.
  - New `npm run backend:keys`: same data, keys from `backend/.env`. The seed still runs in no-key mode first.
  - I did not add a second FOR_REXTON line; the 04:50 one stands.
- **#4 Evaluation headline**:
  - `run_hub.py` reads the manifest. S1–S5 with BOTH renders and evaluator files (`scenario_<S>.json`,
    `events_truth_<S>.jsonl`, `flow_truth_<S>.json`) become the headline: one case per scenario subject, taken from
    the manifest (an input).
  - The control flow runs as a sanity check: on the S0 renders once they exist, else the QA clips. It is the headline
    only as a fallback, with its caveat in `latest.json` and on the Operator page, plus why each scenario is waiting.
  - All predictions run before any evaluator file opens (tested).
  - Container subjects (S4 cage): last seen is scored; abstention is "not scored" when the reference data has no track.
  - Today: headline = control flow (fallback), because the scenario manifest has not been written yet.
- **Boundary**: `scenario_card` was added to the truth-marker test (backend runtime + `frontend/src`) and to the seed's
  `guard()`.

## 2. Check these
- `frontend/review_pack/desktop/20_camera_wall.png`, `21_camera_wall_no_renders.png`, `22_source_context_playing.png`,
  `23_source_paused_exact_frame.png`, `24_operator_evaluation_headline.png` (+ the same names under `mobile/`).
- Sidebar change is in every re-shot screenshot (01–15, fx_16–19).
- `docs/DEMO_SCRIPT.md`, `ml/evaluation/spoor_eval/hub.py` (`plan_suite`, `run_hub`),
  `frontend/src/components/wall/CameraWall.tsx`, `frontend/src/app/api/scenarios/route.ts`,
  `frontend/src/components/workspace/SourcePanel.tsx`.
- Tests: frontend typecheck ✓, lint ✓, unit 16/16 ✓, e2e 16/16 ✓ (smoke + axe AA, incl. /wall and play/pause), `next build` ✓, review pack 20/20 ✓; backend pytest 216 ✓ (from `backend/`).

## 3. Known issues
- The scenario wall was checked end to end on a scratch manifest only (QA clips; not committed): ready, not-imported
  and not-rendered tiles all showed as expected. The real check waits for the builder's manifest and the S2 renders.
- **F1 (decision, not built yet):** every scenario has t0 14:32:07 and the same camera IDs, so seeding all of them
  into the one `site_contoh_hub` would stack coverage for the same camera and time (the workspace would pick the
  wrong scenario's clip) and mix the scan logs of different runs for the same parcel IDs. Decision: one site per
  scenario (`site_contoh_hub_s2` …), with the seed adding the site to `users.json` (a backend restart is needed).
  I'll build it with F1, when renders land. The wall is not affected: it matches tiles by SHA-256.
- The wall syncs on each clip's declared start (clock unverified, ±5 s). The caption says so.
- Final renders are H.265. The browser plays the backend's H.264 proxy, so a scenario clip must be imported before it
  can play.
- Pytest from the repo root also collects `assets/hub/*_test.py` (builder scripts) and errors on them; run it from
  `backend/` (216 passed).

## 4. Questions
1. Opening hook: S2 full screen at 3×3 (6 cameras = 2 empty slots, so 3×3 with 6 tiles) or a fixed 2×2 of the four
   most telling S2 cameras? My default: all of the scenario's cameras from `case_input.json`, in case_input order.
