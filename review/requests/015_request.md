# Request 015: M3 (014_GO): the line-A inductor on mocap, 30 s, in the hub (CCTV + front + side)

From the builder. Everything is under **`Spoor/qa/review/m3_hub/`**.

## Proof
- **`m3_inductor_cctv_front_side.mp4`**: 30 s at 10 fps (the CCTV rate), 300 frames, inductor I2 (Male_Adult_04) at the M0 position (x 8.6). Each frame shows:
  - **CCTV:** the hub's own **CAM_01**, cropped around the worker;
  - **front**, from across belt A;
  - **side.**
  - Frame number, time and phase (reach to carton n / carton n in the hands / released) are burned in.
- **`m3_sheet_1fps.jpg`**: 1 fps sheet.
- **`dense/`**: your 014d #2 crops, every frame (0.1 s) for 1.5 s around a grasp and a release (carton 1), from each hand's side. Sheets: `dense_grasp.jpg`, `dense_release.jpg`.
- **`heads/`**: bare-head sheet, front and side at f001/f150/f300 (014b): `heads_sheet.jpg`.
- **`m3_qa.json`**: every number below, measured on Blender's **evaluated** pose and deformed mesh.

## 1. Pipeline (014_GO steps 7–9), `assets/hub/mocap/`
- **`clips.py`:**
  - cuts the AndyData takes on their labels;
  - boundaries snapped to a wrist-speed minimum within ±0.15 s;
  - sidecar `assets/mocap/clips.json` with grasp/lift/release times, root and foot travel, yaw, hand height, two-hand flag and posture.
- **Clip choice, from the data:**
  - AndyData carries walk about 2 m between tables, so a whole cycle never fits a planted inductor. Only two stationary pieces are used:
    - **pick:** end of the reach, the two-hand pick, and the 60–85° turn after the lift;
    - **place:** set-down and the start of the release.
  - Filters: two-handed; pick hand height ≥ 0.9 m; place hand height ≤ 1.15 m (belt height, not a shelf); travel < 0.45 / 0.35 m.
  - **Pool:** 4 picks (5124 ×2, 2274, 541) and 4 places (5124, 2274, each also mirrored), from 3 performers.
- **`inductor.py`, per carton:**
  - pick clip then place clip, each at a **constant retime ratio of 1.0–1.15**: lab pace is slower than a hub's, and there is no slow motion;
  - if the next carton isn't at the stop yet, the worker holds;
  - **anchored at the event:** the pick so the palms meet the carton at the grasp, the place so the worker faces belt A at the release with the body clear of the belt. **The pick's end heading is chained to the place's start heading,** so no join spins the worker;
  - **inertialized joins** (offset decays over 0.3 s, no crossfade);
  - **foot locks** (M2);
  - **hand IK** (two-bone, ramped, pole = the mocap elbow pushed outward while carrying, elbows wide);
  - **carton world-matrix bake:** table → hands → belt.
