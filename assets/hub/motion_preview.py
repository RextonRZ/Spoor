"""Free local motion preview of a scenario blend (Rexton 31 Oct, before any full render): every CCTV camera, the whole
window, Workbench at 640x360 / 10 fps - one MP4 per camera and one 4 x 5 grid MP4 of all of them on one clock.
Workbench (solid colours, studio light): it shows motion, contact and placement, not the final look.

  blender -b <S2.blend> -P assets/hub/motion_preview.py -- --out <dir> [--frames 1-900] [--cams CAM_01,...]
      renders <dir>/_frames/<cam>/<frame>.jpg (each frame evaluated once, every camera rendered from it); run several
      with different --frames in parallel
  py -X utf8 assets/hub/motion_preview.py --encode <dir> [--fps 10] [--keep-frames]
      labels each tile (camera, time), encodes <dir>/<cam>.mp4 (H.264 CRF 23) and <dir>/grid_4x5.mp4, then deletes the
      frames (C: free space)
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--out", default="")
ap.add_argument("--frames", default="1-900")
ap.add_argument("--cams", default="")
ap.add_argument("--res", default="640x360")
ap.add_argument("--encode", default="")
ap.add_argument("--fps", type=int, default=10)
ap.add_argument("--keep-frames", action="store_true")
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
CAMS = [c["id"] for c in json.loads((HUB / "hub_spec.json").read_text(encoding="utf-8"))["cameras"]]


def render():
    import bpy
    sc = bpy.context.scene
    out = Path(a.out).resolve() / "_frames"
    cams = [c for c in (a.cams.split(",") if a.cams else CAMS) if c in sc.objects]
    rx, ry = (int(v) for v in a.res.split("x"))
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "MATERIAL"
    sc.display.shading.show_shadows = True
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, 100
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 88
    for c in cams:
        (out / c).mkdir(parents=True, exist_ok=True)
    f0, f1 = (int(x) for x in a.frames.split("-"))
    for f in range(f0, f1 + 1):
        if all((out / c / f"{f:04d}.jpg").exists() for c in cams):
            continue  # resumable
        sc.frame_set(f)
        for c in cams:
            sc.camera = sc.objects[c]
            sc.render.filepath = str(out / c / f"{f:04d}.jpg")
            bpy.ops.render.render(write_still=True)
        if (f - f0) % 50 == 0:
            print(f"PREVIEW f{f} ({len(cams)} cams)", flush=True)
    print("PREVIEW done", f0, f1, flush=True)


def encode():
    from PIL import Image, ImageDraw, ImageFont
    d = Path(a.encode).resolve()
    fr = d / "_frames"
    cams = [c for c in CAMS if (fr / c).exists()]
    n = max(len(list((fr / c).glob("*.jpg"))) for c in cams)
    try:
        fnt = ImageFont.truetype("arialbd.ttf", 20)
    except OSError:
        fnt = ImageFont.load_default()
    grid = d / "_grid"
    grid.mkdir(exist_ok=True)
    frames = sorted(int(p.stem) for p in (fr / cams[0]).glob("*.jpg"))
    for f in frames:
        tiles = []
        for c in cams:
            p = fr / c / f"{f:04d}.jpg"
            im = Image.open(p).convert("RGB") if p.exists() else Image.new("RGB", (640, 360), (40, 0, 0))
            dr = ImageDraw.Draw(im)
            dr.rectangle([0, 0, 250, 28], fill=(0, 0, 0))
            dr.text((6, 3), f"{c}  t={(f - 1) / a.fps:5.1f}s  f{f}", font=fnt, fill=(255, 255, 255))
            im.save(p, quality=88)  # labelled in place (the per-camera MP4 carries it too)
            tiles.append(im)
        w, h = tiles[0].size
        g = Image.new("RGB", (4 * w, 5 * h), (16, 16, 16))
        for i, im in enumerate(tiles):
            g.paste(im, ((i % 4) * w, (i // 4) * h))
        ImageDraw.Draw(g).text((3 * w + 20, 4 * h + 20), "SYNTHETIC - motion preview\n(Workbench, not the final look)",
                               font=fnt, fill=(255, 220, 80))
        g.save(grid / f"{f:04d}.jpg", quality=85)
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p"]
    for c in cams:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(a.fps), "-start_number", str(frames[0]),
                        "-i", str(fr / c / "%04d.jpg"), *enc, str(d / f"{c}.mp4")], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(a.fps), "-start_number", str(frames[0]),
                    "-i", str(grid / "%04d.jpg"), *enc, str(d / "grid_4x5.mp4")], check=True)
    if not a.keep_frames:
        shutil.rmtree(fr)
        shutil.rmtree(grid)
    print("ENCODED", len(cams), "cameras +", d / "grid_4x5.mp4", f"({n} frames)")


if a.encode:
    encode()
else:
    render()
