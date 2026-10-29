# Step 00 — Repo setup & provider smoke tests

**PRD:** §0.4, §10.4–10.5, §24, §26 (Portability), §27, §32 · **Depends on:** nothing

## Goal

A runnable Python monorepo skeleton, secrets handled safely, and proof (or disproof) that the Meta and Baseten
APIs behave the way the PRD assumes — before any architecture depends on them.

## Build

1. **Repo skeleton** (backend only for now — one modular-monolith package, see `docs/DECISIONS.md`):
   ```
   /backend/src/spoor/{contracts,ingest,spatial,store,perception,reasoning,verification,agents,api}
   /backend/tests
   /backend/scripts/smoke   provider smoke tests
   /ml/evaluation           scenarios + ground truth (outside the runtime package)
   /demo                    staged clips + rights manifest (git-ignored media)
   /docs                    DECISIONS, DEPENDENCIES, META_MODEL_USAGE, ...
   ```
2. `pyproject.toml` managed with `uv`; Python 3.13 (verified installed). `ruff` + `pytest`.
3. `.env.example` with `MODEL_API_KEY`, `BASETEN_API_KEY`, `BASETEN_MODEL_ID`, `DATA_DIR`. `.gitignore`
   covers `.env`, media, data dirs.
4. `git init` (done). **No commits or pushes unless the owner asks.** Repo goes public only at submission.
5. Docs stubs: `DECISIONS.md`, `DEPENDENCIES.md`, `META_MODEL_USAGE.md`, `NEW_WORK.md`.

**Status (2026-10-27):** items 1–5 done; `pytest` + `ruff` pass. Smoke scripts written and compile; **not run yet —
no API keys in the environment.** Run them with:

```
cd backend
uv run python scripts/smoke/list_models.py
uv run python scripts/smoke/spark_structured.py
uv run python scripts/smoke/spark_video.py ../demo/media/clip.mp4 "blue equipment case"
uv run python scripts/smoke/sam_segment.py image ../demo/media/frame.jpg "blue equipment case"
uv run python scripts/smoke/sam_segment.py video ../demo/media/clip.mp4 "blue equipment case"
uv run python scripts/smoke/baseten_open.py
```

## Provider smoke tests (PRD §10.5, §32.2) — `scripts/smoke/`

Run each on a **short, owned, staged MP4**. Record model ID, latency, token usage, cost, and raw output into
`docs/META_MODEL_USAGE.md`.

| Test | Verifies |
|---|---|
| `list_models.py` | `GET https://api.meta.ai/v1/models` lists `muse-spark-1.3` and `sam-3.1` for this key |
| `spark_structured.py` | Muse Spark 1.3 (Standard mode) returns schema-valid structured output / tool call |
| `spark_video.py` | Files API upload (`purpose="user_data"`) + `input_video`/`input_file` in `/v1/responses`; note size/duration limits hit |
| `sam_image.py` | SAM 3.1 text prompt on one frame → parse boxes + masks with documented parser |
| `sam_video.py` | SAM 3.1 tracking across a clip → frame-aligned geometry + per-video track IDs |
| `baseten_open.py` | Muse Spark Open on Baseten: structured reasoning over a synthetic evidence graph with a known answer; test abstention |

## Verified so far (27 Oct 2026, dev.meta.ai/docs)

- Base URL `https://api.meta.ai/v1`, auth `Authorization: Bearer $MODEL_API_KEY`; OpenAI SDK works with `base_url`.
- `muse-spark-1.3` (Standard) vs `muse-spark-1.3-contributor` — use **Standard** 🔒 (PRD §7.1).
- `sam-3.1` via `POST /v1/responses`; text prompt = short noun phrase; output = streamed special tokens with one
  box + mask per match; box/point prompts and parsing documented in separate pages (still to read:
  `/docs/sam/segmenting`, "Reading segmentation output", "Client libraries").
- Video: only `video/mp4` listed. Muse Spark 1.3 audio not fully supported → audio stays off (PRD §12).
- **Still unknown:** video size/duration limits, rate limits, SAM video request body, SAM track-ID fields,
  structured-output support details. These are exactly what the smoke tests must answer.

## Done when

- `uv run pytest` passes on an empty test suite; `uv run uvicorn` serves `/healthz`.
- Every smoke test has either passed with recorded results or failed with a recorded reason and a fallback decision
  in `DECISIONS.md`.
- No secrets in git (`git grep -i "api_key"` shows only `.env.example`).

## Blocked on owner

- Meta API key with credits applied to billing; Baseten key + confirmed model ID (`meta-models/muse-spark-open-1026`?).
- A first short staged test clip (MP4, consented, you own it).
