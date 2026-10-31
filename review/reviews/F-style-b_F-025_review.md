# F-style-b + F-025 review — APPROVED WITH FIXES (big step up)

Reviewed 04:15 Sat: desktop 30_h2, 31_h10, 33_h14, 34_h15 (new /hub home).

Big improvement: CCTV hero + camera route strip + plan on the right; timeline visible at 1440×900; the plan now
speaks the reference language; hub home with tracking search and the stalled inbox; same words everywhere
("Last confirmed at chute C04 · 14:32:31.8 MYT"); H14 headline + sub-line exactly right; F-025 pose sync with a
projection test — the CAM_10 expected box now sits on the belt. F-025: APPROVED.

## P1
1. **Proof shots taken before media loads, again.** Journey hero says "Loading frame", the camera strip tiles are
   black. In the review specs wait for network idle + `img.decode()` on every visible frame before the capture.
   Same for the recording.
2. **Plan chips clip and overlap.** "14:32:30.8–3…" and "Expected on C…" are cut at the panel's right edge (journey
   and summary); chips overlap each other and the CAM 10 / CAM 07 labels and "Chutes + bagging". Clamp chips inside
   the plan bounds with simple collision avoidance; at small plan sizes show only Last confirmed + Expected chips and
   reveal the others on hover/tap.
3. **Background seam still there** (left rail/page band change at ~y 840–900 in journey, hub and summary shots).
4. **Stalled inbox can't show the demo story.** "As of the last imported scan" means S2's own parcel (divert C04,
   then no bag scan) is never overdue. Add an **as-of time**: default = end of the imported scenario window (or
   now, in live mode), adjustable in Operator. Then S2's parcel appears as Stalled with its age → one click opens the
   case. This is the "catch it before the customer complains" beat for the video.

## P2
5. Next action says 14:32:31–34; CAM_07's expected window says 14:32:30.8–36.9. One source for both.
6. Plans use about half their card (summary, hub). Fit the building to the card; fewer empty margins.
7. "Show where it was last confirmed" wraps to 2 lines in the left column: shorter label ("Show last confirmed")
   or full-width single line.

Then continue: I4/H4 possible locations (next), camera strip polish, 3D twin view (owner_ideas_0303).
