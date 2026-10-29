"""Download the CC0 Poly Haven textures / models / HDRI the hub uses into assets/hub/build/third_party/ (gitignored).

Every file comes from https://api.polyhaven.com (all Poly Haven assets are CC0). A manifest.json records the asset id,
licence, source page and download time for CREDITS.md. Files are data (images, glTF); nothing downloaded is executed.

  py -I assets/hub/fetch_assets.py
"""

import argparse
import json
import time
import urllib.request
from pathlib import Path

API = "https://api.polyhaven.com/files/"
UA = {"User-Agent": "Spoor-demo-hub-builder/0.1 (hackathon; CC0 asset fetch)"}
OUT = Path(__file__).parent / "build" / "third_party"
TEXTURES = {  # id -> maps to fetch (2k jpg)
    "smooth_concrete_floor": ["Diffuse", "nor_gl", "Rough"],
    "box_profile_metal_sheet": ["Diffuse", "nor_gl", "Rough", "Metal"],
    "galvanized_sheet_metal": ["Diffuse", "nor_gl", "Rough", "Metal"],
    "painted_metal_shutter": ["Diffuse", "nor_gl", "Rough"],
}
MODELS = ["cardboard_box_01", "metal_office_desk", "tool_cart", "steel_frame_shelves_01", "plastic_monobloc_chair_01",
          "compost_bags", "drawer_cabinet", "steel_frame_shelves_02", "concrete_road_barrier",
          "korean_fire_extinguisher_01", "mounted_fluorescent_lights"]  # all on the licence-checked list in the spec
HDRIS = ["overcast_industrial_courtyard"]


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def save(url: str, dest: Path) -> int:
    if dest.exists() and dest.stat().st_size > 0:
        return dest.stat().st_size
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = get(url)
    dest.write_bytes(data)
    return len(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="hub", choices=["hub"])
    ap.parse_args()
    manifest = {"licence": "CC0 1.0 (Poly Haven)", "fetched": time.strftime("%Y-%m-%dT%H:%M:%S"), "assets": []}
    for aid, maps in TEXTURES.items():
        files = json.loads(get(API + aid))
        got = {}
        for m in maps:
            url = files[m]["2k"]["jpg"]["url"]
            got[m] = str(Path(aid) / Path(url).name)
            save(url, OUT / got[m])
        manifest["assets"].append({"id": aid, "kind": "texture", "maps": got, "page": f"https://polyhaven.com/a/{aid}"})
    for aid in MODELS:
        g = json.loads(get(API + aid))["gltf"]["1k"]["gltf"]
        main_file = Path(aid) / Path(g["url"]).name
        save(g["url"], OUT / main_file)
        for rel, inc in g.get("include", {}).items():  # textures / .bin referenced by the glTF, at their relative path
            save(inc["url"], OUT / aid / rel)
        manifest["assets"].append({"id": aid, "kind": "model", "gltf": str(main_file),
                                   "page": f"https://polyhaven.com/a/{aid}"})
    for aid in HDRIS:
        url = json.loads(get(API + aid))["hdri"]["2k"]["hdr"]["url"]
        f = Path(aid) / Path(url).name
        save(url, OUT / f)
        manifest["assets"].append({"id": aid, "kind": "hdri", "file": str(f), "page": f"https://polyhaven.com/a/{aid}"})
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    total = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"{len(manifest['assets'])} assets, {total / 1e6:.1f} MB in {OUT}")


if __name__ == "__main__":
    main()
