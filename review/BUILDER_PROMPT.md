Rexton is in the office until ~22:00 MYT today and wants you to keep building non-stop until then.
A second Claude (the "reviewer", in Rexton's Claude app, linked to this folder) checks your work about every
30 minutes and sends fixes. You two talk only through files in `review/`.

Start now:
1. Read `review/README.md` (protocol), `review/QUEUE.md` (ordered work), `review/reviews/000_review.md`
   (open issues you must fix), then `review/log.md`.
2. Work the queue top to bottom. Run long Blender renders headless in the background and work on the
   frontend (QUEUE block C) while they run. Never wait idle for a review or a render.
3. After each finished milestone, write `review/requests/NNN_request.md` (format in README) listing the exact
   files to check, append a line to `review/log.md`, and carry on with the next item.
4. Check `review/reviews/` after every step and before starting anything new. Apply P0 fixes first. If you
   disagree with a fix, argue in `review/replies/NNN_reply.md` with evidence — the goal is the best result,
   not obedience. Quality bar: maximum; Rexton is a perfectionist and does not care how long it takes.
5. Things only Rexton can decide (push to GitHub, API keys, paid services, deleting his source files, licence
   doubts, changing 🔒 PRD rules) → append to `review/FOR_REXTON.md` and continue with other work.
6. Hard rules stay: the Spoor runtime never reads `render_truth.*` or `build/truth/`; scan logs labelled
   `scan_simulated`; fictional brand only; CC0/CC-BY/MIT/OFL assets only; footage labelled SYNTHETIC;
   no fabricated model outputs in the frontend — honest "no API key" states instead.
7. Keep backend tests green, commit locally after each approved item (no push), keep ≥ 15 GB free disk.
8. If your context gets long, everything you need is in `review/` — re-read QUEUE.md and the newest review.
9. Around 21:30 write the end-of-day summary in `review/FOR_REXTON.md`.

Do not stop to ask me questions — I'm not here. Decide, note the decision in log.md, keep going.
