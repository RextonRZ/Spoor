# Request 001: B1 floor diagnosis (+ two notes on review 000)

## 1. Changed since last request
First request. Covers QUEUE B1 and review 000 #11. Also answers #6 and #7 (see Questions).

**Diagnosis of the near-white floor: QA preview mode only.** The texture is not lost and the final render is not overexposed.
- The QA videos of 29 Oct used Workbench (studio light, texture colour, no scene lights or exposure). That mode shows the concrete albedo at full brightness.
- The final settings are EEVEE at 4 spp, 2688×1520, exposure 1.7, followed by the CCTV pass (cctv_look). With those settings the floor is mid-grey and textured.
- Material `floor_epoxy_concrete` uses `smooth_concrete_floor` diffuse, roughness and normal (2k), plus the decals: yellow lines, zebra crossings and floor markings.

Measured on the final-settings frames (frame 150). Floor pixels are found by ray-casting a 12 px grid; values are the 0–255 mean of RGB.

| Camera | Floor pixels sampled | Mean | p99 | Max | Share > 230 |
|---|---|---|---|---|---|
| CAM_07 | 20 367 | 78.8 | 137.3 | 176.3 | 0.0 % |
| CAM_13 | n/a | 78.9 | n/a | 169.7 | 0.0 % |

So the floor is darker than the white walls, it never clips, and the concrete texture and yellow lines are visible.

**Change going forward.** From now on the CCTV QA clips (B3) render with the final look: EEVEE plus the CCTV pass, at 960×540. Workbench stays only for the close follow-cam worker clips (A2), where the look doesn't matter and speed does.

## 2. Check these
- `assets/hub/build/qa/floor/proof.png`: left is the old QA preview (Workbench, white). Right is the final settings for CAM_07 (top) and CAM_13 (bottom).
- `assets/hub/build/qa/floor/CAM_07_final.png`, `CAM_13_final.png`: full-resolution final render, before the CCTV pass.
- `assets/hub/build/qa/floor/CAM_07_cctv.png`, `CAM_13_cctv.png`: after the CCTV pass (OSD, SYNTHETIC mark).

## 3. Known issues (already being fixed, skip these)
- These frames were rendered before tonight's people rebuild, so they still show the miming workers (review 000 #1–5, #13, #14). The rebuild is in progress (A1).
- Tyre or wheel marks: the texture has only light wear. I'll add subtle forklift and cage-wheel tracks along the lanes as a P2 polish after A1, unless you rank it higher.

## 4. Questions
1. **Clip length.** `hub_spec.json → render_plan` fixes 30 s per scenario at 10 fps (300 frames). The whole flow timeline (parcels, events, truth) is built for 300 frames. QUEUE B3 and D2 ask for 60 s. **Decision:** keep 30 s, to match the spec, the scenario budget and the existing timeline. Reply if you need 60 s for a reason I'm missing; that doubles render time.
2. **Review 000 #6, stretch wrap "translucent".** Rexton has an owner rule: no see-through materials except glass. It was set after see-through hats and wrap caused artefacts. So the wrap is opaque. What shows through is printed onto the film: the cardboard texture, washed pale, glossy (roughness 0.18), mixed 45–70 % with the film colour. I'll add wrinkle normals and a few torn flaps so it no longer reads as a "plain white block". A reply is in `review/replies/` only if you still want true transparency; that would need Rexton.
3. **Review 000 #7, booms.** Rebuilt tonight: the telescopic booms now run from x 5.0 to −5.6, through the dock door into the lorry body. A belt bed and belt now run over the base unit. You'll see them in the B2 stills and the dock clip.
