# Scenarios v2 — sharpened (owner OK, Rexton 00:09 Sat 31 Oct: "make it even sharp")

Read the real cards (ml/evaluation/scenarios/S*/scenario_card.md) before this. The set of 6 stays — each one is a real,
niche hub failure. These changes make every case land a single, sharp line in the demo. Order of work = S2 first.

## S2 · Removal into the blind spot (PITCH) — sharpen
Real pattern: scan says "in cage", the parcel is physically taken out later; the hub has an uncovered store corner.
1. P0 **Perimeter proof.** Every way out of BLIND_NW / Z11 must be inside some camera's view (entrance gap x 13.4–15.2
   plus any other gap). Then Spoor can say the sharp line: *"No camera sees inside Z11, but every exit is watched and
   nothing left it before the window ended → it is still inside Z11."* Verify with the coverage map; add a camera or
   close a gap if needed. Add `exits_covered: true` + the camera list per exit to the truth card.
2. P0 **The removal actor (worker_s2_1) is the key action of the pitch — put him on mocap first**, before line A
   polish: reach into roll cage RC-864 at ~1.0–1.4 m (side face grip, no hands through the mesh), carry close,
   100STYLE walk to the corner, enters at t≈19.1 s. Same gates as everyone (0 contacts, no headwear, natural).
3. P1 Parcel = a small cash-on-delivery box (phone-box size, ~18×10×6 cm), fictional brand only.
4. P1 Neutral reading on screen: sign the corner "STOR PENGECUALIAN / EXCEPTION STORE" so a lawful reason exists;
   the person stays a pseudonymous token. The answer must say "moved by a person into Z11", never "stolen".
5. P1 The scan conflict must be explicit: last scan = container_add into the west cage (14:21:23); video shows it
   lifted out at t≈5.6 s → the app says *"the cage scan is out of date"*.

## S3 · Scanned into the bag, left on the floor — sharpen (it is good; keep the story)
1. P1 Make the miss consequential: after the parcel is set down beside the C04 frame, the bag is tied and moved toward
   dispatch inside the window, so the system believes the parcel left with the bag. The answer: *"the scan says
   BAG-C04-6915; the video says the floor beside chute C04 — the bag left without it."*
2. P2 Keep the parcel visible on the floor to the end of the window (no worker kicks/covers it).

## S5 · Look-alike pair — P0 BUG
The card's expected answer ("follow the tunnel read and the carrier") is impossible: the S5 scan log has **no line at
all** for CTX409459446096 (tunnel_read_t_s / divert_t_s / in_bag_t_s all null). Fix: put the subject's tunnel_read,
induct_to_carrier and divert_confirm (C12) inside the 15 s window (lengthen to ~25 s if needed), and keep the twin's
reads (C03) too. Then the sharp line works: *"same size, same colour — identity comes from the tunnel read and carrier
#, not appearance."*

## S1 · No-read rework — small fix
P1 The re-induction happens at t≈90 s = the window edge, so its read can fall outside. Either end the window at
~100 s or bring the re-induct to ~80 s, so the closing read is on screen. Keep the realistic bench dwell.

## S4 · Wrong truck (RFID cross-read) — keep
P2 Make sure the D08 cross-read line carries RSSI weaker than D09 and the 0.3 s lag in the scan log, and that a camera
sees the cage roll into D09 — that is the whole proof.

## S0 · Control — keep. It proves "no false alarms".

## Optional S6 (only if S2 + S0 are rendered and time remains): fell off the line
Parcel slides off at an induct-belt merge into the gap under belt A (real: found during conveyor sweeps). Last scan
= induct; never reaches the tunnel; a camera sees the drop. Sharp line: *"not stolen — check under belt A at induct 3."*
Uses the new line A; non-accusatory.

## Priority (replaces the S2-first list where they differ)
1. S2 actor on mocap + S2 perimeter proof → 2. line A rows 0 + mailer pinch (S2 cameras see line A) → 3. S2 gates +
render → 4. S5 bug + S0 → 5. S1/S3/S4 tweaks → 6. S6 if time.

---
# Pass 2 (00:30, Rexton: "loop again") — sharper still

## S2 — make the conclusion airtight, not just "no coverage"
1. P0 **Window 30 s → ~90 s** (start unchanged). With the entry at t≈19 s, a 30 s clip watches the exits for only 11 s;
   "nothing came out" means little. 90 s gives 70 s of watched exits.
2. P0 **The person comes back out EMPTY-HANDED** (t≈40–50 s) through a watched exit. Sharp line: *"went in carrying
   it at 14:32:26, came out empty-handed at 14:32:5x → the parcel is in Z11."* Still neutral (exception store).
3. P1 **The system's false belief:** cage RC-864 (where the scan still places the parcel) is pushed to its dock door
   later in the window and its RFID is read there. Scan story = "left on the truck"; video = "in the exception
   store". This directly tests the evaluator's "false 'left the hub' = 0" row.
4. Cost: ~1–2 h build + ~1.6 h CCTV render for 6 cams × 90 s. Worth it — it is the pitch.

## S5 — make it a real trap, not just two twins
P1 The twins **swap order at a merge** (one overtakes the other where an induct belt joins belt A). An appearance
tracker would swap their IDs there; the app must follow carrier # / divert confirm. Sharp line: *"they swapped places
at the merge — appearance would send you to chute C03; the sorter record says C12."*

## S0 — prove we don't cry wolf
P1 Put one innocent "suspicious-looking" moment in the control: the subject is hidden behind a column / another
parcel for 2–3 s on one camera, then reappears. Correct answer: an amber gap that is NOT bridged and NOT flagged as an
incident; last confirmed = the scan.

## Every card gets a `must_not` list (for the evaluation harness + the judges)
- S0: must not raise an incident; must not bridge the occlusion gap without evidence.
- S1: must not call the no-read a loss; must align the handheld clock before ordering events.
- S2: must not say "left the hub"; must not say "stolen" / name a person; must not trust the cage scan after t≈5.6 s.
- S3: must not trust the bag scan; must not say "dispatched".
- S4: must not trust the D08 read (weaker RSSI, 0.3 s later).
- S5: must not identify by appearance; must not pick C03.
Add `expected_one_liner` + `must_not` to each scenario_card and score them in spoor_eval (pass/fail per line).

## Updated order
S2 actor on mocap → S2 window 90 s + empty-handed exit + perimeter cams → line A rows 0 + mailer pinch → S2 gates +
render → S5 fix (scan lines + merge swap) → S0 (+ occlusion moment) → S1/S3/S4 tweaks → must_not scoring → S6 if time.
