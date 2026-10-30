"""Evidence reel (QUEUE I8 / H7): one MP4 that walks the journey in time order, built only from stored evidence.

Cards, in order: a confirmed sighting = the original pixels around the box (I1 crop, scaled to fit, never enhanced);
a scan = the original frame of a camera watching that read point at the scan time, labelled "context frame, the parcel
is not identified in it"; a belt inference = an amber card ("inferred along the belt, not seen"); a gap = a grey card
("no camera 14:32:31.8 → 14:32:47.0"). Every card burns in the time (MYT), the camera, the source SHA-256 prefix and
SYNTHETIC; the manifest lists every source with its full hash and frame index."""

import json
import subprocess
import tempfile
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import numpy as np

W, H = 1280, 720
MYT = timezone(timedelta(hours=8))
GREY, AMBER, GREEN, BLUE, INK = (60, 58, 55), (36, 191, 251), (128, 222, 74), (250, 165, 96), (247, 245, 244)
FrameGet = Callable[[str, int], bytes]


def _t(iso: str) -> str:
    t = datetime.fromisoformat(iso).astimezone(MYT)
    return f"{t:%H:%M:%S}.{t.microsecond // 100_000} MYT"


def _canvas(color=(16, 13, 11)) -> np.ndarray:
    return np.full((H, W, 3), color, np.uint8)


def _text(img, s: str, y: int, scale=0.8, color=INK, x=48, thick=2):
    cv2.putText(img, s, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)


def _burn(img, t: str, cam: str, sha: str | None, note: str):
    cv2.rectangle(img, (0, H - 64), (W, H), (8, 8, 12), -1)
    _text(img, f"{_t(t)}   {cam}   src {sha[:16] + '...' if sha else '-'}", H - 36, 0.7)
    _text(img, note, H - 12, 0.55, (180, 180, 180), thick=1)
    cv2.rectangle(img, (W - 210, 14), (W - 14, 52), (8, 8, 12), -1)
    _text(img, "SYNTHETIC", 44, 0.8, (36, 191, 251), x=W - 196)


def _fit(png: bytes, rect: tuple[int, int, int, int] | None = None) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    if rect:
        x1, y1, x2, y2 = rect
        img = img[y1:y2, x1:x2]
    h, w = img.shape[:2]
    k = min(W / w, (H - 64) / h)
    img = cv2.resize(img, (max(1, int(w * k)), max(1, int(h * k))), interpolation=cv2.INTER_CUBIC)
    out = _canvas()
    y0, x0 = (H - 64 - img.shape[0]) // 2, (W - img.shape[1]) // 2
    out[y0:y0 + img.shape[0], x0:x0 + img.shape[1]] = img
    return out


