# F-052 — F-047..F-051 fixes: four-eyes site setting, P0 status, flow tests, clean S2 store

From the frontend agent.

## 1. Changed since last request
- **Four-eyes as a site setting** (your decision).
  - `Site.require_second_approver` defaults to **on** (real sites). The approve route still refuses self-approval
    when it's on.
  - With it **off**, a shared report reads **"Investigation summary · decision support"**, with no DRAFT banner.
  - The demo site is seeded with it **off**. Test: `test_four_eyes_is_a_site_setting`. Settings will show it as one
    line (next).
- **P0, false "Records disagree"**: the frontend half is ready but blocked on the canonical geometry.
  - Both specs have **identical scan points**; they differ only in `line_a.layout` ("a" vs "b").
  - `frontend/scripts/site_plan.py` builds conveyor routes from the spec's geometry and **doesn't model layout b**:
    induct at the loop merge, belt order `induction_B, merge, tunnel, …`.
  - Pointing it at `hub_spec_lineAb.json` therefore changes nothing. The route has to come from the builder's
    canonical layout-b geometry (belt polylines, the induct/merge order), and I won't guess it.
  - **Builder:** please say which file is canonical and where the layout-b belt path is (`flow.py` builds it at run
    time). I'll then:
    1. seed and gen:hub from it;
    2. re-run S2;
    3. add the test "no belt-timing conflict on S2's subject with the canonical plan".
  - Until then, Answer, Report and the Hub still show the false conflict.
- **S2 demo store rebuilt clean.** The builder regenerated `events_scan_simulated_S2_long.jsonl` at 09:15 (4,424
  rows, 14:09–14:36), and a re-seed would have mixed both versions.
  - The old store is kept as `.local/backend-data-s2-mixed-1040`.
  - New store: 3,349 scans, 25 cage memberships, 1,066 photo-eye pulses; new case `case_18e37cf158630d40962419f1`.
  - **New finding (builder):** on this log the inbox flags **16 stalled parcels**, all "went into chute C07/C10 at
    14:09–14:10, no bag scan since" (24–25 min). Either the sim leaves those parcels in the chutes or bagging scans are
    missing from the log. S2's own subject is not among them (its last scan is the 14:11 divert; the 14:21 cage add is
    a membership).
- **Tests: the old suites targeted deleted screens, so they are replaced.**
  - `tests/e2e/flow.spec.ts` (11 tests): every screen loads with no page errors, shows its content, has no em dash,
    passes axe AA (no serious/critical), and shows no role switch. Hub → Investigate streams real steps. The account
    menu has no role switch. A held voice note on Go look is sent as 16 kHz mono 16-bit WAV (fake microphone, route
    mocked only to capture the upload). **11/11 ✓.**
  - `tests/review/flow.spec.ts`: 16 shots (8 screens × desktop/mobile) in `frontend/review_pack/flow/`. **16/16 ✓.**
- **Contrast deviation from the prototype:** the prototype's `#5A5F69` text (taglines, map column labels, log times,
  "No footage" labels) fails WCAG AA on these dark surfaces. Those texts now use `#8B909B`; everything else matches.
- **Robustness:**
  - The Investigating screen falls back to reading the stored run if the event stream drops, so it never stays on
    "Starting the crew".
  - The replay works under React StrictMode.
  - A failed start shows its error.
- **Duplicate `<main>` landmarks fixed:** pages use `<div>` inside the top bar's `<main>`.
- **Local commit `5e4c9da`** (the flow; not pushed). It also picked up `frontend/scripts/logo-proof.mjs`, which wasn't
  mine but lives in the frontend folder.

## 2. Check these
- `frontend/review_pack/flow/*` (fresh run on the clean S2 store)
- Tests: e2e 11/11 ✓; review 16/16 ✓; backend test_grounding/test_api ✓; typecheck, lint and ruff clean.

## 3. P1 notes (after the S2 render)
- Proof's default tile becomes the most telling camera (CAM 19 carried in) once frames exist. Report thumbnails
  become the 4 real key frames. Go look already shows one place at a time, the most likely first.

## 4. Next
Settings › Data sources + Models (proof of spend, the four-eyes line), then the layout-b plan fix as soon as the
builder names the canonical spec.
