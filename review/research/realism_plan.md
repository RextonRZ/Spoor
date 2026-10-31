# Realism plan — motion + parcel transit (reviewer research, 30 Oct 12:40–13:00)

Every item has a source. Licence rule unchanged: CC0 / CC BY / MIT / OFL or our own recordings. Apply inside A4 (009d),
in this order. Credit CC BY sources in CREDITS.md.

## A. Make IK motion human (no new data needed — do first)
1. **Minimum-jerk easing on every IK target move:** s = 10τ³ − 15τ⁴ + 6τ⁵ (Flash & Hogan 1985, bell-shaped speed of real
   reaches). Replaces every constant-speed lerp.
2. **Critically damped spring followers** for pelvis lag, spine → neck → head overlap, carried box trailing the hands, and
   foot-lock release (Holden, "Spring-It-On", MIT: https://theorangeduck.com/page/spring-roll-call). Use inertialisation /
   dead blending for clip ↔ IK transitions (https://theorangeduck.com/page/dead-blending).
3. **Gaze leads the hands** (Andrist et al. 2012, https://pages.cs.wisc.edu/~bilge/pubs/2012/ICMI12-W-Andrist.pdf): eyes
   then head; shifts > 30° are mostly head-first; head ~50°/s for a 24° shift; eyes ±45–55°. Look at the target before the reach.
4. **Reach cap at ~90 % of arm chain length** → beyond that move the pelvis or **take a step**. This alone removes the
   straight "zombie arms".
5. **Lift style:** light parcels = stoop lift (trunk bend + some knee flex; "many workers … prefer the stoop lift",
   https://pmc.ncbi.nlm.nih.gov/articles/PMC2213554); heavy sacks/cartons = squat with knees.
6. **Breathing + weight shift on everyone:** chest/clavicle sine at ~18–25 breaths/min while working (rest 12–18, Cleveland
   Clinic); slow noise-driven weight shift every few seconds; ±15 % tempo per worker.
7. Hats parented to the Bip01 Head bone; hand sockets on the **outside** box faces, palms in, offset by finger thickness.

## B. Real motion data (licence-clean) — use to replace walks/idles and seed handling
| Source | Licence | Use it for |
|---|---|---|
| **100STYLE** (Zenodo 8127870) BVH 60 fps | CC BY 4.0 ("The 100STYLE Dataset - Ian Mason") | Walks, turns, sidesteps, idles in many styles (Old, Heavyset, BentForward, HandsInPockets) → kills robotic walks and frozen idles. **Highest value per hour.** |
| **AndyData** (Zenodo 3254403) `xsens_bvh.zip` 1.8 GB | CC BY 4.0 | Reach / pick / carry / place — inductors + dock |
| **Manual Material Handling** (Zenodo 4633087) Xsens MVNX | CC BY 4.0 | Lift / lower / carry, one or two hands, 2–12 kg — dock unloaders + bag change (parse MVNX XML → BVH; download only the subjects you need) |
| **MeLLO** (SimTK) C3D/TRC | CC BY 4.0 (agreement text unverified) | Cart/wheelbarrow push → roll-cage pushers (needs marker solve; optional) |
| MINES ParisTech (Zenodo 5356992) | CC BY 4.0 | Reaching / placing (no box lift) |
Rejected (licence): OpenPack, SAFELIFT (NC), InHARD (restricted), KIT (no licence), CMU/Mixamo/Rokoko (custom).
Retarget: world-space rest-pose difference per bone → Bip01, hips scaled by leg-length ratio, bake.

## C. Parcel transit — real numbers
- Belts: standard ~0.33 m/s (65 FPM); induction belts step up ~0.5 → 0.9 m/s toward sorter speed (Hytrol training PDF).
  Manual induction ≈ 30 items/min average, 50 max (Plant Engineering). Gaps are made by the faster downstream belt.
- Accumulation: **zero-pressure zones** — photo-eye-triggered zone stops, parcels never touch (Hytrol).
- Cross-belt: our 2 m/s is realistic (Interroll up to 2.7 m/s). **Discharge: the carrier belt ramps up, starting before the
  chute, so the parcel leaves on a diagonal = sorter speed forward + carrier-belt speed sideways** (US9150362). No instant
  sideways jump.
- Gravity rollers: 2–7 % slope; curves slow parcels (Hytrol, Cisco-Eagle).
- **Blender method:** keyframe transport analytically along belt splines (gaps, zone stops); use **rigid body only for
  falls** (carrier discharge, chute slide, drop into the bag/cage): carriers + bag as Animated rigid bodies,
  `bpy.ops.rigidbody.bake_to_keyframes` per parcel window, then rest keys. This gives real tumble/settle in bags — the
  current "stacked over the bag" landing is not authentic.

## D. Reference videos to study (timestamps unverified — scrub and log what you measure)
Malaysia first: Ninja Van MY Parcel Lifecycle (https://www.youtube.com/watch?v=Yk6R-yDNoSg); Amanz "Bagaimana Ninja Van
Beroperasi?" (https://www.youtube.com/watch?v=URJt-MdFaAk). Induction: FalconAutotech "Induction in Cross Belt Sorter"
(https://www.youtube.com/watch?v=tIAgnNqpzjY). Unloading: SF Express telescopic conveyor (https://www.youtube.com/watch?v=irwCVmzKeMg),
Shopee Xpress SOC 5 (https://www.youtube.com/watch?v=FCc7hebnC3Q). Hubs: SPX Manila (https://www.youtube.com/watch?v=C7THBczDWIU),
Flash Express PH (https://www.youtube.com/watch?v=-RHNDLo1HM0). Measure per action: seconds per parcel, one vs two hands,
how often parcels are flipped label-up, spacing between workers, how deep they lean into bags.

## E. Own mocap from phone video (needs Rexton — tonight)
FreeMoCap (AGPL tool, our recordings are ours) with **2–3 phones + a ChArUco board**, detector set to MediaPipe (Apache 2.0,
no SMPL). Act: induct + flip label-up, lift carton from a stack, set on belt, lift bulk bag, push/pull a cage. Retarget as in B.
Avoid WHAM / GVHMR / video2bvh / SAM 3D Body (SMPL / non-commercial / custom licences).

## F. Crowd-perception findings (deep research, part 1 of 4 — 14:50)
- **Desync matters more than clip count:** 3 desynchronised motions were rated as varied as all-unique motions (Pražák 2011);
  1 motion per 25 characters still passed (Adili 2021). → Every worker gets a **random start offset** in its clip/cycle and
  **0.85–1.15× speed**; never two neighbours in phase.
- **Foot sliding is noticed above ~21 mm** → keep planted-foot slip < 2 cm per contact (at 1080p/20 m ≈ 2 px, visible).
- Viewers look longest at **head and upper body**; **shoulder turns when people pass each other** read as natural.
- Behaviour pattern used by NVIDIA Isaac Sim people: weighted random next-action table; Idle 2–6 s, LookAround 2–4 s,
  GoTo targets 5–20 m. Good model for walkers/supervisor/technician/break pair.
- Additive layers (breathing, fidgets) each with their own random start and speed (Golaem practice).

## G. Retargeting findings (deep research, part 2 of 4 — 14:52)
- **Rocketbox bind pose is NOT a usable reference pose** — Microsoft's own Unity importer first sets the avatars into a T-pose
  and reorganises bones. → Build a shared reference T-pose for source and Bip01 by bending limbs (no twist), store the
  world-space rotation offset per bone (Off = Rs_ref⁻¹·Rt_ref), apply it every frame **in world space, never local**.
  Hips: translate by the leg-length ratio. (Diffeomorphic retarget method.)
- **100STYLE:** 60 fps Xsens; each file starts/ends with a T-pose + extra frames — trim with `Frame_Cuts.csv`.
  **AndyData** already ships `xsens_bvh.zip` (1.8 GB), no MVNX conversion needed. Both CC BY 4.0 (credit lines in CREDITS.md).
- **Blender 5 API:** `Action.fcurves/groups/id_root` are removed — write keys through slots/channelbags
  (`strip.channelbag(slot, ensure=True).fcurves.new(...)`). Copy Global Transform is built in.
- Phone mocap noise: 1€ filter (BSD): start beta = 0, mincutoff = 1 Hz; lower mincutoff until still poses stop jittering,
  then raise beta ×10 from 0.001 until fast moves stop lagging.
- Sanity reference: Microsoft ships 417 Rocketbox animations on the same skeleton — compare a retargeted walk against them.
- After retarget: foot-contact detection (velocity + height) → IK foot lock; quaternion continuity (make_compatible) to stop
  flips; hand–body pass-through check. Licence watch: FreeMoCap add-on AGPL (offline tool only); MoveBox's video path uses
  VIBE (research-only) — don't use that part.

## H. Mocap + contact IK pipeline (deep research, part 3 of 4 — 14:55)
Order that keeps it human (Kovar/Gleicher footskate cleanup; Unreal Motion Warping; Witkin & Popović motion warping):
1. **Segment** AndyData takes with its per-frame labels (reach / pick / carry / place) into a small clip library.
2. **Retime** with monotone time-warps anchored at event frames (grasp, release, foot plants); keep speed within ~0.8–1.25×.
   DTW alignment between takes: `dtaidistance` (Apache 2.0).
3. **Warp the clip to the parcel** like Unreal Motion Warping (skew warp over a window ending at the grasp): move the
   **root first**, then solve the arm, then allow tiny leg stretch. Keep root offsets/turns small; if the parcel is too far,
   choose another clip or add a step instead of over-warping.
4. **Contact IK on top:** influence ramps in over ~0.2–0.4 s before contact and out after release; pole vector taken from
   the **mocap's own elbow direction**; spine and head stay from the mocap. Parcel parented to the hand at grasp (and to the
   belt after release).
5. **Transitions between clips:** inertialization (record pose + velocity offset at the cut, decay with a critically damped
   spring; ~0.2 s), not crossfades. Then foot locking + leg IK to remove remaining slide.
Licence watch: LaFAN1 (bundled with Holden's MIT Motion-Matching repo) is CC BY-NC-ND → excluded.

## I. Real station numbers (deep research, part 4 of 4 — 14:58)
- **Induction:** 1,200–2,000 items/h per operator (≈ 1.8–3 s/parcel); induction belts join the loop at 30° or 45°; one
  handler can work two induction points side by side; operators put labels face-up "intuitively" (BEUMER, Equinox).
- **Unloading (U. Waterloo case study):** usually **one worker per trailer** (sometimes two); **15–18 lifts/min (~900/h)**;
  wall stacked floor → 180 cm; **hands meet the conveyor at 103 cm height and ~40 cm reach** → boom nose right in front of
  the worker at ~1.0 m. Preferred zone 75–110 cm; 5–7 kg at that pace. Top of wall is pulled, not lifted, where possible.
  → Our 6 cartons/30 s (12/min) per unloader is at the low end; 2 unloaders per trailer is allowed but 1 is more typical.
- **HSE MAC (UK):** hands between knee and elbow = low risk; carry 2–4 m low, 4–10 m medium, > 10 m high → no long carries.
- **Bagging:** bulk sacks ≤ 25 kg generally safe (HSE); full sacks are swapped from roll-out sack carts when full; sacks move
  in carts, not carried one-handed.
- **Roll cages (HSE):** push, don't pull; hands at ~1,000 mm; walking pace; one cage at a time; loaded cages up to 500 kg+;
  most people can't see over 1,400 mm (cages are 1,550–1,830 mm tall) → pushers lean to look around the side.
- **Malaysia scale:** Ninja Van Shah Alam hub ~260,000 sq ft, > 400k parcels/day, part manual, part automated.
