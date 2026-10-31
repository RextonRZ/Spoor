# F-038 — Operator tabs (F-style #1 rest) + DEMO_SCRIPT for the S2 journey

From the frontend agent.

## 1. Changed since last request
- **Operator page** (`frontend/src/app/operator/page.tsx`).
  - The model-backed-steps summary stays on top, then tabs: **Imports** (inbox clock + CCTV retrieval + scan log +
    simulated events) · **Cameras and clocks** · **Footage** (+ clock domains) · **Model calls** · **Evaluation**.
  - The page is no longer one 4,300 px scroll.
  - The review-pack evaluation shot opens the Evaluation tab first.
- **`docs/DEMO_SCRIPT.md`: walkthrough rewritten** around the S2 story, with time / click / screen / what it proves /
  no-key fallback / 🔑 for each step:
  1. Hub stalled inbox, with its proof;
  2. case summary;
  3. journey replay with the CCTV hero, strip and scan cards;
  4. missing moment + camera grid;
  5. the cloud collapsing to the exception store;
  6. records vs cameras;
  7. Wonder plan + agents with key frames;
  8. floor search on a phone → Found;
  9. evidence reel + report;
  10. plan-built 3D.
  - It says "never a fixture on camera", and the floor search outcome must be a real one.

## 2. Check these
- `frontend/review_pack/style_v2/desktop_operator_tabs.png`
- `docs/DEMO_SCRIPT.md` (Walkthrough section)
- Tests: frontend e2e 17/17 ✓, review-pack operator test ✓.

## 3. Questions
- When the S2 render lands, should I seed S2 as its own case right away (F1)? That is: the scenario manifest, its
  clips, its scan-log slice, and the complaint from `case_input.json`. I plan to; say if not.
