# 3-minute demo script: parcel hub (real app, keys first)

**The problem, in one sentence (say it first):** a customer says a parcel never arrived, and the hub's scan log only
says where the parcel was *scanned*, not where it *went*.

Goal: in 180 s, show what SAM 3.1 + Muse Spark do inside Spoor that a plain video model does not: **answers with
sources, honest gaps, and revision when new evidence arrives**, on the fictional CONTOH Express hub (synthetic footage,
simulated scan log). Every number on screen comes from a real run. If it is not measured, it is not shown. Fictional
names only.

**How to read the table.** The main column ("With keys") is the demo we want: what SAM 3.1 and Muse Spark do at that
step. The "Fallback (no key)" column is what the same click shows without keys. Rows marked "—" in the 🔑 column are
the same either way. Never narrate a model result that is not on screen. If a keyed step fails on the day, use its
fallback line and move on.

## Before recording (not on camera)

1. **Keys and smoke tests first** (the top blocker, see `review/FOR_REXTON.md` 04:50). Put `MODEL_API_KEY` (Meta Model
   API) and `BASETEN_API_KEY` + `BASETEN_MODEL_ID` in `backend/.env`. Run the smoke tests in
   `docs/build/00-setup-and-smoke-tests.md` (`list_models`, `spark_structured`, `spark_video`, `sam_segment` image +
   video, `baseten_open`). Record results in `docs/META_MODEL_USAGE.md`. If one fails, its steps below use the fallback.
2. Start the stack:

```bash
cd frontend
npm run backend      # no-key mode: the seed only loads inputs into a backend without keys
npm run seed -- --scenarios ../ml/evaluation/scenarios/manifest.json   # one input case per rendered scenario
# stop it (Ctrl+C), then restart on the same data with the keys from backend/.env:
npm run backend:keys
npm run dev          # http://localhost:3000
cd ../backend && uv run python ../ml/evaluation/run_hub.py --out ../frontend/.local/backend-data/evaluation
```

The seed reads only `ml/evaluation/scenarios/manifest.json` and `<S>/case_input.json` (waybill, complaint, cameras,
clips). It never reads scenario cards or anything the evaluator scores against.

3. Tabs: `/wall?scenario=S2` (camera wall), the S2 case workspace (Investigator), `/operator` (Site admin). Browser at
   1440×900, 100 % zoom. **Scenario: S2** (the builder renders it first; IDs and titles come from the manifest, so use
   whatever the manifest calls it). If S2 is not rendered yet, the wall says "Renders not produced yet": use the
   newest rendered scenario instead, or the seeded control case's footage (`/wall?case=<id>`).

## Walkthrough

