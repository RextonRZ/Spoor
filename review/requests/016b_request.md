# Request 016b: M4 part 2: dock unloader on the mocap engine (D05, south of the boom). Plus 016 fixes, measured

From the builder. Evidence is under **`Spoor/qa/review/m4_dock/`**.

## Proof
- **`m4_dock_cctv_door_behind.mp4`**: 30 s at 10 fps. CAM_02 (crop on the D05 door) | inside the trailer by the door | behind him. Frame, time and phase are burned in.
- **`m4_dock_sheet_1fps.jpg`**: 1 fps sheet.
- **`m4_dock_qa.json`**: the QA.

## How it is built (`assets/hub/mocap/m4_dock.py`)
- **The dock is line A turned 180°.** Facing the carton wall in the lorry, he picks (the wall is the "table" at his front-left). He turns right about 90° and sets the carton on the boom nose in front of him (the boom is the "belt", running out of the lorry at 0.8 m/s, top **1.00 m**). The station is built in that local frame under a parent empty, which is then put on the dock, so every engine convention stays valid.
- **The wall:** loose-loaded columns with 12 cm gaps (room for a hand) on his side of the boom, plus two rows behind, worked **top-down** (BEUMER).
- **Pick clip per carton**, from the AndyData pool nearest its grip height:
  - standing picks for 1.0–1.65 m (IK + un-stoop for the top tier);
  - bent picks at 0.86 m;
  - crouch picks at 0.60–0.69 m.
- **Pace:** retime 0.85–0.95 (slower than an inductor), **3.3–3.7 s per lift** (014_GO: 3.5–4 s).
- **At a wall:**
  - no reach-lean during the pick (it put his head into the wall);
  - stand further back for low cartons (a crouch puts the knees forward);
  - elbows half out, half down;
  - trunk capped at 45° and the neck lifted at the pick (no folding over the column into the rows behind).

## QA (30 s)
| | |
|---|---|
| Cartons | 9, top-down: 1.65 / 1.61 / 1.37 / 1.30 / 1.10 / 1.04 / 0.86 / 0.69 / 0.60 m |
| Foot skate | max **3.0 mm** |
| Ground penetration | **0** frames |
| Trunk clearance (his body) | 0.234 m |
| Frames > 1 cm | **54 of 300.** Fingers 37 (mostly against the next carton in the column / the column beside), forearm 12, upper arm 5. Worst 10 cm (a finger). **Before the wall rules: 76, including head 7–11 cm into the back row and knees in the bottom tier. Those are gone** |

**Not gate-clean. Worse than line A.** Reaching into a stacked wall is the hard case: the hands go between cartons that touch. Next:
- pull the carton out 10 cm before lifting it (real unloaders tip or slide it toward themselves first);
- give the fingers a narrower, flat approach at the wall.

## 016 fixes, measured on line A (15 s, 4 workers; the M4 video in request 016 is from before these)
| # | Fix | Result |
|---|---|---|
| 1 | No palm-up empty hand after the release | The hand comes off the face (0.2 s), then **to a rest point in front of the hips within 0.3 s**, with the hand orientation and finger flattening **fading out over the same 0.3 s** (palms back to the mocap's relaxed pose, fingers relax), then back to the mocap path. The rest point stays ≥ 15 cm above the belts, because relaxed fingers hang ~10 cm and first dragged through the induct belt |
| 2 | Head over the carton at the set-down | The neck now pivots back as needed to keep the **eyes ≥ 25 cm above the carton top** (≤ 35° extra) |
| 3 | Grip at mid-height | **Measured, and not taken:** collision rows per 15 s were **16** with the grip 5.5 cm under the top edge, **28** at 9 cm, **35** at mid-height. The lower grip puts the forearms and hands into the carton. I kept 5.5 cm. **New QA row as asked:** each hand's skin to the held carton, every hold frame. Medians are −2.5 to +0.3 mm on I1, I2 and I4, and **+7.9 mm on I3** (Male_Adult_09's palm sits 8 mm off, within 1 cm). Frames > 1 cm on either hand are mostly the 2 release frames where the palms open on purpose. I'll exclude those 2 frames from the flag unless you want them counted |
| — | Fingers | Each finger is **un-curled at its knuckle into the palm plane** while holding. The bind pose curls the tips up to 5 cm, so the palm lay off the carton |
| 5 | Hold-back stop | **Not done yet.** A carton waiting 0.3 m behind the one at the stop sat right where the left hand and forearm go (measured earlier tonight). It needs a stop ≥ 0.45 m back, so the next carton rolls 0.25 m in ~0.6 s. Next on the list |
| 6 | A woman on line A | Female_Adult_17 (flat shoes) with the finger un-curl: finger contacts gone. Her **hips still touch the carton at the lift** (3.7 cm): her trunk clearance needs measuring at hip height. Next |
