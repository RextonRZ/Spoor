# Review 005 — Frontend fixes (closes C2, C4)

Verdict: **APPROVED.** All nine fixes landed and read well: light walls, decluttered labels with leader lines,
event-kind wording that no longer overclaims ("Identity comes from sorter tracking, not a new read. Whether the parcel then
went into the bag is not shown." — exactly right), hub-flow line, 5 px trace with arrowhead + auto-frame, photo-eye lane
labelled "no identity · simulated", no black frames. Block C is done. Checked: desktop 02/03/09/fx_16, mobile 02, frame
sheet of the new 38.5 s recording.

## Polish (P2, do when convenient — not blocking)
| # | Where | Note | Fix |
|---|---|---|---|
| 1 | fx_16 3D trace | The amber hypothesis link is a straight line cutting across the inside of the loop to the chute — reads like the parcel flew across the sorter | When a hypothesis link follows a known conveyance (loop, belt, chute), draw it along that path (hub topology graph); straight only when no conveyance is known. Still amber dashed |
| 2 | fx_16 3D trace | Green segment looks drawn at floor level beside the deck | Check the trace height uses the observation's z (carrier deck ≈ 1.5 m), not 0 |
| 3 | Recording | ~6 s of "Loading 3D scene" skeletons between part 1 and the fixture part | Preload or cut the reload, so the demo video has no dead air |
| 4 | Mobile 02 | Two labels clipped at the right edge (you noted the live app clamps) | Re-shoot with the clamp |

## Next for the frontend agent (new QUEUE block F)
See QUEUE.md block F — work that helps the demo while the builder renders.
