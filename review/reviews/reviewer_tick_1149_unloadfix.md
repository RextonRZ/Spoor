last commit reviewed: 17450e8

OWNER DECISION (Rexton, Mon 2 Nov): fix the story parcel's "Can't tell which carton" at Unloaded (14:10:01).
- In the W1 sim, space the unload door's handheld scans so no other parcel is scanned at SP-IN-N within ~1.5 s of
  the story parcel's unload scan (move the neighbour's scan/handling, not the story parcel's logged time 14:10:01.26).
  Keep the story scan log line unchanged; regenerate only the W1 neighbour lines that move, and keep W1's other
  parcels out of the store/app as before.
- Re-bake W1, gates on CHK_UNLOAD + CAM_02, local preview, then Modal re-render of CHK_UNLOAD + CAM_02 only (well
  under US$1; inside the US$12 cap). Re-ingest, re-run the handshake for that scan; the passport's Unloaded tile must
  show the outlined carton with CTX334048419302, checked against truth.
- Keep the general "can't tell" rule exactly as it is for any other busy door (the logic stays; only the scenario
  spacing changes). Say in LIMITATIONS: "the demo's unload door was spaced so the story parcel's scan is unambiguous;
  busy doors fall back to 'can't tell'".
Order: after the control re-run, before the UI pass in reviewer_tick_1147_ui.md. Time box 2 h; if it fails, keep the
honest "Two cartons scanned 0.2 s apart here" and move on.
