"""CCTV renders on Modal GPUs (owner_modal_0016): the same render_cctv.py, the same batch settings, on Blender 5.2.3 for
Linux in a Modal container - one container per camera / frame chunk. Test first (S2 CAM_01, 30 frames, <= US$2),
the full batch only after review AND Rexton's go.

Setup (Rexton, once): `pip install modal` then `modal token new` (his login; nothing here reads the token).
  1. pack:    blender -b --factory-startup assets/hub/build/hub_lineAb_S2.blend -P assets/hub/modal_render.py -- pack
              -> assets/hub/build/modal/hub_S2_packed.blend (every image packed: the container has no asset folders)
  2. upload:  modal volume put spoor-render assets/hub/build/modal/hub_S2_packed.blend /hub_S2_packed.blend
  3. test:    modal run assets/hub/modal_render.py::main --blend hub_S2_packed.blend --cam CAM_01 --frames 300-329
              (prints the cost estimate first; frames land in qa/review/modal_test/<mode>/CAM_01/)
  4. compare: py -X utf8 assets/hub/modal_render.py compare qa/review/modal_test/egl/CAM_01 <local frames dir>

EEVEE needs a GPU OpenGL/Vulkan context. Headless (no display) it may or may not get one in a container: mode "egl"
runs plain `blender -b` (Blender's EGL path), mode "xvfb" runs it under a virtual X server. The test tries egl and
reports what the log says about the GPU; it never switches the look to Cycles (owner rule: that needs a review).
"""
import json
import sys
import time
from pathlib import Path

HUB = Path(__file__).resolve().parent
BLENDER_URL = "https://download.blender.org/release/Blender5.2/blender-5.2.3-linux-x64.tar.xz"
BLENDER_SHA256 = "78486c018b4443efe5e75ab54c290ed8c15abafd249b862c2c9ce2530a918eec"  # blender-5.2.3.sha256 (official)
BATCH = ["--samples", "2", "--raytrace", "0", "--shadow-scale", "0.5", "--exposure", "0.2"]  # render_batch.sh
GPU, GPU_USD_S = "L4", 0.000222  # modal.com/pricing (31 Oct 2026): L4 $0.000222/s
CPU_USD_S, MEM_USD_S = 0.0000131, 0.00000222  # per core-second, per GiB-second
CORES, MEM_GIB = 4, 16


def pack():
    """Inside Blender: pack every image into the .blend and save a copy for the container."""
    import bpy
    out = HUB / "build" / "modal" / "hub_S2_packed.blend"
    out.parent.mkdir(parents=True, exist_ok=True)
    missing = [im.name for im in bpy.data.images if im.source == "FILE" and not im.packed_file
               and not Path(bpy.path.abspath(im.filepath)).exists()]
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(out), copy=True, compress=True)
    print("PACKED", out, f"{out.stat().st_size / 1e6:.0f} MB", "missing images:", missing)


def estimate(n_frames, s_per_frame=12.0, startup_s=150.0):
    """US$ for one container: GPU + CPU + memory while it runs (start-up: image pull, Blender load, shader compile)."""
    secs = startup_s + n_frames * s_per_frame
    usd = secs * (GPU_USD_S + CORES * CPU_USD_S + MEM_GIB * MEM_USD_S)
    return secs, usd


