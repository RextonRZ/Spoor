# Builder note (05:15 Sat) — two things from the frontend

1. **S2 subject missing from the sim log.** Frontend 05:07: `assets/hub/build/sim/events_scan_simulated_S2.jsonl`
   (176 rows, 14:10:40–14:32:38) has no row for the S2 case_input subject **CTX971442173782**. The card/case_input
   and the sim log disagree (renamed?). Fix it in the same pass as the 15 min S2 scan log (builder_note_0445), and
   add a check: every scenario's case_input subject appears in its scan log with the scans the card lists.
2. **A worker lying on the floor.** The Spark Open vision smoke test (F-035) reported a worker lying on the floor in
   **CAM_10 frame 248** of the old QA clip. I can see a person lying flat on the right of that frame too. Check
   whether any current station can drop a body to the floor (ragdoll / missing action / fallen rig); add a gate:
   pelvis height ≥ 0.6 m for every standing/walking worker in every frame, and list any hits in 021c.
