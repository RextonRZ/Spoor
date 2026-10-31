# Review 009d — REOPENED: headwear floats + "zombie" motion (Rexton, 09:36 — he is right, I was too lenient)

Verdict: **NOT APPROVED. Block A is reopened. Do NOT start the S0 batch until this passes.**
My 009/009c reviews sampled every 25th frame at 960 px and missed this. From now on I review every worker at 2 fps with
head + hands crops. Evidence: `review/_sheets/caps/lean_caps.jpg` (induct_2 frames 0/100/200/280, 1.5× crop).

## P0 — headwear
| # | Where | Problem | Required fix |
|---|---|---|---|
| 1 | Teal-cap inductor (induct_2 f0–f200, f280; Rexton's screenshot) | Cap **hovers 5–10 cm above the skull**, tilted, hair and headband visible in the gap; when she bends, the cap does not follow the head. At f280 the cap is larger than the head | Parent every hat/cap/hard hat to the **head bone with full transform** (Child Of / bone parent, offset from the bind pose with the cap seated on the skull). Scale the cap to the head. Matte cotton, not glossy |
| 2 | QA | `accessory_off_head` only measures distance, so it passed this | New check `accessory_fit`, every frame: inner-rim points to skull ≤ 1.5 cm, cap up-axis vs head up-axis ≤ 8°. High severity, part of `qa_gate.py` |

## P0 — "zombie" motion (why it looks fake, and what to do)
What I see in the follow-cams (induct_1/2/3, dock, cage):
1. **Slumped reach:** the inductor lies chest-down across the belt with a straight arm (f0–f200). Real inductors stand upright,
   belt at hip height, take the parcel from 15–25 cm away, flip it label-up with two hands. → Check belt height (0.80–0.90 m),
   stand the worker 15–25 cm from the edge, cap reach at 45 cm; past that, **take a step** instead of bending.
2. **Robot arms:** arms travel to the target at constant speed while the torso and shoulders stay still. → Every move needs
   ease-in/ease-out (no linear), **anticipation** (0.15–0.25 s small counter-move before a lift), **overlap** (hand leads,
   shoulder/torso follow 80–120 ms later), **follow-through** after a set-down.
3. **No weight:** an 8 kg carton is lifted as fast as a flat mailer. → Speed and knee bend scale with carton mass; lift with the
   legs, a short settle after the lift.
4. **Dead eyes/head:** gaze does not lead the hands. → Look at the target 0.3 s **before** the reach, at the label when flipping,
   at the destination before the place; blinks; small head bob when walking.
5. **Frozen bodies between actions:** no weight shift, no breathing. → Idle layer on everyone: breathing (~0.25 Hz chest/
   shoulders), weight shift every 4–8 s, small hand/finger movement; ±15 % tempo variation per worker so no two move in sync.
6. **No social life:** nobody glances at a neighbour, nobody talks. → One or two short exchanges per station (a glance, a nod,
   a point at a parcel).

## Strongest lever — real mocap under the IK
Pure procedural poses on top of idle clips are the root of the zombie look. The motion report already names the one
rule-compliant real handling source: **AndyData-lab-onePerson (CC BY 4.0, Xsens BVH, labelled reach/carry/pick)**.
Plan: retarget AndyData pick/carry/place segments to Rocketbox (world-space retarget, report §Retargeting), use them as the
base for **inductors and dock unloaders** (the most visible people in hero cameras), keep IK only for the last 10–15 cm of
contact. Credit in CREDITS.md. Cages/walkers can stay procedural with the principles above. Estimate and report the cost;
if it can't fit, say so in a reply with numbers and do the principle fixes (1–6) at minimum.

## Acceptance (I will check at 2 fps, head + hands crops, every worker)
- No visible gap between any hat and head in any frame; `accessory_fit` 0 rows.
- No worker's chest below belt height + 0.25 m while reaching; no straight-arm reaches > 45 cm.
- Every pick/place shows anticipation → lift → settle; gaze leads reach.
- Side-by-side 5 s clip of induct_1 next to `docs/hub/reference_frames` beesort_t266/t282 in the request.

## P0 — hands through boxes (Rexton, 09:37) — zero tolerance
I accepted the §3 residuals in review 009 ("dock fingers against neighbouring cartons ≤ 8 cm", "inductors' hands against
belt frames ≤ 6 cm", 9 parcel overlaps). **That acceptance is withdrawn.**
- New/strict check `hand_penetration`: palm + finger bone capsules vs every carton/belt/cage volume, **any penetration > 1 cm
  for ≥ 1 frame = high**. Grip targets on the **outside** faces of the carton (palms flat on the sides, fingers under the
  bottom edge for lifts), never inside the volume.
- `qa_gate.py`: no `GATE_FORCE` for people or parcels. The batch starts only when the gate passes clean.

## P0 — OWNER RULE (Rexton, 09:38): nothing passes through anything
**No interpenetration anywhere, in any frame, in any camera:**
- item ↔ item (parcel/parcel, parcel/bag, parcel/cage, cage/cage, bag/cage, parcel/belt or chute walls);
- person ↔ any asset (hands, arms, body, legs, head vs cartons, belts, chutes, cages, tables, racks, walls, posts, fences, doors);
- person ↔ person (shoulders, arms, bodies of neighbouring workers, walkers passing each other).
Required:
1. One **global collision check** over every frame of every scenario: all moving objects (people as bone capsules, parcels,
   bags, cages) vs everything (static + moving). Tolerance **1 cm**, any hit = high, gate fails. Report counts by pair type.
2. People: personal-space spacing ≥ 0.6 m between workers at shared stations (inductors in the 0.55 m aisle need a wider
   aisle or fewer people); walkers path-plan around people and assets, not through them.
3. Items: physical stacking (parcels rest **on** each other, not inside), cages park with ≥ 5 cm gaps, bags sit inside cages.
4. Static scene too: run the same check once on the dressed hub at frame 1 (racks, tables, signs, posts, fences).
This rule overrides every residual I accepted earlier.
