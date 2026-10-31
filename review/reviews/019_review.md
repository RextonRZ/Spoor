# 019 review — S2 perimeter proof + new CAM_19 "EXCEPTION STORE"

**Verdict: APPROVED WITH FIXES.** Strong work: raycast in the real geometry with the lens crop, one walk-in only,
16 % → 5 % inside visibility (doorway view only), gap south face 100 % seen, a person in the gap 100 %, CAM_13's old
claim corrected, TAPA FSR 2023 §7.4.15–16 as the source for an entrance-only camera. Planner re-run, CAM_01–18 unchanged.

Fixes:
1. P1 CAM_19 framing: the doorway sits centre-right with ~60 % of the frame on the west rack front and blank wall. Yaw
   ~10–15° east so the doorway is in the middle third AND the floor approach from cage S11 is in the lower half — the
   pitch needs "walks in carrying it" and "walks out empty-handed" in the same shot.
2. P1 Sign over the doorway, readable in CAM_19: "STOR PENGECUALIAN / EXCEPTION STORE" (scenarios_v2 S2 #4).
3. P2 The unseen strip x 13.45–13.55, z ≥ 0.7 behind the south rack's end upright: accepted (only reachable through the
   fully seen south face). State it in the truth card.
4. P2 Over-the-rack throw: accepted as "not a way out for a person; landing band 83 % seen" — write it into the card's
   limitations; do not build anything for it.
5. P2 Log clock: your 00:58 line comes before the 00:42 line — use the system clock (`date`) for every log time.

Next: the removal actor on mocap (S2 #2), then window 90 s + empty-handed exit + cage RFID at its dock.
