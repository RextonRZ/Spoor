last commit reviewed: ba932cd

- Root cause found and fixed (b851d5f): 28 handshake rows had used the purged 2688 px uploads (the scale bug behind
  the misplaced box and black crops). Re-run on the valid 1920 copies: 51/51 labels right; induction outlines were
  wrong 4/4 once real, so labels at sorter points are now divert-only. Honest. 68% of right outlines labelled.
- a82da9c/da4fb50: SAM mask contours on passport/alert/moments, focus crops, follow player, moments/tracker redesign
  with all four skills. Passport tiles now show pictures with real outlines (passport_after.png 13:49). Good.
- 6098314: Hub hang fixed (dashboard 5.4 s -> 143 ms). ba932cd: no verdict shown before data. bfd332b: docs (F) done.
Remaining:
1. moments_after.png: the 14:32:13 cage-pick moment crops to a person's back with the outline cut at the left edge;
   centre the crop on the outline (padding on all sides). The opened follow view (passport_follow_1.png, CAM 11
   14:11:16) shows no outline on the big frame: draw it there too, and prefer CHK_CHUTE if it saw the divert.
2. Then the unload fix (reviewer_tick_1149) and the demo-path walk with screenshots (1151).
