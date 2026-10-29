# Calibration procedure (floor homography, PRD §13.2)

What you need: a tape measure, masking tape, each fixed camera recording at its final position and zoom.

## 1. Site frame

1. Pick an origin in a room corner. **X** runs along one wall (east/right), **Y** along the other (north/forward),
   **Z** up. Units: metres.
2. Measure the room outline and each zone (shelf, desk, door, walkway) as polygons on the floor. Record shelf/desk
   surface heights. Note the method and expected error (e.g. "tape, ±2 cm").
3. Write `demo/site.json` (a `Site` record — schema in `backend/schemas/Site.schema.json`).

## 2. Floor landmarks per camera

1. Put **10+ tape crosses on the floor**, spread across the whole area each camera sees (near, far, left, right). Not
   in a line. Floor only — never shelf tops or walls in the same fit.
2. Measure each cross's `(x, y)` in the site frame.
3. Grab a frame from the camera, and click each cross's pixel `(u, v)`.
4. Split: ~6 for fitting, **the rest held out** for validation. Choose held-out points across the area, not one corner.

## 3. Fit and validate

Thresholds are decided **before** looking at the result, from what the investigation needs (e.g. "which zone?" needs
roughly ≤ 0.25 m median / ≤ 0.5 m p95). Record them here.

```python
from spoor.spatial import fit_floor_calibration, ValidationThresholds
cal = fit_floor_calibration(..., thresholds=ValidationThresholds(max_median_m=..., max_p95_m=...))
print(cal.rig_state, cal.holdout_error_median_m, cal.holdout_error_p95_m, cal.notes)
```

If the lens is visibly fisheye (straight floor lines look curved), calibrate/undistort first (step 11c) or expect worse
error near the image edges.

## 4. Zone image regions (off-floor items)

For each shelf/desk surface visible to a camera, draw its outline in image pixels → `Camera.zone_image_regions_px`.
Items there are placed as `anchored_height` (coarse), never floor-projected.

## 5. Invalidation

Camera bumped, moved, zoomed, re-mounted, or resolution changed → record an invalidation and re-calibrate. Old
calibration and its estimates are kept but marked stale.

## Results log

| Date | Camera | Fit pts | Held-out pts | Median (m) | p95 (m) | Thresholds | State | Notes |
|---|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | — | not yet measured |
