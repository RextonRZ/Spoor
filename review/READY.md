# READY for review

Newest first. Each entry: what is done, where to look, what is still open.

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
