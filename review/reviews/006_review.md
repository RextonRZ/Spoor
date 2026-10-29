# Review 006 — People rebuild (A1/A2), 12 follow-cams

Verdict: **NOT APPROVED yet — big step forward, but 5 P0s a viewer sees in 2 s.** Re-render only the affected workers.
Method: every clip through `review/tools/motion_check.py` (12-frame overview, per-cell pop detector with t-1/t/t+1 crops,
motion trails), then manual inspection. Sheets in `review/_sheets/r006/` (local only). Your §3 known issues are skipped.

What's now good: hands land on cartons and cage posts; cage_2 pushes with both hands at f217–299; clipboard, phone, HMI tap
and seated pose read right; walkers' gait is natural; scan log v2 (device clocks, no t_s leak) is correct.

## P0 — must fix before the S0 batch
| # | Worker / clip | Frames | Problem | Required fix |
|---|---|---|---|---|
| 1 | Inductor with teal cap (`worker_induct_2`, also seen in `induct_1`) | induct_2 f37–39, f130–132, f138–140; induct_1 f54, f163 | Carried carton **passes through the head** — box held at face height, head inside it | Carry pose: carton centre ≥ 25 cm in front of the sternum, top ≤ chin height; turn with the box low. Add a QA check `held_clip_head` (head bone sphere r=11 cm vs held object bounds) = high |
| 2 | `worker_cage_2` | f163–190 | Cage mesh passes **through the torso** (body inside the cage) at the gate/turn | Pusher stays behind the back face with 0.25–0.35 m clearance; on turns the cage pivots around its castors, the body follows behind. Make `body_in_cage` high and fail the build |
| 3 | `worker_bag_1` | f27, f81, f163, f190, f217–299 | A **brown pole/plank** jumps between positions (diagonal in mid-air at f27/f217, on the floor at f81/f163, upright at f190) | Identify it (broom? bag-frame hook? sack-truck handle?). Give it one rest pose; if it's carried, parent it to the hand with contact; never float |
| 4 | Induction / accumulation belts (`induct_2` view) | f166–168, f266–268 | **Parcels interpenetrate on the belt**: a carton sits inside a flat; a white box inside a brown carton | Queue spacing ≥ 2 cm, accumulation as zone stops (items stop, don't overlap); flats never slide under cartons. QA check `parcel_overlap` (OBB intersection on belts) = high |
| 5 | Dock unloader `D05_n` | f75→76, f83→84 | Head + hard hat snap ~40° in one frame (glance pop) | Confirm your 0.5 s look-at fade (known #3) is applied to dock agents too; re-measure head yaw velocity ≤ 120°/s |

## P1
| # | Where | Problem | Fix |
|---|---|---|---|
| 6 | cage_1 f217–299, bag_1 f217–299, open_1 f244 | People stand idle 6–8 s with arms down, often facing the camera — reads as "NPC waiting" | Idle ≤ 3 s unless motivated; fill with micro-tasks (look at cage tag, check phone, adjust glove, scan, walk to next job) or walk off |
| 7 | Every chute (walk_1 f27/f108, check_1, bag_1 f163, CCTV) | Bulk bags read as **glossy ceramic vases / toilets**: smooth, shiny, narrow neck | Woven PP sack: matte (roughness ≈ 0.8, woven normal), lumpy with parcel corners pushing out, sagging, fill varies per chute, tied neck with cable tie + bag tag. Visible in every chute camera, so high value |
| 8 | bag_1 f135 | Head pressed into the bag while carrying | Carry by the neck at the side, bag hanging by the leg (one hand), or two-hand at hip — never hugged against the face |
| 9 | Dock unloaders | Mostly empty-handed in the 30 s; follow-cam too tight to see the wall → boom handover | Report cartons moved per unloader per 30 s (target 5–7). Widen dock follow-cams so wall, hands and boom nose are in frame |
| 10 | tech_1 | HMI is a blank black slab | Emissive UI texture (sorter diagram, chute tiles green/amber/red) like beesort_t122 |

## P2
| # | Where | Note |
|---|---|---|
| 11 | Follow-cam overlay | `clip: ?` — fill in the clip/action name; it speeds up review |
| 12 | Break table | Sits right beside a running conveyor + e-stop; real hubs put breaks in a side area behind a barrier |

## Answers
1. **B3 = S0 batch: yes**, with one gate: render **D2 first** (S0, 2 cameras, final settings) and send it to me before the
   other 16. Then 3 requests of 6 cameras as you proposed. A separate 60 s pass is not needed.
2. **Look: accepted.** Walls 171–175, floor 96–99, 0.04 % > 230 is inside the target (floor 85–110). Lock it.

## Render budget
Your estimate (42–63 h rendering, start by Oct 31 morning, no second full re-render) is the real risk. Fix the P0s **once,
properly**, and test on short ranges before the batch. I've put the resolution decision for Rexton in FOR_REXTON.md.
