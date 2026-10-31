# Prize strategy (Rexton 01:28 Sat 31 Oct: aiming for the track win + the bonus prizes; global field → must be super solid)

| Prize | What it rewards | What Spoor must show (owner of the work) |
|---|---|---|
| Track winner (Indie) | Judging rubric (paste pending from Rexton) — judges watch the video demo | Flawless S2 demo: missing moment, honest gaps, measured eval scores |
| **Best Build on Meta Open Weights** ($10K) | Muse Glimmer or Muse Spark Open on own hardware or partner inference; the infra partner VERIFIES it runs on an eligible open-weight model | Make open weights LOAD-BEARING, not optional: agents default to Muse Spark Open on Baseten (partner inference); Muse Glimmer on Modal does on-site camera triage. Keep verifiable proof: endpoint/model IDs, request logs, a short screen capture of the run, a "Runs on open weights" section in the README |
| **Best Agentic Use-Case** ($5K) | Autonomy, effectiveness, practical usefulness | Muse Wonder lead investigator → Spark/Spark Open camera analysts → deterministic verifier → it CHOOSES the next camera/time window itself, requests the clip, re-runs and revises; search task + "found it" closes the loop. Effectiveness = eval table (last-seen correct, correct abstention, false "left the hub" = 0) |
| **Best Creative Build** ($5K) | Original creative build with Muse Image or Muse Wonder | Muse Wonder as the lead investigator (planning + sub-agents) is the qualifying use; the "where it could be" cloud collapsing from negative evidence is the original idea to spotlight |
| **Most Viral** ($20K) | Most likes/reposts/comments on the X demo post by Nov 8 11:59 PM ET | 30–45 s vertical cut: hook in 2 s ("Your parcel 'left on the truck'. The cameras say otherwise."), the missing moment, the cloud collapsing, the found-it. Post at US morning ET; Malaysian angle; tag Meta; rally networks |
| **Community Vote** ($10K) | Most votes in the public gallery, announced Nov 16 | Strong gallery thumbnail + title + 60 s video; share the vote link widely (one vote per verified account) |

Implications for the work queue:
1. S2 render + journey must-haves (H1, H2, H10) stay first — every prize depends on the demo.
2. J2 (Wonder lead) and open-weights default move up: AGENT_BACKEND=baseten (Muse Spark Open) as the default path, Meta
   Model API Spark as fallback; J6 Glimmer on Modal is no longer a stretch — it is the open-weights bonus.
3. Keep a verification folder `docs/open_weights_proof/` (model IDs, provider, timestamps, sample request/response with
   secrets removed, cost) for the infra partner.
4. Demo assets: 3-min judged video, 30–45 s X cut, gallery thumbnail — after S2 renders.

## Official rubric (Stage Two, 0–10 each; Stage Three = top 5 per track, judges watch the VIDEO live, same rubric)
Stage One pass/fail: fits a theme + reasonably uses Meta Model API and/or Meta open-weight models.
Track: Indie Developer (1st $150K … 5th $25K) unless Rexton says Startups.

| Category | Weight | Spoor today (honest) | What lifts it to 9–10 |
|---|---|---|---|
| Impact | 30 % | Real, costly problem (lost/disputed parcels, COD, claims, regulator fines); clear users (hub ops, claims, customers). Weak: all footage synthetic; problem-statement fit not yet checked | State the problem statement it fits; quantify the pain (claims per hub, minutes per investigation today vs with Spoor); day-1 deployment story (existing CCTV + scan logs + floor plan + 10-min calibration, on-site Glimmer for privacy); 1 quote from a real logistics person if possible |
| Use of Meta AI tooling | 25 % | Planned breadth is strong (Wonder, Spark, SAM, Spark Open, Glimmer, Voice, search grounding, Image). Weak: none run with a real key yet | Depth over breadth — 3 "surprises": (1) SAM "expected but NOT seen" as negative evidence, (2) Wonder lead delegating per-camera Spark analysts and choosing the next evidence itself, (3) Glimmer on-site triage so raw CCTV never leaves the hub. Show cost per case |
| Technical depth & execution | 20 % | Strong foundations: calibration, clock drift, deterministic verifier, hashes, eval harness with synthetic ground truth | Architecture diagram, clean README, tests green, eval table in the video |
| Demo | 25 % | Depends on the S2 render + journey screens — not done yet | S2 renders clean; the 3-min video shows the missing moment in the first 30 s; works live end-to-end with keys |

Biggest risks: (1) S2 render + H screens by Nov 3; (2) keys not in yet → Meta usage unproven; (3) problem-statement fit
unchecked; (4) "synthetic only" doubt → answer with the deployment story + real input formats.
