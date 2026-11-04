# Reviewer note 23:00 Sun 1 Nov: Meta stack (how each model is used) + customer-complaint flow

Read fully. Priority order at the bottom. Rules that apply to everything below:
- **No S2 hardcoding.** Agent prompts, tool descriptions and rules stay general (no camera names, times, zones, parcel IDs,
  "exception store"). Fix the `run_sam` tool description example "e.g. cam_CAM_13" to a neutral one.
- Fictional brands only (no Shopee/Lazada name or logo in app or video). Everything simulated is labelled.
- Generative output never becomes evidence. Never claim proof. Parcels, not people. No em dashes in UI copy.
- Log one line per commit in review/log.md. Keep LF line endings.

## 1. Meta models: role, proper use, why

| Model | Role in Spoor | Input -> output | Use it properly | Why this model | Status |
|---|---|---|---|---|---|
| SAM 3.1 (hosted) | Tracker in the blind gap after the last scan; also times parcels crossing scan points for clock fits | video + short noun or box/point prompt -> per-frame boxes/masks, track ids | Anchor from the last scan (scan point -> camera -> pixel area via calibration); short windows only; re-link across cameras by place + time, never by id; upload once, reuse file_id | Promptable tracking of ONE object = pixel evidence a supervisor can check + "should be here, isn't" | working |
| Muse Spark 1.3 (hosted) | Clip analyst: fixed questions on short crops (carrying_v1) | clip -> strict JSON | Crop around a SAM track; fixed templates; json_schema; "cannot see" allowed; facts count only if grounded in SAM observations | Cheap native video understanding -> typed facts | working |
| Muse Spark Open (Baseten) | Evidence + hypothesis agents | text/tool results -> tool calls, claims | Native tools, constrained decoding (json_schema, anyOf union), reasoning_effort medium, step/token caps; every claim through the verifier | Open weights = self-hostable (data residency, PDPA); Open Weights prize | working |
| Muse Wonder 1.0 (hosted) | Lead investigator: plans and re-plans, delegates to the agents | scan log + findings (text) -> plan, next steps | Planning/re-planning only; never sees pixels; plan steps cite evidence; re-plans after a verifier rejection (look-alike) | Long multi-step agentic work; needed for Creative + Agentic prizes | **MISSING from keyed runs 1-3: must lead the next run** |
| Muse Glimmer (Modal, Apache 2.0) | On-site triage: flags parcel-handling moments on still frames from all cameras | images -> flags | Few frames per camera per window; flags only choose which clips go further, never evidence | Edge model; raw CCTV stays on site; Open Weights prize | **only tested on old frames: run once on the final S2 footage (estimate first, ~US$1-3)** |
| Muse Voice Transcribe | Staff voice note in Go look ("found it on shelf 3"); complaint call -> text | audio -> transcript, speaker turns | Keyword biasing (waybill, tracking id format); per-turn timing; stored with hash as a human statement | Gloved staff talk; claims start as calls | built, show once in the video |
| Muse Image | not used | - | - | an evidence tool must never generate pictures of what happened | left out on purpose |
| Muse Code | not a product feature | - | mention in README only if used | coding agent, not part of Spoor | - |

API features to keep visible: structured output, Files API, tool calling, reasoning effort, prompt caching; Contributor
mode only on synthetic footage.

Flow: scans -> Glimmer triage -> Wonder plans -> Spark Open agents -> SAM tracks -> Spark checks crops -> verifier
decides -> staff scan the barcode (+ Voice note).

## 2. Customer-complaint flow ("Customer asked")

Real world: the customer complains to the marketplace or the courier's customer service (chat, call, email). Customer
service checks tracking, sees the last scan at this hub, and sends a **trace request** to the hub. The hub supervisor
uses Spoor. The hub never takes customer calls.

| Step | Tool / model | Input -> output | Use it properly |
|---|---|---|---|
| 1. Trace request arrives | Webhook/API from the courier's ticket system (simulated, fictional marketplace) | ticket (tracking no., order no., message) -> case input | labelled simulated |
| 2a. Complaint by phone (optional) | Muse Voice Transcribe | call audio -> transcript | customer statement, not evidence of location |
| 2b. Read the complaint | Muse Spark 1.3 (or Spark Open) | message/screenshot -> JSON: tracking no., order date, claim type, customer's words | json_schema; missing fields stay empty; match tracking no. to the scan log |
| 3. This hub's problem? | Spoor rules (no AI) | tracking no. -> last scan, overdue? | last scan here + overdue -> case marked "Customer asked"; else "not at this hub" |
| 4. Investigate | same pipeline | - | unchanged |
| 5. Reply | Muse Spark 1.3 (or Spark Open) | verified findings -> short customer update | only verified findings; no blame, no person, no "stolen"; human approves; no real sending |

App (keep small, ~1-2 h): "Customer asked" chip on the S2 Hub alert row (S2 case_input.json already has a complaint);
Customer box on the case (complaint text, days waited); "Send update to customer" on Report showing the drafted reply.
Minimum if time is short: the chip + the opening shot. Skip phone calls and claim-rules search unless spare time.

Video opening (~20 s): customer chat "Where's my parcel? 2 weeks." -> tracking says "loaded onto truck" ("The records
say it left. It never did.") -> Hub alert "Customer asked" -> Investigate -> agents -> answer -> customer gets "found
at the hub, re-sent today" + "Spoor can also flag stuck parcels before anyone complains."

## 3. Priority order
1. Keyed S2 run: Wonder leads; agents can run the door check + carrier check; general "in an unseen area" claim
   (went in carrying, came out empty, nobody else came out until the recording ends). Target answer: "most likely in Z11".
2. Glimmer on the final S2 footage (estimate first).
3. Control parcels on the same footage, no code changes (look-alike CTX976456695076, a parcel in a cage that left
   normally, a belt parcel): numbers into EVALUATION.md.
4. Customer-complaint chip/box/reply.
5. Update README, LIMITATIONS, DEMO_SCRIPT, EVALUATION to the current state.
Any single run > US$10 needs Rexton's OK.
