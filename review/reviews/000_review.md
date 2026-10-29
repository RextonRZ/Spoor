# Review 000 — open issues carried over (CCTV QA of 29 Oct + worker QA)

Verdict: **NOT APPROVED** (baseline). These must be gone in the next CCTV and worker requests.
Check each one yourself in the new render before sending; say "fixed / not fixed + why" per number.

| # | Where | Problem | Required fix | P |
|---|---|---|---|---|
| 1 | CAM_10 | Push clips playing with no cage in the hands | Push only with a cage/pallet jack bound to both hands; otherwise walk | P0 |
| 2 | CAM_10 | Worker kneeling on the floor for no task | Remove; kneel only for a real low pick, ≤ 3 s | P0 |
| 3 | CAM_10 | Worker crouched and frozen | Remove or give a real task | P0 |
| 4 | CAM_10 | Worker walks head-first into a bagging frame (body inside geometry) | Nav paths with ≥ 0.4 m clearance; overlap check on every frame | P0 |
| 5 | CAM_01 | Worker kneeling at an empty pallet | Remove, or give the pallet cartons and a real pick | P0 |
| 6 | CAM_01 | Wrapped pallets read as plain white blocks | Stretch-wrap material: translucent, wrinkles, cartons visible through it, some torn wrap | P1 |
| 7 | CAM_01 | Boom/telescopic conveyors stop short of the lorries | Booms extend into the trailer through the dock door (see dpd_t110/t117) | P0 |
| 8 | CAM_04 | Cross-belt carrier bobbing up and down | Carriers ride a fixed track height; no vertical noise | P0 |
| 9 | CAM_04 | Walker hugging/brushing along the wall | Walkway paths at ≥ 0.6 m from walls, follow the painted walkway | P1 |
| 10 | All | Workers face the camera for long stretches | Auto-flag any worker facing a camera > 2 s; vary headings to the task | P0 |
| 11 | All | Floor reads near-white | See QUEUE B1 — diagnose (preview mode / lost texture / exposure) and fix | P0 |
| 12 | All | Action clip without its object (push, carry, lift, scan) | Auto-check in `qa_checks.py`: an action clip without its bound object/prop = **error**, not warning | P0 |
| 13 | Workers | Hands touching air; parcels not moving with hands; caps going transparent | Parcel-first rebuild (in progress). Accessories opaque, parented, no alpha blend | P0 |
| 14 | Workers | Nothing in the logistics moves while people act | Every person action moves a real parcel/cage on the flow timeline; no "busy" mime | P0 |

Reference look: `docs/hub/reference_frames/README.md` (bright linear LED rows, white walls, mid-grey floor,
red-orange scan tunnel, mesh fences + yellow posts, stack lights, booms into trailers, mixed vest/T-shirt crowd).
