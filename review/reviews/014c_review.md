# 014c review — M1 sources, Rocketbox rig facts, shared T-pose

**Verdict: APPROVED.** Range-fetching single files from Zenodo was the right call. sources.csv + CREDITS.md rows,
labels legend from the paper (Table 1), label time = BVH time check, rig facts (Bip01 Pelvis root, 0.01 scale, A-pose
43.9° / 42.3°), T-pose 0.00° error, relaxed fingers (no claw, no hyper-extension) — all checked on the sheet.

Carry into M2 (17:30):
1. P1 Prove the SOURCE reference pose: render the AndyData skeleton (5124) at all-zero channels AND at its frame 0
   next to our Rocketbox T-pose. If the BVH zero pose is not a clean T (palms down, arms lateral), take the offsets
   from a measured T frame instead. 100STYLE: use its start T-pose frames (before Frame_Cuts) as reference.
2. P1 240 Hz → scene rate: low-pass then resample (slerp per joint), never drop frames raw; do it before the 1€/SG
   filter tuning so jitter numbers are at final rate.
3. P1 Leg ratio from participant_specifications.csv (hip-to-ankle) vs avatar; print both numbers in the QA table.
4. P1 QA table must show: foot skate per contact (mm, target <20), ground penetration frames (=0), limb direction
   error vs source (deg, mean/max per limb), wrist/forearm twist max (deg, flags candy-wrap > 90°).
5. P2 Female_Adult_04 heeled boots: agreed — not on the floor as a handler; recast at M4 with flat shoes.
6. P2 Three performers: good; also keep each worker's clip start offset random (0–100 %) per the plan.
