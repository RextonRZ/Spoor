# Improvements: review log and what is left to win

## 2026-10-28 logic review — fixed

Two passes: one by the author, and one independent reviewer that did not see the author's reasoning (12 of its
15 findings were confirmed by running code). Every fix has a regression test (`tests/test_review_fixes.py`,
`tests/test_chunking.py`, and additions to `test_api.py`, `test_perception.py`, `test_evaluation.py`).

| # | Problem | Severity | Fix |
|---|---|---|---|
| R1 | Another site could inject "verified" tracks into a case via `/segment`; `link_track` accepted foreign footage | Critical (tenant isolation) | Case must be visible to the caller and on the media's site; only investigators link; tracks must come from the case's site |
| R2 | Verifier checked IDs and timing but stored the **agent's sentence** as the finding; a hypothesis with dropped claims could still be "supported" | Critical (truthfulness) | Finding text is generated from verified fields; any unchecked claim caps a hypothesis at insufficient; the answer labels agent wording as wording |
| R3 | Exit claim "supported" although the object was seen back in the room (cited, or unzoned) | High | Time-ordered; any later sighting not beyond the door contradicts or blocks the claim |
| R4 | Reviewer could approve a report whose evidence was purged after the draft | High | Approval rebuilds the report and compares a content fingerprint |
| R5 | Streams whose timestamps don't start at 0 cited the wrong frames (frame 5 → ~200) and cut empty clips | High | Relative seeking; proxy cut with the proxy's own frame table; tested with a 20 s offset; empty decodes raise |
| R6 | A site admin could overwrite another site's camera | High | Camera IDs owned by another site are refused (409) |
| R7 | Sensor events were global (listed and cited across sites) | High | `SensorEvent.site_id`; site-scoped import, listing, reports and verification |
| R8 | `/unobserved` accepted another case's object | Medium | Object must belong to the case |
| R9 | Zone membership ignored uncertainty near edges (only checked vertices, and not on the inside) | Medium | Signed distance to edges: within the uncertainty radius = undetermined |
| R10 | Fixed 500 ms gap made 1–5 fps CCTV look like a flickering object | Medium | Gap threshold follows each source's frame interval |
| R11 | Every report labelled footage "staged" | Medium | `recording_kind` declared at upload (required); report label follows it |
| R12 | Purge left clip cuts, model-output caches, manifests on disk | Medium | Purge removes all per-media sidecars |
| R13 | Calibration applied to clips of another resolution gave confident wrong positions | Medium | Calibration records its image size; same-aspect rescale, otherwise refuse |
| R14 | Re-upload dedup re-attributed footage across sites/cameras; coverage could never be added later; perception used the latest clock sync instead of the clip's | Medium | 409 on cross-site/camera dedup; coverage can be registered on re-upload; perception uses the coverage's sync |
| R15 | Evaluation runner crashed on Windows (open SQLite file in a temp dir) | Medium | In-memory store for backend construction |
| A1 | Two cameras seeing the object at once fragmented visibility into hundreds of spans and called cross-camera hand-offs "observed" | High | Visibility merges cameras; solid (observed) motion only within one camera's continuous track (PRD §14.3) |
| A2 | Per-observation queries: unusable at real footage sizes | High | Batched estimate lookup; 3,000 observations in well under a second |
| A3 | Coverage from other sites leaked into "covering cameras" | High | Coverage filtered to the case's site |
| A4 | Agent claims about another case's objects or site were accepted | High | Rejected before verification |
| A5 | Clips over SAM's 15,000-frame limit would fail | High | Verified contiguous chunks; per-chunk tracks never silently stitched |
| A6 | Concurrent investigations of one case raced | Low | Per-case lock |
| m | Cache hits duplicated records; review chains could half-apply; link collisions were 500s; eval scored errors as correct "unknown" | Low | Reuse on cache hit; atomic status chains; 409; errors never score |

## Added to strengthen the entry

- **"New evidence added" diff** — `GET /v1/cases/{id}/diff` (PRD §19.3 signature moment).
- **Render-ready replay** — `GET /v1/cases/{id}/replay`: solid / dashed / grey with the contract embedded.
- **Annotated derivative frames** — box drawn, image stamped "ANNOTATED DERIVATIVE", header says so (PRD §7.3).
- **Operator/judge trace** — `GET /v1/operator/cases/{id}/trace`: every Meta model call, frames billed, tokens, the
  agent causal chain (PRD §23; evidence for the "Meta AI tooling" criterion).
- **Change-detection baseline (CD)** in the evaluation, as the PRD requires (§1.3).

## What is left — ranked by impact on judging

| Rank | Item | Rubric | Needs |
|---|---|---|---|
| 1 | Run the provider smoke tests; fix whatever the live API does differently | All (nothing works without it) | API keys |
| 2 | Record staged footage for C01–C10 + labels | Impact, Technical depth | Room, 2 phones, actors |
| 3 | Real evaluation table A0 / CD / A1 / A2 / A3, with failures written up | Technical depth, Impact | 1 + 2 |
| 4 | Frontend: 3D replay + "where did it go?" click-through to the source frame + evidence diff | Demo | Your frontend decision |
| 5 | Time-to-finding: time a person scrubbing footage vs. using Spoor on the same case | Impact (the headline number) | 2 + 4 |
| 6 | Baseten Muse Spark Open benchmark for agents (open-weight bonus) | Meta AI tooling, bonus | Baseten key |
| 7 | Calibrate the real room; fill `docs/CALIBRATION.md` | Technical depth | Tape measure |
| 8 | Run store tests on Postgres; build the Docker image | Reproducibility | Docker Desktop running |
| 9 | Confirm rubric weights and track enrolment in Discord | — | You |

Not worth doing before the deadline unless 1–5 are done: multi-view XYZ on a real rig, appearance encoder,
LLM verifier challenger, Muse Wonder.
