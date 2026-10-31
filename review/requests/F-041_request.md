# F-041 — J3 search grounding: Malaysian context in every report (cited, dated, official sources marked)

From the frontend agent.

## 1. Changed since last request
- **Backend.**
  - New immutable, hashed, site-level record `LegalContext` (`lctx_`): `contracts/context.py`, table
    `legal_contexts`, schema exported, TS type generated.
  - `spoor/grounding.py` asks Muse Spark 1.3 (standard mode, not Contributor) with
    `tools=[{"type":"web_search","user_location":{"country":"MY"}}]`, per dev.meta.ai/docs/search-grounding.
  - It asks 3 narrow questions, one request each, as the docs advise:
    1. Act 741: MCMC's role and liability for loss;
    2. how to complain about a lost parcel, the time limits, and when to escalate to MCMC;
    3. compensation and claim limits.
  - **Deterministic check before storing:**
    - only the final message counts;
    - a sentence is kept only if a `url_citation` falls on it, and the rest are dropped and counted;
    - the model narrating its own tool use ("Now I'll open…") is dropped and counted;
    - links are stripped from the shown text;
    - sources no kept sentence cites are pruned and the rest renumbered;
    - `.gov.my` sources are marked official.
  - Routes:
    - `POST /v1/sites/{id}/legal-context`: site admin; paid; returns 503 with no key; writes a cost entry with
      tokens and searches.
    - `GET /v1/sites/{id}/legal-context`: latest record, availability, and the measured estimate.
- **Report.** New section "Malaysian context (from the web, cited and dated)":
  - per question, the cited sentences with [n] markers, and "N uncited sentence(s) left out";
  - the numbered sources with domain and an "official" tag;
  - "Retrieved … by muse-spark-1.3 with web search (N searches)", the not-evidence label, and the record id and
    SHA-256;
  - with no record, it says "Not retrieved" honestly. The Evidence Act footnote is unchanged.
- **Frontend.** The Operator → Model calls tab has a "Malaysian context for reports" panel:
  - the answers with [n] markers and the sources tagged official or secondary, each a link;
  - the retrieval date, searches, cost, and the count of sentences left out;
  - an admin button that states the measured cost: "Refresh the Malaysian context · about US$1.00".
- **The real run happened, and it cost much more than estimated.** **US$0.9992 against my US$0.06 estimate**:
  653,514 input / 12,311 output tokens and 52 web searches in 120 s.
  - The search result pages bill as input tokens.
  - It is under the $10 single-run rule and far under 75 % of the cap. Logged before and after; running total Meta
    ≈ US$1.12 / $60 in `FOR_REXTON.md`.
  - The app's estimate now shows the measured US$1.00.
  - I did not re-run.
  - The first run predates the narration rule. I applied that rule to the recorded result, which removed 1 sentence
    (narration glued to a claim) and never edited any text. The stored version has a new id and hash.
- **Result:** 11 cited sentences; 4 sources, of which 1 is official (mcmc.gov.my).
- **My check of the content.** Sections 4, 31, 33, 49–52 of Act 741 as the answer states them match a second copy of
  the Act (LawPlayer), except one word: the model's s.31 sentence says "malicious, negligent **or intentional**", and
  that copy says "maliciously or negligently". The official Laws of Malaysia portal page returned "Invalid request" to
  my fetch, so this was not checked against the official text.
- **Weak spot:** source [1] (Act 741 text) is an unofficial PDF mirror, shown as "secondary". The prompt now says to
  cite lom.agc.gov.my for statute text, not mirrors. That only takes effect on the next run (about $1).
- Tests:
  - backend 246 ✓, including 5 new grounding tests (parser, narration + pruning, pricing, report section, no-key
    API);
  - e2e + a11y 21/21 ✓, plus the new a11y test on all Operator tabs ✓;
  - review shot ✓; ruff, typecheck and lint clean.
- `docs/META_MODEL_USAGE.md`: J3 row in the smoke table.

## 2. Check these
- `frontend/review_pack/desktop/40_j3_malaysian_context.png` (and mobile)
- `frontend/review_pack/desktop/13_report_draft.png`: the new report section
- `backend/src/spoor/grounding.py`, `backend/tests/test_grounding.py`

## 3. Questions
- Re-run once (about US$1) so statute text cites lom.agc.gov.my instead of the mirror? I'd rather you or Rexton OK
  it first, given the estimate miss.
- s.31 "intentional": leave the model's sentence as retrieved (cited, with the source shown), or should the report
  carry a reviewer note? I can't edit the model's text.
