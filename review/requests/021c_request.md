# 021c · S2 full hub 90 s: the 021b fixes, the cage-rule answer, CAM_19 in/out

> **UPDATE 06:29 — read this first. "The S2 actor is clean" below is wrong. Don't approve on it; 021d replaces it.**
> The gates from builder notes 0515 / 0545 found three body spins in one frame each, in bench 14 and in this hub
> run. The collision check can't see them.
> - **The spins:** f183 −145°, f470 +148°, f665 −103° (hip heading per frame). At f183 the carton turns with him
>   (0.55 m, 144°).
> - **Causes:**
>   1. *Source turnarounds.* The 100STYLE forward walk has them (at 26.05 s and 81.53 s the smoothed path heading
>      flips 150–170° in one sample; at 54.2 s there is a slow U-turn). The path warp spins the walker there.
>   2. *Noisy direction after the grab.* A grab cut right at the grab gave the walk a noise "direction" from 1/60 s
>      of hip sway, and he swung 130° round and back with the cage.
> - **Fixes (`remover.py`):**
>   - the forward walk is now a virtual timeline of its clean stretches only, each continued at a leg-phase match,
>     with the joins inertialized;
>   - a clip that ends or starts nearly standing hands on the way its body faces, not its sway.
> - **Bench 19:**
>   - collisions **0**, held-object jumps **0**;
>   - fastest body turn 33.6°/frame (a quick pivot walking away after the release); every other turn ≤ 28°;
>   - foot skate ≤ 0.3 mm.
> - **Also, the hub:** 51 parcels were piled 2–3.2 m high over the chute bags (C01, C12, …). Only C07 has a bag
>   change, so every other heap grew for the whole run. Fixed in `flow.py`: a parcel reaching a full bag's lip
>   settles into the sack.
> - **Next:** a new full-hub run with all of this is going (started 06:28), plus the 15 min S2 scan log and the
>   case_input check. 021d will carry the fresh numbers and both gates.

**Ask:**
- check the three 021b P1 fixes on the bench proof (hands, reach, place);
- check the cage-rule answer to builder note 0415 (before/after counts);
- check the full-hub 90 s run: the S2 actor is clean; the CAM_19 in/out still reads.

The rest of the hub's rows are the known old-motion backlog, listed with what each S2 camera sees.

## 021b fixes (bench 14: the real layout-b hub, 900 frames, `qa/review/s2_actor14/`)

