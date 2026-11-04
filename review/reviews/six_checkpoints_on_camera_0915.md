# Owner request (Rexton, Mon 2 Nov): the parcel identified ON CAMERA at its checkpoints

Rexton's words: each checkpoint knows exactly which parcel it is at the scan instant, so the camera watching that
checkpoint can circle the carton coming out of the scanner a few seconds later. He wants the story parcel shown this
way across the checkpoints, not one camera. He accepts re-doing the video for it. This is now the top priority after
the case-page cleanup you are on. Read fully before starting.

## The idea (call it "scan-to-camera handshake")
At a scan, the scanner gives IDENTITY (barcode) + PLACE (scan point) + TIME. With what is already built:
- visible_by + calibration (pose, lens, < 5 px) -> the scan point's pixel in each camera that sees it
- clock fits (camera clock vs sorter clock, ±0.1-0.2 s) -> the exact frame
-> a SAM 3.1 point/box prompt at the scanner's pixel at that frame outlines THAT carton, labelled with its tracking
number, and SAM follows it for the next few seconds as it leaves the scanner (until the next camera or it is lost).
The scan says WHICH parcel; the camera shows WHAT HAPPENED next. Must be general: any parcel, any scan point, driven
only by the scan record + site plan + calibration + clock fit. No S2 constants anywhere.

## Why footage is missing today
The S2 render covers 14:32:07-14:33:37 only. The story parcel CTX334048419302 was scanned earlier:
unload 14:10:01 (SP-IN-N, handheld) · tunnel 14:10:40 (SP-TUNNEL) · induct 14:10:50 · divert C12 14:11:16 ·
cage RC-760 14:21:33 (SP-CAGE-W, handheld) · [store scan-in: never, that is the story] · truck RFID D07 14:33:25.
So two more short footage windows are needed. NO new cameras: existing cameras already watch every checkpoint
(check visible_by for each scan point and use the best 1-2 cameras per checkpoint).

