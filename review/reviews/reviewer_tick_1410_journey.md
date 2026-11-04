
OWNER CLARIFICATION (Rexton): "evidence video" = ONE merged video of the whole journey, every checkpoint's clip joined
in time order, with SAM's outline ON THE CARTON IN EVERY FRAME, following it exactly (not a still, not just a few
seconds at the scan). Build it as the case's evidence reel (extend forensics/reel.py, exportable MP4 + played in the
journey section):
- Per clip: run SAM's video tracking over the WHOLE time the carton is visible on that camera (from first appearance
  to leaving the view), prompted from the handshake; draw the thin carton-sized contour on every frame. If SAM loses
  it, re-prompt on a later frame (same object); never draw on a guess.
- Hand-over between cameras by place + time (as built); the outline continues on the next clip.
- Where the carton cannot be seen (inside cage RC-760 for 10 min with no footage, in the worker's hands behind his
  body on CAM_13, inside the store), show a short title card or caption ("In cage RC-760, no scan for 10 min",
  "Carton hidden by the carrier") instead of an outline. Never outline the person.
- Burn in per segment: camera name, its own clock, checkpoint name, "Scanned here" or red "No scan", tracking number
  when labelled. SYNTHETIC label stays.
- Check by eye that the outline sits on the carton in every segment (sample frames into READY.md) and re-run the
  stronger eval on the tracked frames. Estimate SAM frames + cost first (SAM ~US$0.20 per 1,000 frames; stay inside
  the US$5 circling budget or ask).
