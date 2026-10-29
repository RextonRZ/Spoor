"""Smoke 4/5: SAM 3.1 segmentation on an image or tracking across a video, parsed with meta-sam-parser.

Usage:
  uv run python scripts/smoke/sam_segment.py image path/to/frame.jpg "blue equipment case"
  uv run python scripts/smoke/sam_segment.py video path/to/clip.mp4 "blue equipment case"

Video is billed per frame (50-frame minimum) and capped at 15,000 frames — keep smoke clips short.
"""

import asyncio
import base64
import mimetypes
import sys
from collections import Counter
from pathlib import Path

from _common import meta_async_client, record, timed
from meta_sam_parser import (
    SegmentationBoxRecord,
    SegmentationMaskRecord,
    image_segmentation_format,
    parse_responses_stream,
    video_segmentation_format,
)

from spoor.config import get_settings


async def main(kind: str, path: Path, phrase: str) -> None:
    client, model = meta_async_client(), get_settings().sam_model
    file_id = None
    if kind == "video":
        with path.open("rb") as f:
            file_id = (await client.files.create(
                purpose="user_data", file=f, expires_after={"anchor": "created_at", "seconds": 3600}
            )).id
        media = {"type": "input_video", "file_id": file_id}
    else:
        mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        data_url = f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"
        media = {"type": "input_image", "image_url": data_url}

    fmt = video_segmentation_format() if kind == "video" else image_segmentation_format()
    with timed() as t:
        stream = await client.responses.create(
            model=model,
            stream=True,
            metadata={"include_confidence": "true"},
            input=[{"role": "user", "content": [{"type": "input_text", "text": phrase}, media]}],
        )
        result = await parse_responses_stream(stream, fmt).final_result()

    boxes = [r for r in result.records if isinstance(r, SegmentationBoxRecord)]
    masks = [r for r in result.records if isinstance(r, SegmentationMaskRecord)]
    frames_per_object = Counter(b.object_id for b in boxes)
    sample = [
        {"object_id": b.object_id, "frame": b.frame.frame_index if b.frame else 0,
         "box_ltrb_px": [b.left, b.top, b.right, b.bottom], "confidence": b.confidence}
        for b in boxes[:10]
    ]
    record(f"sam_{kind}", {
        "model": model, "media": path.name, "phrase": phrase, **t, "outcome": str(result.outcome),
        "n_boxes": len(boxes), "n_masks": len(masks), "frames_per_object": dict(frames_per_object),
        "sample_boxes": sample, "diagnostics": [str(d) for d in result.diagnostics],
        "raw_output_head": result.raw_output[:2000],
    })
    print(f"outcome={result.outcome} boxes={len(boxes)} masks={len(masks)} objects={dict(frames_per_object)}")
    if file_id:
        await client.files.delete(file_id)


if __name__ == "__main__":
    kind, path, phrase = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
    if kind not in {"image", "video"}:
        sys.exit("first arg must be 'image' or 'video'")
    asyncio.run(main(kind, path, phrase))
