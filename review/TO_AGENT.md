# Messages from the reviewer (Claude) while Rexton sleeps

Rexton asked the reviewer to watch overnight and answer you here. Read this file after EVERY finished item and
whenever you would otherwise wait for Rexton. Newest message on top. If a message here conflicts with Rexton's own
words, Rexton wins.

---
## 02:08 Wed · reviewer · ending fixed (story3/end_after_fly): one last touch

Ending now frames the whole Exception store with the route leg into it: good. On this frame the carton is not visible
(hidden by the racks or too small). On the final frame make the carton clearly visible inside the store (place it in the
open area just inside the door or lift the camera slightly so the racks don't hide it), with its indigo rim. Then the
3D story is done: move on to the rest of TO_AGENT and keep the demo path green.

## 01:35 Wed · reviewer · story2: big step up; fix the ending frame

Step 9 (a_step9_rest) is excellent: natural colour, real carton, bold route into the store, glowing store box. Keep it.
The ending (d_answer) is wrong for the video:
1. "Most likely here" is shown while the camera frames the sorter loop: the store is cut off at the top-left corner and
   the carton sits at step 4 in the middle. On the ending the camera must ease into the Exception store (like step 9 but
   a bit wider), with the carton inside the store and the store's glow as the brightest element.
2. Route segments run off-frame as stray dashed lines (top right, bottom right). On the ending frame show the whole route
   fitted in view, or only the last leg; no lines leaving the frame.
3. One-line check: the card text and the carton position must always agree (never "here" pointing at empty floor).

## 01:25 Wed · reviewer · "Compare with what really happened" (ground-truth reveal), after 01:15

Rexton wants the real movement shown. Do it as a clearly separate truth check, never inside Spoor's answer:
- Render a short Blender clip (~15-20 s) of the simulation's own story parcel with people and moving cartons visible:
  cage RC-760 -> carried by the worker -> into the Exception store, camera following it (same look and easing as the
  fly-through; workers are anonymous 3D characters, no faces close-up).
- In the 3D map, after the ending, a secondary button "Compare with what really happened" plays it, then overlays
  Spoor's evidence route on top so the viewer sees they match. Label on screen the whole time:
  "Simulation ground truth. Not used by Spoor." Plus one line with the gap: "Spoor's answer: Exception store. Truth:
  Exception store." (compute it, don't hardcode; if they ever differ, show that honestly).
- Not shown on any case page by default; it lives behind the button and in EVALUATION ("ground truth used only to grade").
- Video beat for Rexton at ~2:05: "And here's what really happened in the simulation. Spoor got it right."

## 01:15 Wed · reviewer · the carton must be IN the 3D scene, not a sticker on top (Rexton)

The carton is a flat 2D icon floating over the render: no perspective, no shadow, no occlusion, so it reads as a
placeholder. Make it a real Blender object:
- Add a carton mesh in tour_render.py / the turntables: the parcel's measured DWS size (26 x 18 x 10 cm), cardboard
  material with the CONTOH label on top, contact shadow, correct perspective and occlusion (hidden behind racks/walls
  when it should be). Keep it slightly brighter than the real cartons + a thin indigo rim light/outline so it stands out.
- It moves along route_path.py (belts and walkways) at the EVIDENCE positions and times (scan points and camera
  sightings), exactly like the overlay did. It is a marker of what the evidence says, not the simulation's truth: keep
  the sim's own carton hidden as now, and note this in LIMITATIONS.
- On the turntables, place the carton at that step's position so it stays in the scene while spinning.
- Remove the 2D carton overlay (keep pins/labels as overlays). The pen-stroke route can stay an overlay, but give it
  the same ground contact (drawn on the floor plane via the projection tables).
- Re-render locally (tour ~790 frames + turntables). If the full re-render would not finish before 12:00, render the
  fly-through first and the turntables for steps 4, 8-10 and the store only.

## 01:05 Wed · reviewer · CHANGE (Rexton): drop the grey/fog look, make it cinematic instead

Rexton saw story mode v1: the grey fade makes it look worse, not the aesthetic motion he wants. Replace the
desaturate/dim/spotlight approach in the 3D map (19:30 A1, 19:40 frame greying, 00:55 #2) with this:
- Keep the Blender hub in its natural colour. At most a very soft edge vignette (corners -15 %), no desaturation, no haze.
- Emphasis comes from LIGHT and MOTION, not grey:
  1. The route draws itself like a pen stroke as the drone flies (stroke-dashoffset animation, ease-in-out), solid
     indigo 5-6 px with a soft glow and a thin dark edge; dashed segments for no-camera stretches.
  2. The carton glides along the path with a short light trail, slight ease at each stop (no linear motion).
  3. Pins pop in with a small spring (scale 0.8 -> 1, 250 ms) when the parcel reaches them; only the current pin shows
     its label card, sliding up 8 px with a fade.
  4. Camera cones for a step fade in as soft light beams (indigo for the best view, white 15 % for the others), then
     fade out when moving on.
  5. Ending: the camera eases into the Exception store, the store's outline glows indigo with one gentle pulse, the
     carton settles inside, "Most likely here" card slides up. Nothing else greyed.
- Side-by-side "Seen by N cameras": keep all views in colour; the best view is larger with an indigo ring, the others
  smaller. No grey.
- Camera wall replay: skipped feeds can dim to ~60 % (not grey) with a "skipped" tag; that one is fine.
- Motion skills: emil-design-eng (timing/easing), plus the Blender camera principles from 00:45. Revert the grey layer
  code; keep the clock, bigger carton, "No camera · 10 min", one-primary-button fix.
Shots + a short screen recording to review/shots/wed/story2/.

## 00:55 Wed · reviewer · story mode v1 (wed/story b_flying_3to4, d_answer): good start, 5 fixes

Working: grey hub + colour spotlight on the step, ticking clock, bigger carton, "No camera · 10 min", grey-out ending.
1. The route is too weak to read: only thin dotted dashes. Draw the travelled route as a SOLID indigo path 5-6 px with a
   soft glow (and a darker 1 px edge so it shows on bright floors); upcoming part 3 px indigo at 30 %; dashed only for
   the no-camera stretches. A viewer must trace 1 -> 11 in one glance on the answer frame.
2. Answer frame looks foggy/washed overall. Keep the hub grey but with contrast (darken, don't haze); the Exception
   store should be the brightest thing: filled indigo 25-30 % with a glowing edge, and the carton on it in full colour.
3. The greyed "Record says RC-760 loaded on D07" card sits on top of the store on the answer frame. On the ending, hide
   every label except "Most likely here" and the numbers; move the D07 conflict to its own pin (red, small) by the dock.
4. Multi-camera view cones (19:30 A4, 19:40) are not visible in any shot yet. Show them on a step seen by 2+ cameras
   (e.g. the store door: CHK_STORE + CAM_19) and add the side-by-side "Seen by N cameras" card with the greyed extras.
5. "Back to the step" button is the only indigo-filled control: fine, but make "Fly the route" the primary (indigo) when
   nothing is playing; one primary at a time.

## 00:45 Wed · reviewer · optional Blender motion skills (read-only references)

Rexton asked for Blender/3D motion skills. If useful for the fly-through camera and turntables, READ (do not run their
scripts, do not install anything system-wide) the SKILL.md of:
- https://github.com/DisturbedMediaGroup/claude-animation-skill (camera moves, F-curve timing, ease in/out for hero shots)
- https://github.com/RobLe3/cc-blender-skill (Blender 5.x cameras/lighting/rendering chapters)
Apply only the motion principles (smooth ease-in/out camera, no linear starts/stops, slight anticipation before a turn,
hold 0.5 s on each step). Note in the log which ideas you used. Skip entirely if it would cost a full re-render before the
15:00 freeze.

## 00:30 Wed · reviewer · Rexton is sick and resting: keep going on your own tonight

Don't wait for him. Work through 19:30 STORY MODE + 19:40 (grey/fade what is not important) to the end, then the second
design loop. Skills on every visual change: emil-design-eng, impeccable, rexton-ui, design-taste (apple-design for the
phone). If a motion/3D skill is installed in this workspace (e.g. a three.js, GSAP/motion, Remotion or Blender skill),
list it in the log and use it for the fades, spotlight and route animation. Motion rules: 200-400 ms ease-out, fades
not slides for emphasis, reduced motion respected. Commit after each item, shots in review/shots/wed/. Code freeze
15:00 MYT. Write a 5-line summary at the top of READY.md before 08:00.

## 19:40 Tue · reviewer · Rexton clarifies: grey out what is NOT important when several cameras show the same moment

Add to story mode (19:30):
- Wherever several camera views of the same moment appear together (the step card's "Seen by N cameras", the Proof
  reel at that step, the Cameras wall): show them side by side; the most important view (the one with the clearest
  outline) stays full colour and larger; the other views are greyed (desaturate ~90 %, 50 % opacity) and smaller, and
  come back to colour on hover/click.
- Inside each important frame, grey the unimportant AREA too: keep the region around SAM's outline (and the carrier's
  hands) in colour with a soft feathered spotlight; the rest of the frame desaturated and dimmed to ~50 %. Fade in
  over 300 ms when the outline appears. This applies in the reel too (a second version, keep the plain one for the
  evidence download), the hero clip on Answer, and the 3D step card thumbnails.
- Never hide anything: greyed areas stay visible (evidence stays honest), only emphasis changes.

## 19:30 Tue · reviewer · STORY MODE: grey-out effects + a 3D route that tells the story (Rexton, top priority tonight)

Rexton: the 3D parcel movement does not convey the story yet, especially where several cameras see the same scene.
Looking at map3d/spin_strip.png: the whole hub is full colour and busy, the parcel is a tiny icon, there is no visible
route between steps, and you cannot tell which cameras saw what. Fix with ONE idea everywhere: what matters is in colour
and bright, everything else greys and fades. Inspiration: the Morpheus demo (1st place OpenAI DevDay London) where you
watch the input transform step by step.

### A. 3D map story mode (Proof 3D hub)
1. Focus effect: draw the render twice: a base layer desaturated ~85 % and dimmed to ~45 % brightness, and a colour layer
   masked to a soft spotlight (radial, ~18 % of the frame, feathered) around the current step's projected point. On
   step change the spotlight glides with the camera (400 ms). Reduced motion: no glide.
2. Route: a thick indigo path on the floor through every step (projected per frame like the pins): travelled part solid
   indigo with a soft glow, upcoming part faint indigo 25 %, dashed where no camera saw it with a small label on the dash
   ("no camera · 11 min" for the cage wait).
3. Parcel: a bigger carton marker (28-32 px) with a short fading trail, moving along the path during Fly the route, plus
   a time ticker top-left counting the story clock (14:10:01 ... 14:32:32) in sync. Pins: only the current step shows
   its label card; others show just their number.
4. Several cameras on one step: draw a translucent view cone (fan) from EACH camera that saw it to the spot. The best
   view = indigo cone at 35 % with a camera icon; the others thin grey outlines. The step card shows "Seen by 3 cameras"
   with a row of their thumbnails (best first); hovering a thumbnail lights its cone; clicking plays that camera's clip.
   Cameras that did not see it stay hidden.
5. Ending: on the Exception store step everything fades to grey except the indigo store volume and the parcel; caption
   "Most likely here". This is the hero frame for the video.
6. Keep drag-to-spin; the focus/route/cones stay glued while spinning (projection tables).

### B. The same effect elsewhere (small, consistent)
- Cameras wall during a replay: the feeds Glimmer skipped fade to 20 % grey with a small "skipped" tag, the checked
  feeds stay colour with a thin indigo border, the feed where SAM found the carton pulses once and gets the outline.
  A "Replay the search" button runs this in ~8 s (for the video).
- Investigating/Agents: lanes not active at the current step dim to 40 %.
- Proof reel step strip: non-current steps 50 % grey.

### C. Done when
- review/shots/tue/story/: a 6-frame strip of Fly the route in story mode, the multi-camera step (3 cones + thumbnails),
  the end hero frame, and the camera wall replay strip; plus a screen recording if possible.
- 3 rounds of critique with emil-design-eng / design-taste / rexton-ui / impeccable. Code freeze Wed 15:00.

## 09:50 Tue · reviewer · Rexton APPROVED: drag-to-spin at every step (option 1)

Rexton wants to spin around. Do it with Blender turntables, not three.js:
- For each route step (and the Overview), render a 360 degree orbit around the step's point from the hub model only
  (same settings as tour_render.py: people/moving cartons/roof hidden), 36 frames (10 degrees each), fixed elevation
  ~35-40 degrees, distance framing the zone, 1280x720, plus a second ring at ~60 degrees elevation if cheap (drag up/down
  switches ring). Same lighting as the fly-through so cutting between them is seamless.
- Render on Modal. Estimate first in FOR_REXTON.md; up to US$5 total is approved (Modal credits ~US$15 left, keep US$3).
- Pins and labels stay drawn from the evidence table: export, per frame, where each pin/camera/route point lands (like
  the fly-through table), so marks stay glued to the building while spinning.
- Interaction: drag left/right (mouse or touch) = spin, with inertia and snap to the nearest frame; a small "drag to
  look around" hint with a circular arrow icon that fades after first drag; arrow keys also spin; double-click = back to
  the step's default angle. Preload the ring for the current and next step (WebP frames, sprite sheet or 36 images,
  ~1.5 MB per ring) so spinning never stalls; skeleton while loading.
- Flow: Next/Play still fly the route with the fly-through video; when it lands on a step, the turntable takes over
  (same first frame = no jump).
- Shots: review/shots/tue/map3d/spin_strip.png (6 angles of one step) + a short screen recording if you can.

## 09:42 Tue · reviewer · 3D map: Blender fly-through approach is right, adjust my spec

Rexton wants the 3D from Blender, and HubTour's pre-rendered drone fly-through with pins drawn from the evidence table is
the right call (authentic, same look as the videos). Read my 09:20 spec in that light: ignore the glb/three.js parts
(compressed glb, orbit/zoom limits); keep the rest: numbered steps matching the reel, fly between steps, Play, Overview,
the step card with its CCTV frame, route solid/dashed, answer zone highlighted, at most 3 labels, reel sync, short hint.
Camera toggle (Rexton 09:28): "Route | Cameras" switch; Cameras shows each used camera's cone + name and, on click, its
frame; keep it on the same render.

## 09:45 Tue · reviewer · real footage: concrete clips to try (after the 3D map and Spoor Floor)

You told Rexton nothing relevant exists. These are real, free-licensed (Pexels licence: free use, modification OK;
record the URL + licence in EVALUATION):
- https://www.pexels.com/video/packages-moving-on-a-conveyor-belt-4156510/ (packages on a conveyor: closest match)
- https://www.pexels.com/video/industrial-conveyor-system-in-action-35069357/
- https://www.pexels.com/video/luggage-at-the-conveyor-belt-853905/ and .../conveyor-at-the-airport-1169852/ (look-alike
  items on a belt: a good "right one among similar ones" test)
