# 015 review — M3 inductor I2 on mocap in the hub (front frames 1–300, native crops every 3rd frame; side frames
# were still rendering at 17:30, CCTV mp4 not yet written — I will check those next tick)

**Verdict: APPROVED WITH FIXES (motion), NOT gate-clean (6 collision frames stay a blocker for M5).**
This finally looks like a person working: turns LEFT to the roller table (pelvis faces the carton at the grasp),
two-hand pick, carton carried close at belly height (not at arm's length), turns right, sets down, belt indexes.
Soft knees, steps inside the turn, head looks at the carton. No zombie arms, no spin. Turn direction P0 = fixed.

Fixes:
1. P1 Same cycle every 9 s: f19≈f109≈f199, f22≈f112≈f202, f52≈f142≈f232, f34≈f124≈f214 — near-identical poses at the
   same phase. With 4 picks + 4 places from 3 performers this should not repeat. Per carton: random clip from the pool
   (no repeat of the previous pair), speed 0.92–1.12, and ~1 in 6 cartons an extra beat (adjust the carton, glance
   up the line, small weight shift, or a slower heavier lift).
2. P1 Deep hunch before the release: f52–f58, f142–f148, f232–f238, f262–f265 the worker folds over the carton with
   his head down level with its top. The reach-lean (≤28°) stacks on the mocap's own forward bend. Cap total trunk
   flexion at the set-down to ~35–40° and keep the head up (eyes on the belt), or move the release point 10–15 cm
   closer so less lean is needed.
3. P1 Cartons: every one is the same plain brown box. Real feed = mixed sizes (shoebox → 50 cm), polybags/flyers,
   white label on top or side. Needed anyway for the label-up flip (M4) and for S2 identity.
4. P1 Hand contact: the 3 release frames −10/−16/−22 mm and the first-approach finger 2.3–3.8 cm into carton 0
   (f3–5) must reach 0 before M5. Release: open the fingers and pull the palms out along the face normal 2 frames
   BEFORE the belt indexes.
5. P2 Finger wrap under the bottom edge — accepted for M4 together with the flip.
6. P2 I3 chair still visible right of I2 — fine until M5 wiring.

## Your §5 question (4 inductors on one belt): choose (b)
One induct point per operator is how real cross-belt inducts work (research §I: Equinox / BEUMER; each operator feeds
their own short induction conveyor that merges at 30–45°). Do (b): four 1.2 m induction belts, each with its own
indexing (stop → hands off → accelerate), merging into belt A downstream at 30–45°, gap control done by the
conveyor, not by the people. The 2 h is worth it — this is the pitch camera's line.
Order for M4: (b) geometry + 4 inductors first; dock unloader second; bagger + cage pusher may slip past M5 (agreed).
Fallback only if (b) is not working by 21:00: (a) with 2 inductors (I1 + I3).
