"""J6: Muse Glimmer (open weights, Apache 2.0) on a Modal GPU as on-site camera triage.

Idea (docs/PRIZE_STRATEGY.md): a hub runs Glimmer on its own hardware next to the recorder; it looks at sampled frames
of every camera and flags only parcel-handling moments, so raw CCTV never leaves the site and only flagged clips go to
the Model API (Spark / SAM). Modal stands in for "the hub's own GPU" in this test.

Facts used (huggingface.co/meta-models/Muse-Glimmer-30B, 31 Oct 2026): dense ~29.6B, text + image input (video as
frames), BF16 weights 59.6 GB (~64 GB VRAM), not gated, `vllm serve` supported, images as `image_url` content.
GPU: A100 80 GB at $0.000694/s (modal.com/pricing). Weights are downloaded once by a CPU-only function into a Volume,
so the GPU bills only for loading + inference. The GPU function has a 25 min timeout: at most $1.04 per run.

Usage (from backend/, after `modal token new` by Rexton; the agents never read the token):
  uv run --with modal modal run scripts/modal/glimmer_triage.py::download   # CPU only, ~60 GB into the Volume
  uv run --with modal modal run scripts/modal/glimmer_triage.py --clip <synthetic.mp4> --fps 1 --seconds 40
Input must be SYNTHETIC footage. The output (flags per frame + timings + versions) is written to
docs/open_weights_proof/ as proof that the open-weights model ran. Flags are triage, never evidence.
"""

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import modal

MODEL = "meta-models/Muse-Glimmer-30B"
GPU = "A100-80GB"
GPU_USD_PER_S = 0.000694
GPU_TIMEOUT_S = 25 * 60
CAP_USD = 3.00  # owner cap for the Glimmer test (QUEUE J6)

app = modal.App("spoor-glimmer-triage")
weights = modal.Volume.from_name("spoor-glimmer-weights", create_if_missing=True)
dl_image = modal.Image.debian_slim(python_version="3.12").pip_install("huggingface_hub[hf_transfer]").env(
    {"HF_HUB_ENABLE_HF_TRANSFER": "1"}
)
gpu_image = modal.Image.debian_slim(python_version="3.12").pip_install("vllm").env(
    {"VLLM_USE_FLASHINFER_SAMPLER": "0"}  # (first run 31 Oct: FlashInfer JIT-compiles its sampler at warm-up and
)  # this slim image has no nvcc - "Could not find nvcc"; the model had loaded and its CUDA graphs were captured)

SYSTEM = ("Reasoning strength: low\nYou watch one CCTV frame from a parcel sorting hub (synthetic footage). Reply with "
          'JSON only: {"handling": true|false, "what": "<at most 12 words>", "people": <int>}. handling = a person is '
          "picking up, carrying, putting down or removing a parcel, or a parcel is leaving a conveyor or chute by hand. "
          'Parcels riding a belt with nobody touching them are not handling. If unsure, handling=false, what="unclear".')  # fmt: skip


@app.function(image=dl_image, volumes={"/w": weights}, timeout=3600, cpu=4)
def download() -> dict:
    from huggingface_hub import snapshot_download

    t = time.time()
    path = snapshot_download(MODEL, local_dir="/w/glimmer")
    weights.commit()
    size = sum(f.stat().st_size for f in Path(path).rglob("*") if f.is_file())
    return {"path": path, "gb": round(size / 1e9, 1), "seconds": round(time.time() - t)}