1. **Hand shape (P1 #1).**
   - Change: a new finger pass in `remover.py`, run on the final arms and the final carton pose. For each finger, the first joint below the carton's bottom edge bends towards the palm, so the rest of the finger runs in under the carton. The thumb lies flat on the end face.
   - Numbers: all 8 fingertips are 11–18 mm under the bottom, in 260 carried frames.
   - Crops: `close/sheet_hands.jpg` (f90 / 120 / 160 / 182 / 200 / 300 / 330, from the front).
2. **Reach into the cage (P1 #2).**

   | Measure (f50–75) | Result |
   |---|---|
   | Head mesh ↔ cage meshes, min | **16.0 cm** |
   | Box-reach lean | **4.0°** (cap now 20°) |
   | Total trunk tilt (pelvis → neck) | 16.8° max |
   | Shoulders ↔ cage, min | **0.1 cm** (f59–67; see below) |

   - Changes: the carton now sits 3 cm right of the opening's centre and 1 cm from the shelf's front edge (before: 7 cm left, 3 cm in).
   - The shoulder number is honest, not hidden. His right shoulder brushes the front-right post at f59–67: 0.1–1.7 cm, no penetration. Moving the carton right freed his head on the left side and brought the shoulder closer on the right; centred, the head was at 3.6 cm.
   - Crops: `close/sheet_reach.jpg` (side, f56–70). Per-frame numbers: `close/close_proof.json`.
   - **Found on the way: a one-frame 0.46 m carton jump at the lift (f66 → 67).** It has been there since bench 3, including the bench you reviewed in 021b.
     - Cause: the held carton turned with the palm-to-palm axis. At the take's lift the hands end up one in front of the other, 4 cm apart sideways, and that axis flipped 137° in one frame. The carton spun round the hands' midpoint, and the hand targets swapped sides round it.
     - Fix: it now turns with his chest (the clavicle line, rigid on the chest). Through the lift it now moves 5–7 cm and turns ~10° per frame.
     - A smoothed shoulder line lagged a corner (carton 4 cm into a forearm at f182), so the clavicles it is.
3. **Place on the store shelf (P1 #3).**
   - Per frame, the gap between the carton's bottom and the board under it:
     - 0.0 mm from f330 to the release (f341), through f376 and at f420;
     - 14 mm at f325, as it comes in over the board's front edge.
   - Crops: `close/sheet_place.jpg`, taken beside him (from behind, his body hid it), f324–368 + f420.
   - Three things were wrong before:
     - **The board top is 1.145 m, not 1.13.** I measured it with rays. The carton had sat 15 mm inside the 1.5 cm board, and the collision check read 0 (see the checker below).
     - **From 1.6 s before the release, the carton followed the place take's own hands,** captured at a lower table: up to 29 cm under the board. It now stays in the snug carry until a 1.2 s rise-first place: up to the board's height in the first 60 %, in over it after.
     - **The fingers opened palms-up beside the carton 1.6 s before letting go** (the "tray" again). The carry hand shape now lets go only in the last 0.4 s.
   - The support guard in `remover.py` (never into a shelf it is set down on) only looks ahead now: it rises before the edge and never stays up after. It had summed neighbouring frames instead of taking a max.
4. **Follow-cam (P2 #4).** Every proof camera checks its line of sight first and turns round him until only he, the carton or the cage is in the way. 0 of 35 shots blocked.

Bench gates: collisions ≥ 1 cm **0 / 900** (new cage rule); foot skate ≤ 0.4 mm; ground min −2.4 mm.

## Cage rule (builder note 0415)

Checking the rule against your four points showed the old rule hid real hits, so the checker changed.

| # | Your point | Now |
|---|---|---|
| 1 | Bars, posts, shelves and base still count | Yes. Person ↔ cage is now the interior-volume test **plus** a surface-depth test on the posts, rails and deck, open front or not. Before, a moving cage got the volume test only. The 4–5 mm wires can't show ≥ 1 cm surface depth, so through the side and back walls it's the volume test that counts. |
| 2 | Parcels / sacks inside count | Yes. A cage's own child meshes (mid shelf, sacks, castors) are now checked as "cagepart" against people, parcels and the static hub. Before, they were in neither the moving list nor the static list, so nothing was checked against them. Flow parcels in a cage were already checked against people. |
| 3 | Only the empty air, only through the open front | Yes. Hands are no longer skipped: the old rule skipped every hand and finger vertex. Only a vertex whose line to his pelvis passes through the open front, above the deck, is exempt. |
| 4 | Before / after on the S2 bench | Bench 14: old rule **28 frames** (26 head, 2 right forearm, all through the open front into the air volume); new rule **0**. |

- On the way, on bench 10, the new rule found **56 frames of real hits** during the push that the old rule missed (hands skipped): palms and curled fingers 1.0–1.4 cm into the front posts. Fixed by moving the grip back to 6 cm behind each post's axis.
- Also new: a sampled-surface test for parcels against the static hub. It catches a thin board through a carton, which has no vertex inside the other mesh: that is the 15 mm above.
- `--cage-rule old` reproduces the old rule, for this comparison only.

Files: `qa/review/s2_actor14/collisions/` (new rule) and `collisions_oldrule/`.

## Full hub, 90 s (`assets/hub/build/hub_lineAb_S2.blend`, 04:54–05:40)

- **The S2 actor is bench 14's.** The hub report gives the same grasp / place / grab / release frames, lean 4.0° / 32°, palms on the posts p95 14.3 mm (max 20.3), and the same hook numbers.
- **CAM_19, final look** (EEVEE batch settings → cctv_look, native-pixel crops):
  - going in, f232 / 240 / 245 / 249 / 253 / 258 (`qa/review/s2_hub/cctv_proof/crops_in.png`): the kraft carton is plain in front of him in the first four; at f253 / 258 he has turned into the gap and his body hides it;
  - coming out, f414 / 418 / 422 / 426 / 430 / 436 (`crops_out.png`): empty hands, arms hanging and swinging.
- **Cage push:** grab 63.9 s, at D07 82.3 s, the cage's RFID read at SP-RFID-D07 at 81.9 s.
  - Palms to the posts: p95 14.3 mm, max 20.3 mm. That's the hands' fit to the posts; the cage goes where both hands are.
  - Lean while pushing the loaded cage: up to 32°, the cap for a push.
- **Truth bug, fixed in code:** `exits_empty_t_s` came out **null**, so the expected answer said "came out empty-handed at t = 0 s".
  - Cause: "inside" was pelvis y > 33.3 only, and the cage push later takes him to y ≈ 38.
  - Fix: "inside" is now also limited to the store's x range.
  - From the blend: in the store f257–421, out through the gap **f426 (42.5 s)**. The truth file is regenerated on the next hub run (this one is otherwise unchanged).
- **Collisions, whole hub, f1–900:** **2009 frame-rows** (`qa/review/s2_hub/collisions90/`). **S2 actor and S2 cage: 0.** No line A worker
  is in any row. The rest is the old-motion backlog, now counted by the stricter checker:
- **By what the S2 cameras see** (CAM_01 / 06 / 09 / 11 / 13 / 15 / 19, `qa/review/s2_hub/rows_in_view_90s.json`): **1503 of 2009 rows** are seen by at least one of them.

  | Category | Rows | Seen by an S2 camera | Note |
  |---|---|---|---|
  | Cage pushers (old motion) | 377 | 377 | middle finger round the handle, up to 11.4 cm (the old rule skipped hands) |
  | Parcel ↔ chutes | 350 | 350 | two parcels (5011: 234 frames, 7030: 98) sitting in chute walls up to 10 cm |
  | Docks (old motion) | 320 | 151 | D02 / D05 unloaders: parcels, conveyors |
  | Line B inductors | 256 | 21 | |
  | Parcel ↔ parcel | 216 | 195 | mostly the merge / loop |
  | Parcel ↔ static other | 214 | 156 | 97 of them in line A's area (parcels against the belt / induct conveyors) |
  | Bag opener | 98 | 98 | |
  | Bagger | 88 | 88 | |
  | Sorter carriers | 78 | 55 | |
  | Tech | 12 | 12 | |

  By camera: CAM_13 728, CAM_11 653, CAM_01 417, CAM_09 415, CAM_06 379, CAM_15 377, CAM_19 43.
  Every one of these must be 0 before the S2 render (owner rule). The order I propose is below.

## Proposed order to the S2 render gate (your call)
1. **Line A rows → 0.** The engine fixes are ready on the bench; re-run in the hub.
2. **Parcels in the chutes** (two parcels, 332 rows): probably a sim stacking or stopping issue.
3. **Cage pushers:** a hand grip round the handle, the same fix as S2's posts.
4. **Bag opener, bagger, docks, line B** (old motion, M5 backlog): these are the large ones. Which are in the S2 window's views decides the scope; ask: may stations no S2 camera sees keep old motion for the S2 render?

## Not in this request
- **Mailer pinch** (31 Oct list #1): built on the line A bench behind a station flag, **off in the hub**. I'll send it as its own request with close-ups.
- **Line A rows → 0** (#2): the engine fixes found on the mailer bench go in that request:
  - a one-hand bag turned with the hanging hand's axis and spun in the hand; it now turns with the chest;
  - the belt-dip guard summed neighbouring frames (over-lift); now a weighted max;
  - the surface clamp for hand targets is wider (end stop added, margins for a whole hand).

  This hub run used the engine as it was before those edits, so its line A rows are the "before".
