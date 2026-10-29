# Step 11 — Optional extensions (only after the core works)

**PRD:** §5.4, §13.4, §14.3, §20 · **Depends on:** 03, 05 (and a working core)

Each extension is feature-flagged and off by default. If one fails its gate, disable it — the core 2.5D product must
still work (§13.4.5).

## 11a — Sensor fusion (M9, §20)

- Vendor-neutral `SensorEvent`; CSV import first (MQTT later).
- `door_contact`, `weight_delta_kg`, `rfid_tag_seen`, `motion_trigger`.
- Simulated logs labelled `sensor_simulated` at source and in every output 🔒.
- Door open ≠ who; weight drop ≠ what. Contradictions surfaced, not resolved by trust.

## 11b — Cross-camera association (§14.3)

- Tracklets per camera → candidate links gated by time feasibility, topology, negative constraints.
- Object (not person) appearance embeddings from an evaluated, licence-checked encoder — only if it runs on the local
  CPU affordably (no GPU available on this machine).
- Hungarian matching after hard gates; labels `verified_same_camera | candidate_cross_camera | rejected | unresolved`.
- Compare appearance-only vs time+topology vs combined; thresholds chosen on validation footage only.
- No biometric or face-based person linking 🔒.

## 11c — Multi-view true XYZ (§13.4)

- Preconditions (all 🔒): overlapping synchronized views, full `K`, distortion, `(R,t)`, metric scale, verified
  same-point correspondence, stable cameras.
- ChArUco intrinsics → joint extrinsics → time calibration → held-out landmark validation.
- `cv2.undistortPoints` + `cv2.triangulatePoints`; reject cheirality failures, near-parallel rays, high residuals.
- Monte Carlo uncertainty ellipsoid; `spatial_mode=multiview_xyz`.
- Gate: only shown in product after quantitative validation; otherwise disabled.

## 11d — Model experiments

- Muse Wonder on hard cases only if a measured benefit justifies cost.
- Muse Glimmer local — **likely not feasible** on this machine (no NVIDIA GPU detected); record if skipped.

## Status — code done (2026-10-27), all flags off

- 11a `spoor/sensors.py`: CSV import; every row must say `real` or `simulated`.
- 11b `spoor/association.py`: hard gates (time overlap, topology travel time, speed, appearance) -> Hungarian
  assignment -> `candidate_cross_camera` / `unresolved` (ambiguity margin) / `rejected`. No encoder bundled.
- 11c `spoor/spatial/multiview.py`: undistort -> normalized triangulation -> cheirality, ray angle, reprojection,
  workspace and time-offset gates -> Monte Carlo 95% uncertainty. Synthetic tests only; no real rig yet.
- 11d: Muse Glimmer not attempted (no NVIDIA GPU on this machine). Muse Wonder not used.
