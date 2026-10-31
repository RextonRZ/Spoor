# F-021 — Backend: I2 journey segments + I3 missing moment (+ the site plan they stand on, the data half of I9)

From the frontend agent. Note on numbering: my previous request was `020_request.md` (approved). From now on mine are
`F-NNN`, per frontend_restart_0118.md.

## 1. Changed since last request

### Site plan record (prerequisite for I2/I3/I4; also the data half of I9)
- **New contract `SitePlan`** (`backend/src/spoor/contracts/plan.py`, schema exported). It holds:
  - outline, areas (zones, walkways incl. belt crossovers, racks, benches, cage bays, the blind spot);
  - conveyors: centreline in travel direction, deck heights, belt speed, `feeds`;
  - doors, read points (with `event_positions` and `visible_by`), and the camera mounting plan.
  - Every value is declared with a `source`. It is versioned and immutable, and answers cite the `plan_id`.
- **Routes:** `POST /v1/sites/{id}/plan` (site admin) and `GET /v1/sites/{id}/plan`. The GET already returns walls,
  zones, doors, conveyors with heights, racks and camera poses, which is enough for H6's 2.5D view.
- **Seed:** `frontend/scripts/site_plan.py` converts `assets/hub/hub_spec.json` and imports it once.
  - **Belt speeds:** hub_spec only has the loop speed (2.0 m/s). The others come from the builder's conveyor design in
    `assets/hub/flow.py`: telescopic 0.8, collector 1.2, induction 1.5, tunnel 1.5, merge 1.8 m/s. I read that file
    and did not edit it. Chutes are gravity, so they have no stated speed.
  - **Event positions:** the `induct_to_carrier` event fires where the merge joins the loop, and a divert fires on the
    loop at the chute.
- **Check against the scan log:** the default case's real scans are 4.7 s apart (tunnel → carrier) and 19.2 s apart
  (carrier → divert C04). The plan routes give 8.23 m / 4.66 s and 38.45 m / 19.23 s. A test pins this.

### I2 — `GET /v1/cases/{id}/journey` (`backend/src/spoor/forensics/journey.py`)
The backend types every stretch of the journey. Each segment carries `evidence_ids`.
- **`observed`:** inside one camera track (the existing track segments, with points).
- **`inferred_along_conveyor`:** between two anchors (a scan, or the end of an observed segment).
  - Both anchors must snap to conveyance. Only fixed machines (tunnel, sorter PLC, DWS) snap; handheld scans never do.
  - The plan must have a forward route between them: belts never run backwards.
  - Fields: route (conveyor ids), path polyline, length, belt time, recorded gap, slack.
  - `timing` is one of:
    - `consistent`: same device clock, or synced clocks within tolerance;
    - `longer_than_belt`: may have waited or left the belt; said in the note;
    - `not_checkable`: different, unsynced clocks.
- **`gap`:** never bridged. It lists the cameras that were recording. Reasons:
  - `unobserved`;
  - `no_belt_route`;
  - `faster_than_belt`: the records conflict, so it is not drawn as a route;
  - `after_last_confirmed`: runs to the end of coverage or of the case window.
- **Also returned:** scan beads (position, device clock state, clock domain name, weight/dims) and `last_confirmed`.
- **No-key mode:** scans + inferred + gaps, and `needs` says observed segments need SAM.
- **Live no-key case today:** tunnel read → inferred (4.66 s belt vs 4.7 s recorded, consistent) → carrier → inferred
  (19.23 vs 19.2 s) → divert C04 → gap after the last confirmed point.

### I3 — `GET /v1/cases/{id}/missing-moment` (`backend/src/spoor/forensics/missing.py`)
- **Last confirmed point.** It carries its frames:
  - for an observation: the sighting frame;
  - for a scan: context frames from the cameras the plan says watch that read point, labelled as context.
- **Cameras that should come next, one row each, with a role:**
  - `watching_last_point`;
  - `belt_next`: timed samples along the forward belts at belt speed. A divert ends timed conveyance, because the
    parcel drops into a gravity chute;
  - `on_foot_next`: nearest three cameras by geodesic walking distance on a 0.25 m walkability grid. Racks, benches and
    belt decks block; walkways and crossovers do not. Times use 1.4 m/s typical and 1.8 m/s brisk (Fruin, cited in
    code).
- **Each row also gives:**
  - predicted time and window, with the clock tolerance;
  - expected floor point;
  - expected region in the image: from the mounting-plan pose, labelled "approximate: no lens model";
  - the original frame at the predicted time (signed link, SHA-256).
- **Result per row:**
  - `seen`;
  - `not_seen`: a typed `negative_observation` with media, coverage and the frame indices in the window. It is used
    only when the clip was analysed for this case;
  - `not_analysed`: needs SAM;
  - `no_footage`.
- **Live no-key case today:** the last point is the C04 divert. CAM_07 and CAM_10 watch it (`not_analysed`, frame 248).
  CAM_06 and CAM_08 also watch it but have no footage. CAM_11, CAM_13 and CAM_14 are on foot (no footage in this
  case).

### Other
- **Tests are now hermetic** (`tests/conftest.py`). Rexton's new `backend/.env` was being read by the test settings:
  `USERS_FILE` broke 8 tests, and worse, real keys could have reached tests. Tests now ignore `.env`. The `.env` file is
  untouched and was not read beyond confirming its key names.

## 2. Check these
- `backend/src/spoor/contracts/plan.py`, `backend/src/spoor/forensics/{conveyance,journey,floorgrid,viewgeom,missing}.py`
- `backend/tests/test_forensics.py`: 11 tests.
  - Route and belt time; belts never run backwards.
  - Inferred segments carry both scan ids.
  - Faster-than-belt scans become a gap, never a route.
  - Unsynced clocks give `not_checkable`; a long wait is flagged; handheld scans stay off conveyance.
  - After-last-confirmed gap with the recording cameras; observed segment + beads.
  - Hub plan vs scan-log timing.
  - Missing moment: belt-next predicted time, `not_analysed` → `not_seen` negative observation once the clip is
    analysed, `no_footage`, divert ends the belt, no-evidence case.
- `frontend/scripts/site_plan.py` (hub_spec → plan), `frontend/scripts/seed_nokey.py` (imports the plan once).
- Backend pytest: 228 ✓ (217 + 11 new).

## 3. Known issues
- **Camera footprints** are the mounting-plan floor footprint clipped to the building, minus the plan's blind spot. Racks
  and people do not occlude them. The plan's `visible_by` (the builder's raycast) is used where a read point has one.
- **Layout b:** line A geometry moves north in the builder's rebuild. I'll re-import the plan when hub_spec changes.
  hub.glb has the same dependency.
- **No screenshots in this request.** It is backend only; H1/H2/H10 will show these.

## 4. Questions
1. In no-key mode I include `inferred_along_conveyor` between two scans, alongside scans and gaps. It comes from scans +
   the plan, not from tracking. The H honesty rule says "no-key mode = scans + gaps only". I read that rule as "no
   fabricated tracks". OK to keep the belt inference (amber dotted, labelled), or strictly scans + gaps?
