# 018 review — first full-hub run with line A on mocap (progress check; overview + I2 close f50/f120/f200/f270,
# whole-hub collisions_summary)

**Verdict: progress accepted, NOT for render (as you said).** Line A in the real hub: 4 inductors at their tables,
cartons and mailers on feed / tables / induct belts, inductor bodies 0 rows vs anything — real progress.

Confirmed issues (your honest list is right; I add #2):
1. P0 f200 I2: both palms up and open in front of the belly, empty (banned pose). Your idle fix (100STYLE ID cut for
   waits ≥ 1.2 s) is the right direction — verify on this exact wait.
2. P0 f50 I2: right hand hooked at the belly with the palm up/in, left hanging — the post-release "rest point in
   front of the hips" reads as a man holding his stomach. Rest = arms hang relaxed at the sides (palms facing the
   thighs), or one hand lightly on the table rail. Never a held hand in front of the body without an object.
3. P1 Reach safety net 12–15 cm (carton follows the hand): move the place ROOT with the zone clamp as planned. A
   carton that is not between both palms must never move.
4. P1 Mailers still palm-on-top → per-finger pinch (index + middle into the 4.1 cm roller gap, thumb on top) as you
   propose, or pick the mailer from its far long edge off the rollers. Keep it off until it is clean; meanwhile route
   mailers to line B if that keeps S2 honest.
5. P1 Line A parcel rows 65 (corner grazes at mouths + induct belts) → 0.
6. Whole hub 512 rows: mostly the stations still on the old motion (opener_1 vs parcels 7.7 cm, bag_1 vs the tied
   sack 7.2 cm, D02_n / D05 docks 5–9 cm, line B inductors 2.6–5.1 cm). Expected M5 backlog — all must be 0 before
   any render (owner rule).

Tomorrow's order (yours) accepted: idles → root follows clamp → mailer pinch → line A rows 0 → layout b ON for S2 +
S2 gates. Rexton's S2-first answer still pending; proceed on S2-first unless he says otherwise.
