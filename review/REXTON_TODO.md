# Rexton's open asks (kept current; newest at the bottom of each list)

## Video fixes (Rexton 3 Nov ~01:20) - one W1 re-bake + one Modal render
- [ ] Unload door: no zombie carry (front carry, fixed in code) + the mate works during the scan (staging, gate attempt 6 running)
- [ ] Chute C12: the parcel no longer vanishes into a full bag (lands and stays on top; fixed in code, in bake 6)
- [x] Chute C12 "box looks kemek": far cameras zoomed less in the reel (min crop 0.6)
- [ ] Checkpoint 3 "On the sorter" gets its outline + number: the induct is reported where the parcel boards the loop
      (plan event_positions), not at the induction belt; SAM now aims there at the deck height, cameras chosen by
      calibration (CAM 06 sees it), label only if it rides off along the loop. Needs a CAM 06 clip (Modal, with the door)
      + handshakes re-run
- [x] Map: stop 3 showed before 2: reel/map use the event's own spot (checked on Proof: 1 -> 2 -> 3)
- [x] Chapters 8 and 9: one continuous carry (9 starts where 8 stopped)

## Tick 0125
- [x] Task 2 kit sent: labels.pdf, FILMING.md, scan_log.csv, READY entry
- [x] Task 1: journey reel redesign (+ Rexton: no stray outline on the answer card, bigger six-step rail, caption entrance, slow push-in; player shows "Step n of N")
- [ ] Task 2 run when the footage arrives (<= 3 h, SAM <= US$1); drop if no footage by Tue 18:00
- [ ] "Find a very similar real video for the demo": searched; no free CCTV-style hands-only clip with look-alike boxes;
      Intel Geti "Smart Warehouse" sample set (Apache 2.0) has conveyor + warehouse videos (link to confirm). Paused for
      the video fixes; to report

## Done this session
- [x] Insights dashboard, live window, simulated history, How Spoor learns, polish list
- [x] Settings removed; profile label
- [x] Loading pass (fade + shimmer, caches); collapsed sidebar centring; "Not due yet" for case 2

## Rexton 3 Nov ~02:00 (player + step strip)
- [x] Spoor logo bigger in the reel (intro 44 px, answer footer 32 px)
- [x] Steps under the player: each its own frame (the API cuts one per step from the reel), number + time on it, title, one status line, camera; green check on the frame where the number was confirmed
- [x] Custom player: scrubber split into the steps (hover shows that step's frame), play/pause, time, "Step n of N", full screen; keys Space / arrows / F
- [x] Reel sub-line unreadable on bright frames ("SAM tracked no carton..."): solid shade behind the words + brighter text with a soft shadow
- [x] Proof: "How sure" removed (Answer keeps the one limit; the numbers stay in LIMITATIONS / EVALUATION)
- [ ] Customer asked box on the Answer: kept for now (Rexton asked; recommendation sent)
