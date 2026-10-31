# F-050 — Flow screen 6: Report (Report.dc.html), Share report without an approval step

From the frontend agent.

## 1. Changed since last request
- **`/cases/{id}/report`**, ported from `Report.dc.html`. The old report page (draft list, approve button) is
  replaced.
  - Status pill (Found · hh:mm by {name} / Lost track); the 40 px answer; one plain paragraph built from the
    evidence. With the S2 data: "The last scan was into chute C12 at 14:11:12. The sorter's own times for this parcel
    don't fit the belt, so one of its records is wrong. It could be in 8 places; the most likely is the blind
    corner, exception store."
  - **Actions:**
    - **Download PDF** exports the full report document (the existing renderer: tables, hashes, Malaysian context,
      legal notes) and opens it with the print dialog.
    - **Evidence video** builds the reel (I8) and plays it on the page.
    - **Share report** exports and copies the link.
  - **Four key moments, in time order:** the last two scans, the records conflict, then the floor search / found
    tile. Each shows the camera frame when there is footage, otherwise the plan pinned on the spot, captioned
    "time · what · source".
  - **What to fix**, shown only when there is a records conflict: "The sorter's records for this parcel don't add up:
    recorded 21.7 s, but the belt route needs 25.9 s. Ask the sorter team to check this parcel's tracking between
    induction and the chute."
  - **For the customer:** found → "The parcel is in the hub and goes out on the next run." Not found → "We are
    checking N places…". No invented truck or run name.
  - Plan with the route; "Decision support, not a forensic certificate…" with a **full report** link; the
    tagline.

## 2. Check these
- `frontend/review_pack/flow/desktop_06_report.png`, `mobile_06_report.png`
- No console errors. Typecheck and lint clean.

## 3. Question (one user vs the four-eyes rule)
- The backend refuses approval by the person who exported the report (four-eyes rule). With one demo user, nobody
  can approve. So **Share report does not approve**. The shared document keeps its honest "DRAFT · not
  reviewer-approved" banner, and the backend rule is unchanged. If you'd rather the single supervisor's share count
  as approval, that means relaxing the four-eyes rule in the backend. I won't do that without an explicit OK.
- Next: Cameras (all 19 on one synced clock, Camera wall | 3D hub, zone filter), then Settings.
