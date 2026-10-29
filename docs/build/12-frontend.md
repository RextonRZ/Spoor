# Step 12 — Frontend (DEFERRED)

**Status: on hold — the owner is still deciding how to build the frontend.** Nothing in steps 00–11 should depend on
a frontend decision. The backend exposes everything over HTTP (step 09) and exports JSON Schemas (step 01), so any
frontend approach can plug in later.

## What the PRD asks for (for reference when designing) — §19, §23

Surfaces (§19.2): case overview · 3D scene (room, shelves, doors, camera frusta, observed positions, uncertainty) ·
one canonical timeline with clock-drift warnings · movement trace (object / anonymous people / all) · synchronized
source panel (original vs annotated toggle) · evidence graph view · agent panel (live tool activity, no fake typing) ·
report review/export · separate operator/showcase surface (§23).

Signature interaction (§19.3): "Where did the blue case go?" → camera flies to last confirmed position → solid green
observed segments, amber dashed hypothesized links, grey unknown gaps → click any segment to see the exact source
frame → request another camera → "new evidence added" diff.

Hard rules 🔒: solid lines never bridge gaps; every marker shows its `spatial_mode`; non-colour encodings for
evidence labels; 2D floor-plan fallback; reduced-motion support; no decorative fake metadata.

PRD default stack 🧭: Next.js + React + TypeScript, Three.js / React Three Fiber + drei, GLB room from Blender.

## Backend contracts the frontend will need (already planned)

- `GET /v1/cases/{id}/state`, `GET /v1/cases/{id}/world-at?time=` (step 09)
- `GET /v1/cases/{id}/evidence/{obs_id}` → signed frame/clip URL (step 09)
- Generated TS types from `packages/contracts/schemas` (step 01)
- Site Z-up → renderer Y-up transform (step 03)
