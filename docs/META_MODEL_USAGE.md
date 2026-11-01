# Meta model usage

## Verified API facts (dev.meta.ai docs, 2026-10-27)

- Base URL `https://api.meta.ai/v1`; `Authorization: Bearer $MODEL_API_KEY`; OpenAI SDK compatible.
- Muse Spark 1.3: `/v1/responses`; video via `input_video` (`video_url` or `file_id`) or `input_file`; only
  `video/mp4` listed for Spark. Audio understanding "not fully supported" → audio off.
- Structured output on Responses uses `text.format` (json_schema). Strict subset: root object,
  `additionalProperties: false` everywhere, all keys required, no `allOf`/`oneOf`, no recursion.
- SAM 3.1: `/v1/responses`, `stream: true`. Text prompt = one short noun phrase. Box/point prompts are inline tokens
  in **pixel** coordinates of the displayed (post-rotation) frame, e.g.
  `<0f>1<|box;x1=..;y1=..;x2=..;y2=..;w=..;h=..|>`. Video: MP4/MOV, H.264/H.265/MPEG-4, ≤15,000 frames,
  billed per frame with a 50-frame minimum. `metadata.propagation_direction`: `both|forward|backward`.
  `metadata.include_confidence: "true"` adds per-record confidence.
- SAM output: one `output_text` line per frame `<Nf>`; frame indices can skip; object IDs stable within one response
  but not across exit/re-entry/full occlusion. Masks are base85, decoded with `meta-sam-parser`.
- Files API: `POST /v1/files`, `purpose="user_data"`; 1 GiB upload limit (50 MB inline); files don't expire unless
  `expires_after` is set (smoke tests set 1 hour); 100 GiB team storage limit.

## Still unknown (smoke tests must answer)

Spark video duration/size limits and frame sampling; rate limits; actual cost per clip-second; whether SAM video
object IDs survive short occlusions in our footage.

## Smoke test log

| Date | Test | Model | Result | Latency | Usage/cost | Notes |
|---|---|---|---|---|---|---|
| 2026-10-31 | list models | — | all required listed: sam-3.1, muse-spark-1.3, muse-wonder-1.0 (+1.1/1.2, contributor variants, muse-image-1.0, muse-voice-transcribe-1.0) | <1 s | free | `scripts/smoke/list_models.py` |
| 2026-10-31 | SAM 3.1 image, text prompt "box" | sam-3.1 | 3 parcels on the loop, conf 0.62–0.66, masks decoded | 4.7 s | 1 image ≈ $0.0025 | synthetic CAM_07 QA frame 960×540 |
| 2026-10-31 | SAM 3.1 video, "cardboard box" | sam-3.1 | completed, **0 records** | 9.3 s | 60 frames ≈ $0.012 | the noun phrase matters: same clip found nothing with this phrase |
| 2026-10-31 | SAM 3.1 video, "box" | sam-3.1 | 2 objects tracked: 32 + 26 frames, ~8 px/frame along the belt, conf 0.70 | 7.3 s | 60 frames ≈ $0.012 | 6 s synthetic clip uploaded via Files API (1 h expiry), deleted after |
| 2026-10-31 | Spark 1.3 video question | muse-spark-1.3 | correct: red parcel on the lower straight, left→right past the crossover, 0–5.3 s; "stops being visible: not_observable" | 3.7 s upload + 16.3 s | 1,622 in / 2,725 out (2,592 reasoning) ≈ $0.014 | a 6 s clip costs only ~1.6k input tokens (sparse frame sampling) |
| 2026-10-31 | Spark 1.3 structured output (strict json_schema) | muse-spark-1.3 | schema-valid; cites only obs_1/obs_2; abstains on "did it leave" | 14.0 s | 278 in / 2,056 out ≈ $0.009 | `scripts/smoke/spark_structured.py` |
| 2026-10-31 | Wonder 1.0 investigation plan over a real no-key case (journey + missing moment) | muse-wonder-1.0 | schema-valid plan: CAM_07 then CAM_10 at 14:32:31.8–34.8 MYT (the only cameras with footage watching the divert); 0 dangling citations; unknowns listed, no location claimed | 23.7 s | 2,291 in / 2,886 out (1,872 reasoning) ≈ $0.067 | `scripts/smoke/wonder_plan.py` |
| 2026-10-31 | Baseten Muse Spark Open, evidence graph (answerable + unanswerable) | meta-models/muse-spark-open-1026 | both PASS (cites obs_2; abstains on door_b); reasoning returned in `reasoning_content` (~2k chars), kept apart from the JSON answer | 3.9 s / 2.4 s | ~350 in / ~570 out each (Baseten price not in the response) | proof: `docs/open_weights_proof/2026-10-31_j1_baseten_smoke.json` |
| 2026-10-31 | J4 Voice Transcribe, DIARIZATION, 10 s **synthetic** TTS speech (Windows speech synthesis, not evidence) | muse-voice-transcribe-1.0 | 1 turn (A, 140–9420 ms); exact except "Waybill" → "Wable" (the case route now sends "waybill" as a keyword) | 4.8 s | 10 audio s = $0.0005 | multipart `request` JSON + `audio` WAV to `/v1/asr/transcribe`; `scripts/smoke/voice_transcribe.py` |
| 2026-10-31 | J3 search grounding, 3 narrow MY-law questions (`tools=[{"type":"web_search"}]`) | muse-spark-1.3 | 11 cited sentences kept, 5 uncited + 1 tool-narration sentence dropped; 4 sources (1 .gov.my); ss. 4/31/33/49-52 of Act 741 match a second copy of the Act (LawPlayer), except that s.31 adds "intentional" | 120 s | 653,514 in / 12,311 out + 52 searches = **$1.00** (estimate was $0.06) | the search result pages bill as input tokens: budget about $0.33 per grounded question; `scripts/smoke/search_grounding.py` |

