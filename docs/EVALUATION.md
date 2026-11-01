# Evaluation

**Status (2026-11-02):** measured on the synthetic hub (scenario S2, 19 cameras, 90 s, rendered; scan logs labelled
`scan_simulated`), with live models: Muse Wonder plans, Muse Spark Open agents (Baseten), SAM 3.1, the deterministic
verifier. Results are in "Hub S2: keyed runs and control parcels" below. The A0-A3 variant table further down has not
been run on the hub yet.

## Hub S2: keyed runs and control parcels (2026-11-02)

Ground truth (the render's flow truth) is read only here, after each run; never by the app or in a prompt.

**The S2 parcel** (CTX334048419302, last scan: put in cage RC-760 at 14:21:33; truth: carried into the Exception store
at 14:32:32 and still there when the footage ends). Keyed runs 12 to 18, same store, same footage:

| Runs | Answer | Correct |
|---|---|---|
| 12, 13, 14, 15, 16, 18 | "Most likely in the Exception store (Z11), where no camera sees inside: last seen at its door at 14:32:30 on CAM 19, carried in, not seen coming out until the recording ends at 14:33:36, assuming the door is the only way in (site plan)" | 6 / 6 |
| 17 | run failed (a crash describing a rejected claim; fixed, test added) | - |

Each run: Muse Wonder planned first (1 step kept: the doorway camera), about 66k-110k Spark Open tokens, 70-210 s,
Wonder US$0.08-0.18. The verifier's "stayed inside" rule is general (last seen within reach of an unwatched area's edge, a
likely carrier goes in within -3..+10 s, at least 10 s of coverage after); no S2 names in prompts or rules.

**Control parcels** (no code changes, same footage, opened the way the Hub opens a case, one keyed run each):

| Parcel | Why it is a control | Truth at the end of the footage | Spoor's answer | Verdict |
|---|---|---|---|---|
| CTX976456695076 | the look-alike: same size as the S2 parcel, on the belt at the same time | in chute C08 (divert scan 14:32:35.8) | abstained: "never visibly confirmed"; no "most likely" | safe: NOT placed in the Exception store; not located either |
| CTX119368214201 | an ordinary belt parcel | in chute C02 (divert scan 14:32:38.7) | abstained; the right idea ("diverted into chute C02") proposed but Unproven | safe; missed: the scan says C02, no camera check was made |
| CTX639569664089 | unload scan only (14:33:04), nothing after | on the inbound belt, not yet at the tunnel | abstained; "not established" | correct abstention |

Tokens per control run: 58k-111k Spark Open in, 7.7k-11k out; Wonder US$0.08-0.18; 160-519 s.

What the controls show: no false location in 3 of 3 (the look-alike is not mistaken for the S2 parcel), but 0 of 2 belt
parcels located. The answer ignores what the divert scan says when no camera confirms it ("never visibly confirmed"),
and the agents did not aim SAM at the chute cameras after the divert. Both are listed as improvements; a parcel that
was caged and then left normally does not exist in the S2 scan log (the only cage scan with a waybill is the S2 parcel),
so that control is not run.

**On-site triage (Muse Glimmer, Modal A100):** 855 frames from all 19 cameras (one every 2 s), US$0.62, 0 unparsed.
Footage sent on to the cloud models: 286 s of 1,710 s (17 %, 83 % less), each flag sending from the sample before to
the sample after. Key moments: CAM_13 14:32:10-12 (the pick from the cage) covered; CAM_19 14:32:21-31 covered, 14:32:32
not. With only the flagged frame's own 2 s (±1 s), 187 s would be sent but the CAM_13 pick would be missed.

## Question being tested (PRD §21.1)

Does a persistent evidence graph plus bounded agent investigation produce more accurate, better-grounded answers than
asking a video model directly?

## Variants (PRD §21.4)

| Variant | What it is |
|---|---|
| A0 | Muse Spark 1.3 reads the clip(s) and answers in one structured reply |
| CD | Deterministic change detection on the operator-selected region (no model; PRD §1.3) |
| A1 | SAM 3.1 tracks only: latest detection, no graph, no verification |
| A2 | SAM + evidence store + deterministic verifier and orchestrator, no LLM agents |
| A3 | A2 + Evidence/Hypothesis agents |

If A3 does not beat A2, the agents are simplified or the limited benefit is explained (no invented percentages).

## Firewall

`scenarios/*.json` (inputs) and `ground_truth/*.json` (labels) are separate files and types. The runner produces every
prediction before loading any label. A test fails if runtime code under `backend/src/spoor` mentions the evaluation
package or ground truth. Target initiation (an operator box on one frame) is an investigator input, not an answer.

## Metrics

Last-seen accuracy (time within tolerance AND zone), median time error, zone accuracy, left-the-area accuracy,
event precision/recall (temporal IoU matching), spatial error median/p95 (m), abstention precision/recall, model calls,
tokens, latency. Citation validity and unsupported-claims-per-100 come from a **blind human review** CSV
(`metrics.citation_review`).

## Running

```bash
cd backend
uv run python ../ml/evaluation/run.py --dataset ../ml/evaluation/datasets/<name> --variants A0,A1,A2,A3 --split holdout
```

Writes `data/evaluation/latest.json` and `latest.md`; the API serves the latest at `GET /v1/evaluations`.

## Results

| variant | n | last-seen acc. | median time err (s) | zone acc. | left-area acc. | abstention P / R | calls |
|---|---|---|---|---|---|---|---|
| — | — | not yet run | — | — | — | — | — |

## Failure cases

- Belt parcels with a divert scan and no camera sighting are answered "never visibly confirmed" (controls above): the
  scan is shown on the Answer screen but the investigation does not say "last scanned into chute C02".
- Agents' wording can say more than their claims: in keyed run 13 an idea worded "exited ... carried out" was marked
  Passed because its only claim was the stay-inside check. The prompt now requires claims that test the wording; the
  Answer screen shows ideas only behind a toggle, with the check that decided each.
- Muse Wonder returned an empty plan (run 10) and invented a camera and a date (run 11): an empty plan is retried once,
  and a plan whose steps all fail the checks is sent back once with the reasons.
- Run 17 crashed while describing a rejected claim that named an area as a door zone (fixed, test added).
