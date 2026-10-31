# OWNER 01:52 Sat: keys are in backend/.env (checked: MODEL_API_KEY set, BASETEN_API_KEY set,
# BASETEN_MODEL_ID=meta-models/muse-spark-open-1026, AGENT_BACKEND=baseten, file gitignored)

Frontend agent — start J1 now (it unblocks the Meta score):
1. Restart the backend so it loads .env. GET /v1/capabilities must show sam, spark, agents = true.
2. Smoke tests (fill the table in docs/META_MODEL_USAGE.md): SAM 3.1 on one rendered clip (box prompt at a scan point),
   Muse Spark 1.3 one clip question with structured output, Muse Wonder 1.0 one planning call, Baseten Muse Spark Open one
   chat call (reasoning split from answer). Record latency, tokens/frames, cost. Print the estimate BEFORE each call.
3. Budget for J1: ≤ US$3 total on Meta, ≤ US$1 on Baseten. Never print, log or copy a key; redact headers in any saved
   request/response (docs/open_weights_proof/).
4. Then run the default case once with keys vs no-key and send screenshots + the eval comparison as a request.

## Update 01:58 (Rexton): bigger budgets — use the credits properly
Totals until submission (Nov 4), across both agents, logged per run in review/log.md (estimate before, actual after):
- **Meta Model API: up to US$100 of the $150** (keep $50 for the final demo recording, re-runs and the judges' week).
  J1 smoke tests may use up to $10. Full SAM passes on S2/S0 (≈ $1.3 each) are fine whenever useful.
- **Baseten: up to US$70 of the $100** (keep $30 reserve). Per-token endpoint only; never a dedicated deployment.
- **Modal: $30** unchanged — render test ≤ $2, Glimmer test ≤ $3, full batch only with Rexton's go.
Any single run estimated > $10 still needs Rexton's OK. Keep a running total line in FOR_REXTON.md.

## Update 02:00 (Rexton wants more reserve) — FINAL caps until Rexton changes them
- Meta: **≤ US$60** (reserve $90). Baseten: **≤ US$50** (reserve $50). Modal unchanged.
- Expected real need: Meta ≈ $30–50 (≈ 20 SAM passes ≈ $26 + ≈ 30 Wonder/Spark runs ≈ $1 each), Baseten ≈ $10–30.
- Single run > $10 → ask Rexton. At 75 % of a cap, stop paid experiments and write it in FOR_REXTON.md.
