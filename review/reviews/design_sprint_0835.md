# OWNER (Rexton, 08:28 Sat): "frontend still very AI and ugly" — DESIGN SPRINT. Frontend agent: STOP new features.

Rexton's words: arrangement looks AI-made; no CCTV feel; opening the app shows "nothing at all"; too many
"synthetic test" warnings; he asked whether the 4 skills (rexton-ui, emil-design-eng, design-taste, impeccable) were
really used. Reviewer agrees: my reviews checked honesty and function and were too soft on visual design.

## Allowed work until Rexton approves the new look
Only: (a) this sprint, (b) the J6 Glimmer run already approved, (c) the final logo swap. Nothing else new.

## Step 1 — written critique BEFORE code (send as F-044, no code changes)
- Open each of the 4 skills again and quote the 3–5 rules from each that the current hub / journey / summary
  screens break most, with a screenshot crop per rule. Be harsh. Also read Reelism's DESIGN.md again and name what
  makes Reelism's home dashboard feel premium (hierarchy, scale, whitespace, motion, imagery) — in your own words.

## Step 2 — fixed rules for the 3 screens (hub home, case journey, case summary)
1. **One hero per screen.** Journey = the CCTV player, big (≥ 60 % of the width at 1440). Summary = the answer
   sentence + one key frame. Hub = the stalled-parcel inbox + search.
2. **CCTV must look like CCTV.** Show only final-look frames (builder's cctv_look output: lens, sensor noise,
   H.265, burned-in OSD with date/time and camera name). Never the raw white QA renders. Until S2 renders, use the
   CAM_19 final-look frames in `qa/review/s2_hub/cctv_proof/cctv/` (+ `raw/`) for the S2 case.
3. **One synthetic label.** A single quiet "Synthetic demo hub" chip in the top bar + the SYNTHETIC burned into the
   footage. Remove the per-panel "synthetic test / simulated" chips. Honesty stays in the data (records still carry
   source_kind), not as visual noise.
4. **Fewer, bigger things.** Max ~3 panels visible per screen; max 2 lines of grey helper text per panel; move the
   rest behind "Details". Numbers and times large and tabular.
5. **Never look empty.** The demo opens on the S2 case with real frames, real scans, the camera strip, the plan.
   No-key states are one calm sentence + a button, not a wall of "not analysed yet".
6. **Brand:** final fingerprint-box logo, indigo accent only for actions/selection, evidence colours only for evidence.
7. **Motion:** subtle, purposeful (playhead, marker glide, panel fade ≤ 200 ms). No ambient motion.
- A reviewer reference mockup of the journey screen follows in `review/refs/journey_reference.png` (built from the
  real CAM_19 frames). Match its hierarchy and density, not its pixels.

## Step 3 — show 2 layout options for the journey screen as screenshots (F-045), Rexton picks, then build.

## UPDATE 08:31 — Rexton: "the problem is not the colour, it's the DESIGN": controls (dropdowns, buttons),
## arrangement, use of words, how the user navigates and sees. This section outranks everything above.

### A. Who and what flow (design for this, in this order)
User = hub supervisor / investigator, not an engineer. The demo flow is 5 steps:
1. **Hub** — "3 parcels stalled" → click one (or search a tracking number).
2. **Case — the answer first**: one sentence ("Carried into the exception store at 14:32:38"), how sure, and one
   primary action ("Watch the proof").
3. **The proof**: the CCTV moment (hero player) + camera strip in route order (seen / expected-not-seen / no camera).
4. **Go look**: the search task on a phone ("Check the exception store shelf 3") → "Found it".
5. **Close / share**: the summary page / evidence reel.
Every screen must make the next step obvious with ONE primary button. Write the flow as a storyboard (5 frames,
one sentence each) in F-044 before redesigning.

### B. Navigation
- Main nav: **Hub · Cases · Cameras** only. Operator / imports / evaluation / model calls → one "Settings & data"
  entry at the bottom, admin only. The "Signed in as" role dropdown is a dev tool: hide it behind the avatar menu.
- In a case: a breadcrumb "Hub › CTX… › Proof", a back button, and steps/tabs named by the user's question
  ("Answer · Proof · Where to look · Report"), not by our internals ("Source · Missing moment · Agent").

### C. Controls (components)
- No raw browser controls anywhere: no native `<select>`, no "Choose File" buttons, no default date pickers.
  Use designed menus, segmented controls, drop zones.
- One button system: primary (one per screen), secondary, quiet/text. Same heights, same radius, same icon spacing.
  Destructive / paid actions show the cost inside the button and confirm once.
- Tabs vs segmented controls vs filters used consistently; selected state obvious.
- Player controls like a real video player (play, scrub, ±1 frame, speed), not a row of generic buttons.

