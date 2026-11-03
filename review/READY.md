# READY for review

Newest first. Each entry: what is done, where to look, what is still open.

## For Rexton, Wed 4 Nov morning: the 5-line summary (start here)

1. **3D route, cinematic (Proof):** the carton is a real object in the Blender render riding the belts, lapping the sorter and carried into the store; the route draws itself (dashed "No camera" where no camera saw the move), pins spring in, a story clock runs, and "Fly the route" ends easing into the glowing Exception store: "Most likely here". Recording: `review/shots/wed/story3/fly_the_route.webm`.
2. **"Compare with what really happened"** on the answer card plays the simulation's own carry into the store (labelled "Simulation ground truth. Not used by Spoor." throughout), then draws Spoor's route over it; one line compares the two answers (computed, not typed in).
3. **Cameras page:** the 3D hub now turns (drag, a frame every 2 degrees, inertia) and zooms (scroll, to 2.5x) with every camera and its coverage glued on; a plain camera list replaces the chip grid; "Replay the search" plays the run on the wall in 8 s (Glimmer's skips dim, the 2 picks light, CAM 19 pulses).
4. **Fixed on the way:** at step 11 (the D07 record) the carton used to fly to D07, against our own evidence; it now stays in the store. The step row is a timeline, not boxes; a step's camera opens its own clip.
5. **Decide:** your staff-ID idea is not done on purpose (Spoor links a carrier by place and time, never an identity); the 3D carton is drawn at 2x its size to be visible (LIMITATIONS). Commits from 79b4a57 on; 300 tests pass; production on :3001 rebuilt at 03:00 and the whole demo path clicked through green there (record from :3001); nothing pushed.

## For Rexton, Tue 3 Nov 08:30: what changed overnight (start here)

- **One number for the video: "13 of 13".** Every tracking number Spoor drew on a carton, across all 98 outlines on
  every rendered window, was on the right parcel (checked against the 3-D truth, evaluation only). It shows a number
  only when no other carton could be the one scanned, so most outlines carry none. README, EVALUATION, the demo
  script say the same; the older "51 of 51" was before the stricter rules and is retired.
- **Go look is a real worker app, "Spoor Floor"** (light, for the hall): Tasks -> Find this parcel (last-seen frame,
  tunnel photo, size, number with the last 4 marked, walking route) -> Where to look (checklist, hold-to-talk voice
  note in English or Malay, attached only on "Use this note") -> Scan the label (phone camera; type the last 4 if no
  camera) -> Number matched / Not here (sheet with reasons) -> Spoor re-plans. iOS large titles, edge swipe back, the
  place title flows from the card into the task. Full screen on a phone at `/floor/<case>`; the Go look page shows it in
  a phone frame. Strip: `review/shots/tue/golook/flow.png`.
- **Report = the case file**, six sections: summary + how sure, every step's frame + the reel, a clean vector route map,
  records vs cameras, floor check, evidence with SHA-256 + models + cost. A4 print. "Draft the update to the customer"
  opens a side sheet: chat / email, English / Malay, short / detailed, Spark writes it from verified facts only, each
  fact links to its frame, "Approve and send" is an audited record (nothing leaves Spoor). `review/shots/tue/report/`.
- **Agents page** (`/cases/<id>/investigate`, linked from the Answer and every case header): the run as a detective's
  six questions and answers, every step as a dot per agent (one colour per model), the places as their real frames.
- **Tags at steps 1 and 3:** tried your +0.5 s / +1.0 s retry (2 SAM calls each); neither passed the checks, so both
  stay untagged. Every tag still shown is right (eval 13 of 13). The door step now plays 8 s (the carry is on screen).
- **Decide:** the video script says "Two weeks now"; the case data says the customer waited **4 days** after the last
  scan (28 Oct -> 1 Nov). The app shows 4 days everywhere. Change the script line to "Four days now", or tell me to
  move the case date.
- **Real-footage test (3 Nov):** done on Pexels clip 4156510 (real conveyor, Pexels licence): 9 of 11 scans outlined and
  followed the right item, 51 of 63 checkpoints (81 %); the miss is two touching yellow look-alikes outlined as one.
  The camera pans, so the spot follows its measured shift. Details: docs/EVALUATION.md "Real footage".
- Spend overnight: Modal ~US$0.45, SAM ~US$0.25, Spark drafts a few cents.
- **Screen recordings for the video edit** (production build, 1920x1080, no dev overlay, git-ignored):
  `review/video/scenes/01_landing.mp4` ... `07_report.mp4` in DEMO_SCRIPT order, plus the worker phone flow
  `review/video/spoor_floor_flow.mp4`. Re-record any scene: `node frontend/.local/scenes.mjs 05` (needs :3001 running).
- **Rehearsing changes the case** (Done it's found, Not here, Approve and send): restore with the demo-ready snapshot,
  steps in docs/DEMO_SCRIPT.md. The data is in the demo-ready state now.

## For Rexton, Tue 3 Nov 01:4x: the real-footage test (Task 2), ready to film

- Print `assets/realtest/labels.pdf` at 100 % (three A6 labels, CONTOH Express, CTX900000000101 / 102 / 103).
- Follow `assets/realtest/FILMING.md`: phone fixed 1.8-2.2 m high looking down ~40 degrees, two A4 sheets 1.5-2 m apart
  (S = scan spot, C = cage spot), B and C on sheet C, carry A from S to C, set it next to B, then out of frame. Say
  "scan" when A sits on S. Hands and forearms only. Two takes, 60-90 s each, into `assets/realtest/raw/`.
- Write Box A's size (W x L x H cm) into FILMING.md.
- Last day to film: Tue 18:00 MYT, then the task is dropped.

## 2026-11-02 19:59 · Evening: red only where the records fail, crew storyline, customer note, backend health

- **Red means something again (1707/1708).** Only two steps are red: "Carried into the Exception store · Not scanned
  in" and "Record says RC-760 loaded on D07 · Records disagree". Taken out of RC-760, carried to the door and came out
  without it read "On camera" (grey); the 11 min in the cage reads "No camera" (dotted). Same words on the rail, the
  reel's burned badges, the case hero and the Report captions; the Hub panel already flagged only those two. Shots:
  `review/shots/mon/red/`, reel frames `review/shots/mon/journey/reel_tones_sheet.jpg`.
- **Found and fixed on the eye check:** the reel's store close-up was outlining the carrier (SAM's mask grew onto the
  person). Tracks bigger than the largest parcel at that spot are now skipped; the carton in his hands is outlined
  (`review/shots/mon/journey/store_in_frames.jpg`).
- **What the crew did (1658):** a 7-line storyline by default, each line built from the run's own steps (read the
  scans, Glimmer skipped 83 % of the footage, Wonder planned, SAM tracked who went in and out, the carrier check, 3
  ideas tested with 1 passed, a person asked), the model small on each. The full timestamped log is behind "Show every
  step". Crew panel unchanged on the right. Note: the storyline can't say "hands empty coming out" because the
  analyst's step only records that it checked a clip; I did not invent it.
