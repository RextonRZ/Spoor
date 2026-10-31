# F-044 — Design sprint step 1: written critique, storyboard, nav/controls/words (no code)

From the frontend agent. Screens judged: hub home, case journey, case summary, Operator, at 1440 × 900, dark theme.
Crops are in `frontend/review_pack/design_sprint/` (c01–c10) and the full screens are `now_*.png`.

## 0. The verdict in one paragraph
The screens were built to be **honest and complete**, and they show it: every fact, caveat, hash and "not analysed"
is on the main surface at the same weight. That turns three different jobs (answer, proof, audit) into one wall of
small grey text in equal boxes. There is no hero, no next step, and no CCTV. The one piece of real footage on the
journey screen is a 470-px **raw white QA render** next to two hash rows (c04), while the final CCTV look exists
(`qa/review/s2_hub/cctv_proof/cctv/0249.png`: burned-in date/time, camera name, lens, SYNTHETIC in the frame).
Rexton is right: it reads like an engineer's inspection console made by an AI, not a supervisor's tool.

## 1. Rules from the 4 skills that the screens break most (harsh)

### rexton-ui
1. **"Every metric visible on screen must answer 'why' one click deep at most"**, the inverse of what we do: we
   show the "why" (rules, hashes, clocks) *at depth zero*. c01: the hub's empty state is three lines of rule text
   ("stalled = the next expected scan is overdue and…"). c04: `Master SHA-256 9f0f12a05…` under the player.
2. **"Work surfaces … zero decoration that isn't data"** plus **"A dashboard for judges/planners is a WORK surface with
   ONE showcase moment."** We have no showcase moment. The hub's moment should be the stalled parcel. Instead it is
   four KPI tiles reading 1 / 0 / — / US$0 (c02).
3. **"KPI/stat tiles: micro-label on top, big tabular number…"** We copied the tile but not the point: three of the
   four tiles are empty ("—", "0", "US$0"). An empty KPI row is worse than none.
4. **"Empty/null states: write the real sentence … never a dash"**: c02 "MEDIAN TIME TO LOCATE —"; c10 "Where it is"
   and "Found" are two large hatched boxes saying "Not located" / "Not found yet". Half the summary's hero row is
   empty placeholders.
5. **"Plain owner words on screen … No audit or system-status text"**: c05/c07 "scanner clock, not synchronized",
   "SP-INDUCT · device time", "69 in range · simulated", "tracking needs SAM", "master (original)".

### emil-design-eng
1. **"Unseen details compound."** The details users *do* see are untuned:
   - c06: the player is three generic buttons ("▶ Play", "◀ frame", "frame ▶") with the frame counter as body text;
   - the timeline transport is a separate second player (c07: ▶, 1× 4× 16×, its own clock);
   - two transports for one video is the opposite of "functions exactly as someone assumes".
2. **"Never animate keyboard-initiated actions / should this animate at all?"**: we pass on motion. The failure is
   the inverse: nothing has **spatial continuity**. Clicking a scan bead, a chip or a camera tile changes three
   panels at once with no sign of what drove what.
3. **"Buttons must feel responsive"**, which we do. But we have at least five button looks:
   - indigo primary (Show last confirmed);
   - outline (Play);
   - segmented (1× 4× 16×);
   - pill tabs (Source / Cameras);
   - the native select (c03) and native "Choose File" (c09).
   One system, not five.

### design-taste
1. **"One accent color, locked … Cards are the lazy answer: use only when elevation communicates real hierarchy …
   Nested cards are always wrong."** The journey (c08) has 3 columns × 4–6 bordered cards. The CCTV frame is a card
   inside the Source card inside the hero panel: **nested cards**. Every block has the same border, radius and
   weight, so nothing is primary.
