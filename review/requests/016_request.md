# Request 016: M4 (014_GO) part 1: line A with four inductors on their own induct belts (your 015 choice (b))

From the builder. Evidence is under **`Spoor/qa/review/m4_line_a/`**.

## Proof
- **`m4_line_a_cctv_front.mp4`**: 30 s at 10 fps. Top: the hub's **CAM_01** (crop over line A). Bottom: a front view along the line. Each frame shows the frame number, time and each worker's next grasp.
- **`m4_sheet_1fps.jpg`**: 1 fps sheet.
- **`m4_qa.json`**: everything below, measured on the evaluated pose.

## 1. Layout (b), `assets/hub/mocap/m4_line_a.py`
- **Line A moved 0.9 m north:** workers at y 11.15, roller tables y 11.05–11.78, feed belt y 12.25 (x 5.6–13).
- **One induct belt per operator:** 1.2 m × 0.5 m. Each starts 0.5 m in front of the worker (0.15 m to their right) and runs 45° (+x, −y) into belt A's edge.
  - **Own indexing:** the belt stands while the hands are on it, then starts at 1.5 m/s.
  - **Merge gap control by the conveyor:** a carton that reaches the end waits there until belt A is clear at the merge (its size + the passing carton's + 0.15 m), then rides belt A.
  - The people never wait for gaps any more.
- **Tables:** 0.68 m to the worker's left (was 0.62); diverter paddles at all four mouths. The next carton is diverted 0.6 s after the lift, so the hands are clear when it slides onto the table head, and it rolls down at 0.4 m/s.
- **Workers:** I1 Male_Adult_04 (yellow vest), I2 Male_Adult_12 (orange), I3 Male_Adult_09 (lime), I4 Male_Adult_05 (yellow). All flat shoes. Each has its own seed (clip order, retime ratios, carton sizes) and a start offset of 1–4 s.
  - Female_Adult_09 (flat shoes, fetched today) failed the hand grip: her palms ended flat on the carton's top. She stays off line A until I fix that.

## 2. Your 015 fixes
| # | Fix | Done |
|---|---|---|
| 1 | No repeating cycle | Random pick and place per carton; never the same pick twice in a row; no (pick, place) pair repeated within 3 cartons; ratio **0.92–1.12**; an **extra beat** (0.6–1.1 s pause, head turned ~25° up the line, breathing sway) on ~1 in 6 cartons |
| 2 | Hunch at the set-down | Trunk flexion **capped at 38°** at the set-down (pivot back about Spine1 by the excess); head pitched up 12° (eyes on the belt). The place spot is nearer now (0.22 m along the induct belt, 0.5 m in front of the worker) |
| 3 | Cartons | Mixed sizes 18–40 × 14–34 × 12–30 cm; four colours (brown, dark, kraft, white); a **white label** on the top (70 %) or the side. Polybags and > 40 cm cartons are **not yet in**: they need a different grip (one-hand pinch / hug). Planned with the label flip |
| 4 | Release / first approach | Palms open 1.2 cm off the faces over the last 2 frames before the release; the belt waits for the hands. Start offsets ≥ 1 s, so no first approach is on screen. **Safety net:** where an arm cannot reach its socket, the carton follows the hand the IK did reach (no hand inside the carton) |

## 3. QA (30 s, 4 workers)
| Worker | Avatar | Cartons in 30 s | Cycle (s) | Foot skate max | Ground pen | Yaw while holding | Trunk clearance (own body) | Frames > 1 cm |
|---|---|---|---|---|---|---|---|---|
| I1 | Male_Adult_04 | 8 | 3.3–3.6 | 3.1 mm | 0 | 62–82° | 0.244 m | 10 |
| I2 | Male_Adult_12 | 9 | 3.1–3.9 | 3.0 mm | 0 | 67–83° | 0.234 m | 6 |
| I3 | Male_Adult_09 | 8 | 3.2–3.9 | 3.0 mm | 0 | 58–84° | 0.232 m | 2 |
| I4 | Male_Adult_05 | 8 | 3.1–4.4 | 8.3 mm | 0 | 63–83° | 0.278 m | 14 |

- **Spacing:** the closest two bodies get is **0.40 m**; **0** frames under 0.3 m.
- **Collisions:** **32 frames over 1 cm in 1,200 worker-frames (2.7 %).** It was ~3 % with the shared belt and many more before the fixes. None against the tables, rails, induct belts or belt A.
  - Fingers (mostly the little finger) on their own carton at a grasp or release, 1.1–4.1 cm.
  - A forearm on the carton during the first approach or the lift, 1.9–2.6 cm.
  - I2's chest (Spine1) touching carton 9, 1.2–1.4 cm.
  - I1's right hand on the end stop for 5 frames, 1.3–1.5 cm.
  - **Not gate-clean yet.**
- **Why:** a female and a stocky avatar exposed two things.
  - The bind-pose finger curl: fixed with a 5.6 cm palm offset.
  - Trunk depth: clearance is now measured per avatar, 0.23–0.28 m.
  - What remains is single-frame finger contact at grasp/release edges.
- **Cycle 3.1–4.4 s**, above your 2.5 ±0.5. **The feed sets the pace now.** The next carton is diverted 0.6 s after the lift and rolls 0.58 m at 0.4 m/s (your top speed), so it reaches the stop 2.45 s after the lift. A faster pace needs either a shorter roll (a second hold-back stop nearer the end) or a faster table. Your call.

## 4. Not done / next
- **Dock unloader (M4 part 2):** built on the same engine and **rendering now** (request 016b at ~20:30): D05 south side, carton wall in the lorry worked top-down, turn right, set down on the boom nose (top 1.00 m), 3.3–3.7 s per lift. **Known before the render:** his arms brush the neighbouring wall column on overhead reaches. I'll report the numbers as they are.
- **Bagger and cage pusher:** after M5 (agreed).
- **M5:** wire line A (b) into build_hub / flow / stations: S0 + S2 with full gates. The remaining collision frames are the blocker.
