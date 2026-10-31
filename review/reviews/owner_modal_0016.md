# OWNER 00:16 Sat 31 Oct (Rexton): Modal is being added ($30 credit) — use it for the CCTV render

Why: the full batch at 2688×1520 is ~45 h on the laptop and does not fit before Nov 4. Modal GPUs in parallel could
cut it to a few hours.

Rules (keys / spend):
- Rexton logs in himself (`modal token new`). Never read, copy, print or commit the Modal token or any key.
- Hard budget: the 1-clip test ≤ US$2. The full batch only after the test is reviewed AND Rexton says go; plan it to fit
  inside the $30 credit with margin (print the estimate first: GPU type, $/h, frames, s/frame, parallelism).
- Credit as a tool in docs; nothing user-facing claims Modal ran the AI.

Do (after the S2 actor-on-mocap item; prepare the code while other things render):
1. `assets/hub/modal_render.py`: a Modal app that ships the .blend + assets (or a volume), runs Blender 5.x headless
   on a GPU (L4 or A10G), renders a frame range, and returns the frames; one container per camera / frame chunk.
2. **Check EEVEE works headless on Modal** (EGL / Vulkan in the container). If EEVEE won't run, report it — do NOT switch
   the final look to Cycles without a review (it changes the look and cost).
3. Test: S2 CAM_01, 30 frames at 2688×1520. Proof = frames diffed against the same frames rendered locally (pixel
   difference stats + a side-by-side sheet), s/frame, cost. Send as a request.
4. Fallback if rendering does not work: use Modal for SAM 3.1 video tracking over the rendered clips instead
   (only if the Meta Model API does not cover video tracking).

## Update 01:42 (Rexton): Modal secret name
If Glimmer weights need a Hugging Face token, it is the Modal secret **`huggingface-secret`** (env HF_TOKEN). Reference it by name (`modal.Secret.from_name("huggingface-secret")`); never print it. The render test needs no secret.
