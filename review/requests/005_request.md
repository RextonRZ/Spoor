# Request 005 — Frontend: fixes from review 004 (closes C2 and C4)

From the frontend agent.

## 1. Changed since last request
Fixed from review 004: **1, 2, 3, 4, 5, 6, 7, 8, 9** (all). Answers applied: 002 Q2 (photo-eyes), 004 Q1 (all clips).
1. **P0 wording** — new `frontend/src/lib/scans.ts → describeScan()` used by the source panel, last-confirmed card,
   timeline tooltips/aria labels, 3D/2D labels and evidence-graph nodes. Per event: tunnel read = "label read at the scan
   tunnel"; `induct_to_carrier` = "loaded onto carrier N" ("sorter assigned the tracked item to carrier N at the merge.
   Identity is carried by sorter tracking from the tunnel read, not a new read"); `divert_confirm` = "sorter divert to
   C02" / card "Observed: sorter divert confirmation" / proves "The sorter reports carrier 79 discharged at C02. Identity
   comes from sorter tracking, not a new read. Whether the parcel then went into the bag is not shown." Also no-read
   variants, reject chute, and the new `recirculate_chute_full` events (imported as `recirculated`, reason `chute_full`).
   Backend: parcel lookup and site scan list now return `raw_code`, `raw_description`, `read_outcome`,
   `sort_destination_actual` so the words come from the record. The backend report has no scan text to fix.
2. **Event names + flow** — "loaded onto carrier N"; hub flow line in the source panel and `frontend/README.md`
   ("induction station → infeed belt → scan tunnel → merge onto a carrier → sorter loop → chute").
3. **Label collisions** — screen-space declutter (priority: selected > last confirmed > lit camera > scans), stacked labels
   get a leader line; labels are clamped inside the canvas.
4. **Walls** — `export_hub_glb.py` gives `wall_N/S/E/W` a light warm-grey material in the web copy (`hub.export.json →
   material_overrides`). GLB 3.9 MB.
5. **Trace** — 5 px solid / 3 px dashed screen-space lines drawn over geometry, green arrowhead at the end of each solid run
   (direction of travel), auto-frame to the trace bounds once when observed segments arrive.
6. **Mobile 3D** — portrait viewports look down the hall's long axis from the west; the hub fills the canvas.
7. **Frame loading** — the previous frame stays (dimmed) with a "Loading frame" tag; first load shows a surface-colour
   skeleton, never black.
8. **Double full stop** — `backend/src/spoor/agents/orchestrator.py` strips a trailing "." before adding one. pytest 207 ✓.
9. **Review pack** — regenerated from a fresh seed per viewport in story order; desktop pane states are element shots
   (04/05 source panel, 08 case overview, 09/fx_19 timeline, fx_18 source), so no two files show the same state.
- **Photo-eyes (002 Q2)** — the 20 `bag_drop` pulses are imported through `/v1/cases/{id}/evidence/import` as `simulated`
  `motion_trigger` sensor events (`chute:C03:photo-eye`, zone Z06/Z07, no identity) and drawn as a "Chute photo-eyes ·
  no identity · simulated" timeline lane.
- Inputs: the builder moved the QA clips to `assets/hub/build/qa/_superseded_1029/cctv/`; the seed now reads clips from
  `frontend/.local/clips/` (copies) and the scan log from a snapshot, so the demo data stays stable while hub files change.

## 2. Check these
- `frontend/review_pack/desktop/02_workspace_3d_overview.png` (walls, labels), `03_workspace_3d_last_confirmed.png`
  (wording), `04_source_context_frame.png`, `09_timeline_clock_warnings.png` (photo-eye lane), `fx_16_trace_3d.png`
  (arrowhead, auto-frame), `fx_18_segment_source.png`, `fx_19_timeline_gap.png`
- `frontend/review_pack/mobile/02_workspace_3d_overview.png`, `03_…`, `04_…`
- `frontend/review_pack/signature_interaction.mp4` (re-recorded, 1280×800, < 60 s)
- Tests: typecheck ✓, lint ✓, unit 6/6 ✓, e2e 13/13 ✓ (smoke + axe AA), backend pytest 207 ✓.

## 3. Known issues
- Mobile `02` was captured just before the last label-clamp tweak (one chip touches the right edge); the live app clamps.
- Still no observed segments without SAM; the green/amber trace is shown on the bannered fixture only.

## 4. Questions
None.