- **Customer note** has room: a label line, the customer's words as a quote, "Draft the update to the customer" as a
  real button. Shots: `review/shots/mon/crew/`.
- **Backend slowdown: not reproduced.** Replaying the UI's own requests (325 GETs x6), 4 reel builds and page calls
  during a build all stayed at ~0.1 s; threads plateau (OpenCV's pool), no leak found. Paid jobs not re-run to test.
  Added: `/healthz` reports read speed, threads, busy jobs ("slow" over 1 s); finished jobs capped at 200 in memory;
  DEMO_SCRIPT says restart + check health before recording.
- Open, yours: the idle unloader (~35 s) at the re-staged door; about 17 % labelled vs more numbers under a softer rule.

## 2026-11-02 16:51 · TODAY (Mon 2 Nov), for Rexton: done / dropped / open / decisions

**Done**
- **Every story step has its evidence on camera, with the number where it can be trusted.** Unloaded (CHK_UNLOAD),
  Label read (the tunnel's own photo), Into chute C12 (CAM_11) and Into cage RC-760 (CHK_CAGE_W) carry the tracking
  number on SAM's outline; Taken out of the cage, Carried to the store, Carried in (CHK_STORE) are outlined, in red,
  with no number (no scan there).
- **Labels you can trust: 14 shown, 14 on the right parcel** (render truth); 12 pass the strict carton-size test, 2 sit
  just over it (2.55x, 2.61x: a flat bag, and the story's C12 carton with some of its tray in SAM's box; the screen draws
  SAM's tighter mask edge). Checked by eye, zoomed: `review/shots/mon/labelled_sheet_final.jpg`. Cost: coverage fell to
  ~17 % of right outlines (a number only where a rule rules out the tray, the neighbour and the queue).
- **Unload door re-staged on your call:** W1 re-baked with a quiet door (nothing else handled within 10.5 s), start
  re-pinned (logged scan = set-down, 0.0 s), 7 W1 clips re-rendered on Modal, 5 synthetic history lines re-timed by
  audited corrections (LIMITATIONS says so).
- **The parcel's journey** on the case page: one player + a step rail, playing a 60 s evidence video built only from
  stored evidence (`POST /v1/cases/{id}/journey-reel`, downloadable MP4, manifest with every source hash).
  Recording: `review/video/journey/play_whole_journey.mp4` (git-ignored; stills `rec_sheet.jpg`).
- **Design pass from the brand** (tick 1611/1545): flat sections, status dots, plain verbs, monochrome log, indigo used
  rarely, Google Sans Flex, ridge-style journey rail. Before/after: `review/shots/mon/design/`.
- **Investigating** shows elapsed run time, SAM 3.1 visibly used (reused + fresh tracks), whole sentences.
- Demo path walked at 1440 + 390 (`review/shots/mon/demo_path3/`): nothing flagged, no overflow.
- Keyed answer still **"Exception store (Z11)"** (269 s, Wonder US$0.25). Tests 295 pass.

**Dropped**
- CHK_CHUTE close-up for the C12 step: its clock cannot be fitted (one sorter event in its view, since only the story
  parcel's records describe the story windows). The reel zooms far CAM_11 on SAM's outline instead.
- A number on "On the sorter": induction outlines were wrong 4/4 when tried, and the new one is not on the carton; the
  tunnel photo carries the number one step earlier.
- Optional MEVA (day plan H).

**Open**
- The backend slowed to ~20 s per case call after hours of heavy jobs (48 threads; 0.07 s after a restart). Before any
  demo: restart the backend. Thread growth not yet diagnosed.
- Divert-label thresholds were set on the S2 window; there is no held-out window.

**Decisions for you**
1. The re-staged door: the second unloader stands idle ~35 s around the story carton. Acceptable, or re-stage with a
   shorter quiet (the label then needs a fitted door clock instead)?
2. Coverage vs precision: keep "17 % labelled, 100 % right", or show more numbers with a softer rule?

**Spend today (from the cost ledger, uncached calls only):** Modal ~US$1.9 of US$12 (W1 re-renders US$0.39 + US$0.40
GPU + encodes). Meta SAM 3.1: 37,222 frames since midnight MYT, ~US$7.4 at US$0.20 per 1,000 (overnight runs and
the morning's first S2 handshake pass ~US$6.6; since noon, the re-runs, re-prompts, new W1 clips, store door and clock
fit 4,362 frames ~US$0.87, inside the US$5 re-run budget). Muse Wonder: 7 calls, 133k tokens (keyed runs US$0.17 +
US$0.25 shown on the run); Spark: 4 calls, 31k tokens.

## 2026-11-02 15:15 · The parcel's journey: one player, one video (ticks 1406, 1410, 1505)

**Where to look:** case page (answered) -> "The parcel's journey"; `review/shots/mon/journey/` (1440, 390),
`review/shots/mon/reel/chapters_sheet.jpg` (one frame per chapter), the MP4 via "Download MP4".

- One section replaces the tracker strip, the passport and the moments stills (the answer hero and map stay). Step
  rail: time, one line, Scanned here / No scan (red after the last scan), camera, the number only on a labelled
  handshake; a step plays its chapter; "Play the whole journey" plays all 53 s; gaps between filmed steps are the
  connectors; 390: steps stack under the player.
- The video is built by the API from stored evidence only (POST/GET `/v1/cases/{id}/journey-reel`): 12 chapters in
  time order; SAM's own mask edge on the carton on every frame SAM followed it (labelled tracks at chute C12 and cage
  RC-760, the live alert's pick track, CAM_19's verified carry, the carried carton on the store door close-up); cards
  for "In RC-760, no scan for 11 min" and the answer; burn-ins: camera, shared clock, checkpoint, Scanned here / No
  scan, SYNTHETIC; a manifest with every source clip's hash. Cameras for the store and dock steps are chosen by a
  general best-view rule, not by name.
- Cost: US$0.06 of SAM (one "box" pass on the store door close-up); everything else came from stored tracks.

**Open:** Unloaded and the chute close-up wait for the W1 re-render (below); "On the sorter" stays unlabelled (the
induction outlines were 4 of 4 wrong when tried; the tunnel's own photo carries the number one step earlier).

## 2026-11-02 14:42 · Labels on carton-sized outlines only (ticks 1402, 1405, 1426)

**Numbers (stronger eval: IoU and area against the true carton's projected box, clipped to the picture):**

| Scan | Labelled | Right parcel | Carton-sized (IoU >= 0.3, <= 2.5x area) |
|---|---|---|---|
| Divert (sorter points) | 12 | 12 | 11 + 1 flat bag at 2.55x |
| Cage (handheld) | 1 | 1 | 1 (IoU 0.95) |
| Tunnel exit, induction, unload door | 0 | - | - |
| **All** | **13** | **13 (100 %)** | **12** |

Coverage paid for it: 13 of 76 outlines on the right parcel carry a number (17 %); the rest show the scan record.

**Eye check, every labelled tile zoomed** (SAM box green, true carton centre red):
- before: `review/shots/mon/labelled_sheet.jpg` (54 labels): many on EMPTY trays, one on the camera's clock text,
  several tray-sized with the carton on them. IoU alone had passed some of these.
- after: `review/shots/mon/labelled_sheet_chute.jpg` (13 labels): every one on the carton; none on an empty tray.

**Rules (general, from the plan and the scan log):** carton-sized against the parcel's own DWS size at the point
(re-prompt with a parcel-sized box, else no label); no measured size, no label; a divert label needs the outline to
slide into the chute (>= 1.5 m in 1.5 s, twice as far as along the loop; set on this window, no held-out set);
recirculated and induction: no label. Story: chute C12 (CAM_11, IoU 0.47) and cage RC-760 (CHK_CAGE_W, IoU 0.95) keep
their numbers; tunnel via its own photo. **Induction retry (tick 1405):** the "On the sorter" outlines on CHK_TUNNEL
are belt-sized or the queued neighbour (0 of 12 tunnel-exit outlines pass the carton test, IoU 0.07): still no number,
the tunnel's own photo carries it.

**Open:** unload re-render running on Modal (quiet door baked, gates equal to the accepted W1 in every rendered view);
journey reel next.

## 2026-11-02 13:35 · Day plan B-D: controls, customer flow, consistency + demo path, SAM outline

**Decisions for Rexton**
1. **Unload door (tick 1149):** stopped at feasibility inside the 2 h box. In W1 the story carton's release is pinned
   by the other unloader's placement just before it (the story pull waits 2.6 s for the boom nose); a quiet door moves
   the release, so W1's pinned start and all six W1 clips need re-render + re-ingest + re-fit, plus 5 history log
   lines moved as store corrections: ~3 h, under US$1 Modal. Until then the Unloaded stamp shows the real CHK_UNLOAD
   frame as the "Scan record" (no number on any carton; the reason "Three cartons scanned here within 1.0 s" in the
   details). Say "do the W1 re-pin" and it is done tonight.
2. **Skills:** the installed names are `emil-design-eng` and `design-taste` (no skill named "emilkowalski" / "taste").

**Controls re-run (B):** look-alike and belt parcel now "Confirmed on camera" at their divert (C08, C02; right),
unload-only "Located by scan" (right); 0 false locations; the live alert fired on none of them (only the S2 pick).
RC-696 cannot be opened: no parcel or bag was ever scanned into it (only its own RFID at D08). EVALUATION.md updated.

**Customer asked (C):** Hub chip under the tracking number, customer strip on the case (their words, 4 days waited
after its last scan here), Report: update drafted by Spark Open from the verified answer only, the facts it used
folded, "Approve and copy"; nothing is sent (POST /v1/cases/{id}/customer-update; safety terms fall back to a template).

**Demo path (D, tick 1151)** walked at 1440 and 390: `review/shots/mon/demo_path/` (landing scroll in `landing/`).
Found and fixed on the story parcel's path:
- Hub: "Lost track" on every row and a side panel reading raw scans ("Not loaded onto a truck since", "no footage of
  14:21") -> rows and panel read the verified run ("Likely location found", "Most likely in the Exception store
  (Z11).", "Records say loaded on D07 at 14:33. Cameras say it never left.", the CHK_STORE close-up); controls moved
  to Resolved; "Cameras: not checked yet" in the panel's tracker -> from the run; time compare bug (UTC vs +08:00
  strings) that showed "no footage".
- Proof: "Can't tell" / "Not seen at the point" -> "Scan record" with the real frame; thumbnails picking purged
  2688 px clips -> purged clips skipped everywhere; "No footage" tiles removed.
- Investigating: an internal "ScopeError: camera cam_CHK_STORE" line -> the case can be granted cameras installed
  later (case revision, audited; the six checkpoint cameras granted), failed steps worded plainly; the lead prompt no
  longer restates the appearance rule (it tripped the filter). Keyed re-run: "Exception store (Z11)", plan CAM 19 +
  CHK STORE, 172 s, Wonder US$0.17.
- Report: "Lost track after..." headline -> the verified answer; key moments were CAM 06 / CAM 13 views and "No
  picture" -> the answer's evidence on its best cameras (cage, store in/out, dock in red).
- Landing: the whole snapshot was the 31 Oct run (parcel CTX095138712767, a placeholder tunnel photo) -> rebuilt from
  the final S2 render on the story's cameras (CHK_CAGE_W, CAM_13, CAM_19, CHK_STORE) and case.json refreshed.
Automatic check of every screen's text (no "Can't tell", "Not seen at the point", "No footage", "Not checked yet",
record ids, UTC, undefined/null, "Lost track"): clean at both widths.

**SAM outline (ticks 1233-1319):**
- Passport tiles, the Hub alert card and the moment thumbnails are focus crops from SAM's own box (server pads it;
  never hand-tuned), with the outline drawn; click a passport tile: its clip plays with the outline following the
  carton, then hands over to the next one.
- **Mask edge:** SAM's masks were in its cached raw output all along (our parser kept only the fill); they are now
  traced to polygons per frame (`/v1/media/{m}/tracks/{t}/contours`, test) and drawn instead of the box.
- **"Not marked correctly" (Into chute C12):** checked end to end on the original 1920x1086 frame: the stored
  handshake (frame 23) sits on the carton. What looked wrong was SAM's propagation AFTER the divert: once the carton
  slid down the chute the track latched onto the empty tray. The follow is now shown only up to the scan instant.
- "Black" tiles: lossless 2-3 MB PNG frames still loading while a SAM job held the process -> on-screen thumbnails
  use a downscaled JPEG preview (labelled `*_preview`; exports keep the original) and a frame cache.

**Design pass (four skills):** moments without 01-05, one time + one line, equal cards, the two problems in red, the
selected one ringed and synced with the hero, thumbnails zoomed on the outline; tracker: place name is the map link,
calmer type; impeccable detector: no findings.

Open: the handshake re-run on the valid W1 copies (SAM slow this hour), then the precision re-check; docs (F), video
captures (G), the 19:00 summary.

## 2026-11-02 09:55 · Six checkpoints step 6: handshake, passport, live alert (and the rest of the render)

**Render of the rest (tick 0535) done, frames checked, ingested:** S2 `CHK_STORE` (200-480), W1 `CHK_CHUTE` + `CAM_11`
(945-990), W2 `CHK_CHUTE` (30-100) + `CHK_CAGE_W` (220-320); W2 `CAM_13` not rendered. Modal GPU ~US$0.32 + encodes
(total Modal ~US$1.1 of US$12). Meta SAM for handshakes ~US$3.25 (FOR_REXTON.md has both totals).

**Handshake checked against the render truth (evaluation only, `frontend/scripts/eval_handshakes.py`,
`docs/open_weights_proof/handshake_eval.json`).** The first run looked fine in counts (253 "outlined") and was wrong:
12% of outlines were the scanned parcel. Two general causes, two general rules:
- SAM sometimes outlines the belt, a cage or the whole frame: an outline more than twice the largest parcel (0.9 m
  cube projected at that point) is not a parcel -> "not found".
- A camera clock known only to the uploader's +-5 s can't say which carton was at the point (a belt passes one a
  second) -> "clock not fitted", no SAM call.
After: **67% strictly right, 86% right parcel nearest** (65 of 76 judged; fitted cameras CAM_09/10/11/13, CHK_TUNNEL).
Wrong ones left: CAM_11 6, CAM_13 4 (neighbouring cartons on the sorter), W1 CAM_05 1 (the passport shows CHK_TUNNEL's
right one for that scan).

**Passport (answer page) for the story parcel:** tunnel 14:10:40 met on CHK_TUNNEL, divert into C12 14:11:16 met on
CAM_11; unload, chute and cage "camera clock not fitted" (CHK_UNLOAD, CHK_CHUTE, CHK_CAGE_W have no sorter events to
fit from); induction "not seen" (only belt-sized outlines). Said, never faked.

**Live alert "left without a scan" (Hub):** fires once: **CHK_CAGE_W 14:32:13.8, "could be CTX334048419302"** (the
pick from RC-760, before the cage's RFID load at D07). Not on CAM_13, not on W2's set-down, not on the east cage (RC-696
/ D08 control: that cage holds bags only, so it is not watched). Rules, all general: open containers only (cage, pallet,
gaylord); candidates are parcels; a container's own read accounts for its parcels only from that read on; on an
unfitted clock only parcels caged more than its +-5 s before the exit count, and the alert says so; a close-up whose
view the work area fills counts a carton carried out of view.

**Found on the way:** the importer typed parcel-into-bag scans as "cage" (361). Fixed in seed_nokey.py; this store gets
append-only `incorrect_data` corrections (`frontend/scripts/correct_bag_types.py`), and the planners read the log after
its corrections.

**Story tunnel photo retaken** from W1 at the real read (`scanner_photos.py --replay`): no more "from recorded history".

Open: step 7 (keyed S2 re-run + controls), step 8 (Proof as one timeline of the checkpoint clips, landing).

## 2026-11-02 04:30 · Render (approved part) done; three previews waiting for the next tick

Rendered on Modal (tick 0403 APPROVED partial), full resolution, ~US$0.8 actual (estimate US$2.12):
`assets/hub/build/renders/W1/` CHK_UNLOAD, CAM_02 (f170-242: reach + the story release, ends before the next
carton's overlap at f244), CHK_TUNNEL (f585-725), CAM_05, CAM_01; `assets/hub/build/renders/S2chk/` CHK_TUNNEL,
CHK_CAGE_W, CHK_DOCK. OSD clocks: W1 reads 14:09-14:11, S2 14:32-14:33, each camera on its own planted offset.

RC-760 (tick 0403 check 2): its only container_add in the scan log is the story parcel (14:21:33), then the cage's
RFID read at D07 (14:33:25). No other parcel was ever scanned into it, so the empty cage at D07 is the point.

Waiting for review (previews, CCTV look, 5 fps, `qa/review/chk_preview/`):
- `S2_CHK_STORE.mp4` (re-mounted as a door camera: outside, above, facing the opening with the SCAN IN post in
  frame; held-out 1.0 cm, 0.37 px): carried past the unused handheld 14:32:29-31, in, back out empty ~14:32:48.
- `W1_CHK_CHUTE.mp4`, `W1_CAM_11.mp4`: the divert into C12 at 14:11:16 (planned window f945-990: a different
  carton passes 10 cm into a chute at f998-1000, so it stops before that).
- `W2_CHK_CHUTE.mp4` (the pick out of C12's bag 14:21:11-18; her hands brush the bag rim 2 frames) and
  `W2_CHK_CAGE_W.mp4` (set-down on S11's shelf at 14:21:35, from the fixed blend: the carton rests exactly at S2's
  frame-1 pose, no overlap).

## 2026-11-02 03:55 · Six checkpoints steps 2-3: cameras, W1/W2 sims, gates, local previews (render NOT started)

### Look at (low-res local previews, CCTV look + OSD on each camera's own clock; 5 fps)
`qa/review/chk_preview/`:
- `S2_CHK_TUNNEL.mp4` (14:32:04-18): the look-alike comes out of the tunnel exit first at 14:32:08, the next carton
  after it; belts keep order, so the first-out rule has what it needs.
- `S2_CHK_CAGE_W.mp4` (14:32:05-25, re-mounted): the carton on S11's mid shelf, the reach at 14:32:10-11, the shelf
  empty at 14:32:12, walked off at 14:32:14 (the live alert's moment, close up).
- `S2_CHK_STORE.mp4` (14:32:19-54): walks up with the carton label-up 14:32:29-30, under the camera into the store
  14:32:31, back out empty-handed 14:32:48-49.
- `S2_CHK_DOCK.mp4` (14:33:15-37): the cage pushed into D07 at 14:33:25 past the RFID gate.
- `W1_CHK_UNLOAD.mp4`, `W1_CAM_02.mp4` (14:09:58-10:06): the story carton off the trailer onto the boom (release =
  the unload scan 14:10:01.26 on the handheld clock).
- `W1_CHK_TUNNEL.mp4`, `W1_CAM_05.mp4`, `W1_CAM_01.mp4` (14:10:38-10:52): out of the tunnel at its logged second,
  onto carrier at the merge.
- Still rendering: W1 chute divert (CHK_CHUTE, CAM_11), W2 (CHK_CHUTE pick, CHK_CAGE_W set-down) from the fixed blend.

### What was built
- Six checkpoint cameras from the plan (commits db0f66a, 66875d1): CHK_UNLOAD, CHK_TUNNEL, CHK_CHUTE (bank C10-C12),
  CHK_CAGE_W (5 m over the aisle, all of S11-S13), CHK_STORE (rack frame above the gap), CHK_DOCK (side of D07).
  Install survey + the backend's own fit: held-out 0.7-2 cm median; reprojection 0.6-1.2 px median over 274-1,022
  marks never used in the fit. Two were re-mounted after test stills (tunnel exit not in view; store blocked by a
  rack end), CHK_CAGE_W once (S11 at the frame edge): mount position only, never aimed at the story.
- W1 14:09:39.66-14:11:24.66 (5aa941f): an unloader's wall carton becomes the story carton (its record's size, label
  tile 677), waits ~2 s at the belt end before the DWS and ~5 s at the merge like any parcel, goes down C12. Physical
  vs logged (true) seconds: unload 0.00, tunnel -0.03, carrier +0.07, divert +0.08. The log is unchanged.
- W2 14:21:06.70-14:21:46.70 (69ade1c): a bagger (Female_Adult_17, no clone on screen) takes it out of C12's bag,
  carries it round the column, sets it on S11's mid shelf; the set-down (the cage scan) at 14:21:35.60 true =
  logged 14:21:33.60; rest pose = S2 frame 1 exactly (26.13, 30.30, 0.90); same object name flow_parcel_5013.

### Gates (honest)
- W2: 0 hard, 0 parcel overlaps, 0 strict on the story carton. Found and fixed: flow's snap_rests dropped the carton
  1.65 cm into S11's shelf (now exempt, W2 re-baking). Other stations' rows sit in the wide cameras' frames (C07
  bagger 1-5.7 cm, a cage pusher's vest 5.6-5.9 cm on CAM_13), so W2 is planned on CHK_CHUTE + CHK_CAGE_W only;
  left there: her hands brush C12's bag rim for 2 frames (1.5-1.8 cm) at the reach.
- W1: gates still running (1,050 frames).
- Per reviewer_tick_0147: wide-camera W1/W2 clips come before close-ups, the cage close-up last and droppable. If the
  W2 wide shots can't be cleaned (CAM_13 rows above), CHK_CAGE_W carries W2 or W2 is dropped (fallback: the S2
  window alone shows the cage pick).

### Render plan for the APPROVED tick (estimate unchanged, ceiling US$6 of the US$12 cap)
W1: CHK_UNLOAD + CAM_02 (unload), CHK_TUNNEL + CAM_05 + CAM_01 (tunnel, carrier), CHK_CHUTE + CAM_11 (divert C12).
W2: CHK_CHUTE (pick), CHK_CAGE_W (set-down) [+ CAM_13 only if its rows clear]. S2 window: CHK_TUNNEL, CHK_CAGE_W,
CHK_STORE, CHK_DOCK (CHK_CHUTE dropped: the look-alike goes down C08, outside its bank). Full resolution 2688 x 1520,
same CCTV look, MP4s only come down.

## 2026-11-02 02:00 · Six checkpoints on camera: step 1 (feasibility, same-parcel checks, estimate)

Read: six_checkpoints_on_camera_0915.md with addenda 1-6, reviewer_tick_0147.md. Nothing rendered, S2 window and
store untouched.

### Same parcel across windows (addendum 1)
- **Was the story parcel's journey before 14:32:07 simulated? No.** `stations.BlindRemoval.history_events` only
  writes it as `history=True` lines (unload, tunnel, induct, divert C12, cage). No carton moved in any sim before the
  window. So W1/W2 must make it physically ride, pinned to the logged times, the log unchanged:
  unload 14:10:01.26 (SP-IN-N, handheld OP-***17) · tunnel 14:10:40.69 · induct 14:10:50.49 (carrier 5) ·
  divert C12 14:11:16.38 · cage RC-760 14:21:33.60 (SP-CAGE-W, handheld OP-***08).
- **Same object in every window:** `flow_parcel_5013` (truth file), 0.25 x 0.18 x 0.10 m; the tunnel record says
  25.5 x 18.3 x 10.2 cm (the record's own +-4 mm noise) and 1,824 g; label tile 677 printed CTX334048419302 / KUL /
  C05. W1/W2 use the same object, size and label tile.
- **Continuity:** at S2 frame 1 the carton sits at (26.13, 30.30, 0.90), on the mid shelf of the cage in bay S11.
  W2 ends with the place at exactly that pose (the same constants that put it there now), in the same cage (same
  build code and seed). Side-by-side still (W2 last frame vs S2 frame 1, same camera) comes with the step 3 preview.
- **Other parcels:** the long log's earlier traffic is from a separate sim-only run with synthetic ids, and it is
  not in the store or the app (the store is seeded from `events_scan_simulated.jsonl`: the window plus the story
  parcel's history; only `scanner_photos.py` reads the long log). Re-running that sim today is deterministic (two runs
  identical, 2,674 lines) but differs from run 18's (2,341 lines), because its inputs changed since (the untracked
  `hub_spec_lineAb.json`, edited 1 Nov for the scan points). So W1's other parcels take their identities from the W1
  run itself; their W1 scans are ingested with the clips (step 5) and the long log's earlier part is re-spliced from
  the same run. No record already in the store changes.
- **Look-alike CTX976456695076** is `flow_parcel_5014`, physically simulated in the S2 window (tunnel 14:32:08,
  induct 14:32:12.9, divert C08 14:32:35.8): its handshakes come from the existing S2 footage plus the new checkpoint
  cameras rendered on the same S2 blend.
- **C05 vs C12 is intended, not a bug:** the label says KUL, the sort plan sends KUL to C05, the sorter put it down
  C12, and the bagger set the mis-sort aside into the cage (the stations.py comment). The data stays; the app now says
  "Down C12 (assigned C05)", and addendum 4 #3 (scan vs camera disagreement) has a real case.

### Checkpoint cameras (addendum 6)
Six close-up CCTV cameras, mounted the way a hub mounts them, placed from the site plan only (never from the truth or
to dodge the story parcel), same 2688 x 1520 CCTV look and OSD, own clock domain with a planted offset, calibrated with
the same install survey (floor marks + held-out check), fitted like the others. The 19 wide cameras do not change.

| Camera | Mount (plan) | Sees |
|---|---|---|
| CHK_UNLOAD | inbound door N, on the wall above the door, ~3.2 m, looking into the hub | unloading point SP-IN-N, the handheld scan |
| CHK_TUNNEL | on the tunnel frame past its exit, ~2.6 m, looking back down the belt | cartons coming out of the tunnel (first-out rule, addendum 2) |
| CHK_CHUTE | ceiling over the chute row, ~4.5 m, looking along the chute mouths | diverts into the chutes (C07-C12 side), general for that row |
| CHK_CAGE_W | ceiling above the west cage bays, ~4.2 m, looking down at the bay fronts | cartons on cage shelves, hands taking them, the cage scan |
| CHK_STORE | on the store's front wall beside the gap, ~2.8 m | the door, its SCAN IN handheld, in and out |
| CHK_DOCK | inside above outbound doors D06-D08, ~4.5 m | cages through D07 and its RFID gate |

Target: the carton at >= 250 px/m (a label readable), checked per camera with numbers in step 2. Docs will say "19
wide CCTV cameras plus 6 checkpoint cameras, added for these checkpoints" and "1 tunnel label camera".

### Windows and frames (10 fps; the sims run continuously, only each checkpoint's moment is rendered)
| Window | Cameras and moments | Frames |
|---|---|---|
| W1 sim 14:09:50-14:11:30 | unload 14:09:55-10:10 (CAM_02, CHK_UNLOAD) · tunnel + induct 14:10:36-10:56 (CAM_05, CHK_TUNNEL; CAM_01 10 s) · divert C12 14:11:10-11:24 (CAM_11, CHK_CHUTE) | 1,000 |
| W2 sim 14:21:10-14:21:50 | the bagger carries it from C12 to bay S11, sets it on the mid shelf, scans it (CAM_13, CHK_CAGE_W) | 800 |
| S2 window, new cameras only | CHK_CAGE_W 14:32:05-32:25 (the pick) · CHK_STORE 14:32:18-32:52 (in, out empty) · CHK_DOCK 14:33:15-33:37 (cage through D07) · CHK_TUNNEL 14:32:05-32:20 and CHK_CHUTE 14:32:30-32:42 (look-alike) | 1,030 |
| Total | | ~2,830 |

### Cost and time
- Measured, not the rule of thumb: the S2 render was 17,100 frames for about US$19 including start-ups and encodes,
  so **US$1.11 per 1,000 frames**. 2,830 frames is about **US$3.1**, plus ~12 short jobs' start-ups (~US$0.6):
  **about US$4, ceiling US$6** with margin. Inside the US$12 cap. (Full windows on every camera would be ~12,200
  frames, ~US$13.5: over the cap, not proposed.) Glimmer on the new clips: under US$0.30.
- Modal wall time about 1 h in parallel. Local work: cameras + calibration ~2 h; flow window shift + pinned story
  parcel (W1) ~2-3 h; W2 action ~3-4 h; gates + low-res preview ~1.5 h.

### Risks (honest)
- **W2 is the risky one:** a new action (the bagger carries the loose carton to S11, sets it on the mid shelf with
  the existing place take, scans it with the handheld). Same gates; if not clean after 3 sim runs or by Tue 12:00,
  W2 is dropped and CHK_CAGE_W in the S2 window (the pick at 14:32:10) carries the cage checkpoint.
- **W1:** the flow pins frame 1 to 14:32:07, so it needs a window offset (sim from -1400 s as the long log, frames
  mapped to W1), and the story parcel pinned to its logged times. If the belt queue delays it, it is scheduled ahead
  so it reaches each scanner at the logged second. Gates run on W1's own frames (the stations act differently there).
- Line B stays unstaffed in W1/W2 (same `--unstaff opener,dock_D02,lineB` as S2). The tunnel photo is re-taken at
  the real 14:10:40 in W1 (reviewer 0147).
- Disk: 12 GB free (under the 15 GB floor). Previews are low-res; full renders stay on Modal (MP4s only come down).

Next: step 2 (cameras placed + calibrated, W1 sim + gates), step 3 (local preview MP4) tonight. Modal only after a
reviewer_tick says APPROVED.

## 2026-11-02 01:37 · Investigating screen runs the real keyed investigation (commit 141d9c0)

What changed
- With model keys, the Investigating screen (`/cases/<id>/investigate`) now runs the real pipeline, not a stand-in:
  Muse Wonder plans first (its plan is checked; a failed plan is sent back once and the screen says so), then the
  Spark Open evidence agent's tool calls appear one per step as they finish (scans read, footage found, door
  crossings, likely carrier, SAM tracks, Muse Spark clip checks), then the hypothesis agent's ideas, each followed by
  the verifier's verdict, then the verified sentence, then the search task. Title = the verified headline.
- Every sentence is Spoor's own, built from tool results. Agents' words appear only quoted as "Idea: ...", with plain
  place names and local time (raw wording kept in the record). No S2 names in code, prompts or rules.
- The cost meter counts only priced calls (Muse Wonder). Spark Open has no published Baseten price, so the footer
  reports its tokens. Glimmer's US$0.62 is a one-off on-site run over all footage, shown in its step's receipt, not
  charged to the case.
- The run's end is stored, so a replay ends on the same headline and words.

Where to look
- `/cases/case_18e3f000a5a53074ada1b725/investigate` (backend `node scripts/backend.mjs --data s2r18c --keys`).
- Last run: 100 s, Muse Wonder US$0.14, Spark Open 132k tokens; title "Most likely in the Exception store (Z11)."

Open
- When Muse Wonder's plan fails the checks twice (seen once tonight: 7 steps with unknown cameras), the agents still
  work from the scans and reach the answer; the screen says the plan failed.
- "1 of 19 cameras checked": SAM results are cached from earlier runs, so the agents did not re-run SAM; the count
  covers cameras the verifier used in this run only.

## Next (in this order, per Rexton 2 Nov)
1. Case-page cleanup: one source of truth (the latest verified run) for timeline, checkpoints, where it could be;
   truck D07 checkpoint amber/red; C05 vs C12; fewer sections. Not started.
2. Six checkpoints on camera, steps 1-3 tonight (estimate + same-parcel checks here, sim + gates, local preview MP4).
   Step 4 (Modal render) only after a reviewer_tick_*.md says APPROVED, up to US$10 total.
3. Divert-scan fix ("last scan record, not seen on camera"; located by scan vs confirmed on camera in EVALUATION.md).
4. Caged-and-left control: the parcel in RC-696 (RFID at D08 14:32:19).
