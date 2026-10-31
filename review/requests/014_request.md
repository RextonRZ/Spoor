# Request 014: A4 interim 2 (answers review 013): headwear rebuilt, collisions, mesh hygiene, bag change

From the builder. **Not a pass request yet:** the gate isn't clean. All evidence is under **`Spoor/qa/review/req014/`**: repo root, then `qa/review/`, not `assets/hub/build/...`. Request 013's evidence was in `Spoor/qa/review/req013/`; I'm sorry the paths were ambiguous.
- **Follow-cams and 1 fps sheets** are from test 17 (S0), saved as `assets/hub/build/req014_S0.blend`.
- **Head sheets** are from test 18, which carries the final cap fix described in §1. That blend is `assets/hub/build/req014b_S0.blend`.

## 1. Headwear (review 013 P0): rebuilt, rigid, no shrinkwrap
| Your point | What I did |
|---|---|
| Crown covers the face, mushroom crown | **New cap mesh.** An open crown (no hidden bottom disc), 10 cm above the band. The band sits 7.5 cm below the top of the head, about 2.5 cm above the brows. |
| Duckbill brim | A curved brim about 7 cm long round the front 140°, its sides curving down, joined to the band. |
| Torn band, crown torn open (shrinkwrap) | **No shrinkwrap.** Each cap is shaped once in the rest pose, on that worker's own copy of the mesh: its band follows the head's outline + 6 mm, and the crown keeps ≥ 8 mm from the head at every height up to 8 cm. It is parented to the head bone; nothing deforms at run time. |
| Bun / ponytail through the crown | The one cap wearer with a bun (induct_2, Female_Adult_04) **no longer wears a cap.** No other cap wearer has a bun or ponytail. |
| D05_n "hard hat with no head" (f81, f251) | **Not a separation: the head camera was blocked.** At f81 and f201 it sat behind the mate; at f91, f191 and f251 it was inside the carton wall, which gave the empty grey frames. `qa_heads.py` now picks a view with a clear line of sight. The hat stays within the follow limits (below) in every frame. |
| New QA | **accessory_off_head** (your accessory_follow): ≤ 1 cm and ≤ 3° from the fitted pose relative to the head bone, every frame. **accessory_face:** nothing of the cap in front of the face below the brow line. Both are gate rows, as is **accessory_fit**, which now measures only the band edge. |

**Known in these sheets (fixed after test 18):** the Male_Adult_12 caps (cage_1, inductB_1) have a lumpy crown. The clearance pushed single points out over hair spikes; each height ring of the crown is now inflated evenly. D02_n shows one hair point through the crown, fixed by the same change. A thin dark line at the brim root is the forehead seen between the band and the brim from above.

**Sheets:** `heads/<worker>_front_sheet.jpg` and `_side_sheet.jpg` for every hat wearer, every 10 frames. Headwear QA rows in test 18: **0** (accessory_fit, accessory_face, accessory_off_head).

## 2. Collisions (owner rule)
| Test | S0 | S2 | Main change |
|---|---|---|---|
| 13 (req 013) | 933 | 991 | – |
| 14 | 817 | 873 | boom frame as an arm obstacle; dock hands off the boom |
| 16 | **611** | 645 | docks wait at the wall while the mate sets down (no chest hold); reach path over the top; inductors' hip shift 3 cm |
| 17 | 717 | 614 | regression: rework-bin landings under the reject chute's lip (118 rows from one parcel). Fixed in test 18 |
| **18** | 866, or **579** without one parcel's 287 rows | 869, or **614** without one parcel's 255 rows | Both parcels lie in the rework bin's wall: the wider bin spread didn't allow for parcel size. Fixed after the run (landings a parcel radius inside the walls). |

**Phase attribution:** each row is mapped to the worker's pick phase (reach, settle, pull, hold, turn, place). That showed the dock rows were almost all in "hold", where the carton was held against the chest while waiting for the mate. The docks now wait with their hands on the carton in the wall; their contact error went from p95 13 cm to 0.

**Per worker (test 18 S0):**
| worker | avatar | cartons / window | contact err p95 / max (cm) | hits: parcel / static / sack / person / cage | worst (cm) |
|---|---|---|---|---|---|
| worker_bag_1 | - | - | - | 0 / 0 / 60 / 0 / 1 | 8.1 |
| worker_cage_1 | Male_Adult_12 | - | - | 0 / 0 / 0 / 0 / 1 | 11.4 |
| worker_cage_2 | Male_Adult_04 | - | - | 0 / 0 / 0 / 0 / 1 | 10.3 |
| worker_dock_D02_n | Male_Adult_05 | 6 | 0.0 / 0.0 | 37 / 0 / 0 / 0 / 0 | 5.5 |
| worker_dock_D02_s | Male_Adult_09 | 6 | 0.0 / 0.0 | 15 / 0 / 0 / 0 / 0 | 4.7 |
| worker_dock_D05_n | Male_Adult_12 | 6 | 0.0 / 1.6 | 16 / 0 / 0 / 0 / 0 | 9.2 |
| worker_dock_D05_s | Female_Adult_07 | 6 | 0.0 / 0.0 | 17 / 0 / 0 / 0 / 0 | 3.4 |
| worker_inductB_1 | Male_Adult_12 | 10 | 4.07 / 27.34 | 47 / 1 / 0 / 0 / 0 | 7.6 |
| worker_inductB_2 | Female_Adult_04 | 8 | 7.81 / 26.69 | 27 / 4 / 0 / 0 / 0 | 6.6 |
| worker_inductB_3 | Male_Adult_09 | 4 | 0.0 / 8.6 | 15 / 0 / 0 / 0 / 0 | 5.0 |
| worker_induct_1 | Male_Adult_04 | 5 | 0.0 / 8.67 | 45 / 15 / 0 / 0 / 0 | 5.8 |
| worker_induct_2 | Female_Adult_04 | 7 | 20.16 / 41.13 | 34 / 0 / 0 / 0 / 0 | 10.1 |
| worker_induct_3 | Male_Adult_09 | 7 | 7.42 / 28.0 | 49 / 10 / 0 / 0 / 0 | 6.5 |
| worker_induct_4 | Female_Adult_06 | 7 | 3.76 / 15.5 | 46 / 4 / 0 / 0 / 0 | 14.9 |
| worker_open_1 | Female_Adult_07 | 4 | 7.54 / 23.56 | 27 / 7 / 0 / 0 / 0 | 7.0 |
| worker_tech_1 | - | - | - | 0 / 5 / 0 / 0 / 0 | 1.3 |

