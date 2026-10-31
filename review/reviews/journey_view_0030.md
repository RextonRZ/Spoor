# OWNER MUST-HAVE (Rexton 00:21 Sat): the "wow moment" — show exactly which tiny parcel it is, and its movement/path
Frontend work (frontend agent or builder after S2 render). Builds on what exists: Timeline playhead, Scene3D, FloorPlan2D,
SourcePanel (original frame + annotated derivative), camera wall. Every element below must stay honest (PRD rules).

## 1. Follow-cam close-up (the wow) — P0
- When a segment/scan/playhead lands on a frame where the subject is tracked: an inset that crops the ORIGINAL 2688×1520
  frame around the parcel (2–4× of native pixels, bicubic, NO AI upscaling — no invented detail), corner brackets around
  the box, a chip "CTX… · identified by tunnel read 14:32:12 → carrier 47 → divert C12".
- Inset follows the parcel while the playhead plays (smooth pan, ≤ 1 crop jump per camera handoff).
- One click → the full original frame + SHA-256 (already in SourcePanel).

## 2. Journey ribbon on the floor plan + 3D — P0
- The path snaps to where a parcel can physically go (conveyor centrelines, walkways): solid green = seen on camera,
  dotted amber = inferred along a belt between two scans (belt speed × time), grey hatched = gap, never bridged.
- Scan "beads" (diamonds) at each scanner with time + device clock note.
- A glowing marker travels the ribbon in sync with the playhead ("replay the journey"); ▶ plays at 1×/4×/16×.

## 3. Camera relay strip — P1
- A film strip under the timeline: one close-up thumbnail per camera segment (entry and exit crops), arrows between
  them with "+2.1 s · overlap zone", the gap tiles grey with "no camera". Click → source frame.

## 4. "Where it could be" cloud for gaps — P1 (the creative signature)
- In a gap, a shaded region grows from the last confirmed point at walking/belt speed, clipped by every camera cone that
  watched and saw nothing (negative evidence removes area). S2: the cloud flows into Z11; the empty-handed exit and the
  watched doorway collapse it to Z11 → the answer appears visually. Label: "possible area, computed — not an observation".

## 5. Records vs video — P1
- Two lanes: "What the scan records say" vs "What the cameras saw"; they diverge at a red pin ("records disagree here,
  14:32:12"). S2: cage → truck vs → exception store. S3: in the bag vs floor beside C04. S4: D08 vs D09.

## 6. Camera wall sync — P2
- During replay, cameras that see the subject light up, others dim; the active one shows the follow-cam inset.

## Demo choreography (15 s, S2)
Open case → "Show where it was last confirmed" → follow-cam zooms on the tiny box in the cage → ▶ replay: marker leaves
the cage on the ribbon, relay strip fills, enters Z11 (ribbon turns grey) → cloud grows then collapses to Z11 when the
person exits empty-handed → records-vs-video lanes split. Line: "The records say it left on the truck. The cameras say
it is in the exception store."

## Honesty rules
No solid line across a gap; the crop is original pixels; inferred segments always dotted + labelled; no-key mode shows
scans + gaps only, says "tracking needs SAM", never fakes a track; footage labelled SYNTHETIC.

---
## Pass 2 (00:35, Rexton: "3D or what? in a real deployment how does a real hub become 3D?")
A real hub has no Blender model. What it does have: a floor plan (CAD/PDF), its scanner list, and its cameras. Spoor
already works in floor coordinates (backend fit_floor_calibration = per-camera floor homography; trace mode floor_xy).
So the forensic path must stand on the 2D plan; 3D is a view, never a requirement.

Presentation order (what investigators, claims and police actually use):
1. **Case report** (text): the evidence chain, one line per step with its source frame + hash, gaps stated. The legal
   deliverable. (Exists — polish per review 012.)
2. **Timeline + original frames** (proof). (Exists.)
3. **2D floor-plan journey** = the PRIMARY path view: ribbon, beads, gap cloud, follow-cam inset (items 1–5 above live
   here first). Works for any hub from its plan + a 10-minute calibration per camera (click 4+ known floor points).
4. **3D "twin" view = optional**, and it must be honest about where geometry comes from:
   - Demo: the synthetic hub's own model (hub.glb), labelled "synthetic hub model".
   - **Deployment mode (P1, build it):** Scene3D must also render WITHOUT hub.glb, by extruding the site plan JSON
     (walls, zones, conveyors at their deck heights, racks, doors) into simple 2.5D blocks. Add a toggle
     "Plan-built 3D (what a real hub gets)" so judges see it is deployable on day 1.
   - Optional later: a phone LiDAR/photogrammetry scan for sites that want a realistic twin.
5. **Evidence reel (P1, creative + real):** one button exports a short MP4 that stitches the follow-cam crops across
   cameras in time order, with burned-in time, camera ID, source hash and "SYNTHETIC" mark; gaps shown as a grey card
   "no camera 14:32:26 → 14:32:51". Security teams already compile incident clips by hand — this does it from evidence.

Pitch line: "Any hub with a floor plan and its existing cameras gets this on day one; the 3D is built from the plan."

---
## Pass 3 (00:45, Rexton: "a camera moment to trace how it went missing, see where it stops using the camera combination, then 3D trace + where it might go")
Already in: follow-cam (H1), journey ribbon 2D/3D (H2/H6), relay strip (H3), where-it-could-be cloud (H4).
Added: **H10 the missing moment** (last seen frame + the next camera's frame at the predicted time with an empty dashed
box — "expected here, not seen"), **H11 camera combination grid** at the break point with one scrubber, **H12 ranked
"where it might be" + floor search task** with found / not-found buttons that feed back into the case.
Demo story (S2): follow-cam on the box in the cage → relay strip → the missing moment (CAM_19 doorway: carried in;
CAM_01/06 at the predicted time: nothing came out) → 3D/2D cloud collapses into Z11 → ranked list: "1. Exception store
Z11 — go look here" → (later in the demo) "Found it" revises the case.

---
## Design bar for block H (Rexton 01:12: "nice, clear, aesthetic, useful")
- One hero per screen: the follow-cam close-up + the 2D journey; everything else is secondary panels.
- One colour language everywhere (video overlays, map, 3D, timeline, cards): green = observed, amber dotted = inferred,
  grey hatched = gap, red = conflict / no-read, blue = scan bead. Legend always one click away.
- Calm motion: ≤ 300 ms eased transitions, the replay marker glides (no jumps), respects reduced-motion.
- Readable at a glance: 2–3 type sizes, tabular numerals for times, every card answers "what / where / when / how sure".
- Honest by design: every element has a source link; "computed" and "inferred" are labelled in place, not in a footnote.
- The search task view works on a phone (one column, big buttons).
- Proof per item: Playwright screenshots at 1440×900 and 390×844 + a 30 s screen recording; the reviewer checks them
  against this bar before approval.
