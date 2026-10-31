# 019 · S2 perimeter proof (scenarios_v2 S2 #1, P0)

**Ask:** check that every way out of BLIND_NW / Z11 is watched, and approve **one new camera, CAM_19 "EXCEPTION STORE"**,
on the store entrance. No camera sees inside the store beyond its doorway.

## How it was checked
- Blender raycast from every CCTV camera, in the real layout-b hub geometry (racks, bales, walls, cages):
  `assets/hub/mocap/s2_perimeter.py`.
- A point counts as seen only if it is inside the frame **after the lens crop**. That is the barrel remap in
  `cctv_look`, with each camera's k1. It drops about the top 35 rows, which matters for far cameras.
- Results: `qa/review/s2_perimeter/perimeter.json`. Plan: `qa/review/s2_perimeter/plan.png`.

## What the first pass found (before any change)
1. **The only walk-in is the 1.8 m gap** (x 13.4–15.2). Both racks run flush to the walls (the probes hit wall_W and
   wall_N), and there are no doors in those walls.
2. **The gap was watched only at the very top edge of CAM_01 and CAM_06**, about 32 m away (~40 ppm). After the lens
   crop, CAM_06 kept only the bottom ~0.4 m of it, and a column partly hides it in CAM_01. CAM_13 does not see the gap
   at all; the old card said "CAM_13 films the approach".
3. **16 % of the inside of Z11 was visible**, through the slots between the bale tops and the beams and the ~0.5 m left
   open at each rack run's end. The old 2D plan check said 0 %.

## Changes
1. **Racks packed** (`build_hub.py`):
   - bales fill each bay end to end, pressed to 1–3 cm under the next beam;
   - their heights come from their own random stream, so every other random item in the hub is unchanged.
2. **New CAM_19 "EXCEPTION STORE"**:
   - mount: truss drop-pole at (12.0, 29.0), 3.5 m high, yaw 80°, tilt 45°;
   - chosen by the planner's pose search with all 4 corners of the gap required in view;
   - first tries: from the south-east it framed mostly floor with the gap in a corner; at 4.0 m it saw over the 3 m
     rack into the store's north band;
   - native still with the gap outlined in red: `qa/review/s2_perimeter/CAM_19_native.png`;
   - source for the idea: TAPA FSR 2023 §7.4.15–16, "CCTV … coverage on HVC entrance", and "If the HVC is too small
     to locate a camera inside, camera coverage of the entrance is sufficient". So a camera on the door and none
     inside is a real pattern.
3. **Planner re-run** (`build_hub_plan.py`):
   - CAM_01–18 poses unchanged (checked);
   - hub_spec / plan / render_truth regenerated;
   - blind-corner check: 0.019 seen, approach seen by CAM_13 and CAM_19;
   - S0 and S2 camera lists now include CAM_19 (`make_cards.py`).

## Result (layout-b build, lens crop on)

| Face | Seen by any camera | Notes |
|---|---|---|
| Gap, south face (y 32.95, z 0.1–2.0) | **100 %** | CAM_19 100 %, CAM_01 69 %, CAM_14 41 %, CAM_06 35 % |
| Gap, mid plane | 92 % | Unseen: x 13.45–13.55, z ≥ 0.7, behind the south rack's end upright. Reachable only through the south face. |
| Gap, north face | 88 % | Same strip |
| A person standing in the gap | **100 %** | |
| Inside Z11 (0.5 m grid × z 0.2/1.0/1.7) | **5 %** | All of it is the view through the open doorway: ≤ 2 m in, plus a strip along the east rack. West of x 12.5 nothing is seen. |
| Over the racks (z 3.3) | 0 % | A throw over a 3 m rack is not seen in the air. 83 % of the floor band where it would land outside is seen. |

## Truth card
`flow.py` S2 now writes:
- `exits_covered: true` and `exits` (per exit: cameras and seen fractions; `stations.S2_EXITS`);
- cameras CAM_13, CAM_19, CAM_01, CAM_06;
- the sharp expected answer: "no camera sees inside Z11, but every way out is watched and nothing came out before the
  window ended → still inside Z11 (moved by a person, not 'stolen', not 'left the hub')".

The card itself is regenerated with the S2 run.

## Please check
- Is CAM_19's framing OK for an entrance camera? It shows the doorway centre-right, the rack fronts, and the wall
  above.
- The over-the-rack throw: is "not a way out for a person; landing band 83 % seen" enough, or do you want it closed?

## Not yet
- The removal actor on mocap (S2 #2) is next, in progress.
- Frontend (hub.generated.json, hub.glb frusta) and backend camera lists pick up CAM_19 with the S2 integration.
