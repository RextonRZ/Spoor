# Request 004 — Frontend: C5 + C6 + C7 (no-key mode, design bar, review pack, tests)

From the frontend agent. Requests 002 and 003 are still unreviewed; this one closes block C.

## 1. Changed since last request
- **C5 no-key mode.** `npm run backend` starts FastAPI with blank `MODEL_API_KEY`/`BASETEN_*`, `AGENT_BACKEND=none`
  (`frontend/scripts/backend.mjs`). `npm run seed` (`frontend/scripts/seed_nokey.py`) loads only real inputs through the
  HTTP API and refuses to run if any model key is configured:
  - site, 15 zone polygons, 18 cameras from `assets/hub/hub_spec.json` (poses marked not measured; uncalibrated);
  - 20 clock domains from hub_spec, **no fits** (fits need matched anchor events);
  - QA clips `CAM_01/04/07/10` as `synthetic_test` media, SYNTHETIC mark burned into the imported copy; camera clocks get
    an explicit `UNVERIFIED … uploader-declared` sync (±5 s) because the upload route needs one to place a clip;
  - `events_scan_simulated.jsonl` → Spoor `ScanEvent` rows (field mapping only) → `/v1/sites/{id}/scans/import` with
    `source=simulated`: 69 imported, 26 `bag_drop` pulses not imported (no identity, no container);
  - one INPUT case: the parcel with the most reads in the log (operator choice of input, §23).
  - Guard: the seed refuses paths matching `render_truth|flow_truth|/truth/`; the smoke test asserts no browser request
    touches such a path. Model steps show "analysis unavailable — no API key" (agents, SAM, Spark, evidence agent,
    people tracks, model-call trace).
- **C6 design bar.** Dark-neutral tokens, one accent; evidence colours always paired with a line pattern and a word.
  axe-core WCAG 2.0/2.1 AA: **0 serious/critical** on cases, workspace, graph, report, operator
  (`frontend/tests/e2e/a11y.spec.ts`; canvas and the sandboxed report iframe excluded). Keyboard: skip link, all
  controls are buttons/inputs, 3D scene (arrows/±/R), timeline slider. Reduced motion: CSS durations → 0, 3D fly-to
  becomes a jump. Every panel has loading / error (with "Try again") / empty / unavailable states. Fictional names only
  (CONTOH Express); the smoke test fails on DPD, BEUMER, PosLaju, Skynet, J&T, Ninja Van, FedEx, UPS, DHL, FORTNA.
  1440×900 and 390×844 (tabbed workspace on phones, no horizontal overflow).
- **C7 tests**: `npm run typecheck` ✓ · `npm run lint` ✓ · `npm run test:unit` 6/6 ✓ · `npm run test:e2e` 13/13 ✓
  (8 smoke + 5 a11y) · `next build` ✓ · backend `uv run pytest` 207 ✓.
- Fixed while testing: trace lines now draw over the hub geometry (a parcel on the 1.5 m deck hid its own line);
  phone camera framing; timeline tick density on narrow screens; cases page overflow at 390 px; web GLB re-export drops
  non-rendered asset templates and props taller than the eaves.

## 2. Check these
- `frontend/review_pack/signature_interaction.mp4` — H.264, 1280×800, **37 s**, 1.3 MB. Part 1 real no-key stack
  (last confirmed → lit camera → exact frame → frame step → earlier scan → agent run over SSE). Part 2 route-mocked
  TEST FIXTURE with banner (green solid, amber dashed, grey gap; click a segment → frame; click the gap).
- `frontend/review_pack/desktop/*.png` and `frontend/review_pack/mobile/*.png` (19 each, list in request 003).
- `frontend/README.md` (run commands), `frontend/tests/e2e/smoke.spec.ts`, `frontend/tests/e2e/a11y.spec.ts`.

## 3. Known issues
- Seeded data is a snapshot: the builder regenerates `events_scan_simulated.jsonl` and the QA clips. Re-seed with
  `rm -rf frontend/.local/backend-data` + restart backend + `npm run seed` after B3/D renders (case parcel will change).
- No observed segments without SAM; green/amber only on the bannered fixture.
- In the recording at 1280×800 the timeline shows 3 camera lanes before scrolling.

## 4. Questions
1. When B3 final clips exist (OSD clocks drifting per camera), should the seed import all 18 or only the cameras on the
   case path? I plan: all clips that exist, so the timeline shows real coverage gaps.
