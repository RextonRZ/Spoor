# M5 plan: from the mocap benches to S0 / S2 (written 30 Oct, evening)

## Where things stand
- **Built and proven** (`assets/hub/mocap/`):
  - the retarget (M2);
  - the inductor engine `inductor.py` (M3), which also drives the dock unloader;
  - line A with four induct points (`m4_line_a.py`, request 016);
  - the dock unloader at D05 south (`m4_dock.py`, request 016b).
- **All of them are standalone scenes:** the lit hub with their own geometry added and their own cartons. **None is in `flow.py` yet.** S0–S5 still use the old procedural workers (`stations.py` + `contact.py`).

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
