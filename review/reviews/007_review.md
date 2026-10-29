# Review 007 — F3 evaluation, F4 demo script, F5 polish (+ F1/F2 prep, scan log v2)

Verdict: **APPROVED WITH FIXES.** The evaluator is honest and well fenced (truth read in phase 2 only, after every
prediction; boundary tests; on-screen caveat). Routed hypotheses now follow the loop counter-clockwise to C04 — reads
right. Scan log v2 mapping (container_opened/closed, bag→cage, late handheld uploads) is correct EPCIS-style thinking.
Checked: operator_evaluation_1440.png, fx_16, DEMO_SCRIPT.md, request text.

## Fixes
| # | Where | Problem | Required fix | P |
|---|---|---|---|---|
| 1 | Demo script | The synthetic CCTV — the most impressive thing we built — never plays on screen. Judges see stills and tables only | Add a 10–15 s opening hook: a 2×2 or 3×3 synchronized **camera wall** of the scenario clips with OSD + SYNTHETIC mark, then "a customer says parcel CTX… never arrived". In the app: a play/pause control in the source panel that plays the original clip around the selected time (still frame-accurate, still labelled "context, not an observation" unless a model observation exists) | P1 |
| 2 | Demo script | Every 🔑 step degrades to "unavailable". Meta tooling is 25 % of the score, so the no-key path can't be the main story | Write the script **keys-first** (what SAM 3.1 + Muse Spark do at each step), with the no-key column as fallback. In `FOR_REXTON.md` add one line: getting the Meta keys and running the smoke tests is the top blocker for the demo | P1 |
| 3 | Demo script | Starts at the Cases list with no problem statement | Open with the problem in one sentence (lost-parcel claim; scan log says where it was *scanned*, not where it *went*), then the camera wall (#1), then the case | P2 |
| 4 | Evaluation | On the control flow "last seen 100 %, median 0.0 s" is expected (WCS = reference clock); it proves little | Keep it, but the headline numbers should come from the D scenarios (no-read, relabel, phantom containment, mis-load, look-alike, blind spot, drifting handheld clock), where the score can actually fail | P2 |

## Answer — Q1 (scenario manifest)
Yes, one manifest — but agree the location with the builder: the builder already writes per-scenario
`ml/evaluation/scenarios/<S>/case_input.json` (question only) + `scenario_card.md` (**evaluator-only**) + `manifest.json`.
Use that manifest; don't create a second one. Rule: the seed may read `manifest.json` (clips dir, scan-log slice, clip
start) and `case_input.json` only — never `scenario_card.md`. The **waybill/parcel ID belongs in `case_input.json`** as part
of the customer complaint (a legitimate input), so the seed never needs the card. Builder: please confirm that in
`case_input.json`. Note the scenario IDs differ between your text ("S3 · Wrong bag at bagging") and the builder's
(S3 = phantom containment) — take IDs and titles from the manifest only.
