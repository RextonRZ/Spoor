# Request 002 — Frontend: C1 + C2 (app skeleton, contracts, hub GLB, frusta, 2D plan)

From the frontend agent (block C). Builder's Blender work untouched; I only read `hub_dressed.blend` through a temp copy.

## 1. Changed since last request
First frontend request.
- **C1** `frontend/`: Next.js 16 (App Router) + TypeScript 5.9 + React Three Fiber 9 + drei 10.
  - TS types generated from `backend/schemas/*.schema.json` by `frontend/scripts/gen-types.mjs` → `frontend/src/contracts/generated/` (28 types).
  - Site Z-up → renderer Y-up: the backend now serves its own matrix (`/v1/capabilities.site_to_renderer`, from
    `spoor.spatial.frames.SITE_TO_RENDERER`); the UI installs it after checking it is a proper rotation. A unit test pins
    the UI default to the backend source file (`frontend/tests/unit/geometry.test.ts`).
  - The browser never holds a token: `/api/spoor/*` (Next route) proxies to FastAPI and adds the bearer token for the
    chosen demo role (investigator / reviewer / site admin) from server-only `.env.local`.
- **C2** `frontend/public/hub.glb`: **3.9 MB**, Draco, 246 k faces, 314 meshes, JPEG textures ≤ 512 px. Exported by
  `npm run export:hub` (`frontend/scripts/export-hub.mjs` copies the .blend to %TEMP%, runs
  `frontend/scripts/export_hub_glb.py` headless). Dropped: People/PeopleTemplates/Flow collections, `worker_*`, `Bip01*`,
  `mixamo*`, Rocketbox `[fm]NNN_*`, `flow_*`, lamps, Blender cameras, non-rendered objects (asset templates parked at the
  origin). Every node carries glTF extras `spoor_id` (= object name) and `zone_id` (hub_spec zone of its footprint).
  Report: `frontend/review_pack/m1/hub.export.json`.
  - Camera frusta + floor footprints are computed from hub_spec's mounting plan (heading CCW from east, tilt, H/V FOV),
    labelled "approx. FOV" (no occlusion, no lens model), per PRD §13.5.
  - 2D floor-plan fallback (SVG) from hub_spec: zones, blind corner, loop, conveyors, chutes, scan points, camera FOVs.
    Automatic when WebGL is unavailable or the 3D view throws.
- Backend (additive, read-only routes, tests added, `uv run pytest` → **207 passed**, ruff clean):
  `GET /v1/me`, `/v1/capabilities`, `/v1/sites`, `/v1/sites/{id}`, `/v1/sites/{id}/cameras`, `/v1/sites/{id}/media`,
  `/v1/sites/{id}/clock-domains`, `/v1/sites/{id}/scans`, `/v1/media/{id}/frame-at?time=`, `/v1/cases`,
  `/v1/cases/{id}/last-seen` (graded last seen), `/v1/cases/{id}/reports`. No route derives new evidence.

## 2. Check these
- `frontend/review_pack/m1/workspace_3d_overview_1440x900.png` — 3D scene, default view (roof, S/E walls hidden for a cut-away).
- `frontend/review_pack/m1/workspace_3d_last_confirmed_1440x900.png` — after "Show where it was last confirmed": camera moves
  to the last fixed-scanner read, CAM_10 cone lit (the camera that sees that read point), source panel shows CAM_10's
  original frame at the scan time, labelled "context frame, not an observation".
- `frontend/review_pack/m1/workspace_2d_plan_1440x900.png` — 2D fallback, same state.
- `frontend/review_pack/m1/cases_1440x900.png` — case list.
- Code: `frontend/scripts/export_hub_glb.py`, `frontend/src/lib/frames.ts`, `frontend/src/lib/trace.ts`.

## 3. Known issues (already planned)
- Colour tokens (Rexton's process rule says "show tokens first"; he is away, so I chose and will apply review changes):
  | token | value | use |
  |---|---|---|
  | bg / surface / surface-2 | #0e1012 / #15181b / #1b1f23 | dark-neutral canvas |
  | ink-strong / ink / ink-muted | #f3f5f7 / #d6dbe0 / #9aa4ad | text scale (muted on surface ≈ 6.9:1) |
  | accent | #a99bff | primary button, selected, lit camera only |
  | observed / estimated / hypothesis / unknown / contradicted | #4ade80 / #60a5fa / #fbbf24 / #8b949c / #f87171 | evidence labels, always with a line pattern + word |
- No observed (green) segments exist yet: no SAM key, so no tracks. The trace renderer is implemented and unit-tested
  (`solid never bridges a gap`), and will get a clearly marked test-fixture screenshot in the C7 pack.
- Current clips are the 30 s QA renders (`assets/hub/build/qa/cctv/CAM_01/04/07/10.mp4`) — unmarked, so the seed burns a
  `SYNTHETIC - fictional hub` mark into the imported copy. Final B3 clips will be imported unchanged.
- Dark theme only (PRD §19.1 dark canvas). Mobile 390×844 screenshots come with C3/C7.
- Floor in the web scene is overridden to neutral grey so evidence colours read; it is not meant to match CCTV.

## 4. Questions
1. The builder's `hub_dressed.blend` (02:10) has `steel_frame_shelves_01.001` (NW, x 11–22, y 37–42) and `.002` (east) at
   **21.4 m tall**, rendered (not hidden). I drop anything above eaves + 1.5 m from the web GLB and list it in
   `hub.export.json → dropped_oversize`. Builder: probably a scale bug in the dressing pass — worth a look in CAM_15/CAM_02.
2. The sim log has 52 `bag_drop` photo-eye pulses with `parcel_id: null` and no bag ID. Spoor's `ScanEvent` has no kind for
   an event with neither identity nor container, so the seed reports them as "not imported" (count shown) instead of
   inventing an ID. OK, or should step 14 add a `photo_eye` machine-event kind?
