"""On-site triage (Muse Glimmer on the hub's own GPU): which moments of footage leave the hub for the cloud models.

Glimmer looks at one frame every `every_s` seconds. An action can happen anywhere between two samples, so a flagged
frame sends the footage from the sample before it to the sample after it (pad = every_s each side); overlapping windows
merge. What counts is seconds sent out of seconds recorded, not cameras flagged: in a busy hub most cameras show
someone handling parcels. Flags choose footage only, never evidence."""

import json
from pathlib import Path

FILE = "triage_flags.json"  # written next to the recorder export by the on-site box (seeded from its proof record)


def windows(times: list[float], every_s: float, seconds: float) -> list[tuple[float, float]]:
    out: list[list[float]] = []
    for a, b in sorted((max(0.0, t - every_s), min(seconds, t + every_s)) for t in times):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def summary(tri: dict) -> dict:
    """tri: {"every_s", "seconds", "cameras": [camera_id...], "flags": {camera_id: [t_s...]}, "frames"?, "model"?}."""
    every, secs = float(tri["every_s"]), float(tri["seconds"])
    sent = {c: windows(ts, every, secs) for c, ts in tri["flags"].items() if ts}
    sent_s = sum(b - a for w in sent.values() for a, b in w)
    total_s = secs * len(tri["cameras"])
    return {"cameras_flagged": len(sent), "cameras": len(tri["cameras"]), "frames": tri.get("frames"),
            "pad_s": every, "sent_s": round(sent_s, 1), "total_s": round(total_s, 1),
            "sent_share": round(sent_s / total_s, 3) if total_s else 0.0,
            "windows": {c: [[round(a, 1), round(b, 1)] for a, b in w] for c, w in sent.items()}}  # fmt: skip


def from_proof(proof: dict) -> dict:
    """The triage file from a Glimmer hub proof record (docs/open_weights_proof/*_glimmer_triage_hub.json)."""
    inp = proof["input"]
    return {"model": proof["model"], "every_s": inp["every_s"], "seconds": inp["seconds"], "frames": inp["frames"],
            "cameras": [f"cam_{Path(c).stem}" for c in inp["clips"]],
            "flags": {c: [f["t_s"] for f in fl] for c, fl in proof["triage_flags"].items()},
            "usd": proof.get("usd_gpu_seconds"), "label": "triage flags, not evidence"}  # fmt: skip


def load(data_dir: Path) -> dict | None:
    p = Path(data_dir) / FILE
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def name_flagged(steps: list[dict], tri: dict | None) -> list[dict]:
    """A stored run's triage step, with the cameras Glimmer flagged and the ones it swept named (the Cameras wall's
    replay greys the rest). Runs that kept only the counts get the names from the triage file, but only when it is the
    file the run used: the same cameras, flags and seconds. Steps are copied, never changed in the store."""
    if not tri or not tri.get("flags"):
        return steps
    t = summary(tri)
    out = []
    for s in steps:
        o = ((s.get("receipt") or {}).get("output") or {})
        if s.get("tool") == "triage_clips" and "flagged" not in o and all(o.get(k) == t[k] for k in ("cameras_flagged", "cameras", "sent_s", "total_s")):
            s = {**s, "receipt": {**s["receipt"], "output": {**o, "flagged": sorted(t["windows"]), "swept": sorted(tri["cameras"])}}}
        out.append(s)
    return out
