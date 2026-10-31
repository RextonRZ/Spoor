# M5 plan: from the mocap benches to S0 / S2 (written 30 Oct, evening)

## Where things stand
- **Built and proven** (`assets/hub/mocap/`):
  - the retarget (M2);
  - the inductor engine `inductor.py` (M3), which also drives the dock unloader;
  - line A with four induct points (`m4_line_a.py`, request 016);
  - the dock unloader at D05 south (`m4_dock.py`, request 016b).
- **All of them are standalone scenes:** the lit hub with their own geometry added and their own cartons. **None is in `flow.py` yet.** S0–S5 still use the old procedural workers (`stations.py` + `contact.py`).

## Step 1 status (30 Oct, 19:05): geometry done behind a switch, not yet switched on
- **`build_hub_plan.py`:** `LINE_A_LAYOUT = "a"` (current). Under `"b"`:
  - the collector turns east at y 12.25 to x 13;
  - a `d02_stub` belt (D02's boom joins it and runs north into the feed corner);
  - a "line A workstation" floor obstacle;
  - `"line_a": {"layout": ...}` in the spec. Verified: with `"a"`, the regenerated spec only gains that key.
- **`build_hub.py`:** under `line_a.layout == "b"`:
  - table mouths cut in the feed's south frame, merge openings in belt A's north frame;
  - 4 roller tables (guides, end stops, legs);
  - 4 induct belts as sheared slabs, both ends parallel to belt A (flush at its frame; square ends poked 18 cm in);
  - 4 diverter paddles.
  - Test build: `py -X utf8 assets/hub/mocap/make_lineab_spec.py`, then build_hub with `--spec assets/hub/hub_spec_lineAb.json`. Views in `qa/review/m5_geom/`.
- **`dress_hub.py`:** under `"b"`, the I3 chair (on I3's induct belt) moves to the end of the line (13.6, 11.2).
- **To switch on:** set `LINE_A_LAYOUT = "b"`, regenerate the spec, rebuild. **That breaks the current flow / stations for line A until steps 2–3 land**, so it should be done together with them.

## Step 2 status (30 Oct, ~19:40): flow wired for (b), simulation only
- **`line_a_geom.py`** (new): the line A (b) geometry in one place for build_hub, flow and stations (build_hub now imports it; values identical).
- **`mocap/inductor.py`:** `Planner` plans one carton per `cycle(ready)`, so the flow can drive it as parcels arrive. `plan_cycles` wraps it; the benches' plans are identical (4 cases checked).
- **`flow.py`:**
  - `--spec` and `--sim-only <json>` (QA trace, then stop);
  - under `line_a.layout == "b"`:
    - feed y 12.25 at 0.8 m/s with an end stop just past the last mouth;
    - `d02_stub`;
    - 4 gravity tables (0.4 m/s, stop at the low end);
    - 4 induct belts (1.5 m/s) that merge onto belt A by the existing side-merge rule;
  - anything else under "b" stops with a clear message.
- **`stations.MocapInductors`** (simulation part):
  - diverters push any parcel that fits through the 0.6 m mouth into an empty table, at least 0.6 s after the last lift;
  - at the stop, the station's `Planner.cycle(ready)` gives grasp / lift / release;
  - lift takes the parcel off the table; release puts it on the induct belt at 0.22 m, held there 0.5 s for the light curtain.
- **Sim-only QA, 30 s window, seeds 7 / 11:**

  | | Seed 7 | Seed 11 |
  |---|---|---|
  | Tunnel reads | 39 | 40 |
  | Cycles per inductor | 7 / 6 / 6 / 4 | 8 / 6 / 6 / 5 |
  | Release gap, median (max) | 4.4 s (8.2 s) | 4.3 s (11.8 s) |
  | Feed queue max | 7 | 7 |
  | Collector max | 5 | 6 |
  | Booms max | 3 | 3 |
  | Conflicts | 0 | 0 |

  Layout "a" for comparison: 41 tunnel reads. The line is now **supply-limited** (the docks), so inductors wait for parcels; downstream I4 gets the fewest.
- **Not done:**
  - step 3 (workers built from the Planner's segs plus the engine's carton bake, which hands over to the flow at the curtain start);
  - diverter paddle animation;
  - S1's feed stand (8.95, 11.62) sits inside the new workstation.
- **BLOCKER for step 3: 60 % of flow parcels are mailers** (`pick_look`: 60/40, 4–6 cm thick). The engine only does the two-hand side grip on cartons. A one-hand pick for mailers is needed before S0 can use line (b) with every parcel handled honestly. Options: a one-hand mailer clip (AndyData source to find), or line A takes only boxes and mailers go to line B. The second changes the hub's flow story, so the first is preferred.

## Step 3 status (30 Oct, ~19:45): wired, first full-hub run under test
- **`mocap/line_a_worker.py`** (new): avatar + vest import, trunk clearance, the station dict, the induct QA volumes. The bench now uses it, and its QA output is identical (4 workers, 60 % mailers).
- **`stations.MocapInductors.build`:**
  - per inductor: Rocketbox avatar, his Planner's timeline cut at the last pick starting ≥ 3 s before frame 1 (rounded up to a frame);
  - `inductor.build` with each parcel's own size, the stop pose recorded at planning (`at`, `yaw`; the dims swap when the hands take the other pair of faces), one-hand for mailers, and the flow's belt start (`curtain_s` 0.3 s);
  - returns the hand frames (grasp → release) per parcel.
- **`flow.py`** (layout b):
  - builds the inductors before the bake;
  - the engine owns each parcel from grasp to release;
  - the induct-belt run carries the engine's release offset (position + yaw), easing out over 5 frames on belt A;
  - the bake accepts a full rotation for held parcels.
- **Engine:**
  - `curtain_s` (a fixed belt start; clearance recorded, not hidden);
  - per-parcel `at` / `yaw`;
  - one-hand grip (prototype, 017b);
  - per-hand orientation / finger weights, which also fix an old ~3-frame twitch before every two-hand grasp.
- **`dress_hub.py --spec`** so the (b) hub can be dressed: `build/hub_lineAb_dressed_lit.blend` (78 s).

## Step 3/4 status (30 Oct, ~20:45): first full-hub runs (reviews 017, 018)
- **Inductor bodies vs anything:** 0 rows ≥ 1 cm in every hub run (whole-hub `collision_check.py`).
- **Line A parcel rows:** 141 → 212 → 65 over runs 1–3.
- **Fixes along the way:**
  - feed frame opened at the D02 stub;
  - photo-eye diverter, with the fit checked against the table guides;
  - head zone stop on the last mouth;
  - guides square parcels (feed, induct belts, belt A);
  - engine re-clamps the set-down into the induct zone;
  - world yaw kept at the induct → belt A transfer;
  - hold over the belt ≤ 1.5 s (017 #3; overflow counted, 0 in 5 seeds).
- **Idles (017 #1, 018 #1):** every wait ≥ 0.6 s and every "beat" is a cut of 100STYLE `Neutral_ID`, chained in ≤ 6 s mirrored chunks. Pick / place timing is unchanged.
- **Release rest (018 #2):** hands hang beside the thighs (palm to thigh), not in front of the belly. The bench rose to 33 frames > 1 cm (was 25): fingertip grazes against the bench's box-shaped induct volumes in the rest → mocap blend; to verify on the real mesh.
- **Open:**
  1. reach safety net 12–15 cm (move the place root with the zone clamp);
  2. mailer pinch, per finger (thumb-swing try failed, off);
  3. line A parcel rows → 0;
  4. 2 early belt starts;
  5. dock on the full trailer wall + head ≥ 5 cm (016b);
  6. all old-motion stations → 0 rows (018 #6).

## What M5 needs, in order
1. **Geometry into the build** (`build_hub_plan.py` / `hub_spec`, then `build_hub.py`):
   - line A moved north:
     - feed belt y 12.25, x 5.6–13;
     - 4 roller tables, y 11.05–11.78, 0.68 m left of each worker;
     - side guides and end stops;
     - 4 diverter paddles;
     - 4 induct belts, 1.2 m at 45° into belt A;
   - the old feed run (y 10.85) removed;
   - the I3 chair moved;
   - walkway check: nobody crosses the feed/table aisle.

   *Estimate: 2–3 h.*
2. **Flow** (`flow.py`):
   - new Belts: the feed path, each induct belt (index, then 1.5 m/s) and the merge gap control into belt A;
   - parcel route: collector → feed → diverter k → table k → *(inductor k)* → induct belt k → belt A → tunnel;
   - the inductor's grasp/release times and the carton's world track come from the engine; the flow only owns a carton before the diverter and after the release.

   *Estimate: 3–4 h.*
3. **Stations** (`stations.py`):
   - `MocapInductors` replaces `Inductors`, wrapping `inductor.build` per worker;
   - `MocapDocks` replaces `Docks`, keeping its wall plan (columns, top-down) and its "picked carton becomes a flow parcel at the release";
   - per-avatar trunk clearance;
   - flat shoes only.

   *Estimate: 3–4 h.*
4. **Gates:** `collision_check.py` over the whole hub (not just the station pieces), the spacing row, and the 014_GO gates. Then fix what they find. The benches still have 2–25 % frames with 1–4 cm finger/forearm grazes.

   *Estimate: 4–8 h.*
5. **Stations not on mocap yet:**
   - line B (gaylords, the same engine, 3–4 h);
   - bagger and cage pushers (100STYLE walks + hands on the sack/cage, 6–8 h);
   - opener and tech (2–3 h).

**Total:** roughly 23–34 working hours before S0 and S2 pass the gates with every worker on mocap.

## Known open items
- **Dock:** arm and finger contact with the neighbouring wall column on overhead reaches.
- **Line A:** single-frame finger contact at grasp and release. The cycle is 3.1–4.4 s, paced by the gravity table.
- **Female avatars:** Female_Adult_09's hands fail the side-face grip; F01 and F17 are untested. Line A is all male for now.
- **Not yet built:** polybags and cartons over 40 cm (one-hand pinch or hug); the label-up flip (one-hand re-grip); finger wrap under the bottom edge.
- **Visual fixes:** the hair-card opacity close up (Rocketbox), and the dock-leveler / CAM_15 speckle.
