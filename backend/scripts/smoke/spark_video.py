"""Smoke 3: upload an owned staged MP4 via the Files API and ask Muse Spark 1.3 a bounded presence question.

Usage: uv run python scripts/smoke/spark_video.py path/to/clip.mp4 "blue equipment case"

Only run on footage you own and have consent for (PRD §7.1). The uploaded file expires after 1 hour.
"""

import sys
from pathlib import Path

from _common import meta_client, record, timed, usage_of

from spoor.config import get_settings

clip, target = Path(sys.argv[1]), sys.argv[2]
client, model = meta_client(), get_settings().spark_model

with timed() as up, clip.open("rb") as f:
    uploaded = client.files.create(
        purpose="user_data", file=f, expires_after={"anchor": "created_at", "seconds": 3600}
    )

question = (
    f'Is a "{target}" visible in this clip? If yes, give the approximate time(s) in seconds where it is clearly '
    "visible and where it stops being visible. Describe only what is visible; if you cannot tell, say not_observable."
)
with timed() as inf:
    resp = client.responses.create(
        model=model,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": question},
                {"type": "input_video", "file_id": uploaded.id},
            ],
        }],
    )

record("spark_video", {
    "model": model, "response_model": resp.model, "response_id": resp.id, "clip": clip.name,
    "clip_bytes": clip.stat().st_size, "file_id": uploaded.id, "upload_latency_s": up["latency_s"],
    "inference_latency_s": inf["latency_s"], "usage": usage_of(resp), "answer": resp.output_text,
})
print(resp.output_text)
client.files.delete(uploaded.id)