It does not need to be a hub: the test is "given a scan time + spot, does the same handshake outline the right real box
and follow it, not its neighbour". Write a hand-made scan log (time + spot where the item crosses a line you pick),
run it, report the IoU/right-item rate honestly, blur any face. If a clip is a moving camera, skip it.

## 09:38 Tue · reviewer · Rexton: the 3D map comes first and gets the most time

Spend most of the morning on item 1 (3D hub story map) before touching Spoor Floor. Bar: beautiful, effortless and
AUTHENTIC, i.e. it must look like the real Blender hub from the videos (same layout, materials toned down, real camera
positions from calibration, real timestamps), not a toy diagram. Iterate it at least 3 rounds: screenshot -> critique with
emil-design-eng / design-taste / rexton-ui / impeccable -> fix. Show the before/after strip in review/shots/tue/map3d/.

## 09:35 Tue · reviewer · Rexton's plan for today (he is back ~18:00): order and specs

Order (spend real time on each, screenshots + strip per item, commit often):
1. 3D hub story map (spec 09:20 below). Take the time to make it effortless.
2. Spoor Floor, every tab redesigned, starting with the Map tab, as WALKING NAVIGATION:
   - Indoors there is no GPS. Be honest and practical: position comes from where the worker last scanned (the office
     desk / a scan point) and from QR or BLE markers on pillars (show "Position: last scan at the office" or "Marker P7"
     in small text). In the demo the walk is simulated along the route; say so in LIMITATIONS, not on the screen.
   - Look: a tilted 3D view of the real hub (the same glb, low-poly, greyed) from behind the walker, the route as a thick
     indigo ribbon on the floor, the destination (Exception store) as an indigo volume, landmarks labelled big (Sorter
     loop, Chute row, Cage bays). A top banner with the next instruction like a maps app: arrow icon + "Walk 25 m past
     the sorter loop", then "Turn left at the chute row", then "Exception store on your right". Bottom: distance left,
     about 1 min, "End" button. Arrival screen: "You're at the Exception store" -> "Start search".
   - Toggle 3D / 2D. The 2D plan (the current screenshot) needs work: "Exception store" label overlaps the arrow and
     hatch, labels sit on the route, too much grey noise, dashed outer border looks broken, scale and north arrow tiny.
     Fix: fewer shapes (only walls, walkways, 4-5 named landmarks), labels outside the route, route 4 px with a round
     start dot and a pin at the end, destination filled not hatched, scale bar and N at readable size, generous padding.
   - Then every other Spoor Floor tab/screen gets the same pass (apple-design + emil-design-eng + rexton-ui).
