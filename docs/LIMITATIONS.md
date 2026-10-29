# Limitations and claims not made

## Not yet validated (as of 2026-10-27)

- No live call to SAM 3.1, Muse Spark 1.3 or Baseten has been made. Adapters follow the official docs and are tested
  against fixtures in the documented formats; real behaviour (limits, latency, cost, output quirks) is unknown.
- No real footage, room measurement or calibration error exists yet. Calibration accuracy is unmeasured.
- No evaluation numbers exist. No accuracy, speed or cost claim should be made until `docs/EVALUATION.md` is filled.
- Postgres, Docker images and the Compose file have not been run.
- Muse Glimmer was not attempted (no NVIDIA GPU on the development machine).

## Design limits

- Floor homography maps only floor-contact points. Items on shelves get coarse `anchored_height` (zone centroid +
  zone radius); carried items have no independent position.
- A gap is a gap: Spoor never claims the route an object took while unobserved.
- "Left the room" is only supported by footage beyond the door. Door/weight sensors corroborate; they never prove.
- Cross-camera association has no appearance encoder yet; it relies on time, topology and geometry and abstains when
  ambiguous. Cross-camera links are never confirmed automatically.
- SAM object IDs are per video and unreliable across exit/re-entry or full occlusion (per Meta's docs).
- Multi-view XYZ is synthetic-tested only and off by default.
- Confidence is qualitative (observed / estimated / hypothesized / unknown); no calibrated probabilities.
- Jobs run in-process; restarting the API loses in-flight jobs (results already written to the store are kept).
- Auth is a token file, not an identity provider.
- Exit claims count a sighting "at the door" when it is inside the door zone or within its position uncertainty.
- Clips longer than 15,000 frames are split into chunks; an operator box prompt only covers its own chunk, and
  SAM tracks are not stitched across chunk boundaries (the boundary appears as a camera-internal hand-off).
- Continuity gaps scale with the source frame rate (≥ 2.5 frame intervals, minimum 500 ms).

## Claims Spoor never makes

Identity of any person, intent, guilt, theft, emotion or personal attributes; hidden faces or fingerprints; that a
3D animation is evidence; that hashes alone establish legal chain of custody; courtroom admissibility.
