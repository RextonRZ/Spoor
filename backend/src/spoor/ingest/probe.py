"""Read container/stream facts and the per-frame timestamp table (PRD §8.3, §12).

The frame table maps `frame_index` (presentation order) to `pts_ms` relative to the stream start. It is the
authority for every FrameRef: we never assume the same frame index means the same instant across cameras, and we
never assume constant frame rate.
"""

import bisect
import statistics
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from itertools import pairwise
from pathlib import Path

from spoor.contracts import MediaProbe

from .ffmpeg import MediaToolError, run_ffprobe


class UnsupportedMediaError(ValueError):
    pass


def _rate(value: str | None) -> float | None:
    if not value or value in ("0/0", "0"):
        return None
    r = Fraction(value)
    return float(r) if r else None


def _rotation(stream: dict) -> int:
    for side in stream.get("side_data_list", []) or []:
        if "rotation" in side:
            return round(float(side["rotation"])) % 360
    tag = (stream.get("tags") or {}).get("rotate")
    return int(tag) % 360 if tag else 0


def _creation_time(fmt: dict, stream: dict) -> datetime | None:
    raw = (stream.get("tags") or {}).get("creation_time") or (fmt.get("tags") or {}).get("creation_time")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return dt if dt.tzinfo else None


@dataclass(frozen=True)
class FrameTable:
    """`pts_ms[i]` is frame i's presentation time in ms after `stream_start_s` (the first frame's PTS)."""

    stream_start_s: float
    pts_ms: list[float]

    def to_json(self) -> dict:
        return {"stream_start_s": self.stream_start_s, "pts_ms": self.pts_ms}

    @classmethod
    def from_json(cls, data: dict) -> "FrameTable":
        return cls(stream_start_s=data["stream_start_s"], pts_ms=list(data["pts_ms"]))

    def index_at(self, pts_ms: float) -> int:
        """Index of the last frame presented at or before `pts_ms`."""
        i = bisect.bisect_right(self.pts_ms, pts_ms + 1e-6) - 1
        if i < 0:
            raise IndexError(f"pts {pts_ms} ms precedes the first frame")
        return i


def frame_table(path: Path) -> tuple[FrameTable | None, list[str]]:
    """Presentation-ordered frame timestamps (ms from stream start) and timing flags."""
    data = run_ffprobe(path, "-select_streams", "v:0", "-show_entries", "packet=pts_time,dts_time")
    packets = data.get("packets", [])
    flags: list[str] = []
    pts = []
    missing = 0
    for p in packets:
        t = p.get("pts_time")
        if t in (None, "N/A"):
            missing += 1
            continue
        pts.append(float(t))
    if missing:
        flags.append("missing_pts")
    if not pts:
        return None, [*flags, "no_timestamps"]

    dts = [float(p["dts_time"]) for p in packets if p.get("dts_time") not in (None, "N/A")]
    if any(b < a for a, b in pairwise(dts)):
        flags.append("non_monotonic_dts")

    pts.sort()
    if len(set(pts)) != len(pts):
        flags.append("duplicate_pts")
    start = pts[0]
    table = [round((t - start) * 1000.0, 3) for t in pts]

    deltas = [b - a for a, b in pairwise(table) if b > a]
    if deltas:
        med = statistics.median(deltas)
        if any(d > 1.5 * med for d in deltas):
            flags.append("frame_gap")  # dropped frames or a recording pause
        if max(deltas) - min(deltas) > 0.25 * med:
            flags.append("variable_frame_rate")
    return FrameTable(stream_start_s=start, pts_ms=table), flags


def probe(path: Path) -> tuple[MediaProbe, FrameTable]:
    try:
        data = run_ffprobe(path, "-show_format", "-show_streams")
    except MediaToolError as e:
        raise UnsupportedMediaError(f"unreadable media: {e}") from e

    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise UnsupportedMediaError("no video stream")
    fmt = data.get("format", {})

    table, flags = frame_table(path)
    if table is None:
        raise UnsupportedMediaError("video stream has no decodable frame timestamps")

    rotation = _rotation(video)
    if rotation:
        flags.append("rotated")
    avg_fps, nominal_fps = _rate(video.get("avg_frame_rate")), _rate(video.get("r_frame_rate"))
    duration_s = float(video.get("duration") or fmt.get("duration") or 0.0)

    result = MediaProbe(
        container=fmt.get("format_name", "unknown"),
        video_codec=video.get("codec_name", "unknown"),
        width_px=int(video["width"]),
        height_px=int(video["height"]),
        rotation_deg=rotation,
        duration_ms=round(duration_s * 1000.0, 3),
        avg_fps=avg_fps,
        nominal_fps=nominal_fps,
        variable_frame_rate="variable_frame_rate" in flags,
        frame_count=len(table.pts_ms),
        time_base=video.get("time_base"),
        has_audio=any(s.get("codec_type") == "audio" for s in streams),
        creation_time_utc=_creation_time(fmt, video),
        flags=sorted(set(flags)),
    )
    return result, table
