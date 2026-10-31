# OWNER CONFIRMED (Rexton, 02:59–03:03 Sat): these ideas are now part of Spoor — BOTH agents read

Builds on `floorplan_design_0300.md` (floor plan, journey fixes, H15 exceptions inbox, masking, logo hold).

## 1. 3D view = the whole hub as a twin (frontend; builder supplies the model)
- 2D stays the working screen. 3D is the wow shot for the video and the "3D" tab.
- Shows: the whole hub, zone name labels, the parcel trail (same evidence styles as 2D), camera view cones for
  cameras in play, and the "could be here" area as a soft volume. Not seen = dotted, never solid.
- Frontend: build it from `hub.glb` + the site plan; labels come from the plan, not hand-placed.
- Builder: keep `hub.glb` export clean for this — named nodes per zone/machine, no people, no flow parcels,
  light enough to load fast in the browser (poster frame while loading). Say what you change in your next request.

## 2. Deployment story: "Scan once, then the cameras keep it live" (frontend: docs + pitch only)
- Day one: a floor plan is enough. Upgrade: a one-time 3D scan of the real building (phone LiDAR for small
  areas; laser scanner such as Leica BLK360 / Matterport Pro3 / a walk-through scanner such as NavVis for a whole
  hub; or Gaussian splatting from a walk-through video).
- "Live" comes from CCTV + the scan log + conveyor/PLC status laid on the static model (a digital twin), never from
  re-scanning. Add this to the deployment section of the README / docs. No code needed for the scanning part.

## 3. Camera strip on the journey screen (frontend)
- Cameras in route order; each tile = parcel crop highlighted (SAM mask) / "expected here, not seen" /
  "not analysed". The gap must be obvious at a glance. (H10, built on F-023 crops.)

## 4. People: "Spoor watches parcels, not people" (both)
- Default views (2D, 3D, dashboard): no people at all.
- Case replay only: a person who handled the parcel appears as a small grey anonymous marker ("Person A") for
  those seconds only. No faces, no names, no realistic avatars, never every worker live on the map.
- Handheld scan events may carry the scanner user ID: masked by default; a supervisor reveals it with a typed
  reason, and the reveal is logged. No face recognition. Never the word "suspect".
- Builder: ground-truth person tracks stay anonymous ids (Person A/B); no worker names anywhere in exports.

## 5. Already in floorplan_design_0300 (now confirmed as project scope)
- H15 = exceptions inbox: stalled-scan alerts from the scan log + tracking-number search + KPIs.
- Personal data: store tracking number, size, weight, route only; mask anything else.

Order for the frontend: F-style fixes → floorplan_design_0300 → I1/H10 camera strip → H14 → 3D twin view.
Order for the builder: unchanged (021 fix → 021b → RC-864 …); the hub.glb cleanup comes after S2 render.

## 6. Video: twin <-> real transition (Rexton 03:07) — AFTER the S2 render, not now
- Shot (~15 s, video 2:25-2:40): app 3D tab orbits the hub -> cross-dissolve on the SAME camera path into the
  realistic Blender render (workers, belts moving, SYNTHETIC burned in) -> dissolve back to the 3D tab.
- Builder: define one 8-10 s camera path, export it as JSON (position, look-at, fov per frame, metres in the hub
  frame), render it at best quality when Modal is set up (within the render-test cap).
- Frontend: a hidden replay mode in the 3D tab that plays the same JSON path so the screen recording lines up
  frame for frame.
