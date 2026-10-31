# 021d · S2 hub run 4, the P0 layout fix, the S2 long log, the Modal render test

**Ask:**
- check the P0 answers (builder notes 1040 + 1140): one canonical spec, the false "records disagree", the false
  stalled parcels, and the two new checks;
- check run 4 against run 3 (the per-camera table below) and the run-5 fixes in flight;
- answer one question (at the end): may a station that can't reach 0 visible rows be unstaffed for the S2 render?

Run 5 (all the fixes below) started 12:20. Its numbers come in 021e with the top-5 turn crops (0650 #1). Those crops
are only worth looking at after the turn cap, which is in run 5.

## P0 · builder note 1040: one canonical spec = `assets/hub/hub_spec.json` (layout b)

- **Canonical file:** `assets/hub/hub_spec.json` is now line A layout b, the layout S2 is simulated and rendered on.
  - It is generated: `build_hub_plan.py` with `LINE_A_LAYOUT = "b"`. It has the collector turning east at the feed
    line, D02's stub belt, and `"line_a": {"layout": "b"}`.
  - Against the old hub_spec.json, only the conveyor list and the layout flag changed.
- **The old copy:** `hub_spec_lineAb.json` is now an exact copy (`make_lineab_spec.py` checks for layout b, then
  copies), so old commands keep working. It had gone stale at 01:12: it missed the 02:09 CAM_04 / CAM_07 re-aims and
  the cameras' `visible_by` lists.
  - Also fixed: both files had broken en dashes ("â€“" / "�") from a non-UTF-8 write.
  - The hub was rebuilt from the canonical file at 12:18.
- **Frontend:** seed and run gen:hub from `assets/hub/hub_spec.json`.
- **The "records disagree" cause** was not the scan point position. SP-INDUCT's event position was already the merge
  end (30, 11) in site_plan.py, and the loop is the same in both layouts.
  - It was the S2 story's history lines, typed by hand in `stations.BlindRemoval.history_events`: induct → C12 in
    21.7 s. The loop takes 25.9 s: 51.8 m at 2.0 m/s, and the sorter tips the carrier as it reaches the chute.
  - S3 had the same bug: → C04 in 16.7 s against 19.2 s.
  - **Fix:** flow passes `loop_ride_s(chute)` (from the loop geometry) to the histories. The divert now follows the
    load by exactly the loop ride.
- **New check:** `assets/hub/check_scan_routes.py [S…]`.
  - It reads only the canonical spec.
  - Rules: tunnel → carrier load must be ≥ the belt travel; carrier load → divert must equal the loop ride + whole
    laps, ± 0.25 s; `designed_route_conflicts` in a scenario's truth exempts a designed one.
  - Before the fix it flags exactly the S2 and S3 history lines. All 2,261 simulated pairs in S1–S5 pass, which also
    cross-checks the checker against flow.
  - The pipeline runs it now. S2 must pass in run 5; S3 needs its own re-run, which is queued.

## P0 · builder note 1140: the 16 false "stalled" parcels

- **Cause:** the spec says the bagger scans each parcel into the bag (SP-BAG-Cxx, `container_add`, parcel into bag),
  but the long log's bagging model only wrote bag close / cage add / open. No parcel ever got its bag scan.
  - The inbox's rule then fired on C07 / C10's early parcels as soon as a later bag close at the same point showed the
    chute kept working.
- **Fix (`splice_scan_log.py`):**
  - each diverted parcel outside the window gets its bagging scan into the bag open at its chute, 20 s – 4 min after
    the divert and before that bag closes;
  - the log ends with the 90 s window. After it, only the sim-only run's own (different) parcels carried on, so the
    full run's parcels still on the line looked lost: 5 tunnel reads in the window's last 5 s.
- **New check, in the splice:** the inbox's stalled rule (allowance per last scan + the next point kept scanning
  others), re-implemented on the spliced log. Any parcel not in the scenario truth's `designed_stalled` fails it (exit 3).
- **Result on run 4's data:**
  - **0 stalled** (designed 0);
  - S2's subject's last scan is its cage scan (2 h allowance), so it shows as the customer case, not as stalled.
- **The long log now** runs 14:09:14 → 14:33:36: 4,993 rows.
  - 815 per-parcel bag scans, 17 bag closes, 18 opens, 5 cage loads at the doors.
  - After S2's C12 divert (14:11) the next points keep scanning for 22 min, against the ≥ 12 min of builder note 0755.

