# Request 010 — Frontend: review 008 follow-ups (wall layout, re-shot 20)

From the frontend agent. (009 is reserved for the builder.)

## 1. Changed since last request
- **Q1, the hook layout.** The grid now adapts with no empty slots: 2 → 2×1, 3 → 3×1, 4 → 2×2, 5–6 → 3×2, 7–9 → 3×3
  (`wallColumns`, unit-tested). Scenario tiles keep the camera order from `case_input.json`.
  - Click a tile, or press Enter/Space on it, to enlarge it. It goes full width and the other tiles shrink to a strip
    underneath. Click it again or press Esc to restore. All tiles stay on the same wall clock.
  - New e2e test covers it.
  - The demo script now says: S2 with all of its cameras (6 → 3×2).
- **P2 #2.** `20_camera_wall.png` was re-shot from the top of the page as a full page, so the "Case footage · synthetic"
  header now shows. New `25_camera_wall_enlarged.png`.
- The builder's manifest now exists: `/wall?scenario=S2` reads "S2 · Removal into the blind spot (0/6 rendered)" and shows
  the complaint and "Renders not produced yet" with all 6 camera IDs (`21_camera_wall_no_renders.png`).

## 2. Check these
- `frontend/review_pack/desktop/20_camera_wall.png`, `25_camera_wall_enlarged.png`, `21_camera_wall_no_renders.png`
  (+ the same names under `mobile/`).
- `frontend/src/components/wall/CameraWall.tsx`, `frontend/src/components/wall/wall.css`, `frontend/src/lib/playback.ts`.
- Tests: typecheck ✓, lint ✓, unit 16/16 ✓, e2e wall/a11y/playback 4/4 ✓ (incl. the new enlarge test), `next build` ✓.

## 3. Known issues
- On phones (≤ 640 px), the grid is always 2 columns, so 5 or 7 cameras leave one empty slot there.
- The real S2 wall and the F1/F2 captures wait for the renders.

## 4. Questions
None.
