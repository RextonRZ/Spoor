# Step 03 — Site, cameras & floor calibration (M2)

**PRD:** §13.1–13.3, §13.5, §8.3 · **Depends on:** 01 · **Package:** `packages/spatial`

## Goal

Map a visible floor-contact point in a camera image to metres on the site floor, with a **measured** error — or
honestly fall back to zone-level / image-only.

## Build

1. **Site model:** metric frame (X right/east, Y forward/north, Z up, metres), `floor_id`, named zones as polygons
   (shelf, desk, door, walkway) with stable `zone_id`s. Loaded from a versioned JSON file.
2. **Camera record:** position, orientation/FOV estimate (marked measured vs approximate), resolution, validity
   period, FOV polygon on the floor.
3. **Homography calibration:** ≥4 non-collinear floor correspondences `(u,v)↔(x,y)`; `cv2.findHomography(…, RANSAC)`;
   optional undistort first if lens distortion is noticeable.
4. **Holdout validation:** separate validation points → error in metres (median, p95). Calibration gets
   `RigState=validated_floor_only` only if it passes a threshold chosen on validation data, not on the demo.
5. **Projection:** `project_floor_contact(camera_id, u, v)` → `SpatialEstimate` with `floor_xy_m`,
   `uncertainty_radius_m`, `calibration_id`, `spatial_mode=floor_xy`. Reject points outside floor/site.
6. **Anchor for non-floor objects:** item on a shelf → `anchored_height` using the known shelf zone; item carried →
   hypothesized relation to a person floor track, never an independent position (§13.2 step 6).
7. **Fallback chain** (§13.4.4): `floor_xy` → `zone_only` → `image_only` → `unknown`.
8. **Clock sync record:** per-camera offset + uncertainty + method; never assume synchronous feeds (§8.3).
9. **Site → renderer transform** (Z-up → Y-up) as a pure, unit-tested function for the future frontend (§13.5).
10. Calibration invalidation: new version on camera move/zoom; dependent estimates marked stale (§16.4).

## Done when

- Synthetic test: known homography + noise → recovered error within expected bounds; collinear input rejected.
- Real test (once room is measured): holdout median/p95 error recorded in `docs/CALIBRATION.md`.
- Out-of-floor projection returns `zone_only`/`unknown`, never a fabricated XY.

## Owner input needed

Room measurements (metres), landmark positions on the floor, camera mounting positions.

## Status — code done (2026-10-27); real-room validation pending

Code: `backend/src/spoor/spatial/` (`homography`, `projection`, `frames`, `clock`). Tests: `backend/tests/test_spatial.py`
using a synthetic pinhole camera with known pose.

- `fit_floor_calibration`: RANSAC homography, rejects <4 / collinear / clustered points, computes held-out error;
  becomes `validated_floor_only` only when held-out median/p95 meet thresholds **passed in by the caller**.
- `project_observation` fallback chain: `floor_xy` → `anchored_height` (measured surface via operator image region)
  → `zone_only` → `image_only`. Uncertainty radius = hypot(held-out p95, local px→m stretch × pixel σ), so it grows
  with distance from the camera. Overlapping zone regions → no guess. Points outside the camera frame, beyond the
  horizon, or outside the room → `image_only`.
- Site Z-up → renderer Y-up transform is a proper rotation (det +1), tested.
- Clock sync from a shared visible event; ordering of two frames is `None` (undetermined) inside combined uncertainty.
- Procedure for the real room: `docs/CALIBRATION.md`.
