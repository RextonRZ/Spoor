# 021d review (12:45 Sat) — P0s APPROVED; run 4 progress good; question answered

## P0 answers — APPROVED
- Canonical spec = `assets/hub/hub_spec.json` (layout b, generated), lineAb = checked copy, mojibake fixed. Good.
- The false "records disagree" was the hand-typed S2/S3 history lines (21.7 s vs a 25.9 s loop ride). Fixed at the
  source (loop_ride_s from geometry) + `check_scan_routes.py` in the pipeline with `designed_route_conflicts`
  exemptions, and it passes all 2,261 simulated pairs. Exactly the right fix.
- The 16 false stalled: missing per-parcel bag scans + log ending mid-flow. Fixed in the splice, with the inbox's own
  rule re-run as a check against `designed_stalled`. 0 stalled; S2's subject shows as the customer case; ≥ 22 min of
  traffic after the divert. Good.
- **Frontend:** reseed from `assets/hub/hub_spec.json` + the new long log, run `npm run gen:hub`, re-shoot Answer and
  Report: S2's only conflict must be the designed dock one.

## Run 4 vs 3
Visible rows 1,507 → 774; S2 actor 0. Chutes 487 → 24, pusher 2 fixed, line A fully diagnosed for run 5. Keep going in
the same order (pusher 1 next).

## Question: may a station that can't reach 0 visible rows be UNSTAFFED for the S2 render? — Yes, with conditions
1. Only stations that are **not part of the S2 story**. Always staffed: the S2 actor, cage staging around RC-864, the
   C12 bagging, the dock D07 cage load, and anyone CAM_19 sees.
2. The empty station must look **plausibly idle**, not abandoned mid-task: bag opener = bags waiting on the bench,
   none half-open; dock D02 = no truck docked / doors closed, or a truck waiting with the boom retracted; no parcels
   arriving at an unmanned point; nothing frozen in mid-air.
3. At least one other person stays visible in each S2 camera that had one, so the hub still feels busy (wall-to-wall
   empty frames read as fake).
4. List each unstaffed station in the S2 card's known limitations and in 021e. Fix them before any scenario that
   films them and before the fly-through (unchanged rule).
Bag opener (mime grip, overhead carry, heeled boots) and dock D02 → unstaff for S2 is accepted on those terms.

Next: 021e with run 5's numbers + the top-5 turn crops, then the S2 render estimate (if one run > US$10, it waits
for Rexton's OK).
