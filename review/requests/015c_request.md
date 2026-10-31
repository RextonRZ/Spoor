# Request 015c: M3 media complete (CCTV mp4, dense crops, head sheet). Answers to 015 / 015b

From the builder. Everything is in **`Spoor/qa/review/m3_hub/`**.

## Media
- **`m3_inductor_cctv_front_side.mp4`**: all 300 frames. CAM_01 crop | front | side, with the phase burned in.
- **`m3_sheet_1fps.jpg`**: 1 fps sheet.
- **`dense_grasp.jpg`**, **`dense_release.jpg`**: every frame (0.1 s) for 1.5 s around carton 1's grasp (f37) and release (f59), from each hand's side.
  - From the left: the hand comes in from the side and lies flat on the side face from the grasp through the lift, fingers along the face.
  - The right-hand camera is blocked by his own torso on most frames. That is a camera placement problem, not a fix I'm hiding; it gets a different angle next time.
- **`heads_sheet.jpg`**: bare head, front and side, at f001/f150/f300. No headwear anywhere.
  - **Seen up close:** Male_Adult_04's hair cards show as dark strips (a helmet-like pattern). This is the known Rocketbox hair-opacity issue (research step 2). At CCTV distance it reads as hair. The opacity material fix goes on the list before the final renders.

## 015 / 015b
- **All 015 fixes are done in the engine and shown at M4** (request 016, line A with 4 inductors on induct belts, your choice (b)):
  - no repeating cycle; ratio 0.92–1.12; an extra beat on ~1 in 6 cartons;
  - set-down flexion capped at 38°, head up 12°;
  - mixed cartons with labels;
  - palms open before the release;
  - a reach safety net.
- **The M3 render above is the version before those fixes.** Its numbers are in request 015: 6 collision frames, and 3 hold frames outside ±1 cm.
- **015b P2, dock-leveler plates speckling (D01/D02):** on the list with the CAM_15 speckle. Check at 2688 with 16× aniso, then a coarser diamond-plate normal map or a flattened albedo.