@app.function(image=gpu_image, gpu=GPU, volumes={"/w": weights}, timeout=GPU_TIMEOUT_S)
def triage(frames: list[tuple[float, str]]) -> dict:
    """frames: (t seconds, JPEG data URL). Returns per-frame flags, raw replies, timings and versions."""
    import vllm
    from vllm import LLM, SamplingParams

    t0 = time.time()
    llm = LLM(model="/w/glimmer", max_model_len=16384, limit_mm_per_prompt={"image": 1}, gpu_memory_utilization=0.92)
    t_load = time.time() - t0
    convs = [[{"role": "system", "content": SYSTEM},
              {"role": "user", "content": [{"type": "image_url", "image_url": {"url": url}},
                                           {"type": "text", "text": "Is a parcel being handled in this frame?"}]}]
             for _, url in frames]  # fmt: skip
    t1 = time.time()
    # (first run 31 Oct: 160 tokens ran out inside the model's reasoning channel, before its JSON)
    outs = llm.chat(convs, SamplingParams(temperature=0.0, max_tokens=900))  # deterministic triage
    t_inf = time.time() - t1
    rows = []
    for (t, _), o in zip(frames, outs, strict=True):
        raw = o.outputs[0].text.strip()
        try:
            j = _last_json(raw)
            rows.append({"t_s": t, "handling": bool(j.get("handling")), "what": str(j.get("what", ""))[:120],
                         "people": j.get("people"), "raw": raw[-400:]})  # fmt: skip
        except ValueError:
            rows.append({"t_s": t, "handling": None, "what": "unparsed", "people": None, "raw": raw[-400:]})
    return {"rows": rows, "load_s": round(t_load, 1), "inference_s": round(t_inf, 1), "vllm": vllm.__version__}


def _last_json(raw: str) -> dict:
    """The reply's final JSON object: the model reasons first and echoes the asked-for template ({"handling":
    true|false, ...}) on the way, so the first brace is not the answer (first run 31 Oct: 12/12 unparsed)."""
    for i in range(len(raw) - 1, -1, -1):
        if raw[i] != "{":
            continue
        depth = 0
        for k in range(i, len(raw)):
            depth += {"{": 1, "}": -1}.get(raw[k], 0)
            if depth == 0:
                try:
                    j = json.loads(raw[i : k + 1])
                    if isinstance(j, dict) and "handling" in j:
                        return j
                except ValueError:
                    pass
                break
    raise ValueError("no JSON answer")


def sample(clip: str, fps: float, seconds: float) -> list[tuple[float, str]]:
    import base64

    import cv2

    cap = cv2.VideoCapture(clip)
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
    out, t = [], 0.0
    while t < seconds:
        cap.set(cv2.CAP_PROP_POS_FRAMES, round(t * src_fps))
        ok, img = cap.read()
        if not ok:
            break
        ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        out.append((round(t, 2), "data:image/jpeg;base64," + base64.b64encode(jpg.tobytes()).decode()))
        t += 1.0 / fps
    return out


@app.local_entrypoint()
def main(clip: str, fps: float = 1.0, seconds: float = 40.0):
    frames = sample(clip, fps, seconds)
    worst = GPU_TIMEOUT_S * GPU_USD_PER_S
    print(f"estimate: {len(frames)} frames on {GPU}; ~10 min GPU ≈ ${600 * GPU_USD_PER_S:.2f}; "
          f"hard ceiling (timeout) ${worst:.2f}; cap ${CAP_USD:.2f}")  # fmt: skip
    if worst > CAP_USD or len(frames) > 120:
        raise SystemExit("refusing: over the J6 cap")
    t = time.time()
    res = triage.remote(frames)
    wall = time.time() - t
    flagged = [r for r in res["rows"] if r["handling"]]
    proof = {"test": "j6_glimmer_triage", "run_at_utc": datetime.now(UTC).isoformat(), "model": MODEL,
             "weights": "BF16 from Hugging Face (Apache 2.0)", "provider": "modal", "gpu": GPU, "vllm": res["vllm"],
             "input": {"clip": Path(clip).name, "label": "SYNTHETIC footage", "fps": fps, "frames": len(frames)},
             "load_s": res["load_s"], "inference_s": res["inference_s"], "wall_s": round(wall, 1),
             "usd_upper_bound": round(wall * GPU_USD_PER_S, 3), "flagged": len(flagged), "rows": res["rows"],
             "label": "triage flags, not evidence: only flagged moments would go to the Model API"}  # fmt: skip
    out = Path(__file__).resolve().parents[3] / "docs" / "open_weights_proof" / f"{datetime.now(UTC):%Y-%m-%d}_j6_glimmer_triage.json"
    out.write_text(json.dumps(proof, indent=2))
    print(f"actual: wall {wall:.0f} s (load {res['load_s']} s, inference {res['inference_s']} s) ≤ ${wall * GPU_USD_PER_S:.2f}; "
          f"{len(flagged)}/{len(frames)} frames flagged; proof {out}")  # fmt: skip


