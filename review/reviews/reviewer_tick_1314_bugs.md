last commit reviewed: ad7d67a

Reviewer, on review/shots/mon/passport_after.png, passport_follow_1.png (12:39) and case_1440.png (12:57):
1. BUG: the zoomed passport tiles are BLACK (Unloaded, On the sorter, Into chute C12, Into a cage, store, dock):
   only the green box and the label render, the cropped image does not. The crop must show the frame region.
2. BUG: case_1440.png at 12:57 is an empty skeleton ("Lost track", grey bars). Either the screenshot was taken
   before load, or the case API is hanging: the reviewer saw /v1/sites/.../dashboard pending > 45 s at 12:25 on the
   Hub ("Reading the scan log" forever). Check backend response times while your jobs run; the demo must not hang.
   A screenshot only counts after the page finished loading.
3. The outline is a small square box, not SAM's mask edge, and the chute tile uses the far CAM 11 (carton tiny).
   Draw the mask contour; prefer the CHK_CHUTE close-up where it saw the divert; zoom so the carton fills the tile.
Fix 1 and 2 first, then continue tick 1245.
