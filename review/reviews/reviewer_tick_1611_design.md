last commit reviewed: c345a18

OWNER (Rexton): the screens still look "AI-made". Do ONE design pass (time box 2 h) with emil-design-eng,
design-taste, impeccable and rexton-ui loaded, on Hub, Investigating, Answer + journey, Report. Reviewer's read of
demo_path2 screenshots, what reads as AI-generic and what to do instead:
1. Card soup: every block is the same rounded dark card with the same border, cards inside cards (hero inside a card,
   customer card, journey card). -> Flatten: one surface, sections separated by space and hairline rules; a border
   only where something is truly a separate object (the video player, the alert).
2. Chip overload: "Scanned here", "No scan", tracking-number chips, "Likely location found", tool chips with ticks.
   -> Plain text with a small status dot; the tracking number in plain tabular text; at most one badge per item.
3. Developer words on screen: read_scans, footage_for x2, door_crossings, carrier_check, sam_track, verify_claim,
   create_search_task. -> Plain verbs ("Read the scans", "Found the footage", "Checked the door", "Tracked the carton
   with SAM 3.1"). Model names stay small and secondary.
4. Rainbow role colours in the crew log (blue/pink/yellow). -> Monochrome log: time in muted tabular figures (elapsed,
   per tick 1540), role in muted text, sentence in normal text; colour only for verdicts (green passed, red rejected).
5. Generic indigo accent on everything (buttons, active step, links). -> Pick an identity that fits a CCTV / ops
   console: neutral near-black with a slight warm or cool bias, ONE accent used rarely (primary action + active
   step), amber/red reserved for "no scan / records disagree", green only for verified.
6. Evidence is not the hero: a large empty black player, small frames. -> Video first: the player shows a poster
   frame with the outlined carton, VMS-style overlay (camera, clock, step) on the video itself, the step rail as a
   thin timeline under it, not a row of cards.
7. Type: one clear scale (title, section, body, caption), fewer weights, tabular numerals for times and money,
   balanced headings. Monospace only for camera OSD-style labels, not for every ID.
8. Motion: subtle and purposeful only (step change, alert entry), respect reduced motion.
Keep all content and logic; this is styling/layout only. Before/after screenshots (1440 + 390) of the 4 screens in
review/shots/mon/design/, and one log line per screen saying what each skill changed. Do it after the open items of
tick 1540, before re-recording any demo video.
