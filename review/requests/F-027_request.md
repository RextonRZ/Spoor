# F-027 — F-style-b review fixes 1–7 (media-loaded proofs, plan chips, seam, inbox clock, one window, plan fit)

From the frontend agent. Fixed from the F-style-b review: 1, 2, 3, 4, 5, 6, 7.

## 1. Changed
1. **Proofs wait for media.**
   - The review specs capture only after `settled()`: no visible "Loading…" status, and every visible image complete and
     decoded (`FadeImg` sets `data-loaded`).
   - The recording waits for all images before the take starts.
   - All block-H shots are re-taken.
2. **Plan chips.**
   - Chips are clamped inside the plan even when every candidate spot collides.
   - On small plans (< 12 px/m: journey panel, summary) only the story chips show: last confirmed + expected. The other
     scans keep their details in the bead tooltips.
   - The chip width estimate is wider, so text no longer runs past the chip.
3. **Seam.** The sidebar now uses the same colour as the rail band below it (the material blur differed by a few
   values, which showed as a band at ~y 840–900 in full-page shots). The fixed-attachment page gradients were already
   gone.
4. **Inbox clock.**
   - The backend `GET /v1/sites/{id}/exceptions` takes `after_log_min` (the last imported scan + N minutes) or
     `now_clock=true` (live server clock). The response states its basis.
   - **Operator** has a new "Exceptions inbox clock" control: end of the imported log · +30 min · +2 h · now (live). It
     is stored in this browser only and changes no evidence.
   - The Hub shows "as of … · 30 min after the last imported scan · change in Operator".
   - Test: a divert with no bagging scan is in time at the log's end, and stalled 10 min overdue at +30 min.
   - Proof: `34b_h15_inbox_plus_30_min.png`. The default 30 s log has no bagging scans at all, so at +30 min every
     parcel is stalled, and the inbox says so honestly. With S2 seeded, its parcel (divert C04, then no bag scan) shows
     the same way, with "Open case" going straight to its summary.
   - "Open a case" in the table is now a secondary button: one accent per screen. Only the search result's button is
     primary.
5. **One window source.** Next action now prints the same window as the expected camera row and the strip, in tenths:
   "Review CAM_07 and CAM_10 from 14:32:30.8 to 14:32:36.9 MYT".
6. **Plans fill their card.** The summary and hub plans use `fit="width"`: the building spans the card width, and the
   height follows.
7. The button now reads "Show last confirmed" (one line).

## 2. Check these
- `frontend/review_pack/{desktop,mobile}/`:
  - `30_h2_journey_inferred.png`
  - `30b_h2_journey_unknown_after_last.png`
  - `31_h10_missing_moment.png`
  - `fx_32_h1_followcam.png`
  - `33_h14_case_summary.png`
  - `34_h15_hub_home.png`
  - `34b_h15_inbox_plus_30_min.png`
- **Code:**
  - `frontend/src/lib/inboxClock.ts`
  - `frontend/src/app/operator/page.tsx` (`InboxClockControl`)
  - `frontend/src/components/plan/HubPlan.tsx` (fit, compact chips, clamping)
  - `backend/src/spoor/forensics/exceptions.py`
  - `frontend/tests/review/journey.spec.ts` (`settled`)
- **Tests:** backend forensics 16 ✓; frontend typecheck ✓, lint ✓, review specs 8/8 ✓.

## 3. Known issues
- None new.
- I4 / H4 (F-026) is waiting for review.
