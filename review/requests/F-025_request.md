# F-025 — F-024 fixes (stale camera poses, load-time wording, follow-cam placement, next-camera rows, image fade-in)

From the frontend agent. Builds on F-style-b (same session).

## 1. Fixed from F-024 review: 1, 2, 3, 4, 5, 6, 7

1. **Stale poses: confirmed and fixed.**
   - The backend's plan still had CAM_07 at (39, 5), while the spec now has (42.8, 4.0, 8.5 m), yaw 95. CAM_04 was at
     heading 160°; the spec now has 125°.
   - New `sync_geometry` in the seed (`seed_nokey.py --sync-geometry`) re-posts any camera whose mounting pose changed and
     imports a **new plan version** whenever the plan differs from `hub_spec.json`. It is idempotent: a second run
     reports 0 re-posed and "plan unchanged". It now runs on every seed.
   - Ran it: 19 camera records updated; current plan `plan_18e366dd22fa8284b18c56ba`. Old versions stay as history,
     and answers cite their `plan_id`.
   - **Test** `test_divert_c04_projects_inside_the_cameras_that_watch_it_with_current_poses`: the plan's CAM_07 and
     CAM_10 poses equal the hub spec, and the C04 divert point projects inside both frames with a valid expected box.
   - **Honest limits:**
     - The no-key clips are the old white-floor QA renders made **before** the re-aim, so boxes on those clips stay off.
       S2's renders use the current poses.
     - The box comes from the mounting-plan pinhole without the lens remap, so it stays labelled approximate. Once a
       floor calibration exists, the region should come from its homography instead.
2. **No wording flicker.** The left column renders "Last confirmed / Unknown / Next action" only from the loaded
   journey and missing moment (skeleton until then), using the same functions as the summary (`answerParts`,
   `unknownSentences`, `nextAction`). There are no raw ids.
3. **Follow-cam is docked in the CCTV hero,** above the original frame (F-style-b layout), so it never covers the route.
   - Outside a seen segment it is one quiet caption line.
   - Zoom is measured from the real width and capped at 4× native.
4. **Next-camera rows.**
   - Cameras predicted next without footage are now listed one row each: role, predicted window, how it was predicted,
     and "no footage in this case, so it cannot show where it went". On the default case these are CAM_11 / CAM_13
     (next on foot from the chutes) and CAM_14.
   - With footage, they get the full frame + dashed box + close-up rows as before.
5. **Images fade in** (180 ms) over a quiet placeholder: key frames, missing-moment frames and close-ups, strip tiles,
   follow-cam (`FadeImg`).
6. **Fixture re-shot** with the tighter crop; zoom is now within 2–4×.
7. **The "• •" bullet is gone.** Unknown is plain sentences.

## 2. Check these
- `frontend/review_pack/{desktop,mobile}/`:
  - `30_h2_journey_inferred.png`
  - `31_h10_missing_moment.png`
  - `fx_32_h1_followcam.png`
  - `33_h14_case_summary.png`
  - `34_h15_hub_home.png`
- `frontend/review_pack/journey_replay.mp4` (re-recorded)
- `frontend/scripts/seed_nokey.py` (`sync_geometry`, `_norm`, `_subset`)
- `backend/tests/test_forensics.py` (new projection test)
- `frontend/src/components/ui.tsx` (`FadeImg`), `frontend/src/components/workspace/MissingMoment.tsx`
- Tests: backend forensics 14 ✓; frontend typecheck ✓, lint ✓, review specs 8/8 ✓.

## 3. Known issues
- Expected boxes on the old QA clips: see #1.
- I4 / H4 ("where it could be" cloud) is next.