## Plan (in this order; estimate before any paid run)
0. Commit everything first. Do NOT modify or re-render the existing S2 window (14:32:07-14:33:37) or its store.
1. FEASIBILITY + ESTIMATE (write it in review/READY.md, then wait for Rexton's OK in chat or a reviewer tick):
   - Can the same flow run (run 18, same seed, same parcel identities and timings as events_scan_simulated_S2_long)
     be animated for two extra windows?
       W1 ≈ 14:09:50-14:11:30 (unload -> tunnel -> induct -> chute C12), cameras that see SP-IN-N, SP-TUNNEL,
          SP-INDUCT, SP-DIV-C12 (likely CAM_02, CAM_05, CAM_01/04, CAM_11; confirm from visible_by)
       W2 ≈ 14:21:15-14:21:50 (handheld scan into cage RC-760), the camera(s) that see SP-CAGE-W (CAM_13 + any overlap)
   - Frames, Modal cost (use the S2 actuals: ~US$0.47 per 1,000 frames on L4/A10G), wall time, and the glitch risk
     for the stations in those views at those times. Any single run > US$10 needs Rexton's OK.
2. SIM + GATES for W1/W2 with the existing gates (collisions, head clips, overlaps, feet, turn caps) on the cameras
   that render. Story parcel's history must stay identical to the long log (same times, same cage RC-760).
3. LOCAL PREVIEW FIRST: low-res MP4 grid of W1/W2 cameras; Rexton or the reviewer watches it before the Modal render.
   Fix only glitches visible on camera. Max 3 sim runs per window, then lock the best.
4. MODAL RENDER of W1/W2 (frames stay on Modal, download MP4s only), same CCTV look/OSD as S2.
5. INGEST into the S2 store as extra clips on each recorder's own clock (like the run-18 reseed); clock fits must
   recover the planted offsets for these clips too.
6. HANDSHAKE for every scan inside any footage window (W1, W2 and the existing S2 window): point prompt at the
   scan point's pixel at the scan frame, follow a few seconds. For handheld scans (unload, cage) use the work-area
   box + the scan instant (carton in the worker's hands). Store per scan: outlined? frames followed? camera.
   Report precision honestly: how many scans in the windows were outlined on the right carton (check against truth
   only in the evaluation, never at runtime). Include the look-alike CTX976456695076 (tunnel 14:32:08, induct
   14:32:12.9, divert C08 14:32:35.8): its handshakes are what visibly rule it out.
7. KEYED S2 RE-RUN, agents unchanged: the answer must still be "most likely in the Exception store (Z11)". The
   agents may now cite the handshake at the cage scan as the start of the trail.
8. FRONTEND:
   - Proof page = one timeline of the 6 checkpoints, each with its clip and the outlined carton + tracking number:
     1 Unloaded (W1) · 2 Tunnel (W1, + tunnel photo) · 3 Into chute C12 (W1) · 4 Into cage RC-760 (W2) · then
     "in the cage, no scan for 10 min" · taken out 14:32:10 (CAM_13) · carried to the store (CAM_19) ·
     5 Exception store: carried in WITHOUT the scan-in (CAM_19 shows the handheld at the door unused) ·
     6 Truck D07: RFID "loaded" 14:33:25 while the cage leaves without it (records vs cameras, red).
   - Route wall: one card per camera moment, real clips, no "No footage" for these steps.
   - Investigating screen and look-alike card use the handshake ("identified by its own scans on N cameras").
9. Labels: footage is synthetic; scan logs simulated; say "SAM outlines the carton at the scan instant", never
   "identified by size and look". Parcels, not people; no faces; plain words; no em dashes.

## Time box and fallback
- Deadline Thu 5 Nov 10:00 MYT; video is recorded Wed. W1/W2 must be rendered and ingested by Tue 18:00.
- If W1 or W2 is not clean after 3 sim runs or by Tue 12:00, stop that window and ship what works. Step 6 on the
  existing S2 window (look-alike + other parcels scanned during 14:32-14:33) is the minimum and needs no render.
- Commit after every step that works; one log line per commit with the real system time (`date`).
- Write review/READY.md after steps 1, 3, 6 and 8 with the screenshots/clips to look at.

## ADDENDUM: same parcel across windows (Rexton's question, must be answered in step 1)
The clips only make sense if the carton in W1/W2 IS the same object as in the S2 window. Check and report:
- Was the story parcel's journey before 14:32:07 actually SIMULATED, or only written as history records
  (stations.py S2.history_events writes unload/tunnel/induct/divert/cage as history=True lines)? If it was only
  written, W1/W2 must make the parcel physically ride that route at exactly those logged times (unload 14:10:01,
  tunnel 14:10:40, induct 14:10:50, divert C12 14:11:16, cage RC-760 14:21:33); the log must not change.
- Same object in all windows: same object id (flow_parcel_5013 or whatever S2 uses), same size
  (25.5 x 18.3 x 10.2 cm, 1.82 kg as the tunnel measured), same label/texture, same barcode on the label.
- Continuity: where the parcel sits at the end of W2 (which shelf of RC-760, in bay S11) must equal where it sits at
  the start of the S2 window (14:32:07), and RC-760 must be the same cage in the same bay. Show a side-by-side still.
- Same for the look-alike and any other parcel the handshake uses: identities in the clips must match the scan log.
If any of this cannot be made consistent, say so in READY.md before rendering anything.

## ADDENDUM 2: "the first parcel coming out" (Rexton)
Where the carton is hidden at the scan instant (inside the scan tunnel, under an arch), prompt at the EXIT, not the
reader: the parcel read at time t is the first carton to come out of the exit after t, at t + (reader-to-exit
distance / belt speed) from flow's belt geometry. Belts keep order, so mark the first carton out in that time window;
if two cartons come out within the uncertainty, mark neither and say "two cartons, can't tell" (honest abstain).
Handheld scans: the carton is in the worker's hands at the scan instant (work-area box). Chute divert: the carton at
the divert point at the confirm instant, then down the chute. Report per scan type how often the first-out rule hit
the right carton (evaluation only).

## ADDENDUM 3: keep the mark from camera to camera (Rexton)
After the handshake marks the carton, keep it marked for as long as cameras can see it, not only on the scan camera:
- Inside one camera: SAM follows the marked carton until it leaves the view or is lost (re-prompt on a later frame
  if it is briefly hidden; never trust SAM track ids across exits).
- To the next camera, link by place + time only (already built for the carrier check): overlapping views -> same
  floor position at the same synced moment; on a belt -> predicted position on the next camera from belt path,
  speed and order; walking -> reachable in that time. If two cartons fit, keep both as candidates and mark neither
  as the parcel ("can't tell"), never guess.
- Every next scan re-confirms the identity and resets the chain (scan = certain; between scans = followed).
- On screen, two clearly different labels: "Scanned here" (identity from the barcode) and "Followed on camera"
  (linked by place and time, with the camera hand-offs listed). A link that rests on a guess is shown as "likely".
- Report per window: how long the parcel stayed marked, how many hand-offs, and any breaks.

## ADDENDUM 4: what the handshake must cover (Rexton + reviewer brainstorm)
Edge cases (handle honestly, general code):
- Two cartons out of the tunnel exit within the uncertainty: break the tie with the tunnel's own measurement
  (L x W x H from the DWS record) against the SAM box measured through the calibration on a near camera; if the
  sizes don't separate them, "two cartons, can't tell". Never guess.
- Carton hidden at the scan instant (worker's body, arch): mark it when it reappears within a short window.
- Scan point no camera sees: label "Scanned · not on camera" (no fake clip).
- No-read at the tunnel (S1), dropped off the belt (S3: not on the next camera when predicted -> "should be here,
  isn't"), RFID wrong door (S4: camera shows the cage elsewhere), look-alikes (S5: each identified by its own
  scans). Only S2 is rendered; write in README/LIMITATIONS how the handshake covers each scenario.
New outputs (build in this order, only after steps 1-8 work):
1. PARCEL PASSPORT: a strip of the outlined carton crop at every checkpoint where it was marked (time, camera,
   "Scanned here" / "Followed on camera"). On the Proof page and the case header. Mention its use for damage claims.
2. LIVE ALERT "left without a scan": a carton marked at a container scan (cage/bag) that is seen leaving that
   container's area with no new scan of it -> exceptions inbox alert at that moment, before any complaint. In S2
   this fires at the CAM_13 pick (14:32:10-12): the cage scan identity + the work-area exit. Must be general (any
   container, any parcel) and must not fire for parcels that are scanned out normally (check on the control parcels).
3. SCAN-VS-CAMERA DISAGREEMENT: when the camera shows the marked carton going somewhere other than the record says
   (e.g. tunnel destination_chute vs the chute it actually went down), flag it as a sorter/scan mismatch. First
   confirm whether the story parcel's C05 (tunnel destination) vs C12 (divert) is intended; if it is a data bug,
   fix the data instead of building a feature on it.
4. COVERAGE GAPS: list of scan points no camera sees (from visible_by), shown in Settings > Cameras.
Priority if time runs short: 1 and 2 first (demo value), 3 only if C05/C12 is real, 4 last.

## ADDENDUM 5: landing page too (Rexton)
The landing page's checkpoint section ("How a hub tracks a parcel", the right-hand content) must also get, for each
checkpoint, the nearby camera's clip of the parcel passing through it with the carton outlined and its tracking number
(from W1/W2 + the S2 window), so a visitor sees the parcel at every checkpoint. Same clips and labels as the Proof
page ("Scanned here" / "Followed on camera"); the store checkpoint shows "carried in, not scanned"; the truck
checkpoint shows the cage leaving without it. Refresh public/landing/case.json from the store after the handshake.

## ADDENDUM 6: CLOSE-UP CHECKPOINT CAMERAS (Rexton, most important addendum)
Rexton means NEW cameras mounted very close to each checkpoint, like real hubs have at scan stations and dock
doors, so the carton is big and clear in the picture (label visible), not a far CCTV view. Add one per checkpoint:
  CHK_UNLOAD (SP-IN-N, over the unloading point) · CHK_TUNNEL (tunnel exit, looking at parcels coming out) ·
  CHK_CHUTE_C12-style (a chute-row camera that sees the divert into the chutes; general for the chute row, not only
  C12) · CHK_CAGE_W (over the west cage bays, close enough to see cartons on the shelves and hands taking them) ·
  CHK_STORE (the Exception store door + its SCAN IN handheld) · CHK_DOCK (outbound dock doors incl. D07 + RFID gate).
Rules:
- Place each where a hub would really mount it (on the scanner frame, ceiling above the bays, over the door), at a
  realistic CCTV height and lens, using the site plan, NEVER tuned with the answer key to dodge occlusion of the story
  parcel. Accept whatever it then sees. Same CCTV look, OSD with its own name and clock.
- Add them to hub_spec (cameras, visible_by), calibrate with the same install survey (floor marks + held-out
  check), plant their own clock offsets and fit them like the others. Wide cameras CAM_01..19 stay unchanged.
- Render each checkpoint camera only for the windows where its checkpoint matters: W1 (unload, tunnel, chute),
  W2 (cage scan) AND the existing S2 window for CHK_CAGE_W (the pick 14:32:10), CHK_STORE (carried in / out empty)
  and CHK_DOCK (cage RC-760 through D07 at 14:33:25). Do not re-render the existing 19 cameras.
- Fold the new cameras into the step-1 estimate (frames, cost, time). Total for W1/W2 + checkpoint cameras must be
  <= US$12 (Rexton raised it), or it waits for Rexton.
- The handshake (step 6) prefers the checkpoint camera; the wide cameras show context. The keyed S2 run must be re-run
  after the new clips are ingested; report whether the answer and the controls change.
- Docs: "the hub has 19 wide CCTV cameras plus 6 checkpoint cameras"; no hiding that they were added.
