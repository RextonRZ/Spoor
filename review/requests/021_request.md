# 021 · S2 removal actor on mocap, 90 s chain + review 019 fixes (CAM_19 framing, sign)

**Ask:** review worker_s2_1 on real capture (scenarios_v2 S2 #2 and pass 2 #1–2), the re-framed CAM_19 (019 #1) and
the sign (019 #2). The bench is done. The full-hub 90 s run is in progress; its collision result follows as 021b.

## What he does (90 s, every frame from capture)
| t (s) | what | source |
|---|---|---|
| 0–2.1 | walks over from the south-west | 100STYLE Neutral forward walk (CC BY 4.0), path-warped onto the route |
| 2.1–8.4 | walks up to cage RC-864 (S11), stops, takes the COD box (18×10×6 cm) off its **mid shelf at 0.9 m** with both hands (grasp 6.0 s), turns away and walks off carrying it | AndyData Participant 541, A3 trial 2 at 27.07 s (CC BY 4.0), mirrored |
| 8.4–29.4 | carries it close at the waist across the staging edge; **into the store through the doorway at 22.9 s** (under CAM_19 and the sign) | forward walk; the carry arms of the pick's last frame held to the chest |
| 29.4–34.2 | inside the store (no camera sees it): walks up to the steel shelving, **sets the box down at 31.3 s** (1.13 m level), arms hang, turns away | AndyData 541 A3/2 at 60.9 s |
| 34.2–90 | walks back out **empty-handed through the doorway at ~40 s**, then east along the staging aisle until the window ends | forward walk |

- **Box** (all rigid):
  - static on the cage shelf until the grasp;
  - from the grasp to the release, held between both palms on its end faces;
  - static on the store shelf after the release.
- **The engine pieces, reused:**
  - the retarget solve and foot lock;
  - two-bone IK with palms flat on the box;
  - trunk clearance from his own mesh (0.253 m);
  - un-stoop / reach lean, plus the safety net (6.7 mm max);
  - after the release, the arms hang beside the thighs until he walks (018b rule).
- **Joins:**
  - every clip's cut point (pre / post ranges, 1/30 s steps) is searched against every forward-walk frame, both mirrors, at a speed-matched retime. The best leg match wins (knee and ankle offsets plus velocities in the heading frame), so no stride is joined against the wrong foot;
  - inertialized over 0.4 s;
  - where the mesh still dipped under the floor at a join, the body is lifted by the dip, smoothed.

## Gates (bench: the real layout-b hub, whole-hub collision check, 900 frames)
| Gate | Result |
|---|---|
| Collisions ≥ 1 cm, actor / box vs anything | **0** (`qa/review/s2_actor/collisions/`) |
| Palm to box while held | ≤ 6.7 mm (p95 0.0) |
| Foot skate in stance | ≤ 0.3 mm |
| Ground penetration | min −2.5 mm (0 frames < −5 mm) |
| Box in the doorway / back out empty-handed | 22.9 s / ~40 s |
| Headwear | none |

The earlier 30 s run in the **full hub** (all stations, line A on mocap; `hub_lineAb_S2.blend`) gave worker_s2_1 0 rows
against anything.

## How I got here (bench iterations, honest)
1. First pick take (541 at 66.8 s): it walks along the table edge, so the approach ran **through the cage**. I switched
   to 541 at 27.1 s, which walks straight up from the front.
2. The avatar is 0.84× the participant's scale. A 1.0 m shelf would be about 1.18 m for him, so the shelf went to
   **0.9 m**. That is half the cage's 1.8 m height; roll containers with a removable mid shelf are standard.
3. Collisions went 20 → 1 → 2 → 225 → 0, in these steps:
   - belly at the box: hips kept ≥ 0.42 m behind the hands;
   - shoulder at the front post: box 7 cm off-centre, so he stands centred in the opening;
   - fingers through the box corner: the approach goes beside and in front of the end face, then in;
   - box into the belly after the draw-in: trunk clearance;
   - forearm through the box he had just set down: arms hang after the release.
4. **I found this myself in the frame-by-frame review:** after the place, his hands passed in front of the belly for
   0.4 s (f340–343). The arms now hang 2.6 s, until the walk's own arm swing takes over.

## Evidence
- **Follow-cam QA video**, frames 1–460 (workbench, textured, frame number burned in):
  `qa/review/s2_actor/s2_actor_follow.mp4`
- **Contact sheets** (`qa/review/s2_actor/`):
  - every 10th frame: `sheet_follow_every10.jpg`;
  - the four joins, frame by frame: `sheet_joins.jpg`;
  - the place: `sheet_place.jpg`;
  - textured close-ups of the pick and carry: `sheet_close_q.jpg`, `sheet_close_s.jpg`.
- **CAM_19 at native 2688×1520** (workbench), `qa/review/s2_actor/`:
  - f200 / f222: approaching, carrying;
  - f229: going in under the sign;
  - f395 / f402: coming out empty-handed;
  - f420: walking away.
- Motion report: `qa/review/s2_actor/motion_report.json`.

## Review 019 fixes
1. **CAM_19 framing:**
   - the planner's search framed it at tilt 20 (top third wall) or tilt 40 (doorway cut at the top, half the frame
     empty floor), so it is now pinned at yaw 65, tilt 30, at (12.0, 29.0), 3.5 m;
   - the doorway sits in the middle third, with the sign and rack tops in frame;
   - the approach from the cages is in the lower half;
   - still: `qa/review/s2_perimeter/CAM_19_v2.png`;
   - the planner gained a "pose" option for hand-framed cameras (no search);
   - the perimeter raycast will be re-run on this pose with the 021b hub.
2. **Sign:**
   - "STOR PENGECUALIAN" with "EXCEPTION STORE" on a second line;
   - 1.75 × 0.40 m board, bolted under a steel header beam across the two rack ends at 2.9–3.0 m;
   - bottom at 2.52 m, readable in CAM_19.
3. / 4. The strip behind the upright and the throw over the rack are now in the card's `limitations`, together with
   `expected_one_liner` and `must_not` (S2). `make_cards` prints all three.
5. Log times now come from `date`.

## Truth card (S2, written by flow.py)
- `placed_t_s`, `exits_empty_t_s`, `final_location` (Z11 shelving, xyz).
- The expected answer: "went into Z11 carrying it at ~14:32:30, came out empty-handed at ~14:32:47; every way out is
  watched … → it is in Z11; the cage scan is out of date after t=6.0 s; moved by a person, not stolen".

## Not yet (in order)
- 021b: the full-hub 90 s run, collision check and perimeter re-check (running).
- Pass 2 #3: cage RC-864 pushed to its dock with an RFID read. That needs a cage-push motion; the hub's cage pushers
  are still old motion.
- Then line A rows → S2 gates + render (Modal test prep in parallel).
