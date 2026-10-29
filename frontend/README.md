# Spoor frontend

Investigation workspace for the Spoor backend (PRD §19, §23): Next.js 16 (App Router), TypeScript, React Three Fiber +
drei. It runs end to end **without model API keys**: model-backed steps show "analysis unavailable" and nothing is
simulated in their place.

## Run the no-key stack (Windows, from `frontend/`)

```bash
npm install
npm run setup:local      # once: random demo tokens -> .local/users.json + .env.local (never committed)
npm run backend          # FastAPI on :8000, no Meta/Baseten keys, AGENT_BACKEND=none, data in .local/backend-data
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

Nothing in the frontend or the seed reads `render_truth.*`, `flow_truth.json` or `assets/hub/build/truth/`.

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
