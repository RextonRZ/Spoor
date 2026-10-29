"""Shared helpers for provider smoke tests (PRD §10.5, §32.2).

Run from backend/:  uv run python scripts/smoke/<name>.py ...
Results are written to scripts/smoke/out/ (git-ignored) so they can be copied into docs/META_MODEL_USAGE.md.
"""

import json
import sys
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from openai import AsyncOpenAI, OpenAI

from spoor.config import get_settings

OUT_DIR = Path(__file__).parent / "out"


def meta_client() -> OpenAI:
    s = get_settings()
    if s.model_api_key is None:
        sys.exit("MODEL_API_KEY is not set (copy .env.example to .env)")
    return OpenAI(api_key=s.model_api_key.get_secret_value(), base_url=s.meta_base_url)


def meta_async_client() -> AsyncOpenAI:
    s = get_settings()
    if s.model_api_key is None:
        sys.exit("MODEL_API_KEY is not set (copy .env.example to .env)")
    return AsyncOpenAI(api_key=s.model_api_key.get_secret_value(), base_url=s.meta_base_url)


@contextmanager
def timed():
    box = {}
    start = time.perf_counter()
    yield box
    box["latency_s"] = round(time.perf_counter() - start, 3)


def record(test: str, payload: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"{test}_{stamp}.json"
    path.write_text(json.dumps({"test": test, "run_at_utc": stamp, **payload}, indent=2, default=str))
    print(f"[{test}] wrote {path}")
    return path


def usage_of(response) -> dict | None:
    usage = getattr(response, "usage", None)
    return usage.model_dump() if usage is not None else None