J1 total: Meta ≈ $0.12, Baseten ≈ 1.8k tokens. Answers to the open questions: Spark samples a short clip sparsely
(~270 input tokens per second of 960×540 video); every Muse model spends most output tokens on reasoning, so budget
by output tokens; SAM text prompts must be short generic nouns ("box", not "cardboard box").

## Expanded Meta stack plan (Rexton 01:22 Sat 31 Oct: "use more of the Meta offering") — every use must be real, not decoration

| Meta tech | Where in Spoor | Why it fits | Effort |
|---|---|---|---|
| **SAM 3.1** (video segmentation) | Track the scanned parcel / person / cage across frames from the scan anchor | Core: the follow-cam, journey, missing moment | in place, needs key |
| **Muse Spark 1.3** (video understanding, tool calling, structured output) | Camera-analyst sub-agents: describe each clip as typed observations (json_schema) | Core evidence extraction | in place, needs key |
| **Muse Wonder 1.0** (long-horizon agent, sub-agents, 1M context) | Lead investigator: plans the case over the whole scan log + all observations, delegates per-camera work to Spark agents | Long multi-step investigation is exactly its job; Spark stays the cheaper worker | small (model switch + role) |
| **Muse Spark Open** (open weights) on **Baseten** | Agent reasoning backend option (AGENT_BACKEND=baseten) | Same model family, self-hostable — on-prem story for hubs | in place, needs key |
| **Muse Glimmer** (open weights, Apache 2.0, edge) on **Modal** GPU | On-site triage: watches each camera and flags only parcel-handling moments, so raw CCTV never leaves the hub (privacy, PDPA) — only flagged clips go to Model API | Deployment story: edge + cloud | medium (stretch) |
| **Muse Voice Transcribe** | (a) floor staff say "found it on shelf 3" into the phone search task → transcript with speaker turns becomes case evidence; (b) a customer complaint call → transcript becomes the case input | Gloved floor staff talk, not type; claims start from calls | medium |
| **Search grounding** (inline citations) | Case report's Malaysian context: Postal Services Act 2012 / MCMC rules, claim timelines — cited, dated | Review 012 asked for sourced MY legal context | small |
| **Structured output, Files API, prompt caching, token counting, reasoning effort, Contributor mode** | Typed observations; upload each clip once; cache the site/camera context per case; show cost before a run; high effort only for the lead; Contributor mode for bulk camera passes | Tech depth + lower cost | small |
| **Muse Image** (generate / edit) | ONLY synthetic set dressing for the fictional hub: CONTOH Express label artwork, signage, posters, parcel print textures | Fictional brand assets without copying real brands | small (builder) |
| **Muse Code** (coding agent) | Write the Meta smoke tests + one backend module with Muse Code; note it in the repo | Uses Meta's own dev tooling honestly | small |

Hard rule: generative models (Muse Image, any text generation) never create or alter evidence. Evidence = original frames,
scan records, SAM tracks, typed observations — each with its source hash.

### Prices from the Model API models page (Rexton's dashboard, 31 Oct 2026, per 1M tokens unless stated)
Muse Wonder 1.0 $4.00 in / $0.20 cached / $20.00 out · Muse Spark 1.3 $1.25 / $0.15 / $4.25 · Spark 1.3 Contributor
$0.10 / $0.002 / $0.20 (select countries; inputs/outputs used to train Meta models) · SAM 3.1 $0.20 per 1,000 video frames,
$2.50 per 1,000 images · Muse Voice Transcribe $0.18/h · Muse Image 1.0 $0.01/image · Muse Glimmer 30B (Apache 2.0,
single GPU, Hugging Face) and Muse Spark Open (Muse Model License) are self-hosted.
Rough S2 cost: SAM on 7 cameras × 90 s × 10 fps ≈ 6,300 frames ≈ $1.26; Spark camera passes are cents with caching.
**Contributor mode rule:** only for our SYNTHETIC footage during development. Real customer CCTV must never go through
Contributor mode (it trains Meta models) — Standard mode or on-site Glimmer only. State this in docs/PRIVACY.md.

