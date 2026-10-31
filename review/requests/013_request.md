# Request 013: A4 interim milestone (owner rule, 009d/009e, progress nudge 12:35)

From the builder. **This is not a pass request.** The zero-interpenetration gate is not clean yet. This request shows:
- the measured state, and what changed since 09:38;
- the evidence 009e and the 12:35 nudge asked for;
- what comes in the next 2 hours.

Everything here comes from one build: test 13, S0, 30 s, 10 fps, the current code. It is saved as `assets/hub/build/req013_S0.blend`.

## 1. Collision trend (owner rule: any two things ≥ 1 cm into each other, every frame; `collision_check.py`)
"Frame-hits" are one row per frame per touching pair. One 2 cm graze through a 6 s pick is about 60 rows.

| When | Test | S0 total | parcel–person | person–static | parcel–static | parcel–parcel | person–sack | S2 total |
|---|---|---|---|---|---|---|---|---|
| 09:38 (owner rule) | a1 | **3994** | 1566 | 670 | 1195 | – | – | – |
| 10:47 | a3 | 3799 | 1959 | 691 | 882 | 110 | 129 | – |
| 11:38 | a5 | 3474 | 1615 | 1122 | 396 | 140 | 129 | – |
| 12:00 | a6 | 2659 | 1708 | 333 | 289 | 128 | 129 | – |
| 12:40 | a9 | 2214 | 1410 | 346 | 275 | 104 | 54 | – |
| 13:07 | a10 | 1744 | 1257 | 302 | 52 | 78 | 47 | 1791 |
| 13:26 | a11 | 921 | 582 | 142 | 71 | 72 | 47 | 956 |
| **13:58** | **a13** | **933** | **561** | **210** | **53** | **41** | **48** | **991** |

- Sack–static: 18. Cage–person: 2.
- Per pair type, by object pair, by body part, and the worst 20: `qa/review/req013/collisions/collisions_summary.txt`. The full rows are in `collisions.csv`.
- **The 12 largest remaining groups, with close-ups at each group's deepest hit:** `qa/review/req013/collisions/crops/`. The index is `groups.txt`; there are two views per group.

| # | Frame-hits | Group | What it is |
|---|---|---|---|
| 1 | 37 | dock D02_n forearm × boom frame | Arm resting on the boom's side frame at hip height. |
| 2 | 33 | bagger's left calf × tied sack | Fixed after test 13: the sack is carried 0.55 m out instead of 0.46. |
| 3 | 28 | dock D05_n forearm × boom frame | Same as #1. |
| 4, 5, 9 | 21–27 | dock forearms × the carton held | The carton is held close; the forearm runs along its side. |
| 6, 11 | 19–26 | inductors 1 and 4 spine × induction belt frame | Leaning over the belt to set a parcel down; the belt's side frame stands 4 cm above it. |
| 7, 10 | 20–24 | dock D05_n upper arm / chest × the carton held | Carton held against the chest. |
| 8, 12 | 19–23 | inductors' forearms × belt frame or parcel | – |

**Per worker (S0, test 13).** Cartons are counted per 30 s window, measured from the baked carton tracks the render uses (a release = the carton leaving the hands). Contact error is the palm-to-face distance while gripping.

| worker | avatar | cartons / 30 s | contact err p95 / max (cm) | hits: parcel / static / sack / person / cage | worst (cm) |
|---|---|---|---|---|---|
| worker_bag_1 | Male_Adult_09 | – (bag change) | – | 0 / 0 / 65 / 0 / 1 | 8.2 |
| worker_cage_1 | Male_Adult_12 | – | – | 0 / 0 / 0 / 0 / 1 | 11.4 |
| worker_cage_2 | Male_Adult_04 | – | – | 0 / 0 / 0 / 0 / 1 | 10.3 |
| worker_dock_D02_n | Male_Adult_05 | 6 | 2.7 / 11.2 | 58 / 37 / 0 / 0 / 0 | 8.3 |
| worker_dock_D02_s | Male_Adult_09 | 6 | 0.0 / 8.9 | 78 / 13 / 0 / 0 / 0 | 6.0 |
| worker_dock_D05_n | Male_Adult_12 | 6 | 13.2 / 34.4 | 69 / 28 / 0 / 0 / 0 | 10.4 |
| worker_dock_D05_s | Female_Adult_07 | 6 | 0.0 / 7.6 | 43 / 1 / 0 / 0 / 0 | 6.0 |
| worker_induct_1 | Male_Adult_04 | 5 | 0.0 / 2.5 | 46 / 26 / 0 / 0 / 0 | 6.7 |
| worker_induct_2 | Female_Adult_04 | 7 | 16.3 / 32.9 | 37 / 6 / 0 / 0 / 0 | 7.4 |
| worker_induct_3 | Male_Adult_09 | 7 | 6.4 / 20.2 | 52 / 23 / 0 / 0 / 0 | 7.2 |
| worker_induct_4 | Female_Adult_06 | 7 | 2.1 / 9.2 | 43 / 19 / 0 / 0 / 0 | 11.9 |
| worker_inductB_1 | Male_Adult_12 | 11 | 2.8 / 19.0 | 45 / 8 / 0 / 0 / 0 | 5.5 |
| worker_inductB_2 | Female_Adult_04 | 9 | 9.8 / 23.8 | 54 / 7 / 0 / 0 / 0 | 6.1 |
| worker_inductB_3 | Male_Adult_09 | 5 | 0.0 / 9.5 | 21 / 0 / 0 / 0 / 0 | 4.6 |
| worker_open_1 | Female_Adult_07 | 4 | 8.0 / 23.8 | 27 / 7 / 0 / 0 / 0 | 7.0 |
| worker_tech_1 | Male_Adult_05 | – | – | 0 / 5 / 0 / 0 / 0 | 1.3 |
| worker_walk_1, worker_walk_2 | – | – | – | 0 | 0 |

