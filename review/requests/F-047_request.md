# F-047 — Flow screen 3: Answer (Case.dc.html), plus the F-046 fixes

From the frontend agent.

## 1. Changed since last request
- **F-046 fixes (Investigating):**
  1. Unavailable tools are quiet grey with the reason in the tooltip. No strike-through.
  2. The hero shows the floor plan pinned at the camera being checked, or where the parcel stopped. No bracketed
     text.
  3. Plain words, said once: "The AI planner isn't connected in this demo mode, so the plan comes from the floor
     plan and belt routes." Later AI steps say "Skipped: the AI tracker isn't connected in this demo mode." No "model
     key" wording.
     - Camera steps say "CAM 11: no footage for this camera yet."
     - Test updated: `test_run.py`.
  4. The keyed run is noted for when S2 footage is imported.
  5. Mobile: the search map stacks to one column, with the log and crew below. See `mobile_02_investigating.png`.
- **Answer = `/cases/{id}`**, ported from `Case.dc.html`. It **replaces the old workspace page**, which is deleted
  (the old UI is in git history).
  - **Case bar** (shared `components/flow/CaseSteps.tsx`): "Hub › CTX… · customer says it never arrived" and the
    numbered steps **1 Answer · 2 Proof · 3 Go look · 4 Report**.
  - **Left column:**
    - the status pill (Lost track / Likely location found / Found);
    - the 40 px one-sentence answer: "Lost track after chute C12 at 14:11:12.";
    - the plain explanation;
    - **How sure: low / medium / high**, with three reasons from the read models: last scan (green dot); cameras
      that would show it next and their footage state (grey); the **records conflict** (red dot: "The sorter's own
      times don't fit the belt: recorded 21.7 s, but the belt route needs 25.9 s").
  - **Watch the proof** (primary, to `/proof`) and **Send someone to look** (to `/search`).
  - **Right column:** the last confirmed frame when footage exists; until then, the plan pinned where it stopped,
    with its route, captioned "Where it stopped · chute C12 · 14:11:12 · no footage yet".
  - **Moments in order:** each scan ("Label read at the tunnel", "On the sorter", "Into chute C12"), the **records
    conflict as the red dashed tile** at its own time, and the end state: green "Found by floor staff", or dashed
    "Not seen since".
  - The old `/cases/{id}/summary` is deleted; Answer replaces it.

## 2. Check these
- `frontend/review_pack/flow/desktop_03_answer.png` and `mobile_03_answer.png`
- `frontend/review_pack/flow/desktop_02_investigating.png` and `mobile_02_investigating.png` (fixes)
- The Case prototype renders; the side-by-side image is coming with Proof.
- Tests: backend `test_run` ✓; typecheck and lint clean.

## 3. Question
- The S2 case **has a real records conflict** (sorter timing). Should the Hub row's pill say **"Records disagree"**
  (as in the prototype) instead of "Lost track" whenever a case has a records conflict? I'd do it; say if not.

## 4. Next
Proof (Video | 3D hub), then Go look, Report, Cameras.