### Credits and budget (Rexton, 31 Oct 01:26)
- Meta Model API: **$150 free credits**. While on free credits "content may be used for product improvement" → same rule
  as Contributor mode: synthetic footage only; real CCTV only on paid Standard mode or on-site.
- Baseten: **$100**. Use Baseten's per-token Model API endpoint for Muse Spark Open if offered; do NOT start a dedicated
  deployment of the 816B model (multi-GPU, can burn the $100 in hours). If a dedicated deployment is the only way:
  scale-to-zero on, smallest NVFP4 config, max 1 h test, Rexton approves first.
- Modal: **$30** shared — render test ≤ $2, Glimmer test ≤ $3, anything bigger needs Rexton.
- Expected spend to submission: Meta ≈ $10–30 (SAM ≈ $1.3 per S2 pass; Spark/Wonder cents–dollars per run with caching),
  Baseten ≈ $5–20 per-token, Modal ≈ $20–28 if the full render goes there. Every agent prints a cost estimate before a
  paid run and logs the actual cost after it in review/log.md.

### Baseten hackathon access (Rexton's award email, 31 Oct)
- Model name (exact): `meta-models/muse-spark-open-1026` — the key only works with this model (docs say
  `meta-models/muse-spark-open`; for the hackathon always use the `-1026` name). Base URL `https://inference.baseten.co/v1`,
  OpenAI-compatible chat completions. $100 credits, up to 2M tokens/min.
- Muse Spark Open always reasons: parse the reasoning separately from the answer (see Baseten "Reasoning" doc) so the
  JSON validator only sees the answer.
- Vision and audio input are supported on Baseten — BasetenChatBackend is text-only today; adding image input (key
  frames) makes the open-weights path load-bearing for the bonus (task for J2).

## Best practices from the official docs (dev.meta.ai, read 1 Nov 2026) + what they mean for Spoor

**SAM 3.1** (`/docs/sam/segmenting`, `/docs/sam/reading-segmentation`)
- Concept prompt = one short noun phrase; one concept per request; no commands/questions/lists/negation/spatial words.
  Docs suggest adding colour/type to narrow - BUT our own 31 Oct test: "cardboard box" -> 0 records, "box" -> 2 tracks.
  Measure on our footage before narrowing.
- A specific object: box/point prompt on any frame `<Nf>id<|box;x1;y1;x2;y2;w;h|>` (w/h = displayed size; wrong aspect
  -> 400). Can't mix concept + box/point in one request. Up to 16 objects.
- Re-prompt the SAME object id on a later frame to pick it up again (the only re-entry mechanism); ids are NOT reliable
  across entry/exit/full occlusion or very long clips - relink in our own code (place + time), never by id.
- `propagation_direction`: both (default) / forward / backward, measured from the earliest prompt frame; with `both`
  frames arrive out of order -> key by `<Nf>`. Empty frames emit no line (a valid "not visible").
- `include_confidence: "true"` (string) -> per-frame c; `mask_encoding: "one_bit"` for smaller payloads; MP4 faststart;
  upload once (Files API user_data) and reuse file_id; results vary slightly run to run. Billed per frame, 50 minimum.
**Muse Spark Open** (`/docs/muse-spark-open/prompting`, `/settings`)
- Native OpenAI tools (append `tool` messages by tool_call_id, same order); reasoning always on, `reasoning_effort`
  low 8 / medium 32 / high 256 / xhigh 512 (default!) - use medium for agent loops, low for extraction; stream long ones;
  most important rules first in the system prompt; video input >= a few seconds and >= 448 px short side.
- Baseten (tested 1 Nov, meta-models/muse-spark-open-1026): `response_format` json_schema strict WITH an `anyOf`
  tagged union -> valid schema-shaped JSON; native `tools` -> correct tool_call. => our BasetenChatBackend (schema in
  the prompt + local repair) is why every hypothesis was rejected as "malformed claim": switch it to native tools +
  response_format, claims as anyOf of kind-tagged objects (no oneOf), reasoning_effort medium.
**Structured output** (`/docs/structured-output`): constrained decoding; strict: root plain object, no allOf/oneOf
anywhere, anyOf only below root, additionalProperties false + all required; no recursion; <= 10 nesting levels.
