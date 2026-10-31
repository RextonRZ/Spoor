# F-043 — J6 Muse Glimmer on Modal: ready to run, asking before spending shared Modal money

From the frontend agent.

## 1. Changed since last request
- **`backend/scripts/modal/glimmer_triage.py`**, a Modal app, not yet run.
  - **Facts** (from the HF model card `meta-models/Muse-Glimmer-30B`, 31 Oct): Apache 2.0, not gated; dense, about
    29.6B parameters, with a perception encoder; text and image input, video as frames; BF16 weights 59.6 GB, needing
    about 64 GB of VRAM; `vllm serve` supported, images passed as `image_url`.
  - **Download:** a CPU-only function pulls the weights into a Modal Volume `spoor-glimmer-weights` once, so no GPU
    time is spent downloading. Storage is free under 1 TiB.
  - **Triage:** the GPU function runs on an **A100 80 GB**, $0.000694/s per modal.com/pricing. It loads Glimmer with
    vLLM (`max_model_len` 16k, one image per prompt) and asks, per sampled frame (1 fps), for JSON `{handling, what,
    people}`: is a person picking up, carrying, putting down or removing a parcel? Parcels riding a belt don't count.
  - **Run settings:** temperature 0 for deterministic triage, and "Reasoning strength: low" as the card describes.
  - **Output:** a proof file `docs/open_weights_proof/<date>_j6_glimmer_triage.json` with model, GPU, vLLM version,
    load and inference seconds, wall time, a cost upper bound, and every frame's flag and raw reply. It is labelled
    "triage flags, not evidence".
  - **Cost guard:** it prints the estimate first. The GPU timeout is 25 min, so a run costs at most **$1.04**. It
    refuses if that ceiling would exceed the $3 cap or there are more than 120 frames.
  - The local frame sampling has been dry-run on a synthetic 30 s clip: 30 frames, no Modal call. It runs with
    `uv run --with modal …` in the backend environment. The Modal token stays Rexton's; I never read it.
- **Estimate for the test:** download ≈ $0.05 of CPU; GPU about 10 min (load + 40 frames) ≈ **$0.42**, ceiling $1.04.
  Total **≤ about $1.1**, under the $3 J6 cap.

## 2. Check these
- `backend/scripts/modal/glimmer_triage.py`

## 3. Questions
- **OK to run the J6 test now?** The queue lists the builder's Modal render test (≤ $2) first, and it hasn't run
  yet (log 01:56: prep only). The budget is shared ($30). If you say go, I run the download, then one triage pass on
  a synthetic clip (CAM_10 or CAM_07 QA, 30–40 frames), and log before and after.
- After the test, I plan to wire the flags into the backend as a per-camera "Glimmer flagged" lane, so only flagged
  windows are offered to Spark/SAM. Say if you want that kept to the proof only.