def build_reel(journey_obj: dict, *, frame_get: FrameGet, frame_lookup, crop_of, out_dir: Path,
               reel_id: str, case_label: str) -> dict:  # fmt: skip
    """Render the reel. `frame_lookup(cam, t_ms)` -> frame ref; `crop_of(observation_id)` -> (media_id, idx, rect, sha)."""
    cards: list[tuple[np.ndarray, float]] = []
    sources: list[dict] = []
    title = _canvas()
    _text(title, "Evidence reel", 120, 1.4, INK, thick=3)
    _text(title, case_label[:70], 170, 0.8)
    _text(title, "Built from stored evidence only. Synthetic footage of a fictional hub.", 220, 0.7, (180, 180, 180), thick=1)
    _text(title, "green = seen   amber = inferred along the belt   grey = no camera", 270, 0.7, (180, 180, 180), thick=1)
    cards.append((title, 2.5))
    items = sorted([("scan", b["t"], b) for b in journey_obj["scans"]] + [(s["kind"], s["start"], s) for s in journey_obj["segments"]],
                   key=lambda x: (x[1], x[0] != "scan"))  # fmt: skip
    for kind, t, it in items:
        if kind == "observed":
            for p in it["points"][:: max(1, len(it["points"]) // 12)]:
                media, idx, rect, sha = crop_of(p["observation_id"])
                img = _fit(frame_get(media, idx), rect)
                cv2.rectangle(img, (6, 6), (W - 6, H - 70), GREEN, 3)
                _burn(img, p["t"], it["camera_id"].removeprefix("cam_"), sha, "seen: original pixels around the confirmed box (scaled to fit, not enhanced)")
                cards.append((img, 0.5))
                sources.append({"kind": "crop", "media_id": media, "frame_index": idx, "sha256": sha, "rect": list(rect)})
        elif kind == "scan":
            ref = frame_lookup_first(frame_lookup, it)
            if ref:
                img = _fit(frame_get(ref["media_id"], ref["frame_index"]))
                cv2.rectangle(img, (6, 6), (W - 6, H - 70), BLUE, 3)
                _burn(img, it["t"], ref["camera_id"].removeprefix("cam_"), ref.get("sha256"),
                      f"scan {it.get('raw_code') or it['event_kind']} at {it.get('station_id')}: context frame, the parcel is not identified in it")
                sources.append({"kind": "context_frame", "media_id": ref["media_id"], "frame_index": ref["frame_index"],
                                "sha256": ref.get("sha256"), "scan_event_id": it["scan_event_id"]})
            else:
                img = _canvas()
                _text(img, f"Scan: {it.get('raw_code') or it['event_kind']} at {it.get('station_id')}", 300, 1.0, BLUE)
                _text(img, "no camera with footage watches this read point", 350, 0.8)
                _burn(img, it["t"], "-", None, "scan record (scan_simulated)")
                sources.append({"kind": "scan", "scan_event_id": it["scan_event_id"]})
            cards.append((img, 1.6))
        elif kind == "inferred_along_conveyor":
            img = _canvas((20, 26, 30))
            _text(img, "Inferred along the belt (not seen)", 300, 1.1, AMBER, thick=2)
            _text(img, f"{' -> '.join(it['route'])}: {it['belt_time_s']} s at belt speed, recorded {it['recorded_gap_s']} s",
                  350, 0.8)
            _burn(img, it["start"], "-", None, "inference from the site plan and two scans; nothing was observed in between")
            cards.append((img, 1.4))
        elif kind == "gap":
            img = _canvas(GREY)
            _text(img, f"No camera   {_t(it['start'])}  ->  {_t(it['end'])}", 320, 1.0, INK, thick=2)
            _text(img, "unknown: no scan and no sighting in this interval", 370, 0.8, (210, 210, 210), thick=1)
            _burn(img, it["start"], "-", None, "gap: never bridged")
            cards.append((img, 2.0))
    with tempfile.TemporaryDirectory() as tmp:
        lst = []
        for i, (img, dur) in enumerate(cards):
            f = Path(tmp) / f"c{i:04d}.png"
            cv2.imwrite(str(f), img)
            lst.append(f"file '{f.as_posix()}'\nduration {dur}")
        lst.append(f"file '{(Path(tmp) / f'c{len(cards) - 1:04d}.png').as_posix()}'")
        (Path(tmp) / "list.txt").write_text("\n".join(lst), encoding="utf-8")
        out_dir.mkdir(parents=True, exist_ok=True)
        mp4 = out_dir / f"{reel_id}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(Path(tmp) / "list.txt"),
                        "-vf", "fps=25,format=yuv420p", "-c:v", "libx264", "-crf", "23", "-movflags", "+faststart", str(mp4)],
                       check=True)  # fmt: skip
    manifest = {"reel_id": reel_id, "cards": len(cards), "seconds": round(sum(d for _, d in cards), 1), "sources": sources,
                "label": "built from stored evidence; synthetic footage"}
    (out_dir / f"{reel_id}.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def frame_lookup_first(frame_lookup, bead: dict) -> dict | None:
    """The first camera with footage that watches the bead's read point at its time (plan visibility)."""
    for cam in bead.get("_watchers", []):
        f = frame_lookup(cam, datetime.fromisoformat(bead["t"]).timestamp() * 1000)
        if f:
            return f
    return None
