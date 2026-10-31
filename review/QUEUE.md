> **REVIEWER LOOP STOPPED (Rexton 13:15 Sat):** no more 30-min reviewer checks. All decisions so far stand (reviews/ + the banners below). Rexton now works with one agent directly. Open items: builder hub run 6 (~15:15) → S2 render estimate (> US$10 one run needs Rexton's OK) → S2 render on Modal (frames stay on Modal, download MP4s only); frontend reseed from assets/hub/hub_spec.json + run-6 S2 logs, then the keyed S2 run.

> **REVIEWS 12:45 Sat:** `reviews/021d_review.md` — P0s APPROVED (canonical spec = assets/hub/hub_spec.json layout b; history-line bug fixed + check_scan_routes; stalled fix, 0 stalled). **Frontend: reseed from assets/hub/hub_spec.json + the new S2 long log, gen:hub, re-shoot Answer/Report.** Builder: unstaffing non-story stations for the S2 render allowed on 4 conditions (plausibly idle, others still visible, listed as limitation).

> **BUILDER (11:40 Sat): `reviews/builder_note_1140.md`** — S2 long log flags 16 false 'stalled' parcels at chutes C07/C10 (no bag scans) → fix sim/bag scans with the canonical layout-b spec. Frontend F-052/F-053 noted (four-eyes setting, Settings & data, Proof of spend): reviewed next tick with screenshots.

> **P0 (10:40 Sat) BOTH AGENTS: false 'Records disagree' on S2** — app plan seeded from hub_spec.json (layout a) while S2 runs on layout b → `reviews/builder_note_1040.md` + `reviews/F-047_to_F-051_review.md`. Four-eyes: site setting 'Require a second approver', ON for real sites, OFF for the demo site (no DRAFT banner). Answer/Proof/Go look/Report/Cameras APPROVED WITH FIXES; 3D hub = keep.

> **REVIEWS 10:05:** F-045b Hub APPROVED (matches prototype). F-046 Investigating APPROVED WITH FIXES (no strike-through for unavailable tools, no bracket placeholder in hero, plain words, keyed run once S2 footage exists). → `reviews/F-045b_F-046_review.md`

> **OWNER FINAL (Rexton 09:24 Sat): TOP BAR (no sidebar, no rail). DELETE all the old design; the app is ONLY the reviewer's flow in `review/refs/flow/` (Hub, Investigating, Answer, Proof, Go look, Report, Cameras + Settings).** **ONE user, no account switching:** remove the role switch / 'Signed in as' / multi-account UI everywhere. The demo runs as one supervisor who can do everything (investigate, share the report, Settings). Keep backend permission checks but give the single demo user all roles; no reviewer/approval step in the UI (Report button = 'Share report'). Rexton's reason: in an earlier competition, switching accounts confused people watching the video for the first time. Commit locally before deleting old UI (no push).

> **OWNER (Rexton 09:22 Sat): FOLLOW THE PROTOTYPE 100 %.** Port `review/refs/flow/*.dc.html` as-is: the TOP BAR (logo · Hub / Cases / Cameras · search · one synthetic chip · avatar menu), **no left sidebar rail**, the same page widths, grids, spacing, radii, type sizes and weights, colours, button styles, and the same copy word for word. Lift the inline styles straight into your components/CSS. Only differences allowed: real data instead of sample data (same layout; honest empty states in the prototype's style) and real interactions. If something in the prototype can't work with real data, ask in the request, don't redesign. Redo the Hub to match Main.dc.html exactly (F-045b, side-by-side screenshot: prototype vs app), then continue screen by screen the same way.

> **OWNER PRIORITY (09:25 Sat): `reviews/agent_showcase_0925.md`** — show HOW the agent works (Agentic bonus + Meta tooling). Investigating screen = search map + crew with real tools + timestamped log + live meter + visible self-correction (verifier rejects a look-alike, lead re-plans) + human only when needed; then 'How Spoor found it' + Proof of spend. Prototype updated: refs/flow/Investigate.dc.html. Builder: make sure S2 has a look-alike candidate the verifier can reject.

> **FLOW UPDATED (09:15 Sat, Rexton asked):** `review/refs/flow/` now has 7 screens: Hub (richer rows: last-sighting thumbnail, mini trail, why it matters, Investigate) → **Investigating** (agents at work, live: scan log → Muse Wonder plan → Muse Spark per camera → SAM 3.1 → verifier, with the camera being checked + running cost; this is the Meta-tooling showcase) → Answer → Proof (**Video | 3D hub** switch) → Go look → Report; plus **Cameras** (top menu): all 19 cameras on one synced clock, Camera wall | 3D hub, zone filter. 3D = the real Blender hub.glb (the tilted plan image in the mockup is only a stand-in). Read the README again before F-045.

> **OWNER FINAL (Rexton 09:04 Sat): the app = the flow in `review/refs/flow/`. REMOVE the previous UI.** Old pages, layouts, tabs and dashboard panels that don't belong to the 5-screen flow (+ Settings, + Cameras/3D, + the Investigating screen coming next in refs/flow) are taken out of the app, not hidden behind a switch. Keep the backend and the data/logic; re-use components only where they fit the new screens. Remove the ?style=v1/v2 switch: one look. Commit locally first so the old UI stays in git history (no pushing; don't delete anything outside frontend/src that isn't regenerable). Hub first → F-045.

> **F-044 APPROVED (09:08):** build to review/refs/flow, Hub first → F-045 shots. New rule §J: no em dashes in visible text.

> **OWNER APPROVED (Rexton 08:58 Sat): build the app to the flow in `review/refs/flow/`** (Hub → Answer → Proof → Go look → Report). He does NOT want the current AI-style dashboard layout back: the old Operator-style dashboard, tab soup and panels go. Order: Glimmer run + logo swap (small) → F-044 = short critique + plan to map every existing feature into these 5 screens (what moves to Evidence details / Settings / gets cut) → rebuild screen by screen, Hub first, screenshots of each at 1440×900 + 390 wide.

> **FRONTEND (09:05 Sat): reviewer's flow prototype is in `review/refs/flow/` (README first).** 5 screens: Hub → Answer → Proof → Go look (phone) → Report. Rexton is reviewing it on his phone; build to it ONLY after he says OK (step 3 of design_sprint_0835 becomes: adapt this flow, not invent new layouts). Until then: Glimmer run, logo swap, F-044 critique.

> **FRONTEND STOP — DESIGN SPRINT (Rexton 08:28 Sat): read `reviews/design_sprint_0835.md` NOW.** No new features. Step 1 = written critique against the 4 skills (F-044, no code); then the 7 rules; then 2 layout options for the journey screen. One synthetic label only; CCTV final-look frames only; demo opens on S2 with real frames; one hero per screen.

> **MODAL LOGGED IN (Rexton, 08:19 Sat)** via `modal token set` (token in his user config, not in the repo — never read, print or copy it). Now allowed, per owner_modal_0016 + keys_in_0152: **builder** — the Modal render test (≤ US$2; hard timeout; stop the app after); **frontend** — J6 Glimmer triage run per F-043 (25-min ceiling ≈ US$1.04, cap US$3; proof file for the open-weights prize; synthetic footage only). Log estimate before / actual after in FOR_REXTON.md. No idle GPUs, no deployments left running. If a run looks like > US$5, stop and ask.

> **OWNER CONFIRMED (08:16 Sat): S2 render gate per 021c_review.md** — 0 collision rows visible in any camera S2 renders; unseen stations fixed after S2 (before any scenario that films them and before the fly-through). Work in the 021c order.

> **OWNER CONFIRMED (08:13 Sat) — BOTH AGENTS READ `reviews/owner_final_0815.md`:** LOGO FINAL = fingerprint parcel box (`assets/brand/spoor_logo_fingerprint_{light,dark}.png`; replaces the trail mark everywhere; frontend rebuilds as SVG + small mark + favicon). Tagline released: "Every parcel leaves a trail." **Deadline: Wed 5 Nov 10:00 AM MYT; target submit Tue 4 Nov evening.**

> **NEW REVIEWS (07:56 Sat):** frontend → `reviews/F-040_F-041_review.md` (F-040 APPROVED; J3: no statute text from mirror sites, hide the s.31 misquote, ONE re-run approved ≤ ~$1.50 with a search cap, not if > $2) + `reviews/F-042_F-043_review.md` (J4 APPROVED; J6 Glimmer APPROVED TO RUN once Rexton logs Modal in). Builder → `reviews/builder_note_0755.md` (S2 long log must keep traffic ≥ 12 min after S2's C04 divert).

> **NEW REVIEWS (06:22 Sat):** builder → `reviews/021c_review.md` (S2 actor + cage APPROVED; **render gate = 0 rows visible in any camera S2 renders**, other stations old motion allowed for the S2 render only; fix order: chute parcels → cage pushers → line A → bag opener/bagger → parcel rows → docks/carriers/line B/tech → 15 min S2 log → render). Frontend → `reviews/F-039_review.md` (APPROVED; P2 zone labels under chips, mobile card height, yard camera pins).

> **NEW REVIEWS (05:16 Sat):** frontend → `reviews/F-032_to_F-038_review.md` (APPROVED WITH FIXES: F-033 P0 fixed well; P1 chips still overlap → spec that fails on overlap, 3D labels overlap + 'Exception store'; P2 default demo case = S2 subject). Builder → `reviews/builder_note_0515.md` (S2 subject CTX971442173782 missing from the sim log; worker lying on the floor in CAM_10 f248 → pelvis-height gate).

> **NEW REVIEWS (04:46 Sat):** frontend → `reviews/F-026_to_F-031_review.md` (APPROVED WITH FIXES; **P0 stalled inbox floods: stalled only if the next device kept working past the allowance, else 'log ended'**; P1 H5 wording 'into' + door from truth, H12 search order favours blind/searchable places, H11 grid shows no-footage cameras). Builder → `reviews/builder_note_0445.md` (longer sim-only S2 scan log ~15 min, after 021c, before render).

> **NEW REVIEWS (04:15 Sat):** frontend → `reviews/F-style-b_F-025_review.md` (APPROVED WITH FIXES; F-025 APPROVED: proof shots after media load, chips clip/overlap, seam, stalled inbox needs an as-of time so S2 shows as stalled). Builder → `reviews/builder_note_0415.md` (cage collision rule: bars/shelves/parcels still count; before/after counts in 021c).

> **NEW REVIEWS (03:42 Sat):** builder → `reviews/021b_review.md` (APPROVED WITH FIXES: P0 fixed; P1 finger curl, head-to-cage clearance at the reach, shelf-place proof in 021c). Frontend → `reviews/F-024_review.md` (APPROVED WITH FIXES: commit approved backend parts now; P1 CAM_07 expected box uses stale pose, load-time wording flicker, follow-cam inset covers route, next-camera rows).

> **TARGET DATES (03:12 Sat): Rexton: NO scope freeze — keep improving realism and scope.** Priority order only: get S2 working end-to-end first (S2 rendered → keyed run with SAM 3.1 + Muse + Spark Open + Glimmer → real numbers on screen), then keep polishing and add S1, S3–S5. Aim: S2 rendered Sat night, keyed run Sun, video recorded Mon, submit Tue Nov 4 evening (deadline Wed 5 Nov 10:00 MYT). Whatever is best by Mon evening is what the video shows.

> **BOTH AGENTS READ NOW (03:12 Sat): `reviews/owner_ideas_0303.md`** — OWNER CONFIRMED scope: 3D whole-hub twin view (builder: clean hub.glb after S2 render), 'scan once, cameras keep it live' deployment doc, camera strip, people = anonymous markers in case replay only, masked scanner IDs. Frontend also: `reviews/F-style_review.md` (APPROVED WITH FIXES, 14 items) + `reviews/F-023_review.md` (APPROVED).

> **FRONTEND READ (03:00 Sat): `reviews/floorplan_design_0300.md`** — Rexton: floor plan looks AI-drawn → reference `refs/floorplan_reference.png`; journey screen fixes; H15 = exceptions inbox (stalled-scan alerts + search); personal-data masking; LOGO ON HOLD (don't polish/place further).

> **KEYS IN (01:52):** reviews/keys_in_0152.md — frontend agent: J1 smoke tests now (≤ $3 Meta, ≤ $1 Baseten), then key vs no-key comparison.

> **STYLE (01:36):** reviews/owner_style_0136.md — frontend uses Rexton's skills (rexton-ui, emil kowalski, impeccable, taste) + the Reelism design DNA; first a style-mapping request with 3 screens for his OK.

> **PRIZES (01:40):** docs/PRIZE_STRATEGY.md — open weights are now load-bearing (agents default to Muse Spark Open on Baseten; J6 Glimmer on Modal = required, not stretch); keep docs/open_weights_proof/. Order: S2 render → H1/H2/H10 → J1 → J2 + open-weights default → J6 → rest.

> **OWNER CONFIRMED (01:24): do ALL of block J (Meta stack: J1 smoke tests → J2 Muse Wonder lead → J3 search grounding → J4 Voice Transcribe → J5 Muse Image set dressing → J6 Muse Glimmer on Modal).** Modal budget is shared ($30): render test ≤ $2 first, Glimmer test ≤ $3, nothing bigger without Rexton. Contributor mode only on synthetic footage.

> **OWNER CONFIRMED (00:40):** QUEUE block H (H1–H12, incl. H10 missing moment, H11 camera combination grid, H12 where-it-might-be + search task) is the product's key demo — spec reviews/journey_view_0030.md. Build right after the S2 render; do not drop items without asking Rexton.

> **OWNER MUST-HAVE (00:30):** reviews/journey_view_0030.md — follow-cam close-up + journey ribbon + where-it-could-be cloud (frontend, after S2 render).

> **CCTV (00:25):** reviews/cctv_setup_0025.md — Z11 doorway camera (P0, with S2), CAM_04 / CAM_07 re-aim.

> **MODAL (00:16):** reviews/owner_modal_0016.md — Modal render test (after the S2 actor item); Rexton logs in himself; test ≤ $2.

> **SCENARIOS v2 (00:20 Sat):** reviews/scenarios_v2.md — S2 actor on mocap + perimeter proof FIRST; S5 scan bug P0.

> **OWNER ORDER 22:10:** keep working tonight — reviews/owner_continue_2210.md (S2 first; start the 31 Oct list now).

> **READ FIRST (15:52, owner order):** reviews/014_review.md → 013c_review.md (no headwear, closed) → 014_GO_mocap_plan.md (mocap pipeline M0–M5). Stop patching old inductor/dock arm motion.

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

- [ ] A4 Natural-motion pass (review 009d): headwear fit, posture, animation principles, AndyData base for inductors + dock, ZERO interpenetration (items, people vs assets, people vs people). Blocks the S0 batch.

## B. CCTV (all 18 cameras)
- [x] B1 Floor: find out why it reads near-white (QA preview mode? lost texture? exposure/WDR?). Fix it to the
      reference look (mid-grey epoxy, wheel marks, yellow lines). Show one before/after still → request.
- [ ] B2 Final-look stills: one full-settings still per camera, CAM_01–CAM_18, with OSD → request.
- [ ] B3 CCTV QA clips, all 18 cameras, 60 s each, normal shift (no scenario) → request (split into
      2–3 requests of 6–9 cameras so review can start early).
- [ ] B4 Fix → re-render changed cameras → request until APPROVED.

## C. Frontend (do this while renders run) — PRD §19, §23, docs/build/12-frontend.md
Rexton's ask: "set up the frontend everything". Build the real app, not a mock-up.
- [x] C1 `frontend/`: Next.js (App Router) + TypeScript + React Three Fiber + drei. TS types generated from the
      backend JSON Schemas (step 01). Site Z-up → renderer Y-up from the backend transform (step 03).
- [x] C2 Hub model for the web: export `hub_dressed.blend` → `frontend/public/hub.glb` by script (no people,
      decimated, Draco/meshopt, target < 25 MB, same object IDs/zone IDs as hub_spec). Camera frusta and
      coverage from hub_spec/calibration. 2D floor-plan fallback from the plan SVG.
- [x] C3 Surfaces §19.2: case overview · 3D scene · one timeline with clock-drift warnings · movement trace
      (object / anonymous people / all) · source panel (original vs annotated) · evidence graph ·
      agent panel (real job events over SSE; no fake typing) · report review/export · operator page (§23).
- [x] C4 Signature interaction §19.3 against the real backend: green solid = observed, amber dashed =
      hypothesis, grey = unknown gap; solid never bridges a gap; click a segment → exact source frame.
- [x] C5 No-key mode: the backend runs with no Meta keys. Feed it real inputs only (cameras, calibration,
      synthetic clips as media, `scan_simulated` log through the import route). Where a model step would run,
      the UI shows an honest "analysis unavailable — no API key" state. **Never** fabricate tracks/answers,
      and the runtime **never** reads `render_truth.*`, `flow_truth.json` or anything under `build/truth/`.
- [x] C6 Design bar §19.5: restrained, evidence-first, dark-neutral canvas, clear contrast (WCAG AA), keyboard
      navigation, reduced motion, explicit loading/error states, fictional names only. Works at 1440×900
      and 390×844.
- [x] C7 Review pack: Playwright screenshots of every surface at both sizes + a ≤ 60 s screen recording of the
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

## F. Frontend agent — next (added by reviewer 03:45, after block C approval)
- [ ] F1 Per-scenario input cases: when D renders land, the seed creates one INPUT case per scenario (the parcel the scenario is
      about, its own clips + scan-log slice), chosen from the scenario card, never from truth. Cases list shows scenario name + "synthetic".
- [ ] F2 §19.3 "new evidence added": once B3 clips exist, record the real flow — investigate with 2 cameras, import a 3rd camera
      clip in Operator, re-run, show the diff. Replace the fixture part of the recording where real data now exists.
- [x] F3 Evaluation harness (`ml/evaluation`): evaluator-only code may read `build/truth/` (runtime never). Score Spoor's
      no-key answers per scenario: last-seen correctness, correct abstention ("unknown"/"no coverage"), no false "left the hub".
      Results shown on the Operator page. Keep the import boundary tested (runtime package can't import the evaluator).
- [x] F4 Demo path doc `docs/DEMO_SCRIPT.md`: 3-minute walkthrough on the real app (which case, which clicks, what each screen
      proves), updated to the parcel hub. Mark every step that needs an API key so Rexton knows what changes once keys are in.
- [x] F5 Review 005 P2 polish (hypothesis routing along conveyance, trace height, no dead air in the recording).

## H. Frontend — OWNER MUST-HAVE: the forensic journey (Rexton 00:21–00:35 Sat 31 Oct). Spec: review/reviews/journey_view_0030.md
- [ ] H1 P0 Follow-cam close-up: crop of the ORIGINAL frame around the tiny parcel (2–4x native, no AI upscale), brackets, ID chip + "why we know" chain (tunnel read -> carrier -> divert), follows the playhead.
- [ ] H2 P0 2D floor-plan journey = primary view: ribbon snapped to belts/walkways (green observed / amber dotted inferred / grey hatched gap), scan beads, glowing marker replay 1x/4x/16x synced to the timeline.
- [ ] H3 P1 Camera relay strip: one close-up per camera segment, "+2.1 s · overlap", grey "no camera" tiles.
- [ ] H4 P1 "Where it could be" cloud in gaps: grows at walk/belt speed, clipped by cameras that watched and saw nothing; S2 collapses to Z11. Labelled "computed possible area".
- [ ] H5 P1 Records vs video lanes: diverge at a red pin (S2 truck vs exception store, S3 bag vs floor, S4 D08 vs D09).
- [ ] H6 P1 3D stays optional: deployment mode renders Scene3D WITHOUT hub.glb by extruding the site plan JSON (2.5D) + toggle "Plan-built 3D (what a real hub gets)"; demo model labelled "synthetic hub model".
- [ ] H7 P1 Evidence reel: export MP4 stitching follow-cam crops in time order with time / camera / source hash / SYNTHETIC, grey cards for gaps.
- [ ] H8 P2 Camera wall sync during replay. H9 (if Rexton OKs) Coverage advisor (reviews/cctv_setup_0025.md).
- [ ] H10 P0 "The missing moment" (Rexton 00:39): the break point where the chain stops. Show the LAST frame it was seen AND, for the next camera(s) it should have reached, the frame at the predicted time (belt speed / walk speed) with an empty dashed box: "expected here ~14:32:30 — not seen". Negative evidence made visible = how we prove where it went missing.
- [ ] H11 P1 Camera combination at the break: 2–4 cameras around the break point in a synced grid, one shared scrubber, the subject's box in each; this is the "camera moment".
- [ ] H12 P1 "Where it might be" ranked list + search task: each possible place (e.g. Z11 store, under belt A, cage RC-864) with evidence for / against, shown on the 2D/3D map (cloud + pins) and as a mobile-friendly "go look here" checklist for floor staff with a walking route; "Found it here / not here" buttons record the outcome on the case (new evidence, revises the answer).
- [ ] H13 P1 Scan cards (Rexton 01:10, reviews/scan_moment_0115.md): pop-up card on the video at the scanner + on the map bead when the playhead hits a scan ("✓ Tunnel read · id · weight · size · → chute · time, clock corrected"; red for no-read), linked to the frames where the DWS stack light flashed. Hub side: stack lights + live DWS screen + handheld aiming light synced to the scan log.
- [ ] H14 P0 (Rexton 01:33) **Case summary page = page 1 of every report** (what claims / customer service / managers read): one-sentence answer + status chip (Located / Found / Unknown — never "stolen"), 3–4 key frames side by side (last confirmed · missing moment · where it is · found), a mini 2D map of the route with gaps, confidence in plain words, the next action ("Search exception store Z11"), time to resolve. Shareable as one image/PDF page. The current formal document becomes the **Evidence appendix** (pages 2+), kept as is (+ review 012 polish).
- [ ] H15 P1 (Rexton 01:33) **Hub dashboard** on the Operator page (what hub / regional managers watch, Grafana-style but in-app): open cases, median time to locate, found rate, false "left the hub" = 0, gaps by zone (a heat map on the floor plan — the blind spots that cost the most), records-vs-video conflicts by scanner/door, cameras most used as evidence, cost per case; trend over days. Uses the scenario cases + evaluation data; labelled synthetic.
- Honesty: no solid line across a gap; crops are original pixels; inferred = dotted + labelled; no-key mode = scans + belt-route inference (dotted, labelled) + gaps, never a fabricated track; "tracking needs SAM".
- Order: after S2 is rendered (H1, H2 first — they are the demo's wow); proof = Playwright screenshots + a 30 s screen recording of the S2 journey.

## I. Backend for the forensic journey (Rexton 00:41 Sat 31 Oct) — serves block H. Existing API: backend/src/spoor/api/app.py
Rules: every new output is computed from evidence (scans, observations, site geometry, calibrations) and typed as
observed / inferred / computed / gap; runtime never reads build/truth; no-key mode returns scans + gaps and says what needs SAM.
- [ ] I1 P0 Follow-cam crop (H1): GET /v1/cases/{id}/tracks/{track}/crop?frame= → signed crop of the ORIGINAL frame around the box (+ margin, no upscale), with source media id, frame index, SHA-256 and the identity chain (scan ids that name the object).
- [ ] I2 P0 Journey segments (H2): extend /trace so the backend (not the browser) types every segment: observed (track), inferred_along_conveyor (between two scans, belt route × belt speed, with the time window), gap (never bridged). Each segment carries its evidence ids.
- [ ] I3 P0 Missing moment (H10): GET /v1/cases/{id}/missing-moment → the last confirmed sighting + for each camera the object should have reached next: predicted window (belt / walking speed + handoff overlaps + clock sync), region in the image, and the result (seen / NOT seen / not analysed). "Not seen" is a typed NEGATIVE observation with its frames.
- [ ] I4 P1 Possible locations (H4, H12): GET /v1/cases/{id}/possible-locations?t= → reachable floor area from the last confirmed point (walkways, belts, doors) minus every area a camera watched without seeing it; returned as polygons per time step + ranked candidate places (zones/containers) with evidence for / against. Labelled "computed".
- [ ] I5 P1 Synced camera grid (H11): GET /v1/cases/{id}/sync-grid?cams=…&t= → playback sources for 2–4 cameras with per-camera clock offset/drift applied (existing clock-syncs / clock-domains), so one scrubber shows the same real moment.
- [ ] I6 P1 Records vs video conflicts (H5): verifier rule that compares scan claims (container_add, rfid_read, bag scan) with video observations and emits a typed Conflict (claim, contradicting observation, divergence time). S2 cage vs Z11, S3 bag vs floor, S4 D08 vs D09.
- [ ] I7 P1 Search task + outcome (H12): POST /v1/cases/{id}/search-tasks (from ranked places) and POST …/search-tasks/{tid}/outcome {found | not_found, optional photo} → stored as a human observation (pseudonymous token, timestamp, hash) → re-run revises the answer (existing /diff shows it).
- [ ] I8 P1 Evidence reel (H7): POST /v1/cases/{id}/reel → MP4 built with ffmpeg from I1 crops in time order, grey "no camera" cards for gaps, burned-in time / camera / source hash / SYNTHETIC; manifest with every source hash; download via signed link.
- [ ] I9 P1 Plan for 3D (H6): GET /v1/sites/{id}/plan → walls, zones, doors, conveyor polylines with deck heights, racks, cameras (pose + cone) so the frontend can extrude a 2.5D hub without hub.glb.
- [ ] I10 P2 Coverage advisor (H9, only if Rexton OKs): per gap, the single camera pose that would have closed it (from site geometry + I4), ranked across cases.
- [ ] I11 Keys (Rexton does the keys himself): SAM 3.1 tracking through perception/backend.py with MODEL_API_KEY; agents through reasoning/backends.py with BASETEN_API_KEY + BASETEN_MODEL_ID; compare no-key vs key in spoor_eval.
- Tests for each (pytest), schemas in backend/schemas, contracts in contracts/. Order: I2 → I3 → I1 → I4 → I6 → I5 → I7 → I8 → I9 (follows H).

## J. Wider Meta stack (Rexton 01:22 Sat 31 Oct) — plan in docs/META_MODEL_USAGE.md "Expanded Meta stack plan"
- [ ] J1 (frontend agent) Smoke tests with the real key for SAM 3.1, Muse Spark 1.3, Muse Wonder 1.0 — fill the smoke-test log table (latency, cost, limits). Write them with Muse Code if Rexton installs it.
- [ ] J2 (frontend agent) Muse Wonder 1.0 = lead investigator role (plans, delegates per-camera Spark agents); Spark stays the worker; Contributor mode for bulk passes; prompt caching of site/camera context; token-count cost preview before a run (shown in the Agent panel).
- [ ] J2a (owner-confirmed 01:48) BasetenChatBackend: model `meta-models/muse-spark-open-1026`; split Muse Spark Open's reasoning from the final answer before JSON validation (log the reasoning length, never feed it to the validator).
- [ ] J2b (owner-confirmed 01:48) BasetenChatBackend vision: send the key frames (last confirmed, missing-moment frames, CAM_19 doorway) as images so the open-weights model reasons over evidence pictures, not only text; keep video to Meta Spark; record model/provider/request ids in docs/open_weights_proof/.
- [ ] J3 (frontend agent) Search grounding for the report's Malaysian context (Postal Services Act 2012 / MCMC), inline citations, dated.
- [ ] J4 (frontend agent) Muse Voice Transcribe: voice note on the phone search task + complaint-call transcript as case input; transcript stored as evidence with hash, speaker turns.
- [ ] J5 (builder) Muse Image for fictional CONTOH Express label / signage / parcel print textures only (never evidence); keep prompts + outputs in assets with a provenance note.
- [ ] J6 (REQUIRED for the open-weights bonus, needs Modal; ≤ $3 test, single GPU, 30B Apache 2.0) Muse Glimmer on a Modal GPU as on-site triage that flags parcel-handling moments per camera; only flagged clips go to Model API.
- [ ] J7 (optional, Nov 3, only after the S2 video is safe) Public demo: frontend on Vercel + small backend with the S2 case preloaded in DEMO MODE (replays computed results, NO live paid calls, no keys on the server), SQLite file DB; link for the gallery / X post.
- Keys: scripts read backend/.env; agents never print or copy keys. Generative output never becomes evidence.

## G. When a queue runs dry — research for AUTHENTIC REALISM (Rexton, 11:22: "authentic, realistic", not decoration)
Never idle. If your blocks are done or blocked, research how a **real Malaysian parcel hub** actually looks and works, then
make ours match it. Every change must be backed by a source (reference frame, public hub video, vendor/operator doc, safety
regulation) — note the source in the request. No decoration for its own sake.
- **Builder — how real hubs really are:** real work tempo and crew sizes per station; how real inductors/unloaders/baggers
  move (watch reference videos frame by frame, copy timing and posture); what workers wear in Malaysian hubs (company T-shirt
  vs vest, caps, gloves, safety boots, lanyards); real wear (scuffed cage paint, dirt in corners, taped-up cartons, crushed
  corners, mixed label types — courier waybills, Shopee/Lazada-style marketplace mailers but **fictional brands only**);
  real lighting (some tubes dimmer, daylight spill at open dock doors); Malaysian signage and floor markings (BM/EN,
  DOSH/JKKP-style safety signs, fictional); real CCTV artefacts (H.265 blocking in motion, noise in darker zones, a dirty
  dome, slight colour cast differences between cameras).
- **Frontend agent — how real investigators/ops staff work:** research how hub ops teams actually investigate a lost parcel
  (claims workflow, scan-history screens, CCTV request forms, chain-of-custody notes) and make the app's wording, steps and
  report match real practice. Use authentic logistics terms (waybill, consignment, bagging, manifest, linehaul, POD).
- **Both:** a short "what the research showed → what we changed" note per item, with sources.
- [ ] A5 (PRIORITY, reviews/014_GO_mocap_plan.md — milestones M0–M5, supersedes priority_mocap_now.md) Realism plan (review/research/realism_plan.md): A1–7 motion principles with the sourced numbers, 100STYLE walks/idles,
      parcel transit (zero-pressure accumulation, ramped diagonal discharge, rigid-body falls baked per parcel). Do inside A4.
  - **Status 30 Oct 22:00 (builder):**
    - **Approved:** M0–M4 (014b–016b) and M5 steps 1–2 (017). Idles and release rest (018b).
    - **M5 step 3 (in progress):** line A on mocap inside the full hub. Inductor bodies vs anything: 0 rows.
  - **Open, in order for 31 Oct:**
    - [ ] mailer pinch: index + middle into the roller gap, thumb on top (017 #2, 018 #4);
    - [ ] line A parcel rows 63 → 0: induct belts 35 (side rail just after the set-down), feed 27 (mouth frame / guide ends);
    - [ ] put-back-on-table when the set-down zone stays taken > 1.5 s (017 #3; seen once, in pre-roll);
    - [ ] dock D05 on the full trailer wall + head ≥ 5 cm (016b);
    - [ ] old-motion stations → 0 rows (docks, bagger, cages, line B, opener: ~370 rows; 018 #6);
    - [ ] then layout b ON for S2 + S2 gates + review videos (S2-first, waiting for Rexton's answer).
- [ ] A6 (P2, AFTER mocap M5 only; Rexton 15:22 idea) Headwear done right, if ever: cap/helmet MODELLED INTO the avatar mesh (hair under it cut away, skinned 100% to the head bone, one mesh), never a separate prop. Only 1–2 workers, caps not hard hats (MY parcel hubs: no helmets). Proof: head sheet every 10 frames.
