# Review 001 — B1 floor (+ answers to your 3 questions)

Verdict: **APPROVED WITH FIXES.** Diagnosis accepted: the white floor was the Workbench preview only.
Final look shows mid-grey textured epoxy, crisp yellow bay marks, no clipping. Good call moving B3 to the final look.
Review 000 #11 → closed. (Checked: proof.png, CAM_07_cctv.png, CAM_13_cctv.png.)

## Fixes (fold into B2 stills — no separate request needed)
| # | Where | Problem | Required fix | P |
|---|---|---|---|---|
| 1 | Both cams | Image reads dim and muddy next to the reference frames (dpd_t138–t152, beesort_t250): background walls/roof grey, not white; everything sits in the 40–140 band | Lift walls/roof/ceiling to read white-ish (wall mean ≥ 170 in the final CCTV frame), floor mean 85–110, keep floor share > 230 at 0 %. Visible linear LED strip rows in frame where the camera sees the ceiling line. Report the numbers again like you did | P1 |
| 2 | Both cams | Both OSDs show exactly `14:32:07` on the same frame. The case depends on drifting device clocks | Apply the per-camera offsets/drift from hub_spec in the OSD (e.g. CAM_13 a few seconds off CAM_07). Same frame → different OSD times. Log offsets to truth only | P1 |
| 3 | CAM_13 | Roll cages float at random angles across the floor and ignore the painted bay corners; the yellow cage mid-bottom reads skewed/sheared (gate panel swung at an odd angle) | Snap parked cages into their painted bays (jitter ≤ ±5°, ≤ 10 cm); only cages being moved are off-bay. Gate panels closed or fully open at a believable hinge angle | P1 |
| 4 | CAM_13 | Loose parcels lying on the floor beside the chutes (≈ 4 visible) | Every floor parcel must be a deliberate, registered object (in parcels_registry/truth) — random floor parcels become false leads for Spoor. Keep 1–2 as realistic "dropped" mess, registered; remove the rest | P1 |
| 5 | CAM_07 | Sorter loop has no guarding: no mesh fence + yellow posts (dpd_t068/t075), no stack lights, no e-stops on the loop | Add mesh guard fence with yellow posts around the walkable sides of the loop (gate at the crossover), e-stop pull-cord or boxes every ~10 m, 2–3 stack lights | P1 |
| 6 | Both cams | Lens looks perfectly rectilinear for a 103° HFOV dome; no vignette | Mild barrel distortion (k1 ≈ −0.05 to −0.08) + soft vignette in cctv_look, same model as the calibration file so Spoor's homography stays honest | P2 |
| 7 | CAM_07 | Floor inside the loop is one clean uniform slab | Wheel tracks/wear along lanes as you planned + a few scuffs/patch repairs; keep subtle | P2 |

## Answers
1. **Clip length — accepted: 30 s default.** Exception: a scenario whose story physically needs longer (e.g. chute → cage →
   trailer for the mis-load) may run up to 120 s instead of speeding anything up. Never compress real motion to fit 30 s.
   Note the per-scenario length in its scenario card.
2. **Stretch wrap — accepted: opaque**, Rexton's no-see-through rule wins. Printed cartons + gloss + wrinkle normals +
   torn flaps is the right approach. Close 000 #6 when it shows in B2.
3. **Booms** — will judge in B2 (CAM_01 + the dock camera). They must visibly enter the trailer.

Note: your log times run ~25 min ahead of the PC clock (you wrote 01:58 at 01:29). Use `Get-Date` when logging.
