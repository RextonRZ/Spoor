# 016b reply (builder, 30 Oct): dock D05 fixes

| # | Fix | Finding | Action |
|---|---|---|---|
| 1 P0 | Head vs column, behind f61–71 | **Measured, not contact:** new QA `assets/hub/mocap/head_clear.py` (head + neck vertices to every carton box, every frame), output `qa/review/m4_dock/head_clear.json`. At f57–80 the head is 22–35 cm from the nearest carton. From the behind camera the column edge only covers his face. **But the check found a real breach elsewhere: f198–205**, the floor-tier stoop (carton 6, pick 0.86 m) puts the head **0.5–3.2 cm** from the back-row carton above it (rule ≥ 5 cm: 8 frames). | Head ≥ 5 cm becomes a gate row for every station (line A too). Fix at M5 step 3 when the dock moves onto the full trailer wall: root further back and less stoop for low picks behind a high back row (the bench's `pick_root_max_n` per-tier back-off, extended with the head rule). |
| 2 P1 | Full trailer load | Agreed. The bench wall is two thin columns + 30 back-row cartons in a grey box. | Comes with `MocapDocks` (M5 step 3): reuse `stations.build_wall` (full 2.4 m width, mixed sizes, loose-loaded to 1.7–1.8 m, inside the hub's real trailer with ribbed walls / floor / roof), unloaded face by face, top-down. |
| 3 P1 | Carton conservation | **Holds.** Positions at f1 / f150 / f296: the 9 picked cartons (1.65 → 0.60 m) leave the two front columns top-down; at f296 they are on the boom or past its end, and only the 2 bottom front cartons remain. The columns that look unchanged are the 30 back-row cartons (3 rows deep), which nobody reaches in a 30 s window. | On the full wall, the face being worked will step down visibly. I'll show a column-height row (f1 vs f300) in the M5 evidence. |
| 4 P1 | 54 collision frames | Agreed (slide / tip toward himself, flat finger approach, ≥ 3 cm column gaps). | M5 step 3 / 4. |
| 5 P2 | A pause 1 in ~6 lifts | Agreed: the planner's beat already gives 1 in 6 a 0.6–1.1 s pause. | Brow wipe / back straighten needs a source clip (100STYLE has none; to search). |

016c: closed as you say; the feed-limited 3.1–4.4 s line stays.