2. **Anti-slop: "Tiny uppercase tracked eyebrow above every section"** (c01, c04, c05, c07, c09):
   - "CONTOH EXPRESS KLANG VALLEY HUB (FICTIONAL)", "QUESTION", "LAST CONFIRMED", "SCAN HISTORY · 3 SCANS",
     "UNKNOWN", "WHERE IT MIGHT BE · computed";
   - "FLOOR PLAN · SYNTHETIC HUB", "TIMELINE · MYT", "OPERATOR · SHOWCASE CONTROLS", "MODEL-BACKED STEPS";
   - the 4 KPI micro-labels on top of all that.
   The skill calls this "the saturated AI scaffold". It is our main grammar.
3. **"The middle-dot (·) is rationed. Maximum 1 per line."** c05: "sorter divert confirmation · scanner clock, not
   synchronized"; c07: "scans · visibility", "69 in range · simulated"; summary: "CAM_07 · expected 14:32:30.8–14:32:36.9
   MYT · not analysed yet". Three or four dots per line, everywhere.
4. **"Hierarchy through scale + weight contrast (≥1.25 ratio) … Cap body line length at 65-75ch."** Journey left
   column: a 26-px question, then about 25 lines of 13-px grey (c05). Hub: the rule paragraph runs 1,100 px wide
   (c01). Summary: fine scale, but the grey sub-copy under every frame is the same size as the facts.
5. **"Copy: Every word earns its place."** Count of the word "synthetic/simulated/fictional" on the journey screen:
   **7** (sidebar brand line, frame burn-in, plan eyebrow, legend chip, "simulated" ×2 in timeline lanes, OSD). On
   the summary: 3 more, including a yellow chip next to the status (c10).

### impeccable (craft floor + operate)
1. **Refuse list: "A kicker or eyebrow above a heading. This one is a ban, not a default: no brief earns it back."**
   This is the same as design-taste #2, and it is our signature.
2. **Refuse list: "The hero-metric template: big number, small label, supporting stats."** That is exactly the hub's
   "Hub dashboard" row (c02), and empty at that.
3. **"Browser surfaces: the parts you did not draw still carry the design."** c03: the native `<select>` for the
   role ("Signed in as Investigator"). c09: native "Choose File / No file chosen", native radio buttons, native
   `<select>` for camera and case. The Operator page is three default HTML forms.
4. **Operate: "Inconsistent component vocabulary across screens … Empty states that teach the interface, not
   'nothing here.'"**
   - Inconsistent: the hub search is an input + indigo "Find"; the journey has an indigo full-width "Show last
     confirmed"; the summary has none.
   - The empty states narrate internals ("needs analysed footage or a floor search") instead of offering the one
     action.
5. **"Coverage: every brief requirement present and findable within seconds."** Rexton's requirement is "watch the
   proof". From the hub it takes: Find → workspace → understand four tabs → find the frame. There is no path named
   for his question.

## 2. What makes Reelism's home feel premium (my words, from its DESIGN.md + screens)
- **One idea per viewport, with real air.** Sections sit 96–180 px apart; Spoor's panels sit 10–16 px apart.
  Reelism trusts space to do the grouping. Spoor uses a border for every group.
- **One stage that holds the next step.** Its "business stage" is one card with the page's one next step, and its
  frame is the only one with the doubled indigo shadow. Spoor has no stage: every panel wears the same frame.
- **The product's output is the hero, shown as the real thing.** Every reel is a real 9:16 frame with a reel shadow
  and slight perspective. Our output is CCTV, so the CCTV frame has to be the stage, shown big, in its final look.
- **Few type steps, big jumps, one family.** Display 46–88 px, title 20 px, body 18 px, labels 13 px. **No eyebrows**:
  "Section heads carry no eyebrow or kicker label; a section head is a headline plus a lede." Spoor runs about 9
  sizes between 10 and 26 px, plus an eyebrow on almost every block.
- **Tabular truth.** Prices and times are big tabular numerals (26 px/700). Our times are 13-px inline text inside
  sentences.
