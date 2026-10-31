# F-032 — H6 plan-built 3D (deployment mode: no hub.glb)

From the frontend agent.

## 1. Changed since last request
- **3D view switch** (bottom-left of the 3D panel): **Synthetic hub model | Plan-built 3D**. Plan-built is the default.
  - Captions: "What a real hub gets on day one: extruded from its floor plan (walls, zones, conveyors at deck height,
    racks). No 3D model." / "The fictional hub's own model, used for the synthetic footage."
  - The panel header reads "3D · built from the site plan" or "3D · synthetic hub model".
- **`frontend/src/components/workspace/PlanScene3D.tsx`** is built only from `GET /v1/sites/{id}/plan` (I9 data):
  - floor;
  - walls cut away at 3 m so the inside stays visible;
  - zone tints with human names;
  - every conveyor as a deck at its **real deck height** per point (loop at 1.5 m, induction ramps, chutes);
  - racks and benches extruded to their heights;
  - each camera's mounting position with a heading tick.
- **Same evidence language as 2D:** amber dashed inferred route at deck height, blue scan beads, grey ring where the
  trail ends, and the computed "could be here" area (translucent) for the playhead's step.

## 2. Check these
- `frontend/review_pack/desktop/38_h6_plan_built_3d.png`
- `frontend/src/components/workspace/PlanScene3D.tsx`
- Typecheck ✓, lint ✓.

## 3. Known issues
- **Labels:** zone labels are DOM overlays. drei `Text` fetches a font at runtime and blanked the scene, so it's not
  used.
- **Default framing:** shows the centre of the hub; orbit to see the rest.
- **Not built yet** (owner_ideas §1, after the S2 render and the builder's hub.glb cleanup):
  - the full 3D twin, with camera cones for cameras in play and the cloud as a soft volume;
  - the camera-path replay for the video.
