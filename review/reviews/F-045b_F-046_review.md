# F-045b + F-046 review (10:05 Sat)

## F-045b Hub — APPROVED
Side-by-side matches Main.dc.html: top bar, widths, rows, mini trail, Investigate buttons, filters, stats, plan card,
footer line, one user. Real data differences (2 parcels, plan-pin thumbnails until S2 frames exist) are honest. Good.

## F-046 Investigating — APPROVED WITH FIXES
Right architecture: typed run steps (POST/GET /v1/cases/{id}/run), search map, crew, log and meter all from real
AgentSteps; no-key mode honest. Fixes:
1. **Unavailable tools are struck through** (plan, triage_clips, observe_clip, sam_track): strike-through reads as
   "done/removed". Use the prototype's states only: ✓ done (green), running (indigo), not run (quiet grey), dashed =
   only when needed. Unavailable = quiet grey + the reason in the tooltip.
2. **Hero panel** shows "[Asking a person: no picture for this step]". When a step has no frame, keep the last real
   frame or show the plan crop with the place pinned (as on the Hub). Never a step name in brackets.
3. **Plain words in the log**, no "model key"/"isn't configured": e.g. "The AI planner isn't connected in this
   demo mode, so the plan comes from the floor plan and belt routes." One sentence, once, not on every line.
4. **The real demo run must use the keys.** backend/.env has MODEL_API_KEY and BASETEN keys: the demo store should
   run on `npm run backend:keys` once S2 footage is imported, so Wonder/Spark/SAM steps are real (estimate before /
   actual after, caps in keys_in_0152). Until the S2 render lands, keep building screens in no-key mode.
5. Mobile: check the search map stacks as one column with the crew below (send the 390 shot in the next request).
Next: Answer → Proof → Go look → Report → Cameras (side-by-side each).
