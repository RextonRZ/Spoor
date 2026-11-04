last commit reviewed: 1ff7654

Rexton (on hub_story_1440.png + case_1440.png):
1. FOCUS AREA on every evidence image: crop/zoom each displayed frame around what matters (the outlined carton,
   the person carrying it, the door, the cage leaving), not the full wide frame. Example: the Hub live-alert card
   ("A carton left the west cage bays without a scan") shows mostly empty floor; it must show the cage bay and the
   carton/hands at 14:32:13 with SAM's outline. Same for the side-panel image, the 5 moments, the passport tiles and
   the hero. Keep the full frame one click away. Crops come from the outline/track box with padding, never hand-tuned
   per image.
2. DESIGN the moments strip (01-05) and the checkpoint tracker better: they still don't feel comfortable or nice.
   Load and follow ALL FOUR skills before this pass: emil-design-eng, design-taste, impeccable, rexton-ui. Ideas to
   test against the skills: fewer competing labels per item, one clear time + one plain line, consistent card sizes and
   baselines, the red items clearly "the problem", calmer spacing and type scale, a short relative-time connector that
   reads as a timeline, the selected moment synced with the hero. Write in the log what each skill changed.
3. Before/after screenshots at 1440 and 390 in review/shots/mon/, READY.md entry. Do this right after the SAM
   outline work (reviewer_tick_1240_outline.md), before the demo-path walk.