@app.local_entrypoint()
def hub(clips: str, every_s: float = 2.0, seconds: float = 90.0, out: str = ""):
    """Every camera of a scenario (CAM_XX.mp4 in `clips`): one frame every `every_s` over `seconds`, split over two GPU
    calls that run in parallel (each well inside the 25 min timeout). Writes the proof record and triage_flags
    {camera_id: [{t_s, what}]} for the investigation run. Flags are triage only, never evidence."""
    paths = sorted(Path(clips).glob("CAM_*.mp4"))
    frames = [(p.stem, t, url) for p in paths for t, url in sample(str(p), 1.0 / every_s, seconds)]
    worst = 2 * GPU_TIMEOUT_S * GPU_USD_PER_S
    print(f"estimate: {len(frames)} frames from {len(paths)} cameras, 2 parallel calls on {GPU}; "
          f"worst case (both hit the timeout) ${worst:.2f}; cap ${CAP_USD:.2f}")  # fmt: skip
    if worst > CAP_USD:
        raise SystemExit("refusing: over the Glimmer cap")
    half = sorted({c for c, _, _ in frames})
    groups = [[f for f in frames if f[0] in half[: len(half) // 2 + 1]], [f for f in frames if f[0] in half[len(half) // 2 + 1:]]]
    t = time.time()
    results = list(triage.map([[(f"{c}@{s}", u) for c, s, u in g] for g in groups]))
    wall = time.time() - t
    rows = [dict(r, camera=r["t_s"].split("@")[0], t_s=float(r["t_s"].split("@")[1])) for res in results for r in res["rows"]]
    gpu_s = sum(r["load_s"] + r["inference_s"] for r in results)
    flags: dict[str, list] = {}
    for r in rows:
        if r["handling"]:
            flags.setdefault(f"cam_{r['camera']}", []).append({"t_s": r["t_s"], "what": r["what"]})
    proof = {"test": "glimmer_triage_hub", "run_at_utc": datetime.now(UTC).isoformat(), "model": MODEL,
             "weights": "BF16 from Hugging Face (Apache 2.0)", "provider": "modal", "gpu": GPU,
             "vllm": results[0]["vllm"], "input": {"clips": [p.name for p in paths], "label": "SYNTHETIC footage",
                                                  "every_s": every_s, "seconds": seconds, "frames": len(frames)},
             "calls": [{"load_s": r["load_s"], "inference_s": r["inference_s"]} for r in results],
             "wall_s": round(wall, 1), "usd_upper_bound": round(wall * 2 * GPU_USD_PER_S, 3),
             "usd_gpu_seconds": round(gpu_s * GPU_USD_PER_S, 3), "triage_flags": flags,
             "unparsed": sum(1 for r in rows if r["handling"] is None), "rows": rows,
             "label": "triage flags, not evidence: only flagged moments would go to the Model API"}  # fmt: skip
    dest = Path(out) if out else Path(__file__).resolve().parents[3] / "docs" / "open_weights_proof" / \
        f"{datetime.now(UTC):%Y-%m-%d}_glimmer_triage_hub.json"  # fmt: skip
    from spoor.forensics.triage import from_proof, summary  # local entrypoint only (the backend's package)

    sent = summary(from_proof(proof))  # what leaves the hub: seconds, padded one sample each side, not cameras
    proof["sent"] = {k: sent[k] for k in ("pad_s", "sent_s", "total_s", "sent_share", "cameras_flagged", "cameras", "windows")}
    dest.write_text(json.dumps(proof, indent=2))
    print(f"sent to the cloud: {sent['sent_s']:.0f} s of {sent['total_s']:.0f} s ({100 * sent['sent_share']:.1f}%)")
    print(f"actual: wall {wall:.0f} s, GPU {gpu_s:.0f} s ≈ ${gpu_s * GPU_USD_PER_S:.2f} (upper bound ${wall * 2 * GPU_USD_PER_S:.2f}); "
          f"flagged {sum(len(v) for v in flags.values())} frames on {len(flags)}/{len(paths)} cameras; "
          f"{proof['unparsed']} unparsed; proof {dest}")  # fmt: skip
