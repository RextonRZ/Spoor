# 014b review — M0 line A induction layout (stills m0_top / m0_front / m0_operator_view) + headwear + spacing

**Verdict: APPROVED WITH FIXES. Good turnaround. Build on the gravity-roller table (answer to your question).**

Checked: 4 stand-ins 1.6 m apart (≈270 px at 169 px/m in m0_top), each facing belt A; worker centre ≈0.36 m from the
belt frame, table edge ≈0.3 m to the left, carton centre ≈0.55 m lateral → one easy reach with ~80° trunk turn, no spin.
Aisle 0.95 m. "LABEL MENGHADAP ATAS" sign over the line: good, authentic.

Fixes for M3 (when you wire it into build_hub / flow / stations):
1. P1 Chair overlaps table I3 (m0_top, m0_front) → move it, and run the static-vs-static check on the new pieces.
2. P1 Feed → table transfer must be physical and visible: an angled diverter (pop-up wheel or paddle) at each table
   mouth that visibly actuates; feed belt top higher than the table head so the table falls ~3–5° toward the operator;
   parcels roll at gravity speed (≈0.2–0.4 m/s), stop at an end stop at 88 cm, and ACCUMULATE without touching
   (zero-pressure: ≥2 cm gaps, never stacked, never through the rollers). Max 3 parcels per table.
3. P1 The table ends level with the inductor's hip line (m0_top) — keep it there; do not let the next parcel sit
   behind the worker's back.
4. P1 Spacing gate row (your idea): any two workers' bodies < 0.3 m while working = fail; 0.6 m is the target.
5. P2 Tables block the aisle between feed and induct frames → nobody walks that aisle; route walkers elsewhere and
   make sure no flow path crosses it.
6. P2 Line B at M4: same rules (gaylord at the side, waist height via tilt, face belt B).

Headwear: HEADWEAR_ALLOWED=False guard accepted; bare-head sheets due with M2/M3.
Person–person: 14.5 cm "no touch" is understood, the new layout removes it — but keep the 0.3 m row in the gate.
