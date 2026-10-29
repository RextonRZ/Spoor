# Review 002 + 003 + 004 — Frontend block C (combined)

Verdict: **APPROVED WITH FIXES.** This is strong work: honest no-key states everywhere, provenance inline, context frames
labelled "not an observation", the fixture banner on every mocked image, truth-file guards in the seed and the smoke test,
operator page with no control that sets an answer. Matches PRD §19/§23. Checked: 16 desktop + 4 mobile shots,
a frame sheet of `signature_interaction.mp4` (every 2 s), `events_scan_simulated.jsonl`, the seed/gen scripts.

## Fixes
| # | Where | Problem | Required fix | P |
|---|---|---|---|---|
| 1 | Source panel "Proves" text + Last confirmed card | For `divert_confirm` at SP-DIV-C03 it says *"the parcel ID was read at this read point"*. A divert confirm is not a label read: the sorter PLC reports that the carrier holding the tracked item tipped at chute C03 (often + a chute photo-eye). Identity there is **carried by sorter tracking from the induction/tunnel read**, not re-read | Event-kind-specific wording. `tunnel_read`: "label read at the tunnel". `induct_to_carrier`: "sorter assigned the tracked item to carrier N". `divert_confirm`: "sorter reports carrier N discharged at chute C03; identity from sorter tracking, not a new read". Card title "Observed: sorter divert confirmation" (keep the backend label, change the source-type words). Same for timeline tooltips and report text | P0 |
| 2 | Event names | "inducted" is shown for `induct_to_carrier`, and it appears *after* "tunnel read" — reads like a time-travel bug to a judge. In this hub the tunnel is on the infeed line before the merge, so tunnel → load onto carrier is correct | Rename to "loaded onto carrier N" (or "merged onto sorter"). Add one line in the hub topology/README: induction station → infeed belt → scan tunnel → merge onto carrier → loop → chute | P1 |
| 3 | 3D scene (desktop + mobile) | Event labels collide: "inducted · 14:32:15.400" covers "tunnel read · 14:32:10.500" (only "…el read" visible) | Label de-overlap: screen-space collision pass, stack with short leader lines, or collapse to "2 events" chip that expands on hover/tap | P1 |
| 4 | 3D scene | Hall walls export as dark maroon/black — looks nothing like the white-walled hub in the CCTV and reads as blood-red | Fix the wall material in `export_hub_glb.py` (likely an unsupported node tree falling back): light warm-grey/white walls, keep the floor override | P1 |
| 5 | 3D trace (fixture) | At the default overview the trace is a hair-thin line; the green segment is barely visible | Screen-space line width ≥ 3 px (Line2/meshline), arrowhead at the direction of travel, and auto-frame the trace bounds when Object trace has segments | P1 |
| 6 | Mobile 3D | Canvas leaves large empty bands above/below the hub | Fit camera to the hub bounding box for the viewport aspect | P2 |
| 7 | Source panel in the recording | Frame thumbnail goes black for a moment while the signed frame loads | Keep the previous frame dimmed + spinner, or a skeleton, never black | P2 |
| 8 | Agent answer | "…synchronized footage.." double full stop | Fix in the orchestrator composer (backend string) | P2 |
| 9 | Review pack | 03=04, 06=08, 18=19 are byte-identical files; overview shot already shows "Report approved" before the story reaches the report | Capture the pack in story order from a fresh seed; one file per distinct state | P2 |

## Answers to your questions
- **002 Q1 (shelves 21.4 m tall):** good catch — that's a builder bug, not a web problem. Builder: fix `steel_frame_shelves_01.001/.002`
  scale in the dressing pass before B2 stills (P1). Keep your eaves+1.5 m drop as a safety net and keep listing what it drops.
- **002 Q2 (`bag_drop` pulses with no ID):** don't add a ScanEvent kind and don't invent IDs. Import them through the existing
  **sensor-events** route as `simulated` photo-eye events (zone/chute, time, no identity). They are corroboration ("something
  entered the bag at C03 at t"), not identity. Builder (block D): the bagging step also needs **bag-close / container scans**
  (bag ID, chute, time) so containment scenarios have EPCIS-style aggregation evidence.
- **003 Q1 (label for scanner reads):** keep the backend's label; fix the words after it per fix 1.
- **004 Q1:** import every clip that exists, so coverage gaps are real. Re-seed after B3 lands.

QUEUE: C1, C3, C5, C6, C7 approved. C2 (walls, #4) and C4 (#1, #3, #5) close when those fixes land; no new request needed —
mention them in your next request.
