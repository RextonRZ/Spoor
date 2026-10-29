# Optional multi-view XYZ (PRD §13.4)

**Status: implemented and synthetic-tested; disabled (`ENABLE_MULTIVIEW_XYZ=false`); no real rig calibrated.**
The core product works without it.

## When it is allowed

All of: two+ cameras simultaneously seeing the same physical point; full intrinsics `K`, distortion and pose `(R,t)`
for each in the metric site frame (Z up, metres); measured scale; clock offset small enough for the object's speed;
a verified same-point correspondence (initially user-confirmed — SAM masks do not provide point correspondences);
rig state `validated_multiview_3d`.

## Convention (locked in `spoor/spatial/multiview.py`)

Pixels -> `cv2.undistortPoints` -> normalized coordinates -> `cv2.triangulatePoints` with `[R|t]` ->
divide by `w` -> site metres. Reprojection is checked in pixels with `cv2.projectPoints`. A test shows that feeding
distorted pixels into a pixel-projection solver biases the point by more than 10x the locked convention's error.

## Quality gates (each failure returns reasons, never a point)

time-offset × object speed ≤ 5 cm · finite homogeneous solution · cheirality (in front of both cameras) ·
ray angle ≥ 5° · reprojection ≤ 3 px per camera · inside the measured workspace.
Thresholds are defaults for tests; real thresholds must be chosen on held-out landmarks.

## Uncertainty

Monte Carlo over pixel noise (default σ = 1 px, 200 samples): reported as the 95th-percentile 3D deviation.

## Synthetic tests (PRD C11–C13)

Accurate recovery (< 1 mm on exact projections); wrong correspondence rejected by reprojection; near-parallel cameras
rejected; time offset with a moving object rejected; outside-workspace rejected.

## Still to do before enabling

ChArUco intrinsics per camera, joint extrinsics, held-out surveyed landmarks, measured error table, storage of rig
records and `MultiView3DEstimate` from the API.
