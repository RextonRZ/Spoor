"""QA review videos: renders (qa_render.py, batches of jobs per Blender run), burns in labels, encodes H.264, verifies,
deletes the PNG frames, writes qa/manifest.json. Resumable: finished MP4s are skipped.

  py -X utf8 assets/hub/qa_videos.py [--only worker_xx,CAM_07] [--batch 6]

Needs qa/timeline.json + qa/visibility.json from qa_checks.py (clip name per frame for the burn-in, cameras that see
each worker for the manifest).
"""

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HUB = Path(__file__).resolve().parent
QA = HUB / "build" / "qa"
FR = QA / "_frames"
BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
BLEND = HUB / "build" / "hub_dressed.blend"
ap = argparse.ArgumentParser()
ap.add_argument("--only", default="")
ap.add_argument("--batch", type=int, default=6)
args = ap.parse_args()

TL = json.loads((QA / "timeline.json").read_text(encoding="utf-8"))
VIS = json.loads((QA / "visibility.json").read_text(encoding="utf-8"))
CAMS = [f"CAM_{k:02d}" for k in range(1, 19)]
jobs = [("worker", n) for n in sorted(TL)] + [("cam", c) for c in CAMS]
if args.only:
    want = set(args.only.split(","))
    jobs = [j for j in jobs if j[1] in want]
(QA / "workers").mkdir(parents=True, exist_ok=True)
(QA / "cctv").mkdir(parents=True, exist_ok=True)
FONT = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 17)


def mp4_path(kind, name):
    return QA / ("workers" if kind == "worker" else "cctv") / f"{name}.mp4"


def frames_ok(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                        "stream=nb_read_frames", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return int(r.stdout.strip())
    except ValueError:
        return 0


def finish(kind, name):
    d = FR / name
    pngs = sorted(d.glob("*.png"))
    for p in pngs:
        f = int(p.stem)
        im = Image.open(p).convert("RGB")
        dr = ImageDraw.Draw(im)
        if kind == "worker":
            clip = TL[name]["clips"][f - 1] if f - 1 < len(TL[name]["clips"]) else "?"
            txt = f"{name}  |  {TL[name]['role']}  |  clip: {clip}  |  frame {f:03d}"
        else:
            txt = f"{name}  |  frame {f:03d}"
        w_ = dr.textlength(txt, font=FONT)
        dr.rectangle([6, 6, 14 + w_, 32], fill=(0, 0, 0))
        dr.text((10, 9), txt, font=FONT, fill=(255, 235, 60))
        im.save(p)
    out = mp4_path(kind, name)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", "10", "-start_number", str(int(pngs[0].stem)),
                    "-i", str(d / "%04d.png"), "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], check=True)
    n = frames_ok(out)
    if n == len(pngs):
        shutil.rmtree(d)
    return n, len(pngs), out.stat().st_size


t_all = time.time()
todo = [j for j in jobs if not mp4_path(*j).exists()]
print(f"QAV {len(jobs)} jobs, {len(todo)} to render", flush=True)
for i in range(0, len(todo), args.batch):
    chunk = todo[i:i + args.batch]
    need = [j for j in chunk if not (FR / j[1] / "done").exists()]
    if need:
        t0 = time.time()
        subprocess.run([BLENDER, "-b", "--factory-startup", str(BLEND), "-P", str(HUB / "qa_render.py"), "--",
                        "--jobs", ",".join(f"{k}:{n}" for k, n in need), "--out", str(FR)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"QAV rendered {[n for _, n in need]} in {time.time() - t0:.0f}s", flush=True)
    for kind, name in chunk:
        if not (FR / name / "done").exists():
            print(f"QAV FAILED render {name}", flush=True)
            continue
        n, want, size = finish(kind, name)
        print(f"QAV {name}: {n}/{want} frames, {size / 1e6:.1f} MB", flush=True)

manifest = {"note": "QA review material; render-side only, never read by Spoor", "fps": 10, "frames": [1, 300],
            "resolution": [960, 540], "workers": [], "cameras": []}
for n in sorted(TL):
    clips = list(dict.fromkeys(TL[n]["clips"]))
    p = mp4_path("worker", n)
    manifest["workers"].append({"worker": n, "role": TL[n]["role"], "clips": clips, "seen_by": VIS.get(n, []),
                                "file": str(p.relative_to(QA)).replace("\\", "/") if p.exists() else None,
                                "mb": round(p.stat().st_size / 1e6, 2) if p.exists() else None})
for c in CAMS:
    p = mp4_path("cam", c)
    manifest["cameras"].append({"camera": c, "sees": sorted(n for n, v in VIS.items() if c in v),
                                "file": str(p.relative_to(QA)).replace("\\", "/") if p.exists() else None,
                                "mb": round(p.stat().st_size / 1e6, 2) if p.exists() else None})
tot = sum(p.stat().st_size for p in QA.rglob("*.mp4"))
manifest["total_mb"] = round(tot / 1e6, 1)
(QA / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
print(f"QAV done in {(time.time() - t_all) / 60:.1f} min, total {tot / 1e6:.1f} MB", flush=True)
