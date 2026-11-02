# Limitations and claims not made

Current as of Mon 2 Nov 2026. The deadline is Thu 5 Nov, 10:00 MYT.

## What the evidence is

- **Synthetic footage, simulated scan log.** Everything was measured on a fictional hub rendered in Blender (with
  mocap workers) and a simulated scan log. No real hub, real CCTV or real courier records were used. Real footage
  (compression, lighting, crowds) will be harder.
- **One main scenario.** The S2 case and three control parcels on the same 90 s of footage, plus two short story
  windows (W1 the parcel's arrival and sorting, W2 its cage). Numbers in EVALUATION.md are from these, not from a
  benchmark.
- **The story parcel's unload scan carries no number.** Other parcels were scanned at the same door within the
  close-up camera's clock uncertainty ("Three cartons scanned here within 1.0 s"), so it is shown as the scan record.
  Busy doors fall back to "can't tell" by design. (Spacing the demo's unload door is a decision waiting for Rexton.)

## Design limits

- **A number goes on an outline only when the rule rules out a neighbour.** Against the render truth all 51 numbers
  shown are right, but only 63 % of the right outlines carry one: tunnel exits are never labelled on CCTV (the
  tunnel's own photo identifies the parcel instead), busy handheld points and cameras whose clocks are not fitted are
  shown as scan records.
- **Camera clocks must be fitted to the sorter** (from sorter events or overlap with a fitted camera). CHK_UNLOAD,
  CHK_CHUTE, CHK_CAGE_W and CHK_STORE see no sorter events and stay at the uploader's declared time (+-5 s); that
  limits what they can label.
- **SAM's follow is shown only up to the scan instant.** After a divert, SAM's propagation can latch onto the empty
  tray once the carton has gone down the chute (seen in the truth check).
- **No camera sees inside the exception store.** "Most likely inside" rests on the verified door evidence (carried
  in, came out empty-handed, nobody carried it out before the recording ends) and assumes the door is the only way in;
  the answer says so and sends a person to look.
- **Cross-camera identity is by place and time**, never by appearance or by person. A likely carrier is "a link by
  place and time, never an identity".
- **Live alert covers open containers only** (cages, pallets, gaylords): a carton inside a closed bag cannot be seen
  leaving as a carton.
- **Jobs run in the API process.** Long SAM jobs slow the API while they run; restarting loses in-flight jobs (results
  already stored are kept). Auth is a token file, not an identity provider.

## Claims Spoor never makes

Identity of any person, intent, guilt, theft, emotion or personal attributes; that a 3D view or a generated sentence is
evidence; that hashes alone establish legal chain of custody; courtroom admissibility.
