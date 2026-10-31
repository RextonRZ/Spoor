# F-024 review — H2 journey + replay, H10 missing moment, H1 follow-cam — APPROVED WITH FIXES

Reviewed 03:40 Sat: desktop 31_h10, fx_32_h1, the 23 s journey_replay.mp4 (sampled every 2 s).
This was built before `F-style_review.md`, `floorplan_design_0300.md` and `owner_ideas_0303.md`; apply those on top.

Good: marker never drawn in a gap; live caption; one colour language; "not analysed yet · needs SAM" in no-key
mode; "Not seen" only from typed negatives; zoom factor printed as browser scaling; the fixture is honest (yellow
banner, real J1 SAM boxes on real crops, only the link mocked); the summary now waits for the missing moment.
**You may commit the approved backend parts (I1/I3 follow-ups, F-023) now.**

## P1
1. **Expected box on CAM_07 looks wrong.** In the CAM_07 close-up the dashed box sits on empty floor beside a
   person, not on the belt/chute. The builder moved CAM_07 to (42.8, 4.0, 8.5 m) yaw 95 and re-aimed CAM_04 at 02:11
   (log). Check the backend projects regions with the **current** camera poses from the hub spec, not a cached copy,
   and add a test that the C04 divert point projects inside CAM_07's and CAM_10's frames.
2. **Wording flicker on load.** The recording opens with "Observed: fixed scanner read · site_contoh_hub/zone_Z06 ·
   site_contoh_hub/zone_Z06" and "No suggestion: no last read point", then switches to "sorter divert confirmation"
   and the CAM_10 suggestion. Same fix as the summary: render the answer only when the journey is loaded (skeleton
   until then); never show raw ids.
3. **Follow-cam inset covers the route.** Bottom-left inset hides the 14:32:07 bead and the west of the trail.
   Dock it where it never covers the trail (e.g. top-right of the scene, or in the right panel when it's open), and
   collapse to a pill when outside a seen segment.
4. **Missing-moment rows only show "watching the last point".** The request promises "next on the belt" and
   "next on foot" rows. If the plan predicts them (bagging aisle → CAM_11/13, foot routes), show them with their
   predicted window; if not, say why in one line.
5. Images pop in black (summary key frames, close-ups): keep the tile's aspect ratio with a quiet placeholder and
   fade in (≤ 200 ms).

## P2
6. Fixture shot says "1.8× browser zoom"; re-shoot after the tighter crop so it shows the 2–4× you built.
7. The "• •" bullet before "4 camera clocks are unverified" is still broken.

Order: F-style fixes + these → floorplan_design_0300 → I4/H4 (your next) → camera strip → 3D twin.
