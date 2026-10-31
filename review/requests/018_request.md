# 018 request: M5 step 3, the first full hub run with line A on mocap (not for render, a progress check)

**Date:** 2026-10-30 ~20:30 MYT · **Builder**

**What:** layout (b) built and dressed (`build/hub_lineAb_dressed.blend`, test spec, the switch still off for S0–S5). The full flow runs with every station, and line A's 4 inductors are built by the mocap engine from the flow-timed plan (017). One run is 7.5 min. Then the **whole-hub** collision check (`collision_check.py`, every moving thing, every frame).

## Evidence
| What | File |
|---|---|
| Overview of line A at f50 / f120 / f200 / f270 (Workbench) | `qa/review/m5_hub/overview_f50_f120_f200_f270.jpg` (singles in `stills/`) |
| I2 close at the same frames | `qa/review/m5_hub/I2_close_f50_f120_f200_f270.jpg` |
| Collision check, whole hub | `qa/review/m5_hub/collisions/collisions.csv` + `collisions_summary.txt` |
| Inductor report (cycles, reach fix, curtain, zone correction, release offsets) | `qa/review/m5_hub/induction_report.json` |

## Numbers (30 s)
| | Run 1 | Run 2 | **Run 3 (now)** |
|---|---|---|---|
| Inductor body vs anything ≥ 1 cm | **0** | **0** | **0** |
| Line A parcel vs conveyor / parcel rows | 141 | 212 | **65** (feed 36, induct belts 29) |
| Release offset, engine vs flow | 25 cm | 25 cm | 12 cm |
| Cycles in window I1–I4 | 6/7/6/2 | — | 7/7/4/3 |

Fixes between the runs:
- feed frame opened where D02's stub joins;
- diverter = photo-eye trigger, and the fit is checked against the table's guides;
- the feed zone-stops its head parcel on the last mouth;
- the guides square parcels on the feed, the induct belts and belt A;
- the engine re-clamps the set-down into the induct belt's zone;
- the parcel keeps its world yaw at the induct → belt A transfer (no snap).

The remaining 65 rows are 1–4 cm corner grazes at the mouths and on the induct belts. **Not zero yet.** Other stations (docks, bagger, cages, line B, opener) are still on the old motion; their rows are the known M5 backlog.

## Honest list (what is NOT right yet)
1. **f200 (I2), empty-handed hold:** while waiting for a parcel he holds both hands out in front, as if carrying. That is exactly your 017 #1. Fix next: idle variations from 100STYLE / Rocketbox in every wait over 1.5 s, plus a gate row for the longest still stretch (< 3 s).
2. **Reach safety net up to 12–15 cm on 3 workers:** where the IK can't reach the grip, the carton follows the hands. The new zone re-clamp moves the set-down 7–17 cm, more than the arms can follow on some cycles. To fix: move the place root with the clamp instead of only the carton.
3. **Mailers are still palm-on-top** (rejected in 017). First try at the pinch: thumb tip swung under the near edge into a roller gap. Result: 163 frames, the thumb through the edge (its base sits over the mailer). Switched off. It needs per-finger articulation: index + middle into the 4.1 cm roller gap with the thumb on top, or the thumb curling round the edge.
4. **Belt start:** 2 set-downs where the 0.3 s start comes before the hands are clear.

## Next (tomorrow, in this order)
1. Idles.
2. Root follows the zone clamp.
3. Mailer pinch.
4. Line A parcel rows to 0.
5. Then switch layout (b) on for **S2** and run its gates (your 18:45 S2-first plan, still waiting for Rexton's answer).
