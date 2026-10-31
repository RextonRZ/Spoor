# 021b · S2 actor: review 021 P0 fixed (readable carton, natural carry)

**Ask:** check that the carton is obvious going in and absent coming out on CAM_19, and that the carry now reads as a
carry.

## Changes
1. **The parcel** is now a COD carton, **25 × 18 × 10 cm**, kraft with a white label, as you suggested. It goes
   everywhere the old one did: the cage shelf, the hands, the store shelf, the truth card. In the hub it is flow's
   labelled kraft parcel.
2. **The carry** (`remover.py`, `S2_CARRY`):
   - from 0.6 s after the lift, the carton sits snug against his belly / lower chest. Its back face is 8 mm in front
     of his own torso, measured in the 12 cm band the carton sits in;
   - it rides at pelvis + 0.14 m (~1.05 m), so it bobs with his gait;
   - his hands are low on its sides (palms 3 cm below its centre), fingers turned 55° down and curled under it;
   - the elbows bend to it and are swung wider (pole out 0.45);
   - a quarter of the walk's own arm motion is layered on the held arm pose, so the shoulders and elbows move with
     the gait; nothing is frozen for 21 s;
   - 1.6 s before the store shelf it returns to the side-face grip for the place.
3. **Fixed while at it:**
   - after the release, the hanging-rest target sat 0.66 m below the shoulder, beyond this avatar's arm. That
     triggered a 24° forward lean after the set-down; the rest target now comes from his own arm length;
   - the reach lean is now limited to when he holds or approaches the carton.

## Gates (bench, real layout-b hub, 900 frames)
| Gate | Result |
|---|---|
| Collisions ≥ 1 cm | **0** (`qa/review/s2_actor3/collisions/`) |
| Palms on the carton while held | ≤ 9.7 mm (p95 0.0) |
| Foot skate in stance | ≤ 0.3 mm |
| Ground | min −2.5 mm |
| In through the doorway / out empty-handed | f228 (22.8 s) / ~f400 (40 s) |

## Proof
- **CAM_19, final look** (EEVEE at batch settings, then cctv_look: lens k1, sensor, ISP, H.265, OSD), native-pixel
  crops of the doorway and the approach:
  - going in: f200 / 212 / 222 / 226 / 229 / 232, `qa/review/s2_actor3/cctv_proof/crops_in.png`. The carton is
    obvious in every frame;
  - coming out: f392 / 397 / 401 / 405 / 410 / 420, `qa/review/s2_actor3/cctv_proof/crops_out.png`. Empty hands,
    arms hanging;
  - full frames: `qa/review/s2_actor3/cctv_proof/cctv/`.
- **Close-ups of the carry** (f76 / 90 / 120 / 160 / 200, front and side): `qa/review/s2_actor3/sheet_close.jpg`.
- **Follow-cam**, frames 1–460: `qa/review/s2_actor3/s2_actor_follow.mp4`.

## Also done since 021 (log)
- Perimeter re-check on the pinned CAM_19: gap south face 100 %, inside Z11 4.8 % (doorway view only), and CAM_19
  sees 49 % of the air over the racks. `S2_EXITS` and the limitations are updated.
- S5 P0: the subject's tunnel read, carrier and C12 divert all fall inside the 60 s window on layout b. Pass-2 swap
  added: the twins change order through line A.
- One-liners and `must_not` lists for S0, S1, S3, S4, S5, written into the scenario truth.
  `make_cards` prints them. **Scoring them in spoor_eval is the evaluation harness's job: frontend agent?**
- CAM_04 re-aimed at line A (b) and CAM_07 moved off the XO-1 bridge's axis (cctv_setup #2/#3):
  `qa/review/cctv_reaim/before_after.jpg`.
- Line A fixes for the next hub run:
  - the table belt's profile: the feed stays flat to its edge, then a 5 cm step onto the table head;
  - a carried carton never dips below belt A or the induct belt tops.
- **Docks on mocap (in progress):** `stations.MocapDocks` plus a `belt_side` option in the engine.
  - First hub run: the 4 unloaders' bodies 0 rows; the cartons 165 rows (pulled through the wall);
  - fix: `slot_pull` (straight out of the slot first); re-run going.

## Next
- 021c: the full-hub 90 s S2 run with this actor, plus whole-hub collisions and the in-view breakdown.
- Pass-2 #3: the cage push.
