"""Frame-accurate retrieval from the ORIGINAL file. Every citation in Spoor resolves through `extract_frame`."""

from pathlib import Path

from spoor.contracts import FrameRef

from .ffmpeg import MediaToolError, run_ffmpeg
from .probe import FrameTable

# Seek this far before the target, then decode forward to the exact frame (input seeking lands on a keyframe).
_PREROLL_S = 3.0


def frame_ref(media_id: str, table: FrameTable, frame_index: int) -> FrameRef:
    if not 0 <= frame_index < len(table.pts_ms):
        raise IndexError(f"frame {frame_index} out of range (0..{len(table.pts_ms) - 1})")
    return FrameRef(media_id=media_id, pts_ms=table.pts_ms[frame_index], frame_index=frame_index)


def extract_frame(path: Path, table: FrameTable, frame_index: int, fmt: str = "png") -> bytes:
    """Decode exactly frame `frame_index` (presentation order) as an image, rotation applied.

    PNG is lossless so repeated calls return identical bytes for the same frame.
    """
    if not 0 <= frame_index < len(table.pts_ms):
        raise IndexError(f"frame {frame_index} out of range (0..{len(table.pts_ms) - 1})")
    target_s = table.stream_start_s + table.pts_ms[frame_index] / 1000.0
    # Select the first frame at or after the target. Tolerance for timestamp rounding is half the interval to the
    # PREVIOUS frame, so it can never reach back to an earlier frame (matters next to gaps / VFR).
    prev_interval_ms = table.pts_ms[frame_index] - table.pts_ms[frame_index - 1] if frame_index > 0 else 0.2
    tolerance_s = max(prev_interval_ms / 2000.0, 1e-4)
    # Input -ss is relative to the file's start time; with -copyts the select filter sees absolute timestamps.
    seek_s = max(0.0, table.pts_ms[frame_index] / 1000.0 - _PREROLL_S)
    out_args = {
        "png": ["-c:v", "png", "-f", "image2pipe"],
        "jpg": ["-c:v", "mjpeg", "-f", "image2pipe"],
        "rgb": ["-pix_fmt", "rgb24", "-f", "rawvideo"],  # raw pixels, used for exact comparisons
    }[fmt]
    data = run_ffmpeg(
        "-ss", f"{seek_s:.6f}", "-copyts", "-i", str(path),
        "-vf", f"select='gte(t\\,{target_s - tolerance_s:.6f})'",
        "-frames:v", "1", "-fps_mode", "passthrough", *out_args, "pipe:1",
        capture_stdout=True,
    )  # fmt: skip
    if not data:
        raise MediaToolError(f"frame {frame_index} could not be decoded (empty output); refusing to serve a blank frame")
    return data