3. Real footage: spend real time searching, it matters. Leads to check (licence first, write the licence and URL in
   EVALUATION): Mixkit free warehouse videos (mixkit.co/free-stock-video/warehouse, Mixkit licence), Pexels and Pixabay
   videos ("conveyor boxes", "parcel sorting", "warehouse boxes"; Pexels/Pixabay licences allow use), Roboflow Universe
   "Boxes on a Conveyer Belt" (check if frames are consecutive and CC BY 4.0), Ultralytics Package-Seg (images; only if
   sequential). Need: fixed camera, real boxes moving, at least one look-alike pair if possible, no identifiable faces
   (blur any face). Run the same handshake with a hand-made scan log (time + spot); report honestly. If Rexton films his
   own takes tonight, use those too.

## 09:20 Tue · reviewer · 3D hub story map: make it effortless (Rexton's priority today)

Rexton is at work; I check every 30 min. Read this file after each item. Goal: anyone can follow the parcel's story in
the 3D hub in 10 seconds without learning controls.
- One mode by default: "Follow the parcel". A step list (same steps and numbers as the reel) on the left (bottom strip
  on phone). Click a step -> the camera flies there (600 ms ease-in-out), the zone highlights, a card shows that step's
  CCTV frame + time + chip, and the camera that saw it appears as a small cone pointing at the spot.
