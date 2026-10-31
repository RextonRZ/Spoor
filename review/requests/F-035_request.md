# F-035 — J2a reasoning split + J2b images for the open-weights model (Baseten Muse Spark Open)

From the frontend agent.

## 1. Changed since last request

### J2a — `BasetenChatBackend` (`backend/src/spoor/reasoning/backends.py`)
- **`split_reasoning(message)`.** Muse Spark Open's reasoning arrives either as `reasoning_content` / `reasoning` or
  inline as `<think>…</think>`. It is kept apart, and **only the answer goes to the JSON validator** (and to the repair
  loop).
- **`BackendReply.reasoning_chars`** records how much reasoning there was: the length only, never the text.
- The agent runtime writes it into each `model_output` checkpoint (`agents/runtime.py`).
- Tests (parametrized: separate field and inline `<think>`): the answer validates, `reasoning_chars > 10`, and no
  `<think>` reaches `raw`.

### J2b — evidence pictures to the open-weights model
- **The backend accepts image parts.** `input_image` (data URL or URL) becomes OpenAI-style `image_url` content next to
  the text. Video is still refused: "route video questions to Muse Spark on Meta".
- **Test:** a text + image request reaches Baseten as `[{"type":"text",…},{"type":"image_url",…}]`.
- **Real smoke test** (`scripts/smoke/baseten_vision.py`): one call with the CAM_10 frame at the C04 divert time
  (synthetic, 960×540).
  - **Result:** 862 in / 1,877 out tokens, 12.8 s. A valid JSON answer: 32 parcels, 4 people, chutes visible, a plain
    description, and a "cannot tell" list ("exact count …", "what happened before or after this single frame …").
  - **Proof** (redacted, with response id): `docs/open_weights_proof/2026-10-31_j2b_baseten_vision.json`.
  - **Cost:** Baseten running total ≈ 4.5k tokens (cap $50); Meta unchanged at ≈ $0.12. Both are in FOR_REXTON.md.
- **Still to wire (next):** the agents attach the key frames automatically: the last confirmed frame, the
  missing-moment frames, and the CAM_19 doorway in S2. The model, provider and request ids are recorded with each run.

### Note for the builder (found by the open-weights model)
- On the old QA render CAM_10 frame 248 (14:32:31.8), the model describes "one person in a yellow high-visibility vest
  **lying on the floor** on the right side near a chute". It may be an old take, but please check for a worker pose
  collapsing to the floor in that clip.

## 2. Check these
- `backend/src/spoor/reasoning/backends.py` (`split_reasoning`, `_chat_parts`), `backend/src/spoor/agents/runtime.py`
- `backend/tests/test_reasoning.py`: 3 new tests.
- `backend/scripts/smoke/baseten_vision.py`, `docs/open_weights_proof/2026-10-31_j2b_baseten_vision.json`
- Tests: agents + reasoning 21 ✓.
