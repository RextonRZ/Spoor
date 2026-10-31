# 014d review — M2 retarget (m2_retarget_front_side.mp4, 300 frames; native crops of the avatar panels every 4th
# frame f50–f290, front + side, plus the 1 fps sheet)

**Verdict: APPROVED. This is the first worker motion that reads as a real person.** Checked every tile:
- Reach (f50–f110 front): hip hinge with soft knees, head leads, arm swings out from the shoulder, weight shifts back
  over the heels — matches the stick figure frame for frame. No arms-out zombie pose, no elbow pop.
- Pick / fine manipulation (side f90–f170): two hands meet in front of the belly, shoulders round slightly, head looks
  at the hands. Natural.
- Turn + walk (side f250–f290, front f170–f210): heel strike, toe-off, arm counter-swing, feet do not slide (your 0.7 mm
  max agrees with what I see), no knee pop through the lock ramps.
- No candy-wrap at the wrists, no shoulder collapse, no mesh tearing at the jacket.
- Numbers accepted: skate max 0.7 mm (31/45 mm without locks — keep locks on), penetration 0, limb error ≤ 0.21° upper
  body, leg ratio 0.835 from the participant spec, chordal-mean SO(3) resample from all 240 Hz frames, BVH zero pose
  proven = clean T, palms-inward check on the hold frames.

Carry into M3 (request 015, 19:00):
1. P0 Turn direction must match the table side. In M0 the roller table is at the inductor's FRONT-LEFT, so the pick
   turn is to the LEFT. Your note says "left-turning takes are mirrored so every line-A inductor turns right" — check:
   mirror only the takes that turn AWAY from the table. The worker must never turn his back to the table to reach it.
2. P0 Hand–carton contact: open splayed fingers are fine with no object (f60–f110), but at M3 both palms must sit on
   the carton's side faces (≤1 cm), fingers wrapped under/around the bottom edge for the lift, and release with the
   fingers opening as the push ends. Give me a dense crop (every 2nd frame, 1.5 s around grasp and release).
3. P1 Source table height vs ours: AndyData's reach goes to roughly knee–hip height (deep stoop here). Our table end is
   88 cm, so the stoop must shrink — use the root/spine warp + hand IK, not a bend into thin air. Report hand height
   at grasp (source vs target).
4. P1 Label-up flip: add a short wrist/forearm rotation in the carry turn for ~1 in 3 parcels (label facing down on
   the table → up on the belt). Real inductors do this constantly.
5. P2 Belt indexing: stop → hands off 0.3 s → accelerate to 1.5 m/s is how real induction belts sync with a sorter.
   Keep it.
6. P2 Desync at M3 already: 4 inductors from 3 performers, random start offsets, speed 0.92–1.12, no two neighbours on
   the same take.
