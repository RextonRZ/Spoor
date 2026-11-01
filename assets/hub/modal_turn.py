"""Turntables (place_turn.py) on Modal GPUs (Rexton 1 Nov: "if Modal has money left, just do"): the packed S2 final on
the spoor-render Volume (/hub_S2_final_packed.blend), the same Blender 5.2.3 image as modal_render.py, scanners split
over containers (Modal runs up to 10 at once on this plan), frames come back as bytes into assets/places/out/turn/.

  py -X utf8 assets/hub/modal_turn.py headings          (writes assets/places/out/turn/headings.json from the locator)
  SPOOR_GPU=L4,A10G modal run assets/hub/modal_turn.py::main [--ids SP-DIV-C12,...] [--per 5] [--go]
      (estimate first; --go renders)
"""
import json
import math
import os
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent
ROOT = HUB.parent.parent
OUT = ROOT / "assets" / "places" / "out" / "turn"
HEADINGS = OUT / "headings.json"

if len(sys.argv) > 1 and sys.argv[1] == "headings":
    spec = json.loads((HUB / "hub_spec.json").read_text(encoding="utf-8"))
    h = {}
    for zid in {s["zone"] for s in spec["scan_points"]}:
        j = ROOT / "assets" / "locator" / "out" / "_raw" / f"{zid}_map.json"
        if j.exists():
            c = json.loads(j.read_text(encoding="utf-8"))["three_camera"]
            h[zid] = math.atan2(-(c["position"][2] - c["target"][2]), c["position"][0] - c["target"][0])
    OUT.mkdir(parents=True, exist_ok=True)
    HEADINGS.write_text(json.dumps(h, indent=1), encoding="utf-8")
    print("HEADINGS", len(h), "zones ->", HEADINGS)
    sys.exit(0)

import modal  # noqa: E402

# as modal_render.py (only this file ships to the container, so no import from it)
BLENDER_URL = "https://download.blender.org/release/Blender5.2/blender-5.2.3-linux-x64.tar.xz"
BLENDER_SHA256 = "78486c018b4443efe5e75ab54c290ed8c15abafd249b862c2c9ce2530a918eec"
GPU_PRICE = {"L4": 0.000222, "A10G": 0.000306, "T4": 0.000164}  # US$/s, modal.com/pricing (31 Oct 2026)
GPU_LIST = [g.strip() for g in os.environ.get("SPOOR_GPU", "L4,A10G").split(",") if g.strip()]
GPU = GPU_LIST[0] if len(GPU_LIST) == 1 else GPU_LIST
CPU_USD_S, MEM_USD_S, CORES, MEM_GIB = 0.0000131, 0.00000222, 4, 16

image = (modal.Image.debian_slim(python_version="3.11")
         .apt_install("wget", "xz-utils", "libegl1", "libgl1", "libglx0", "libopengl0", "libxi6", "libxrender1",
                      "libxkbcommon0", "libxkbcommon-x11-0", "libsm6", "libice6", "libxext6", "libx11-6", "libxxf86vm1",
                      "libxfixes3", "libxrandr2", "libxinerama1", "libxcursor1", "libwayland-client0", "libwayland-egl1",
                      "libdecor-0-0", "libgomp1", "libvulkan1")
         .run_commands(f"wget -q {BLENDER_URL} -O /tmp/b.tar.xz",
                       f"echo '{BLENDER_SHA256}  /tmp/b.tar.xz' | sha256sum -c -",
                       "mkdir -p /opt/blender && tar -xJf /tmp/b.tar.xz -C /opt/blender --strip-components=1 && rm /tmp/b.tar.xz")
         .env({"NVIDIA_DRIVER_CAPABILITIES": "all"})
         .add_local_file(str(HUB / "place_turn.py"), "/root/place_turn.py")
         .add_local_file(str(HUB / "hub_spec.json"), "/root/hub_spec.json")
         .add_local_file(str(HEADINGS), "/root/headings.json"))
vol = modal.Volume.from_name("spoor-render")
app = modal.App("spoor-place-turn", image=image)


@app.function(gpu=GPU, cpu=CORES, memory=MEM_GIB * 1024, volumes={"/vol": vol}, timeout=3600)
def turn(ids: str) -> dict:
    import subprocess
    import time
    out = Path("/tmp/turn")
    t0 = time.time()
    p = subprocess.run(["/opt/blender/blender", "-b", "--factory-startup", "/vol/hub_S2_final_packed.blend", "-P",
                        "/root/place_turn.py", "--", "--out", str(out), "--ids", ids, "--mapdir", "/root/headings.json"],
                       capture_output=True, text=True)
    files = {str(f.relative_to(out)).replace("\\", "/"): f.read_bytes() for f in out.rglob("*.jpg")}
    meta = json.loads((out / "turn.json").read_text()) if (out / "turn.json").exists() else {}
    return dict(ids=ids, rc=p.returncode, secs=round(time.time() - t0, 1), files=files, meta=meta,
                log_tail=(p.stdout + p.stderr)[-3000:])


@app.local_entrypoint()
def main(ids: str = "", per: int = 5, go: bool = False, s_per_frame: float = 1.2):
    spec = json.loads((HUB / "hub_spec.json").read_text(encoding="utf-8"))
    pts = [s["id"] for s in spec["scan_points"] if not ids or s["id"] in ids.split(",")]
    groups = [",".join(pts[i:i + per]) for i in range(0, len(pts), per)]
    frames = len(pts) * 48
    secs = frames * s_per_frame + len(groups) * 150
    usd = secs * (max(GPU_PRICE[g] for g in GPU_LIST) + CORES * CPU_USD_S + MEM_GIB * MEM_USD_S)
    print(f"ESTIMATE {GPU}: {len(pts)} scanners x 48 frames = {frames} frames, {len(groups)} containers, ~{secs / 3600:.1f} GPU-h, ~US${usd:.2f}")
    if not go:
        raise SystemExit("estimate only: --go renders")
    OUT.mkdir(parents=True, exist_ok=True)
    allmeta = json.loads((OUT / "turn.json").read_text(encoding="utf-8")) if (OUT / "turn.json").exists() else {}
    bad = []
    for r in turn.map(groups):
        for name, b in r["files"].items():
            (OUT / name).parent.mkdir(parents=True, exist_ok=True)
            (OUT / name).write_bytes(b)
        allmeta.update(r["meta"])
        (OUT / "turn.json").write_text(json.dumps(allmeta, separators=(",", ":")), encoding="utf-8")
        print(json.dumps({"ids": r["ids"], "rc": r["rc"], "secs": r["secs"], "files": len(r["files"])}), flush=True)
        if r["rc"] != 0 or len(r["files"]) < 48 * len(r["ids"].split(",")):
            bad.append(r["ids"]); print(r["log_tail"])
    print("TURN DONE", len(allmeta), "scanners;", "failed groups:", bad)
