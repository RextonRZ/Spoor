# Step 08 — Multi-agent investigation (M6)

**PRD:** §17, §32.3 · **Depends on:** 05, 06, 07 · **Package:** `packages/agents`

## Goal

"Where is the blue case? Did it leave the room?" → a bounded, logged investigation that searches evidence, forms
competing hypotheses, gets them verified, asks for more evidence when it would discriminate, and either answers with
sources or abstains.

## Build

1. **Orchestrator:** simple durable loop first (🧭 LangGraph only if it earns its keep — decide in `DECISIONS.md`).
   Checkpoint after every tool result; idempotent tool calls.
2. **Roles** (§17.1): Lead, Evidence, Hypothesis, Verifier. Perception, geometry, hashing and DB are **tools**, not
   agents.
3. **Typed tools:** `last_confirmed`, `transitions`, `unobserved_intervals`, `get_spatial_estimates`,
   `explain_spatial_basis`, `run_sam(clip, prompt)`, `ask_spark(clip_window, question)`, `get_frame`,
   `request_clip(camera, interval)`, `verify_claim`.
4. **Protocol** (§17.2): every request has `case_id, request_id, role, question, evidence_scope, available_tools,
   token_budget, max_steps, deadline, output_schema`; orchestrator rejects out-of-scope tool args.
5. **Model routing:** clip interpretation → Muse Spark 1.3 (Meta); planning/hypotheses → Muse Spark Open (Baseten)
   only if step-00 benchmark passes, else Meta Spark.
6. **Stopping:** max steps/spend per case; a revision must add evidence or resolve a contradiction, else stop and
   abstain (§17.5).
7. **Causal log:** question → delegated task → observation → hypothesis → verification → output, persisted.
8. **New evidence import:** adding a clip/sensor log re-runs affected hypotheses, keeps prior history (§5.2 step 7).

## Done when

- On a staged case: produces a supported last-seen finding with resolvable citations, or `unresolved` with the
  specific evidence needed. Ground truth never visible to the agents 🔒.
- Budget caps enforced in a test with a mocked expensive tool.

## Status — code done (2026-10-27); live agents not yet run

Code: `backend/src/spoor/agents/`. Tests: `tests/test_agents.py` (ScriptedBackend fixture replays agent turns).
- Lead = deterministic orchestrator; Verifier = step-07 engine; Evidence + Hypothesis = LLM agents (DECISIONS.md).
- Agent protocol: each turn returns `{action: call_tool|final, tool, args_json, final_json}`, so it works on any
  backend without provider-specific tool calling. Unknown tools, bad args and out-of-scope IDs are rejected and
  logged; repeated calls are served from checkpoints; step/token/deadline budgets enforced.
- The answer text is composed from verified findings + recorded hypothesis statuses only.
- Without any LLM, investigation still returns the verified last-seen answer (this is ablation A2).