- The bagger's sack hits come from test 13; they were fixed after it (see #2 above).
- Dock D05_n's contact error is a reach problem while holding (p95 13 cm). It is on the list below.
- The cage pushers' one cage hit each is a toe for 1 frame as the cage rolls into the trailer.

## 2. What was wrong and what changed (since request 009)
| Group (09:38 count) | Cause found | Fix |
|---|---|---|
| Fingers in every carton (~850) | **Bug:** Rocketbox (3ds Max Biped) finger bones don't point along the finger. "Flat" fingers were laid flat by their bone axis, so the real fingers pointed across the palm, 3–5 cm into the face being gripped. | Flattened along the actual finger chain (each joint's head to the next joint's head). |
| Forearms through carton corners (~700) | The palm sat on the side face, so the forearm ran along that face and dipped 1–5 cm inside it. With the top grip, the palms sat mid-lid with the elbows lower than the lid. | Side grip at the near end of the face (wrist past the carton's edge). Top grip at the near edge. Palms 2.2 cm off the face. Elbows swivel round the shoulder–wrist axis, clear of the carton and the station's belt frames. |
| Hands on belts / the wall while waiting; "zombie arms" (009e) | The empty-hands pose was held out in front at belly height for the whole wait. | Between picks the hands come down to a relaxed pose in front of the thighs (0.6 s), and up again just before the next reach. Kept behind the wall face and the queue line. |
| Parcels sinking into the ramps (~330) | Parcels only turned in yaw, so on the 11–12° ramps their downhill end went 4–5 cm into the belt. | Pitched to the belt: they rest on its upper hull under their centre of mass. The same on chute slides. |
| Boom D02/D05 (~150) | 3 cm step between the nested boom sections. | One continuous belt surface over all sections. |
| Bag landings (~300) | Landing in the static bag contents, against the chute end, or in the sack wall. The static parcels resting on the chutes were slid through. | Raycast through chute and frame down to the contents. Spots under the chute end or in the sack wall are rejected. Full bags hold their static parcels at 0.65 m. **The static chute piles are gone:** on an open chute a parcel slides into the bag; piles only form on a closed chute. |
| Heap stations (opener, line B) | A diagonal pull went through the neighbouring parcels. The carton was then held above the heap and pushed back into it by the chin-height cap. | Straight up over the parcels in its way, then out; held beside the heap. The worker straightens as it comes up. |
| Dock overlaps (9–19 cm) | **Each unloader held their carton over the boom nose, exactly where the mate was setting one down.** | Held on their own side of the boom. Set-downs wait one frame at a time if the belt has stopped since the commit (also for the inductors). |
| Merge rail (both merges) | The loop's outer guard rail ran straight across both merge belts. | Openings at both merges; the machine fence also opens at line B's ramp. |
| Bagger (~130) | Lifting a full sack (0.6 × 0.5 × 0.7 m) out over a 0.9 m rim needs the neck at 1.6 m. Carried in front or at the side, it went through the legs. | The tied sack slumps on the floor in the frame, is pulled out under the front rail, and is carried low one-handed at the left side, 0.55 m out (no parcel-hub reference shows this; that is my decision). It is lifted up first, then across, into the cage. The new-bag time is unchanged (23.38 s), so C07's closed window and the recirculation stay the same. |

**Gate tooling:**
- `qa_gate.py --collisions` treats any collision row as **STRICT**.
- `render_batch.sh` requires the scenario's collision report. **GATE_FORCE is removed** (owner rule).
- Not a fix, but a measurement rule: feet or toes on anything below 2 cm height (painted floor lettering, door sills) count as floor contact, like the floor itself. Sole height and foot slide are the feet checks' job.

## 3. Headwear (009d/009e "teal cap never seated")
- **The QA check was measuring the wrong thing.** The cap mesh's bottom is a flat disc hidden *inside* the head, and the "ring" included it. Its inner points read as 2–8 cm gaps.
- Now only the band edge is measured. The cap's band is **shrinkwrapped to each skull, 4 mm off the skin**, fading to the stiff crown, and it moves with the head.
- Hard-hat shells are 4–8 mm smaller.
- **accessory_fit:** test 13 has **0 rows**, caps and hard hats alike. The bagger's hard hat was 3.6 cm against 3.5 in test 9.
- **Other hard gate rows in test 13:** 7 `held_clip_head`, each 1–2 frames, 0–9 cm. Six are at line B's inductors, where a parcel comes up past the face as it leaves the heap; one is line A's induct_2 (2 cm). They are on the list in §6.
- Sheets for every hat wearer, every 10 frames, front and side: `qa/review/req013/heads/*_sheet.jpg`. Single close-ups are in the same folder.
- **Known defect in these sheets:** the cap band's edge is jagged (a sawtooth), because the wrap snapped some band points onto hair cards. The next build smooths the band after the wrap. The side sheets (`*_side_sheet.jpg`) show the seat best: band on the forehead, no gap, no tilt. The front sheets look down on bowed heads.

## 4. Follow-cams and 1 fps sheets (nudge #1)
- **Front angle**, the 4 line A inductors: `qa/review/req013/follow/worker_induct_[1-4]_front.mp4`.
- **Hall angle**, docks D05_n and D02_s: `qa/review/req013/follow/worker_dock_*.mp4`.
- Frame numbers are burned in, workbench shading. 1 fps sheets (6 × 5, every 10th frame) are in `qa/review/req013/stills/*_sheet.jpg`, with single frames in `stills/<worker>/`.
- **The MP4s are in (14:24).** All 6 are in `follow/`, labelled with the worker name and frame number. The first encode had failed on a font path, so they were re-rendered.

## 5. Induction line B (B2_prereview_b)
- **Layout:** a workstation between the forklift lane and the loop. Three inductors stand 1.1 m apart, each with a half-size gaylord heaped at the rim.
- **Flow:** belt B runs at 1.5 m/s, ramps up through DWS arch B (SP-TUNNEL-B), and merges with carrier booking (SP-INDUCT-B).
- **Belt start moved:** it now starts at x 40.8. From 39.6, its first 0.7 m ran into the XO-1 south stair. There is a new plan check, `stairs_clear`.
- **Line A is unchanged:** line B has its own random stream and parcel range (7xxx), and its labels are assigned last, so line A's labels and story timings stay as they were.
- **Pace:** ~3 s per parcel (~1,200/h per inductor), inside the 800–2,250/h range public sources give for manual induction with orientation.
- **Loop occupancy is 27–29 % in S0** (32 % in S2 at test 11), below the 30–35 % target. See the question below.

## 6. Next 2 hours (to ~16:00) and the expected count
1. **Docks:** keep the forearm and hip off the boom side frame (the frame as an arm obstacle, a hold lane), the carton off the chest, and D05_n's hold within reach.
2. **Inductors:** keep the spine clear of the induction belt frame on the set-down (a step toward the belt instead of a lean).
3. **Bagger:** verify the carry and lift fixes. **Line B:** parcels leaving the heap stay below chin height (`held_clip_head`).
4. **Mesh hygiene (new P0):** a detection script over every camera-visible mesh (n-gons / fans, slivers, coplanar duplicates, z-fighting between objects), plus Rexton's D01 panel test (topology or moiré).
5. Re-run S0 and S2. **Expected: S0 < 400, S2 < 450.** The remaining hits after that are 1–3 cm grazes at the hands; the plan for them comes in the 16:00 request.

## 7. Questions
1. **Occupancy 27–29 %:** line A is limited by what the docks unload (≈23 parcels / 30 s), and line B by a heap a person can reach. To reach 30 % I would either add a **4th line B inductor on the north side of belt B** (gaylord between the belt and the fence; pallet-truck access along the 1.9 m corridor), or **add a third unloader at D05**. Which do you prefer, or is 27–29 % acceptable?
2. Is the bagger's drag-out sequence (slump, pull under the rail, carry low at the side) believable to you? I found no reference footage of a bag change in a parcel hub.