- **Colour only as state.** The gradient appears only where something moves, is checked or is chosen. We do this
  with evidence colours already; it's the one part that works.
- **Buttons: few, tall, confident.** 54 px tall, 15 px radius, one primary per region, named for the product action
  ("Start your Brand Brain"). Ours are 32–40 px and named for internals ("Show last confirmed").

## 3. The flow as a storyboard (5 frames, one sentence each)
1. **Hub:** "2 parcels stalled since this morning". The supervisor sees one stalled card with its tracking number,
   where it stopped and the CCTV still at that moment, and clicks **Open case**. Search by tracking number sits
   above it.
2. **Answer:** a big sentence, "Last seen at chute C04 · 14:32:31. Should have reached CAM 10 by 14:32:34, and
   didn't", with how sure we are in plain words and one primary button, **Watch the proof**.
3. **Proof:** the CCTV player fills about 60 % of the screen in final look, with real player controls (play, scrub,
   ±1 frame, speed). The route strip below it lists cameras in route order (seen / expected, not seen / no camera),
   and the small plan sits at the side with the marker gliding. The next button is **Where to look**.
4. **Where to look:** on a phone, "Go check: exception store, shelf 3" first, then two more places in walking order.
   Big **Found it** / **Not here** buttons, an optional voice note. Found → the case turns green.
5. **Close and share:** the summary page, with the answer sentence, one key frame, the evidence reel button and the
   report. Hashes, clocks and model calls sit behind **Evidence details**.

## 4. Navigation, controls, words: what changes (for F-045 and the build)
- **Nav:** Hub · Cases · Cameras. "Settings & data" at the bottom, admin only: today's Operator becomes Data sources
  (drop zone), Cameras & clocks, Model calls, Evaluation. The role switcher moves into the avatar menu (dev tool).
- **In a case:** a breadcrumb "Hub › CTX…7857 › Proof" and a back button. Steps are named by the question, **Answer ·
  Proof · Where to look · Report**, replacing Source / Cameras / Missing moment / Agent.
- **Controls:**
  - one button system: primary (one per screen, 44 px), secondary, quiet;
  - paid actions carry the cost in the label and confirm once;
  - one video transport, with the timeline as its scrubber;
  - designed menus instead of native selects, a drop zone instead of "Choose File", segmented controls only for
    view switches.
- **Words:**
  - answer first ("Lost track after 14:32:31", "Go check: exception store");
  - nothing on the main screens from Rexton's banned list (master, SHA-256, media_, hypothesis, SAM via
    MODEL_API_KEY, clkd_, case 1ffadda5, scan_simulated, observation, verifier, device-clock jargon), all of it
    behind **Evidence details**;
  - **at most one** dot per line, sentence case, no eyebrows (one tiny section label per panel at most);
  - one quiet "Synthetic demo hub" chip in the top bar, plus the SYNTHETIC burned into the footage. Every
    per-panel chip goes.
- **CCTV:** only final-look frames. Until S2 renders, the S2 case uses the CAM_19 final-look frames from
  `qa/review/s2_hub/cctv_proof/`. White QA renders never appear in the product again.
- **Never empty:** the demo opens on the S2 case. No-key states become one calm sentence and one button, with no
  walls of "not analysed".

## 5. Next
- F-045: two layout options for the journey screen as screenshots, built as throwaway branches of the page, not
  shipped:
  - **A**, player-centred: a 60 % player with the strip under it and the plan plus answer in a right rail;
  - **B**, answer-left: an answer column, the player centre, and the plan as a collapsible aside.
  Both use CAM_19 final-look frames. I'll match the reference mockup's hierarchy if
  `review/refs/journey_reference.png` arrives first.
- Allowed meanwhile: the J6 Glimmer run (the weight download is running on Modal now) and the final logo swap.

## Questions
- None. If you'd rather I build only one layout option to save time, say so.
