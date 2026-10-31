# 018b request: 018 #1 (idles) and #2 (release rest) fixed and re-run in the hub; #3 diagnosed

**Date:** 2026-10-30 ~21:00 MYT · **Builder** · same scene as 018 (layout b test spec, full hub run 7)

## Evidence
| What | File |
|---|---|
| I2 close at f50 / f120 / f200 / f270 (same frames as 018) | `qa/review/m5_hub/I2_close_f50_f120_f200_f270.jpg` |
| Overview, same frames | `qa/review/m5_hub/overview_f50_f120_f200_f270.jpg` |
| Whole-hub collision check, run 7 | `qa/review/m5_hub/collisions/` |
| Inductor report | `qa/review/m5_hub/induction_report.json` |

## What changed
1. **#1 idles:**
   - every wait for a parcel ≥ 0.6 s, and every "extra beat", is a cut of **100STYLE Neutral_ID** (CC BY 4.0, already credited): weight shifts, arms down;
   - long waits are chained ≤ 6 s mirrored cuts inside the take's clean frames;
   - it plays from where the last clip ended, facing the same way, blended in and out over 0.3 s;
   - pick and place timing is unchanged (checked on 4 benches).

   **f200 now:** standing relaxed, arms at the sides (was: palms up in front of the belly).
2. **#2 release rest:**
   - after a release the hands go back toward the body, then down, and hang beside the thighs, palm to the thigh, fingers relaxed;
   - if that point is over a belt or table it slides in toward the pelvis.

   **f50 now:** right hand down at the hip (was: hooked in front of the belly).
3. **#3 reach safety net:** the 12–15 cm cases are **all one-hand mailers** (I1 #48 37×27 cm, I4 #35 32×24 cm, 122 mm each); boxes ≤ 47 mm. So it goes with the mailer grip rebuild (#4), not with the place root.

## Numbers
- **Inductor bodies vs anything ≥ 1 cm, whole hub, run 7: 0.**
- On the bench (4 workers, 60 % mailers) the hanging rest showed +8 fingertip frames against the bench's box-shaped belt volumes. The real belt meshes in the hub check show none.
- **Line A parcel rows: 65, unchanged (#5, next).**
- Whole hub: 512 rows, mostly the old-motion stations (#6, the M5 backlog).

## Please check
- **f50, right hand at the hip:** natural enough, or do you want the arm fully down along the thigh?
- **The idles at your camera distance:** is the 100STYLE neutral idle (a man standing, small weight shifts) the waiting look you meant, or should some waits get the hand-on-rail / glance-up-the-feed variants? Those need other sources (none fetched yet).
