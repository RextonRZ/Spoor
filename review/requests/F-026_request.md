# F-026 — I4 possible locations + H4 "where it could be" cloud + H12 ranked places (first part)

From the frontend agent.

## 1. Changed since last request

### I4 — `GET /v1/cases/{id}/possible-locations[?t=]` (`backend/src/spoor/forensics/possible.py`)
- **Start:** the last confirmed point from the typed journey.
- **Reach on foot:** geodesic distance on the plan's 0.25 m walkability grid at the brisk 1.8 m/s. Racks, benches and belt
  decks block; walkways and crossovers don't. Anyone could have carried it.
- **Reach on conveyance:** forward belts at belt speed, only while it is still on a belt. A divert ends that, because the
  parcel drops into a chute.
- **Negative evidence:**
  - A camera removes its floor footprint, and blocks paths through it, only when all of these hold:
    - its clip was **analysed** for this case;
    - the clip covered the window;
    - it never confirmed the subject.
  - A clip with tracks in the window that aren't linked to the subject removes **nothing** ("identity open").
  - Unanalysed footage removes nothing, and the response says so: "negative evidence needs SAM tracking".
- **Output:**
  - polygons per time step (2, 5, 10, 20, 40, 60, 120, 300 s, up to the end of coverage / case window), with area, the
    cameras that removed area, and the cameras where identity is open;
  - **ranked places:** the zone holding the last confirmed point first, then the share still possible (places no camera
    covers weigh 1.5×), then walking distance. Each place has evidence for and against (e.g. "100 % still possible ·
    reachable on foot: 5 m · against: in view of CAM_06, CAM_08, footage not analysed for it yet").
- **Test (S2 in miniature):** the parcel is last confirmed inside a store, and the band between the store and the hall
  is watched by an analysed camera that never saw it.
  - Before analysis: the hall is reachable too, and the note says why.
  - After analysis: area ≤ 12.5 m², `removed_by_cameras = ["cam_door"]`, the store ranks first, and the hall share = 0.
- **Live no-key case:** 46 m² at +2 s → 234 m² at +5 s → 1,408 m² at +15 s. Chutes + bagging is flagged
  "last confirmed here".

### H4 — the cloud on the plan
- **Grey hatched area** with a dashed outline, drawn for the step at the playhead. It grows while the replay runs; none
  appears before the trail ends.
- **Tooltip:** "Could be here (computed): reachable within N s on foot, minus what CAM_x watched without seeing it. Not an
  observation."
- **Replay caption:** "Unknown since 14:32:31.8 MYT: no scan and no sighting after it · could be anywhere in the hatched
  234 m² (computed)".
- The legend entry "No coverage / could be here" already existed.

### H12 (first part) — "Where it might be · computed"
- The left column lists the top 3 places with their evidence for and against, plus the note when nothing is analysed.
- The summary's "Where it is" tile now reads "Not located. Computed places still possible: Chutes + bagging, then …".
- Still to come for H12: the search task + found / not-found outcome (I7), the mobile checklist and the walking route.

### Also
- Time chips on the plan are clamped inside the plan even when every candidate spot collides, so no chip is clipped.

## 2. Check these
- `frontend/review_pack/{desktop,mobile}/30b_h2_journey_unknown_after_last.png`: cloud + caption + ranked places.
- `frontend/review_pack/{desktop,mobile}/33_h14_case_summary.png`: tile 3 with computed places.
- `backend/src/spoor/forensics/possible.py`, `backend/tests/test_forensics.py::test_possible_area_collapses_into_the_store_when_its_only_exit_was_watched`
- Tests: backend pytest **232 ✓**; frontend typecheck ✓, lint ✓, review specs 8/8 ✓.

## 3. Known issues
- In no-key mode the cloud only grows: nothing is analysed, so no camera can remove area. S2 + one keyed SAM pass is
  what makes it collapse into Z11.
- Footprints come from the mounting plan (no occlusion), clipped by the plan's blind spot.

## 4. Next (queue order)
- I6 records-vs-video conflicts → H5
- I5 synced grid → H11
- I7 search task → H12 rest
- I8 reel → H7
- H6 plan-built 3D
- H13 scan cards
