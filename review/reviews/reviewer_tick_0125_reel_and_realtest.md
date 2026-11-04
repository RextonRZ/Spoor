# Reviewer 01:25 Tue 3 Nov: two tasks (Rexton asked, detailed)

Order: Task 1 (journey reel design) first, then Task 2 (real phone footage test). Rexton films Task 2 himself, so send him
the filming sheet (2.2) as soon as Task 1 starts, and he can film while you build.
Rules that still hold: no faces, never "suspect", generative output never evidence, keys never printed, commit locally, no push.
Code freeze Wed 3 pm MYT.

---

## Task 1: Journey reel redesign (backend/src/spoor/forensics/journey_reel.py + JourneyReel.tsx)

Goal: the reel is the single most-shown asset in the video (Proof, 1:45 to 2:10). Today it reads as a debug render:
OpenCV Hershey font, two camera labels per frame, loud solid-green badges, bare black cards. Make it look like Spoor:
calm, CCTV-real, branded, every frame readable in one second. Same facts, same chapters, same honesty.

### 1.1 What stays (do not change)
- Chapter order, timings, tones, manifest, hashes, SAM outline on every frame where SAM followed the carton.
- The render's own CCTV OSD (camera name bottom-left, "SYNTHETIC - fictional hub" bottom-right): that IS the CCTV look.
- Labels only where the handshake is unambiguous (the 51/51 rule).

### 1.2 Type: real fonts, not cv2
- Draw all text with Pillow (ImageFont.truetype) on the frame, not cv2.putText. Use the app's own font (Inter, the
  frontend uses next/font Inter) as a TTF in assets/fonts/ (OFL licence file beside it). Tabular numbers for times
  (Inter feature "tnum", or use Inter's tabular digits / a mono for times only: JetBrains Mono or IBM Plex Mono, OFL).
- Sizes at 1280x720: step title 26 px semibold; time 22 px tabular; sub-line 17 px regular; chip 15 px semibold;
  label tag 14 px mono. Never below 14 px. Text colours: ink #F2F3F5, muted #A3A8B3 (cool neutrals, not the warm
  (244,242,240) now).
- Supersample: render the overlay layer at 2x and downscale, or draw text with anti-aliasing on an RGBA layer, so
  edges are clean after H.264.

### 1.3 Layout of a footage frame (1280x720)
- ONE top bar, 64 px tall, gradient from rgba(10,11,14,0.82) at the top to 0 at 64 px (no hard band, the footage shows
  through). Left to right, 24 px side padding, baseline-aligned:
  `14:11:16` (time, ink, tabular) · 16 px gap · `Into chute C12` (title, ink semibold) · on the far right the chip.
- Sub-line (only when there is one): 17 px muted, directly under the title, same left edge as the title. Max one line;
  wrap is not allowed (rewrite shorter, max ~70 chars).
- Camera name: REMOVE ours from the top bar. The render's OSD already prints it bottom-left; one camera label only.
  (If a still has no OSD, e.g. the tunnel reader photo, print `Tunnel reader` small, muted, bottom-left in the same
  style as the OSD.)
- Chip (right of the top bar): pill, 28 px tall, 12 px horizontal padding, radius 14, TINTED not solid:
  fill = tone colour at 18 % over the dark bar, 1 px border tone colour at 60 %, text tone colour.
  Tones (match the app's evidence colours, one map shared with the frontend):
  - Scanned / Last scan: green #22C55E (text #4ADE80)
  - On camera: neutral, border #A3A8B3, text #E5E7EB (not green: it is seen, not scanned)
  - No scan / Not scanned in: red #EF4444 (text #F87171), only at the store door, per 1708_red
  - Records disagree: red, same as above, only at D07
  - Waiting (no camera): grey #6B7280, text #9CA3AF
- Progress rail INSIDE the reel: a thin rail just under the top bar's text row (y = 56 px), full width minus 24 px
  padding: one dot per chapter (8 px), done = ink 70 %, current = indigo #6366F1 ring 12 px, future = ink 25 %;
  connecting line 2 px ink 20 %, round caps (same ridge style as the logo/rail in the app). Red dots for the two red
  chapters. This lets a judge see "step 6 of 10" without reading.
- SAM outline: keep the mask edge, 2 px, colour #4ADE80 with a 1 px dark halo (draw 4 px rgba(0,0,0,0.5) first, then
  the 2 px line) so it reads on bright floors. No filled box. Ease-in: first 3 frames of a clip draw at 40/70/100 %
  opacity.
- Label tag (only when unambiguous): small dark tag, not a solid green block: fill rgba(10,11,14,0.78), 1 px
  #4ADE80 border, radius 4, text 14 px mono #E5E7EB, 6 px gap above the outline, a 1 px leader line to the outline
  if the tag had to move to stay on screen. Never covers the carton.
