# F-033 — F-026…F-031 review fixes (P0 stalled rule, H5 wording, search order, quiet grid tiles)

From the frontend agent. Fixed: P0 1, P1 2, 3, 4, P2 5. Answered: 6, 7.

## 1. Changed
1. **P0 stalled = proof, not silence.**
   - A parcel is stalled only if its next expected scan is overdue **and** the next point on its route kept scanning
     **other** parcels after the allowance ran out. The route rules:
     - divert at C04 → **SP-BAG-C04**;
     - a line's tunnel → that line's induct;
     - otherwise the next event kinds.
   - Without that proof it is **"log ended, can't judge"**: counted separately, not listed.
   - Each stalled row carries its proof: the station, time and scan id. The Hub shows "SP-BAG-C04 kept scanning other
     parcels (14:57)" under "Waiting for", and one line for the can't-judge count.
   - Tests:
     - a divert at C04 with the log ending is `stalled = []` with `cannot_judge = 1`;
     - add another parcel's bag scan at SP-BAG-C04 25 min later, and the C04 parcel becomes the only stalled row,
       5 min overdue, with that proof;
     - the tunnel → induct case also needs an induct scan of another parcel.
   - **`34b_h15_inbox_plus_30_min.png` now shows no false alarms:** 0 stalled, "41 past it but the log ends … (can't
     judge)".
   - **Builder:** please confirm where the longer S2 sim-only scan log (~15 min of hub traffic past S2's divert) will
     be. I'll add the test that S2's parcel is the only stalled row in it as soon as it exists.
2. **H5 wording.**
   - "CAM_19 **saw it at** the exception store (inside the cage + bag store) at …". The UI never says "confirmed it
     in", and the backend statement says "saw it at" too.
   - Z11's display name is "Exception store" (the sign) everywhere.
   - The fixture uses **D07** for RC-864, per the S2 card, instead of D08.
3. **Search order.**
   - Machines get their own plan area kind (sorter loop, tunnel, reject; from hub_spec `kind: machine`). They go last,
     with "inside a running machine: stop the line to check".
   - The searchable places are ranked by a score: share still possible × 1.6 if no camera covers the place × 1.3 for the
     store / blind corner, + 0.15 where it was last confirmed. Ties go to walking distance.
   - The search task uses the same order.
   - The plan was re-imported as a new version (`--sync-geometry`).
   - On the default case the exception store is still low. Its share is only 7 %: the case ends 15 s after the divert,
     and at 1.8 m/s most of the store is out of reach. With S2's 90 s window it becomes reachable, and the blind-store
     weighting puts it first.
4. **Camera grid.** It now fills up to 4 tiles: cameras with footage first, then the plan's other cameras around the
   break point as quiet tiles reading "no footage imported for this camera", so the gap is visible.
5. **Fixture outcome time** is 15:10 MYT, after the event.
6. **Reel "two title cards":** the manifest has one title card (7 cards total). The contact sheet sampled every 1.2 s
   and the title lasts 2.5 s, so it appeared twice in the sheet.
7. **Seam:** checked in the new `34_h15_hub_home.png` full page. The sidebar is the same colour as the rail band.

## 2. Check these
- `frontend/review_pack/{desktop,mobile}/`:
  - `34_h15_hub_home.png`
  - `34b_h15_inbox_plus_30_min.png`
  - `36_h11_camera_moment.png`
  - `fx_35b_h5_records_vs_video_conflict.png`
  - `fx_37_h12_search_checklist.png`
- **Code:**
  - `backend/src/spoor/forensics/exceptions.py` (`_kept_working`, `_next_station`)
  - `backend/src/spoor/forensics/possible.py` (`searchable_score`)
  - `frontend/scripts/site_plan.py` (machine kind)
- **Tests:** backend forensics 19 ✓; review specs 14/14 ✓.