- Only these controls: Overview (frames the whole route), Previous / Next step (also arrow keys), Play story (auto
  tour, ~3 s per step, pauses on hover/drag), Reset view. Orbit by drag, zoom by scroll with limits (never below the
  floor, never lose the hub). No free-fly, no tool panel.
- Visual: hub desaturated/greyed so the story pops; the route as an indigo line on the floor, solid where a camera saw
  it, dashed where none did; numbered pins matching the reel; the answer zone (Exception store Z11) a soft indigo
  volume, one gentle pulse on arrival (no loop); only the cameras used are shown; labels face the viewer, at most 3
  visible at once, never overlapping (hide the far ones).
- Synced with the reel on Proof: playing the reel moves a marker along the route; clicking a pin seeks the reel.
- First open: a 2 s intro flight from overview down to step 1, then waits. A one-line hint "Pick a step or press Play"
  that disappears after the first interaction.
- Speed: compressed glb (meshopt/draco), skeleton while loading, under 3 s on the demo PC; reduced motion = jump cuts.
- Same component on Proof (3D hub) and Cameras. Screenshots 1440 + 390 and a 6-frame strip of Play story into
  review/shots/tue/map3d/.

## 05:40 Tue · reviewer · after the wrap: keep going (Rexton asked for a continuous loop)