- Safe area: nothing drawn in the bottom 56 px except the OSD (the web player's controls sit there).

### 1.4 Stills (tunnel reader photo)
- Do not show the raw grey photo full-bleed. Card layout: dark background (#0B0C0F), the reader's photo centred at
  ~70 % height with radius 8 and a 1 px #2A2D35 border, the label read shown as the tag style above, plus the same top
  bar. Line under the photo, muted 17 px: `DWS-01 · 14:10:40.690 · weight and size measured` (from the record).

### 1.5 Cards (Intro, "Waiting in RC-760 for 11 min", the answer card at the end)
- No more bare black. Background = the relevant CCTV frame, scaled to cover, darkened (multiply to ~25 % brightness),
  Gaussian blur radius ~8 px, plus a left-to-right gradient rgba(10,11,14,0.85) -> 0.4 so the text side is calm.
  - Intro card: CHK_UNLOAD first frame. Text: small fingerprint logo (assets/brand/spoor_logo_fingerprint_dark.png,
    32 px) + `Spoor` 20 px; then `Parcel CTX334048419302` 34 px semibold; then `Its journey through the hub, on
    camera` 20 px muted. Hold 2.0 s.
  - Waiting card: the CHK_CAGE_W frame at 14:21:34 with the cage RC-760 visible. Title `Waiting in RC-760 for 11 min`,
    sub `14:21 to 14:32 · no scan, no movement on camera` (keep the honest meaning). Grey dot on the rail.
  - Answer card (end): CHK_STORE frame at the door at 14:32:32, with SAM's outline frozen on the carton at the door
    (full opacity, the only bright thing on screen). Text block left, vertically centred:
      - `14:33:36 · end of recording` 17 px muted tabular
      - `Most likely in the Exception store (Z11)` 36 px semibold ink
      - `Carried in at 14:32:32 · not seen coming out` 20 px muted
      - 16 px gap, then the six checkpoints as a compact rail: Unloaded · Tunnel · Chute C12 · Cage RC-760 ·
        Store door · Truck D07; green dots for scanned, neutral for on camera, red for "not scanned in" (store) and
        "records disagree" (D07), the store dot with an indigo ring = where it is now. 13 px labels under dots.
    - Bottom-left: logo 24 px + `Spoor` + muted `Every parcel leaves a trail.` Bottom-right: keep `SYNTHETIC`.
    - Hold 3.0 s (the video needs time to land the answer).
- Transitions: 0.4 s crossfade between chapters (not cuts), 0.5 s fade into the answer card. Card text fades up 8 px
  over 300 ms ease-out. No other motion (emil-design-eng: work surface, no ambient motion).

### 1.6 Copy check (1855_wording + 1708_red)
- Chips: `Scanned`, `Last scan`, `On camera`, `Not scanned in`, `Records disagree`. No other words.
- "On the sorter" chapter says "Outlined, but it could not be told from the carton next to it": that is honest but
  weak in the video. Shorten to `Too close to the next carton to label` (sub-line), chip `On camera`. Keep the chapter.
- No em dashes, no ids other than the parcel's own number, times in MYT.

### 1.7 Web player (JourneyReel.tsx)
- The player already shows a caption bar under the video (camera · time · title · chip). Since the reel now carries its
  own top bar, the player caption must not repeat it: keep the step cards under the player (the clickable rail), drop
  the duplicate caption line, or reduce it to the chapter number `Step 4 of 10` muted.
- Poster image = the new intro card, not a black frame.

### 1.8 Done when
- Contact sheet (3x4 like reel_tones_sheet.jpg) + full-size frames: intro, a scanned step, the tunnel still, an
  on-camera step, the waiting card, the store door (Not scanned in), D07 (Records disagree), the answer card.
  Save to review/shots/tue/reel/. Also 1440 screenshot of the Proof page with the player.
- Check at 50 % zoom that every title is still readable (the video will be watched small).
- Skills: emil-design-eng, impeccable, rexton-ui, design-taste. Time box: 3 h.

---

## Task 2: Real phone footage test (optional, hard limit 3 h build + SAM <= US$1)

Goal: answer the judge's doubt "it only works on Blender footage" with ~8 s of real footage where the same handshake
(scan time + scan spot -> SAM prompt -> track that carton -> next spot) outlines the right box and not its look-alike.
It is a separate test, never part of case S2's evidence.

### 2.1 What the agent prepares first (send to Rexton within 30 min)
1. `assets/realtest/labels.pdf`: 3 A6 shipping labels, fictional CONTOH Express style, Code128 barcodes with fake
   numbers CTX900000000101 / 102 / 103, big human-readable number. Printable on A4.
2. A one-page filming sheet (2.2 below) as `assets/realtest/FILMING.md`, plus the same text in READY.md for Rexton.
3. `assets/realtest/scan_log.csv` template: `waybill,event,spot,time_s` (time_s = seconds from the video start;
   Rexton or the agent fills it from the video; labelled "hand-entered from the video" in EVALUATION).

### 2.2 Filming sheet for Rexton (the agent copies this)
- Camera: phone in landscape, 1080p 30 fps, fixed on a shelf/cupboard top or taped to a door frame, 1.8 to 2.2 m high,
  pointing down at ~40 degrees, like CCTV. Lock focus and exposure (long-press on iPhone, Pro mode on Android). Do
  not touch the phone during the take. Even indoor light, no window in frame.
- Floor or a big table. Two A4 sheets taped flat, 1.5 to 2 m apart: sheet S = "scan spot", sheet C = "cage spot".
  The A4 sheets double as calibration (known size 21.0 x 29.7 cm).
- Boxes: 3 boxes. Box A and Box B must look alike (same size and colour if you can: the look-alike test). Box C
  different. Stick label 101 on A, 102 on B, 103 on C, label facing up.
- Before the take, B and C sit on sheet C ("in the cage").
- Take (60 to 90 s, one continuous video):
  1. 0-5 s: empty scene, nothing moves.
  2. Hands bring Box A in and set it on sheet S. Hold still 3 s. Say "scan" out loud (the audio marks the scan
     moment). Optional: point a second phone's barcode app at the label at that moment.
  3. Hands pick A up and carry it slowly to sheet C, put it down right next to B (touching is fine).
  4. Wait 5 s. Then hands slide B away a little and carry A out of the frame on the far side.
  5. 5 s of the scene after it leaves.
- Privacy: only hands and forearms in frame. No face, no mirror, no screens, no other people. If the frame catches
  more than arms, re-take. Plain clothes, no name tags.
- Do 2 takes. Send both MP4s into `assets/realtest/raw/` (gitignored if > 50 MB; keep a 720p copy for the repo).

### 2.3 What the agent runs
- Calibration: click the 4 corners of each A4 sheet once (or detect the white rectangles) -> homography floor <-> pixel;
  report the reprojection error in px.
- Scan time: find the "scan" word in the audio (Muse Voice Transcribe if it is already wired, else the audio peak);
  write it to scan_log.csv. Spot = sheet S centre in pixels via the homography.
- Handshake, exactly as in the S2 pipeline: at the scan instant, prompt SAM 3.1 with the point at sheet S's centre plus
  a box of the measured carton size (measure Box A with a ruler; Rexton types W x L x H into FILMING.md); track
  forward. Same "first-out"/carton-sized rules; no new tuning just for this footage (say so in EVALUATION).
- Truth: Rexton or the agent draws a box on Box A every 1 s (a 60-90 s take = 60-90 boxes; a small click tool in
  scripts/ is fine). Score: IoU >= 0.5 on Box A per sampled frame; and the key moment: when A sits next to B, is the
  outline on A, not B, and does it leave the frame with A?
- Output: `docs/open_weights_proof/realtest_eval.json` (rows: t, iou, on_right_box), a 10 s clip with the outline drawn
  in the NEW reel style (Task 1), corner chip `REAL · phone test` (neutral) instead of SYNTHETIC, and a 1-line result.

### 2.4 Pass / fail (decide honestly, by Tue 22:00 MYT at the latest)
- PASS: outline on Box A (IoU >= 0.5) in >= 90 % of sampled frames AND on A, not B, through the next-to-B moment AND
  leaves with A. -> use it (2.5).
- FAIL: write in LIMITATIONS.md what broke (e.g. "SAM jumped to the look-alike when the boxes touched") and the numbers.
  Do not tune the pipeline on this footage to make it pass; do not use it in the video. Stop.

### 2.5 Where it goes if it passes (only these four places)
1. Demo video, 2:40-2:52, replaces the plain "built in 3D" beat: split screen, left = Blender CHK_STORE clip with
   outline (label SYNTHETIC), right = the real phone clip with outline (label REAL · phone test), same outline style.
   Voice: "Real hub CCTV is private, so we built a hub in 3D and filmed it. Then we pointed a phone at real boxes: the
   same scan-to-camera handshake follows the right one, even next to its look-alike."
2. Landing page, "Built to be trusted": a 5th tile `Tested on real footage too`: 4 s loop of the real clip, one line
   `Same handshake, a phone camera, real boxes: right box in N of M checks.`
3. docs/EVALUATION.md: section "Real footage check" with setup, numbers, what it does NOT prove (one camera, one room,
   3 boxes, not a hub).
4. README: one line in the results table.
Not on: Hub, Answer, Proof, Insights, the case (it is not part of any case).

### 2.6 Cost and time
- SAM hosted <= US$1 (two 90 s takes at the existing rate is far below); no Modal, no Glimmer rerun.
- Build time box 3 h after the footage arrives. If Rexton cannot film by Tue 18:00 MYT, drop the task.
