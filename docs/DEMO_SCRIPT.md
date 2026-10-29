# 3-minute demo script (draft)

Goal: in 180 s, show judges a capability a plain video model does not have — **answers with sources, honest gaps,
and revision when new evidence arrives** — on footage we recorded during the hackathon. Every number on screen must
come from a real run (see `docs/EVALUATION.md`); if a number is not measured yet, it is not shown.

| Time | Screen | Say (short) | Rubric hit |
|---|---|---|---|
| 0:00–0:15 | Two CCTV views of our staged storeroom; the blue case on Shelf A | "A case went missing. Staff usually scrub hours of footage. Spoor gives the room a memory — and every answer a source." | Impact |
| 0:15–0:35 | Ask plain Muse Spark (baseline A0): "Where is the case? Did it leave?" — fluent answer, no frame, possibly wrong | "A video model answers fluently. But where's the evidence?" | Creative use / contrast |
| 0:35–1:05 | Spoor: same question → 3D room, camera flies to **last confirmed** position; solid green observed track; grey gap; "Leaving the room: NOT established" | "Spoor says only what was seen: last confirmed here, at this time, on this camera. The gap stays a gap." | Technical depth, Demo |
| 1:05–1:25 | Click the point → original frame + annotated derivative toggle + SHA-256 | "Every claim is one click from the original frame, hashed at ingest." | Technical depth |
| 1:25–1:50 | Agent panel: Evidence agent's tool calls; Hypothesis agent proposes H1 occluded / H2 out the door; verifier: H2 insufficient — "no footage beyond the door"; evidence request for the hallway camera | "Agents investigate, but a deterministic verifier decides. No source, no fact." | Meta AI tooling (Muse Spark, SAM 3.1), Agentic |
| 1:50–2:15 | Import hallway clip → **diff view**: "new evidence: H2 now supported; last seen moved to hallway" | "New evidence revises the case — history is kept." | Demo signature moment |
| 2:15–2:40 | Evaluation table: A0 vs CD vs A2 vs A3 on our scenarios, including where Spoor fails | "Measured, not claimed — including our failures." | Technical depth |
| 2:40–3:00 | Report export, reviewer approval; disclaimer; "built during the hackathon" (NEW_WORK) | "Investigation support, not accusation. No faces, no identity, no guessing." | Impact, eligibility |

## Recording checklist

- Footage: consented actors, distinct blue case + a lookalike, clap for clock sync, hallway camera clip.
- Operator view open in a second tab (trace endpoint) in case a judge asks "which Meta model did what?".
- Have a pre-run case **and** do one live step (import the hallway clip) so the diff is real, not replayed.
- Never show test fixtures (synthetic ffmpeg clips) as results.