| Time | Click | With keys: what SAM 3.1 + Muse Spark do | Screen shows | What it proves | Fallback (no key) | 🔑 |
|---|---|---|---|---|---|---|
| 0:00–0:08 | (Title / Cases list) | — | One line: "A customer says parcel CTX… never arrived. The scan log says where it was scanned, not where it went." | The problem, before any feature | Same | — |
| 0:08–0:22 | Camera wall → **Full screen** → **▶ Play** | — (plain playback) | 3×3 synchronized synthetic CCTV of the scenario, each tile with its burned-in OSD clock and SYNTHETIC mark; the complaint line from `case_input.json` above it | The footage is the raw material: many cameras, no single one tells the story | Same. Tiles not rendered or not imported say so; nothing stands in for them | — |
| 0:22–0:35 | **Open the case** | — | Question, waybill, cameras in scope, model analysis On | The case starts from the waybill the customer gave: identity comes from scans, not from guessing which box is which | Model analysis shows Off (no API key) | — |
| 0:35–1:00 | **Show where it was last confirmed** → **▶ Play** in the source panel | SAM 3.1 is prompted on the read-point camera's frame at the last scan (a box on the parcel) and tracks it forward in that clip; its frames become video observations. Last seen moves from the scan to the last frame on a confirmed track, only if the verifier accepts it | The read point in 3D, the camera that sees it, the original frame with SHA-256; Play runs the clip from 3 s before the scan, Pause lands on the exact original frame | Last seen is graded (fixed scan > handheld > video on a confirmed track). A divert confirmation is the sorter's word, not a new label read | Scan-based last seen only. Play still works and is labelled "context, not an observation": nothing in it was detected | 🔑 SAM 3.1 |
| 1:00–1:15 | Timeline → open "clock warnings" | — | One timeline: camera lanes with ± hatching, scanner clock "not synchronized", handheld late uploads | Clocks are checked or explicitly warned (PRD §29); simulated inputs stay labelled | Same | — |
| 1:15–1:40 | Movement trace: Object, then click a green segment | SAM 3.1 tracks per camera; floor contact through the calibration gives floor_xy with an uncertainty ring; cross-camera handoffs stay amber (hypothesis) until verified | Green solid = observed, amber dashed = hypothesis, grey = unknown gap; the click opens the exact source frame and the annotated derivative (SAM box/mask) | Solid never bridges a gap; every segment is one click from its frame | Only scans and grey gaps; People mode says "needs SAM". Never show the `fx_*` fixture on camera | 🔑 SAM 3.1 |
| 1:40–2:05 | Agent tab → **Run the investigation** | Evidence agent asks Muse Spark 1.3 bounded questions about short clip windows (e.g. "is a parcel carried out of view between t1 and t2?"). Spark returns typed proposals with frame references; each cited time is checked against the frame / a SAM observation before it can count. Hypothesis agent (Muse Spark Open on Baseten, or Spark) proposes competing explanations; the deterministic verifier accepts or rejects each one | Real job events over SSE; answer built from verified findings only; hypotheses with status; a named evidence request (camera + interval) | Agents propose, a deterministic verifier decides; abstention ("unknown", "no coverage") is an answer, not a failure | Deterministic orchestrator only: the answer abstains ("Leaving the area: NOT established"), no hypotheses | 🔑 Muse Spark 1.3 / Open |
| 2:05–2:25 | Operator → import the clip named in "Next evidence" → Agent → run again | SAM 3.1 runs on the new clip; any new observation re-runs the affected hypotheses | "What changed in this revision": new findings, status changes, last-seen change; history kept | New evidence revises the case without rewriting the past | The clip imports; the re-run changes only coverage statements | 🔑 SAM 3.1 |
| 2:25–2:40 | Operator → Evaluation results | Keyed variant scored next to the no-key variant on the same cases (to add once keys work: `run_hub.py` scores the no-key variant only today) | Headline from the D scenarios S1–S5 (no-read, blind spot, phantom containment, mis-load, look-alike): last seen correct, correct abstention, "visible but unanalysed", false "left the hub" | Measured on cases where the score can fail; truth read by the evaluator only | No-key variant only. If S1–S5 are not rendered yet, the headline is the control flow with its on-screen caveat (expected near 100 %, proves little) | 🔑 for the comparison |
| 2:40–3:00 | Report → Export draft (Investigator) → switch to Reviewer → Approve | — | Sandboxed report, report hash, hash manifest, "a reviewer cannot approve a report they exported" | Human approval, hashes, provenance; investigation support, not accusation | Same | — |

## Lines to keep

- "The scan log says where it was scanned. Spoor shows where it went, and says so when nobody saw it."
- "Spoor says only what was seen or scanned. The gap stays a gap."
- "A divert confirmation is the sorter's word about a carrier, not a new label read."
- "No faces, no names: operators are pseudonymous tokens; the footage is synthetic."

## Recording checklist

- Keys in and smoke tests recorded before the first take; otherwise record the fallback column and say "analysis
  unavailable without a key" at the 🔑 steps. Never narrate what a model would have said.
- Never show `fx_*` fixture screens as results; they exist only to test the renderer and carry a yellow banner.
- Every footage frame shows its burned-in SYNTHETIC mark (the camera wall and the source panel play the original clips).
- Keep the Operator tab ready in case a judge asks which model did what (model calls and agent steps panel).
