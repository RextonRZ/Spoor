last commit reviewed: ad7d67a

Rexton: "not marked correctly". In passport_follow_1.png (Into chute C12, CAM 11, 14:11:15) the green box sits mostly on
an EMPTY sorter tray at the chute mouth with only a sliver of white behind the yellow flap, while a clear carton sits
on the tray to its left. To a viewer it looks like the wrong spot, even if the stored handshake is right.
1. Verify overlay alignment end to end: same frame index as the stored outline (not the OSD second), same pixel space
   (1920x1086 delivery copy vs 2688 master: scale!), same clip. Add a test that draws a stored outline and checks it
   against the truth projection for that frame. Report any offset found.
2. Choose the DISPLAY frame inside the follow window where the carton is most visible (largest unoccluded mask area,
   e.g. sliding down the chute), not the instant it is hidden by the flap; prefer the CHK_CHUTE close-up.
3. Draw the mask contour, not a square; zoom on it. Then eyeball every outlined tile on the demo path and say in
   READY.md "checked by eye: the outline sits on the carton" for each, with the screenshot.
