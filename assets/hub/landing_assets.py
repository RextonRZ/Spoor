"""Landing hero assets from the S2 render: the push-in steps (from ground truth), posters for all 19 cameras, one
short clip per step, and the 2x doorway inset. Writes <out>/landing.json + media.

  uv run --project backend python assets/hub/landing_assets.py --blend assets/hub/build/hub_lineAb_S2.blend \\
      --tracks <tracks.json from landing_truth.py> --out frontend/public/landing

Steps: at every sampled frame the camera with the clearest view of the parcel (box area x share of it in clear line of
sight) wins; stretches under 1.5 s merge into their neighbour. So the page pushes in only where a camera really saw it,
in time order, without a hand-picked list. Each step gets a clip window: the step holding the pick shows the pick, the
last step ends just after the parcel goes into the blind store, the others are centred.
Frames: render_cctv.py at the batch settings (the final look), then the CCTV pass of cctv_look (lens, sensor, ISP)
WITHOUT the burned-in OSD: the page draws the camera name and its clock over the tile. H.264, veryfast, no audio.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

HUB = Path(__file__).resolve().parent
sys.path.insert(0, str(HUB))
import cctv_look as L  # noqa: E402

BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
BATCH = ["--samples", "2", "--raytrace", "0", "--shadow-scale", "0.5", "--exposure", "0.2"]
FPS = 10


def steps_from(tr, min_s=1.5):
    best = {}
    for s in tr["sightings"]:
        for f, b in s["boxes"].items():
            sc = (b[2] - b[0]) * (b[3] - b[1]) * s["seen"][f]
            f = int(f)
            if f not in best or sc > best[f][1]:
                best[f] = (s["camera"], sc)
    segs = []
    for f in sorted(best):
        c = best[f][0]
        if segs and segs[-1]["camera"] == c and f - segs[-1]["f1"] <= FPS:
            segs[-1]["f1"] = f
        else:
            segs.append(dict(camera=c, f0=f, f1=f))
    while len(segs) > 1:
        short = [i for i, s in enumerate(segs) if (s["f1"] - s["f0"]) / FPS < min_s]
        if not short:
            break
        i = min(short, key=lambda k: segs[k]["f1"] - segs[k]["f0"])
        nb = [j for j in (i - 1, i + 1) if 0 <= j < len(segs)]
        j = max(nb, key=lambda k: segs[k]["f1"] - segs[k]["f0"])
        lo, hi = sorted((i, j))
        merged = dict(camera=segs[j]["camera"], f0=segs[lo]["f0"], f1=segs[hi]["f1"])
        segs[lo:hi + 1] = [merged]
        k = 0  # neighbours with the same camera join up
        while k < len(segs) - 1:
            if segs[k]["camera"] == segs[k + 1]["camera"]:
                segs[k:k + 2] = [dict(camera=segs[k]["camera"], f0=segs[k]["f0"], f1=segs[k + 1]["f1"])]
            else:
                k += 1
    return segs


def window(seg, key_f, length_f, f_min, f_max, end_at=None):
    if end_at is not None:
        b = min(f_max, end_at)
        return max(f_min, b - length_f + 1), b
    c = key_f if key_f is not None and seg["f0"] <= key_f <= seg["f1"] else (seg["f0"] + seg["f1"]) // 2
    a = max(f_min, c - length_f // 2)
    return a, min(f_max, a + length_f - 1)


def render(blend, cams, frames, raw, res):
    subprocess.run([BLENDER, "-b", "--factory-startup", str(blend), "-P", str(HUB / "render_cctv.py"), "--",
                    "--cams", ",".join(cams), "--frames", frames, "--out", str(raw), "--res", res] + BATCH,
                   check=True, capture_output=True)


def look(src, cam, f, truth, spec_cams):
    raw = cv2.imread(str(src))
    k1 = truth.get(cam, {}).get("lens_k1", -0.06)
    hfov = spec_cams[cam].get("hfov_deg", 103.0)
    rng = np.random.default_rng([97, f])
    return L.isp(L.sensor(L.lens(raw, k1, hfov), rng))


def encode(frames_dir, mp4, crf=27):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(frames_dir / "%04d.png"),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", "-an", str(mp4)], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", required=True)
    ap.add_argument("--tracks", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--res", default="1280x720")
    ap.add_argument("--hold-s", type=float, default=4.5)
    ap.add_argument("--last-s", type=float, default=3.2)
    # landing_truth.py run on the S2 look-alike carton (scenario truth "lookalike"): the verifier's step shows it
    ap.add_argument("--lookalike-tracks", default=None)
    # the cameras the hero may push in to (the story's own route: a far view that only glimpses it is left out)
    ap.add_argument("--cameras", default="", help="comma list; empty = every camera that saw it")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tr = json.loads(Path(a.tracks).read_text(encoding="utf-8"))
    if a.cameras:
        keep = set(a.cameras.split(","))
        tr["sightings"] = [s_ for s_ in tr["sightings"] if s_["camera"] in keep]
    spec = json.loads((HUB / "hub_spec.json").read_text(encoding="utf-8"))
    spec_cams = {c["id"]: c for c in spec["cameras"]}
    truth = json.loads((HUB / "render_truth.json").read_text(encoding="utf-8"))["cameras"]
    f_min, f_max = tr["frames"]
    sc = tr["scenario"]
    pick_f = f_min + round(sc["picked_t_s"] * FPS) if sc.get("picked_t_s") is not None else None
    blind_f = f_min + round(sc["enters_blind_t_s"] * FPS) if sc.get("enters_blind_t_s") is not None else None
    segs = steps_from(tr)
    steps = []
    for i, s in enumerate(segs):
        last = i == len(segs) - 1
        n = round((a.last_s if last else a.hold_s) * FPS)
        f0, f1 = window(s, pick_f, n, f_min, f_max, end_at=(blind_f + 3 if last and blind_f else None))
        steps.append(dict(camera=s["camera"], seen_f=[s["f0"], s["f1"]], clip_f=[f0, f1],
                          event="picked" if pick_f and f0 <= pick_f <= f1 else
                          ("into_blind" if last and blind_f and f0 <= blind_f <= f1 + 3 else "carried")))
    # the showreel's fifth moment: back out of the store without it (the doorway camera; the parcel stays inside,
    # so there is no box)
    exit_f = f_min + round(sc["exits_empty_t_s"] * FPS) if sc.get("exits_empty_t_s") is not None else None
    extra = []
    if exit_f and steps and steps[-1]["event"] == "into_blind":
        extra.append(dict(camera=steps[-1]["camera"], seen_f=[exit_f, exit_f], clip_f=[max(f_min, exit_f - 15),
                                                                                       min(f_max, exit_f + 20)],
                          event="out_empty"))
    poster_f = pick_f or f_min
    tmp = out / "_raw"
    shutil.rmtree(tmp, ignore_errors=True)
    cams = sorted(spec_cams)
    print("steps", [(s["camera"], s["clip_f"], s["event"]) for s in steps], flush=True)
    render(a.blend, cams, f"{poster_f}-{poster_f}", tmp / "posters", a.res)
    (out / "posters").mkdir(exist_ok=True)
    for c in cams:
        img = look(tmp / "posters" / c / f"{poster_f:04d}.png", c, poster_f, truth, spec_cams)
        cv2.imwrite(str(out / "posters" / f"{c}.jpg"), cv2.resize(img, (640, 360), interpolation=cv2.INTER_AREA),
                    [cv2.IMWRITE_JPEG_QUALITY, 78])
    for i, st in enumerate(steps + extra):
        c, (f0, f1) = st["camera"], st["clip_f"]
        render(a.blend, [c], f"{f0}-{f1}", tmp / f"s{i}", a.res)
        d = tmp / f"s{i}_look"
        d.mkdir(parents=True, exist_ok=True)
        for k, f in enumerate(range(f0, f1 + 1)):
            cv2.imwrite(str(d / f"{k + 1:04d}.png"), look(tmp / f"s{i}" / c / f"{f:04d}.png", c, f, truth, spec_cams))
        name = f"step{i + 1}_{c}"
        encode(d, out / f"{name}.mp4")
        first = cv2.imread(str(d / "0001.png"))
        cv2.imwrite(str(out / f"{name}.jpg"), first, [cv2.IMWRITE_JPEG_QUALITY, 80])
        st.update(video=f"/landing/{name}.mp4", poster=f"/landing/{name}.jpg")
        if st["event"] == "into_blind" and blind_f:  # the doorway, 2x: half the frame round the parcel, scaled up
            sb = next(s for s in tr["sightings"] if s["camera"] == c and str(min(f1, blind_f - 1)) in s["boxes"]
                      or s["camera"] == c)
            fb = max((int(k) for k in sb["boxes"] if int(k) <= blind_f), default=int(next(iter(sb["boxes"]))))
            bx = sb["boxes"][str(fb)]
            h, w = first.shape[:2]
            cx, cy = (bx[0] + bx[2]) / 2 * w, (bx[1] + bx[3]) / 2 * h
            x0 = int(min(max(0, cx - w / 4), w / 2))
            y0 = int(min(max(0, cy - h / 4), h / 2))
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out / f"{name}.mp4"), "-vf",
                            f"crop={w // 2}:{h // 2}:{x0}:{y0},scale=640:360:flags=bicubic", "-c:v", "libx264",
                            "-preset", "veryfast", "-crf", "27", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                            "-an", str(out / f"{name}_inset.mp4")], check=True)
            st.update(inset=dict(video=f"/landing/{name}_inset.mp4", crop=[x0 / w, y0 / h, 0.5, 0.5]))
    look_info = None
    if a.lookalike_tracks and Path(a.lookalike_tracks).exists():
        lt = json.loads(Path(a.lookalike_tracks).read_text(encoding="utf-8"))
        cands = [(int(f), s_["camera"], b) for s_ in lt["sightings"] for f, b in s_["boxes"].items()]
        if cands:  # where it is seen biggest
            f, c, b = max(cands, key=lambda x: (x[2][2] - x[2][0]) * (x[2][3] - x[2][1]))
            render(a.blend, [c], f"{f}-{f}", tmp / "look", a.res)
            img = look(tmp / "look" / c / f"{f:04d}.png", c, f, truth, spec_cams)
            cv2.imwrite(str(out / "lookalike.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 80])
            look_info = dict(object=lt["object"], camera=c, frame=f, box=b, poster="/landing/lookalike.jpg",
                        t_s=round((f - f_min) / FPS, 1))
    shutil.rmtree(tmp, ignore_errors=True)
    keep = {(s["camera"], f) for s in steps for f in range(s["clip_f"][0], s["clip_f"][1] + 1)}
    sightings = [dict(camera=s["camera"], t0_s=s["t0_s"], t1_s=s["t1_s"],
                      boxes={f: b for f, b in s["boxes"].items() if (s["camera"], int(f)) in keep})
                 for s in tr["sightings"]]
    land = dict(kind=tr["kind"], note=tr["note"], story_parcel=tr["story_parcel"], fps=FPS, frames=tr["frames"],
                t0=tr["t0"], scenario=sc, cameras=tr["cameras"], camera_xy=tr["camera_xy"], path=tr["path"],
                sightings=sightings, steps=steps, moments=steps + extra, lookalike=look_info, poster_frame=poster_f)
    (out / "landing.json").write_text(json.dumps(land, indent=1), encoding="utf-8")
    sizes = {p.name: round(p.stat().st_size / 1e6, 2) for p in out.glob("*.mp4")}
    print("LANDING_ASSETS", json.dumps(dict(steps=[(s["camera"], s["clip_f"], s["event"]) for s in steps],
                                           mp4_MB=sizes)), flush=True)


if __name__ == "__main__":
    main()