## Run 4 vs run 3 (S2 hub, 90 s, 900 frames)

Collision rows ≥ 1 cm, frame-hits:

| | run 3 | run 4 |
|---|---|---|
| all rows | 2,025 | 1,272 |
| visible in an S2 render camera | 1,507 | **774** |

Per S2 render camera (a row seen by two cameras counts in both):

| camera | run 3 | run 4 |
|---|---|---|
| CAM_01 | 431 | 439 |
| CAM_06 | 246 | 61 |
| CAM_09 | 437 | 44 |
| CAM_11 | 638 | 167 |
| CAM_13 | 729 | 270 |
| CAM_15 | 377 | 114 |
| CAM_19 | 43 | 35 |

Visible rows by station, in the 021c order:

| # | station | run 3 | run 4 | what changed / what is in run 5 |
|---|---|---|---|---|
| 1 | chutes (parcels) | 487 | 24 | Heap parcels placed clear of static parcels; full-bag parcels hidden as they leave the chute end. The 24 left are landings at four chutes (CAM_09/11/13). |
| 2 | cage pushers | 375 | 111 | Pusher 2 (D11): 261 → 1, fingers now point out of the handle. Pusher 1 (D08): 110 rows, up to 10.9 cm, its own cage path. **Next.** |
| 3 | line A (conveyors, CAM_01) | 156 | 156 | Run 5 fixes all of them (breakdown below). |
| 4 | bag opener (CAM_01) | 98 | 122 | Next after line A. |
| 4 | bagger C07 | 88 | 87 | Next after line A. |
| 5 | parcel ↔ parcel / static parcels | 55 | 24 | Heap placement. |
| 6 | dock D02 unloaders (CAM_01) | 151 | 152 | See the question below. |
| 6 | line B inductor, tech, carriers | ~63 | ~60 | Carriers: 1.7 cm landings on the carrier band. |

**The S2 actor: 0 rows in run 4, as on the approved bench 20.**

**Line A, the 156 rows by cause (all fixed for run 5):**
- **78 · induct-belt start edge.**
  - The engine kept the carton inside a rectangle along / across the 45° belt, but the built belt's near end is cut
    along x. Near the start, the rectangle's far corner stuck out past that edge onto the end frame (y 10.64,
    z 1.04).
  - Now the footprint stays 3 cm inside the cut edge (`inductor._induct_zone`, unit-tested over yaw × size).
- **37 · D02's stub belt.**
  - Line A layout b moved D02's boom off the collector onto the new stub, but the boom opening was only cut in the
    collector's frame. Every D02 parcel went 4 cm through the stub's closed side frame.
  - The opening is now cut in the stub too (`build_hub`).
- **17 · induct side-guide ends at belt A.** Cartons turning onto A at the merge caught the guides' ends. The guides
  now stop 12 cm short of A.
- **13 · table end stop.** Lifted off the rollers, the carton was carried 1–3 cm through the 4 cm stop lip.
  - New guard: while held, a carton's rotated footprint (separating-axis test) never dips into a station surface. It
    is raised to the surface top, ramped over 3 frames, and the hands follow.
  - It doesn't change set-downs, since cartons already sit at the belt top there.
- **8 · boom nose.** `flow.py` started both boom paths at z 0.97; since an earlier fix the built belt is flat at
  1.0. They now start at 1.0.
- **2 · stub → feed corner.** The feed frame's gap is widened from ±0.38 m to ±0.5 m.
- **1 · a mailer 3.8 cm into the induct belt.** I'm watching for it in run 5.

## Gates (run 4) and what run 5 changes

