# Builder note (13:10 Sat) — disk: plan the S2 render so it never fills C:
Your 13:0x finding is right to flag (C: under the 15 GB floor; AppData\Local\Claude-Data +8.5 GB in 5 h is the
desktop app's own data — don't touch it; Rexton decides). The S2 render must not make it worse:
1. ~10 cameras × 900 frames at 2688×1520 as PNG ≈ 40–45 GB. **Never download raw frames.** Render on Modal, run
   cctv_look + encode on Modal, keep frames on the Modal Volume.
2. Download only: one final MP4 per camera (the delivery encode), the SHA-256 manifest, and ≤ 20 native PNG proof
   frames for reviews. Expect ≈ 1–3 GB total.
3. Check free space before each download and stop at 20 GB free.
4. Old regenerable .blend files in assets/hub/build (req013/014*, test_*, *.blend1, docktest) ≈ 1.5 GB can go
   (they are regenerable by your scripts). Keep hub_lineAb_S2.blend, hub_spec*, the S1/S5 hub files.
5. Put the render estimate (frames, GPU, s/frame, US$, GB downloaded) in the next request. One run > US$10 waits for
   Rexton's OK.
