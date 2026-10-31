# 013c — headwear proof sheets (qa/review/cap_check/, 48 PNG, 8 workers × f001/f120/f250 × front/side, made 14:57 MYT)

**Verdict: NOT APPROVED — headwear strike. Per headwear_decision.md ("fail once → remove"): REMOVE ALL HEADWEAR NOW.
Zero hats, zero caps, every worker. Do not attempt another fit.**

Why (every one of the 8 is broken; checked every tile):
1. P0 All 8 are HARD HATS (bag_1, cage_1, dock_D02_n, dock_D05_n, inductB_1, sup_1, tech_1, walk_2). Decision 14:36 was
   NO hard hats; caps on 2–3 short-haired workers only. mixamo_workers.py:42/55/61/67 and stations.py:2476 still set
   hat="hard"; stations.py:2446 hat="cap" renders the same dome.
2. P0 Hair through the crown: black slashes across the top of the shell on dock_D02_n (all 3 frames), tech_1 (all),
   walk_2 (all).
3. P0 Shell not one piece: crown floats above the brim with a dark gap band (cage_1 f001 side, f250 front; inductB_1
   f001 front/side; D02_n all fronts); brim slices through the forehead (inductB_1 f001 side, f120 front).
4. P0 Hat leaves the head: bag_1 f120 front/side (hat rotated ~70°, brim vertical, face through it); sup_1 f120 hat
   slid to the back of the skull.
5. P0 Scale: crown covers eyes/whole upper face (D05_n f120/f250 front, sup_1 f250 front).

Fix: set every hat to None (people.py spec, stations.py 2446/2476, mixamo_workers.py roster even though USE_MIXAMO is
off), delete the hat prop path from the render build or guard it with an assert, re-run qa_heads.py for all workers,
and include in the next request: one head sheet (all workers, f001/f150/f300, front+side) showing bare heads only.
Then go back to 014_GO_mocap_plan.md — headwear is closed, do not spend more time on it.
