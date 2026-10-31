# Request 014b: M0 (014_GO), line A induction re-laid, headwear removed, person–person finding

From the builder. I missed 013b, 013c, headwear_decision and 014_GO while I was heads-down (I didn't re-check `reviews/` after 14:24). That is my fault. Request 014 crossed with them. From now on I check `reviews/` before and after every test run.

## 1. Headwear: removed (013c)
- `hat=None` on every worker in `stations.py` and `mixamo_workers.py`: 15 places, none left.
- `people.py` has `HEADWEAR_ALLOWED = False`: the hat prop path is switched off, so nothing can bring one back.
- The next test run carries this. Bare-head sheets for all workers (f001/f150/f300, front and side) come with M1/M2.

## 2. Person–person (013b #1, 014 #2): measured
Line A's inductors in test 18, checked every 5th frame. The body meshes **never touch**:
- closest pair: induct_2 and induct_3, **14.5 cm apart** at f176;
- induct_1 and induct_2: 22.5 cm; induct_3 and induct_4: 24.1 cm;
- no overlapping triangles at all.

The front follow-cam looks straight down the 0.45 m aisle, so their bodies **occlude** each other in that view. But 14.5 cm between two people breaks the ≥ 0.6 m personal-space rule from 009d. The collision check can't see that, because nothing touches. The layout below removes the cause. I'll also add a QA spacing row: any two workers' bodies closer than 0.3 m while they work.

## 3. M0: line A induction re-laid (layout only, as asked)
Stills (EEVEE): `Spoor/qa/review/m0/m0_top.png` (top, orthographic), `m0_front.png` (from the induction side), `m0_operator_view.png`.
- This is a preview: the current hub with the old feed run cut out, the new pieces added, and **stand-in figures** (yellow, with a nose showing the facing) on the inductor spots. The real workers come at M3, on the mocap pipeline.
- Script: `assets/hub/m0_layout_preview.py`.

| | Before | Proposed |
|---|---|---|
| Inductors | 4 in one 0.45 m aisle, 1.0 m apart (bodies 14.5 cm apart) | 4 at x 7.0 / 8.6 / 10.2 / 11.8: **1.6 m apart, one per induct point** |
| Facing | down the aisle; feed queue on one side, induction belt on the other, so every parcel needed a turn of up to 180° | **facing the induction belt** |
| Buffer | the feed belt's queue beside them | a **gravity-roller table at each inductor's front-left**, from the feed belt down to them. Its end is at 88 cm (75–110 cm zone), about 80° from their facing |
| Aisle (frame to frame) | 0.45 m | **0.95 m**: the feed belt moves north to y 11.35 and extends to x 13 |
| Per parcel | lift, spin, place | glance left, reach (~80° trunk turn), slide or short two-hand lift, label up, turn back, **push forward into the gap**. Feet planted, one small step at most |

Seen in the stills:
- **An existing plastic chair overlaps table I3.** It moves at M3.
- A short leftover of the old feed run is visible at the far left of the front view. It is not part of the proposal.

Line B (gaylords) gets the same rules at M4 (face belt B, gaylord at the side within reach).

**Question:** OK to wire this layout into build_hub / flow / stations at M3, with the parcel diverting from the feed belt onto each table? Or do you want a different buffer: the feed belt's own end at the operator's side?

## 4. M1 (due 16:30): under way
- Downloading from Zenodo (both CC BY 4.0):
  - AndyData `xsens_bvh.zip` (1.8 GB), `labels_csv.zip` and `participant_specifications.csv`;
  - 100STYLE `100STYLE.zip` (1.5 GB).
- `assets/mocap/raw/` and `assets/mocap/own/raw/` are gitignored.
- Next:
  - `assets/mocap/sources.csv`;
  - a Rocketbox bone dump (2 avatars: names, unit scale, bind-pose arm angle);
  - a scripted swing-only T-pose (front and side PNG);
  - relaxed static fingers;
  - the AndyData label list.
