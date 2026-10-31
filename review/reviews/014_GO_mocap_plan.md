# 014 GO — build the mocap pipeline now (owner order, Rexton 14:59 "Go fix using this plan")

Source: review/research/mocap_report.md (read "The ordered build plan" table + sections it cites). This replaces
hand-keyed / procedural arm motion for inductors, dock unloaders, baggers and cage pushers. Everything else waits
except finishing a gate run already in progress.

Checked now: USE_MIXAMO = False (good — Mixamo stays out of the render path). P2: confirm the HMI stand / break
table meshes that stations.py takes from mixamo_workers are from the CC BY vest-worker file, not Mixamo; write the
source in sources.csv.

## Milestones (system clock, MYT). Each one = a request file with proof, or a reply saying why not.

| # | Due | Do (report step) | Proof I will check at 1 fps |
|---|---|---|---|
| M0 | 15:47 | Req 014 as promised: redesigned inductor station (faces belt, buffer at the side, <=60–90° trunk turn, no spin with a parcel), current motion OK | EEVEE front + side 10 s; I judge LAYOUT only |
| M1 | 16:30 | Steps 1–2: `assets/mocap/sources.csv` (file, licence, URL, credit); download AndyData `xsens_bvh.zip` only (1.8 GB, disk now 26 GB free) + label CSV, 100STYLE (+ Frame_Cuts.csv); dump Rocketbox bone names / unit scale / bind-pose arm angle for 2 avatars; scripted swing-only T-pose; relaxed static fingers | `bones_<avatar>.txt`, T-pose front+side PNG, label names list from the CSV |
| M2 | 17:30 | Steps 3–6: `assets/hub/mocap/retarget.py` (numpy; world-space offsets at shared T-pose, root on Bip01 scaled by leg ratio, pelvis tilt only on Bip01 Pelvis, quaternion hemisphere fix, channelbag bulk write). One AndyData reach/pick/carry/place take on ONE inductor avatar. QA: foot skate per contact, ground-penetration frames, limb-direction error vs source | 10 s EEVEE front+side next to the BVH stick figure; QA numbers table |
| M3 | 19:00 | Steps 7–9 for the inductor: segment by labels (+ grasp/release sidecar JSON), PCHIP retime to a 2.5 s ±0.5 s cycle (ratio 0.85–1.15, holds instead of slow-mo), root warp, inertialized joins (~0.2 s), foot locks, hand IK ramp 0.2–0.4 s with the mocap elbow pole, parcel world-matrix bake (belt → hand → belt) | Req 015: 30 s, 1 inductor, front+side + CCTV angle |
| M4 | 20:30 | Same pipeline for dock unloader (top/mid/floor tiers, boom nose 103 cm beside the worker, 3.5–4 s/lift, slows + one pause), bagger (two-hand sack, drag), cage pusher (hands ~1 m, cage lags 0.1–0.2 s). Step 10: 4 inductors with different avatars, start offsets 0–100 %, speed 0.85–1.15, breathing layer, glances | Req 016: each station 30 s front+side; S2 QA cams |
| M5 | 21:45 | S0 + S2 rebuilt with new motion; full gates | Req 017: gate table + S2 QA video |

## Gates (added to qa_gate.py, STRICT, fail = no render)
- Foot skate during a contact < 20 mm (report: viewers see ~21 mm). Ground penetration frames = 0.
- Hand to parcel at grasp/carry <= 1 cm; parcel never moves without a hand on it (except belt/fall).
- No worker yaws > 90° while holding a parcel without stepping.
- OWNER RULE collisions: items, people vs assets, people vs people, 1 cm, every frame = 0.
- No two neighbouring workers share an avatar or a phase-locked clip.

## Licence (hard)
Ship only: Rocketbox (MIT, incl. its 417 clips), AndyData + 100STYLE (CC BY 4.0, credit), Quaternius (CC0), Rexton's
own takes. EXCLUDED: LaFAN1, Bandai Namco, Geno.fbx, VIBE/MoveBox, Mixamo, Manual-Material-Handling set (unverified).
CMU = do not use unless Rexton says yes. FreeMoCap add-on = offline tool only, never import its code.

## Rexton's own phone takes
Shot list IDs IN-01…PR-01 (Claude Docs). Raw video → `assets/mocap/own/raw/` (gitignore it NOW, it shows his face
and home); BVH → `assets/mocap/own/bvh/`. When an own take exists for a shot, it beats AndyData for that station.

## How I review
Every proof video: 1 fps native crops front + side, zombie checks (arms hanging, phase lock, slide, spins, stiff
knees, floating hands), and I forward the sheets to Rexton. Miss a milestone → reply with the blocker, not silence.
