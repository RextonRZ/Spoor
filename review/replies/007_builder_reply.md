# Reply to review 007, Q1 (builder)

**Confirmed:** there is one manifest, at `ml/evaluation/scenarios/manifest.json`. Per scenario:
- `<S>/case_input.json` carries the inputs only:
  - `waybill`: the parcel ID, as the customer gives it (null for the S4 cage case);
  - `complaint`: one sentence;
  - `subject_id` / `subject_kind`, `question`, `window`, `cameras`, `scan_log`, `clips`.
- `scenario_card.md` stays evaluator-only.

Scenario IDs and titles: S0 control, S1 no-read rework, S2 removal into the blind spot, S3 phantom containment, S4 mis-load (RFID cross-read), S5 look-alike pair. These match `make_cards.TITLES` and the manifest.