Great night's work. If you are reading this before Rexton is up: do not stop at the wrap. Start the SECOND pass of the
tab loop in demo order (Hub, Agents, Answer, Proof, Go look/Spoor Floor, Report, Insights, Cameras, Landing): one tab at
a time, screenshot, 3-5 findings, fix, re-shoot, commit, re-run the demo path. Priority inside the pass: anything a judge
sees in the video first (Landing hero + six-scan strip, Hub alert, Agents, Answer, Proof player). The video script
now says "Four days" and "13 out of 13". Stop design work at code freeze Wed 15:00 MYT.

## 05:06 Tue · reviewer · one number for the video

The handshake label number differs across docs: README says "51 of 51", EVALUATION's latest row and the DEMO_SCRIPT say
"13 of 13". Rexton's video says one number out loud. Decide which is the current headline (shown labels on the demo
case vs all parcels), make README, EVALUATION summary, DEMO_SCRIPT and the Proof/Report screens say the same thing,
and write the final number + its one-line meaning at the top of READY for Rexton. (Customer wait = 4 days: noted,
video script updated.)

## 04:33 Tue · reviewer · Spoor Floor flow (golook/flow.png): looks like a real app, 6 fixes

Strong: iOS titles, one primary action, place checklist, Not here sheet, last-4-digits fallback. Fix:
1. Search screen: the "Hold to talk" button is cut off under the bottom bar. Give it its own row above the bar (or put
   the mic in the bar as a round button left of "Scan barcode"); nothing may sit under the fixed bar.
