# Request 020 — Frontend: review 012 fixes (the report as a claims hand-over document)

From the frontend agent. Next: QUEUE block I (I2 → I3 → I1 …) then block H, on labelled test data until the S2 render lands.

## 1. Changed since last request
Fixed from review 012: 1, 2, 3, 4, 5, 6, 7 (7 partly: see below).

- **#1 Human labels.** Every report table now has plain headers ("Gap since previous scan", "Uploaded late", "Device",
  "From / To", "Master SHA-256", "Received", …). Cells: Yes / No, "—" for empty, seconds as "4.7 s". No Python literals.
  Backend test asserts no `<td>None</td>`, `<td>False</td>` or raw field names in the page.
- **#2 One time zone.** Every time in the document is MYT, written "28 Oct 2026, 14:32:07.9 MYT". One footnote: "All times
  are Malaysia Time (MYT, UTC+08:00). Stored records and the JSON download keep ISO 8601 times with their UTC offset."
  Malaysia has no DST, so a fixed +08:00 is exact. The Report page caption now says the same.
- **#3 Complaint block** (first section): case reference, claim reference, waybill, date reported, opened by (user + time),
  and the customer's complaint as reported.
  - `Case` gained three optional fields: `claim_reference`, `complaint`, `reported_at`. Schemas and TS types regenerated.
  - "Start a case" form has the three fields.
  - The scenario seed copies `complaint` from `<S>/case_input.json`. It does not invent a claim reference or a date
    reported, so those read "not recorded" unless someone enters them.
  - The default no-key case was opened before this change, so it shows "Not recorded when the case was opened."
- **#4 Sources used.** New `sources_used`: the CCTV masters reviewed (camera, media id, SHA-256, footage type) plus the
  scan-log batches. A separate line lists what findings cite ("none" today). Every empty section now has one sentence that
  says why, e.g. "No floor calibration was used (no spatial estimates)". "None. None." is gone (asserted in the test).
- **#5 Processing** is a short list: models used none, model calls 0 (0 from cache), agent steps 0, tokens 0 in · 0 out.
  The JSON is in a collapsed "Processing record (JSON appendix)", and still in the report JSON download.
- **#6 CCTV reviewed.** The clock cell is now short, e.g. "±5 s · unverified, uploader-declared [1]". The full method
  text appears once, as footnote [1]. Camera IDs read `CAM_01` everywhere, continuity included. Working copy reads
  "d5b4b29f18ade002… · converted format (H.264)".
  - The report JSON also keeps structured `clock_offset_ms`, `clock_uncertainty_ms`, `clock_method` and
    `working_copies`.
  - Reports stored before this change still render, falling back to their stored sentence.
- **#7 Malaysian context.**
  - **Added:** one footnote for the Evidence Act 1950 (Act 56) s.90A(2) and (4). I read both subsections word for word
    in the Laws of Malaysia "online version of updated text of reprint", as at 1 December 2012 (latest amendment
    A1432). lom.agc.gov.my returned "Invalid request" to my fetch, so I read the same official reprint PDF from
    https://www.icj.org/wp-content/uploads/1950/05/Malaysia-Evidence-Act-1950-2012-eng.pdf.
  - **What the footnote says:** under s.90A(2), that a document was produced by a computer in the course of its
    ordinary use may be proved by a certificate. The certificate is signed by the person responsible for the management
    of that computer's operation, and s.90A(4) then presumes the computer was working properly. The footnote adds that
    this report is not that certificate: for CCTV recorders and scan systems it would come from their operator. It
    cites the reprint date.
  - **Not added: PDPA 2010 s.10 retention.** I could not read its text from a primary source. pdp.gov.my and the
    reprint copy I found did not load, and the search gave only law-firm summaries. Per your rule, no PDPA line until
    someone can read the Act.
  - **Not checked:** whether s.90A was amended after Dec 2012. The footnote states the reprint date for that reason.

## 2. Check these
- `frontend/review_pack/desktop/26_report_document_full.png` (whole document, new export approved by reviewer_01)
- `frontend/review_pack/desktop/13_report_draft.png`, `14_report_approved.png` (+ `mobile/`)
- `frontend/review_pack/desktop/01_cases.png`, `mobile/01_cases.png` (Start a case: complaint, claim reference, date reported)
- `backend/src/spoor/reports.py` (`render_html`, `fmt_time`, `_clock_cell`, `_sources_used`, `MY_EVIDENCE_NOTE`),
  `backend/src/spoor/contracts/case.py`, `backend/tests/test_api.py::test_parcel_scan_routes`
- Tests: backend pytest 217 ✓ (new review-012 assertions); frontend typecheck ✓, lint ✓; review shots cases + report ✓.

## 3. Known issues
- Default case: complaint, claim reference and date reported are blank (opened before the fields existed). Scenario cases
  get the complaint from their card when F1 seeds them.

## 4. Questions
- None.
