# Review 013b — the follow-cam videos (qa/review/req013/follow/), 1 fps crops

Sheets: `review/_sheets/r013/*.jpg` (local). Caps/hard hats ignored here (headwear_decision.md removes them).
Verdict: **NOT APPROVED.**

## P0
| # | Clip | Frames | Problem |
|---|---|---|---|
| 1 | induct_1_front, induct_2_front | almost every frame (f10, f40, f90, f140, f190, f240, f290) | **People overlap people.** The four line-A inductors stand front-to-back in one aisle ~0.3–0.4 m apart; bodies merge (orange vest into the teal-cap worker's back, green vest into the teal cap). **Your collision table has no person–person column** — add it now; the owner rule covers person ↔ person. Real induction stations are spaced along the belt (≥ 1.2–1.5 m per operator), not queued in one aisle. Fewer inductors or a longer induction face. |
| 2 | induct_1_front f170, f230; induct_2_front f170, f190 | — | Big carton held **out at arm's length** over the feed belt with straight arms (the 009e zombie/strength problem is back). Carry close to the body, elbows bent, then turn and place. |
| 3 | dock_D02_s | f210–f230, f290 | **The unloader disappears** — only cartons in frame. Either she is inside the carton wall or the camera clips through her. Side view + collision rows for these frames. |
| 4 | dock_D02_s | f0, f50, f100, f150 | Both hands **open, palms up, holding nothing** beside the cartons — a "receiving / begging" pose. Hands are either gripping a carton's outside faces or relaxed at the sides. |
| 5 | dock_D05_n | f0–f290 | The head sits **merged into a single huge (~0.8 m) carton** next to the boom in nearly every frame. Occlusion or penetration can't be told from this angle → side view + collision rows. Also: why is one huge carton standing there for 30 s? An unload face is a wall of mixed cartons inside the trailer, worked top-down. |

## P1
| # | Clip | Frames | Problem |
|---|---|---|---|
| 6 | induct_2_front | f120, f160 | Green-vest arms spread wide to both sides, hands empty — reads unnatural. |
| 7 | all | — | Workbench follow-cams make it hard to judge contact. Add one **final-look (EEVEE) follow-cam** per station in the next request. |

## Required in the next request
Person–person column in the collision table (S0 + S2), the inductor spacing change with before/after sheets, side views for
docks D02_s/D05_n with the frames above, and the headwear change (no hard hats; 0–3 proper caps).
