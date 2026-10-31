# OWNER PRIORITY (Rexton 09:15 Sat): show HOW the agent works — Agentic bonus ($5K: autonomy, effectiveness,
# practical usefulness) + Meta tooling (25 %). Frontend + backend. Prototype: review/refs/flow/Investigate.dc.html

Rexton's previous win (Rexgent) won partly because judges could SEE the crew work: each stage expanded into its
real tools with ✓, dashed optional tools, a timestamped log, a cost meter that never stopped, self-correction from
a judge, and a "prove the spend" page. Spoor must make its agent equally visible — in Spoor's own look (don't copy
Rexgent's layout), and in an investigator's language.

## The Investigating screen (between Hub and Answer; opened by "Investigate")
1. **Search map** (Spoor's signature): columns Last scan → Into the cages → Out of the cage → Ways out; one node per
   camera/place. States: not chosen (faint) · picked by the lead · checking (indigo) · seen (green) · ruled out
   (struck, "not seen, clear view" / "not on this route") · rejected (red, struck, reason) · records disagree (red
   dashed). Driven by the real agent run (typed events), never scripted text in the UI.
2. **The investigation crew** with real tool names, ✓ when done, dashed = only when needed:
   Lead investigator · Muse Wonder (read_scans, plan, pick_cameras, re_plan) · On-site triage · Muse Glimmer on
   Modal (triage_clips) · Camera analysts · Muse Spark, parallel (observe_clip) · Tracker · SAM 3.1 (sam_track) ·
   Verifier · rules, no AI (verify, reject) · Reporter · Muse Spark Open on Baseten (create_search_task,
   draft_report, ask_a_person — dashed).
3. **Timestamped log** in plain words (who · what · result).
4. **Live meter**: US$ spent · cameras checked of 19 · seconds. Each tool chip opens its real call (input, output,
   latency, cost, source frame hash) in a drawer — "receipts".
5. **Visible self-correction**: the verifier REJECTS at least one candidate in the demo run with a reason
   ("would have moved 9 m in 1.1 s"), and the lead re-plans to another camera. Backend: make sure the S2 run really
   produces a look-alike candidate (S2 has look-alike parcels; if not, the builder can place one) and that the
   rejection + re-plan are typed AgentSteps, not text.
6. **Human only when needed**: ask_a_person runs only if ≥ 2 places remain; otherwise skipped (shown dashed).
7. **End line**: "Took 41 s and US$0.29. By hand: about 2 to 4 hours of watching 19 cameras." Numbers from the
   real run + a stated assumption for the manual baseline (cite it in docs).

## After the run
- Answer screen: a "How Spoor found it" fold = the same search map, frozen, with the receipts.
- **Proof of spend** (Settings › Models, linked from the Report): per Meta model — job, calls, tokens/frames, cost;
  share of reasoning on open weights (Spark Open); "Glimmer kept N % of raw video on-site". This doubles as the
  Meta-tooling and Open-Weights evidence.

## Optional if time: Spoor's tools as an MCP server
Expose investigate_parcel / get_journey / missing_moment as MCP tools (same registry as the API) so any agent can
call Spoor. One line in the README; only if it is < 2 h of work.

Order for the frontend: rebuild Hub → **Investigating** (this spec) → Answer → Proof → Go look → Report → Cameras.
