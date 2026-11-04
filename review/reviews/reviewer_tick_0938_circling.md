last commit reviewed: f55fa59

Rexton asks: make the circling (handshake) more accurate, not only hide the uncertain ones. Ideas, all general (any
parcel, any scan point; no S2 constants), measured with eval_handshakes.py against truth (evaluation only):
1. EXPECTED BOX, not a point: project the parcel's own tunnel-measured L x W x H through the camera pose at the scan
   point (and the predicted belt position at the scan instant + reader-to-exit delay) -> an expected box with size.
   Prompt SAM with that box; reject candidates whose box size differs from the projected size beyond tolerance.
2. MOTION CHECK over a short window (e.g. -0.5 s .. +1.5 s): on a belt the right carton moves along the belt
   direction at belt speed; in a handheld scan it moves with the worker's hands. Score candidates by how well their
   track matches the predicted path; pick the best only if it clearly beats the second.
3. ORDER (global assignment): within one window, assign all scans at a scan point to all cartons coming out of it
   together (Hungarian on time + position + size cost) instead of each scan greedily; belts keep order, so the
   sequence of reads must match the sequence of cartons on camera.
4. PREFER the close-up checkpoint camera; use the wide camera only to confirm.
5. Clock: if a camera's fitted offset has uncertainty bigger than the gap between two consecutive cartons, abstain
   there (already partly done); do not fit a clock from the handshakes themselves.
Report per scan type (handheld, tunnel exit, divert, cage) before/after: strict %, right-parcel-nearest %, withheld %.
Target (Rexton): 100% correct on every label shown (precision, checked against truth), AND 100% of the story parcel's checkpoints labelled and correct; for all other scans, aim to label at least 80% (coverage) with every shown label correct, and withhold the rest rather than show a wrong one. The UI does not show these percentages (no "67%" on screen); a withheld one just says "can't tell which carton". EVALUATION.md reports the real numbers honestly. Time box 2 h, Meta spend for SAM
re-runs <= US$5 (log it). Keep instruction 1 of reviewer_tick_0938 (label only unambiguous ones) as the safety net.
