last commit reviewed: 1ff7654

Rexton (from case_1440.png 12:01): "why is the parcel not circled, where is SAM's follow?" The handshakes store SAM's
outline per frame and the follow ("followed 2 s / 6 s"), but the passport tiles and moment thumbnails show plain
frames, so SAM is invisible. Fix (UI, emil-design-eng + design-taste):
1. Every passport tile and every moment thumbnail draws SAM's outline (mask edge, not just a box) on the carton, with
   the tracking number label when the handshake is labelled, and is cropped/zoomed around the outline so the carton
   fills a good part of the tile (show the full frame on hover/click).
2. Clicking a tile plays its clip with the outline moving frame by frame through the follow window ("Followed on
   camera for 6 s"), then hands over to the next checkpoint's clip. That is the visible "SAM follows it" moment.
3. A small "Outlined by SAM 3.1" caption on these tiles (plain words), consistent with the hero.
4. Also: the last passport tile is cut off at 1440 (row overflows: "Its cage at dock D0..."); wrap or scroll inside
   its own container. Map inset label "Exception..." cut at the right edge.
Screenshots before/after in review/shots/mon/, READY.md entry.
