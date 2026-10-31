# 014 review — interim 2 (test 17/18), 1 fps sheets of induct_2, dock_D05_n, bag_1 (+ heads)

**Verdict: NOT APPROVED. And you have not picked up two newer orders — read these FIRST, they override your §6 plan:**
- `reviews/013c_review.md` (15:18): headwear strike → **NO headwear on any worker. Closed.** Do not fit caps again.
- `reviews/014_GO_mocap_plan.md` (15:03, owner order "Go fix using this plan"): mocap pipeline M0–M5.

## Findings (frame = follow-cam frame number)
1. P0 Headwear still in the scene: yellow hard hat on dock_D05_n (every frame f0–f290), white hard hat on bag_1
   (f0–f290, over a ponytail). Your new cap also ships. → remove all (013c). Stop all headwear work.
2. P0 Line A inductors (induct_2 follow): 3–4 people packed into the 0.45 m aisle between the belt frames; bodies
   overlap each other at f40, f80, f140, f180, f230 (tudung worker merged behind the man; blonde inside his
   shoulder). Owner rule: people never overlap people. Your own table shows person column = 0 → the person–person
   check is not catching this. Fix the check, then the layout.
3. P0 Station layout not redesigned (M0 missed): inductors still turn away from the belt to cartons lying on the
   floor beside them (f50, f150, f200) and hug big cartons to the chest (f170). Required (Rexton 14:40, research
   §I): face the belt, buffer at the SIDE within reach at ~75–110 cm height, short slide/lift + push, ≤60–90° trunk
   turn, never a spin with a carton, one inductor per induct point (max 2 side-by-side inducts per person).
4. P1 dock_D05_n: the worker is hidden behind a giant carton for ~25 of 30 tiles; only head bobbing visible; no
   carton reaches the boom in view; the mate is a head over the wall. I cannot judge this → re-pick the follow
   camera (side view, 3/4 from the trailer door) so hands, carton and boom nose are all in frame.
5. P1 bag_1: stands idle f150–f190 (4 s, arms hanging) after the cage drop. Sack drag + lift reads plausible now.

## What to do now (no more patching the old motion — it is being replaced)
- Stop the §6 collision work on inductor/dock arm grazes: that motion is thrown away by M2–M3.
- Next 45 min: remove headwear (013c) + fix the person–person check + deliver M0 (inductor layout only, 4 people,
  1 per induct point, clear 0.8 m+ aisle, buffer at the side) as a still top view + front view.
- Then M1 by 16:30 exactly as in 014_GO_mocap_plan.md (sources.csv, AndyData BVH + labels, 100STYLE, Rocketbox
  bone dump + T-pose).
- Mesh hygiene work (3,062 → 9 z-fights, n-gons 0): accepted for now, good. CAM_15 speckle: later.
