# Request 011 — Frontend: induction line B in the seed mapping, hub data and topology (B2_prereview_b)

From the frontend agent.

## 1. Changed since last request
I read `assets/hub/hub_spec.json` (regenerated 11:06). Nothing about line B is hard-coded beyond the scan-point ids
used for wording.
- **Hub data:** `npm run gen:hub` now gives 48 scan points, including SP-INDUCT-B and SP-TUNNEL-B, and the
  `induction_B` belt with its per-point `heights`. Everything that lists scan points or belts reads this data, so the
  new points appear everywhere with no code change:
  - 2D plan scan-point markers and belts;
  - 3D scan markers and labels;
  - timeline lanes;
  - the source panel's "cameras that see this read point" (SP-TUNNEL-B: CAM_07 and CAM_08; SP-INDUCT-B: CAM_07 and
    CAM_18).
- **Seed** (`frontend/scripts/seed_nokey.py`, also used by the evaluator):
  - `tunnel_read`, `tunnel_no_read` and `induct_to_carrier` now keep the record's own `scan_point` through `own_point()`.
    Before, they were hard-wired to SP-TUNNEL / SP-INDUCT, which would have filed every line-B read under line A.
  - Records without a scan point (older logs) still map to line A.
  - An unknown scan point raises an error instead of being silently filed under line A.
- **Default seeded case:** `auto_case_parcel()` now picks only from parcels inducted on line A. Line B draws its own
  parcel stream, so adding line-B traffic can't change the default case. I did not re-seed the running backend, so the
  existing case is unchanged.
- **Topology** (`frontend/src/lib/topology.ts`):
  - `feederChains()` derives the infeed lines from the site plan's belts: belts are joined end to start, and a chain
    counts if it ends on the loop. That gives line A (induction+tunnel_line+merge, merging at x 30) and line B
    (induction_B, merging at x 46.6). The collector belt is correctly not a feeder.
  - `routeLink()` routes a hypothesis from a point on either line along its own belt to its own merge, then round the
    loop or down a chute. A line-B route never passes line A's merge (unit-tested).
  - `surfaceHeight()` follows the belt heights, including line B's ramp through DWS arch B (1.0 → 1.5 m).
  - The 3D scene and the 2D plan pass the site plan's belts to both functions.
- **Scan wording** (`frontend/src/lib/scans.ts`): `inductionLine()` reads the line from the scan point. Titles read e.g.
  "label read at the scan tunnel (line B)", the carrier-assignment card says "at the line B merge", and the hub flow
  line reads "induction line A or B → … that line's scan tunnel → merge …".
- **Evidence graph:** its edges come only from stored records (batch → scan, camera → track, observation →
  hypothesis / finding). It has no topology edges and assumed no single induction path, so it is unchanged.
- **hub.glb not re-exported:** `build/hub_dressed.blend` is dated 11:05, which is before 11:30, so belt B is not in the
  3D model yet. The 2D plan already draws it.

## 2. Check these
- `frontend/src/lib/topology.ts`, `frontend/src/lib/scans.ts`, `frontend/scripts/seed_nokey.py` (`own_point`,
  `auto_case_parcel`), `frontend/src/data/hub.generated.json`.
- Tests:
  - 4 new unit tests in `frontend/tests/unit/geometry.test.ts`: feeder chains, the line-B route, the ramp height and
    the line wording.
  - New `test_seed_maps_induction_line_b_to_its_own_scan_points` in `backend/tests/test_evaluation.py`.
  - Results: frontend typecheck ✓, lint ✓, unit 20/20 ✓; e2e 16/17 on the full run + 1/1 on rerun (the "signature interaction" frame took more than 20 s to load while renders loaded the CPU; it passes alone in 7 s); backend pytest 217 ✓ from the root.

## 3. Known issues
- The current `events_scan_simulated*.jsonl` files have no line-B records yet (0 SP-TUNNEL-B / SP-INDUCT-B rows as of
  11:12), so the mapping is tested on fixture records, not on the rebuilt log. After your rebuild:
  `npm run seed -- --scenarios …` and the evaluator pick line B up with no further change.
- hub.glb re-export waits for a `hub_dressed.blend` newer than 11:30 (`npm run export:hub`). Message me, or I'll check
  the timestamp on my next pass.

## 4. Questions
None.
