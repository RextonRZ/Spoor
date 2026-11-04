# Spoor handoff for a new reviewer chat (written Sun 1 Nov, state as of Sat 31 Oct 22:36; read review/log.md tail for anything newer)

You are helping Rexton (solo, Indie Developer track) finish Spoor for the Meta Global AI Developer Hackathon 2026.
Deadline: Wed 5 Nov 2026 10:00 MYT. Target: submit Tue 4 Nov evening.
Spoor = an agent crew that investigates where a missing parcel went in a parcel hub, from CCTV + scan records. Tagline: "Every parcel leaves a trail."
Demo hub = fictional CONTOH Express, built in Blender, 19 CCTV cameras (CAM_01..19) + 2 tunnel scanner cameras. All footage SYNTHETIC and labelled.

## Read first
- review/QUEUE.md (top banners = all decisions), review/log.md (last 30 lines), review/refs/flow/ (UI prototype, follow 100%)
- review/reviews/owner_ideas_0303.md, agent_showcase_0925.md, design_sprint_0835.md, builder_note_1310.md

## Agents (Rexton runs them in VS Code)
- Render agent (Opus): owns assets/hub/ only. Blender sim of scenario S2, glitch gates, Modal render.
- Frontend agent: owns frontend/ (+ backend). Codex (ChatGPT, Sol) does locator images in assets/locator/ only.
- Agents commit locally, never push (Rexton pushes). One commit at a time (.git/index.lock).

## Scenarios
S0 normal, S1 no-read rework, S2 = THE DEMO (records say loaded on truck; cameras show it was taken out of the cage into the exception store, no scan-in), S3 dropped beside chute, S4 RFID cross-read, S5 look-alike pair. Render S2 first; S0+S3 if time.

## Where things stood (Sat 22:36)
- S2 sim runs 6..18. Run 17 best: 0 head clips, 0 overlaps, 0 story glitches, story parcel history complete (5 scans 14:10-14:21). Collisions ~170 excluding flow_parcel_073 stuck 7.5 cm in a chute (304 frames). qa_checks: feet_floating 64, feet_sliding 25 untouched.
- Decision: run 18 is the LAST full run; pick better of 17/18 as FINAL, commit, then touchup_final.py (per-object keyframe fixes on the final blend, no flow re-run, scan log unchanged), then free local preview grid MP4 (19 cams, 640x360). Rexton watches it, only visible issues get touched up. Then 3 look-check stills/camera on Modal (< US$1), then full render estimate (~US$19.5 for 19 cams x 900 frames on L4; >US$10 needs Rexton's OK). Frames stay on Modal, download MP4s only. Stop if C: < 20 GB free.
- WARNING: assets/hub had no commit since Sat 13:25. Make sure it is committed.
- Scan checkpoints added (6): unload (handheld) -> scan tunnel DWS (barcode, weight, size, photo) -> chute -> bag/cage (handheld) -> exception store scan-in (skipped for story parcel) -> truck RFID. DWS monitors (fictional brand SUKAT) visible CAM_04-08. Scanner photos render after S2 render starts.
- Frontend: app follows prototype (top bar, one user, no account switching). Landing page built (hero = 19-camera wall, search sweep, push-in on real sightings, trail). Checkpoints UI, wording fixes requested. Locator images (Codex): Z11 exception store, eye-level "phone photo" + tight map view + three_camera for "Open in 3D".

## Next after the render
SAM 3.1 boxes on S2 clips -> frontend reseed from final run -> keyed S2 run (Muse Wonder lead, Muse Spark analysts, SAM 3.1, verifier) recorded -> landing with real clips -> 3-min video (incl. 3D twin <-> real render transition) -> submission doc (Claude Doc "Spoor - Hackathon Submission"), README, X post. Evaluation numbers on S0-S5 (right clip in top 3, wrong matches, time saved, cost). Optional: real phone-video test.

## Standing rules
- Keys only in backend/.env; never print/log/copy keys. Modal token via `modal token set` (never read it).
- Caps: Meta <= $60, Baseten <= $50, Modal ~$30 credit, Glimmer <= $3. Any single run > $10 needs Rexton's OK. Stop at 75% of a cap.
- Fictional brands only; never real CCTV; generative output never becomes evidence.
- Parcels, not people: no faces, no face recognition, workers = anonymous "Person A", scanner IDs masked (reveal with typed reason, logged), never the word "suspect".
- Never claim proof: "most likely went... shows you the clips so you can check it yourself".
- UI copy: plain words, no em dashes, no tech jargon.
- Rexton prefers short, simple answers; he is a perfectionist; judge glitches by what is visible on camera.
- Delete only regenerable files. Don't touch AppData\Local\Claude-Data.
