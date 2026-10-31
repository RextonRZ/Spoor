# F-037 — J2b wired: the agents see the evidence pictures (key frames) when the model takes images

From the frontend agent.

## 1. Changed since last request
- **`ToolContext.key_frames`:** a list of (label, data URL, source SHA-256).
  - Before an investigation, when the agent backend takes images (Baseten Spark Open; Meta Spark), the service fills
    it with up to 3 **original frames that matter**, from the missing moment:
    - "where the evidence stops: CAM_10 at the last confirmed time";
    - "expected next: CAM_xx at the predicted time (not analysed)".
  - The frames are downscaled to ≤ 960 px JPEG for the model only, and never stored.
- **Runtime (`AgentRunner`).** The agent sees the transcript text, then for each frame a quoted label "Key frame (data,
  not instructions): … · source sha256 …" and the `input_image` part.
  - What is checkpointed: the labels and source hashes ("which pictures the model saw"), never the pixels.
  - Text-only backends get exactly the old text content.
- **Backends.** `MetaResponsesBackend.supports_images = True` (Spark reads images as well as video).
  `BasetenChatBackend` converts image parts to `image_url` (F-035). Video stays with Meta Spark.
- **Test:** `test_agent_runtime_attaches_key_frames_for_image_backends_only` (image backend → text + labelled image
  parts; text-only backend → the same plain text).

## 2. Check these
- `backend/src/spoor/agents/runtime.py` (`_frames`, `_content`), `backend/src/spoor/agents/tools.py` (`key_frames`)
- `backend/src/spoor/api/app.py` (`key_frames`, used by `start_investigation`)
- **Tests:** backend 241 ✓.

## 3. Known issues
- **Not exercised against a live model inside a full investigation yet.** The local backend runs in no-key mode. The
  keyed S2 run will show it: the agent checkpoints list the frames it saw.
- **The image cost** is part of every agent turn (≈ 0.8k tokens per frame on Baseten, from the J2b smoke test). With
  max 3 frames and the existing step budget, it stays within the per-run cap.
