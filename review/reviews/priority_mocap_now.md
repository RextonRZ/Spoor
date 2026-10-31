# PRIORITY CHANGE — 14:40 (Rexton, again: "why the action still so zombie")

Root cause is the method, not a bug: inductor and dock motion is **computed** (IK poses on top of idle clips). However many
collisions get fixed, computed poses read as robotic — no weight, no rhythm, no human timing. Fixing collisions on that motion
now and then swapping the motion later means **doing the collision work twice**.

**Do now, in this order:**
1. **Real motion base for inductors + dock unloaders, today** (realism_plan.md §B): AndyData `xsens_bvh.zip` (CC BY 4.0,
   reach/pick/carry/place) and Manual Material Handling (CC BY 4.0, lift/lower/carry 2–12 kg). Download only what you need,
   cut pick → carry → place segments, retarget to Bip01 (world-space rest-pose difference, hips by leg-length ratio), and
   let IK correct only the last 10–15 cm to the actual parcel. Credit both in CREDITS.md.
2. **100STYLE (CC BY 4.0)** for every walk, turn and idle (replaces robotic walks and frozen stands).
3. The motion layer from realism_plan.md §A on top: minimum-jerk easing, spring followers (pelvis/spine/head/box lag),
   gaze leads hands, reach cap → step, breathing + weight shift, ±15 % tempo per worker.
4. **Then** resume collision fixing on these stations. Keep fixing collisions now only where motion won't change
   (cages, bags, parcels on belts/chutes, static scene, mesh hygiene).
5. **First proof within 2 hours:** one inductor and one dock unloader on the new base, front + side follow-cams, **final look
   (EEVEE)**, side-by-side with the old version. If the mocap base doesn't clearly look more human, say so with the clips.

This supersedes the "AndyData only if time allows" note in decision_resolution.md — Rexton's bar makes it mandatory.

## Rexton 14:40: "take box, turn around — super fake". The approach (P0, part of the same change)
The fake look is built into the **station layout**: the feed belt and the induction belt are parallel with the worker in an
aisle between them, so **every parcel forces a lift + 180° spin**. Real stations are laid out so the transfer is short:
- **Induction (line A and B):** the operator **faces the induction belt**; parcels arrive on an angled gravity-roller table
  or the accumulation belt's end **at the operator's side / front-left**, at the same height. Motion per parcel:
  glance → reach to the side → **slide** (light parcels are slid, not lifted) or short two-hand lift for heavy ones → flip
  label-up if needed → **push forward** onto the belt into the gap. Trunk rotation ≤ 60–90°, feet mostly planted with one
  small step when needed. No 180° spins. Check against the FalconAutotech induction video and the Ninja Van MY videos in
  realism_plan.md §D before locking the geometry.
- **Dock unload:** the boom nose sits **right beside the worker at waist height** inside the trailer, so the move is: grab
  carton from the wall → short pivot (≤ 90°) with a step → set on the boom. Never walk/turn with the carton across the trailer.
- **Bagging, cages:** same rule — design the spot so the move is a short pivot or a straight push, not a spin.
Change the station geometry first, then re-cut the mocap segments to these shorter moves.

## Rexton 14:47 — he wants to SEE it
Send the proof as soon as it exists, even rough: **first visible clip within ~60 min** (one inductor at the redesigned
station, EEVEE, front + side, 10–15 s), then the rest. Put it in `review/requests/014_request.md` with the video paths.
The reviewer forwards it to Rexton's phone immediately. Deep research on applying mocap (retargeting, blending with IK,
real station geometry, studio practice) is running now; results land in `review/research/` — read them when they appear.
