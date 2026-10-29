# Review 008 — Camera wall, play control, keys-first demo script, scenario headline

Verdict: **APPROVED.** The wall is exactly the hook we needed and stays honest (SHA-matched tiles, "Render not produced
yet" instead of filler, one wall clock with the ±5 s caveat). Play/pause lands on the exact original frame and keeps the
"context, not an observation" caption. Keys-first script with the fallback column is right. Checked: 20_camera_wall,
22_source_context_playing, request text.

## Answers
- **Q1 hook layout:** adaptive grid with no empty slots — 4 cams → 2×2, 5–6 → 3×2, 7–9 → 3×3; order from `case_input.json`.
  Click a tile to enlarge it (others shrink to a strip) so the narrator can point at the blind-spot entry. For the opening
  use S2 with all its cameras.
- **F1 one site per scenario:** agreed — good catch on stacked coverage and mixed scan logs for the same parcel IDs.

## P2
| # | Where | Note |
|---|---|---|
| 1 | Repo root | `pytest` from the root collects `assets/hub/*_test.py` and errors. Add a root `pytest.ini`/`pyproject` `testpaths = backend/tests ml/evaluation/tests` (or rename the builder scripts) so one command runs clean for judges |
| 2 | 20_camera_wall.png | Page is captured scrolled; the "Case footage · synthetic" header is cut off. Re-shoot from the top |
