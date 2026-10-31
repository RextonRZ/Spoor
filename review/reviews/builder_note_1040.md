# Builder note (10:40 Sat) — P0 geometry mismatch (see F-047_to_F-051_review.md)
The app's site plan comes from `assets/hub/hub_spec.json` (line A layout "a"); S2 runs on layout "b"
(`hub_spec_lineAb.json`). SP-INDUCT is at (12.0, 9.5) in both, but in layout b the carrier load is at the loop merge.
Result: a false "sorter times don't fit the belt" (21.7 s recorded vs 25.9 s planned) on S2's subject.
Please: make ONE canonical spec for the rendered layout (b) — scan point positions, conveyor paths, belt routes, the
induct/merge order — and say its path in your next request so the frontend can seed from it. Add a check that every
scenario's consecutive scans fit the canonical belt routes (± clock tolerance) unless the scenario truth says the
conflict is designed.
