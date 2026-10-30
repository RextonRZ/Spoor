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

## Walkthrough (S2: "the records say it left on the truck; the cameras say it is in the exception store")

Updated 31 Oct (block H/I/J). Every screen below runs on the real app; 🔑 marks what changes with keys.

| Time | Click | Screen shows | What it proves | No key | 🔑 |
|---|---|---|---|---|---|
| 0:00–0:10 | **Hub** (Operator clock "+30 min") | Stalled parcels: S2's parcel, overdue, with "SP-BAG-C07 kept scanning other parcels" as proof; tracking-number search | Alerting from the scan log, before the customer complains; no false alarms when a log just ends | Same | — |
| 0:10–0:25 | **Open case** → case summary | "Last confirmed at … · time" + one sub-line, 4 key frames (last confirmed · missing moment · where it is · found), route map, how sure, next action | Page 1 for claims and managers, built only from typed evidence | Same words; frames are context frames | — |
| 0:25–0:55 | **Open the investigation** → ▶ replay at 4× | CCTV hero (follow-cam on the parcel), camera route strip, 2D journey: green seen, amber belt inference, blue scan beads, scan cards as the playhead passes each scan | It is a CCTV product: original pixels with hashes; the route snaps to belts; inferred is never drawn as seen | Scans + amber belt stretches + grey gap; follow-cam says "tracking needs SAM" | 🔑 SAM 3.1 |
| 0:55–1:20 | **Missing moment**, then **Cameras** | Where the evidence stops; each camera due next at its predicted time with a dashed box; CAM_19 doorway carried in; CAM_01/06 "not seen" = typed negative evidence; synced grid on one scrubber | How we prove where it went missing: negative evidence made visible | "not analysed yet"; no-footage cameras listed | 🔑 SAM 3.1 |
| 1:20–1:40 | Scrub past the break | The "could be here" area grows, then collapses into the exception store when the watched exits did not see it; "Where it might be · computed": 1. Exception store | A computed area, labelled as such; cameras that watched remove area | The area only grows (nothing analysed) | 🔑 SAM 3.1 |
| 1:40–1:55 | Summary → **records vs cameras** | Two lanes split at a red pin: "The records say it left the hub (RC-864 loaded at D07); CAM_19 saw it at the exception store" | Records and video disagree, and the app says where | Empty camera lane: "not agreement" | 🔑 |
| 1:55–2:15 | **Agent** → Plan with Muse Wonder (cost shown) → Run the investigation | Wonder's plan (steps checked against the evidence); Spark Open on Baseten sees the key frames; verifier decides | Agents propose, a deterministic verifier decides; open weights reason over evidence pictures | "Unavailable: no API key"; deterministic answer abstains | 🔑 Wonder · Spark · Spark Open |
| 2:15–2:30 | Phone: **Floor search** → "Found it here" | Checklist in walking order; the case turns Found; summary headline updates | A person's outcome is new evidence, pseudonymous and hashed | Same (a real outcome, never a fixture on camera) | — |
| 2:30–2:45 | Summary → **Export evidence reel** → Report → Approve | MP4 of the journey (seen crops, scan frames, amber, grey cards; SYNTHETIC, hashes); report appendix with hashes and the Evidence Act footnote | Hand-over material a claims team or police can use | Reel uses context frames + cards | — |
| 2:45–3:00 | 3D → **Plan-built 3D** | The hub extruded from its floor plan; journey and cloud in 3D | "Any hub with a floor plan and its cameras gets this on day one" | Same | — |

Never show a `fx_*` fixture on camera. Synthetic footage and simulated scans stay labelled.

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
