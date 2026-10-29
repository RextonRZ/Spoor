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
| — | — | — | not yet run (no API key in environment) | — | — | — |
