# Reply to reviews 009d / 009e + owner rule (builder): plan and cost

All accepted. Pass 3 is stopped (obsolete); nothing renders until the gate passes clean.

## Time budget (honest)
- **Batch** after the CCTV-pass speed-up (0.8 s/frame):
  - 2688×1520: ~45 h;
  - 1080p: ~27 h (Rexton's call, see FOR_REXTON).
- **Spoor evaluation + buffer:** ~14 h.
- **So the batch must start by about Nov 2 01:00** at 2688×1520, or Nov 3 at 1080p.
- That leaves **~63 h for A4** at full res, ~81 h at 1080p.

| Work (in this order) | Estimate | Notes |
|---|---|---|
| 1. Headwear seated + `accessory_fit` QA (rim–skull ≤ 1.5 cm, up-axis ≤ 8°, every frame) | 1.5–2 h | First; Rexton saw it. |
| 2. Global collision check (people as bone capsules + mesh samples, parcels, bags, cages vs everything static + moving; 1 cm; pair-type counts; worst-20 crops), plus the static-scene check at frame 1 | 3–4 h | Becomes the gate (no GATE_FORCE anywhere). |
| 3. Zero-interpenetration fixes: palms on outside faces (sockets were 1 cm *inside*); inductor spacing ≥ 0.6 m (aisle widened or 2 inductors); dock step-back (now required: no collision-free top-row pick without it); walkers / pushers path-plan around people | 8–14 h | Iterative: fix → re-run → check. |
| 4. Motion principles 1–6: upright reach + step instead of a slump (cap 45 cm); eased moves with anticipation / overlap / follow-through; mass-scaled lift with knees and a settle; gaze leads hands; breathing + weight shift + ±15 % tempo per worker; short glances / nods | 6–9 h | One shared layer in the contact solver, so every station gets it. |
| 5. Induction line B (SP-INDUCT-B / SP-TUNNEL-B, spec topology, `scenario_support`, 30–35 % occupancy; story parcels unchanged) + frontend seed mapping | 4–6 h | The frontend agent works in parallel. |
| 6. AndyData mocap base for inductors + dock (download CC BY 4.0 BVH, world-space retarget to Biped, segment pick/carry/place, IK only for the last 10–15 cm) | 10–16 h | Highest risk. |
| Re-runs, QA, follow-cams (side for pushers, front for inductors), 1 fps crops, measured carton counts, request + review rounds (~3) | ~10 h | |

**Total: 1–5 alone ≈ 33–45 h; with 6, 43–61 h.** That fits at 2688 only with no slack; at 1080p with ~20 h slack.

**Proposal:**
- Do **1 → 5 first** (certain wins, and they unblock the gate).
- Start **6 (AndyData) for the inductors only** when 1–5 pass. Use it only if a test clip clearly beats the procedural layer; otherwise report numbers and stop.
- Recommend **1080p** to make 6 affordable.

Requests come per milestone: headwear + collision report first (request 011), then motion, then line B.
