# F-044b — Feature map: every existing feature into the 5-screen flow (Hub → Answer → Proof → Go look → Report)

From the frontend agent. Follows the owner's 08:58 approval of `review/refs/flow/`. F-044 has the critique; this file
is the map. The build goes screen by screen, Hub first, with shots at 1440 × 900 and 390 wide.

## App chrome
- **Rexton asked in chat at 08:50 for "the sidebar like Reelism", so I keep a left rail instead of the prototype's
  top bar.** It is already built: a floating panel, the logo alone, Hub · Cases · Cameras, the open case as one
  context row, and a foot with Settings & data (admin), Collapse and the account menu (role switch, model status).
  The prototype's top-bar items still come along: search goes on the Hub and in the rail, and "Synthetic demo hub"
  is said once, under the account.
- In a case: the breadcrumb (Hub › CTX… › step), and the 4 numbered steps **Answer · Proof · Go look · Report** as a
  segmented control top right, also in the rail.
- §J: no "—" in any visible text. A test fails on it (UI strings, report, reel cards).

## 1. Hub
| Today | Goes to |
|---|---|
| Stalled inbox (proof rule, "can't judge") | **The hero list** "N parcels need attention": waybill, one-sentence status, a pill (Stalled N min / Records disagree), one **Open case** for the top row and **Open** for the rest. "Can't judge" rows sit under "Not enough log to judge" (Details). |
| Tracking search | The search field at the top of the Hub (and in the rail) |
| KPI tiles (open / located / median / cost) | 3 small stat tiles: found today, median time to find, open cases. A tile with no data is **hidden**; there are no "—" tiles. Model cost moves to Settings. |
| "Where evidence trails end" plan | A small card, "Where today's trails ended" |
| Cameras the open cases depend on | Cut from the Hub (that's the Cameras page) |
| Records that disagree | Becomes the "Records disagree" pill on its row |
| Rule paragraph | One line under the list: "A parcel shows here when its next scan is late and the next scanner kept working." |

## 2. Answer (today's case summary)
| Today | Goes to |
|---|---|
| Answer headline + sub (answerParts) | Status pill + one sentence (≤ 2 lines) + a 2–3 line plain explanation |
| (new) | **How sure**: high / medium / low, with 3 plain reasons drawn from the typed journey (seen on which camera, what is unobserved, coverage facts). No-key mode says low and why. |
| Key frames 1–4 | One hero CCTV frame (final look) beside the answer. The 4 frames move to Report. |
| Records vs video lanes | A moment in the timeline row ("Records say truck D07. Cameras disagree.") plus full lanes in Proof › Evidence details |
| Route plan | Proof (mini-map) and Report |
| Complaint + complaint call | The breadcrumb carries the complaint ("customer says it never arrived"); the transcript and audio go to Evidence details |
| Reel export | Report › "Evidence video" |
| Buttons | **Watch the proof** (primary), **Send someone to look** (secondary) |
| (new) | Timeline of moments: scans, sightings and the records conflict as 5–6 tiles, with the final state highlighted |

## 3. Proof (today's workspace)
| Today | Goes to |
|---|---|
| Source panel, follow-cam, camera grid, missing moment (4 tabs) | **One hero player** (≥ 60 % width): the frame at the selected moment, the follow-cam box when tracked, §G pin or box, real controls (play, scrub, ±1 frame, 1× / 4×) |
| Camera route strip | **"Every camera on its route, in order"**: tiles marked seen / expected, not seen / no camera / records disagree; a click selects the moment |
| Scan card, missing-moment text | **Side card**: camera · place, a headline, two sentences for the selected moment |
| 2D journey plan | A mini-map in the side card, with the marker gliding with the playhead; a 2D / 3D switch opens the real hub 3D (§H/§I) in the player area |
| Left column (question, scan list, unknown, places) | Cut from the main screen: the answer is on Answer; the scan list and places go to Evidence details |
| Bottom timeline lanes (scans, photo-eyes, cameras) | The player's scrubber carries the moments; full lanes go to Evidence details |
| Agent panel, lead plan, model traces | Evidence details › "How Spoor worked it out" (keyed runs only; one calm line in no-key mode) |
| Hashes, clocks, SHA-256, media ids, frame numbers | Evidence details only |
| Primary | **Go look: {place}** |

## 4. Go look (phone, today's floor search)
| Today | Goes to |
|---|---|
| Places checklist | **One task at a time**: "Check the exception store", how to get in, the CCTV frame, "Look for" (size, label, waybill tail from the parcel's identifiers) |
| Found here / Not here | **Not here** / **Found it** (big). Not here moves to the next place. |
| Voice note | "Hold to add a voice note", labelled "statement by floor staff" (F-042 P2) |

## 5. Report
| Today | Goes to |
|---|---|
| Report page (claims document, approve flow) | The top half is plain: the answer, 4 key frames with captions, **What to fix** (only when a records conflict exists), **For the customer**, then Download PDF · Evidence video · Send for approval. The full formal document (tables, hashes, Malaysian context, legal notes) stays as "Full report" behind those buttons. |
| Evidence graph | Linked from Full report ("How the evidence connects") |
| Legal context (J3) | Inside Full report only |

## Settings & data (admin, from the rail foot)
Today's Operator, regrouped: **Data sources** (drop zones, later; the forms stay until then), Cameras & clocks,
Model calls (incl. Malaysian context), Evaluation, Inbox clock. Not in the video.

## Cameras
The camera wall becomes a calm grid of final-look feeds, with the case's cameras first. No chips.

## Cut outright
Hub "Cameras the open cases depend on" tile; per-panel synthetic chips (done); eyebrows (as each screen is rebuilt);
the native role select (done); "Show last confirmed" (replaced by the step flow).

## No-key honesty
Every screen renders from the typed journey. Until the keyed S2 run, the demo case says what is really known
("Lost track after 14:32:31", "How sure: low"). The prototype's S2 story (cage RC-864, CAM 13/19, D07) appears only
when those records exist. Frames: final look only (CAM_19 proof frames for the S2 case until S2 renders); the
Thursday QA clips aren't used for §G tiles.

## Already done today (for this flow)
Reelism-style rail; one synthetic mention; §G pin before analysis; §H/§I real hub first with plan orientation,
compass, landmarks, trail-framed home and tighter orbit; logo SVG rebuilt closer to the final PNG
(`frontend/review_pack/design_sprint/logo_proof.png`).

## Questions
- None. Starting the Hub now.
