"""Copy the Places pictures into the app (Rexton 1 Nov): assets/places/out (top / eye / hub_top) and the locator's
tilted maps (assets/locator/out/<zone>_map.png) -> frontend/public/places/*.webp, and places.json with the app paths.
  py -X utf8 assets/hub/place_export.py
"""
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent.parent
SRC, LOC, DST = ROOT / "assets" / "places" / "out", ROOT / "assets" / "locator" / "out", ROOT / "frontend" / "public" / "places"
DST.mkdir(parents=True, exist_ok=True)
meta = json.loads((SRC / "places.json").read_text(encoding="utf-8"))


def webp(src, name, q=80):
    Image.open(src).convert("RGB").save(DST / name, "WEBP", quality=q, method=6)
    return f"/places/{name}"


meta["hub_top"]["image"] = webp(SRC / "hub_top.jpg", "hub_top.webp", 82)
for zid, z in meta["zones"].items():
    for view in ("top", "eye"):
        if view in z:
            z[view]["image"] = webp(SRC / z[view]["image"], f"{zid}_{view}.webp")
    if "map" in z:
        z["map"]["image"] = webp(LOC / f"{zid}_map.png", f"{zid}_map.webp")
        # the live 3D view starts where this picture was taken (three.js axes, as the app's hub.glb)
        z["map"]["camera3"] = json.loads((LOC / "_raw" / f"{zid}_map.json").read_text(encoding="utf-8"))["three_camera"]
spec = json.loads((ROOT / "assets" / "hub" / "hub_spec.json").read_text(encoding="utf-8"))
meta["points_m"] = {s["id"]: s["position_m"] for s in spec["scan_points"]}  # site metres (x east, y north, z up)
# per scanner: tilt / top / eye, each aimed at it (place_shots.py)
pt = SRC / "pt" / "pt.json"
if pt.exists():
    (DST / "pt").mkdir(exist_ok=True)
    meta["pt"] = json.loads(pt.read_text(encoding="utf-8"))
    for pid, views in meta["pt"].items():
        for v in ("tilt", "top", "eye"):
            if views.get(v):
                Image.open(SRC / "pt" / views[v]["image"]).convert("RGB").save(DST / "pt" / f"{pid}_{v}.webp", "WEBP", quality=80, method=6)
                views[v]["image"] = f"/places/pt/{pid}_{v}.webp"
                views[v].pop("camera_m", None)
# turntables (place_turn.py): frames per scanner as webp + one small json each, loaded only when that place opens
tj = SRC / "turn" / "turn.json"
if tj.exists():
    turns = json.loads(tj.read_text(encoding="utf-8"))
    meta["turn"] = {}
    for pid, t in turns.items():
        d = DST / "turn" / pid
        d.mkdir(parents=True, exist_ok=True)
        for ring, frames in t["rings"].items():
            for k in range(len(frames)):
                out = d / f"{ring}_{k:02d}.webp"
                if not out.exists():
                    Image.open(SRC / "turn" / pid / f"{ring}_{k:02d}.jpg").convert("RGB").save(out, "WEBP", quality=72, method=4)
        (d / "turn.json").write_text(json.dumps(t, separators=(",", ":")), encoding="utf-8")
        meta["turn"][pid] = {"n": t["n"], "rings": list(t["rings"])}
meta.pop("hidden_for_case", None)  # build detail, not for the app
(DST / "places.json").write_text(json.dumps(meta, separators=(",", ":")), encoding="utf-8")
files = [f for f in DST.rglob("*") if f.is_file()]
print("EXPORT", DST, len(files), "files", f"{sum(f.stat().st_size for f in files) / 1e6:.1f} MB")
