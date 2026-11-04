last commit reviewed: b7ffa21

Reviewer tick 01:47 Mon 2 Nov. Everything Rexton decided after your 01:38 ACK, in one place:
- Investigating screen (141d9c0): good. Fix the count: "1 of 19 cameras checked" undersells it; count every camera
  the run used incl. reused SAM results and Glimmer's sweep, e.g. "19 cameras swept · 3 examined closely".
- six_checkpoints_on_camera_0915.md now has ADDENDUM 5 (landing page checkpoint section gets the clips) and
  ADDENDUM 6 (6 close-up checkpoint CCTV cameras: unloading, tunnel exit, chute row, west cage bays, Exception store
  door, outbound dock D07; the most important part). Re-read the whole file (addenda 1-6) before step 1.
- Render cap is now US$12 total (Rexton). Modal render only after a reviewer_tick says APPROVED.
- Keep line B unstaffed in W1/W2 too, same as S2, so the hub looks the same in every clip.
- When W1 is simulated, re-take the story parcel's tunnel photo (SCANNER_TUNNEL_A) at the real 14:10:40 moment,
  replacing the staged "from recorded history" still.
- Camera counts everywhere (screens, Glimmer step, docs) must match the final setup: 19 wide CCTV + 6 checkpoint
  CCTV + 1 tunnel label camera. Glimmer swept the 19 only: run it on the new clips too (< US$0.30) or say "19 wide
  cameras swept".
Order tonight: finish the case-page cleanup -> commit -> six-checkpoint steps 1-3 (estimate + same-parcel checks in
READY.md, cameras placed + calibrated, sim + gates, local preview). Reviewer checks at 04:00 for the render OK.

BUILD ORDER for the six-checkpoint work (Rexton OK 01:50): each step must be usable on its own, so a late failure
still leaves a working demo. Commit after each.
1. Handshake + passport + live "left without a scan" alert on the EXISTING S2 footage (no render): look-alike and
   other parcels scanned 14:32-14:33, the CAM_13 pick for the alert.
2. New W1 / W2 clips on the existing WIDE cameras.
3. Close-up checkpoint cameras, easiest first: tunnel exit, chute row, dock D07, store door.
4. Cage-bays close-up LAST. If hands taking the carton look fake after the allowed sim runs, drop that camera and
   keep CAM_13 + the live alert for that moment. Do not let it delay steps 1-3.
Close-ups show animation flaws that far cameras hid: judge them in the local preview before asking for the render.

AVOID DOUBLE WORK (Rexton 01:55): the evidence sections (checkpoints, route wall, timeline, Proof) will be rebuilt
around the six-checkpoint clips and the passport. So finish the case-page cleanup as CORRECTNESS ONLY: one source
of truth (latest verified run), no contradictions, truck D07 not green, no internal IDs/UTC, C05/C12 resolved,
camera counts. No layout or visual polish on those sections now. Commit it and move to the six-checkpoint step 1.
