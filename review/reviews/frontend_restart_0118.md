# Frontend agent restarted (Rexton 01:17 Sat 31 Oct)

Lanes (two agents work at the same time — do not edit each other's files):
- Frontend agent: `frontend/`, `backend/`, `ml/evaluation/` (scoring only), `docs/`. Request files named `F-NNN_request.md`.
- Builder (CCTV): `assets/`, `qa/`, Blender, renders. It owns hub.glb export and hub_spec; ask it (via review/) if you
  need geometry/camera data changed.
Order for the frontend agent:
1. Review 012 fixes (report reads like a document: no raw headers / False / None / raw JSON, one time zone (MYT) with
   device-clock notes, complaint block, Sources consistent).
2. Block I backend (I2 → I3 → I1 → I4 → I6 → I5 → I7 → I8 → I9) with pytest for each.
3. Block H frontend (H1, H2, H10 first), design bar in journey_view_0030.md; until the S2 render exists use test data
   clearly marked as test (fx_ / yellow banner) and never show it as a result.
4. Never touch keys: keys live in backend/.env (Rexton puts them in). No paid services. No pushes.
Proof per item: request file with screenshots 1440×900 + 390×844 and, for H items, a ≤ 30 s screen recording.
