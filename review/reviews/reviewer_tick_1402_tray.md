last commit reviewed: ba932cd

Rexton spotted it, reviewer confirmed by zooming passport_after.png (13:49): on "Into chute C12" SAM's outline is the
whole flat SORTER TRAY (carrier plate) with the small carton sitting on it, not the carton. The eval still says
"right" because it only checks that the carton's true centre is inside SAM's box (handshake_eval.json:
box [1234,238,1300,300], truth (1269,265)). A tray-sized outline around a carton passes that test but looks wrong.
1. Rule: the outline must be carton-sized. Project the parcel's own DWS size (25.5 x 18.3 x 10.2 cm) through the
   camera pose at the scan point -> expected pixel box/area. If SAM's mask is much larger (tray, bag, cage, person),
   re-prompt SAM with a tighter box/point on the carton's top face inside it (general, any parcel), or take the
   sub-mask that matches the expected size; if neither works, don't label it.
2. Stronger eval: compare against the truth carton's projected 3D box (IoU of boxes, and mask-area ratio vs the
   expected area), not only "centre inside box". Re-run, report per scan type; anything failing loses its label.
3. Re-check every labelled tile by eye (zoomed) and post the zoomed crops in READY.md.
Do this before the unload fix.
