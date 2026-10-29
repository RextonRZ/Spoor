"""Ingest pipeline (PRD §12): authorize -> store original -> hash -> probe -> working proxy -> manifest.

Idempotent: re-ingesting identical bytes returns the existing manifest without new files.
"""

import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from spoor.contracts import AssetKind, MediaAsset, MediaAuthorization, MediaProbe

from .ffmpeg import run_ffmpeg, tool_version
from .probe import FrameTable, UnsupportedMediaError, probe
from .storage import MediaStore

MAX_UPLOAD_BYTES = 1 << 30  # Meta Files API limit is 1 GiB (dev.meta.ai/docs/file-handling)
PROXY_METHOD = "proxy_h264_v1"
# Video only, audio dropped (PRD §12), rotation applied, timestamps passed through so frame i == frame i.
PROXY_ARGS = [
    "-map", "0:v:0", "-an", "-sn", "-dn",
    "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
    "-fps_mode", "passthrough", "-movflags", "+faststart", "-map_metadata", "-1",
]  # fmt: skip
FRAME_ALIGN_TOLERANCE_MS = 1.0


class IngestRejected(ValueError):
    pass


@dataclass(frozen=True)
class IngestResult:
    original: MediaAsset
    proxy: MediaAsset
    original_frames: FrameTable
    proxy_frames: FrameTable
    deduplicated: bool


def media_id_for(sha: str) -> str:
    return f"media_{sha[:20]}"


def _check_authorization(auth: MediaAuthorization, site_id: str, now: datetime) -> None:
    if auth.site_id != site_id:
        raise IngestRejected("authorization is for a different site")
    if auth.retention_until <= now:
        raise IngestRejected("authorization retention period has already ended")


def _flags_with_context(p: MediaProbe, now: datetime) -> MediaProbe:
    extra = []
    if p.creation_time_utc and p.creation_time_utc > now:
        extra.append("creation_time_in_future")
    if p.has_audio:
        extra.append("audio_present_not_analyzed")
    return p.model_copy(update={"flags": sorted({*p.flags, *extra})}) if extra else p


def _make_proxy(store: MediaStore, original_path: Path, original_frames: FrameTable) -> tuple[str, Path, MediaProbe,
                                                                                               FrameTable]:
    with tempfile.TemporaryDirectory(dir=store.root) as tmp:
        out = Path(tmp) / "proxy.mp4"
        run_ffmpeg("-i", str(original_path), *PROXY_ARGS, str(out))
        sha, path = store.put_derivative(out, ".mp4")
    proxy_probe, proxy_frames = probe(path)
    if len(proxy_frames.pts_ms) != len(original_frames.pts_ms):
        raise IngestRejected(
            f"proxy has {len(proxy_frames.pts_ms)} frames, original {len(original_frames.pts_ms)}; frame indices "
            "would not line up"
        )
    drift = max(abs(a - b) for a, b in zip(proxy_frames.pts_ms, original_frames.pts_ms, strict=True))
    if drift > FRAME_ALIGN_TOLERANCE_MS:
        raise IngestRejected(f"proxy timestamps drift {drift:.2f} ms from the original")
    return sha, path, proxy_probe, proxy_frames


def ingest(
    src: Path,
    *,
    store: MediaStore,
    authorization: MediaAuthorization,
    site_id: str,
    camera_id: str | None,
    ingested_by: str,
    now: datetime | None = None,
) -> IngestResult:
    now = now or datetime.now(UTC)
    _check_authorization(authorization, site_id, now)
    size = src.stat().st_size
    if size == 0:
        raise IngestRejected("empty file")
    if size > MAX_UPLOAD_BYTES:
        raise IngestRejected(f"file is {size} bytes; limit is {MAX_UPLOAD_BYTES}")

    sha, original_path, existed = store.put_original(src)
    media_id = media_id_for(sha)
    if existed and (store.root / "manifests" / f"{media_id}.json").exists():
        return load_result(store, media_id, deduplicated=True)

    try:
        original_probe, original_frames = probe(original_path)
    except UnsupportedMediaError as e:
        store.delete_file(original_path)
        raise IngestRejected(str(e)) from e
    original_probe = _flags_with_context(original_probe, now)

    original = MediaAsset(
        media_id=media_id, site_id=site_id, camera_id=camera_id, kind=AssetKind.ORIGINAL, sha256=sha,
        byte_size=size, mime_type=f"video/{original_probe.container.split(',')[0]}",
        original_filename=src.name[:255], probe=original_probe, authorization_id=authorization.authorization_id,
        ingested_at=now, ingested_by=ingested_by,
    )  # fmt: skip

    proxy_sha, proxy_path, proxy_probe, proxy_frames = _make_proxy(store, original_path, original_frames)
    proxy = MediaAsset(
        media_id=media_id_for(proxy_sha), site_id=site_id, camera_id=camera_id, kind=AssetKind.WORKING_DERIVATIVE,
        sha256=proxy_sha, byte_size=proxy_path.stat().st_size, mime_type="video/mp4",
        original_filename=f"{media_id}.proxy.mp4", probe=proxy_probe, parent_media_id=media_id,
        processing_method=PROXY_METHOD, software_version=tool_version("ffmpeg"),
        authorization_id=authorization.authorization_id, ingested_at=now, ingested_by="system:ingest",
    )  # fmt: skip

    store.write_json("frame_tables", original.media_id, original_frames.to_json())
    store.write_json("frame_tables", proxy.media_id, proxy_frames.to_json())
    store.write_json("manifests", media_id, {
        "original": original.model_dump(mode="json"),
        "proxy": proxy.model_dump(mode="json"),
        "proxy_args": PROXY_ARGS,
    })  # fmt: skip
    return IngestResult(original, proxy, original_frames, proxy_frames, deduplicated=False)


def load_result(store: MediaStore, media_id: str, deduplicated: bool = False) -> IngestResult:
    manifest = store.read_json("manifests", media_id)
    original = MediaAsset.model_validate(manifest["original"])
    proxy = MediaAsset.model_validate(manifest["proxy"])
    return IngestResult(
        original=original,
        proxy=proxy,
        original_frames=FrameTable.from_json(store.read_json("frame_tables", original.media_id)),
        proxy_frames=FrameTable.from_json(store.read_json("frame_tables", proxy.media_id)),
        deduplicated=deduplicated,
    )


def asset_path(store: MediaStore, asset: MediaAsset) -> Path:
    """Where an asset's bytes live in the store."""
    return store.original_path(asset.sha256) if asset.kind == AssetKind.ORIGINAL else store.derivative_path(
        asset.sha256, ".mp4"
    )
