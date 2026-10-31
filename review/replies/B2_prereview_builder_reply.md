# Reply to the B2 pre-review (builder)

All fixes are in the build that is running now (pass 3: rebuild + all six scenarios). The B2 stills are re-shot from it in request 011, together with D2.

| # | Cause found | Fix |
|---|---|---|
| P0 1 (CAM_15 cages) | Before a push, the cage was placed ahead of the pusher's *walking* heading. cage_2 walked up to the empty cage heading west, so the cage sat inside queue cage 2, then swung round to south as the push began. A scan of all 50 cages at f150 found it was the only colliding pair. | The walk to a cage now ends with a 0.35 m approach along the push direction, so he arrives facing the way he pushes. |
| P0 2 (floating carton) | The three `reject_crate` parcels stood at z 0.35 m, 0.9 m past the rework bin, on a crate that was never built. | Moved into the bin, on top of its contents. Same random draws, so nothing else moves. |
| P1 3 (wall-base "fur") | The wall-grime decal used dithered alpha. At the batch's 2 samples, dithering renders as a coarse stipple, and the vertical fade turns it into strands. | All decals are now blended alpha (smooth at 2 spp). |
| P1 5 (tunnel) | — | The body is painted frame grey; the light bars are red-orange LEDs; three vertical scanner strips glow on each inner wall; three scanner heads sit on the roof; yellow guard posts with black caps stand at the corners. The DWS screen stays on its stand. |
| P1 6 (yard) | — | **Dropped from the S0 batch** (17 cameras). S4 keeps CAM_17, because the mis-load happens at the lorries, so the lorries were upgraded: 3 m cab with windscreen, side windows, grille, bumper and mirrors; chassis rails; side underrun bars; round twin tyres; yellow bay lines; wheel stops. |
| P2 7 (trolley) | The tool cart's scratched-paint atlas. | One flat green powder coat; the atlas only keeps wheels and rubber dark. |
| P2 8 (chair, panel) | The "black panel on a stand" was the crude standing fan (a 0.6 m black slab on a pole). | The fans are rebuilt as pedestal fans: round base, pole, motor, round guard. The lone chair is removed. |
| P2 9 (lines in CAM_04) | They are the 8 mm suspension chains of the forklift-crossing warning signs hung at 3 m over each zebra. They stop at the sign, but CAM_04 sees the sign edge-on, so the chains seemed to reach the floor. | Galvanised instead of black, which no longer reads as a cable. |
| P2 10 (break table) | — | Laminate tone; two water bottles, a mug and a lunch box (clear of the seated worker's forearms). The break pair now face each other; the barrier comes from review 006b. |

**P1 4 (empty loop): needs your call.**
- Occupancy follows the one modelled induction line: 3 manual inductors at ≈ 0.86 parcels/s (≈ 3,100/h). That is ~17 % of 99 carriers.
- 25–40 % honestly needs a **second induction line** (off-camera or new), with its own tunnel reads and induct events in the scan log. That changes the scan topology the frontend and evaluator use, about 2 h plus a scenario re-run.
- Options:
  - (a) Accept ~17 % for this hub: one induction line, a quiet hour.
  - (b) Add induction line B. Real hubs of this size do have 2+.
- I lean (a) for Nov 4 and would note it in the cards. Say if you want (b).

**Also found by the new QA:** a parcel whose track started mid-window was drawn at its first pose from frame 1 (a "ghost", belt parcels running through it). Late-entering parcels are now hidden until they appear, and the flow report lists every late one.
