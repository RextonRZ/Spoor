# Request 006: A1 + A2 (people rebuilt on the flow timeline) + review-001 fixes

Built from the 04:28 snapshot (rebuild 31). Several fixes (§3) are already being tested; please concentrate on what §3 does not list.

## 1. Changed since last request

**Fixed from review 000:** 1, 2, 3, 4, 5, 8, 9, 12, 13 and 14. Item 6 was accepted as opaque, item 7 is done, item 10 is auto-flagged, and item 11 was closed in review 001.

**Fixed from review 001:** 1 lighting, 2 OSD clocks, 3 cages, 4 floor parcels, 5 loop guarding, 6 lens (render_truth k1 in cctv_batch) and 7 floor wear. Builder items from review 004 are also fixed: the shelves, and the bag container scans.

### People: every worker rebuilt as Rocketbox (MIT) on the flow timeline
Per Rexton's decision, Mixamo is out of the render path.

| Station | Workers | What they do (real contact) |
|---|---|---|
| Dock unload D02/D05 | 4 | Each takes the top carton of a column from a packed parcel wall inside the lorry, near the doors, and holds it at the chest until the boom nose is clear (and the other unloader is clear of it). Then they turn, set it on the boom, and the carton becomes that flow parcel. Cycle 4–6 s. |
| Induction | 3 | Between a new accumulation feed belt and the induction belt (0.55 m aisle). Each takes a stopped parcel from the queue (which then acts as a zone stop), checks it label-up, waits for a ≥0.3 m gap, turns through the front with pivot steps and sets it down. About 3.5 s per parcel. |
| Roll cages | 2 | Push from staging bays to the D08/D11 doors across new zebras ZX5–7, with both hands on the back posts at 1.0 m and the wheels spinning. One also brings an empty cage back into a bay. |
| Bag change C07 | 1 | Unclips the full bag, lifts it out tied (Rexton's rule: no tying is animated), carries it by the neck to a cage in S06, takes the spare off the hook and clips a new bag on. The C07 stack light is red until the new bag hangs, while the sorter recirculates C07 parcels (`recirculate_chute_full`). Scans: `bag_close`, `container_add` (bag→cage) and `bag_open`. |
| Bag opening | 1 | Takes parcels from an opened sack on bench 1 and sets them on the collector's near half into gaps; they then flow on to induction. |
| Walkers | 2 | Walk on the W3 and W1 centre lines at the clip's stride speed; one stops to look at the reject chute. |
| Technician | 1 | Taps the HMI touchscreen by the tunnel. |
| Supervisor | 1 | Texts on a phone held in the hand, with glances at the chutes. |
| Cage checker | 1 | Holds a clipboard at the destination tag of cage S08. Replaces the old people.py worker, whose facing was about 80° off. |
| Break table | 2 | One sits on a real chair with forearms on the table; one stands texting. |

**Contact solver** (assets/hub/contact.py):
- Blender's IK can't drive Rocketbox: the FBX bone tails don't point at their children (measured: tail→child = length × 1.41). So the solver is an analytic two-bone IK, oriented by each limb's hinge so the arms never flip.
- Feet are pinned, with pivot steps on big turns and a settling step after each walk.
- The trunk does reach adaptation: it leans first, then twists, then shifts the hips a little (never while walking).
- The gaze is upright, rate-limited and clamped to what a neck can do.
- Fingers lie flat on cartons and wrap round posts.

**Measured contact while gripping** (hand-to-socket, every 3rd frame):
- p95 0.0 cm for every unloader, inductor and pusher;
- bag opener p95 0.6 cm;
- maxima ≤ 6 cm on a handful of frames.

### Scan log (flow.py)
- Every record now carries **its device's clock**: WCS for the sorter, tunnel and portals; the handheld fleet at −2 s for SP-BAG / CAGE / IN / REWORK.
- Each record has a `clock_domain`, and handheld records also get `received_time` for the batch upload.
- The `t_s` field leaked true time and is gone; true times are now only in build/truth/events_truth.jsonl.
- New event kinds: `rfid_read` at the door portals on every cage push (with occasional neighbour cross-reads), `bag_close`, `container_add` and `bag_open`.

### B2 fixes
1. **Lighting (#1):** measured with look_stats.py (raycast-classified pixels, final settings) on CAM_07 and CAM_13.
   - Settings: LED rows, white walls, floor albedo 0.35× (mid-grey epoxy), floor roughness ≥ 0.6 (it mirrored the LED rows) and exposure 0.25.
   - Result: **walls 173–174, floor 101–110, 0 % > 230.**
2. **OSD (#2):** each camera shows its own clock offset and drift from render_truth.
3. **Cages (#3):** parked square in their bays (±3°). Gates open at ≤ 90°; they were 92–115° and went through the side mesh.
4. **Floor parcels (#4):** the 17 unregistered Poly Haven cartons are gone. One registered "dropped" parcel remains by C04, which is also the S3 story parcel.
5. **Loop guarding (#5):** 2 m mesh fence with yellow posts on the walkable sides, an access gate, e-stops every ~10 m and 3 loop stack lights. Every chute also has its own stack light.
6. **Floor wear (#7):** scuffs and patch repairs inside the loop.
7. **Shelves:** the 21.4 m steel_frame_shelves_01 was a 10× unit bug in the glTF; fixed in the dress pass.

## 2. Check these
- **Follow-cams (A2), 12 workers:** `assets/hub/build/qa/workers/*.mp4`. Workbench, 10 fps, worker name and frame burned in.
  - The dock follow-cam `worker_dock_D02_s.mp4` shows only the lorry wall. The camera picked its "front" from a facing that was ~90° off. This is fixed in qa_render.py and will be in the next request.
- **Auto checks:** `assets/hub/build/qa/review/req006/auto_flags.csv`, `summary.txt` (322 flag rows; breakdown in §3).
- **Final-look CCTV clips: not in this request.** The pack's CCTV step failed; I edited the script while it ran. They come in the next request, rendered from the fixed build with the final floor.
- **Look numbers (look_stats.py, raycast-classified pixels, CAM_07/13, batch settings):**
  - Settings: no ray tracing, shadow scale 0.5, 2 samples; floor specular 0.12, roughness 0.7; exposure 0.2.
  - Result: walls 174.6 / 171.4, floor 96.0 / 99.3, 0.04 % of floor > 230.
  - Render cost: 8.9 s/frame at 2688×1520, down from 27–140 s/frame.
- **Scenario cards (D1, for your info):** `ml/evaluation/scenarios/<S>/` (once the scenario runs finish).

## 3. Known issues (already planned)
Found in my own frame-by-frame review. All are fixed in code and being re-tested now:
1. **Bagger pops at walk starts (f137, f198).** The heading filter front-loaded a 180° turn: 26° in the first frame. It is now critically damped. A big first turn also eases the travel in, so the worker turns on stepping legs instead of spinning or moonwalking.
2. **Bagger folds over in one frame at the spare bag (f190).**
   - Cause: the reach-lean curve only existed on frames with hand targets, and ignored the hands' blend weight, so it started as a step.
   - Fix: it is now weighted and smoothed over every frame.
   - The spare hook also moved to the front post at chest height (it was at 0.62 m, 0.7 m away, over the frame).
3. **Glance pops (break_2 every ~3–5 s; also sup_1 and check_1).** The head snapped between the clip's own head and the look target. The look-at now fades in and out over 0.5 s.
4. **Dock unloaders' heads inside the carton wall (up to 12 cm), hands in neighbouring cartons.** They dug one column to the floor and bent into the slot. The face now comes down in layers: always the highest carton on their columns.
5. **cage_2 walked through the D11 queue cage (f122–134).** Rerouted south of it and up the gap.
6. **Foot slide at leg starts (cage_1 f20, cage_2 f155, walk_2 f20).** Every leg now eases in over 3 frames.
7. Still open:
   - feet_sinking at the bagger's walk ends (−10 to −19 cm; likely the reach drop bleeding into walk frames, to be re-measured after item 2);
   - the opener's far reach;
   - break_2's phone (15 hand verts through it).

The `loop_pop` (134) and `body_clip_static` (108) counts are dominated by items 1–4.

## 4. Questions
1. **B3 scope.** I propose that the S0 control batch (18 cameras × 30 s, final settings, full res) serves as the B3 QA clips, sent as 3 requests of 6 cameras. A separate 60 s pass would cost ~20 h of rendering, and the Nov 4 budget is 58–89 h of work against ~115 h left (overnight_log top). OK?
2. **Look.** Are the numbers above (walls 171–175, floor 96–99) the target you want, given that the floor is now a little darker than in B1?
