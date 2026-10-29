"""Bounded clip windows for model questions (PRD §15.3). Model times are relative to the window; we map them back
to original frame indices ourselves and record what was NOT inspected."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from spoor.ingest.clips import ClipWindow, cut_clip

__all__ = ["ClipWindow", "cut_clip", "uploaded"]


@contextmanager
def uploaded(client: Any, path: Path, ttl_s: int = 3600) -> Iterator[str]:
    """Upload a clip to the Meta Files API for one question; it expires after `ttl_s` and is deleted after use."""
    with path.open("rb") as f:
        file_id = client.files.create(purpose="user_data", file=f,
                                      expires_after={"anchor": "created_at", "seconds": ttl_s}).id  # fmt: skip
    try:
        yield file_id
    finally:
        client.files.delete(file_id)
