# 017 request: M5 steps 1–2, line A (b) in the real build and the parcel flow (no workers yet)

**Date:** 2026-10-30 19:30 MYT · **Builder** · **Plan:** `assets/hub/mocap/M5_PLAN.md` (step 1 / step 2 status sections)

This is the wiring under the mocap line A, done behind a switch so today's S0–S5 builds are unchanged. **No workers are in it yet:** step 3 builds the avatars from the timings below.

## Evidence
| What | File |
|---|---|
| Geometry (Workbench, random colours): top + perspective of the new line A in the real `build_hub` | `qa/review/m5_geom/lineab_top.png`, `lineab_persp.png` |
| Flow simulation, 3 seeds: 6 plan-view snapshots each (boxes brown, mailers grey; orange worker = carton in the hands) + every inductor's timeline (grey = parcel waiting at the table stop, orange = grasp → release) | `qa/review/m5_flow/sim_seed7.png`, `sim_seed11.png`, `sim_seed3.png` (+ `.json`) |

## What changed
1. **Geometry** (`build_hub.py`, `build_hub_plan.py`, `dress_hub.py`; new `line_a_geom.py`, shared by build / flow / stations). Under `line_a.layout = "b"`:
   - feed line at y 12.25;
   - D02 stub belt;
   - 4 gravity roller tables with guides and end stops;
   - 4 diverter paddles;
   - 4 induct belts, 45° into belt A, ends cut flush with belt A's frame;
   - mouths cut in the frames;
   - I3 chair moved.

   The switch is off (`LINE_A_LAYOUT = "a"`): regenerating the spec only adds the `line_a` key.
2. **Engine** (`mocap/inductor.py`):
   - `Planner` plans one carton per call, so the flow drives it as parcels arrive. The benches' plans are identical (4 cases compared).
   - `Planner.delay()` lets the operator hold the carton over his belt while its set-down spot is still taken.
3. **Flow** (`flow.py --spec … --sim-only …`, `stations.MocapInductors`):
   - collector / D02 stub → feed (0.8 m/s, end stop 0.3 m past the last mouth);
   - diverter k pushes any parcel that fits through the 0.6 m mouth into empty table k (at least 0.6 s after the last lift);
   - the guides centre and square it;
   - at the stop, the station's Planner gives grasp / lift / release from the real clips;
   - set-down on induct belt k at 0.22 m, held 0.5 s for the light curtain;
   - merge onto belt A by the existing side-merge gap rule.

## Numbers (30 s window, 240 s pre-roll)
| Seed | Tunnel reads / 30 s | Cycles I1–I4 | Median release gap | Feed max | Collector max | Conflicts | Parcels squared at the stop |
|---|---|---|---|---|---|---|---|
| 7 | 35 | 7 / 6 / 6 / 3 | 4.2 s | 7 | 6 | 0 | 0.1° max skew |
| 11 | 44 | 6 / 6 / 6 / 7 | 4.8 s | 8 | 7 | 0 | 0.1° |
| 3 | 38 | 6 / 5 / 5 / 3 | 5.5 s | 6 | 5 | 0 | 0.1° |

Today's layout "a" gives 41 tunnel reads. Measured and rejected:
- **Feed 0.5 m/s:** I3 and I4 starved, the collector backed up to 20, and I4 never worked.
- **Feed 1.0 m/s:** 2 set-downs onto an occupied induct belt.
- **No hold at the belt:** 3 conflicts on seed 11. With the hold there are 0.

## Decisions I made (please challenge)
1. **The line is supply-limited** (the docks feed it), so inductors wait for parcels and I4, the last one, idles most (3 of 30 s on two seeds). That is what a first-free-table diverter does. Options: leave it, or staff I1–I3 only in S0 and keep I4 as an empty station.
2. **BLOCKER for step 3, mailers:** 60 % of flow parcels are flat mailers (4–6 cm), and the engine only does the two-hand side grip on cartons. I'll build a **one-hand pick** for them:
   - right hand, palm down over the near edge, thumb under the lip at the table's low end;
   - the left arm relaxed out of the two-hand clip (rotations taken from an idle pose, relative to the spine).

   The real reference frames show inductors reaching one-handed into the stream at induction, and polybags at the induct points, but no clear grip. The alternative, mailers off line A, would change the hub's flow. Do you see a one-hand mailer pick differently?
3. Holding the carton longer over the belt (up to 8 s grasp → release) is how the merge backs up, instead of a set-down onto a waiting parcel.

## Also (016b)
P0 measured: the head is 28–33 cm from every carton at f61–71 (occlusion from the behind camera). The new head check found **f198–205 at 0.5–3.2 cm** (floor-tier stoop under the back row). It becomes a gate row; see `replies/016b_builder_reply.md`.
