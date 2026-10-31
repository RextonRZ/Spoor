# Review 012 — Authentic investigator workflow (QUEUE G frontend)

Verdict: **APPROVED WITH FIXES.** The research is real and sourced, and the "decided not to change" section (no invented claim
deadlines, no guessed customer-status mapping) is exactly the right instinct. But the **report document** (26_report_document_full)
does not yet look like something a claims team or investigator would hand over — it reads like a database dump.

## Fixes
| # | Where | Problem | Fix | P |
|---|---|---|---|---|
| 1 | Report tables | Raw field names as headers (`gap_from_previous_s`, `late_upload`, `device_kind`, `period_start`, `master_sha256`, `received_at`) and Python literals in cells (`False`, `None`) | Human labels ("Gap since previous scan", "Uploaded late", "Device", "From / To", "Master SHA-256", "Received"); Yes/No; "—" for empty; seconds as "4.7 s" | P1 |
| 2 | Report times | Scan times in +08:00, audit-trail times in +00:00 — two time zones in one document | Everything in MYT (UTC+08:00) as "28 Oct 2026, 14:32:07.9 MYT"; one footnote with the UTC offset | P1 |
| 3 | Report scope | No complaint/claim block even though G1 says cases start from the complaint | Add: claim/case reference, date reported, waybill, the customer's complaint sentence (from case_input), who opened the case | P1 |
| 4 | "Sources: None." / "Clocks and calibration: None. None." | Contradicts the tables above (scan log + 4 CCTV masters are sources); duplicate "None." | List the sources actually used; one empty-state line per section | P1 |
| 5 | "Processing" | Raw JSON dump at the end | Readable summary: models used (none), model calls 0, agent steps 0, tokens 0 — keep the JSON as a download/appendix | P1 |
| 6 | CCTV reviewed | The clock-check text repeats the same 3-line UNVERIFIED sentence in every row; `cam_CAM_01` double prefix | One short cell ("±5 s · unverified, uploader-declared") with a footnote; camera IDs as `CAM_01` | P2 |
| 7 | Malaysian context | All evidence-handling references are UK / NZ | Research (primary sources only, e.g. Laws of Malaysia on lom.agc.gov.my, PDPC guidance) how CCTV/computer output is handled in Malaysia — Evidence Act 1950 (computer-produced documents) and PDPA 2010 retention. Add a sourced one-line footnote only if verified; never state a legal requirement you couldn't read | P2 |

## Answer — RFID (Q1)
**Yes: a dedicated `portal_read` kind** (device `rfid_portal`, door ID, antenna/read strength if the log has it). It is never
"loaded" on its own. Display: "RFID portal read at D08 (may be a cross-read from a neighbouring door)". A loading claim needs
corroboration (door/trailer assignment, no conflicting read at a neighbouring portal in the same window, or video). That is
exactly what S4 must show.