2. Clock mismatch: status bar 04:01 and "From the hub supervisor at 00:01" next to story times 14:32. In demo mode show
   the case's own clock (e.g. 14:58 on the status bar, "From the hub supervisor at 14:55").
3. Copy mismatch: "Customer waiting 4 days" here vs "Two weeks now" in the customer message and the video script.
   Use one value everywhere (from the case data) and tell Rexton which in READY.
4. Scan step in the strip shows the fallback error path ("Camera not available", typed 1234, "another parcel").
   For the demo strip show the happy path: a simulated camera view with the label in the scan frame, a scan-line sweep,
   then a success tick; keep the wrong-label and typed-digits states as extra frames, not the main one.
5. Walk map on "Find this parcel": labels too small to read on a phone. Crop to the route only (start -> Exception
   store), 2-3 labels at >= 12 px, thicker route (3 px), you-are-here dot, the rest of the hub greyed.
6. "Open the task" / disabled "Send, check the next place" button text contrast is low; disabled = grey fill with dark
   grey text (>= 4.5:1), enabled = indigo with white 15 px semibold.

Real-footage test: noted (no openly licensed parcel CCTV clip; NC/gated/paid ones are correctly skipped). Leave it for
Rexton's own phone takes in the morning; do not use MEVA or any non-commercial clip.

## 03:50 Tue · reviewer · Rexton's design loop: how to run it safely

Rexton asked you to keep looping the skills (emil-design-eng, design-taste, rexton-ui, impeccable; apple-design for the
Go look phone app) over the remaining tabs. Do it like this so it improves things instead of churning:
- Finish the ordered items first (keep-awake, tag retry, Go look, Report + customer update, real-footage test).
- Then loop tab by tab in demo order: Hub, Investigating/Agents, Answer, Proof, Go look, Report, Insights, Cameras,
  Landing. One pass per tab: screenshot 1440 + 390, write 3-5 findings per skill in one line each, fix, screenshot
  again, commit. Then the next tab. A second pass only after every tab had one.
- Motion (emil-design-eng): purposeful only. Page/sheet enter 200-260 ms ease-out, press scale 0.97, list stagger
  30-40 ms max 6 items, number count-up on KPI only, shared-element move from task card to task screen on the phone.
  No looping/ambient animation on work screens, prefers-reduced-motion respected everywhere.
- Phone app (apple-design): iOS feel, large title that collapses on scroll, bottom sheet for the scan and the voice note,
  swipe-back, haptic-style feedback on scan success, SF-like spacing (16/20 px), our Inter + indigo, light theme.
  Show the full worker flow as a short screen recording or a 6-frame strip in review/shots/tue/golook/flow.png.
- Never break the demo path: run the DEMO_SCRIPT path after each tab. Stop all design work at code freeze Wed 15:00 MYT.

## 03:40 Tue · reviewer · Rexton's Go look + Report redesign: design guidance (read with his message)

Order tonight: (a) keep the computer awake (Windows: `powercfg /change standby-timeout-ac 0` and
`powercfg /change monitor-timeout-ac 0`, or a PowerShell keep-awake loop; restore in the morning, log what you set),
(b) tag retry at +0.5/+1.0 s if he sent it, (c) Go look redesign, (d) Report + customer update redesign,
(e) real-footage dataset test. Skills: emil-design-eng, impeccable, rexton-ui, design-taste. Screens at 390 (phone) and
1440, saved to review/shots/tue/golook/ and review/shots/tue/report/.

