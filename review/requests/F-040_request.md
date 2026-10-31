# F-040 — F-039 P2s: zone labels under chips, phone card height, 3D camera pins

From the frontend agent.

## 1. Changed since last request
- **P2 #1, zone labels under chips** (`HubPlan.tsx`, `useChipKnockout`).
  - After each render, any zone label whose box intersects a time chip is hidden whole. This covers the zone names
    and codes, plus "Cross-belt sorter" and its speed line.
  - Labels come back when the chip moves away.
- **P2 #2, phone card height.** The scene pane carries `data-view`.
  - On screens up to 1100 px wide, the 2D plan pane sizes to its content, so the card ends at the legend.
  - The 3D stage keeps its fixed 68vh.
- **P2 #3, 3D camera pins "in the yard": checked against `hub_spec.json`.**
  - Only **CAM_17 "YARD NORTH" (22.0, 40.4)** is outside the building, by design.
  - The others near the top are inside, mounted along the north side: CAM_02 at y = 31.5, CAM_13/15/16 at y = 31,
    CAM_19 at y = 29.
  - The 3D camera looks from the south, so a pin mounted about 6 m up projects above the 3 m cut-away north wall.
  - Fix: every camera now has a faint drop line to its floor point, indigo for cameras in play. The floor position
    now reads correctly.

## 2. Check these
- `frontend/review_pack/mobile/30_h2_journey_inferred.png`: card ends at the legend; no label peeks out from under the
  chips.
- `frontend/review_pack/desktop/39_h13_scan_card.png`: no "Ex… Ch…" behind the Last-confirmed chip.
- `frontend/review_pack/desktop/38_h6_plan_built_3d.png`: drop lines.
- Tests: e2e + a11y 21/21 ✓; review H2/H13/H6 ✓ with the chip gate; typecheck and lint clean.

## 3. Questions
- None. Next I plan to start J3 (search grounding for the report's Malaysian context), while the S2 log fix is pending.
  Say if you'd rather I do J4 first.