### D. Words (copy)
- Plain supervisor language, short. Answer first, detail behind "Evidence details".
- Remove from the main screens (keep only in Evidence details / Settings): "master (original)", "Master SHA-256",
  "media_…", "hypothesis", "SAM 3.1 via MODEL_API_KEY", "clkd_…", "case 1ffadda5", "scan_simulated",
  "observation", "verifier", device-clock jargon.
- Examples: "Last confirmed at chute C04 · 14:32:31" ✓; "Should have appeared on CAM 10 by 14:32:34 — didn't" ✓;
  "Go check: exception store" ✓; "Unknown since 14:32:31.8 MYT: no scan and no sighting after it" → "Lost track after
  14:32:31" ✓.
- Sentence case everywhere; no ALL-CAPS labels except tiny section eyebrows (max one per panel).

### E. How the user sees (layout)
- Inverted pyramid: answer → proof → details. Left-to-right reading: question/answer left, proof centre, map/aside.
- Progressive disclosure: hashes, clocks, model calls, costs → "Evidence details" drawer.
- Every empty state = one sentence + one button.

### F. Operator import page (Rexton 08:33: "this one is useless")
- For users and judges it is: three long engineer forms (clip import, scan log, sensor CSV) with native controls and
  paragraphs of jargon. The demo is seeded by script, so nobody needs it on screen.
- Keep the function; redesign it as **Settings › Data sources**, admin only:
  - one **"Add footage"** drop zone: drag clips in, Spoor guesses the camera from the file name / OSD, the user
    confirms in a list (camera, start time read from the OSD, status). Clock check, footage kind and rights go into
    an "Advanced" fold with sensible defaults;
  - one **"Connect scan log"** card (file drop or "connected to WMS" mock state) with a row count and time range;
  - sensor CSV import → "Advanced" only.
- Not in the video. At most a 3-second drag-and-drop shot in the deployment beat.

### G. The "expected here" box (Rexton 08:49: "why is the box circling air?")
- Today the summary/missing-moment frames draw a dashed box on a spot where nothing is, with no clear reason. To a
  user that reads as a broken detector.
- Rule: **before analysis, don't draw a box on the frame.** Mark the place with a named pin ("Chute C04 · parcel
  should pass here at 14:32:31–34") and the camera status "not checked yet".
- **After analysis:** red dashed box + "Not seen here between 14:32:31 and 14:32:34" (a typed negative), or green
  brackets + "Seen at 14:32:33" on the actual parcel.
- And only on footage that matches the scan log in time (the S2 render). The Thursday QA clips don't contain the
  scanned parcel at that moment, so any box on them points at air — don't use them for this tile.

### H. 3D view: "I can't even tell the direction" (Rexton 08:53)
- Open in the **same orientation as the 2D plan** (north away from the viewer, inbound docks on the left/west,
  outbound docks at the back/north), as a calm 3/4 view framed on the parcel's trail, not a random orbit.
- Always-visible **compass** (N arrow) in a corner, turning with the camera; a **"Reset view"** button; orbit limited
  (no going under the floor, no flipping); zoom limited to the building.
- **Landmark labels** that stay readable: "Inbound docks 01–06", "Outbound docks 07–12", "Sorter", "Chutes",
  "Cage staging", "Exception store", plus the trail's start and end ("Scanned 14:32:07", "Last seen 14:32:38").
- When the user picks a camera or a moment, **fly** the view there (≤ 600 ms) and show that camera's cone.
- A 2D mini-map in a corner with a "you are looking here" wedge.

### I. 3D = the real Blender hub, Google-Earth style (Rexton 08:55)
- Rexton expects the 3D tab to show **the hub the builder made in Blender** (`frontend/public/hub.glb`, textured,
  realistic), navigated like Google Maps 3D: smooth orbit/zoom, tilted bird's-eye default, buildings readable.
- So: **default = "Real hub" (hub.glb)**; the extruded "Plan-built 3D" stays as a secondary switch labelled
  "What a hub gets on day one (from the floor plan)".
- On top of the real model: the trail (same evidence styles), camera cones for cameras in play, landmark labels,
  compass + reset (§H), fly-to on camera/moment pick. People never shown except the anonymous "Person A" marker in a
  case replay (owner_ideas_0303 §4).
- Performance: poster image while loading; keep it smooth on a laptop (the builder's hub.glb clean-up comes after the
  S2 render — owner_ideas_0303 §1; use the current hub.glb meanwhile).

### J. No em dashes in UI copy (Rexton 08:59)
- Rexton: the long dash "—" reads as AI-written. **No "—" anywhere in the app's visible text** (UI, report, reel cards,
  README headings shown in the app). Use a full stop, a colon or a middle dot "·" instead. Ranges keep the short
  en dash only where it is a range ("C01–C06", "14:32:31–34").
- Add a lint/test that fails on "—" in user-visible strings.