def compare(a_dir, b_dir):
    """Pixel difference between two frame folders (same names): mean / p99 / max abs diff per frame + a side-by-side
    sheet of the first frame (a | b | |a-b| x 8)."""
    import numpy as np
    from PIL import Image
    a_dir, b_dir = Path(a_dir), Path(b_dir)
    rows = []
    names = sorted(p.name for p in a_dir.glob("*.png") if (b_dir / p.name).exists())
    for n in names:
        a = np.asarray(Image.open(a_dir / n).convert("RGB"), dtype=np.int16)
        b = np.asarray(Image.open(b_dir / n).convert("RGB"), dtype=np.int16)
        d = np.abs(a - b)
        rows.append(dict(frame=n, mean=round(float(d.mean()), 3), p99=float(np.percentile(d, 99)), max=int(d.max())))
    if names:
        a = Image.open(a_dir / names[0]).convert("RGB")
        b = Image.open(b_dir / names[0]).convert("RGB")
        d = Image.fromarray(np.clip(np.abs(np.asarray(a, np.int16) - np.asarray(b, np.int16)) * 8, 0, 255).astype("uint8"))
        w, h = a.size
        sheet = Image.new("RGB", (w * 3 // 2, h // 2))
        for i, im in enumerate((a, b, d)):
            sheet.paste(im.resize((w // 2, h // 2)), (i * w // 2, 0))
        sheet.save(a_dir.parent / f"compare_{a_dir.name}.jpg", quality=90)
    out = dict(frames=len(rows), mean_of_means=round(sum(r["mean"] for r in rows) / max(1, len(rows)), 3),
               worst_p99=max((r["p99"] for r in rows), default=None), rows=rows)
    (a_dir.parent / f"compare_{a_dir.name}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}))


if "bpy" in sys.modules:  # run by Blender (-P ... -- pack)
    if "--" in sys.argv and sys.argv[sys.argv.index("--") + 1:] == ["pack"]:
        pack()
elif len(sys.argv) > 1 and sys.argv[1] == "compare":
    compare(sys.argv[2], sys.argv[3])
else:
    import modal

    image = (modal.Image.debian_slim(python_version="3.11")
             .apt_install("wget", "xz-utils", "xvfb", "xauth", "libegl1", "libgl1", "libglx0", "libopengl0",
                          "libxi6", "libxrender1", "libxkbcommon0", "libxkbcommon-x11-0", "libsm6", "libice6",
                          "libxext6", "libx11-6", "libxxf86vm1", "libxfixes3", "libxrandr2", "libxinerama1",
                          "libxcursor1", "libwayland-client0", "libwayland-egl1", "libdecor-0-0", "libgomp1",
                          "libvulkan1")
             .run_commands(f"wget -q {BLENDER_URL} -O /tmp/b.tar.xz",
                           f"echo '{BLENDER_SHA256}  /tmp/b.tar.xz' | sha256sum -c -",
                           "mkdir -p /opt/blender && tar -xJf /tmp/b.tar.xz -C /opt/blender --strip-components=1"
                           " && rm /tmp/b.tar.xz")
             .env({"NVIDIA_DRIVER_CAPABILITIES": "all"})  # graphics (EGL / Vulkan), not only compute
             .add_local_file(str(HUB / "render_cctv.py"), "/root/render_cctv.py"))
    vol = modal.Volume.from_name("spoor-render", create_if_missing=True)
    app = modal.App("spoor-cctv-render", image=image)

    @app.function(gpu=GPU, cpu=CORES, memory=MEM_GIB * 1024, volumes={"/vol": vol}, timeout=3600)
    def render(blend: str, cam: str, frames: str, res: str, mode: str) -> dict:
        import subprocess
        out = Path("/tmp/out")
        cmd = ["/opt/blender/blender", "-b", "--factory-startup", f"/vol/{blend}", "-P", "/root/render_cctv.py",
               "--", "--cams", cam, "--frames", frames, "--out", str(out), "--res", res] + BATCH
        if mode == "xvfb":
            cmd = ["xvfb-run", "-a", "-s", "-screen 0 1920x1080x24"] + cmd
        t0 = time.time()
        p = subprocess.run(cmd, capture_output=True, text=True)
        secs = time.time() - t0
        log = p.stdout + p.stderr
        gpu_lines = [ln for ln in log.splitlines() if any(k in ln for k in ("GPU", "OpenGL", "EGL", "Vulkan", "GHOST",
                                                                           "Error", "error", "CCTV"))][:60]
        files = {f.name: f.read_bytes() for f in sorted((out / cam).glob("*.png"))} if (out / cam).exists() else {}
        return dict(rc=p.returncode, secs=round(secs, 1), files=files, gpu_log=gpu_lines, log_tail=log[-4000:])

    @app.local_entrypoint()
    def main(blend: str = "hub_S2_packed.blend", cam: str = "CAM_01", frames: str = "300-329",
             res: str = "2688x1520", mode: str = "egl", out: str = "qa/review/modal_test"):
        f0, f1 = (int(x) for x in frames.split("-"))
        secs, usd = estimate(f1 - f0 + 1)
        print(f"ESTIMATE {GPU} x1, {f1 - f0 + 1} frames: ~{secs:.0f} s, ~US${usd:.2f} (budget for the test: US$2)")
        if usd > 2.0:
            raise SystemExit("over the test budget: not run")
        r = render.remote(blend, cam, frames, res, mode)
        d = Path(out) / mode / cam
        d.mkdir(parents=True, exist_ok=True)
        for n, b in r["files"].items():
            (d / n).write_bytes(b)
        rep = dict(mode=mode, rc=r["rc"], secs=r["secs"], frames=len(r["files"]),
                   s_per_frame=round(r["secs"] / max(1, len(r["files"])), 2),
                   usd=round(r["secs"] * (GPU_USD_S + CORES * CPU_USD_S + MEM_GIB * MEM_USD_S), 3),
                   gpu_log=r["gpu_log"])
        (Path(out) / f"report_{mode}_{cam}.json").write_text(json.dumps(rep, indent=1))
        (Path(out) / f"log_{mode}_{cam}.txt").write_text(r["log_tail"])
        print(json.dumps({k: v for k, v in rep.items() if k != "gpu_log"}))

    # ---------------------------------------------------------------------------------------------- full batch
    # The final-look batch (owner 0016: only after the test is reviewed AND Rexton says go; > US$5 asks him first):
    # GPU containers render frame chunks straight onto the Volume (/vol/frames/<tag>/<cam>/), then one CPU container
    # per camera runs the CCTV pass (cctv_batch.py: lens, grain, ISP, OSD clock, ONE H.265 encode over the whole
    # sequence) and returns only the .mp4; its frames are deleted from the Volume. No 38 GB of PNGs on the laptop.
    #   modal run assets/hub/modal_render.py::batch --cams CAM_01,CAM_06 --frames 1-900   (prints the estimate only)
    #   modal run assets/hub/modal_render.py::batch ... --go                                 (runs it)
    enc_image = (modal.Image.debian_slim(python_version="3.11").apt_install("ffmpeg")
                 .pip_install("numpy", "opencv-python-headless")
                 .add_local_file(str(HUB / "cctv_batch.py"), "/root/hub/cctv_batch.py")
                 .add_local_file(str(HUB / "cctv_look.py"), "/root/hub/cctv_look.py")
                 .add_local_file(str(HUB / "render_truth.json"), "/root/hub/render_truth.json")  # render side only
                 .add_local_file(str(HUB / "hub_spec.json"), "/root/hub/hub_spec.json"))
    ENC_CORES = 8

    @app.function(gpu=GPU, cpu=CORES, memory=MEM_GIB * 1024, volumes={"/vol": vol}, timeout=3600)
    def render_chunk(blend: str, cam: str, frames: str, res: str, tag: str) -> dict:
        import subprocess
        out = Path(f"/vol/frames/{tag}")
        out.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        p = subprocess.run(["/opt/blender/blender", "-b", "--factory-startup", f"/vol/{blend}", "-P",
                            "/root/render_cctv.py", "--", "--cams", cam, "--frames", frames, "--out", str(out),
                            "--res", res] + BATCH, capture_output=True, text=True)
        vol.commit()
        n = len(list((out / cam).glob("*.png"))) if (out / cam).exists() else 0
        return dict(cam=cam, frames=frames, rc=p.returncode, secs=round(time.time() - t0, 1), n_on_volume=n,
                    log_tail=(p.stdout + p.stderr)[-1500:])

    @app.function(image=enc_image, cpu=ENC_CORES, memory=16 * 1024, volumes={"/vol": vol}, timeout=3600)
    def encode(cam: str, tag: str, first: int) -> dict:
        import shutil
        import subprocess
        vol.reload()
        src = Path(f"/vol/frames/{tag}/{cam}")
        dst = Path(f"/tmp/{cam}.mp4")
        t0 = time.time()
        p = subprocess.run(["python", "/root/hub/cctv_batch.py", str(src), str(dst), "--cam", cam, "--codec", "h265",
                            "--width", "0", "--first", str(first), "--workers", str(ENC_CORES)],
                           capture_output=True, text=True, cwd="/root/hub")
        ok = p.returncode == 0 and dst.exists()
        data = dst.read_bytes() if ok else b""
        if ok:  # the frames go once the clip is made
            shutil.rmtree(src, ignore_errors=True)
            vol.commit()
        return dict(cam=cam, rc=p.returncode, secs=round(time.time() - t0, 1), mp4=data,
                    log_tail=(p.stdout + p.stderr)[-1500:])

    @app.local_entrypoint()
    def batch(blend: str = "hub_S2_packed.blend", cams: str = "CAM_01,CAM_06,CAM_09,CAM_11,CAM_13,CAM_15,CAM_19",
              frames: str = "1-900", chunk: int = 450, res: str = "2688x1520", tag: str = "S2",
              out: str = "assets/hub/build/renders/S2", s_per_frame: float = 3.5, go: bool = False):
        f0, f1 = (int(x) for x in frames.split("-"))
        cl = [c for c in cams.split(",") if c]
        jobs = [(c, f"{a}-{min(f1, a + chunk - 1)}") for c in cl for a in range(f0, f1 + 1, chunk)]
        n_fr = (f1 - f0 + 1) * len(cl)
        gpu_s = n_fr * s_per_frame + len(jobs) * 150.0
        usd = gpu_s * (GPU_USD_S + CORES * CPU_USD_S + MEM_GIB * MEM_USD_S) \
            + len(cl) * 420.0 * (ENC_CORES * CPU_USD_S + 16 * MEM_USD_S)
        print(f"ESTIMATE {GPU}: {n_fr} frames ({len(cl)} cameras x {f1 - f0 + 1}) at ~{s_per_frame} s/frame, "
              f"{len(jobs)} containers of <= {chunk} frames in parallel (+150 s start-up each), "
              f"+ {len(cl)} CPU encodes: ~{gpu_s / 3600:.1f} GPU-h, ~US${usd:.2f}")
        if not go:
            raise SystemExit("estimate only: re-run with --go once Rexton has said go (owner 0016)")
        rs = list(render_chunk.starmap([(blend, c, fr, res, tag) for c, fr in jobs]))
        bad = [r for r in rs if r["rc"] != 0]
        for r in rs:
            print(json.dumps({k: v for k, v in r.items() if k != "log_tail"}))
        if bad:
            raise SystemExit(f"{len(bad)} chunk(s) failed, not encoding: {bad[0]['log_tail']}")
        Path(out).mkdir(parents=True, exist_ok=True)
        for e in encode.starmap([(c, tag, f0) for c in cl]):
            if e["rc"] == 0 and e["mp4"]:
                (Path(out) / f"{e['cam']}.mp4").write_bytes(e["mp4"])
            print(json.dumps({k: v for k, v in e.items() if k not in ("mp4", "log_tail")}),
                  "" if e["rc"] == 0 else e["log_tail"])
        secs = sum(r["secs"] for r in rs)
        print(f"ACTUAL GPU container time {secs:.0f} s ~US${secs * (GPU_USD_S + CORES * CPU_USD_S + MEM_GIB * MEM_USD_S):.2f}"
              " (+ encodes)")
