# Request 003 — Frontend: C3 + C4 (all §19.2 surfaces, operator page, signature interaction)

From the frontend agent. Builds on request 002 (not yet reviewed).

## 1. Changed since last request
- Fixed reviewer log note (02:11): `frontend/package.json` description mojibake → plain ASCII.
- **C3 surfaces** (`frontend/src/app/…`, `frontend/src/components/workspace/…`):
  - Case overview: question, last confirmed (graded: fixed scan > handheld > video; leads listed separately and never
    called "last seen"), unknowns, next evidence (backend evidence requests; otherwise cameras that see the last read
    point, marked "suggested from the camera mounting plan"), report state.
  - 3D scene (R3F) and 2D plan, keyboard: arrows pan, +/- zoom, R reset; labels are plain DOM projected from 3D.
  - One canonical timeline (MYT display of normalized UTC): parcel lane (scans, visibility, grey unknown intervals),
    hub-scan lane, one lane per camera with footage, sync uncertainty drawn as hatched ends, clock warnings list
    (unverified camera clocks, unsynchronized WCS clock). Range-input scrubber (←/→ 1 s, Shift 10 s, Home/End).
  - Movement trace: Object / People (anonymous) / All. People shows an honest "needs SAM (no API key)" note.
  - Source panel: original frame via signed link, frame stepping, media id + SHA-256 inline, footage kind; annotated
    derivative toggle for model observations; context frames at a scan time say "Not an observation".
  - Evidence graph: sources → evidence → hypotheses → findings, counter-evidence dashed red; empty columns say why.
  - Agent panel: runs `/v1/cases/{id}/investigate`, shows the job's own SSE events as they arrive, then the stored
    answer verbatim and the revision diff ("what changed"). No typing effect, no invented tool activity.
  - Report: investigator exports a draft, a different reviewer approves; sandboxed preview of the backend HTML;
    downloads of the stored report JSON and hash manifest.
  - Operator (§23): capability status, imports (clip, scan log with mandatory real/simulated, simulated sensor CSV),
    cameras/clocks/calibration table, footage table, clock domains, model calls + agent steps, evaluation results.
    It has no control that sets an answer, a trace, provenance or a metric.
- **C4**: "Show where it was last confirmed" → scene moves to the last confirmed read point (550 ms ease, instant under
  reduced motion), the camera(s) that see it light up, source panel opens the exact frame at that time. Trace contract
  (green solid / amber dashed / grey gap, solid never bridges a gap) enforced in `src/lib/trace.ts` + unit test; clicking
  a solid segment opens that observation's frame. With no SAM key there are no observations, so the green/amber part is
  shown on a route-mocked **TEST FIXTURE** (yellow banner on every such image, files `fx_*`).

## 2. Check these (both sizes: `frontend/review_pack/desktop/` 1440×900 and `frontend/review_pack/mobile/` 390×844)
- `02_workspace_3d_overview.png`, `03_workspace_3d_last_confirmed.png`, `04_source_context_frame.png`,
  `05_source_frame_stepped.png`, `06_workspace_2d_plan.png`, `07_trace_people_mode.png`, `08_case_overview.png`,
  `09_timeline_clock_warnings.png`, `10_agent_before_run.png`, `11_agent_after_run.png`, `12_evidence_graph.png`,
  `13_report_draft.png`, `14_report_approved.png`, `15_operator.png`
- Fixture (C4 renderer): `fx_16_trace_3d.png`, `fx_17_trace_plan.png`, `fx_18_segment_source.png`, `fx_19_timeline_gap.png`
- `01_cases.png`

## 3. Known issues
- The "request another camera interval → new evidence added" step of §19.3 works through Operator → Import a camera
  clip, then re-running the investigation (diff panel). There is no further clip to import yet: only the four QA clips
  exist. I will show it once B3 clips land.
- QA clips are 960×540 renders of a moving scene; camera sync is declared, not fitted (±5 s), shown as warnings.
- 3D in headless screenshots uses SwiftShader; real GPUs render the same scene faster.

## 4. Questions
1. The workspace shows the backend's label for a fixed scanner read as "Observed" (graded_last_seen gives
   `EvidenceLabel.OBSERVED` for fixed reads, `ESTIMATED` for handheld). Keep, or should a scan read be its own label
   ("Scan read") everywhere so "Observed" stays video-only? I lean to keep the backend's label and add "fixed scanner
   read" right after it (as now).
