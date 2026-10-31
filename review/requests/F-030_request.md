# F-030 — I7 floor search task + outcome (backend) and H12 search checklist (frontend)

From the frontend agent.

## 1. Changed since last request

### I7 (backend)
- **New records:** `SearchTask` and `SearchOutcome` (`contracts/search.py`, own tables, ids `srch_` / `sout_`).
- **`POST /v1/cases/{id}/search-tasks`** (investigator). It builds a task from the ranked possible places (I4) in
  walking order: the zone where it was last confirmed first, then by walking distance. Each place carries its "why".
- **`POST …/search-tasks/{tid}/outcome {area_id, found | not_found, note?, photo_sha256?}`**
  - Stored as a **human observation**: pseudonymous user id (never a name), time, and a SHA-256 of its content.
  - It appends a case revision ("floor search: not found at …") and is audited.
- **`GET …/search-tasks`** returns tasks + outcomes, and status `found` / `searching` / `none` with who / where / when.
- **The next read is revised:**
  - "not here" zeroes that place in the ranking ("searched by ivy at …: not there") and removes it from the latest
    possible area;
  - "found" puts the place first ("found here by …");
  - the hub dashboard shows the case as **found**.
- **Test:** `test_search_outcomes_revise_the_possible_area_and_the_status`
  - searching → hall "not here" (share 0, removed from the area) → store "found" (status found, ranked first).
- **Fix:** "last confirmed here" is one place only. A scan belongs to its read point's zone; the C04 divert used to flag
  both the loop zone and the chutes zone.

### H12 (frontend)
- **`/cases/{id}/search`:** a phone-first checklist.
  - One column; places numbered in walking order with their reasons.
  - Two big buttons per place, **Found it here** / **Not here** (52 px).
  - Done places show the outcome, who and when.
  - The page notes "each answer is recorded on the case with your user id and the time".
- **Case summary:**
  - a "Start a floor search" / "Floor search checklist" button next to "Open the investigation";
  - once found: headline "Found at <place> · <time>", sub-line "Recorded by <user> during the floor search", and the
    Found tile filled in.

## 2. Check these
- `frontend/review_pack/{desktop,mobile}/fx_37_h12_search_checklist.png`: **TEST FIXTURE banner**.
  - The task and one "not here" outcome are route-mocked from the real computed places.
  - **No outcome was written to the demo case**: a real "found" on the default case would be fabricated evidence.
- **Code:**
  - `backend/src/spoor/contracts/search.py`
  - `backend/src/spoor/forensics/search.py`
  - `backend/src/spoor/api/app.py` (search routes)
  - `frontend/src/app/cases/[caseId]/search/page.tsx`
- **Tests:** backend forensics 18 ✓; frontend typecheck ✓, lint ✓, review H12 + H14 ✓.

## 3. Known issues
- **Walking route:** the order is by walking distance from the last confirmed point. A drawn route between places on the
  plan is not built yet.
- **Photo:** only its hash is accepted for now (no upload).
- **API test:** not written yet for the search routes. The read model is unit-tested.

## 4. Next
- I8 evidence reel → H7
- H6 plan-built 3D
- H13 scan cards
