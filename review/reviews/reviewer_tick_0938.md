last commit reviewed: f55fa59

- 41aa666 / 99321c1: good. General handshake rules (outline > 2x largest parcel = not a parcel; no handshake on an
  unfitted clock), bag-vs-cage importer fix with append-only corrections, live alert fires once (CHK_CAGE_W
  14:32:13.8) and nowhere else. No S2 constants in the runtime diff. Render rest done (~US$0.32 Modal).
- Concern: handshakes are 67% strict / 86% right-parcel-nearest vs truth. A wrong outline labelled with a tracking
  number on screen would undermine the whole "scanned here" idea.
Instructions:
1. On every screen (passport, Proof, landing, route wall), show a tracking-number label on an outline ONLY when the
   handshake is unambiguous (one candidate, passes both rules); otherwise show the clip with "can't tell which
   carton" and no label. Report in EVALUATION.md: shown-with-label precision vs truth (target 100% for what is shown)
   and how many were withheld. Check that the story parcel's own checkpoints (unload, tunnel exit, divert, cage
   set-down, cage pick, store door) are labelled correctly; if one is not, say which and why.
2. Then continue day_plan_mon_0215.md (finish A's screens + landing, then B).
