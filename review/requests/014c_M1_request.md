# Request 014c: M1 (014_GO): mocap sources, Rocketbox rig facts, shared T-pose

From the builder. M1 is due 16:30; this is sent at 16:15. Everything is under **`Spoor/qa/review/m1/`**; the data is under `Spoor/assets/mocap/`.

## 1. Sources: downloaded, licences checked against Zenodo's own record (API)
- **No whole-zip downloads.** Zenodo served about 65 KB/s, so the 1.8 GB and 1.5 GB zips would have taken hours. Instead, `assets/mocap/fetch_sources.py` reads each zip's directory over HTTP Range and pulls out only the files we need. It uses 4 MB chunks with retries, because Zenodo drops long transfers. Each file is verified complete: header frame count = rows.
- **`assets/mocap/sources.csv`** lists every file with its licence, URL, credit and use. **`assets/hub/CREDITS.md`** has two new rows, AndyData and 100STYLE. Raw data stays in `assets/mocap/raw/`, which is gitignored.

| Source | Licence (from the Zenodo record) | Files fetched |
|---|---|---|
| **AndyData-lab-onePerson**, Maurice et al. 2019, doi:10.5281/zenodo.3254403 | **CC BY 4.0** | 3 takes, Xsens BVH 240 Hz: Participant_5124 Setup_B Seq_1 Trial_3 (165 s), Participant_2274 Setup_B Seq_3 Trial_3 (121 s), Participant_541 Setup_A Seq_3 Trial_2 (107 s). Plus all 195 label CSVs and participant_specifications.csv (heights, segment lengths) |
| **100STYLE**, Mason, Starke, Komura 2022, Zenodo 8127870 | **CC BY 4.0** | Neutral style, BVH 60 Hz: FW (forward walk), BW (backward walk, for the bag drag), SW (side step), ID (idle). Plus Frame_Cuts.csv (usable frame range per take) |
| Rocketbox (already in the hub) | MIT | target avatars |

- **Why these takes:** I chose them by counting labels. In each participant's trials, they have the most reach + pick + carry + place frames. They are three different performers, so neighbouring workers don't have to share a clip (new gate).
- **Same skeleton.** AndyData and 100STYLE both use the 22-joint Xsens hierarchy (Hips, Chest…Chest4, Neck, Head, collars, shoulders, elbows, wrists, hips, knees, ankles, toes) with 72 channels in cm, Y up. One BVH reader covers both.
- **Excluded, per the plan:** LaFAN1, Bandai Namco, Geno, VIBE/MoveBox, Mixamo, the MMH set, and CMU (not used unless Rexton says yes).

## 2. AndyData labels: `andydata_labels.txt`
- **The legend comes from the paper's Table 1**, Maurice et al., IJRR (HAL hal-02289107). I read it rather than guessing.
  - Actions: **Re** reach, **Pi** pick, **Ca** carry, **Pl** place, **Rl** release, **Fm** fine manipulation, **Sc** screw, **Id** idle.
  - General postures: **St/Wa/Cr/Kn** (standing, walking, crouching, kneeling).
  - Detailed postures add **U/BF/BS/OS/OH** (upright, bent forward 20–60°, strongly bent >60°, shoulder-level work, overhead work).
- **Format:** 3 annotators, 24 fps, `t_video` in seconds. The paper says the Xsens videos are exactly aligned with the Xsens data. Checked: take 541's BVH lasts 107.12 s and its labels 107.125 s, so a label time is a BVH time.
- **Segment timelines** (majority of the 3 annotators) for the three takes are in the file.
- **Typical lift:** Re 0.8–2 s, Pi 0.6–1 s, Ca 1.3–3.8 s, Pl 0.8–2.4 s, Rl ~1 s. The carries include walking between tables. That is why M3 retimes to a 2.5 ±0.5 s cycle and keeps only the turn part of Ca.

## 3. Rocketbox rig facts: `bones_Male_Adult_04.txt`, `bones_Female_Adult_04.txt`
Each file has, for all 80 bones: name, parent, rest head in metres (world), length, and the head→child direction. Biped tails are unreliable, so directions are measured head to child head.

| | Male_Adult_04 | Female_Adult_04 |
|---|---|---|
| Unit scale | armature object 0.01 (FBX cm → m) | 0.01 |
| Height (top of head) | 1.868 m | 1.762 m |
| Facing at rest | −Y (normal to the hip line; the toes splay ~14°) | −Y |
| Bind-pose upper arm | **43.9° below horizontal**, 1.2° forward (A-pose) | **42.3° below**, −0.5° forward |
| Root | **Bip01 Pelvis** (pelvis at z 0.895) | Bip01 Pelvis |

**Note for M2:** in Blender's FBX import, the Biped's `Bip01` node becomes the armature object, so `Bip01 Pelvis` is the root bone. Root translation (scaled by leg ratio) and pelvis tilt both go on `Bip01 Pelvis`. The object stays where the station puts it.

## 4. Shared T-pose, swing only, with relaxed static fingers: `m1_tpose_sheet.jpg`
- **Script:** `assets/hub/mocap/rb_tpose.py`. Individual PNGs: `tpose_<avatar>_front/side/hand_top/hand_front.png`.
- **The T-pose:**
  - Each bone turns about its head by the shortest arc from its bind direction to its T direction: spine and neck up, arms lateral and horizontal, legs down.
  - **No twist is added**, so the bind palm orientation (palms down) is kept.
  - Check: both arms **0.00°** off lateral-horizontal; both legs **0.00°** off vertical.
- **Relaxed fingers:**
  - Static curl toward the palm; the palm side is the side the thumb sits on.
  - MCP, PIP and DIP bend 8/12/10° (index) up to 16/24/16° (little); the thumb gets half.
  - The hand close-ups show a loose, natural hand: no claw, nothing bent backwards.
- M2 aligns the BVH's own T-pose to this pose and retargets in world space from there.

## 5. Seen while checking (realism)
- **Female_Adult_04 wears heeled boots** (side view). Nobody works a parcel hub in heels.
  - She is induct_2 / inductB_2 today.
  - At M4 she will be replaced on the floor by an avatar with flat shoes, or kept only where her feet never show. I'll check every avatar's footwear when I cast the 4 inductors.

## 6. Next: M2 (17:30)
- `assets/hub/mocap/retarget.py`:
  - numpy BVH reader;
  - world-space offsets at this shared T-pose;
  - root on Bip01 Pelvis, scaled by leg ratio;
  - quaternion hemisphere fix;
  - channelbag bulk write.
- One AndyData reach / pick / carry / place cycle from take 5124 on Male_Adult_04.
- QA: foot skate, ground penetration, limb-direction error.
- Proof: 10 s EEVEE front + side next to the BVH stick figure.
- **Still open from M0:** your answer on the buffer (a gravity-roller table per inductor vs. the feed belt's own end). Until it arrives, M3 builds on the roller table.
