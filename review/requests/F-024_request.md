# F-024 — H2 2D journey + replay, H10 missing moment, H1 follow-cam (frontend), with I1/I3 follow-ups

From the frontend agent. Style v2 (`?style=v2`) is on in every shot; it is the direction under review in F-style.
H14 (case summary) and H15 (hub dashboard) shipped with F-style and are re-shot here.

## 1. Changed since last request

### H2 — the 2D journey is the primary view (real no-key data)
- The workspace now opens on **"2D journey"**; 3D is the second button. The 2D layer draws only the backend-typed
  `/journey`:
  - green solid = seen in one camera track;
  - **amber dotted** = inferred along the plan's belt route between two scans, not seen. The tooltip gives belt time vs
    recorded gap and the timing verdict;
  - a **grey hatched dashed halo** where the trail ends;
  - **blue diamond scan beads** with their time.
  - The plan is now framed on the building, not the yards.
- **Replay** (timeline): ▶ / ❚❚ and 1× / 4× / 16×. One requestAnimationFrame loop drives the playhead, and it stops at
  the end of the case.
- A marker glides along the journey. It is green when seen and amber when inferred, and **it is never drawn inside a
  gap** (the test checks there is no marker at 14:32:40).
- A live caption says what the marker rests on:
  - "inferred position on the belt route (not seen)";
  - "scan at …";
  - "seen on CAM_07";
  - "Unknown since 14:32:31.8: no scan and no sighting after it".
- **One colour language everywhere:**
  - the legend now reads Seen / Inferred / Gap / Scan, with pattern swatches;
  - scans are blue in v1 as well (`--ev-scan`);
  - indigo is the brand accent only.

### H10 — "Missing moment" tab (right panel; "Moment" tab on mobile)
- The tab opens with where the evidence stops, in words.
- Then one row per camera that should have shown the parcel next, with:
  - its role: watching the last point, next on the belt, next on foot;
  - the predicted time and how it was predicted;
  - the **original frame at the predicted time** with the **dashed expected box**;
  - a **close-up**: the backend's region crop of the original pixels, labelled "shown 2.3× (browser scaling, no AI
    upscale)";
  - the result chip.
- "Not seen" with frame numbers appears only for a typed negative observation from the backend. No-key mode shows
  "not analysed yet · needs SAM".
- Cameras with no footage are listed in one line. Clicking a frame opens it in the Source panel.

### H1 — follow-cam inset (scene, bottom-left)
- While the playhead is inside a seen segment, the inset shows:
  - the I1 crop of the original frame, enlarged by the browser, with the factor printed ("2.6× browser zoom of original
    pixels");
  - green corner brackets on the box;
  - the identity line: waybill · how the track is linked, then the scans that name the object, e.g. "label read at the
    scan tunnel 14:32:07.9 → loaded onto carrier 87 14:32:12.6 → sorter divert to C04 14:32:31.8";
  - the source and crop SHA-256s.
- Clicking the inset opens the full original frame.
- Outside a seen segment it shows a small pill: "Follow-cam: no confirmed sighting at this moment · tracking needs SAM".
- **Proof is on a labelled fixture made of real material:**
  - the boxes are the **real SAM 3.1 output from the J1 smoke test** on CAM_07 frames 220–229;
  - the pixels are the backend's real crops of those original frames;
  - only the track → case link is route-mocked, and the yellow TEST FIXTURE banner is on the shot.

### Backend follow-ups (I1 / I3)
- **Track crop:** accepts `t=` (nearest observed frame by normalized time). The crop is tighter (margin 0.6, at least
  64 px tall), so the 300 px inset shows 2–4× as H1 asks; it was 1.8×.
- **Region crop:** accepts `basis=W,H`. Expected regions are measured on the planned 2688×1520 view and scaled onto the
  actual frame.
- **Identity chain and journey beads:** now carry `raw_description` (so carrier numbers show), plus `read_outcome`.
- **Missing moment rows:** carry `region_basis_wh_px`.
- **Case summary:** waits for the missing moment, so it never shows an interim sentence that then changes. This was
  found in the recording review.
- The workspace has a "Case summary" button next to "Review report".

## 2. Check these (desktop = 1440×900, mobile = 390×844)
- `frontend/review_pack/{desktop,mobile}/`:
  - `30_h2_journey_inferred.png`
  - `30b_h2_journey_unknown_after_last.png`
  - `31_h10_missing_moment.png`
  - `fx_32_h1_followcam.png` (banner)
  - `33_h14_case_summary.png`
  - `34_h15_hub_dashboard.png`
- **Recording, 23 s, real data, no fixture:** `frontend/review_pack/journey_replay.mp4`. It shows the workspace → replay
  at 4× (beads, amber belt stretches, "unknown since") → missing moment with frames and close-ups → case summary.
- **Code:**
  - `frontend/src/components/workspace/{FloorPlan2D,FollowCam,MissingMoment}.tsx`
  - `frontend/src/lib/journey.ts` (`markerAt`, answer / confidence / next-action wording)
  - `frontend/src/components/workspace/context.tsx` (replay)
  - `frontend/tests/review/journey.spec.ts`, `journey-recording.spec.ts`
  - `backend/src/spoor/forensics/crop.py`
- **Tests:**
  - frontend: typecheck ✓, lint ✓, unit 20/20 ✓, a11y 6/6 ✓ (fixed: the 2D plan SVG is `role="group"` now that it holds
    buttons), review specs 8/8 + recording ✓;
  - the e2e fixture contract test moved to a `/journey` fixture (solid never overlaps the gap; a gap is never drawn
    as a route);
  - backend pytest 229 ✓.

## 3. Known issues
- On first load the left "Last confirmed" card briefly shows "fixed scanner read / zone path" before the parcel lookup
  arrives. This is older code; I'll fix it with the v2 switch.
- No-key clips are the old white-floor QA renders. S2's final render, a scan-anchored link, and one keyed SAM pass will
  give H1 real tracks.
- H3 (relay strip), H4 (cloud), H5, H6, H7, H11, H12, H13 are next, in the queue's order.

## 4. Questions
- None.
