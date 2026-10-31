# F-021 + F-022 review — I2 journey, I3 missing moment, site plan, J1 smoke tests

**Verdict: APPROVED.** Strong, honest backend: typed segments with evidence ids, belts never run backwards,
faster-than-belt = gap, unsynced clocks = not_checkable, plan timing pinned against the scan log (4.66 vs 4.7 s,
19.23 vs 19.2 s), negative observations only for analysed clips, and the `unresolved_candidates` fix is exactly right.
Hermetic tests (ignoring .env) — good catch. J1: all four models pass for ≈ $0.12; reasoning split already in place.

Answers:
1. F-021 Q1 — **keep `inferred_along_conveyor` in no-key mode.** It comes from scans + the plan, not from tracking:
   amber dotted, labelled "inferred from belt route and scan times". The H honesty rule means "no fabricated tracks";
   I'm updating its wording.
2. F-022 Q1 — **yes, add `scan_anchored`**, with these conditions:
   - only at fixed read points (tunnel, DWS arch, divert, RFID portal); never handheld;
   - SAM box prompt at the read point's expected region, inside the scan time ± clock tolerance;
   - link only if exactly ONE candidate is in that region in that window; two or more (S5 twins!) → `unresolved`,
     goes to human review;
   - same camera only, never cross-camera; record confidence, prompt, frame range, scan id;
   - UI wording "identified by tunnel read 14:32:12"; a human can confirm or reject it.
Then: I1 (follow-cam crop with this identity chain) → the keyed S2 vs no-key run once the S2 render exists. Also still
pending on your side: the style mapping (owner_style_0136.md, logo direction there) and H14 summary page.
