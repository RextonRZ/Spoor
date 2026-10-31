# F-032 … F-038 review (H6 plan-built 3D, F-033 fixes, H13 scan cards, J2a/J2b, J2 lead plan, Operator tabs) — APPROVED WITH FIXES

Reviewed 05:15 Sat: 38_h6, 34b_h15 (+30 min), 39_h13, request texts; costs read from the requests.

Good:
- **F-033 P0 fixed properly**: "+30 min" now says 42 past due but the log ends before the next point shows the hub
  kept working → can't judge. No false alarms. Rule text on screen is clear.
- Scan card (H13): record facts, clock state, source id. Right.
- J2a/J2b/J2 wired with recorded cost + agent steps; spend tiny (Baseten ≈ 4.5k tok, Meta ≈ $0.12 + one ≈ $0.07
  lead plan). Within caps. Images downscaled, ≤ 3, never stored, labelled — right.
- Plan-built 3D with the "Synthetic hub model | Plan-built 3D" switch and the "what a real hub gets on day one"
  caption: exactly the deployment story (owner_ideas_0303 §2).

## P1
1. **Plan chips still collide.** In 39_h13 "Last confirmed · Divert C0…" is cut by the "14:32:30.8–36 Expected on
   CAM 07" chip. Collision avoidance must move chips apart (or stack them with leaders), never overlap. Add a review
   spec that fails if any two chip rects intersect or a chip leaves the plan box.
2. **Plan-built 3D labels overlap** ("Exception bench" over "Reject chute") and one is cut ("on-conveyable area").
   Same rule: no overlaps, clamp inside. Name the S2 store **"Exception store"** in 3D as you now do in 2D (3D still
   says "Empty cage / bag store").

## P2
3. The default demo case is still the old CTX160258795857 (6.7 kg, 40×30×25 cm). For the video, the default case
   must be S2's subject once the builder fixes the S2 log/subject mismatch you flagged (05:07). Keep the old one as a
   second case.
4. 3D: camera pins as lollipops are fine; give cameras in play the indigo + cone treatment as in 2D.

Builder side of your 05:07 note is relayed in builder_note_0515.md.
