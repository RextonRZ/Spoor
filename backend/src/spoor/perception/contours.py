"""SAM's mask edge for a track (the outline drawn on screen): SAM 3.1 returns a mask with every box (box-local raster,
lossless); the pipeline keeps the box and the mask's fill. The masks stay in the cached raw output, so a track's
contour is recovered from there: each cached box is paired with the mask that follows it, matched to the track's own
boxes (same frame size, within a pixel), decoded and traced to a polygon in frame pixels."""

import json
import re
from pathlib import Path

import cv2
import numpy as np
from meta_sam_parser import decode_mask_to_raster
from meta_sam_parser._types import SegmentationMask

TOKEN = re.compile(r"<\|box;x1=([\d.]+);y1=([\d.]+);x2=([\d.]+);y2=([\d.]+);w=\d+;h=\d+;c=[\d.]+\|>"
                   r"(?:<\|mask;x=(\d+);y=(\d+);c=[\d.]+;data=(\d+),(\d+),([~!][^|]*)\|>)?")


def polygon(box: tuple[float, ...], mx: int, my: int, h: int, w: int, payload: str) -> list[list[float]] | None:
    """The mask's outer edge in frame pixels (largest contour, lightly simplified)."""
    raster = decode_mask_to_raster(SegmentationMask("lossless" if payload[0] == "~" else "one_bit", payload, w, h))
    img = (np.frombuffer(bytes(raster), np.uint8).reshape(h, w) > 0).astype(np.uint8) * 255
    found, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not found:
        return None
    c = cv2.approxPolyDP(max(found, key=cv2.contourArea), 0.8, True).reshape(-1, 2)
    sx, sy = (box[2] - box[0]) / w, (box[3] - box[1]) / h  # the raster spans the box
    return [[float(round(box[0] + (mx + x) * sx, 1)), float(round(box[1] + (my + y) * sy, 1))] for x, y in c]


def contours_for(boxes: list[tuple[int, tuple[float, ...]]], cache_files: list[Path]) -> dict[int, list[list[float]]]:
    """{frame_index: polygon} for the track's (frame_index, box) pairs, from SAM's cached outputs of this clip."""
    want = {f: b for f, b in boxes}
    out: dict[int, list[list[float]]] = {}
    for path in cache_files:
        try:
            raw = json.loads(path.read_text(encoding="utf-8")).get("raw_output") or ""
        except (OSError, ValueError):
            continue
        for t in TOKEN.finditer(raw):
            if t.group(9) is None:
                continue
            box = tuple(float(v) for v in t.group(1, 2, 3, 4))
            for f, b in want.items():
                if f not in out and all(abs(box[i] - b[i]) <= 1.5 for i in range(4)):
                    try:
                        poly = polygon(b, int(t.group(5)), int(t.group(6)), int(t.group(7)), int(t.group(8)), t.group(9))
                    except Exception:  # noqa: BLE001 - a mask that does not decode keeps the box
                        poly = None
                    if poly:
                        out[f] = poly
                    break
        if len(out) == len(want):
            break
    return dict(sorted(out.items()))
