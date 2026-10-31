# 021c review — S2 full hub 90 s — S2 ACTOR APPROVED; hub NOT yet render-clean (plan below)

Reviewed 06:20 Sat: close/sheet_hands, sheet_reach, sheet_place, s2_hub CCTV crops, the request tables.

## S2 actor + cage: APPROVED
- Hands: fingers hooked under the bottom edge, thumbs on the end faces — reads as a real carry now (no tray).
- Reach: head ↔ cage 16 cm, lean 4°; shoulder brushing the post 0.1–1.7 cm with no penetration is fine and honest.
- Place: carton lands flat on the board (0.0 mm f330–420) and stays; hands let go late. Good.
- The one-frame carton jump find + the clavicle-line fix: good engineering. The held-object jump gate
  (builder_note_0545) keeps it from coming back.
- Cage rule: old 28 → new 0 with the stricter checker that also caught 56 real post hits. Good.
- Truth: exits f426 (42.5 s) — regenerate on the next run.
- P2 (bench only): after the release his right hand rests at the hip with the palm turned out/forward (place sheet,
  rows 2–3). Let it hang palm-in by the thigh.

## The hub: 2009 rows, 1503 seen by S2 cameras — render gate
**Reviewer decision (Rexton can override in the morning):** for the **S2 render**, the gate is
**0 collision rows visible in any camera that S2 renders** (cameras in play + neighbours per render_plan,
counted with your `rows_in_view` test at the native 2688×1520 pose). Stations no rendered camera sees may keep old
motion **for the S2 render only**. They still must reach 0 before (a) any other scenario that sees them is rendered
and (b) the twin↔real fly-through (owner_ideas_0303 §6), which sees the whole hub. Keep the full-hub count in every
request so the backlog stays visible.

Order (rows in S2 views per likely hour of work):
1. **Parcels in chute walls** (350, all in view; 2 parcels, up to 10 cm) — likely a sim stop/stack bug; quick.
2. **Cage pushers** (377, all in view) — same grip fix as S2's posts.
3. **Line A → 0** (engine fixes ready on the bench).
4. **Bag opener + bagger** (186, all in view).
5. **Parcel ↔ parcel at the merge/loop** (195 in view) and **parcel ↔ static** (156 in view).
6. **Docks D02/D05** (151 in view), **sorter carriers** (55), **line B** (21), **tech** (12).
Then the 15 min S2 scan log with the subject fixed (builder_note_0445 / 0515), then S2 gates + render.

Every fix: before/after rows by camera, and native crops of the 2–3 worst frames that remain.