- **Turns (0650 #1):**
  - 106 frames over 25°/frame, all mocap inductors and dock workers: AndyData pick → place takes, retimed, swing
    the hips ~90° from table to belt in 2 frames (46–49°/frame).
  - Run 5 holds the whole-body heading to 220°/s (22°/frame), with forward and backward passes averaged so the turn
    spreads round the corner. It turns each frame's pose about its hip centre; the hands' IK still meets the carton
    path.
  - Top-5 crops come with run 5. The S2 actor: ≤ 24.1°/frame (bench 20).
- **Piles (0650 #2, permanent gate):**
  - 3,225 flags. Most "stacked" ones are designed: the parcel walls in the lorries at D02 / D05, and the gaylord at
    line B.
  - The "floating" clusters (line B belt, the opener bench, dock floors) need a probe fix: the probe misses some belt
    surfaces.
  - In 021e the gate will list only flags in an S2 camera's view (the same in-view pass as the collision rows).
- **Held jumps:** 92, all old-motion stations (line B parcels 70xx, dock parcels 50xx); 0 for S2.

## S2 story check (run 4)

- **CAM_19 in / out:** enters the blind spot 23.7 s, comes out empty-handed 41.7 s.
- **Look-alike (agent_showcase_0925):** CTX181432283202 (`flow_parcel_5014`), the same size kraft carton with a white
  label.
  - Its route: tunnel 4.7 s, carrier 10.1 s, divert C08 33.0 s. That is exactly the loop ride (22.9 s), so it passes
    the new route check.
  - It is in the truth as `lookalike` with why it can't be the subject.
- **Card check:** `make_cards --check` OK (S2: 4 scan lines on the card, 4 in the log).

## Modal render test (owner 0016, cap $2): done

- **Result:** CAM_01 frames 300–329 at 2688×1520 with the batch settings, on one L4: 3.1–3.5 s/frame (this laptop:
  16.3). EEVEE ran on the container GPU through EGL; no X server was needed.
- **Pixels vs the same 30 frames rendered here:** mean diff 0.36/255, worst p99 2/255. Only label and barcode texture
  sampling differs, so it is the same look.
  - Sheet: `qa/review/modal_test/egl/compare_CAM_01.jpg`; numbers: `compare_CAM_01.json`.
- **Cost:** ≈ $0.05. The app is stopped, and the 268 MB packed blend stays on the free Volume.
- **The full S2 render** (7 cameras × 900 frames) would be ≈ $6.8 on Modal, over the $5 line. Options A/B/C are with
  Rexton in FOR_REXTON.md; it waits for a clean gate anyway.

## Also since 021c

- **Review hook (owner_hook_0105):** live in this session, tested by hand (the frontend agent had installed it).
- **Glimmer J6 and the logo swap:** done (log 09:03 / 09:14).
- **Credits:** `CREDITS.md` had lost the AndyData and 100STYLE (CC BY 4.0) rows and the Rocketbox detail at the
  02:09 plan regeneration. They now live in the generator's asset table, so a regeneration keeps them; the motion
  data is credited in the CC BY line.
- **Disk:** the floor of 15 GB free was broken twice today by growth outside my folders. I removed only my own
  regenerable intermediates (bench blends, frame dumps already encoded into MP4).

## Question for the reviewer

The S2 gate is 0 visible rows. Dock D02's two unloaders (152 rows, CAM_01) and the bag opener (122, CAM_01) are old
motion that needs real rework: lorry-wall picks onto the boom, and bag tipping. I'll do them in the 021c order after
line A and the cage pusher.

If one of them still can't be made convincing and clean after one honest attempt, **may it be unstaffed for the S2
render?** For example, D02's door closed with the boom retracted, or the opener bench idle with full bags waiting. A
real hub has idle stations, and the owner rule says to remove what can't be made convincing. I'd tag it in the truth
as `unstaffed_for_render`, so it is fixed before any scenario that films it.

### Evidence for the question (close-ups from run 4, `qa/review/s2_hub4/<station>/sheet.jpg`)

- **Bag opener** (`opener/sheet.jpg`, f172 / 313 / 463 / 605; side + top):
  - she squats deep with straight arms, and her hands hover flat over the heap instead of gripping;
  - her arms pass through the mailers, and one heap carton (5001) is hit by her left arm in every cycle;
  - at f605 she carries a carton over her head to the collector;
  - the avatar wears heeled boots, against the flat-shoes rule for floor workers.

  Not convincing. **My recommendation: unstaff it for S2** (the bench idle with full bags waiting) and rebuild it on
  the mocap engine after S2 (M5 plan: 2–3 h).
- **Dock D02** (`dock/sheet.jpg`, f120 / 300 / 600 / 720; the top views are the lorry roof, ignore them):
  - two unloaders at the wall; the motion is mime-like, with cartons handed across over the boom;
  - one squats into the boom (person ↔ conveyors rows).

  **Run 6 tries `MocapDocks`** (the motion approved in 016b, not yet gate-clean). If D02 isn't clean then, close the
  door for S2.
- **Bagger C07** (`bagger/sheet.jpg`, f45 / 75 / 110 / 140): the sack drag reads right. Its rows are the sack's path
  through his calves and his forearm resting through the frame rim. **I'll fix it** (targeted, no unstaffing).
