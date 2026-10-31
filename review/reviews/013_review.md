# Review 013 — A4 interim milestone

Verdict: **NOT APPROVED (interim, as expected) — real progress on collisions, but headwear is still broken.**
Collision trend 3994 → 933 (S0) and the cause analysis (finger axis bug, forearm along faces, mates' overlap at the boom nose)
are excellent. Measured cartons/30 s from the baked tracks: thank you, that's the right evidence.

## Missing from what was promised
- `qa/review/req013/follow/` is **empty** — no front-angle inductor videos and no dock hall-angle videos. Only `_frames/`
  partial PNGs exist. Send them in the next request.
- Evidence was written to **`Spoor/qa/review/req013/`**, not `assets/hub/build/qa/review/req013/` as the request says. Fix the
  path (or the text) so nothing gets lost.

## P0 — headwear is NOT fixed (from your own head sheets)
`accessory_fit = 0` passes because it only measures the band. Look at the sheets:
| Sheet | Frames | Problem |
|---|---|---|
| `heads/worker_induct_2_front_sheet` | **every frame** | From the front, the cap crown **covers the whole face** — eyes, nose, mouth hidden behind a big white dome. The cap is pulled far down/forward, or the crown is scaled far too large. |
| `heads/worker_induct_2_side_sheet` | f1–f291 | Crown is a tall bulbous mushroom; brim is a thin long "duckbill"; **jagged black teeth along the band** (shrinkwrap tearing); the ponytail/bun **pokes through the back of the crown** (f61, f71, f171, f231, f291). |
| `heads/worker_cage_1_side_sheet` | f1–f291 | The back of the crown is **torn open** — the head silhouette shows through a jagged hole in every frame. |
| `heads/worker_dock_D05_n_side_sheet` | **f251**, f81 | **Hard hat with no head under it** at f251 (hat alone in an empty frame); at f81 the hat sits detached above the head. f91/f191 empty frames — the head camera lost the head (or the head is somewhere the hat isn't). |
Required:
1. A cap that looks like a real cap: crown height ~10–11 cm above the band, brim ~7 cm, curved, band 2–3 cm above the
   eyebrows; the crown never below the brow line. Hair: ponytail/bun exits the back opening (or is hidden) — never through
   the crown.
2. No shrinkwrap tearing: if shrinkwrap can't do it cleanly, fit the cap rigidly per avatar head size (scale + offset from the
   bind pose) and parent to the head bone. Clean closed mesh, no holes.
3. Hard hats: parent to the head bone with full transform; investigate f81/f251 — that's a separation, not a gap.
4. New QA `accessory_follow`: hat centroid offset from its fitted pose relative to the head bone ≤ 1 cm and ≤ 3°, **every frame**;
   plus a face-visibility check (eyes not covered in a front render).
5. Head sheets must show a recognisable face from the front. Include them again for every hat wearer.

## Answers
1. **Loop occupancy 27–29 %: accept it.** My 30–35 % target wasn't sourced; 27–29 % is a believable mid-shift and both
   structural options cost hours that belong to the people. Note it in the scenario cards.
2. **Bag change:** dragging a full sack across the floor is believable (it's how heavy sacks move), but a **one-handed carry
   at 0.55 m to the side is not** for a full sack. Make it: unhook, tie (off-screen is fine), **drag on the floor with two hands
   on the neck, walking backwards or half-turned**, then a **two-hand squat lift** into the cage (or tip it in from the cage's low
   side / onto a low-sided cage). Check the realism plan's reference videos for any bagging footage before locking it.

## Next request — must include
Follow-cam videos (front inductors, hall-angle docks, side pushers), 1 fps sheets, fixed head sheets (front + side) for every
hat wearer, collision table (target S0 < 400, S2 < 450), and the mesh-hygiene first report (D01 panel diagnosis).
