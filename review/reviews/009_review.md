# Review 009 — A3 people fixes + QA gates (+ early look at D2 CAM_07)

Verdict: **APPROVED WITH FIXES — block A closed.** The cause analysis is excellent (stacked lean, root offset, 7 overlap
causes) and the new gate (`qa_gate.py` in `render_batch.sh`) is exactly how this should be enforced.
Re-checked with motion_check: induct_2 local pops 33 → 5, cage_2 15 → 7, bag_1 17 → 8, D05_n 18 → 14, cage_1 11 → 2.
Carton now carried out front (induct_2 f27, f299), cage_2 pusher stays behind the posts (f190–299), bagger works in
sequence, HMI shows a UI, dock follow-cam stands in the hall.

## Answers
1. **§3.1–3.2 residuals for the S0 batch: accepted, with one condition.** None of the residual overlaps/contacts may involve
   the **story parcel** of any scenario, any parcel within ±10 s of a scenario event, or the hero cameras' key windows
   (S2: blind-spot entry; S5: the look-alike swap). Make `qa_gate.py` strict (no GATE_FORCE) inside those windows.
2. **Dock step-back: not before the batch.** At CCTV distance an 8–11 cm head contact for 4 frames on the far side of a
   carton isn't visible; 2 h + re-running every scenario isn't worth it now. Put it on the post-batch list.

## Still to do before the S0 batch — from `B2_prereview.md`
P0 #1 interpenetrating red cages (CAM_15), P0 #2 carton hanging past the reject chute (verify in D2/CAM_09 — if it's mid-fall
it must land inside the bin), P1 #3 fur-like wall-base fringe, P1 #4 loop occupancy, P1 #5 scan tunnel hero look, P1 #6 yard.
These are cheap scene fixes; the batch should not start without them.

## Early D2 check (renders/S0/CAM_07.mp4, unrequested)
- 2688×1520 HEVC, 10 fps, 300 frames, 7.7 MB ✓. **OSD ticks exactly 1 s per 10 frames** (14:32:11 → :21 → :31 → :41) ✓.
- motion_check: 0 global jumps, 0 local pops ✓. Trails: carriers move smoothly along the loop, people move along the chute row.
- Same note as B2 #4: the loop carries very few parcels; half the frame is the empty loop interior. Occupancy fix helps this
  camera most.
