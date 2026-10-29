"""Fetch only the Microsoft Rocketbox avatars + animations the hub uses (MIT licence) into
assets/hub/build/third_party/rocketbox/ (gitignored). Per-file download instead of cloning the multi-GB repo.
Textures are downscaled 4K TGA -> 1K PNG (a worker is ~100–200 px tall on camera; the integrated GPU shares RAM),
specular maps are skipped (roughness is set in the material), and the source TGAs are not kept.

  cd backend && uv run --with pillow python ../assets/hub/fetch_rocketbox.py
"""

import json
import time
import urllib.request
from pathlib import Path

from PIL import Image

RAW = "https://raw.githubusercontent.com/microsoft/Microsoft-Rocketbox/master/"
OUT = Path(__file__).parent / "build" / "third_party" / "rocketbox"
UA = {"User-Agent": "Spoor-demo-hub-builder/0.1"}
AVATARS = ["Female_Adult_04", "Female_Adult_06", "Female_Adult_07", "Female_Adult_13",
           "Male_Adult_04", "Male_Adult_05", "Male_Adult_09", "Male_Adult_12"]
CLIPS = {  # folder suffix -> clip names (both genders): no carry / lift / push exist in Rocketbox
    "xy": ["walk_neutral_01", "crouch_in", "crouch_out"],
    "static": ["idle_neutral_01", "idle_neutral_02", "idle_look_around_01", "work_table", "work_mid",
               "crouch_idle", "trolley_idle", "documents_check", "hold_bag_idle", "gestic_talk_neutral_01",
               "cell_phone_textmessage"],
}
FEMALE_NAMES = {"hold_bag_idle": "hold_bag_idle_01"}  # female file names that differ
FEMALE_STATIC = {"crouch_in", "crouch_out"}  # female crouch in/out live in the static folder
TEX_KEEP = ("_color", "_normal", "_opacity")


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read()


def main():
    tree = json.loads(get("https://api.github.com/repos/microsoft/Microsoft-Rocketbox/git/trees/master?recursive=1"))
    paths = {t["path"] for t in tree["tree"]}
    manifest = {"source": "https://github.com/microsoft/Microsoft-Rocketbox", "licence": "MIT",
                "fetched": time.strftime("%Y-%m-%dT%H:%M:%S"), "avatars": [], "animations": []}
    lic = OUT / "LICENSE.md"
    lic.parent.mkdir(parents=True, exist_ok=True)
    lic.write_bytes(get(RAW + "LICENSE.md"))
    for a in AVATARS:
        base = f"Assets/Avatars/Adults/{a}/"
        fbx = OUT / a / f"{a}.fbx"
        if not fbx.exists():
            fbx.parent.mkdir(parents=True, exist_ok=True)
            fbx.write_bytes(get(RAW + base + f"Export/{a}.fbx"))
        texs = []
        for p in sorted(x for x in paths if x.startswith(base + "Textures/") and x.endswith(".tga")):
            name = Path(p).stem
            if not any(k in name for k in TEX_KEEP):
                continue
            dst = OUT / a / "Textures" / f"{name}.png"
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                tmp = dst.with_suffix(".tga")
                tmp.write_bytes(get(RAW + p))
                with Image.open(tmp) as img:  # OpenCV cannot read TGA; Pillow can
                    img.resize((1024, 1024), Image.LANCZOS).save(dst)
                tmp.unlink()
            texs.append(dst.name)
        manifest["avatars"].append({"id": a, "fbx": f"{a}/{a}.fbx", "textures": texs})
        print("avatar", a, len(texs), "textures", flush=True)
    for g in ("m", "f"):
        for folder, names in CLIPS.items():
            for n in names:
                fname = FEMALE_NAMES.get(n, n) if g == "f" else n
                fold = "static" if (g == "f" and n in FEMALE_STATIC) else folder
                p = f"Assets/Animations/all_animations_max_motextr_{fold}/{g}_{fname}.max.fbx"
                if p not in paths:
                    print("missing", p)
                    continue
                dst = OUT / "animations" / f"{g}_{n}.fbx"
                if not dst.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes(get(RAW + p))
                manifest["animations"].append({"clip": f"{g}_{n}", "file": f"animations/{g}_{n}.fbx", "source": p,
                                               "root_motion": "extracted (in place)" if fold != "static" else "static"})
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print("done:", len(manifest["avatars"]), "avatars,", len(manifest["animations"]), "clips")


if __name__ == "__main__":
    main()
