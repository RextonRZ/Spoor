# Request 014d: M2 (014_GO): retarget.py, one AndyData pick/place take on one inductor avatar

From the builder. M2 was due 17:30; this is sent at 16:38. Everything is under **`Spoor/qa/review/m2/`**. It includes the four items you added in 014c.

## Proof
- **`m2_retarget_front_side.mp4`**: 10 s at 30 fps, AndyData Participant_5124 Setup_B Seq_1 Trial_3, from 30.5 to 40.5 s (reach, pick, carry, place). The retargeted Male_Adult_04 (EEVEE) sits next to the source BVH stick figure:
  - both use the same orthographic projection;
  - the stick figure is scaled by the leg ratio and placed like the root;
  - each frame shows the label, time and frame number.
  - "front" and "side" are fixed world cameras (−Y and +X). The actor turns during the take, so the view swaps sides.
- **`m2_sheet_1fps.jpg`**: 1 fps sheet of the same.
- **`m2_qa.json`**: the full QA, including every contact.
- **`m2_source_reference_pose.png`**: your item #1 (§2).

## 1. How it works (`assets/hub/mocap/retarget.py`, numpy)
- **BVH reader:** reads the 22-joint Xsens hierarchy with YXZ channels; FK is vectorised over frames.
- **240 Hz → scene rate (your #2):** low-pass and resample in one step; no source frame is dropped.
  - Each output time takes a Gaussian (σ = 0.5/fps) over **all** source frames within 3σ.
  - Positions are averaged. Rotations take the weighted chordal mean, projected back onto SO(3) (SVD). That is the rotation low-pass, evaluated at fractional times.
- **Shared T-pose:** every mapped bone is swung so its head→child direction equals the BVH rest direction. Fingers keep M1's relaxed pose.
  - Per frame, each source joint's world rotation relative to rest is applied to the bone's T-pose world rotation.
  - Local rotations follow from the rest matrices. So the Biped's hierarchy quirks don't matter: here the thighs hang off `Bip01 Spine` and the clavicles off `Neck`.
- **Root, on `Bip01 Pelvis`:**
  - Its location is solved per frame so the **thigh-head midpoint** sits on the source hip midpoint × leg ratio. Root translation alone wasn't enough: the thighs hang 12 cm below the spine head, so spine flexion would swing the hips.
  - Pelvis tilt comes from the source Hips rotation, on the same bone.
  - One vertical constant, measured on the deformed mesh, puts the lowest sole point on the floor.
- **Leg ratio (your #3):**
  - avatar hip-to-ankle **0.794 m**;
  - participant 5124 (188 cm), measured hip − ankle height from `participant_specifications.csv`: **0.95 m**. The BVH offsets would give 0.975 m;
  - ratio **0.835**.
- **Output:** quaternions with the hemisphere fix, written in bulk (`foreach_set`) into one slotted action (`fcurve_ensure_for_datablock`).
- **Foot locks (built now, needed at M3 anyway):**
  - stance is taken from the source (ankle within 3 cm of its low and < 0.15 m/s, at least 3 frames);
  - the ankle is pinned to its median stance position, ramped over 0.1 s;
  - analytic thigh/calf solve in the mocap knee plane; the foot keeps its mocap world rotation.

## 2. Source reference pose (your #1): `m2_source_reference_pose.png`
| | Measured |
|---|---|
| BVH **all-zero channels** | arms **0.00°** off lateral-horizontal, legs 0.01° off vertical, spine 0.02°, feet forward. A clean T |
| BVH **frame 0** | Xsens' measured T. Arms 1.1° off lateral. Its only non-zero channels are sagittal spine/hip/knee/ankle curves (max 12.7°) and ±2.3° at the elbows/wrists. Row 1 is already 77° (arms down) |
| Our Rocketbox T-pose (M1) | swing-only, 0.00° off |
| Retargeted avatar at raw frame 0 | a T with **palms down**, the same as our T-pose |

- **So we align to the zero pose.** It is the clean T that frame 0 approximates.
- **Palms are the one thing a stick figure can't show**, so I measured them on the hold frames (Pi + Ca labels, 123 frames). The avatar's palms **face each other**: median cos **0.90 (L) / 0.54 (R)** toward the other hand, both inward on 69 % of frames. A palm-down mismatch would make that negative or zero.
- **100STYLE (for M4):** row 0 is *not* a T; its arms hang at −70°. The T frames are around row 199, before FW_START 351, as you said. That's where I'll take its reference.

## 3. QA table (your #4): measured on Blender's **evaluated** pose (bone heads + deformed mesh), not on my numpy model. Model vs Blender: **0.0 mm**
| Check | Result | Gate |
|---|---|---|
| Foot skate, per contact (13 contacts) | 0.0, 0.0, 0.3, 0.0, 0.0, 0.0, 0.0, 0.0, 0.4, 0.7, 0.7, 0.0, 0.0 mm; **max 0.7 mm** | < 20 mm ✔ |
| Without foot locks (for reference) | 31 / 45 mm | ✘, which is why the locks are on |
| Ground-penetration frames (mesh below z 0 by > 0.5 mm) | **0** of 300; median sole float 9.4 mm (heel/toe roll) | 0 ✔ |
| Limb direction vs source, mean / max per limb | spine, neck, clavicles, arms, feet: **≤ 0.04° / ≤ 0.21°**; thighs 0.39–0.52° / 5.3–7.0°; calves 0.77–0.92° / 4.9–5.2° | legs: the foot lock bends the knee to hold the plant |
| Forearm twist vs T-pose, max | L 35.8°, R 43.4° | candy-wrap flag > 90°: **no** |
| Wrist twist vs forearm, max | L 29.8°, R 29.3° | no |

## 4. Next: M3 (19:00), request 015
- Already written, being tested now:
  - `clips.py` cuts the takes on labels into **stationary pick and place clips**, boundaries snapped to wrist-speed minima ±0.15 s, sidecar `assets/mocap/clips.json`. It found that AndyData carries walk about 2 m between tables, so only the pick (which includes a 60–70° turn) and the set-down are used.
  - `inductor.py` does the rest:
    - constant retime ratio 0.92–1.12, holds instead of slow motion;
    - each clip anchored at its event, with the pick's end heading chained to the place's start heading so no join spins;
    - inertialized 0.3 s joins;
    - foot locks;
    - ramped two-bone hand IK (pole = the mocap elbow) onto the parcel's side faces;
    - parcel world-matrix bake: table → hands → belt.
  - Left-turning takes are mirrored, so every line-A inductor turns right.
- **014b fixes:**
  - visible diverter;
  - gravity roll 0.2–0.4 m/s, zero-pressure ≥ 2 cm, ≤ 3 parcels per table, end stop at 88 cm;
  - the I3 chair moved;
  - the spacing row;
  - no walker in the feed/induct aisle.
- **One design choice to check:** after the release, the placement belt waits until the hands are off (0.3 s, as with a light curtain), then accelerates to 1.5 m/s. That way the leading hand isn't dragged. If line A should instead run continuously, I'll change it.
