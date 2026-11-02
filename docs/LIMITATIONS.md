# Limitations and claims not made

Current as of Mon 2 Nov 2026. The deadline is Thu 5 Nov, 10:00 MYT.

## What the evidence is

- **Synthetic footage, simulated scan log.** Everything was measured on a fictional hub rendered in Blender (with
  mocap workers) and a simulated scan log. No real hub, real CCTV or real courier records were used. Real footage
  (compression, lighting, crowds) will be harder.
- **One main scenario.** The S2 case and three control parcels on the same 90 s of footage, plus two short story
  windows (W1 the parcel's arrival and sorting, W2 its cage). Numbers in EVALUATION.md are from these, not from a
  benchmark.
- **The story window's unload door was re-staged.** At first, other parcels were scanned at the same door within the
  close-up's clock uncertainty, so the story parcel's unload scan could only be shown as the scan record. On Rexton's
  call (2 Nov) the W1 sim was re-baked with a quiet door: nothing else is set down there within 10.5 s of the story
  carton (its unloader waits; the mate stands idle about 35 s), W1's start was re-pinned so the carton is set down at
  its logged scan time, and five synthetic history lines at that door were re-timed to the re-baked door's real
  set-downs, as `incorrect_data` correction events (`frontend/scripts/retime_w1_door.py`; originals kept, the story
  parcel's own line unchanged). A real busy door still falls back to "can't tell" by design.

## Design limits

- **A number goes on an outline only when the rule rules out a neighbour, and the outline is carton-sized.** Against
  the render truth all 13 numbers shown are on the right parcel (12 carton-sized, 1 a flat bag at 2.55x), but only
  17 % of the right outlines carry one: divert outlines must slide into the chute (a tray rides the loop), tunnel exits
  are never labelled on CCTV (the tunnel's own photo identifies the parcel instead), and busy handheld points and
  cameras whose clocks are not fitted are shown as scan records. The chute-slide threshold was set on the S2 window;
  there is no held-out window.
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
