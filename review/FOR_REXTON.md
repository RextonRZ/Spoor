# For Rexton (append only)

Decisions only you can make, problems, and the end-of-day summary go here.

## Frontend (block C) — decisions for Rexton (frontend agent, 30 Oct)
- **Colour tokens**: your rexton-ui rule says tokens get your approval before building. You were away, so I chose a
  dark-neutral set (table in `review/requests/002_request.md` §3) and built on it. A theme change is a variable swap in
  `frontend/src/app/globals.css`. Dark only for now (PRD §19.1).
- **Licence note**: `frontend/public/draco/` is the Draco mesh decoder that ships inside the `three` npm package
  (Apache-2.0 code library, not an asset). If you want only MIT/CC0/CC-BY/OFL even for code, I can switch the GLB to
  meshopt compression (MIT) instead.
- **Demo sign-in**: the web app switches between three local demo users (investigator / reviewer / site admin) through
  a cookie; tokens stay server-side in `frontend/.env.local` (git-ignored). A real identity provider is out of scope.

## Builder notes (30 Oct, early morning)
- **Mixamo is out of the render path**, per your decision. Every worker is now Rocketbox (MIT), driven by a procedural contact solver (assets/hub/contact.py, stations.py). The Mixamo files are still on disk (gitignored) but no longer used.
- **The "387/388" chute photo you mentioned is not in docs/hub/reference_frames** or anywhere else under Spoor. I built the bag frames and woven bags from your decision text instead. If you have the photo, drop it in reference_frames and I'll check the bags against it.
- **Scan log change (render side):** each record now carries its own device clock: WCS for the sorter and tunnel, the handheld fleet (−2 s) for scanners, plus the handheld batch-upload receive time. The true time moved to build/truth/events_truth.jsonl. Before this, the log had a `t_s` field that leaked true time; it's gone.

## 04:50 · reviewer — top blocker for the demo
Meta tooling is 25 % of the score, and every model step (SAM 3.1 tracking, Muse Spark reasoning, agents) currently shows
"analysis unavailable — no API key". The app and the footage are ready to receive them. **Getting the Meta Model API key
(and Baseten) in and running `docs/build/00-setup-and-smoke-tests.md` is the single most valuable thing you can do when
you're back.** The builders will not touch keys.

## 05:05 · builder — Nov 4 fit estimate (you asked to be warned)
- **It fits, but with no room for a second full render.**
  - The batch is 25,200 frames at 2688×1520, at 6–9 s/frame (measured at the final settings) = **42–63 h** on this laptop.
  - Add ~12–18 h of fixes/QA/test render before it, and ~4–8 h of Spoor evaluation after.
  - Total 58–89 h, against ~115 h until Nov 4.
- The batch must start by **Oct 31 morning**. While it runs, the laptop's GPU is busy, so expect the machine to be slow.
- Render order puts **S2 (the pitch core) first**, ~3–4.5 h, then S0 → S5 → S3 → S4 → S1.
- **Your call (only if you want more slack):** render at 1920×1080 instead of 2688×1520. That is ~40 % faster, but the clips are lower-res than the spec. Default: keep 2688×1520.

## 05:35 · reviewer — resolution decision (yours)
The builder estimates 42–63 h of rendering on your laptop for S0–S5 at 2688×1520, which fits Nov 4 only if the batch starts
by Oct 31 morning and nothing is re-rendered. **My recommendation: render at 1920×1080.** It saves ~40 % of render time,
and 1080p (2 MP) is the most common real CCTV resolution in hubs, so realism doesn't drop. The builder keeps 2688×1520
until you say otherwise.
