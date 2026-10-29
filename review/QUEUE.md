# Work queue — until Rexton is back (~22:00 MYT, Fri 30 Oct)

Order = priority. Tick `[x]` when the reviewer has APPROVED it (not when you finish it).
Long Blender renders run **headless in the background** (`blender -b … --python …`) while you work on
the next non-render item, usually the frontend (block C). Never sit and watch a render.

Goal for tonight: **all CCTV footage and scenario cases rendered and approved, and the frontend set up
end to end on the backend — without any API keys.** Keys, Meta API runs and anything paid wait for Rexton.

## A. People + parcels (finish the rebuild in progress)
- [ ] A1 Rocketbox workers on every station, parcel-first contact (matrix bake, two-hand IK, foot lock).
      Gates from the motion report: hand–socket < 1 cm, released parcel ≤ 5 mm from its surface,
      foot slide ≤ 2 cm/frame, no pops, no overlaps, accessories opaque, no action clip without its object.
- [ ] A2 Re-render `qa/workers/*.mp4` (one per worker, close follow-cam, 10 fps, frame no. burned in)
      + regenerate `auto_flags.csv`/`summary.txt` → **request**.
- [ ] A3 Fix every P0/P1 from the review, re-render only the changed workers → request.

## B. CCTV (all 18 cameras)
- [x] B1 Floor: find out why it reads near-white (QA preview mode? lost texture? exposure/WDR?). Fix it to the
      reference look (mid-grey epoxy, wheel marks, yellow lines). Show one before/after still → request.
- [ ] B2 Final-look stills: one full-settings still per camera, CAM_01–CAM_18, with OSD → request.
- [ ] B3 CCTV QA clips, all 18 cameras, 60 s each, normal shift (no scenario) → request (split into
      2–3 requests of 6–9 cameras so review can start early).
- [ ] B4 Fix → re-render changed cameras → request until APPROVED.

## C. Frontend (do this while renders run) — PRD §19, §23, docs/build/12-frontend.md
Rexton's ask: "set up the frontend everything". Build the real app, not a mock-up.
- [ ] C1 `frontend/`: Next.js (App Router) + TypeScript + React Three Fiber + drei. TS types generated from the
      backend JSON Schemas (step 01). Site Z-up → renderer Y-up from the backend transform (step 03).
- [ ] C2 Hub model for the web: export `hub_dressed.blend` → `frontend/public/hub.glb` by script (no people,
      decimated, Draco/meshopt, target < 25 MB, same object IDs/zone IDs as hub_spec). Camera frusta and
      coverage from hub_spec/calibration. 2D floor-plan fallback from the plan SVG.
- [ ] C3 Surfaces §19.2: case overview · 3D scene · one timeline with clock-drift warnings · movement trace
      (object / anonymous people / all) · source panel (original vs annotated) · evidence graph ·
      agent panel (real job events over SSE; no fake typing) · report review/export · operator page (§23).
- [ ] C4 Signature interaction §19.3 against the real backend: green solid = observed, amber dashed =
      hypothesis, grey = unknown gap; solid never bridges a gap; click a segment → exact source frame.
- [ ] C5 No-key mode: the backend runs with no Meta keys. Feed it real inputs only (cameras, calibration,
      synthetic clips as media, `scan_simulated` log through the import route). Where a model step would run,
      the UI shows an honest "analysis unavailable — no API key" state. **Never** fabricate tracks/answers,
      and the runtime **never** reads `render_truth.*`, `flow_truth.json` or anything under `build/truth/`.
- [ ] C6 Design bar §19.5: restrained, evidence-first, dark-neutral canvas, clear contrast (WCAG AA), keyboard
      navigation, reduced motion, explicit loading/error states, fictional names only. Works at 1440×900
      and 390×844.
- [ ] C7 Review pack: Playwright screenshots of every surface at both sizes + a ≤ 60 s screen recording of the
      signature interaction → request. Add `frontend` tests (typecheck, lint, a Playwright smoke test).

## D. Scenarios
- [ ] D1 Scenario set: S0 control + the planned S1–S5 first, then the rest of `hub_spec.yaml →
      scenario_support` (14 total). One timeline per scenario drives footage, `scan_simulated` log and truth.
- [ ] D2 Test render: S0 on 2 cameras, final settings, 60 s → request (check time sync, OSD drift, scan log
      lines up with what is visible).
- [ ] D3 Full batch: every scenario × the cameras that see it. Disk guard: keep ≥ 15 GB free on C:; encode each
      chunk to H.265 then remove that chunk's image sequence; stop the batch and log it if free space < 15 GB.
- [ ] D4 Per scenario: a 1-page `scenario_card.md` (what happens, which cameras, which scan lines, expected
      Spoor answer incl. "unknown"/"no coverage") + 3 key stills → request.

## E. Always
- Local git commits after each approved item (no push). `.gitignore`: renders, image sequences, `.blend1`,
  `third_party/mixamo/`, `docs/hub/reference_frames/*` (already has its own ignore).
- Backend tests stay green (`uv run pytest`). Update README "Status" table at the end of the day.
- End of day (~21:30): write the summary into `FOR_REXTON.md`: what is approved, what is left, what needs him.

## Disk rule (Rexton, 01:34)
~33 GB free at start. If free space drops below 15 GB, clear **only regenerable files**, in this order:
1. image sequences already encoded to mp4, 2. `*.blend1` backups, 3. `__pycache__`, old `qa/_frames`, superseded QA mp4s,
4. npm/pip caches. Never delete Rexton's own files (screenshots, downloads, source assets). Log what you removed and how much.
