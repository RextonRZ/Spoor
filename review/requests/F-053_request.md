# F-053 — Settings & data in the flow look, Proof of spend, flow tests 12/12

From the frontend agent.

## 1. Changed since last request
- **Settings & data** (`/operator`, from the avatar menu), in the flow's look. Tabs **Data sources · Cameras & clocks
  · Models · Evaluation**.
  - **Data sources:** three cards (clips from N of 19 cameras, scans in the scan log (simulated), site plan version);
    the four-eyes line "Require a second person to approve reports: **Off** (one-user demo site…)"; the import forms
    and the inbox clock under **"Advanced"** (function kept).
  - **Cameras & clocks:** the camera, footage and scanner-clock tables.
  - **Models:** **Proof of spend** (new `GET /v1/spend`, from the cost ledger: per model and job, calls, tokens in and
    out, units, US$, total, and the share of calls on open weights), which models are on in this run, the Malaysian
    context, and the per-case model trace.
  - **Evaluation:** unchanged.
- **Backend:** `GET /v1/spend` (site admin; sums `CostEntry` rows for the user's sites plus site-level entries).
  Test: `test_spend_sums_the_cost_ledger`.
- **Tests:**
  - e2e flow 12/12 ✓ (Settings added; Investigating is audited once its replay finishes, because rows mid-fade
    measured as low contrast);
  - review pack 18/18 ✓ (`review_pack/flow/*_09_settings.png` added);
  - the breadcrumb's waybill link reads "Case" while loading (axe link-name).

## 2. Check these
- `frontend/review_pack/flow/desktop_09_settings.png`, `mobile_09_settings.png`
- Tests: e2e 12/12 ✓, review 18/18 ✓, backend grounding/api ✓, typecheck, lint and ruff clean.

## 3. Waiting on
- **P0:** the builder's canonical layout-b geometry (F-052). The false sorter-timing conflict stays on Answer,
  Report and the Hub until then.
- **The S2 render**, then the keyed S2 run (`npm run backend:keys` on the S2 store with footage). Estimate before,
  actual after.
