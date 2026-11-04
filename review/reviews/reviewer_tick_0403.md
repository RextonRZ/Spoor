last commit reviewed: faf72ee

Reviewer tick 2026-11-02 04:03 (overnight render check; Rexton delegated the OK, cap US$12). I watched contact sheets of
S2_CHK_CAGE_W, S2_CHK_STORE, S2_CHK_DOCK, S2_CHK_TUNNEL, W1_CHK_UNLOAD, W1_CHK_TUNNEL from qa/review/chk_preview/.

APPROVED (partial): Modal render, cap US$12 total for everything in this note, of
- W1: CHK_UNLOAD, CAM_02, CHK_TUNNEL, CAM_05, CAM_01, **only if the W1 gates (still running at 03:55) finish with
  0 hard rows and 0 parcel overlaps on these cameras**. Unload and tunnel exit look good: cartons clear on the belt,
  first-out order visible, no visible glitches at this sampling.
- S2 window: CHK_TUNNEL, CHK_CAGE_W, CHK_DOCK (CHK_DOCK after check 2 below).

NOT approved yet:
1. CHK_STORE: the key moment is blocked. From 14:32:22 to 14:32:54 the frame is mostly empty floor; the carrier
   with the carton appears only at 14:32:31 at the left edge, mostly behind the blue upright, and the doorway and
   the SCAN IN handheld are not in view. A door camera should frame the doorway itself. Re-mount it where a hub
   would put a door camera (outside, above, facing the store opening, with the handheld on the post in frame), not
   aimed at the story carton. New preview, then I review it.
2. CHK_DOCK: cage RC-760 looks EMPTY at D07 (14:33:24-35). Check RC-760's container_add records in the scan log: if
   other parcels were scanned into RC-760, they must be visible in the cage in every clip (W2, S2 CHK_CAGE_W, dock);
   if RC-760 really held only the story parcel, say so in READY.md (then an empty cage going out is the point).
3. W1 chute divert (CHK_CHUTE, CAM_11) and W2 (CHK_CHUTE pick, CHK_CAGE_W set-down): previews were still rendering;
   not reviewed. Post them and I check at the next tick.

Note: CHK_CAGE_W shows all three bays from 5 m, so the carton is small. Fine for the full-res render (2688 px);
don't re-mount it closer to the story bay.
