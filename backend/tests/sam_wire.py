"""TEST-ONLY: synthesize Responses API event streams in the documented SAM 3.1 wire format so the real
meta-sam-parser path can be exercised without an API key. These are fixtures, never presented as inference."""

from meta_sam_parser._mask_codec import _encode_raster


def mask_token(h: int = 4, w: int = 5, fill: float = 1.0, conf: float | None = None) -> str:
    ones = round(h * w * fill)
    payload = _encode_raster(bytes([1] * ones + [0] * (h * w - ones)), w, h)
    c = f";c={conf}" if conf is not None else ""
    return f"<|mask;x=0;y=0{c};data={h},{w},{payload}|>"


def record(object_id: int, box_inclusive: tuple[int, int, int, int], frame_wh: tuple[int, int],
           conf: float | None = None, fill: float = 1.0) -> str:  # fmt: skip
    x1, y1, x2, y2 = box_inclusive
    w, h = frame_wh
    c = f";c={conf}" if conf is not None else ""
    return f"{object_id}<|box;x1={x1};y1={y1};x2={x2};y2={y2};w={w};h={h}{c}|>" + mask_token(fill=fill, conf=conf)


def line(frame: int, *records: str) -> str:
    return f"<{frame}f>" + ",".join(records)


def events(lines: list[str], response_id: str = "resp_fixture") -> list[dict]:
    text = "".join(f"{ln}\n" for ln in lines)
    item = {"id": "msg_fixture", "type": "message", "role": "assistant"}
    ev = [
        {"type": "response.created", "response": {"id": response_id, "status": "in_progress"}},
        {"type": "response.output_item.added", "output_index": 0, "item": {**item, "content": []}},
        {"type": "response.content_part.added", "output_index": 0, "content_index": 0, "item_id": "msg_fixture",
         "part": {"type": "output_text", "text": ""}},
    ]  # fmt: skip
    ev += [{"type": "response.output_text.delta", "delta": f"{ln}\n", "output_index": 0, "content_index": 0,
            "item_id": "msg_fixture"} for ln in lines]  # fmt: skip
    ev += [
        {"type": "response.output_text.done", "text": text, "output_index": 0, "content_index": 0,
         "item_id": "msg_fixture"},
        {"type": "response.content_part.done", "output_index": 0, "content_index": 0, "item_id": "msg_fixture",
         "part": {"type": "output_text", "text": text}},
        {"type": "response.output_item.done", "output_index": 0,
         "item": {**item, "content": [{"type": "output_text", "text": text}]}},
        {"type": "response.completed", "response": {"id": response_id, "status": "completed"}},
    ]  # fmt: skip
    return ev


async def stream(evs: list[dict]):
    for e in evs:
        yield e