**What remains:**
- 1–3 cm grazes of hands and forearms on the carried carton, in the turn.
- Bellies of line A inductors against the induction-belt frame. The aisle between the two belt frames is 0.45 m; the body barely fits.
- The bagger's hands at the sack's neck.

Plan in §6.

## 3. Mesh hygiene (review mesh_hygiene): first report
- **Detector:** `assets/hub/mesh_hygiene.py`; the report is in `Spoor/qa/review/mesh_hygiene/` and `assets/hub/build/qa/mesh_hygiene/`. The gate reads it: `qa_gate.py --hygiene`, required by `render_batch.sh`. Any same-facing z-fighting face fails.
- **Cleanup at the source** (`dress_hub.hygiene_pass`, every rebuild), on 136 static objects:
  - vertices merged under 0.1 mm, within each connected part (welding parts that only touch made non-manifold edges);
  - degenerates dissolved;
  - **n-gons 7,941 → 0** (Beauty triangulation, no fans);
  - normals made consistent on closed meshes;
  - smooth shading only below 30°.
- **Before/after check:** every object's bounding box and materials are unchanged (`build/qa/mesh_hygiene_diff.json`).
- **Z-fighting (same-facing faces within 1 mm):**
  - the columns and trusses were flush with the walls; they are now 3 mm clear;
  - the slab edge and the wall corners are fixed, and so are the door plinths, whose tops lay in the slab's top plane in every doorway;
  - floor decals now sit ≥ 1.2 mm apart.
  - Count: 3,062 → ****9**: conveyor/scan tunnel, a carrier, the office glass, one sign; next on the list**. Undersides facing the floor are not counted, because no camera sees them.
- **Rexton's D01 "spiderweb":** test renders are in `Spoor/qa/review/mesh_hygiene/d01_test/`: workbench as the QA renders it, without textures, EEVEE at 2/16/64 spp, and a camera moved 5 cm.
  - **QA follow-cam (where he saw it):** the closed shutter is one plain box face. The radiating streaks are workbench's stencil shadow volumes on big flat faces. Shadows are now off in the QA workbench.
  - **Final CAM_01:** the shutter's slat texture aliases into bands at the grazing angle, which matches the line aliasing at its lower left. Final renders now use 16× anisotropic filtering (Blender's background default is 2×).
- **The B2 still items:**
  - The notice board that overlapped the electrical board (CAM_14/16) is moved 2 m away; the boards sit 3 mm proud of the wall.
  - CAM_14's "yellow sign leaning against nothing" is the yellow forklift guard round the column at (48.3, 25.0). The lens distortion makes it read as a board; it stands on the floor.
  - The CAM_15 speckle is not checked yet.

## 4. Follow-cams and 1 fps sheets (all MP4s are in `follow/`, frame number burned in)
- **Front:** line A inductors 1–4 and line B inductors 1–3.
- **Hall angle:** dock unloaders D05_n and D02_s.
- **Side:** cage pushers 1 and 2 (009e).
- **Also:** the bagger and the opener.
- **1 fps sheets:** `stills/<job>_sheet.jpg`.

## 5. Your answers, applied
- **Loop occupancy 27–29 %:** accepted, and stated on every scenario card (`make_cards.py`).
- **Bag change**, as you described:
  1. The sack slumps tied on the floor and is pulled out under the front rail.
  2. The bagger **walks backwards dragging it with both hands on the neck**, bent over it, at a slower pace. Backward walking is new in `contact.walk`: the walk clip plays reversed and the body faces against the travel.
  3. At the cage: a **two-hand squat lift**, up first, then across into the cage.
  4. The new-bag time is unchanged, so C07's closed window and the recirculation stay the same.

  I found no bag-change footage in the realism plan's reference videos, so this sequence is based on your description.

## 6. Next 2 hours (to ~18:00)
1. Inductors: the belly against the belt frame, and the forearm grazes in the turn (the carton's pose relative to the hands in the turn).
2. The bagger's neck hold (palms now 6.8 cm off the neck axis).
3. The remaining z-fight pairs, and the CAM_15 speckle.
4. Then **S2 gate-clean first** (009d-b). Target: S0 < 400, S2 < 400.
