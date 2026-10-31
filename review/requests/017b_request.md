# 017b request: one-hand mailer pick, PROTOTYPE (M5 step 3 blocker), please steer the grip

**Date:** 2026-10-30 ~19:50 MYT · **Builder**

**Not for approval as is: the grip itself is wrong (see "Honest finding").** I'm asking which grip you want before I build it properly.

## Evidence
| What | File |
|---|---|
| Two mailer cycles, I1 only, Workbench from the belt side, every 3rd frame (f8–44 and f113–149) | `qa/review/m5_onehand/mailer_cycles_f8-44_f113-149.jpg` |
| Bench QA (60 % mailers, I1, 30 s) | `qa/review/m5_onehand/m4_qa_mailers06.json`, scene `m4_line_a.blend` |

## What it does
`inductor.build`, for parcels with `grip="one_hand"`, plus `m4_line_a --mailers 0.6`, using `flow.MAILER_DIMS` 24–44 × 17–31 × 3.5–5 cm, grey / black / white:
- **Right hand:** comes down on the top 6 cm in from the near edge, palm down, fingers forward, and carries it to the induct belt. The engine's approach, release, retract and light curtain are unchanged.
- **Left arm:** blends out of the two-hand clip and hangs beside the thigh (palm in, fingers down, relaxed curl). Where his shoulder comes over the table's near rail (leaning to the pick), it swings 20 cm back behind the hip.
- **Engine:** hand orientation and finger flattening are now per hand. This also removes a hand twitch on every two-hand approach: for ~3 frames, 0.8–0.5 s before the grasp, the old code rotated each hand up to ~45–90° about the vertical. That fix lands on the line A and dock benches too.

## Numbers (I1, 30 s, 8 cycles: 6 mailers + 2 cartons)
| | Cartons only (same seed) | Mailers 60 % |
|---|---|---|
| Frames > 1 cm | 16 | **8** |
| R hand to carton, p50 | −2.1 mm | −0.1 mm |
| Foot skate | 3.1 mm | 3.1 mm |
| Ground penetration | 0 | 0 |
| Yaw while holding | < 90° | 62–82° |
| Cycle | 3.3–3.6 s | 3.3–3.6 s |

Free-hand variants measured:
- hanging straight: 42 frames > 1 cm (forearm through the table rail);
- palm on the 4 cm rail: 50 (the palm sinks 2 cm into it);
- swung back: 8.

## Honest finding
**A flat palm on top cannot lift anything.** Close up, the mailer looks magnetised to the palm. At CCTV distance (worker 100–200 px) it may pass, but that is not the standard you set.

The physical grips are:
- **(a) Edge pinch:** thumb on top, fingers under the near edge. That needs the edge free, and on our table the near edge rests against the end stop: the fingers can't get under it.
- **(b) Side-edge pinch:** on the mailer's long side away from the operator rail; there is 20 cm+ of free roller there. Hand vertical, thumb on top, fingers under. My preference, because the table geometry allows it.
- **(c) Drag then pinch:** fingertips press on top and slide it 5 cm toward himself over the stop, then pinch. Most realistic, but two phases, about +1 h.

The reference frames show one-handed reaching at induction and polybags at the induct points, but not the grip.

**Question:** (b), (c), or keep (a)-like top contact for distance cameras only? If you don't answer, I build (b).
