# CCTV setup review (00:25 Sat, Rexton: "the CCTV setup is one importance of the project — can be the framework")
Checked: all 18 views (qa/b2/CAM_01..18) against hub_plan.svg.

## Fix now (part of the S2 perimeter item)
1. P0 **Z11 / BLIND_NW entrance** is only at the edge of CAM_01 / CAM_06 / CAM_13 (s2_perimeter crops). Give the
   entrance a camera that sees the doorway clearly, full height, from outside — re-aim C02 (it stands next to the store
   but looks SW at bag opening) or add C19 "STORE ENTRANCE". The inside stays blind (that is the point).
2. P1 **CAM_04 Induction**: the XO-2 stair and its rails fill the middle of the view and hide the induction line. Move or
   re-aim so the line A tables / induct belts are unobstructed (it is the pitch camera area).
3. P1 **CAM_07 Sorter mid**: the XO-1 crossover bridge runs straight through the centre. Shift the camera off its axis.
4. P2 Views that are mostly empty floor (CAM_03 lower half, CAM_14, CAM_16, CAM_18) are fine for exits/aisles, but tilt
   each so its subject (doors, staff exit, walkway) sits in the middle third, not the bottom edge.
5. P2 Plan advisory "cameras watch each other: FAIL" — real practice: at least the dock and exit cameras see another
   camera (tamper check). Cheap to fix with the re-aims above.

## Framework idea (proposal for Rexton; frontend + backend, after S2 render)
**Coverage-aware investigation + "Coverage advisor".** Spoor already knows every camera's cone, the blind zones and
the handoff overlaps (hub_spec cameras / blind_corner, FloorPlan2D). Make it a visible feature:
- In each case: the floor plan shows where the parcel could be during a gap (the reachable area between the last
  confirmed point and the next camera that would have seen it).
- "Next evidence" names the exact camera + time window (already the pattern).
- Operator page: **Coverage advisor** — for every gap across all cases, the single camera position/aim that would have
  closed it; ranked ("adding 1 camera at the Z11 doorway closes the gap in S2 and S3"). Honest: computed from cones and
  geometry, labelled as a suggestion.