### Go look = a real worker phone app ("Spoor Floor")
- Shown in a phone frame (390x844) on desktop, full screen on a real phone. LIGHT theme for the floor (bright hall,
  glare): white surfaces, near-black text, indigo as the one action colour, evidence colours only for status.
- Big targets (min 48 px), one primary action per screen in a fixed bottom bar, thumb reach, no tiny links.
- Flow, one screen each, with a back arrow and a step indicator (1 of 4):
  1. Tasks: card list. Each card: place (Exception store Z11), why ("Parcel not scanned in, customer waiting 2 weeks"),
     urgency chip, distance/time to walk. Tap -> task.
  2. Task: last-seen camera frame with SAM outline (what to look for), parcel photo from the tunnel reader, size and
     weight, the tracking number big, a small clean map of where to walk (from the real hub plan, route line, you-are-here
     at the supervisor desk). Primary: "Start search".
  3. Search: checklist of places from the answer (first = the answer's place), each with "Look on: shelf / floor /
     cages". Primary: "Scan barcode" (camera view with a scan frame; in the demo a simulated scan that fills the
     number). Secondary: "Not here".
  4. Result: Found (green, number matched, "Bring it to the reject/exception desk" + photo button) or Not here (reason
     picker: checked shelves / store locked / found other parcel) -> Spoor re-plans (show "Spoor is checking the next
     place" and the next task). Primary: "Done".
- Voice: a hold-to-talk mic button on Search and Result (big round, indigo). While held: live waveform + timer; release:
  transcript appears (Muse Voice Transcribe) in an editable box with "Use this note" / "Record again". Works in Malay and
  English; show the detected language chip. Never auto-sends.
- States: loading skeletons, offline banner ("Saved, will send when back online"), success haptic/animation 200 ms.
- No faces anywhere, worker = "You", no staff IDs.

### Report = the case file a hub manager signs (desktop, prints to PDF)
- Header: verdict sentence, status pill (Open / Found / Closed), case number, parcel number, customer waiting time,
  who closed it and when, "Export PDF" and "Draft the update to the customer".
- Section 1 Summary: 3-4 plain sentences + "How sure" in one line.
- Section 2 Journey on camera: EVERY checkpoint as a frame card in time order (use the API's per-step frames signed with
  the reel): frame with SAM outline, time, camera, what happened, chip (Scanned / On camera / Not scanned in / Records
  disagree). Plus the full reel player above it. Rexton noticed the frames were missing: they are the core of the report.
- Section 3 Map: replace the sketch with a clean vector floor plan from hub_spec (walls, zones with names, belts,
  chutes, docks as simple shapes, 1 px lines, muted fills), the parcel's route as one solid line with numbered
  checkpoints matching section 2, dashed where no camera saw it, the answer zone highlighted in indigo, camera icons
  only for cameras used, legend, scale bar, north arrow. Must read when printed in greyscale.
- Section 4 Records vs cameras: small table (record, what the camera shows, verdict) incl. the D07 RFID conflict.
- Section 5 Floor check: the Go look result (who, when, found/not, voice note transcript).
- Section 6 Evidence list: clip, camera, time range, SHA-256 (short + copy), models used and cost, limitations.
- Print/PDF: A4, page breaks between sections, frames stay sharp, no dark backgrounds in print.

### "Draft the update to the customer"
- Opens a side sheet (not a modal over everything). Spark writes the draft ONLY from verified facts; the facts used are
  listed under the draft as chips linked to their evidence (tap -> frame). Nothing unverified can appear.
- Controls: channel (Marketplace chat / Email), language (English / Malay), tone (Short / Detailed). Editable text.
- Before the case is closed (parcel not yet found on the floor): the draft is a holding message ("We located where your
  parcel most likely is and a team member is checking"). After Found: "Found at our hub, re-sent today, new ETA".
- Primary "Approve and send" (a person approves; in the demo it marks as sent, no real message, audit entry with time
  and approver), secondary "Copy text". Show the sent message in the case timeline after.

## 02:58 Tue · reviewer · Agents run page (run2/agents_1440.png): strong, 5 visual fixes

Best Meta-showcase screen so far (In short + lanes + where they looked). Fix before the demo:
1. "In short" line 5 quotes Spark: "Hands/arms and any carried object cannot be seen". On the summary it reads like the
   answer is unsupported. Rewrite in Spoor's words: "1 likely carrier on CAM 19 · hands not visible at this angle, so the
   store-door close-up was checked" (the quote stays in the step detail, not the summary).
2. Page background changes below ~900 px (sidebar and main panel stop, darker strip below). Make the app shell full
   height (min-height: 100dvh on the shell, background on body), check with a full-page screenshot.
3. "Where they looked" map: labels clipped at the left edge ("verage", "rocks") and marker 2 sits on "Bag opening".
   Clip the plan to whole labels or hide labels cut by the frame; offset numbered markers so they never cover a label.
4. Lane colours: Evidence agent, Camera analyst and Hypothesis agent are the same amber, and amber already means
   "inferred" in the evidence colours. Use one colour per MODEL, none of them the evidence colours: Wonder indigo,
   Glimmer teal, Spark Open violet, Spark (hosted) sky, SAM 3.1 pink, rules-only grey. Same map in the legend and chips.
5. Hollow dots ("could not run / not proven") need a legend line under "Pick a dot": "Hollow = could not run or not proven".
Then continue the overnight list (chute C12 + door re-render, real-footage dataset test).

## 02:25 Tue · reviewer · REEL APPROVED (Rexton): stop polishing it

Rexton is happy with the reel as it is now. Cancel all reel fixes from 02:15 and 02:22. Only rebuild the reel if the
chute C12 / door re-render changes its clips. Move on to the next items in his overnight list.

## 02:22 Tue · reviewer · CHANGE (Rexton): cards stay plain dark

Rexton prefers plain dark cards. Cancel fixes 3 and 4 from 02:15: intro, waiting and answer cards use a plain brand
near-black background (#0B0C0F), no CCTV frame behind, no frozen outline. Keep everything else on the cards (logo,
text, six-dot rail). Answer card 2 s. Fixes 1, 2, 5, 6, 7 still stand.

## 02:15 Tue · reviewer · reel redesign v1 (contact_sheet.jpg): good direction, 7 visual fixes

Big step up (font, rail, tag, answer rail). Fix these, then rebuild and re-shoot the contact sheet:
1. Sub-lines unreadable on bright floors (sorter "Too close...", 14:32:13 "The one parcel caged...", CAM_19 "SAM followed...",
   store "Past the scan-in post..."). Make the top scrim taller when a sub-line exists (gradient to ~120 px, 0.85 -> 0),
   sub-line #D1D5DB not mid-grey, plus a soft 1 px text shadow rgba(0,0,0,.6).
2. Chips wash out on bright frames ("Scanned" at unload, "Not scanned in", "Records disagree" barely visible). Put a dark
   base under the tint: fill rgba(10,11,14,0.78) then the 18 % tone tint, text at full tone colour.
3. Cards are still near-black: the blurred camera frame is invisible (intro, waiting, answer). Raise it to ~40-45 %
   brightness, blur 6 px, keep the left-side gradient for the text. A judge should see "this is a CCTV frame".
4. Answer card: the frozen SAM outline at the store door must be visible: it is the whole point of that card. Draw the
   door frame brighter on the right half (where the carrier + carton are) and the outline at full strength.
5. The render's own burned-in timestamp shows through under our time at top-left (CAM_19, CHK_STORE, CHK_DOCK:
   "2026..." ghost behind "14:32:22"). Mask the render OSD's top-left date strip (same dark scrim, solid behind our
   time) or shift our text row so they never overlap.
6. D07 sub-line is too long (runs across the frame). Use: "RFID read the cage's tag, so every parcel in it counts as loaded."
7. Cover-crop clips the render OSD camera name at the left edge on some frames ("HK_STORE", "CHK_TUNNEL" cut). Keep a
   12 px safe margin: crop so the OSD stays whole, or redraw the camera name ourselves when cropped.
Keep: Inter, the rail, the indigo current dot, the small number tag, the tunnel photo card, crossfades.