- **Corrections on top of the mocap (each measured):**
  - **Un-stoop (your #3):** the lab tables were lower than our 88 cm table end. Where the hand targets sit above the mocap hands, the upper body straightens (pivot back about Spine1, up to 30°) instead of the arms bending up out of a deep stoop. Only around the pick.
  - **Reach lean:** where the belt is beyond the arm, the upper body leans in (about Spine1, ≤ 28°).
  - **Hands on the carton:**
    - palms rotated flat onto the side faces;
    - fingers straightened toward the bind pose, along the face (20° down at the table, level over the belt);
    - **thumb swung into the palm plane:** a thumb on the palm side went 4.5 cm through the carton;
    - grip 5 cm from the body-side edge and 5.5 cm under the top edge, so the forearms come over less of the carton.
  - **Trunk clearance:** a held carton never comes within 21 cm of the spine line; it is pushed forward, with the hands following.

## 2. Your 014d points
| # | Point | Result |
|---|---|---|
| 1 P0 | Turn direction | **Left to the table** before each grasp (+59° to +84°), **right back to the belt** with the carton (−59° to −83°). At every grasp the pelvis faces the carton within **3–14°**: the worker never turns their back to the table. Mirroring is applied only to takes whose post-lift turn went left (away from where our belt is) |
| 2 P0 | Palms on the side faces ≤ 1 cm | Hand skin to carton surface on hold frames: **p05 −6.2 / p50 −2.5 / p95 −1.9 mm** (palm skin pressed 2–6 mm into the cardboard). **3 hold frames** are outside ±1 cm (−10.1, −16.2, −22.2 mm, all at a release). Finger wrap under the bottom edge: **not done**. The grip is high on the side face (forearm clearance), so fingers lie flat along the face. Wrapping under the bottom needs a low grip plus a lift-off tilt; planned for M4 |
| 3 P1 | Hand height at the grasp, source vs ours | Source palms (scaled to the avatar) **0.77–0.91 m**; our grip **0.975–1.03 m**. The un-stoop takes up to 30° of the difference; the IK takes the rest |
| 4 P1 | Label-up flip, ~1 in 3 | **Not done in M3.** A two-hand flip without a re-grip rotates the hands in the face plane until the fingers point backward. It needs a one-hand re-grip, which comes with M4. Our test cartons carry no label yet, so a flip would not show |
| 5 P2 | Belt indexing | Kept: the placement belt waits until both hands are off (0.3–0.6 s per carton, from a sweep check against the hand targets), then accelerates to 1.5 m/s |
| 6 P2 | Desync | At M4 (4 inductors): avatars Male_Adult_04 / Female_Adult_06 / Male_Adult_09 / Male_Adult_05 (all flat shoes); own seed and random start offset each; neighbours start on different takes |

## 3. 014b fixes in this proof
- **Feed → table:**
  - a yellow **diverter paddle** at the table mouth swings 45° in 0.2 s as the carton arrives, then back;
  - the carton crosses the mouth, which has a gap in the feed belt's near frame, onto the table head;
  - it rolls down at **0.4 m/s** to a low end stop;
  - **one carton on the table at a time:** the next is diverted when the previous one is lifted. A second carton held at the table head left no room for the worker's forearm on this 0.8 m table;
  - the stop is level with the worker's hip line;
  - **skewed rollers** run each carton against the operator-side guide, which takes 13 cm off the reach.
- **Table guides** sit 3 cm above the rollers. The end stop is a low plate (top 0.92 m).
- **Spacing row / aisle:** one worker here, so the spacing row comes with M4. No walker uses the feed/induct aisle.
- The **I3 chair** is still in the scene (visible right of I2 in the front view). It is removed when M5 wires the layout into build_hub.

## 4. QA (30 s, 10 cartons)
| Gate | Result |
|---|---|
| Cycle | 2.7–3.2 s (mean 2.97); spec 2.5 ±0.5 |
| Foot skate | max **3.7 mm** (41 contacts); gate < 20 mm ✔ |
| Ground penetration | **0** frames ✔ |
| Hand to carton while holding | p95 within 2 mm; 3 frames > 1 cm (above) |
| Yaw while holding | 60–84° per carton, all < 90° ✔ (the feet step within the source's own turn) |
| Collisions > 1 cm, every frame vs table, rollers, guides, stop, feed belt, belt A volume and all cartons | **6 frames of 300**: the first approach (frames 3–5, left fingers 2.3–3.8 cm into carton 0), two release frames (left pinky 1.6 / 2.2 cm), one end-stop graze (right pinky 1.1 cm). **Not gate-clean yet.** That is the owner rule, and it stays a blocker for M5 |
| Model vs Blender | 0.0 mm (every bone head) |

**Not yet checked:** the official `collision_check.py` against the whole hub. This proof checks the M0 pieces plus belt A's volume. The full check runs at M5.

## 5. Question for M4: four inductors on one belt don't fit (measured; my M0 error)
I dry-ran line A with all 4 inductors (`m4_line_a.py`, 15 s). Avatars Male_Adult_04 / Female_Adult_09 / Male_Adult_09 / Male_Adult_05, own seeds, start offsets 1.4–2.7 s. Spacing is fine: min 0.57 m between bodies, 0 frames under 0.3 m.

**The belt is the problem.** Belt A runs +x at 1.5 m/s, so every carton I1 places passes I2, I3 and I4.
- **Gap control** (hands kept out of the passing cartons' path from 1.0 s before the release to 0.9 s after it) makes I2–I4 wait **4 s** (the cap) on most cartons. I3 finished **no** carton in 15 s.
- Cartons held while waiting still get **hit** by cartons passing underneath.
- **The arithmetic:** 4 operators at ~3 s per carton is 1.3 cartons/s, a 1.1 m pitch at 1.5 m/s. A downstream operator never gets the ~2 s gap they need.
- Real cross-belt practice is **one induct point per operator**: each operator has their own short induction belt joining the sorter at 30–45° (research table: Equinox, BEUMER). My M0 put 4 operators on one belt and called each a "point". That is wrong.

**Options** (your call; until you answer I continue M4 with option a):
- **(a)** Keep belt A, but **staff 2 inductors** (I1 + I3, 3.2 m apart), with gap control. Measured on the bench, one inductor runs 2.7–3.2 s per carton, so two have room.
- **(b)** **Four induct points:** each inductor gets a 1.2 m induction belt angled 30–45° into belt A downstream (geometry change in build_hub; about 2 h).
- **(c)** Keep 4 on belt A as **singulators**, not inductors: each waits for gaps, at 6–10 s per carton.

## 6. Next
- **M4 (20:30):**
  - line A with 4 inductors (`m4_line_a.py`, written), including the spacing row;
  - then the dock unloader on the same pick/place engine (wall tiers → boom nose at 103 cm);
  - cage pusher and bagger on 100STYLE walks.
- **Honest timing:** 4 inductors + dock by 20:30 is realistic. The bagger and cage pusher probably land after M5.
- **M5:** S0 + S2 with line A wired in for real (build_hub / flow / stations), full gates.
