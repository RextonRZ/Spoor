# F-028 — I6 records-vs-video conflicts (backend) + H5 two lanes (frontend)

From the frontend agent.

## 1. Changed since last request

### I6 — `GET /v1/cases/{id}/conflicts` (`backend/src/spoor/forensics/conflicts.py`)
- **A conflict needs two things:** a record that claims an ongoing place, and a confirmed sighting that contradicts it.
  - **custody:** the parcel is inside a container (a bag / cage membership from the scan log), the container's own
    scans put it in zone A, and a confirmed track shows the parcel in zone B after that. This is S3: bag vs floor.
  - **departure:** a loading / departure scan, either the parcel's own or one inherited through its bag → cage chain,
    says it left, but a confirmed track shows it inside the hub afterwards. This is S2 (cage "left on the truck" vs
    the exception store) and S4 (D08 vs D09).
  - **records_timing:** two scans faster than the belt route allows, taken from the journey.
- **Not a conflict:** a sighting after a plain scan. That is just movement.
- **Each conflict carries** its divergence time, the claim (time, zone, words, evidence ids: membership + container
  scan) and the observation (id, time, camera, zone).
- **No-key mode:** "no confirmed camera track yet: the video side is empty, which is not agreement (tracking needs SAM)".
- **Test (S2 in miniature):** the parcel is inside RC-864 (membership); the cage's loading scan at D08 (with a trailer
  parent) says it left; a human-confirmed track then shows the parcel in the hall. Result: one `departure` conflict at
  the sighting time, citing the load scan and the observation. Before the track exists, there is no conflict and the
  "not agreement" note shows.

### H5 — "What the records say vs what the cameras saw" (`frontend/src/components/RecordsVsVideo.tsx`)
- **Two lanes on one time axis:**
  - scan records: blue diamonds for scans, hollow diamonds for claims inherited through containers;
  - cameras: green bars for confirmed tracks, or a dashed "no confirmed track yet".
- **Each disagreement** gets a **red pin** across both lanes, plus one plain sentence built from the typed fields (MYT
  times, human zone names), e.g. "The records say it left the hub (RC-864 container loaded at SP-LOAD-D08, 14:32:35.0
  MYT); CAM_19 confirmed it in Cage + bag store at 14:32:38.0 MYT."
- **Shown on** the case summary (full width) and at the foot of the Missing moment tab.

## 2. Check these
- `frontend/review_pack/{desktop,mobile}/35_h5_records_vs_video.png`: real default case, no disagreement, empty video
  lane said as such.
- `frontend/review_pack/{desktop,mobile}/fx_35b_h5_records_vs_video_conflict.png`: **TEST FIXTURE banner**. Real
  records; the sighting and the conflict are route-mocked to show the pin.
- `backend/src/spoor/forensics/conflicts.py`,
  `backend/tests/test_forensics.py::test_records_say_it_left_on_the_truck_but_a_camera_confirms_it_inside`
- Tests: backend forensics 17 ✓; frontend typecheck ✓, review spec H5 ✓.

## 3. Known issues
- The default log has no container memberships for the case parcel (bagging scans aren't in the 30 s slice), so its
  records lane shows the three scans only. S2 / S3 / S4 carry the claims.

## 4. Next
- I5 synced camera grid → H11.
