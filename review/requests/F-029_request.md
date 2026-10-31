# F-029 — I5 synced camera grid (backend) + H11 "the camera moment" (frontend)

From the frontend agent.

## 1. Changed since last request

### I5 — `GET /v1/cases/{id}/sync-grid[?cams=a,b&t=]`
- **Default cameras:** the 2–4 cameras around the break point, taken from the missing moment: the ones watching the
  last point, then the next ones with footage. With no `t`, it uses the last confirmed time.
- **Per camera:**
  - the original frame at `t`, placed by that camera's **own clock sync** (coverage start is already normalized;
    offset, drift, uncertainty and method are returned);
  - the coverage window;
  - the case object's boxes within ±0.6 s, with `subject: true` only for a linked track (human-confirmed,
    same-camera verified or scan-anchored); other tracks come back as `subject: false`;
  - the expected region from the missing moment.
- **Label:** "one instant on every camera … boxes only where a track exists".
- **Test:** added to `test_end_to_end_flow`. The grid for cam_a at T0 + 0.5 s gives frame 5, the clock uncertainty
  (50 ms), and the linked track's box flagged as the subject.

### H11 — "Cameras" tab in the CCTV hero (and a "Cameras" tab on mobile)
- 2–4 tiles in a synced grid, driven by **the one scrubber**: the timeline playhead (throttled to ~350 ms while
  scrubbing or replaying).
- **Boxes:**
  - solid green = the subject's confirmed track;
  - thin grey = something else tracked;
  - dashed = where it was expected (red only for a typed "not seen").
- **Each tile:** camera, result chip, frame number, and its clock note, e.g. "clock ±5.0 s, unverified".

## 2. Check these
- `frontend/review_pack/{desktop,mobile}/36_h11_camera_moment.png`: real no-key case, CAM_10 + CAM_07 at 14:32:31.8 MYT.
- `frontend/src/components/workspace/CameraGrid.tsx`, `backend/src/spoor/api/app.py` (`sync_grid`)
- Tests: backend e2e ✓; frontend typecheck ✓, review spec H11 ✓.

## 3. Known issues
- The dashed expected boxes are small on the old QA clips (approximate pinhole pose; see F-025 #1).

## 4. Next
- I7 search task + found / not-found outcome → H12 rest (mobile "go look here" checklist).
