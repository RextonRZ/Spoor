# Request 009: A3, review 006 fixes (people re-rendered) + new QA gates + scenario timelines

Built from the final rebuild (07:45) with the locked look, then S0 run on it. Every worker in review 006 is re-rendered; all workers changed, because the fixes are in the shared solver.

## 1. Changed since last request
Fixed from review 006: P0 #1, #2, #3 (closed in 006b), #4, #5; P1 #6, #7, #8, #9, #10. P2 #12 (barrier) is in the next build pass; #11 is deferred, as agreed in 006b.

| # | What was wrong (cause found) | Fix |
|---|---|---|
| P0 1 | **Carton through the head.** The reach adaptation added up to 0.7 rad of lean per pass over 3 passes, uncapped, on top of the station's own flex. People folded 70–80° over their work, head into what they held. | Total adaptive lean capped at 0.5 rad; past that the knees drop. Upright through the turn, bending for the set-down only in its last 40 %. The carton is carried 0.5 m out (was 0.42). New QA check **held_clip_head** (head sphere r = 11 cm vs every moving object's box). |
| P0 2 | **Body inside the cage.** f163 was the old walk route through queue cage 3 (rerouted). At f190/f299 the torso entered the pushed cage: root 0.42 m behind the posts plus a 0.26 rad push lean. | Root 0.52 m behind the posts (chest ~0.3 m clear); push lean 0.10–0.22 rad. Walks now join pushes exactly. `body_in_cage` is high, and `qa_gate.py` fails a scenario on it. |
| P0 4 | **Parcels inside each other.** The new QA check **parcel_overlap** (oriented boxes, 2-D SAT + height) found 7 separate causes. | The causes and fixes are in the list below this table. |
| P0 5 | **Head snaps.** Glances switched the head between the clip's head and the target; target and clamp crossings also jumped. | Look weight fades over 0.5 s; head world rotation limited to ≤ 12°/frame (120°/s) in the solver; walking turns critically damped and capped at 18°/frame, torso facing at 15°/frame. |
| P1 6 | Idle 6–8 s. | cage_1 walks back through the bay he emptied to the next cage (S15); the bagger walks on to check C08's bag. |
| P1 7 | Bags read as vases. | Full sacks fill the frame (belly 5 %, was 15 %); parcel-corner bumps; specular 0.2; matte weave. Same for the tied sacks. |
| P1 8 | Face into the sack at the cage. | The sack is placed exactly at its resting pose (it also jumped 30 cm at the let-go); he stops closer; lean 0.08–0.2. |
| P1 9 | Dock follow-cam / cartons per 30 s. | 6 / 6 / 6 / 7 cartons per unloader per 30 s. The follow-cam now stands in the hall: hip-measured facing, 8 angles, enclosed spots scored down. |
| P1 10 | Blank HMI. | The screen shows a UI drawn in code: header, the loop, 12 chute tiles (C07 red, two amber), status rows. |

**The 7 parcel-overlap causes and their fixes:**
1. Opener grid pile: now a real heap, taken top-first; parcels lifted 15 cm and carried over the heap.
2. Dock diagonal pull: now straight out of the slot, lowered at the wall before being drawn in; the turn arc avoids the wall.
3. Inductor pull: lift 12 cm and out of the lane; the queue place is held until the parcel is clear; a keep-out line at the feed for the carry and the hold.
4. Collector→feed corner and D02 boom: the boom joined the collector 15 cm before its corner. It now hands over at the feed start, taking turns with the collector, with lateral ease instead of a sideways jump.
5. Merge waiting on the loop track: it now waits 0.45 m short and books the carrier.
6. Two parcels on one chute: they slide down different halves.
7. Bag landings: stacked over the whole bag; they were centred on the frame's front edge.

Results:
- S0: `parcel_overlap` 117 → 27 rows; `held_clip_head` 15 → 2; `loop_pop` (high) 104 → 45; `body_in_cage` 1 → 0.
- High flags 180 → 142, with two new checks counted.

Other:
- **Gate:** `assets/hub/qa_gate.py` fails a scenario on any `body_in_cage` / `held_clip_head` / `accessory_off_head`, or any parcel overlap ≥ 5 cm × 3 frames. `render_batch.sh` runs it and stops unless `GATE_FORCE=1` (logged).
- **Scenarios:** S1 crash fixed (rework set-down after the window); S0 picks its story parcel with a fallback; `case_input.json` carries `waybill` + `complaint`.
- **Walk cadence:** I tried calibrating it and reverted. The 2–3 cm/frame toe slip is the clip's own toe roll: +10 % cadence changed nothing.

## 2. Check these
- **Follow-cams (A3), all 13 workers re-rendered from S0 of the final build:** `assets/hub/build/qa/workers/*.mp4`. The old ones are in `qa/_superseded_1030am/`.
- **QA:**
  - `assets/hub/build/qa/review/req009/auto_flags.csv`, `summary.txt`, `gate.txt` (S0);
  - per scenario: `assets/hub/build/qa/scenarios/<S>_flags.csv` + `<S>_summary.txt`.
- **B2 stills** (frame 150 of S0, all 18 cameras, 2688×1520, CCTV pass + OSD): `assets/hub/build/qa/b2/CAM_xx.png` and `contact_sheet.jpg`.
  - CAM_17 (yard) now has its own auto-exposure (−1.1 EV): mean 153 → 127, clipped 2.4 % → 0.7 %.
- **Evidence:** `assets/hub/build/qa/review/req009/` (P0 #3 rail, new dock follow-cam).
- **Scenario timelines** (D1): S0, S2, S5 done on the final build; S3, S4, S1 running. Cards go to `ml/evaluation/scenarios/` when the chain ends.

## 3. Known issues (not fixed yet, with numbers)
1. **Dock top-row picks:** 2 head contacts (8–11 cm, 4 frames each) and 4 parcel overlaps (5–18 cm, 3–4 frames). The worker stands 0.32 m from the face, so lowering a top carton passes close to the face. The proper fix is a step back with the carton, which the dock rig can't do yet.
2. **Other parcel overlaps ≥ 5 cm × 3 frames on S0 (5):**
   - inductor set-down/queue (7.7–7.8, 9.7–10.6), 3–4 frames;
   - one bag landing at C08 (5 frames);
   - one merge (3 frames).
3. **Remaining `body_clip_static`** (53 high):
   - dock fingers against neighbouring cartons, ≤ 8 cm;
   - inductors' hips/hands against the belt frames in the 0.55 m aisle, ≤ 6 cm;
   - `loop_pop` 45 high, mostly fast arm moves in the dock and inductor pick cycles.
4. **Yard (CAM_17)** geometry is crude: block lorries on a flat slab.
5. **Walkers' toe roll** 2–3 cm/frame; P2 #11 phase label (deferred); break-pair facing and the barrier go into the next build pass.

## 4. Questions
1. **D2** (S0 on CAM_07 + CAM_13, final settings) is rendering now with `GATE_FORCE=1`, for the items in §3. It comes as request 011. OK to treat §3.1–3.2 as accepted for the S0 batch, or must the gate pass first?
2. Is the remaining dock top-row contact acceptable at CCTV distance, or do you want the step-back implemented before the batch? It is ~2 h of work and needs a re-run of all scenarios.
