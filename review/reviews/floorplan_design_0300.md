# Floor plan + UI direction (Rexton, 02:53–02:59 Sat) — for the frontend agent

Rexton's words: the current 2D floor plan "looks AI-drawn". He knows the UI is still in progress;
this is direction for your next pass, not a NOT APPROVED. Read before the next 2D / dashboard work.

## 1. Floor plan: reference target
- Reference: `review/refs/floorplan_reference.png` (+ `.svg`, generator `make_floorplan_reference.py`).
  It is drawn straight from `assets/hub/hub_spec.json`, Spoor v2 tokens, Inter as a stand-in for Google Sans Flex.
  The journey overlay in it is SAMPLE data showing each evidence style once; do not copy its data.
- Match the *language*, not the pixels:
  1. **Architectural, not boxes.** Thick walls with real door openings; dock numbers 01–12 outside the wall;
     columns as small squares; truck yard as faint hatching outside.
  2. **Machines drawn as machines.** Belts as strips with flow chevrons; the sorter as a stadium track with carrier
     ticks; chutes as small trapezoids numbered 01–12 + R; scan tunnel as a box; cage bays as outlined squares.
  3. **Human names first, codes second.** "Cross-belt sorter", "Chutes + bagging", "Exception bench"; Z-code small
     and faint underneath. No bare "Z05".
  4. **Monochrome base.** Everything structural is greys on the dark surface. The only saturated things are the
     evidence colours and the indigo of cameras in play.
  5. **Cameras quiet until relevant.** All cameras = tiny dim icon with a heading tick. Cameras in play for the
     case = indigo, labelled, with a faint FOV wedge (from hfov + heading).
  6. **Blind spot shown.** BLIND_NW hatched, "No camera coverage".
  7. **Time chips never collide with the route.** Offset chips with a hairline leader; tabular numbers.
  8. **Legend + scale bar + north arrow** under the plan.
- Evidence styles (unchanged meaning): observed green solid with soft glow; inferred-along-belt amber dotted;
  scan beads blue diamonds; last confirmed = green ring; expected-not-seen = red dashed box at the predicted spot;
  could-be-here / no coverage = grey hatch.
- Honesty rule still holds: no-key mode never draws green; it shows scans + amber dotted + grey hatch only.

## 2. Case journey screen (same screenshot Rexton sent)
1. **Put CCTV on screen.** It is a CCTV product; the hero is the camera frame/crop (I1 follow-cam), the plan supports it.
2. **No empty right third.** Default the right panel to the latest evidence or the missing moment, not "Nothing selected".
3. **Timeline visible without scrolling** at 1440×900.
4. **Left column:** less grey small text; "Unknown" as 2–3 plain sentences, not a log. Fix the broken "• •" bullet.
5. **Camera route strip** (Rexton asked again): cameras in route order, each tile = parcel crop highlighted /
   "expected, not seen" / "not analysed". This is the H10 grid; keep it on the journey screen.

## 3. Hub dashboard (H15) = exceptions inbox
- Rexton wants alerting. Do it from the **scan log**, not from watching all cameras:
  rule = a parcel's next expected scan is overdue (e.g. > 20 min after the last one) → "Stalled" exception →
  one click opens a case → only then SAM/agents run on the cameras that matter.
- Top: search by tracking number. Then KPIs (keep yours), the stalled/exception list with age, then your
  existing sections. In-app badge only; no email/push.
- Pitch line: "catch it before the customer complains".

## 4. Personal data
- Spoor stores tracking number, size, weight, route/destination hub only. No recipient name/phone/address.
- If any appears (label OCR, imported manifest): masked by default, e.g. `T** W** · 01*-***-4821 · 47*** Petaling Jaya`.
- Workers: Spoor tracks parcels, not people. People appear only as anonymous tracks ("Person A"). Handheld scan
  events may carry the scanner user ID: masked by default; a supervisor can reveal it with a typed reason, logged.
  No face recognition, no "suspect" wording anywhere.

## 5. Logo — HOLD
Rexton is still choosing the logo. Do not polish or place the current mark further; keep it in the single
brand slot so it swaps in one change. I will tell you when he says final.
