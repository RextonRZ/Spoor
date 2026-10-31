# Pre-review — B2 final-look stills (qa/b2/, 18 cams, S0 frame 150) — reviewer, unrequested, so you can fix before the batch

Overall: **big step up.** Light, white walls, mid-grey floor, barrel distortion, per-camera OSD clocks (14:32:17–29),
mesh fence + stack lights on the loop, cages in bays, Malay signage ("LABEL MENGHADAP ATAS", "PENGHANTARAN / DISPATCH").
It reads as a real hub on most cameras. Fix these **before** the S0 batch — every one would be baked into hours of render.

| # | Camera (pixel ≈ in the 960-wide tile) | Problem | Fix | P |
|---|---|---|---|---|
| 1 | CAM_15 (≈ 850,900) | **Two red roll cages interpenetrate** | Bay assignment collision check for parked cages; QA `cage_overlap` = high | P0 |
| 2 | CAM_09 (≈ 700,860), CAM_11 (≈ 680,1410 of sheet), CAM_12 (≈ 1215,1250 of sheet) | A carton **hangs in the air** below/beyond the red reject chute, past the blue bin | Check in D2 video: if it's mid-fall it must land in the bin within 0.5 s; if it rests there, it's floating. Reject chute discharge must end inside the bin | P0 |
| 3 | CAM_14, 15, 16, 18 (wall base) | Dark **hairy/fur-like fringe** along the wall–floor junction (looks like grass) | Replace the particle/alpha dirt with a soft grime gradient decal (no strands) | P1 |
| 4 | CAM_07, CAM_08 | Sorter loop nearly empty (≈ 1 parcel per 8–10 carriers on CAM_08) — a mid-shift hub looks busier | Carrier occupancy 25–40 % (more feed, or pre-load the loop); keep it consistent with the induction rate in the scan log | P1 |
| 5 | CAM_05 | Scan tunnel reads as a plain white box — it's our hero shot | Red-orange LED glow inside the tunnel, mesh fence + yellow posts, DWS screen on a stand (dpd_t068, beesort_t036) | P1 |
| 6 | CAM_17 yard | Block lorries and a flat slab (known) | If CAM_17 is on no scenario path, **drop it from the S0 batch** (saves ~1/18 of render) and say so in the card; otherwise model kerbs, bay lines, lorry details | P1 |
| 7 | CAM_09/12 | Green trolley has a camouflage-like texture | Plain powder-coat green or galvanised | P2 |
| 8 | CAM_03 | Lone plastic chair mid-floor; black panel on a stand tilted near the floor edge (≈ 100,870) | Chair to a table or remove; check the panel isn't a fallen HMI | P2 |
| 9 | CAM_04 | Two thin black lines hanging from ceiling to floor (≈ 1400,600–930) | Confirm what they are (cable drop? scanner gooseneck?); a cable shouldn't reach the floor | P2 |
| 10 | CAM_02 break table | Plain white plane table | Laminate texture, a few items (bottles, phone) as in beesort_t202 | P2 |

Not needed: OSD spread of ~12 s across cameras is plausible for unsynced cameras and good for the clock story.
