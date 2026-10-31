# F-049 — Flow screen 5: Go look (Search.dc.html), and the run's search task is now real

From the frontend agent.

## 1. Changed since last request
- **`/cases/{id}/search` = Go look**, ported from `Search.dc.html`. The old checklist page is deleted. It is a phone
  screen; on a desk it keeps phone width.
  - Header: back button, "Search task · from the hub supervisor · 10:21", the waybill.
  - **One place at a time**: the first place of the open search task without an answer.
    - "Check the blind corner by the exception store", using the zone's short name.
    - How to get in, taken from the place's own description in the site plan ("Inside corner of the L-flow, behind
      3 m sack racks.").
  - **Picture:** the last camera frame of the parcel when there is one; until then, the plan pinned on the place.
  - **Look for:** from the parcel's own scan facts: "Parcel, 26 × 18 × 10 cm" / "1.8 kg · label ends in …0419".
    No invented colour or label type.
  - **Hold to add a voice note**: press and hold to record, let go to send (16 kHz WAV, transcribed and stored as a
    statement by floor staff, F-042). With no key it reads "Voice notes are off in this demo" and is disabled.
  - **Not here / Found it** (56 px). Not here records the outcome and moves to the next place; Found it records it
    and opens the Report.
  - Empty states, one sentence plus one button each: no task yet ("Send to the floor"), every place checked, already
    found.
- **Backend honesty fix:** the run's `create_search_task` step now **really creates the task** (the same ranking as
  `POST /search-tasks`), unless one is open. Its log line says "Search task ready, first stop: …". The S2 run created
  task BLIND_NW → Z13 → Z11 → Z10 → Z12 → Z09.

## 2. Check these
- `frontend/review_pack/flow/mobile_05_golook.png` (390 × 844 frame), `desktop_05_golook.png`
- No console errors. Backend `test_run` ✓. Typecheck and lint clean.

## 3. Question
- The second stop is "Z13 Supervisor office" (ranked by the I4 searchable score). Should offices and machines rank
  last for a floor search? I can add that to the ranking.
- Next: Report (Share report, no approval step), then Cameras.
