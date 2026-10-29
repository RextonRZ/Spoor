# Spoor frontend

Investigation workspace for the Spoor backend (PRD §19, §23): Next.js 16 (App Router), TypeScript, React Three Fiber +
drei. It runs end to end **without model API keys**: model-backed steps show "analysis unavailable" and nothing is
simulated in their place.

## Run the no-key stack (Windows, from `frontend/`)

```bash
npm install
npm run setup:local      # once: random demo tokens -> .local/users.json + .env.local (never committed)
npm run backend          # FastAPI on :8000, no Meta/Baseten keys, AGENT_BACKEND=none, data in .local/backend-data
                         # (npm run backend:keys = same data, keys from backend/.env; seed first in no-key mode)
npm run seed             # real inputs only: hub_spec site + cameras, QA clips (SYNTHETIC mark), scan_simulated log, one case
npm run dev              # http://localhost:3000
```

Demo roles (investigator / reviewer / site admin) are switched in the sidebar; the Next.js proxy `/api/spoor/*` adds the
token server-side, so the browser never holds one.

## Hub flow (how to read the scan events)

induction station → infeed belt → scan tunnel → merge onto a cross-belt carrier → sorter loop → chute → bag.
So a parcel's "label read at the scan tunnel" comes before "loaded onto carrier N". Sorter events after the tunnel
(carrier assignment, divert, recirculation) carry identity by sorter tracking, not by a new label read. Chute
photo-eye pulses (`bag_drop` in the simulated log) have no identity and are imported as simulated sensor events.

## Generated inputs

| Command | What |
|---|---|
| `npm run gen:types` | TS types from `backend/schemas/*.schema.json` -> `src/contracts/generated/` |
| `npm run gen:hub` | `assets/hub/hub_spec.json` -> `src/data/hub.generated.json` (site plan, cameras, scan points) |
| `npm run export:hub` | copies `assets/hub/build/hub_dressed.blend` to %TEMP% and exports `public/hub.glb` headless (no people, no animated parcels, decimated, Draco). Never writes a .blend |

Nothing in the frontend or the seed reads `render_truth.*`, `flow_truth.json`, `assets/hub/build/truth/` or a scenario
card. Scenario inputs come from `ml/evaluation/scenarios/manifest.json` and `<S>/case_input.json` only.

## Evaluation, scenarios, new-evidence recording

| Command | What |
|---|---|
| `cd ../backend && uv run python ../ml/evaluation/run_hub.py` | scores the no-key answers against evaluator-only truth; headline = D scenarios S1–S5 that have renders + truth (one case per scenario subject), else the control flow with an on-screen caveat; result on the Operator page |
| `npm run seed -- --scenarios <manifest.json>` | one input case per rendered scenario (QUEUE F1) |
| `/wall` (sidebar: Camera wall) | synchronized 2x2 / 3x3 camera wall of a scenario's clips (review 007 #1): scenarios from `ml/evaluation/scenarios/manifest.json` + `<S>/case_input.json` only; a tile plays the backend media whose SHA-256 equals the render file, else says "render not produced yet" / "rendered, not imported". `?case=<id>` shows a case's imported footage. `SPOOR_SCENARIO_MANIFEST` overrides the manifest path |
| Source panel ▶ Play | plays the clip around the selected time (3 s pre-roll) through its H.264 working proxy; the frame counter follows the original's frame table and Pause loads the exact original frame. Still labelled "context, not an observation" |
| `SPOOR_NEW_CLIP=… SPOOR_NEW_CLIP_CAMERA=cam_CAM_11 npx playwright test --config playwright.review.config.ts --project new-evidence` | records the real "new evidence added" flow (QUEUE F2) |

To reset the demo data: stop `npm run backend`, delete `.local/backend-data`, start it again, `npm run seed`.

## Tests

| Command | What |
|---|---|
| `npm run typecheck` | `tsc --noEmit` |
| `npm run lint` | ESLint (next core-web-vitals + typescript) |
| `npm run test:unit` | frame transform, camera geometry, trace contract (solid never bridges a gap) |
| `npm run test:e2e` | Playwright smoke tests on the running no-key stack |
| `npm run review-pack` | screenshots of every surface at 1440x900 and 390x844 into `review_pack/`, plus the recording (`node scripts/make-recording.mjs` -> `review_pack/signature_interaction.mp4`) |

Screenshots named `fx_*` use a route-mocked trace (test fixture) and carry a visible TEST FIXTURE banner: without a SAM
key the backend has no observations to draw.

## Licences

No new third-party assets or fonts (system font stack). `public/hub.glb` is derived from the hub build, whose assets are
credited in `assets/hub/CREDITS.md`. `public/draco/` is the Draco decoder shipped inside the `three` package
(Apache-2.0 code library). Runtime libraries: Next.js, React, three, @react-three/fiber, drei (MIT).
