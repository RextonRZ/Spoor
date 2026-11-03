"""The Cameras page's turntable: the overview ring (spin_render.py, ring "ov") as one video per height, every frame a key
frame so a drag can land on any frame at once, plus the table the page draws with: each frame's projection matrix and
every CCTV camera's mount and floor coverage in world metres (cameras3d.py).

  python assets/tour/publish_hub_spin.py assets/tour/spin_hub frontend/public/tour/hub
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
spin = json.loads((src / "spin.json").read_text(encoding="utf-8"))
ov = spin["rings"]["ov"]
table = json.loads((dst / "cameras3d.json").read_text(encoding="utf-8"))
n = spin["n"]
for e, ring in enumerate(ov["rings"]):
    frames = sorted((src / "ov" / str(e)).glob("f*.*"))
    assert len(frames) == n, f"ring {e}: {len(frames)} frames, expected {n}"
    pat = str(frames[0].parent / f"f%0{len(frames[0].stem) - 1}d{frames[0].suffix}")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "30", "-i", pat, "-c:v", "libx264", "-preset", "slow", "-crf", "21",
                    "-g", "1", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(dst / f"ov{e}.mp4")], check=True)
    # the still shown while the video loads: frame 0, the same picture the video opens on
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(frames[0]), "-q:v", "3", str(dst / f"ov{e}.jpg")], check=True)
    print(f"ring {e}: {n} frames -> {(dst / f'ov{e}.mp4').stat().st_size / 1e6:.1f} MB")
table.update({"n": n, "fps": 30, "size": spin["size"], "look": ov["look"], "rings": [{"elev": r["elev"], "P": r["P"]} for r in ov["rings"]]})
(dst / "cameras3d.json").write_text(json.dumps(table, separators=(",", ":")), encoding="utf-8")
if (dst / "spin").exists():
    shutil.rmtree(dst / "spin")
print("published", dst)
