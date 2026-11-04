# Spoor locator images

Each of the 14 hub zones has a 1600 x 900 eye-height image and a secondary map image.
All generated files stay in assets/locator/. No hub asset, frontend file, or .blend is written or saved.

## Review and integration

- out/review.html: paired image gallery with full-resolution image links.
- out/overview_eye.png and out/overview_map.png: contact sheets.
- out/Zxx_eye.png and out/Zxx_map.png: case-report assets.
- out/locators.json: both camera records per zone; open_in_3d is map.
- out/validation.json: checks for image completeness, camera coordinates, floor colour and source hashes.
- out/run_report.json: render timings, resource settings and before/after input hashes.
- check/index.html: standalone three.js page loading the existing frontend/public/hub.glb read-only.
- check/compare_Zxx.png and check/camera_checks.json: camera comparisons and browser projection results.

The earlier out/Z11.png is the superseded first locator design. Use the suffixed images.

## Run from C:\Users\ooiru\Spoor

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -b --factory-startup assets/hub/build/hub_lineAb_dressed_lit.blend -t 4 --python-exit-code 1 -P assets/locator/make_locators.py -- --zones all --resume --out assets/locator/out
python -B assets/locator/check/capture_check.py --zones all
python -B assets/locator/verify_outputs.py
python -B assets/locator/build_gallery.py
```

--resume preserves completed images and cameras. Omit it to regenerate. Use --zones Z11 or a comma-separated
zone list for a subset, and --views eye or --views map to regenerate just that view. If an eye image changes,
reprocess its map with postprocess.py so both use the new natural floor reference. SP-STORE-IN and
LOC-Z11-EXCEPTION also resolve to Z11. --preflight checks approach cameras without rendering. --reuse-cameras keeps the saved poses during a re-render.

System Python needs Pillow. The screenshot helper also needs Playwright and Chrome. Override Python with
--python or LOCATOR_PYTHON. The check page uses pinned three.js 0.180.0 from jsDelivr and the existing app
Draco decoder. Run `python -B assets/locator/check/capture_check.py --serve` to inspect it interactively at
http://127.0.0.1:8766/assets/locator/check/index.html?zone=Z11. The gallery is at /assets/locator/out/review.html.
The server exposes only the locator folder, frontend/public/hub.glb and frontend/public/draco/.

## Camera and image choices

Eye cameras use 26-28 mm lenses and stand 1.6 m above their actual walking surface, 4-8 m from the
zone approach. The subject bounds, scan points, walking routes and fixtures come from the spec and source
meshes. Candidate views fit the complete subject and reject foreground obstructions. Z03 uses an XO-2
stair tread; Z05 uses the XO-1 crossover deck so the raised track and carriers can be seen. These records
include camera_floor_z_m and the exact step/deck evidence. Z04 uses the specified ZX2 zebra approach,
showing the whole scanner with a temporary fill light at its actual lightbar. No light is saved to the hub.

For Z11 the entrance is the rack gap beside SP-STORE-IN. The supervisor room uses its west door onto W1.
The yard camera stands outside, 1.6 m above the asphalt. Its clear apron strip is derived from the west-yard
polygon and static lorry fronts, looking along the lorry bays. It is explicitly marked as an inferred outdoor
access strip because the spec lists only indoor walkways. Roof, doorway, header, signs and static fixtures
stay in the eye images. Each has one small name pill. The repaired source model now supplies the conveyor joins, guides, legs and settled parcels. Locator geometry
corrections and parcel cleanup are disabled by default, so repairs are not duplicated. LOCATOR_SOURCE_FIXED=0
exists only for explicitly rendering a legacy source. No source model is changed by this renderer.

out/visual_review.json records the latest review of all 14 pairs. All 28 views were recaptured from the repaired
hub with their saved cameras. The earlier captures are retained in out_before_zone_repairs/. Repair details
are in qa/review/zone_audit/ZONE_REPAIRS.md. The app hub.glb still predates the repairs: the standalone check
proves camera alignment, while repaired geometry will require a new export by the hub/frontend owner.

Map cameras test several angles at 40 and 44 degrees down. Rays measure visible zone floor and reject
large empty exterior areas. The full polygon and fixture height are framed with approximately 1 m of context.
Roofs, ceiling equipment and trusses are hidden in memory. People and animated parcels are hidden in both
views, while static fixtures and parcels remain. Camera icons come from the hub spec. The compass uses
its +Y north direction. Z11's BLIND_NW floor is hatched and explicitly labelled as having no coverage.

The natural floor tone is consistent within each eye/map pair. The photo keeps its original floor colours.
Pillow measures the visible physical floor through geometry-derived masks, then matches each map floor's
median RGB to that photo before applying the indigo highlight. Texture and shadow variation are preserved.
Interior concrete and outdoor asphalt are measured separately. Unseen surfaces retain their natural source
material. Non-floor surroundings receive a slight subdued treatment. The selected map zone gets #5558EE
at 35% opacity and a 2.5 px bright edge. Fixtures occlude the fill and hatching. Colour calibration is recorded
in map.floor_colour_match. Eye images have no floor highlight, compass, camera icons or model tag.

cams_covering is based on overlap with declared camera duty rectangles, indicating partial zone coverage.
CAM_19 sees the Z11 entrance; BLIND_NW behind the racks has no coverage. coverage_details preserves this.

## Resource limits

EEVEE uses 32 eye samples and 16 map samples in the repaired-model batch. All 28 images completed in
561.67 seconds including startup, with no image taking more than 29.93 seconds. A single below-normal-priority
Blender worker uses four CPU threads and stays open between
images to avoid reloading geometry and recompiling shaders. The parent unloads its source scene first.
A separate watchdog enforces a 120-second limit per image and retries at half the samples after a timeout.
Every completed image and camera is checkpointed, allowing --resume to continue after interruption.
Pillow runs outside Blender in system Python. The scripts never call Blender's save operators.

## Camera contract for Open in 3D

Use zone.map.three_camera for the report's Open in 3D button. Each zone's eye and map each contain image,
camera (Blender) and three_camera (glTF/three.js). The top-level image points to the eye image.

frontend/scripts/export_hub_glb.py uses export_yup=True and preserves metres:

```text
Blender (x, y, z) -> three.js (x, z, -y)
vertical FOV = 2 * atan((36 / (2 * lens)) * (900 / 1600))
```

Apply position and fov_deg to a Y-up PerspectiveCamera, point it at target, set OrbitControls.target to the
same target, call controls.update(), then update the camera matrices. Use a 16:9 viewport for exact framing.
Do not rotate or scale the GLB root. The map target is the area-weighted centre of the physical floor polygon.
For the identical cutaway apply map.render_profile.hidden_objects or hidden_name_regex as well.

zone_polygon_three is one outline for ordinary zones; the multipart yard has nested outlines.
zone_polygon_parts_three always contains an array of outlines. Overlay vertices are 0.035 m above the
physical floor to avoid z-fighting. Yard floor height is -1.2 m, so its 1.6 m eye camera is at Blender z=0.4 m. Indoor floor walkways are at z=0; crossover treads and decks use their specified elevations.

The standalone check verifies polygon projections after controls are initialized and the scene is rendered.
It also compares three identifiable cage origins in the actual GLB with the Blender source. Visible fixtures
are checked within 0.05 pixels; all fixture world positions are checked within 0.001 metres. Materials and
lighting differ between the full Blender scene and the compressed web asset, so shading similarity is not
used to prove camera alignment. The existing GLB predates some dressing: Z11 store_header and
sign_stor_board are absent, and its shelf contents differ. Source assets remain unchanged.

The existing frontend OrbitControls uses maxDistance=95. Apply each view's three_controls values before
controls.update(); the complete yard map needs a larger distance. The test page applies these hints.
The office map also supplies render_profile.ceiling_cutouts for its ceiling embedded in the fixtures mesh.
The standalone page applies that cutout to its in-memory GLB, preserving office walls and furniture.
