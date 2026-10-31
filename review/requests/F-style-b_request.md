# F-style-b — F-style fixes 1–13 + floorplan_design_0300 (plan language, journey layout, hub home, exceptions inbox)

From the frontend agent. All shots are style v2 at 1440×900 (viewport + full page) and 390×844. The logo is untouched
and on hold, in its single brand slot.

## 1. Changed since F-style (fixes by number)

### Hub dashboard (H15) → its own home page
1. **Done:** `/hub` is now the first item in the nav ("Hub"); the Operator page no longer carries the dashboard.
   **Not done yet:** moving Operator's imports / cameras / eval into tabs. That page is otherwise unchanged.
2. **Exceptions inbox + search.**
   - **New backend route:** `GET /v1/sites/{id}/exceptions` (`forensics/exceptions.py`, tested).
     - A parcel is "stalled" when its next expected scan is overdue. The allowance depends on the last scan kind:
       - tunnel → carrier: 30 s;
       - carrier → divert: 3 loops of 35 s;
       - divert → bagging: 20 min;
       - container → loading: 2 h.
     - Time is measured **on the log's own clock** ("as of the last imported scan"), so the synthetic log isn't judged
       against today's date.
     - Each row links to an open case, or offers "Open a case".
   - **Today's log:** 42 parcels, 0 stalled. The log is a 30 s slice, so every parcel is still inside its allowance,
     and the inbox says exactly that.
   - **Tracking-number search at the top:** it opens the case summary when a case exists; otherwise it shows the scan
     count and an "Open a case" button.
3. **Map in the new floor-plan language,** with zone tint + "1 case ends here · Z06" on the zone and human names.
4. **KPIs:** an em dash plus the reason underneath; no "none" as a numeral.

### Case journey workspace
5. **Re-shot after load.**
   - 3D is no longer the default; the 2D plan is.
   - The hero opens on the camera frame at the last confirmed moment.
6. **Same answer, same words everywhere.**
   - The left column's "Last confirmed", "Unknown" and "Next action" now come from the same journey and missing-moment
     fields as the summary:
     - "Last confirmed at chute C04 · 14:32:31.8 MYT";
     - "Review CAM_07 and CAM_10 from 14:32:31 to 14:32:34 MYT".
   - No raw ids. Unknown is 2–3 plain sentences, and the broken "• •" bullet is gone.
7. **Legend matches the map.**
   - The old left-column legend is removed.
   - The plan carries its own legend under it: inferred is dotted in both the map and the legend.
8. **Layout (floorplan_design §2):**
   - CCTV is the hero (centre): the follow-cam on top when a sighting exists, then the original frame.
   - The plan moves to the right.
   - The **camera route strip** sits under the hero. Its tiles, in time order:
     - a frame at each scan's time from the camera watching that read point;
     - the "expected here" cameras with a dashed box;
     - a grey "no camera" tile after the trail ends.
   - Arrows between tiles read "+4.7 s · belt".
   - The **timeline is fully visible at 1440×900** (the grid is pinned to the viewport; long columns scroll inside).
   - There is no empty right third.

### Case summary (H14)
9. **Headline:** "Last confirmed at chute C04 · 14:32:31.8 MYT". Sub-line: "Where it went next isn't shown yet: CAM_07 and
   CAM_10 haven't been analysed." The full sentence is kept for screen readers.
10. **The dashed box is drawn** (2 px with a dark halo, minimum size), and the claim stands.
11. **Tile 2 shows the predicted window,** e.g. "expected 14:32:31.8–14:32:34.8 MYT".
12. **The route map uses the new plan component.**

### All pages
13. **The background seam is gone.** The page gradients no longer use `background-attachment: fixed`, and the html
    background is the canvas colour.

### floorplan_design_0300 §1: the plan language (`frontend/src/components/plan/HubPlan.tsx`)
- **Ported from your reference generator:**
  - thick walls with real openings and dock numbers 01–12 outside the wall, door swings, columns, truck yards hatched;
  - belts as strips with flow chevrons; the sorter as a stadium with carrier ticks and its caption; chutes as
    trapezoids 01–12 + R; scan tunnel box; crossovers dashed;
  - forklift lane and zebra crossings;
  - the blind spot hatched with "No camera coverage";
  - human zone names first, codes faint;
  - cameras dim, and indigo with a FOV wedge + label only when in play;
  - legend, scale bar, north arrow.
- **Sizing:** drawn at the panel's real pixel size, so text stays true px. Small zones drop their label on small plans,
  so names never collide.
- **Evidence:**
  - amber dotted along the belt;
  - blue diamond beads;
  - **last confirmed ring is blue for a scan and green only for a sighting** (honesty rule: no-key mode never draws
    green);
  - dashed "expected here" box: **red only for a typed negative observation**, grey when not analysed;
  - time chips with hairline leaders, placed greedily so they never sit on the route or on each other.
- **Supporting changes:** `hub.generated.json` now carries the forklift lane, zebras and crossovers
  (`scripts/gen-hub-data.mjs`). The old `FloorPlan2D` is no longer used by the workspace.

### Also fixed while doing this
- The hero's auto-open waits for the user. If they already went to Agent, it doesn't pull them back to Source. This was
  caught by the e2e agent test.

## 2. Check these
- **Style proofs:** `frontend/review_pack/style_v2/{desktop,mobile}_{workspace,summary,hub}.png`
- **Review pack (block H):** `frontend/review_pack/{desktop,mobile}/`
  - `30_h2_journey_inferred.png`
  - `30b_h2_journey_unknown_after_last.png`
  - `31_h10_missing_moment.png`
  - `fx_32_h1_followcam.png`
  - `33_h14_case_summary.png`
  - `34_h15_hub_home.png`
- **Code:**
  - `frontend/src/components/plan/HubPlan.tsx`
  - `frontend/src/components/workspace/CameraStrip.tsx`
  - `frontend/src/app/hub/page.tsx`
  - `frontend/src/app/cases/[caseId]/page.tsx` (layout)
  - `frontend/src/lib/journey.ts` (`answerParts`, `unknownSentences`)
  - `backend/src/spoor/forensics/exceptions.py`
- **Tests:**
  - frontend lint ✓, typecheck ✓, a11y 6/6 ✓, e2e 17/17 ✓ (agent test fixed by the auto-open guard), review specs 8/8;
  - the mobile H1 fixture shot is occasionally slow under load and passes on re-run;
  - backend 13 forensics tests ✓ (new: exceptions inbox).

## 3. Known issues
- Operator tabs (part of #1) are not done yet.
- The 3D twin view (owner_ideas §1) and the camera-path replay for the video come after the S2 render and hub.glb
  cleanup.
- People as anonymous markers (owner_ideas §4): there are no person tracks in no-key mode, so nothing is drawn. The rule
  is noted for when SAM person tracks exist.

## 4. Questions
1. Are you OK with the allowances above as the starting stalled rule (shown on screen as the rule), or does Rexton want
   one flat limit, e.g. 20 min?
