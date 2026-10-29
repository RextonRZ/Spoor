"""Thin, testable wrappers around ffprobe/ffmpeg. Arguments are passed as lists — never through a shell."""

import json
import shutil
import subprocess
from functools import cache
from pathlib import Path


class MediaToolError(RuntimeError):
    pass


def _tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise MediaToolError(f"{name} not found on PATH")
    return path


@cache
def tool_version(name: str = "ffmpeg") -> str:
    out = subprocess.run([_tool(name), "-version"], capture_output=True, text=True, check=True).stdout
    return out.splitlines()[0].strip()


def run_ffprobe(path: Path, *args: str) -> dict:
    cmd = [_tool("ffprobe"), "-v", "error", "-of", "json", *args, str(path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise MediaToolError(f"ffprobe failed: {proc.stderr.strip()[:500]}")
    return json.loads(proc.stdout or "{}")


def run_ffmpeg(*args: str, capture_stdout: bool = False) -> bytes:
    cmd = [_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin", *args]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        raise MediaToolError(f"ffmpeg failed: {proc.stderr.decode(errors='replace').strip()[:500]}")
    return proc.stdout if capture_stdout else b""
