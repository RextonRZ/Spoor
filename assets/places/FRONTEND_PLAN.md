# Where is this place? (pictures + pins for the app's Places)

**Status (1 Nov, render agent, with Rexton's OK): built into the app.** Hub > Places opens on the map (`src/components/hub/HubMap.tsx`, `hubmap.css`, `src/lib/places.ts`), Map | List toggle, any place opens in the panel with "Where this is" (3D map / From above / Eye level), the panel has a close button, `/hub?place=SP-...` opens a place, and a case's checkpoints link there ("Where is this?", `CheckpointStrip where`). Pictures: `public/places/*.webp` + `places.json` (`py -X utf8 assets/hub/place_export.py`). The text below is the original plan.

From the render agent, 1 Nov. Rexton wants every place (scanner) in the app to show where it is, so a judge who has
never seen the hub knows what "Chute C12" or "Dock D07 gate" is. The pictures and pin positions are ready. Nothing
in `frontend/` was changed. **Prototype to click through: `assets/places/index.html`** (opens straight from disk).

## What is ready
| File | What |
|---|---|
| `assets/places/out/hub_top.jpg` | The whole hub from straight above, roof off, north up (1600 x 900) |
| `assets/places/out/Z01_top.jpg` ... `Z14_top.jpg` | Each zone from straight above (1600 x 900) |
| `assets/places/out/Z01_eye.jpg` ... `Z14_eye.jpg` | Each zone at eye height **with the workers in** (the locator's eye cameras, S2 final, frame 300) |
| `assets/locator/out/Z01_map.png` ... `Z14_map.png` | The tilted 3D maps (the locator agent's; zone shaded blue, compass, camera badges) |
| `assets/places/out/places.json` | For every picture above: pixel position of every scanner and the zone outline |

`places.json` (all pixels in the 1600 x 900 picture, origin top left):
```
{ "frame": 300, "size": [1600, 900],
  "hub_top": { "image": "hub_top.jpg", "scan_points": { "SP-INDUCT": {"x": 412.3, "y": 233.1, "zone": "Z03"}, ... },
               "zones": { "Z01": [[[x, y], ...]], ... } },
  "zones": { "Z03": { "name": "Induction",
                      "top": { "image": "Z03_top.jpg", "scan_points": {...}, "zones": {"Z03": [[[x, y], ...]]} },
                      "eye": { "image": "Z03_eye.jpg", "people": ["worker_induct_1", ...],
                               "scan_points": { "SP-INDUCT": {"x": .., "y": .., "zone": "Z03", "seen": true} }, ... },
                      "map": { "image": "assets/locator/out/Z03_map.png", "scan_points": {...}, "zones": {...} } } } }
```
Only scanners inside the picture are listed. `seen: false` (eye only) means the scanner is behind something from that
spot; don't draw that pin there (the prototype says "see From above").

## Suggested interaction (as in the prototype)
1. **Places tab: a hub map beside the table.** `hub_top.jpg` with every scanner as a pin: amber where something is
   stalled, the usual grey otherwise. Zones are outlined and tinted when you hover them. Hovering a row lights its pin,
   and clicking a pin opens the same row (`show(key)`). The list and the map always agree.
2. **Place detail: a "Where is this?" card** above the existing camera `View`, with three tabs:
   **3D map** (the default) | **From above** | **Eye level**. The place's pin pulses (static under
   `prefers-reduced-motion`). The zone's other scanners are small pins you can click. Crossfade 200 ms. Preload all
   three pictures when a place is picked. Under the picture, the zone's scanners are chips.
3. **"Explore in 3D"** opens the live hub (`Scene3D`) and starts the camera exactly where the 3D map picture was
   taken, so the still comes alive without a jump. That camera is
   `assets/locator/out/_raw/<zone>_map.json -> three_camera` (`position`, `target`, `fov_deg`, already in three.js
   axes). Then it's normal orbit / zoom, like Google Maps 3D. The pin in 3D goes at the scanner's `position_m`
   (`hub_spec.json scan_points`, three.js = `(x, z, -y)`).
4. **Case Answer / checkpoints:** each checkpoint (Unloaded, Scan tunnel, Into chute C12, ...) gets a small 3D-map
   thumbnail with its pin. Hover or focus it for the three views. This makes the six-step journey readable for someone
   new to hubs.

Pins and outlines should be drawn by the app (SVG over the image, `viewBox="0 0 1600 900"`), not baked into the
pictures: they stay sharp at any size and can be clicked, hovered and labelled.

## Notes
- **Hidden on purpose:** the S2 case's actor (`worker_s2_1`) and the parcel it carries are left out of every picture,
  so no picture gives the demo case away.
- **Weight:** the maps are PNG (23 MB for 14). Convert them to WebP or AVIF for the app (about 10x smaller). The
  JPGs are about 250 KB each.
- **`frontend/public/hub.glb` is the old geometry** (before the 1 Nov zone repairs). Re-export it from
  `assets/hub/build/hub_lineAb_dressed_lit.blend` before Explore in 3D goes live.
- **Refreshing pins:** `blender -b assets/hub/build/hub_lineAb_S2_final.blend -P assets/hub/place_views.py -- --out
  assets/places/out` re-renders and rewrites `places.json`. Run it again if the locator's map cameras change; the
  map pins come from those cameras. Then `py -X utf8 assets/hub/place_page.py` rebuilds the prototype.
- Place names in the prototype copy `placeName()` from `frontend/src/app/hub/page.tsx` and `ZONE_NAMES` from
  `frontend/src/lib/zones.ts`.
