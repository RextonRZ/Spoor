"""Inference cache keys (PRD §12, §32.1): identical inputs never pay twice."""

import hashlib
import json


def inference_cache_key(
    *,
    source_sha256: str,
    model_id: str,
    prompt_version: str,
    prompt: str,
    settings: dict | None = None,
    clip_window_ms: tuple[float, float] | None = None,
    calibration_id: str | None = None,
) -> str:
    payload = {
        "source_sha256": source_sha256,
        "model_id": model_id,
        "prompt_version": prompt_version,
        "prompt": prompt,
        "settings": settings or {},
        "clip_window_ms": list(clip_window_ms) if clip_window_ms else None,
        "calibration_id": calibration_id,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
