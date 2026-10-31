# Review 009e — sharp pass, 1 fps native-pixel crops (Rexton: "be sharp like my eyes")

Sheets (local): `review/_sheets/dense/*_crop.jpg` (induct_1, dock_D05_n, cage_2, bag_1). Frame numbers below = video frame.
Everything here is **P0 unless marked**. Adds to 009d; 009d's acceptance rules apply.

## Inductor trio (`worker_induct_1` view)
| Frames | Who | What I see |
|---|---|---|
| f10, f20, f30, f50, f60, f70, f120, f150–f290 (every sampled frame) | teal cap | Cap perched on the crown, tilted back ~30°, headband + hair visible under it; at f70, f120, f180, f230, f270 it's a flat disc **above** the bent head. Never seated. |
| f0, f40, f100, f140, f200, f250 | teal cap | **"Zombie arms"**: both arms straight out at chest height, elbows locked, hands hovering over the belt — this is the exact zombie pose. Reach with bent elbows, step in, hands land on the parcel. |
| f180, f230, f270 | teal cap | Head dropped to belt level (chest on the belt) — the slump from 009d #1. |
| f20, f30 | green vest | Carton carried at face height; her head beside/behind the box. |
| f250, f290 | green vest | Big carton held **one-handed at full arm extension** at shoulder height — impossible for that size; two hands, close to the body. |
| f290 | green vest → teal cap | The carried carton passes over/into the teal-cap worker's head space. Workers too close (shoulders < 0.4 m apart, f30, f250, f290). |
| f50, f90, f140, f240 | orange vest | Arms dead at the sides, head bowed, no task for 1–3 s at a time between picks — reads as an idle NPC. |

## Dock unloader `worker_dock_D05_n`
| Frames | What I see |
|---|---|
| **f20–f60** | **Head and shoulders disappear into the carton wall** — at f30/f40 only the hard-hat top shows above a carton, at f50/f60 the head is fully inside the cartons with an arm sticking out. |
| **f120–f290 (17 s)** | **Standing still, head bowed, hands empty** — no carton handled for 17 s. This contradicts "6 cartons / 30 s" in request 009. Show the per-worker carton count from the render, not from the plan. |
| all | Hard hat faceted (low-poly) — P2. |

## Cage pusher `worker_cage_2`
At f0–f20, f140–f210 and f250–f290 the cage mesh lines cross his head and torso. From this follow-cam angle I **cannot tell occlusion from penetration** — that itself is a problem for review. Required: (a) the global collision report (009d OWNER RULE) for this worker, frame by frame; (b) follow-cam from the side (90° to the push direction) for every pusher so overlap is unambiguous.

## Bagger `worker_bag_1`
| Frames | What I see |
|---|---|
| f120–f130 | Leans into the white cage with the **head below the top rail, inside the cage volume** (verify in collision report; should lean over the rail, head above it). |
| f80–f170 | Long walk with nothing in hand between tasks (ok if motivated — show where she's going). P1 |

## What I need in the next request (no exceptions)
1. Collision report (OWNER RULE) per worker and per scenario: counts by pair type, worst 20 frames with crops.
2. Side-angle follow-cams for pushers, front-angle for inductors (so faces/hands are visible), and **1 fps native crops** like mine.
3. Measured cartons handled per worker per 30 s **from the render** (count parcel hand-offs in the timeline).
4. Cap/hard-hat fit report (accessory_fit) — 0 rows.
