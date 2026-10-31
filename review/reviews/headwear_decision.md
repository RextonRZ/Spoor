# Headwear — reviewer decision 14:35 (Rexton: "why the cap still so weird")

Three attempts at caps have failed (floating → torn shrinkwrap → face covered). Root causes: one generic cap mesh is being
warped onto different Rocketbox heads every frame (shrinkwrap tears it), and Biped head-bone axes don't match the cap's axes
(the same axis trap as the fingers), so the cap tilts over the face.

**Authenticity check:** our real-hub reference frames (docs/hub/reference_frames: DPD Warsaw, BeeSort hubs) show workers in
T-shirts and hi-vis vests — **no baseball caps, no hard hats** at sorting, induction, chutes or cage staging. Hard hats are a
construction/yard item, not standard inside a parcel hub.

**Decision (P0, do now):** remove **all caps and hard hats** from every worker. Keep vests/T-shirts (mixed, as the references
show). If a specific role is sourced as wearing headgear (e.g. a yard marshal outdoors), propose it with the source and a
clean, rigidly fitted, per-avatar model — never shrinkwrap.
This also removes the accessory_fit / held_clip_head work on hats, so spend that time on the motion and collisions.
**UPDATED by Rexton (14:36): "maybe some got cap can".** Final rule:
- **No hard hats** on anyone.
- **Caps: only on 2–3 workers** (a real mix — most bare-headed), and only if they look like a real cap:
  - one clean closed cap mesh **made/fitted per avatar head** at the bind pose (scaled + offset to that avatar's skull), then
    **parented rigidly to the head bone (full transform)** — no shrinkwrap, no per-frame deformation;
  - crown ~10–11 cm above the band, curved brim ~7 cm, band 2–3 cm above the eyebrows, matte cotton; hair hidden or out
    the back opening, never through the crown;
  - choose avatars with short hair for caps (no ponytail/bun);
  - proof: front + side head sheets every 10 frames (face clearly visible from the front), `accessory_follow` ≤ 1 cm / ≤ 3°
    every frame, 0 collision rows on the cap.
- If a cap fails any of these in the next request, remove it — no more cap iterations.


## FINAL (15:18, review 013c): strike used. NO headwear on any worker. Closed.
