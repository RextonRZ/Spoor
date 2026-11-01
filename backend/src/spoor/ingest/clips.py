"""Frame-exact sub-clips of a working proxy (for bounded model questions and SAM's 15,000-frame limit).

A cut is verified: its frame count must equal the requested range, otherwise every model timestamp mapped back through
it would be silently shifted.
"""

import bisect
from dataclasses import dataclass
from pathlib import Path

from .ffmpeg import run_ffmpeg
from .probe import FrameTable, probe
from .storage import sha256_file


class ClipCutError(RuntimeError):
    pass


@dataclass(frozen=True)
class ClipWindow:
    path: Path
    sha256: str
    start_frame: int
    end_frame: int  # inclusive
    start_pts_ms: float
    end_pts_ms: float
    source_media_id: str
    pts_ms: tuple[float, ...] = ()  # timestamps of the cut frames in the source the clip was cut from

    @property
    def n_frames(self) -> int:
        return self.end_frame - self.start_frame + 1

    def to_original(self, t_s: float) -> int | None:
        """Model-reported seconds-from-clip-start -> frame index (identical in proxy and original), or None if the
        time is outside the window. Uses the cut's own timestamps, so a different start offset cannot shift it."""
        if t_s < 0:
            return None
        pts = self.start_pts_ms + t_s * 1000.0
        if pts > self.end_pts_ms + 1:
            return None
        return self.start_frame + bisect.bisect_right(self.pts_ms, pts + 1e-6) - 1


def cut_frames(source: Path, table: FrameTable, *, source_media_id: str, start_frame: int, end_frame: int,
               out_dir: Path) -> ClipWindow:  # fmt: skip
    if not 0 <= start_frame <= end_frame < len(table.pts_ms):
        raise ValueError(f"frame range {start_frame}..{end_frame} outside 0..{len(table.pts_ms) - 1}")
    start_pts, end_pts = table.pts_ms[start_frame], table.pts_ms[end_frame]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{source_media_id}_{start_frame}_{end_frame}.mp4"
    expected = end_frame - start_frame + 1
    if not out.exists():
        tmp = out.with_suffix(".part.mp4")
        run_ffmpeg(
            "-y", "-ss", f"{start_pts / 1000.0:.6f}", "-i", str(source),  # relative to the file start
            "-frames:v", str(expected), "-an", "-sn", "-dn", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-fps_mode", "passthrough", "-movflags", "+faststart", str(tmp),
        )  # fmt: skip
        got = len(probe(tmp)[1].pts_ms)
        if got != expected:
            tmp.unlink(missing_ok=True)
            raise ClipCutError(f"cut produced {got} frames, expected {expected}; refusing a misaligned clip")
        tmp.replace(out)
    return ClipWindow(out, sha256_file(out), start_frame, end_frame, start_pts, end_pts, source_media_id,
                      tuple(table.pts_ms[start_frame:end_frame + 1]))


def cut_clip(source: Path, table: FrameTable, *, source_media_id: str, start_ms: float, end_ms: float,
             out_dir: Path) -> ClipWindow:  # fmt: skip
    if end_ms <= start_ms:
        raise ValueError("empty clip window")
    start_frame = table.index_at(max(start_ms, table.pts_ms[0]))
    end_frame = table.index_at(min(end_ms, table.pts_ms[-1]))
    return cut_frames(source, table, source_media_id=source_media_id, start_frame=start_frame, end_frame=end_frame,
                      out_dir=out_dir)  # fmt: skip


def frame_chunks(n_frames: int, max_frames: int) -> list[tuple[int, int]]:
    """Contiguous inclusive ranges of at most `max_frames` (no overlap, so no frame is observed twice)."""
    return [(s, min(s + max_frames, n_frames) - 1) for s in range(0, n_frames, max_frames)]


def crop_window(window: ClipWindow, box_ltrb_px: tuple[int, int, int, int], *, out_width_px: int = 960) -> ClipWindow:
    """The same frames, cropped to one region and enlarged (a person far from a high camera is a few dozen pixels:
    a model sees the hands better this way). Timing is untouched, so answers still map to exact frames."""
    left, top, right, bottom = (int(v) for v in box_ltrb_px)
    w, h = (right - left) // 2 * 2, (bottom - top) // 2 * 2
    if w < 8 or h < 8:
        raise ValueError(f"crop {box_ltrb_px} is too small")
    out = window.path.with_name(f"{window.path.stem}_crop{left}-{top}-{w}x{h}.mp4")
    if not out.exists():
        tmp = out.with_suffix(".part.mp4")
        run_ffmpeg("-y", "-i", str(window.path), "-vf", f"crop={w}:{h}:{left}:{top},scale={out_width_px}:-2:flags=lanczos",
                   "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p",
                   "-fps_mode", "passthrough", "-movflags", "+faststart", str(tmp))  # fmt: skip
        if (got := len(probe(tmp)[1].pts_ms)) != window.n_frames:
            tmp.unlink(missing_ok=True)
            raise ClipCutError(f"crop produced {got} frames, expected {window.n_frames}")
        tmp.replace(out)
    return ClipWindow(out, sha256_file(out), window.start_frame, window.end_frame, window.start_pts_ms,
                      window.end_pts_ms, window.source_media_id, window.pts_ms)
