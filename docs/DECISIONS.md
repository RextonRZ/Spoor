# Decisions

Format: date · decision · why · alternatives considered.

## 2026-10-27 · Backend is one Python package (`backend/src/spoor`), not many packages

PRD §24 recommends a modular monolith. The PRD's suggested `/services/*` + `/packages/*` layout is implemented as
sub-packages of one `spoor` package (`contracts`, `ingest`, `spatial`, `store`, `perception`, `reasoning`,
`verification`, `agents`, `api`). One `pyproject.toml`, managed by `uv`. Evaluation ground truth will live outside
this package (`ml/evaluation`) so runtime code cannot import it (PRD §8.1).

## 2026-10-27 · Frontend deferred

Owner is still deciding the frontend approach. Backend exposes HTTP + JSON Schemas so any frontend can plug in.
See `docs/build/12-frontend.md`.

## 2026-10-27 · No model training in the core build

PRD §5.5 puts training bespoke video models out of scope. SAM 3.1 and Muse Spark are used as hosted pretrained models;
OpenCV calibration is measurement (homography from measured floor points), not learning. The only "fitting" we do is
camera calibration and choosing thresholds on validation footage.

## 2026-10-27 · Meta API via OpenAI SDK + `meta-sam-parser`

Meta docs show the OpenAI SDK with `base_url=https://api.meta.ai/v1`. SAM output is parsed with Meta's
`meta-sam-parser` (SAM License) rather than a hand-written token parser.

## 2026-10-27 · OpenCV pinned to 4.x (4.14), not 5.0

The resolver picked OpenCV 5.0.0, but the PRD's geometry references are the OpenCV 4.13 docs and §13.4.5 asks to pin a
verified 4.x API. 4.14 provides every function we need (`findHomography`, `perspectiveTransform`, `undistortPoints`,
`triangulatePoints`, `solvePnP`, `calibrateCamera`, `projectPoints`). Revisit 5.x after the hackathon.

## 2026-10-27 · Evidence records persisted as JSON manifests until step 04

Ingest writes `MediaAsset` manifests + frame tables as JSON in the data dir. Step 04 moves records into the database;
the JSON files remain as a recoverable sidecar.

## 2026-10-27 · Zone image regions for off-floor items

A floor homography is invalid for items on shelves or desks (PRD §13.2 step 6). Cameras carry operator-drawn image
regions per zone; an item inside a measured surface's region gets `anchored_height` at the zone centroid with the
zone's radius as uncertainty — honest, coarse, and never presented as a measured XY.

## 2026-10-27 · Lead and Verifier are deterministic; Evidence and Hypothesis are LLM agents

PRD §17.1 lists four roles and says deterministic services must not become agents "merely to increase the count".
The Lead/Orchestrator is code (fixed, auditable plan) and the Verifier is the deterministic engine (the only
non-human path to `supported`). LLMs do what they are good at: choosing evidence to inspect and proposing competing
hypotheses as structured claims. Consequence: without any model the system still returns a verified last-seen answer
(ablation A2), and A3 must beat A2 to justify the agents (PRD §21.4). An LLM "challenger" for the verifier can be added
if evaluation shows a benefit.

## 2026-10-27 · Agent protocol is a JSON action envelope, not provider tool-calling

Each turn returns `{action, tool, args_json, final_json}` validated locally. Works identically on Meta Muse Spark and
Baseten Muse Spark Open, and keeps argument validation and scope checks in our code.

## 2026-10-27 · Track-to-object linking requires a human-verified start

SAM IDs are per video and lookalikes exist (C03). A track becomes evidence about the case object only if the
investigator selected the instance (box/point prompt, single resulting track) or confirmed it through the API.
Concept-prompt tracks on other clips are `candidate_cross_camera` until confirmed.

## 2026-10-27 · SQLite for development, Postgres targeted but untested

Same schema and triggers for both dialects; ref inserts use dialect-specific ignore-on-conflict. Postgres has not been
run yet. Run the store tests against Postgres before relying on it.

## 2026-10-27 · No appearance encoder bundled for cross-camera association

The association module accepts an optional object-appearance vector but ships none: no encoder has been evaluated or
licence-checked yet, and this machine has no GPU. Without appearance, matching relies on time, topology and geometry,
and abstains when ambiguous.

## 2026-10-27 · Blank `.env` values mean "not configured"

Found during review: `MODEL_API_KEY=` would have built clients with an empty key and `URL_SIGNING_SECRET=` would have
signed links with an empty HMAC key. Blank values are now coerced to unset (tested).

## 2026-10-28 · Finding text is generated, never copied from an agent

Found by independent review: the verifier checked a claim's IDs but stored the agent's sentence as the finding, so
unverified prose ("carried out of the building") could become a "supported" fact. `Verifier.describe()` now builds
the statement from verified fields (object label, frames, times, mapped positions with "estimated" marked). Agent
wording is shown only as "agent's wording". A hypothesis is SUPPORTED only if every proposed claim was checked.

## 2026-10-28 · Visibility vs tracked motion are separate notions

Visibility merges all confirmed cameras (the object was seen). "Observed" motion requires one camera's continuous
track. A hand-off between cameras is drawn dashed (PRD §14.3).

## 2026-10-28 · Continuity gaps follow the source frame rate

`max(500 ms, 2.5 × frame interval)` per track, so 1–5 fps CCTV does not produce fabricated gaps.

## 2026-10-28 · Uploads declare what the footage is

`recording_kind` (staged_event / real_incident / synthetic_test) is required at upload and drives the report's
provenance label; nothing is assumed.

## 2026-10-28 · Report approval checks evidence, not only revision IDs

Approval rebuilds the report and compares a content fingerprint (generation time excluded). Purges, reviews and
invalidations after the draft therefore block approval.

## 2026-10-28 · Use case pivots to a parcel sorting hub; scans are identity evidence

Owner decision after research (`reports/Parcel hub tracking and investigations.md`). Scans get their own `ScanEvent`
record rather than reusing `SensorEvent`, because a scan *identifies* the parcel (the opposite of a door sensor) while
saying little about where it went next. Event kinds, fields and container semantics follow UPU EMSEVT, GS1 EPCIS 2.0.1
and carrier tracking models; CBV has no `sorting` bizStep, so sort events use our own `ScanEventKind`.

## 2026-10-28 · Container location is inherited and estimated; relabels are aliases

`ContainerMembership` links are time-bounded and versioned; location through them is labelled estimated and can be
contradicted (e.g. a bag emptied at the next hub without the parcel). `IdentifierAlias` prevents a relabel from looking
like a disappearance.

## 2026-10-28 · Clocks are fitted per domain, not trusted

Research: CCTV recorders drift seconds per week; parcels on a belt are ~200 ms apart. `fit_clock()` fits offset and
drift from matched anchors with MAD-based mismatch rejection; the fit's anchors and residual p95 are stored on the
`ClockSync`. Drift reference is separate from the validity window so scans before the first anchor are still covered.

## 2026-10-28 · Import is atomic and idempotent; the file is never trusted for IDs or labels

The importer assigns scan IDs, site and real/simulated label; a re-import of the same log is skipped. Found during
testing: corrections repeat the corrected scan's identity and time, so the duplicate fingerprint includes
`corrects_scan_event_id` (otherwise every correction would have been dropped as a duplicate).
